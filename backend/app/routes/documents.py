"""Document upload, listing and deletion.

Uploads are streamed to disk, recorded as `pending`, then processed (chunk → embed →
store) in a background task; clients poll `GET /documents` for status changes.
"""

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Query, Response, UploadFile, status

from app.config import Settings
from app.core.database import MongoDatabase
from app.core.deps import CurrentUser, DbDep, SettingsDep, get_rag
from app.core.errors import BadRequestError, NotFoundError, PayloadTooLargeError
from app.core.logging import get_logger
from app.models.common import new_id, utcnow
from app.models.document import SUPPORTED_EXTENSIONS, DocumentPublic, DocumentStatus
from app.routes.knowledge_bases import get_owned_knowledge_base
from app.services.rag_pipeline import RAGPipeline

router = APIRouter(prefix="/documents", tags=["documents"])
logger = get_logger(__name__)

RagDep = Annotated[RAGPipeline, Depends(get_rag)]

_READ_CHUNK = 1024 * 1024


async def _save_upload(upload: UploadFile, destination: Path, max_bytes: int) -> int:
    """Stream an upload to disk, enforcing the size limit. Returns bytes written."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    try:
        with destination.open("wb") as out:
            while chunk := await upload.read(_READ_CHUNK):
                written += len(chunk)
                if written > max_bytes:
                    raise PayloadTooLargeError(f"File exceeds the {max_bytes // (1024 * 1024)} MB limit")
                out.write(chunk)
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    return written


async def process_document(db: MongoDatabase, rag: RAGPipeline, settings: Settings, doc_id: str) -> None:
    """Background job: run the RAG ingestion and record the outcome."""
    doc = await db.documents.find_one({"_id": doc_id})
    if doc is None:
        return
    await db.documents.update_one(
        {"_id": doc_id}, {"$set": {"status": DocumentStatus.PROCESSING, "updated_at": utcnow()}}
    )
    try:
        chunk_count = await rag.ingest_document(
            doc_id=doc_id,
            knowledge_base_id=doc["knowledge_base_id"],
            file_path=Path(settings.upload_dir, doc["stored_name"]),
            source_file=doc["filename"],
        )
    except Exception as exc:
        logger.exception("document_processing_failed", doc_id=doc_id)
        await db.documents.update_one(
            {"_id": doc_id},
            {"$set": {"status": DocumentStatus.FAILED, "error": str(exc)[:500], "updated_at": utcnow()}},
        )
        return
    await db.documents.update_one(
        {"_id": doc_id},
        {"$set": {"status": DocumentStatus.READY, "chunk_count": chunk_count, "error": None, "updated_at": utcnow()}},
    )


@router.post("/upload", response_model=DocumentPublic, status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    background_tasks: BackgroundTasks,
    user: CurrentUser,
    db: DbDep,
    rag: RagDep,
    settings: SettingsDep,
    file: Annotated[UploadFile, File(description="PDF, TXT, MD or DOCX file")],
    knowledge_base_id: Annotated[str, Form()],
) -> DocumentPublic:
    await get_owned_knowledge_base(db, knowledge_base_id, user.id)

    filename = Path(file.filename or "upload").name
    extension = Path(filename).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise BadRequestError(
            f"Unsupported file type '{extension or 'none'}'. Allowed: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    doc_id = new_id()
    stored_name = f"{doc_id}{extension}"
    size = await _save_upload(file, Path(settings.upload_dir, stored_name), settings.max_upload_bytes)
    if size == 0:
        Path(settings.upload_dir, stored_name).unlink(missing_ok=True)
        raise BadRequestError("Uploaded file is empty")

    now = utcnow()
    doc = {
        "_id": doc_id,
        "owner_id": user.id,
        "knowledge_base_id": knowledge_base_id,
        "filename": filename,
        "stored_name": stored_name,
        "content_type": file.content_type,
        "size_bytes": size,
        "status": DocumentStatus.PENDING,
        "chunk_count": 0,
        "error": None,
        "created_at": now,
        "updated_at": now,
    }
    await db.documents.insert_one(doc)
    background_tasks.add_task(process_document, db, rag, settings, doc_id)
    logger.info("document_uploaded", doc_id=doc_id, filename=filename, size=size)
    return DocumentPublic.from_doc(doc)


@router.get("", response_model=list[DocumentPublic])
async def list_documents(
    user: CurrentUser,
    db: DbDep,
    knowledge_base_id: Annotated[str | None, Query()] = None,
) -> list[DocumentPublic]:
    query: dict[str, str] = {"owner_id": user.id}
    if knowledge_base_id:
        query["knowledge_base_id"] = knowledge_base_id
    docs = await db.documents.find(query).sort("created_at", -1).to_list(None)
    return [DocumentPublic.from_doc(d) for d in docs]


@router.get("/{doc_id}", response_model=DocumentPublic)
async def get_document(doc_id: str, user: CurrentUser, db: DbDep) -> DocumentPublic:
    doc = await db.documents.find_one({"_id": doc_id, "owner_id": user.id})
    if doc is None:
        raise NotFoundError("Document not found")
    return DocumentPublic.from_doc(doc)


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    doc_id: str, user: CurrentUser, db: DbDep, rag: RagDep, settings: SettingsDep
) -> Response:
    doc = await db.documents.find_one({"_id": doc_id, "owner_id": user.id})
    if doc is None:
        raise NotFoundError("Document not found")
    await rag.delete_document(doc["knowledge_base_id"], doc_id)
    Path(settings.upload_dir, doc["stored_name"]).unlink(missing_ok=True)
    await db.documents.delete_one({"_id": doc_id})
    return Response(status_code=status.HTTP_204_NO_CONTENT)
