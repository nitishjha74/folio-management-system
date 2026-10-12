"""Application settings, loaded from environment variables / .env."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = BASE_DIR / ".env"


class Settings(BaseSettings):
    # --- Application ---
    app_env: str = "development"
    log_level: str = "INFO"
    app_name: str = "Folio Management & Auto-Rebalancing Trading System"
    app_version: str = "1.0.0"

    # --- Database ---
    database_url: str
    redis_url: str = "redis://localhost:6379/0"

    # --- Celery ---
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"
    celery_task_always_eager: bool = False

    # --- Mock broker ---
    broker_latency_ms: int = 0
    broker_failure_rate: float = 0.0
    broker_max_retries: int = 2

    # --- Rebalance worker ---
    rebalance_concurrency: int = 8

    # --- Auth (JWT) ---
    secret_key: str = "CHANGE-ME-IN-ENV"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 8       # 8 hours

    # --- Auth (cookies) ---
    cookie_name: str = "folio_access_token"
    cookie_secure: bool = False                     # True when served over HTTPS
    cookie_samesite: str = "lax"
    cookie_domain: str | None = None
    cookie_path: str = "/"

    # --- CSRF ---
    csrf_cookie_name: str = "folio_csrf_token"
    csrf_header_name: str = "X-CSRF-Token"
    csrf_token_length: int = 32

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