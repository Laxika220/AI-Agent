"""Knowledge base, document and retrieval schemas."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from app.models.common import MongoModel

SUPPORTED_EXTENSIONS: frozenset[str] = frozenset({".pdf", ".txt", ".md", ".docx"})


class DocumentStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class KnowledgeBaseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=500)


class KnowledgeBasePublic(MongoModel):
    owner_id: str
    name: str
    description: str = ""
    document_count: int = 0
    created_at: datetime


class DocumentPublic(MongoModel):
    owner_id: str
    knowledge_base_id: str
    filename: str
    content_type: str | None = None
    size_bytes: int
    status: DocumentStatus
    chunk_count: int = 0
    error: str | None = None
    created_at: datetime
    updated_at: datetime


class RetrievedChunk(BaseModel):
    text: str
    doc_id: str
    source_file: str
    chunk_index: int
    score: float = Field(description="Cosine similarity in [−1, 1]; higher is more relevant")
