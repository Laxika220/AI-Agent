"""RAG pipeline: extract → chunk → embed → store in ChromaDB → retrieve with MMR.

Each knowledge base maps to one Chroma collection (`kb_<id>`, cosine space).
Each chunk is stored with metadata `{doc_id, chunk_index, source_file}`.
"""

import asyncio
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any

from app.config import Settings
from app.core.errors import ExternalServiceError
from app.core.logging import get_logger
from app.models.document import RetrievedChunk
from app.services.redis_cache import RedisCache
from app.utils.chunking import chunk_text
from app.utils.embeddings import EmbeddingModel, maximal_marginal_relevance
from app.utils.extraction import extract_text

if TYPE_CHECKING:
    from chromadb.api import ClientAPI
    from chromadb.api.models.Collection import Collection

logger = get_logger(__name__)

_ADD_BATCH_SIZE = 256


class RAGPipeline:
    def __init__(self, settings: Settings, embedder: EmbeddingModel, cache: RedisCache | None = None) -> None:
        self._settings = settings
        self._embedder = embedder
        self._cache = cache
        self._client: ClientAPI | None = None
        self._client_lock = threading.Lock()

    # ------------------------------------------------------------ chroma client
    def _get_client(self) -> "ClientAPI":
        """Connect lazily so the API can boot before ChromaDB is reachable."""
        if self._client is None:
            with self._client_lock:
                if self._client is None:
                    import chromadb
                    from chromadb.config import Settings as ChromaSettings

                    chroma_settings = ChromaSettings(anonymized_telemetry=False)
                    try:
                        if self._settings.chroma_host:
                            self._client = chromadb.HttpClient(
                                host=self._settings.chroma_host,
                                port=self._settings.chroma_port,
                                settings=chroma_settings,
                            )
                        else:
                            self._client = chromadb.PersistentClient(
                                path=self._settings.chroma_persist_dir, settings=chroma_settings
                            )
                    except Exception as exc:  # chromadb raises a variety of errors
                        raise ExternalServiceError(f"Could not connect to ChromaDB: {exc}") from exc
        return self._client

    @staticmethod
    def collection_name(knowledge_base_id: str) -> str:
        return f"kb_{knowledge_base_id}"

    def _collection(self, knowledge_base_id: str) -> "Collection":
        return self._get_client().get_or_create_collection(
            name=self.collection_name(knowledge_base_id),
            metadata={"hnsw:space": "cosine"},
        )

    def heartbeat(self) -> bool:
        try:
            self._get_client().heartbeat()
            return True
        except Exception:
            return False

    # ---------------------------------------------------------------- ingestion
    def _ingest_sync(self, doc_id: str, knowledge_base_id: str, file_path: Path, source_file: str) -> int:
        text = extract_text(file_path)
        chunks = chunk_text(text, self._settings.chunk_size, self._settings.chunk_overlap)
        if not chunks:
            raise ValueError("No extractable text found in document")

        embeddings = self._embedder.embed_documents(chunks)
        collection = self._collection(knowledge_base_id)
        for start in range(0, len(chunks), _ADD_BATCH_SIZE):
            end = start + _ADD_BATCH_SIZE
            collection.add(
                ids=[f"{doc_id}:{i}" for i in range(start, min(end, len(chunks)))],
                documents=chunks[start:end],
                embeddings=embeddings[start:end],
                metadatas=[
                    {"doc_id": doc_id, "chunk_index": i, "source_file": source_file}
                    for i in range(start, min(end, len(chunks)))
                ],
            )
        logger.info("document_ingested", doc_id=doc_id, chunks=len(chunks), kb_id=knowledge_base_id)
        return len(chunks)

    async def ingest_document(
        self, *, doc_id: str, knowledge_base_id: str, file_path: Path, source_file: str
    ) -> int:
        """Process a stored upload end-to-end. Returns the number of chunks stored."""
        return await asyncio.to_thread(self._ingest_sync, doc_id, knowledge_base_id, file_path, source_file)

    async def delete_document(self, knowledge_base_id: str, doc_id: str) -> None:
        def _delete() -> None:
            self._collection(knowledge_base_id).delete(where={"doc_id": doc_id})

        await asyncio.to_thread(_delete)

    async def delete_knowledge_base(self, knowledge_base_id: str) -> None:
        def _drop() -> None:
            try:
                self._get_client().delete_collection(self.collection_name(knowledge_base_id))
            except Exception as exc:  # collection may never have been created
                logger.info("delete_collection_skipped", kb_id=knowledge_base_id, reason=str(exc))

        await asyncio.to_thread(_drop)

    # ---------------------------------------------------------------- retrieval
    async def embed_query(self, query: str) -> list[float]:
        if self._cache is not None:
            cached = await self._cache.get_embedding(query)
            if cached is not None:
                return cached
        embedding = await asyncio.to_thread(self._embedder.embed_query, query)
        if self._cache is not None:
            await self._cache.set_embedding(query, embedding)
        return embedding

    async def retrieve(
        self,
        knowledge_base_id: str,
        query: str,
        *,
        top_k: int | None = None,
        fetch_k: int | None = None,
        lambda_mult: float | None = None,
    ) -> list[RetrievedChunk]:
        """Cosine-similarity search for `fetch_k` candidates, then MMR down to `top_k`."""
        top_k = top_k or self._settings.retrieval_top_k
        fetch_k = max(fetch_k or self._settings.retrieval_fetch_k, top_k)
        lambda_mult = self._settings.mmr_lambda if lambda_mult is None else lambda_mult

        query_embedding = await self.embed_query(query)

        def _query() -> dict[str, Any] | None:
            collection = self._collection(knowledge_base_id)
            count = collection.count()
            if count == 0:
                return None
            return collection.query(
                query_embeddings=[query_embedding],
                n_results=min(fetch_k, count),
                include=["documents", "metadatas", "distances", "embeddings"],
            )

        result = await asyncio.to_thread(_query)
        if not result or not result["ids"] or not result["ids"][0]:
            return []

        documents: list[str] = result["documents"][0]
        metadatas: list[dict[str, Any]] = result["metadatas"][0]
        distances: list[float] = result["distances"][0]
        embeddings = result["embeddings"][0]

        selected = maximal_marginal_relevance(query_embedding, embeddings, top_k, lambda_mult)
        return [
            RetrievedChunk(
                text=documents[i],
                doc_id=str(metadatas[i].get("doc_id", "")),
                source_file=str(metadatas[i].get("source_file", "")),
                chunk_index=int(metadatas[i].get("chunk_index", 0)),
                score=round(1.0 - float(distances[i]), 4),
            )
            for i in selected
        ]
