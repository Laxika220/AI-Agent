"""Knowledge base CRUD. A knowledge base groups documents an agent can retrieve from."""

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.core.deps import CurrentUser, DbDep, SettingsDep, get_rag
from app.core.errors import NotFoundError
from app.models.common import new_id, utcnow
from app.models.document import KnowledgeBaseCreate, KnowledgeBasePublic
from app.services.rag_pipeline import RAGPipeline

router = APIRouter(prefix="/knowledge-bases", tags=["knowledge-bases"])

RagDep = Annotated[RAGPipeline, Depends(get_rag)]


async def get_owned_knowledge_base(db: DbDep, kb_id: str, owner_id: str) -> dict:
    doc = await db.knowledge_bases.find_one({"_id": kb_id, "owner_id": owner_id})
    if doc is None:
        raise NotFoundError("Knowledge base not found")
    return doc


@router.get("", response_model=list[KnowledgeBasePublic])
async def list_knowledge_bases(user: CurrentUser, db: DbDep) -> list[KnowledgeBasePublic]:
    kbs = await db.knowledge_bases.find({"owner_id": user.id}).sort("created_at", -1).to_list(None)
    counts = {
        row["_id"]: row["count"]
        async for row in await db.documents.aggregate(
            [{"$match": {"owner_id": user.id}}, {"$group": {"_id": "$knowledge_base_id", "count": {"$sum": 1}}}]
        )
    }
    return [KnowledgeBasePublic.from_doc({**kb, "document_count": counts.get(kb["_id"], 0)}) for kb in kbs]


@router.post("", response_model=KnowledgeBasePublic, status_code=status.HTTP_201_CREATED)
async def create_knowledge_base(
    payload: KnowledgeBaseCreate, user: CurrentUser, db: DbDep
) -> KnowledgeBasePublic:
    doc = {"_id": new_id(), "owner_id": user.id, **payload.model_dump(), "created_at": utcnow()}
    await db.knowledge_bases.insert_one(doc)
    return KnowledgeBasePublic.from_doc(doc)


@router.delete("/{kb_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_knowledge_base(
    kb_id: str, user: CurrentUser, db: DbDep, rag: RagDep, settings: SettingsDep
) -> Response:
    """Delete a knowledge base, its documents, stored files and vectors."""
    await get_owned_knowledge_base(db, kb_id, user.id)
    async for doc in db.documents.find({"knowledge_base_id": kb_id, "owner_id": user.id}):
        Path(settings.upload_dir, doc["stored_name"]).unlink(missing_ok=True)
    await db.documents.delete_many({"knowledge_base_id": kb_id, "owner_id": user.id})
    await rag.delete_knowledge_base(kb_id)
    await db.knowledge_bases.delete_one({"_id": kb_id})
    # Detach from agents that referenced it.
    await db.agents.update_many(
        {"owner_id": user.id, "knowledge_base_id": kb_id},
        {"$set": {"knowledge_base_id": None, "updated_at": utcnow()}},
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
