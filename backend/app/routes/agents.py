"""Agent CRUD."""

from fastapi import APIRouter, Response, status

from app.core.database import MongoDatabase
from app.core.deps import CacheDep, CurrentUser, DbDep
from app.core.errors import NotFoundError
from app.models.agent import AgentCreate, AgentPublic, AgentUpdate
from app.models.common import new_id, utcnow
from app.routes.knowledge_bases import get_owned_knowledge_base

router = APIRouter(prefix="/agents", tags=["agents"])


async def get_owned_agent(db: MongoDatabase, agent_id: str, owner_id: str) -> AgentPublic:
    doc = await db.agents.find_one({"_id": agent_id, "owner_id": owner_id})
    if doc is None:
        raise NotFoundError("Agent not found")
    return AgentPublic.from_doc(doc)


@router.get("", response_model=list[AgentPublic])
async def list_agents(user: CurrentUser, db: DbDep) -> list[AgentPublic]:
    docs = await db.agents.find({"owner_id": user.id}).sort("created_at", -1).to_list(None)
    return [AgentPublic.from_doc(d) for d in docs]


@router.post("", response_model=AgentPublic, status_code=status.HTTP_201_CREATED)
async def create_agent(payload: AgentCreate, user: CurrentUser, db: DbDep) -> AgentPublic:
    if payload.knowledge_base_id:
        await get_owned_knowledge_base(db, payload.knowledge_base_id, user.id)
    now = utcnow()
    doc = {"_id": new_id(), "owner_id": user.id, **payload.model_dump(), "created_at": now, "updated_at": now}
    await db.agents.insert_one(doc)
    return AgentPublic.from_doc(doc)


@router.get("/{agent_id}", response_model=AgentPublic)
async def get_agent(agent_id: str, user: CurrentUser, db: DbDep) -> AgentPublic:
    return await get_owned_agent(db, agent_id, user.id)


@router.put("/{agent_id}", response_model=AgentPublic)
async def update_agent(agent_id: str, payload: AgentUpdate, user: CurrentUser, db: DbDep) -> AgentPublic:
    await get_owned_agent(db, agent_id, user.id)
    changes = payload.model_dump(exclude_unset=True)
    # Non-nullable fields: ignore explicit nulls rather than corrupting the record.
    changes = {k: v for k, v in changes.items() if v is not None or k in {"knowledge_base_id", "model"}}
    if changes.get("knowledge_base_id"):
        await get_owned_knowledge_base(db, changes["knowledge_base_id"], user.id)
    if changes:
        changes["updated_at"] = utcnow()
        await db.agents.update_one({"_id": agent_id}, {"$set": changes})
    return await get_owned_agent(db, agent_id, user.id)


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(agent_id: str, user: CurrentUser, db: DbDep, cache: CacheDep) -> Response:
    await get_owned_agent(db, agent_id, user.id)
    conversation_ids = await db.conversations.distinct("_id", {"agent_id": agent_id, "owner_id": user.id})
    await db.messages.delete_many({"conversation_id": {"$in": conversation_ids}})
    await db.conversations.delete_many({"_id": {"$in": conversation_ids}})
    for conversation_id in conversation_ids:
        await cache.delete_conversation(conversation_id)
    await db.agents.delete_one({"_id": agent_id})
    return Response(status_code=status.HTTP_204_NO_CONTENT)
