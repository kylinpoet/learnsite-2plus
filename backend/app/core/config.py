from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "LearnSite 2+ API"
    api_prefix: str = "/api"
    sqlite_url: str = "sqlite:///./learnsite.db"
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


@lru_cache
def get_settings() -> Settings:
    return Settings()
