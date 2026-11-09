"""Shared helpers for Pydantic schemas backed by MongoDB documents."""

import uuid
from datetime import UTC, datetime
from typing import Any, Self

from pydantic import BaseModel, ConfigDict


def utcnow() -> datetime:
    return datetime.now(UTC)


def new_id() -> str:
    """IDs are UUID4 hex strings: URL-safe and simple to serialize."""
    return uuid.uuid4().hex


class MongoModel(BaseModel):
    """A schema that can be built from a raw MongoDB document (`_id` -> `id`)."""

    model_config = ConfigDict(extra="ignore")

    id: str

    @classmethod
    def from_doc(cls, doc: dict[str, Any]) -> Self:
        data = dict(doc)
        data["id"] = str(data.pop("_id"))
        return cls.model_validate(data)


class ErrorBody(BaseModel):
    code: str
    message: str
    details: Any = None


class ErrorResponse(BaseModel):
    error: ErrorBody
