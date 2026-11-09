"""FastAPI application factory and lifespan wiring."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis

from app.config import get_settings
from app.core.database import create_mongo_client, ensure_indexes
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.core.middleware import AuthContextMiddleware, RequestLoggingMiddleware
from app.models.common import ErrorResponse
from app.routes import agents, auth, chains, chat, documents, knowledge_bases, tools
from app.services.agent_executor import AgentRuntime
from app.services.chain_runner import ChainRunner
from app.services.rag_pipeline import RAGPipeline
from app.services.redis_cache import RedisCache
from app.utils.embeddings import get_embedding_model

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_json)
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)

    mongo = create_mongo_client(settings.mongo_uri)
    db = mongo[settings.mongo_db]
    await ensure_indexes(db)

    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    cache = RedisCache(redis, settings)
    if not await cache.ping():
        logger.warning("redis_unavailable", url=settings.redis_url)

    embedder = get_embedding_model(settings.embedding_model)
    if settings.preload_embedding_model:
        await asyncio.to_thread(embedder.load)

    rag = RAGPipeline(settings, embedder, cache)
    runtime = AgentRuntime(settings, rag)

    app.state.db = db
    app.state.cache = cache
    app.state.rag = rag
    app.state.runtime = runtime
    app.state.chain_runner = ChainRunner(runtime)

    logger.info("startup_complete", model=settings.model_name, base_url=settings.openai_base_url or "openai")
    try:
        yield
    finally:
        await redis.aclose()
        await mongo.close()
        logger.info("shutdown_complete")


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_json)

    app = FastAPI(
        title=settings.app_name,
        version="1.0.0",
        description="Multi-agent AI platform with tool-calling, RAG and agent chaining.",
        lifespan=lifespan,
        responses={
            401: {"model": ErrorResponse},
            404: {"model": ErrorResponse},
            422: {"model": ErrorResponse},
        },
    )

    # Middleware runs outermost-last-added: CORS wraps everything so errors carry CORS headers.
    app.add_middleware(AuthContextMiddleware)
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-Id", "Retry-After"],
    )

    register_exception_handlers(app)

    for router in (
        auth.router,
        agents.router,
        knowledge_bases.router,
        documents.router,
        chat.router,
        chains.router,
        tools.router,
    ):
        app.include_router(router)

    @app.get("/health", tags=["health"])
    async def health(request: Request) -> dict[str, Any]:
        state = request.app.state
        try:
            await state.db.command("ping")
            mongo_ok = True
        except Exception:
            mongo_ok = False
        redis_ok = await state.cache.ping()
        chroma_ok = await asyncio.to_thread(state.rag.heartbeat)
        return {
            "status": "ok" if mongo_ok else "degraded",
            "services": {"mongodb": mongo_ok, "redis": redis_ok, "chromadb": chroma_ok},
        }

    return app


app = create_app()
