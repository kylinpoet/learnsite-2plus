import json
from functools import lru_cache
from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "LearnSite 2+ API"
    api_prefix: str = "/api"
    session_ttl_minutes: int = 120
    sqlite_url: str = "sqlite:///./learnsite.db"
    resource_storage_dir: str = "./storage/resources"
    backup_storage_dir: str = "./storage/backups"
    cors_origins: list[str] = [
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:4173",
        "http://localhost:4173",
        "http://127.0.0.1:4174",
        "http://localhost:4174",
    ]

    model_config = SettingsConfigDict(
        env_prefix="LEARNSITE_",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def normalize_cors_origins(cls, value: Any) -> list[str]:
        if isinstance(value, str):
            raw_value = value.strip()
            if not raw_value:
                return []
            if raw_value.startswith("["):
                value = json.loads(raw_value)
            else:
                value = raw_value.split(",")

        if not isinstance(value, list):
            raise TypeError("LEARNSITE_CORS_ORIGINS must be a list or comma-separated string")

        normalized_origins: list[str] = []
        for origin in value:
            normalized_origin = str(origin).strip().rstrip("/")
            if normalized_origin and normalized_origin not in normalized_origins:
                normalized_origins.append(normalized_origin)
        return normalized_origins


@lru_cache
def get_settings() -> Settings:
    return Settings()
