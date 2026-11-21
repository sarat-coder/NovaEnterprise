from __future__ import annotations

import functools
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- AI providers ---
    llm_provider: Literal[
        "fake", "openai", "anthropic", "azure", "google", "cohere", "mistral", "ollama"
    ] = "fake"
    llm_api_key: str = ""
    llm_model: str = ""

    embedding_provider: str = "fake"
    embedding_model: str = ""

    # --- Stores ---
    vector_store: Literal["memory", "qdrant"] = "memory"
    qdrant_url: str = ""
    qdrant_api_key: str = ""

    graph_store: Literal["memory", "neo4j"] = "memory"
    neo4j_uri: str = ""
    neo4j_user: str = ""
    neo4j_password: str = ""

    # --- Database ---
    database_url: str = "sqlite:///data/enterprise.db"

    # --- Redis ---
    redis_url: str = ""  # empty → fakeredis

    # --- Workflow tuning ---
    max_subquestions: int = 4
    max_corrective_rounds: int = 1

    # --- Rate limiting ---
    rate_limit_per_minute: int = 120

    # --- Uploads ---
    max_upload_mb: int = 5

    # --- Auth ---
    jwt_secret: str = "change-me-before-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    # --- Supabase (optional) ---
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""

    # --- CORS ---
    cors_origins: list[str] = ["http://localhost:3001"]

    # --- App ---
    app_env: Literal["development", "testing", "production"] = "development"
    log_level: str = "INFO"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v


@functools.lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def reset_settings_cache() -> None:
    """Clear the lru_cache so the next call re-reads env vars. Use in tests only."""
    get_settings.cache_clear()
