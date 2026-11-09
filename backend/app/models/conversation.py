"""Conversation and message schemas."""

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from app.models.common import MongoModel


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


class ToolCallRecord(BaseModel):
    tool_name: str
    input: Any = None
    output: Any = None
    error: str | None = None
    duration_ms: float | None = None


class Message(MongoModel):
    conversation_id: str
    role: MessageRole
    content: str
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    created_at: datetime


class Conversation(MongoModel):
    owner_id: str
    agent_id: str
    title: str
    created_at: datetime
    updated_at: datetime


class ConversationDetail(Conversation):
    messages: list[Message] = Field(default_factory=list)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=10_000)
    conversation_id: str | None = None
