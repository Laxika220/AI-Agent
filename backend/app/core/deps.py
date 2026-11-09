"""FastAPI dependencies: shared services and the authenticated user."""

from typing import TYPE_CHECKING, Annotated

from fastapi import Depends, Request

from app.config import Settings, get_settings
from app.core.database import MongoDatabase
from app.core.errors import AuthenticationError, RateLimitExceededError
from app.models.user import UserInDB
from app.services.redis_cache import RedisCache

if TYPE_CHECKING:
    from app.services.agent_executor import AgentRuntime
    from app.services.chain_runner import ChainRunner
    from app.services.rag_pipeline import RAGPipeline


def get_db(request: Request) -> MongoDatabase:
    return request.app.state.db


def get_cache(request: Request) -> RedisCache:
    return request.app.state.cache


def get_rag(request: Request) -> "RAGPipeline":
    return request.app.state.rag


def get_runtime(request: Request) -> "AgentRuntime":
    return request.app.state.runtime


def get_chain_runner(request: Request) -> "ChainRunner":
    return request.app.state.chain_runner


DbDep = Annotated[MongoDatabase, Depends(get_db)]
CacheDep = Annotated[RedisCache, Depends(get_cache)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


async def get_current_user(request: Request, db: DbDep) -> UserInDB:
    """Resolve the user id injected by AuthContextMiddleware into a full user."""
    user_id: str | None = getattr(request.state, "user_id", None)
    if not user_id:
        raise AuthenticationError("Not authenticated")
    doc = await db.users.find_one({"_id": user_id})
    if doc is None:
        raise AuthenticationError("User no longer exists")
    user = UserInDB.from_doc(doc)
    request.state.current_user = user
    return user


CurrentUser = Annotated[UserInDB, Depends(get_current_user)]


async def enforce_rate_limit(user: CurrentUser, cache: CacheDep) -> None:
    result = await cache.check_rate_limit(user.id)
    if not result.allowed:
        raise RateLimitExceededError(
            f"Rate limit of {result.limit} requests/minute exceeded",
            retry_after=result.reset_in,
        )
