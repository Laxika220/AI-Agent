"""Agent schemas."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from app.models.common import MongoModel

ToolName = Literal["web_search", "calculator", "code_executor", "json_api_call"]


def _dedupe(tools: list[ToolName]) -> list[ToolName]:
    return list(dict.fromkeys(tools))


class AgentBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=500)
    system_prompt: str = Field(min_length=1, max_length=20_000)
    model: str | None = Field(default=None, description="Overrides MODEL_NAME when set")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    tools: list[ToolName] = Field(default_factory=list)
    knowledge_base_id: str | None = None

    @field_validator("tools")
    @classmethod
    def _unique_tools(cls, tools: list[ToolName]) -> list[ToolName]:
        return _dedupe(tools)


class AgentCreate(AgentBase):
    pass


class AgentUpdate(BaseModel):
    """Partial update: only fields explicitly sent are changed."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    system_prompt: str | None = Field(default=None, min_length=1, max_length=20_000)
    model: str | None = None
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    tools: list[ToolName] | None = None
    knowledge_base_id: str | None = None

    @field_validator("tools")
    @classmethod
    def _unique_tools(cls, tools: list[ToolName] | None) -> list[ToolName] | None:
        return _dedupe(tools) if tools is not None else None


class AgentPublic(MongoModel, AgentBase):
    owner_id: str
    created_at: datetime
    updated_at: datetime


class ToolInfo(BaseModel):
    name: str
    description: str
    parameters: dict[str, Any]


class ModelsInfo(BaseModel):
    default: str
    available: list[str]
