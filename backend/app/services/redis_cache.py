"""Redis-backed caching and rate limiting.

Every method degrades gracefully: if Redis is unavailable the API keeps working
(caches miss, rate limiting fails open) and the problem is logged.
"""

import hashlib
import json
import time
from dataclasses import dataclass
from typing import Any

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_CONVERSATION_TTL_SECONDS = 24 * 60 * 60


@dataclass(frozen=True, slots=True)
class RateLimitResult:
    allowed: bool
    limit: int
    remaining: int
    reset_in: int


class RedisCache:
    def __init__(self, client: Redis, settings: Settings) -> None:
        self._redis = client
        self._settings = settings

    # ------------------------------------------------------------------ health
    async def ping(self) -> bool:
        try:
            return bool(await self._redis.ping())
        except RedisError:
            return False

    # ------------------------------------------------------- conversation cache
    @staticmethod
    def _conversation_key(conversation_id: str) -> str:
        return f"conv:{conversation_id}:messages"

    async def get_recent_messages(self, conversation_id: str) -> list[dict[str, Any]] | None:
        """Return cached messages (oldest first), or None on a cache miss."""
        key = self._conversation_key(conversation_id)
        try:
            if not await self._redis.exists(key):
                return None
            raw = await self._redis.lrange(key, 0, -1)
        except RedisError as exc:
            logger.warning("redis_get_messages_failed", error=str(exc))
            return None
        return [json.loads(item) for item in raw]

    async def set_recent_messages(self, conversation_id: str, messages: list[dict[str, Any]]) -> None:
        key = self._conversation_key(conversation_id)
        size = self._settings.conversation_cache_size
        try:
            async with self._redis.pipeline(transaction=True) as pipe:
                pipe.delete(key)
                if messages:
                    pipe.rpush(key, *[json.dumps(m, default=str) for m in messages[-size:]])
                    pipe.expire(key, _CONVERSATION_TTL_SECONDS)
                await pipe.execute()
        except RedisError as exc:
            logger.warning("redis_set_messages_failed", error=str(exc))

    async def push_message(self, conversation_id: str, message: dict[str, Any]) -> None:
        """Append a message, keeping only the last N (CONVERSATION_CACHE_SIZE)."""
        key = self._conversation_key(conversation_id)
        size = self._settings.conversation_cache_size
        try:
            async with self._redis.pipeline(transaction=True) as pipe:
                pipe.rpush(key, json.dumps(message, default=str))
                pipe.ltrim(key, -size, -1)
                pipe.expire(key, _CONVERSATION_TTL_SECONDS)
                await pipe.execute()
        except RedisError as exc:
            logger.warning("redis_push_message_failed", error=str(exc))

    async def delete_conversation(self, conversation_id: str) -> None:
        try:
            await self._redis.delete(self._conversation_key(conversation_id))
        except RedisError as exc:
            logger.warning("redis_delete_conversation_failed", error=str(exc))

    # ------------------------------------------------------------ rate limiting
    async def check_rate_limit(self, user_id: str) -> RateLimitResult:
        """Fixed-window limiter: RATE_LIMIT_PER_MINUTE requests per user per minute."""
        limit = self._settings.rate_limit_per_minute
        now = int(time.time())
        window = now // 60
        reset_in = 60 - (now % 60)
        key = f"ratelimit:{user_id}:{window}"
        try:
            async with self._redis.pipeline(transaction=True) as pipe:
                pipe.incr(key)
                pipe.expire(key, 60)
                count, _ = await pipe.execute()
        except RedisError as exc:
            logger.warning("redis_rate_limit_failed_open", error=str(exc))
            return RateLimitResult(allowed=True, limit=limit, remaining=limit, reset_in=reset_in)
        count = int(count)
        return RateLimitResult(
            allowed=count <= limit,
            limit=limit,
            remaining=max(limit - count, 0),
            reset_in=reset_in,
        )

    # ---------------------------------------------------------- embedding cache
    def _embedding_key(self, text: str) -> str:
        digest = hashlib.sha256(f"{self._settings.embedding_model}\x00{text}".encode()).hexdigest()
        return f"emb:{digest}"

    async def get_embedding(self, text: str) -> list[float] | None:
        try:
            raw = await self._redis.get(self._embedding_key(text))
        except RedisError as exc:
            logger.warning("redis_get_embedding_failed", error=str(exc))
            return None
        return json.loads(raw) if raw else None

    async def set_embedding(self, text: str, embedding: list[float]) -> None:
        try:
            await self._redis.set(
                self._embedding_key(text),
                json.dumps(embedding),
                ex=self._settings.embedding_cache_ttl_seconds,
            )
        except RedisError as exc:
            logger.warning("redis_set_embedding_failed", error=str(exc))

    # ------------------------------------------------- refresh token rotation
    async def consume_refresh_token(self, jti: str, ttl_seconds: int) -> bool:
        """Mark a refresh token as used. Returns False if it was already used (replay)."""
        try:
            result = await self._redis.set(f"refresh_used:{jti}", "1", nx=True, ex=max(ttl_seconds, 1))
        except RedisError as exc:
            logger.warning("redis_refresh_rotation_failed_open", error=str(exc))
            return True
        return bool(result)
