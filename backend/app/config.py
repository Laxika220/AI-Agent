"""Application settings loaded from environment variables / `.env` via pydantic-settings."""

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed, validated configuration for the whole backend."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- App ---
    app_name: str = "AgentForge"
    environment: str = "development"
    log_level: str = "INFO"
    log_json: bool = False
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://localhost:3000"]
    )

    # --- LLM (OpenAI-compatible) ---
    openai_api_key: str = ""
    openai_base_url: str | None = None
    model_name: str = "gpt-4o-mini"
    available_models: list[str] = Field(
        default_factory=lambda: ["gpt-4o-mini", "gpt-4o", "gpt-4.1-mini"]
    )
    llm_timeout_seconds: int = 60
    agent_max_iterations: int = 8

    # --- Data stores ---
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db: str = "agentforge"
    redis_url: str = "redis://localhost:6379/0"
    chroma_host: str | None = "localhost"
    chroma_port: int = 8001
    chroma_persist_dir: str = "./chroma_data"

    # --- RAG ---
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    chunk_size: int = Field(default=1000, gt=0)
    chunk_overlap: int = Field(default=200, ge=0)
    retrieval_top_k: int = Field(default=5, gt=0)
    retrieval_fetch_k: int = Field(default=20, gt=0)
    mmr_lambda: float = Field(default=0.5, ge=0.0, le=1.0)
    preload_embedding_model: bool = False

    # --- Auth ---
    jwt_secret_key: str = "change-me-to-a-long-random-string"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    # --- Limits ---
    rate_limit_per_minute: int = 10
    conversation_cache_size: int = 20
    embedding_cache_ttl_seconds: int = 3600
    upload_dir: str = "./uploads"
    max_upload_mb: int = 20
    code_exec_timeout_seconds: int = 10
    api_call_timeout_seconds: int = 15
    allow_private_network_api_calls: bool = False

    @field_validator("openai_base_url", "chroma_host", mode="before")
    @classmethod
    def _empty_to_none(cls, value: str | None) -> str | None:
        """Treat empty strings from `.env` files as 'not set'."""
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    """Return a process-wide cached Settings instance."""
    return Settings()
