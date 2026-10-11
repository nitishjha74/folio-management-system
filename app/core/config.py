from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = BASE_DIR / ".env"


class Settings(BaseSettings):
    app_env: str = "development"
    log_level: str = "INFO"
    app_name: str = "Folio Management & Auto-Rebalancing Trading System"
    app_version: str = "1.0.0"

    database_url: str
    redis_url: str = "redis://localhost:6379/0"

    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"
    celery_task_always_eager: bool = False

    # Optional — only used by OrderService
    broker_latency_ms: int = 0
    broker_failure_rate: float = 0.0
    broker_max_retries: int = 2

    # Optional — fan-out concurrency
    rebalance_concurrency: int = 8

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()