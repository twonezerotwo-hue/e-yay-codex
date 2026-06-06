from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "E-yAy BrainChain"
    app_env: str = "development"
    debug: bool = True
    api_prefix: str = "/api/v1"
    execution_mode: str = "OFF"
    log_level: str = "INFO"
    database_url: str | None = None
    redis_url: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()

__all__ = [name for name in globals() if not name.startswith('_')]
