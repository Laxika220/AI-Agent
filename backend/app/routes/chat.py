"""Chat with an agent over Server-Sent Events, plus conversation history."""

import json
from collections.abc import AsyncIterator
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Response, status
from fastapi.responses import StreamingResponse

from app.core.database import MongoDatabase
from app.core.deps import CacheDep, CurrentUser, DbDep, SettingsDep, enforce_rate_limit, get_runtime
from app.core.errors import AppError, BadRequestError, NotFoundError
from app.core.logging import get_logger
from app.models.agent import AgentPublic
from app.models.common import new_id, utcnow
from app.models.conversation import ChatRequest, Conversation, ConversationDetail, Message, MessageRole
from app.routes.agents import get_owned_agent
from app.services.agent_executor import AgentRuntime
from app.services.redis_cache import RedisCache

router = APIRouter(prefix="/chat", tags=["chat"])
logger = get_logger(__name__)

RuntimeDep = Annotated[AgentRuntime, Depends(get_runtime)]

_SSE_HEADERS = {"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"}


def sse(event: str, data: Any) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str, ensure_ascii=False)}\n\n"


def _error_message(exc: Exception) -> str:
    if isinstance(exc, AppError):
        return exc.message
    return f"{type(exc).__name__}: {exc}"[:500]


async def _load_history(
    db: MongoDatabase, cache: RedisCache, conversation_id: str, limit: int
) -> list[dict[str, Any]]:
    """Recent messages from Redis, falling back to MongoDB (and warming the cache)."""
    cached = await cache.get_recent_messages(conversation_id)
    if cached is not None:
        return cached
    docs = (
        await db.messages.find({"conversation_id": conversation_id})
        .sort("created_at", -1)
        .limit(limit)
        .to_list(None)
    )
    history = [{"role": d["role"], "content": d["content"]} for d in reversed(docs)]
    await cache.set_recent_messages(conversation_id, history)
    return history


async def _event_stream(
    *,
    db: MongoDatabase,
    cache: RedisCache,
    runtime: AgentRuntime,
    agent: AgentPublic,
    conversation_id: str,
    user_message_id: str,
    message: str,
    history: list[dict[str, Any]],
) -> AsyncIterator[str]:
    yield sse("conversation", {"conversation_id": conversation_id, "user_message_id": user_message_id})
    final: dict[str, Any] | None = None
    try:
        async for event in runtime.stream(agent, message, history):
            if event["type"] == "final":
                final = event
            else:
                yield sse(event["type"], event)
    except Exception as exc:
        logger.exception("chat_stream_failed", agent_id=agent.id, conversation_id=conversation_id)
        yield sse("error", {"message": _error_message(exc)})
        return

    if final is None:
        yield sse("error", {"message": "Agent produced no response"})
        return

    assistant_doc = {
        "_id": new_id(),
        "conversation_id": conversation_id,
        "role": MessageRole.ASSISTANT,
        "content": final["content"],
        "tool_calls": final["tool_calls"],
        "created_at": utcnow(),
    }
    await db.messages.insert_one(assistant_doc)
    await db.conversations.update_one({"_id": conversation_id}, {"$set": {"updated_at": utcnow()}})
    await cache.push_message(conversation_id, {"role": "assistant", "content": final["content"]})
    yield sse("done", Message.from_doc(assistant_doc).model_dump(mode="json"))


@router.post(
    "/{agent_id}",
    dependencies=[Depends(enforce_rate_limit)],
    responses={200: {"content": {"text/event-stream": {}}, "description": "SSE stream of agent events"}},
)
async def chat(
    agent_id: str,
    payload: ChatRequest,
    user: CurrentUser,
    db: DbDep,
    cache: CacheDep,
    runtime: RuntimeDep,
    settings: SettingsDep,
) -> StreamingResponse:
    """Send a message to an agent and stream the response.

    Events: `conversation`, `token`, `tool_start`, `tool_end`, `retrieval`, `done`, `error`.
    """
    agent = await get_owned_agent(db, agent_id, user.id)
    now = utcnow()

    if payload.conversation_id:
        conversation = await db.conversations.find_one({"_id": payload.conversation_id, "owner_id": user.id})
        if conversation is None:
            raise NotFoundError("Conversation not found")
        if conversation["agent_id"] != agent_id:
            raise BadRequestError("Conversation belongs to a different agent")
        conversation_id = conversation["_id"]
    else:
        conversation_id = new_id()
        title = payload.message.strip().splitlines()[0][:60] or "New conversation"
        await db.conversations.insert_one(
            {
                "_id": conversation_id,
                "owner_id": user.id,
                "agent_id": agent_id,
                "title": title,
                "created_at": now,
                "updated_at": now,
            }
        )

    history = await _load_history(db, cache, conversation_id, settings.conversation_cache_size)

    user_message_id = new_id()
    await db.messages.insert_one(
        {
            "_id": user_message_id,
            "conversation_id": conversation_id,
            "role": MessageRole.USER,
            "content": payload.message,
            "tool_calls": [],
            "created_at": now,
        }
    )
    await cache.push_message(conversation_id, {"role": "user", "content": payload.message})

    return StreamingResponse(
        _event_stream(
            db=db,
            cache=cache,
            runtime=runtime,
            agent=agent,
            conversation_id=conversation_id,
            user_message_id=user_message_id,
            message=payload.message,
            history=history,
        ),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )


@router.get("/conversations", response_model=list[Conversation])
async def list_conversations(
    user: CurrentUser,
    db: DbDep,
    agent_id: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[Conversation]:
    query: dict[str, str] = {"owner_id": user.id}
    if agent_id:
        query["agent_id"] = agent_id
    docs = await db.conversations.find(query).sort("updated_at", -1).limit(limit).to_list(None)
    return [Conversation.from_doc(d) for d in docs]


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(conversation_id: str, user: CurrentUser, db: DbDep) -> ConversationDetail:
    doc = await db.conversations.find_one({"_id": conversation_id, "owner_id": user.id})
    if doc is None:
        raise NotFoundError("Conversation not found")
    messages = await db.messages.find({"conversation_id": conversation_id}).sort("created_at", 1).to_list(None)
    return ConversationDetail.from_doc({**doc, "messages": [Message.from_doc(m) for m in messages]})


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(conversation_id: str, user: CurrentUser, db: DbDep, cache: CacheDep) -> Response:
    result = await db.conversations.delete_one({"_id": conversation_id, "owner_id": user.id})
    if result.deleted_count == 0:
        raise NotFoundError("Conversation not found")
    await db.messages.delete_many({"conversation_id": conversation_id})
    await cache.delete_conversation(conversation_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
