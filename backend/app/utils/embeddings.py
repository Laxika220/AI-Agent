"""Local embedding generation (sentence-transformers) and MMR re-ranking."""

import threading
from collections.abc import Sequence
from functools import lru_cache
from typing import TYPE_CHECKING

import numpy as np

from app.core.logging import get_logger

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

logger = get_logger(__name__)


class EmbeddingModel:
    """Lazily-loaded, thread-safe wrapper around a SentenceTransformer.

    Embeddings are L2-normalised, so a dot product equals cosine similarity.
    Methods are synchronous (CPU-bound); call them via `asyncio.to_thread`.
    """

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self._model: SentenceTransformer | None = None
        self._lock = threading.Lock()

    def _get_model(self) -> "SentenceTransformer":
        if self._model is None:
            with self._lock:
                if self._model is None:
                    from sentence_transformers import SentenceTransformer

                    logger.info("loading_embedding_model", model=self.model_name)
                    self._model = SentenceTransformer(self.model_name)
        return self._model

    def load(self) -> None:
        self._get_model()

    def embed_documents(self, texts: Sequence[str], batch_size: int = 32) -> list[list[float]]:
        if not texts:
            return []
        vectors = self._get_model().encode(
            list(texts),
            batch_size=batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
            convert_to_numpy=True,
        )
        return vectors.astype(np.float32).tolist()

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


@lru_cache
def get_embedding_model(model_name: str) -> EmbeddingModel:
    return EmbeddingModel(model_name)


def maximal_marginal_relevance(
    query_embedding: Sequence[float],
    candidate_embeddings: Sequence[Sequence[float]],
    k: int,
    lambda_mult: float = 0.5,
) -> list[int]:
    """Select `k` candidates balancing relevance to the query and mutual diversity.

    score(d) = λ · sim(q, d) − (1 − λ) · max_{s ∈ selected} sim(d, s)

    Returns indices into `candidate_embeddings`, in selection order.
    """
    if k <= 0 or len(candidate_embeddings) == 0:
        return []

    query = np.asarray(query_embedding, dtype=np.float32)
    docs = np.asarray(candidate_embeddings, dtype=np.float32)
    query = query / (np.linalg.norm(query) or 1.0)
    norms = np.linalg.norm(docs, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    docs = docs / norms

    relevance = docs @ query
    selected: list[int] = [int(np.argmax(relevance))]
    k = min(k, len(docs))
    while len(selected) < k:
        similarity_to_selected = docs @ docs[selected].T  # (n, len(selected))
        redundancy = similarity_to_selected.max(axis=1)
        scores = lambda_mult * relevance - (1 - lambda_mult) * redundancy
        scores[selected] = -np.inf
        selected.append(int(np.argmax(scores)))
    return selected
