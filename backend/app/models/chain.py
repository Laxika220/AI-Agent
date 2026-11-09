"""Multi-agent chain schemas."""

from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator

from app.models.common import MongoModel
from app.models.conversation import ToolCallRecord
from app.utils.graph import resolve_dependencies, topological_levels


class ChainStep(BaseModel):
    id: str = Field(min_length=1, max_length=50, pattern=r"^[A-Za-z0-9_-]+$")
    agent_id: str
    depends_on: list[str] | None = Field(
        default=None,
        description=(
            "IDs of steps whose output feeds this step. `null` means 'the previous step' "
            "(a simple sequential chain); `[]` means it runs on the chain input directly."
        ),
    )


class _ChainStepsMixin(BaseModel):
    steps: list[ChainStep] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def _validate_graph(self) -> Self:
        ids = [s.id for s in self.steps]
        if len(ids) != len(set(ids)):
            raise ValueError("Step ids must be unique")
        graph = resolve_dependencies([(s.id, s.depends_on) for s in self.steps])
        topological_levels(graph)  # raises ValueError on cycles / unknown deps
        return self


class ChainCreate(_ChainStepsMixin):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=500)


class ChainUpdate(_ChainStepsMixin):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=500)


class ChainPublic(MongoModel):
    owner_id: str
    name: str
    description: str = ""
    steps: list[ChainStep]
    created_at: datetime
    updated_at: datetime


class ChainRunRequest(BaseModel):
    input: str = Field(min_length=1, max_length=10_000)


StepStatus = Literal["success", "error", "skipped"]


class StepTrace(BaseModel):
    step_id: str
    agent_id: str
    agent_name: str
    level: int = Field(description="Execution wave; steps in the same level ran in parallel")
    depends_on: list[str]
    input: str
    output: str | None = None
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    status: StepStatus
    error: str | None = None
    started_at: datetime
    finished_at: datetime
    duration_ms: float


class ChainRunResult(MongoModel):
    chain_id: str
    owner_id: str
    input: str
    final_output: str
    status: Literal["success", "partial", "error"]
    steps: list[StepTrace]
    total_duration_ms: float
    created_at: datetime
