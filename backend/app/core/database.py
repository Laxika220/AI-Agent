"""MongoDB connection helpers (PyMongo native async API)."""

from typing import Any

from pymongo import ASCENDING, DESCENDING, AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase

from app.core.logging import get_logger

logger = get_logger(__name__)

MongoDatabase = AsyncDatabase[dict[str, Any]]


def create_mongo_client(uri: str) -> AsyncMongoClient[dict[str, Any]]:
    # tz_aware so datetimes round-trip as timezone-aware UTC values.
    return AsyncMongoClient(uri, tz_aware=True, serverSelectionTimeoutMS=10_000)


async def ensure_indexes(db: MongoDatabase) -> None:
    """Create the indexes the API relies on. Idempotent."""
    await db.users.create_index("email", unique=True)
    await db.agents.create_index([("owner_id", ASCENDING), ("created_at", DESCENDING)])
    await db.knowledge_bases.create_index([("owner_id", ASCENDING), ("created_at", DESCENDING)])
    await db.documents.create_index([("owner_id", ASCENDING), ("knowledge_base_id", ASCENDING)])
    await db.conversations.create_index([("owner_id", ASCENDING), ("updated_at", DESCENDING)])
    await db.conversations.create_index("agent_id")
    await db.messages.create_index([("conversation_id", ASCENDING), ("created_at", ASCENDING)])
    await db.chains.create_index([("owner_id", ASCENDING), ("created_at", DESCENDING)])
    await db.chain_runs.create_index([("chain_id", ASCENDING), ("created_at", DESCENDING)])
    logger.info("mongo_indexes_ready")
