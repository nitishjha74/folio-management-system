"""Test configuration.

Strategy:

1. ``DATABASE_URL`` and ``CELERY_TASK_ALWAYS_EAGER`` are set **before** any
   ``app.*`` import. ``app.core.config.get_settings()`` reads the environment
   once, so this redirects the whole application (including the Celery app)
   to the test database and eager task execution.

2. Celery runs in eager mode. When ``RebalanceService.trigger`` calls
   ``rebalance_fanout.apply_async(...)``, the task executes **inline** in the
   test process — same DB, same transaction semantics, no broker, no worker,
   no polling. No monkeypatching required.

3. Between tests, every table is truncated with ``RESTART IDENTITY CASCADE``
   and the seed re-runs. Fast and deterministic. The alternative —
   transaction rollback — does not work here because services call
   ``session.commit()`` explicitly.

4. ``TestClient`` is used *without* a context manager so the FastAPI lifespan
   (which would create+seed on every entry) never runs.
"""
from __future__ import annotations

import os

# -----------------------------------------------------------------------------
# MUST run before any `app.*` import.
# -----------------------------------------------------------------------------
os.environ.setdefault(
    "DATABASE_URL",
    os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql+psycopg://postgres:root@localhost:5432/folio_management_test",
    ),
)
os.environ["CELERY_TASK_ALWAYS_EAGER"] = "true"
os.environ.setdefault("LOG_LEVEL", "WARNING")
# -----------------------------------------------------------------------------

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from app.db.database import Base, engine
from app.db.seed import seed_folios
from app.main import app as fastapi_app

# Register every model with Base.metadata before create_all().
from app import models  # noqa: F401


# Order matters only for readability — CASCADE handles dependencies.
_TABLES = [
    "orders",
    "positions",
    "rebalance_jobs",
    "subscriptions",
    "folio_stocks",
    "folios",
    "stocks",
]


def _reset_schema() -> None:
    with engine.begin() as conn:
        conn.execute(
            text(f"TRUNCATE TABLE {', '.join(_TABLES)} RESTART IDENTITY CASCADE")
        )


# ---------------------------------------------------------------- schema

@pytest.fixture(scope="session", autouse=True)
def _create_schema():
    """Drop + recreate the schema once per test session."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture(autouse=True)
def _reset_between_tests(_create_schema):
    """Clean slate + seeded folios before every test."""
    _reset_schema()
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with SessionLocal() as db:
        seed_folios(db)
    yield


# ---------------------------------------------------------------- client

@pytest.fixture()
def client():
    """TestClient bound to the app. No context manager — lifespan is skipped."""
    return TestClient(fastapi_app)


# ---------------------------------------------------------------- helpers

@pytest.fixture()
def subscribe(client):
    """Helper: POST /api/subscriptions and assert 201."""

    def _subscribe(
        user_id: str,
        folio_id: int = 1,
        multiplier: int = 1,
    ) -> dict:
        r = client.post(
            "/api/subscriptions",
            json={
                "user_id": user_id,
                "folio_id": folio_id,
                "multiplier": multiplier,
            },
        )
        assert r.status_code == 201, r.text
        return r.json()

    return _subscribe


@pytest.fixture()
def folio_payload(client):
    """Helper: fetch a folio by id, return its body."""

    def _get(folio_id: int = 1) -> dict:
        r = client.get(f"/api/folios/{folio_id}")
        assert r.status_code == 200, r.text
        return r.json()

    return _get