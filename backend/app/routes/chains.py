"""Multi-agent chain CRUD and execution."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Response, status

from app.core.database import MongoDatabase
from app.core.deps import CurrentUser, DbDep, enforce_rate_limit, get_chain_runner
from app.core.errors import BadRequestError, NotFoundError
from app.models.agent import AgentPublic
from app.models.chain import ChainCreate, ChainPublic, ChainRunRequest, ChainRunResult, ChainUpdate
from app.models.common import new_id, utcnow
from app.services.chain_runner import ChainRunner

router = APIRouter(prefix="/chains", tags=["chains"])

RunnerDep = Annotated[ChainRunner, Depends(get_chain_runner)]


async def _get_owned_chain(db: MongoDatabase, chain_id: str, owner_id: str) -> ChainPublic:
    doc = await db.chains.find_one({"_id": chain_id, "owner_id": owner_id})
    if doc is None:
        raise NotFoundError("Chain not found")
    return ChainPublic.from_doc(doc)


async def _load_agents(db: MongoDatabase, agent_ids: set[str], owner_id: str) -> dict[str, AgentPublic]:
    docs = await db.agents.find({"_id": {"$in": list(agent_ids)}, "owner_id": owner_id}).to_list(None)
    agents = {d["_id"]: AgentPublic.from_doc(d) for d in docs}
    missing = agent_ids - agents.keys()
    if missing:
        raise BadRequestError("Chain references agents that do not exist", details={"agent_ids": sorted(missing)})
    return agents


@router.get("", response_model=list[ChainPublic])
async def list_chains(user: CurrentUser, db: DbDep) -> list[ChainPublic]:
    docs = await db.chains.find({"owner_id": user.id}).sort("created_at", -1).to_list(None)
    return [ChainPublic.from_doc(d) for d in docs]


@router.post("", response_model=ChainPublic, status_code=status.HTTP_201_CREATED)
async def create_chain(payload: ChainCreate, user: CurrentUser, db: DbDep) -> ChainPublic:
    await _load_agents(db, {s.agent_id for s in payload.steps}, user.id)
    now = utcnow()
    doc: dict[str, Any] = {
        "_id": new_id(),
        "owner_id": user.id,
        **payload.model_dump(),
        "created_at": now,
        "updated_at": now,
    }
    await db.chains.insert_one(doc)
    return ChainPublic.from_doc(doc)


@router.get("/{chain_id}", response_model=ChainPublic)
async def get_chain(chain_id: str, user: CurrentUser, db: DbDep) -> ChainPublic:
    return await _get_owned_chain(db, chain_id, user.id)


@router.put("/{chain_id}", response_model=ChainPublic)
async def update_chain(chain_id: str, payload: ChainUpdate, user: CurrentUser, db: DbDep) -> ChainPublic:
    await _get_owned_chain(db, chain_id, user.id)
    await _load_agents(db, {s.agent_id for s in payload.steps}, user.id)
    await db.chains.update_one({"_id": chain_id}, {"$set": {**payload.model_dump(), "updated_at": utcnow()}})
    return await _get_owned_chain(db, chain_id, user.id)


@router.delete("/{chain_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chain(chain_id: str, user: CurrentUser, db: DbDep) -> Response:
    result = await db.chains.delete_one({"_id": chain_id, "owner_id": user.id})
    if result.deleted_count == 0:
        raise NotFoundError("Chain not found")
    await db.chain_runs.delete_many({"chain_id": chain_id})
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{chain_id}/run", response_model=ChainRunResult, dependencies=[Depends(enforce_rate_limit)])
async def run_chain(
    chain_id: str, payload: ChainRunRequest, user: CurrentUser, db: DbDep, runner: RunnerDep
) -> ChainRunResult:
    """Execute a chain and return its full execution trace (also persisted)."""
    chain = await _get_owned_chain(db, chain_id, user.id)
    agents = await _load_agents(db, {s.agent_id for s in chain.steps}, user.id)
    result = await runner.run(chain, agents, payload.input)
    doc = result.model_dump(exclude={"id"})
    doc["_id"] = result.id
    await db.chain_runs.insert_one(doc)
    return result


@router.get("/{chain_id}/runs", response_model=list[ChainRunResult])
async def list_chain_runs(
    chain_id: str,
    user: CurrentUser,
    db: DbDep,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> list[ChainRunResult]:
    await _get_owned_chain(db, chain_id, user.id)
    docs = await db.chain_runs.find({"chain_id": chain_id}).sort("created_at", -1).limit(limit).to_list(None)
    return [ChainRunResult.from_doc(d) for d in docs]
