"""Test configuration — Postgres, eager Celery, authenticated clients."""
from __future__ import annotations

import os

os.environ.setdefault(
    "DATABASE_URL",
    os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql+psycopg://postgres:root@localhost:5432/folio_management_test",
    ),
)
os.environ["CELERY_TASK_ALWAYS_EAGER"] = "true"
os.environ.setdefault("LOG_LEVEL", "WARNING")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from app.db.database import Base, engine, SessionLocal
from app.db.seed import seed_folios
from app.main import app as fastapi_app
from app import models  # noqa: F401
from app.models.user import UserRole
from app.services.auth_service import AuthService

DEFAULT_PASSWORD = "Passw0rd!"


# ----------------------------------------------------------------- TestClient

class CSRFTestClient(TestClient):
    """Auto-attaches the CSRF header from the cookie on unsafe methods."""

    def request(self, method, url, **kwargs):
        if method.upper() not in ("GET", "HEAD", "OPTIONS"):
            csrf = self.cookies.get("folio_csrf_token")
            if csrf:
                headers = dict(kwargs.get("headers") or {})
                headers.setdefault("X-CSRF-Token", csrf)
                kwargs["headers"] = headers
        return super().request(method, url, **kwargs)


# ----------------------------------------------------------------- schema

_TABLES = [
    "orders", "positions", "rebalance_jobs",
    "subscriptions", "folio_stocks", "folios", "stocks", "users",
]


def _reset_schema() -> None:
    with engine.begin() as conn:
        conn.execute(
            text(f"TRUNCATE TABLE {', '.join(_TABLES)} RESTART IDENTITY CASCADE")
        )


@pytest.fixture(scope="session", autouse=True)
def _create_schema():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture(autouse=True)
def _reset_between_tests(_create_schema):
    _reset_schema()
    with SessionLocal() as db:
        seed_folios(db)
    yield


# ----------------------------------------------------------------- users

def _create_user(email: str, password: str = DEFAULT_PASSWORD, role: str = UserRole.USER):
    with SessionLocal() as db:
        return AuthService().create_user(db, email=email, password=password, role=role)


def _login(client: TestClient, email: str, password: str = DEFAULT_PASSWORD) -> dict:
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture()
def db_session():
    with SessionLocal() as db:
        yield db


@pytest.fixture()
def raw_client():
    """No authentication — for testing 401/403 behaviour."""
    return CSRFTestClient(fastapi_app)


@pytest.fixture()
def client():
    """Authenticated TestClient as a USER."""
    tc = CSRFTestClient(fastapi_app)
    _create_user("user-101@test.local", role=UserRole.USER)
    _login(tc, "user-101@test.local")
    return tc


@pytest.fixture()
def admin_client():
    """Authenticated TestClient as an ADMIN."""
    tc = CSRFTestClient(fastapi_app)
    _create_user("admin@test.local", role=UserRole.ADMIN)
    _login(tc, "admin@test.local")
    return tc


@pytest.fixture()
def make_client():
    """Factory: create+login a fresh client with a given email/role."""
    def _make(email: str, role: str = UserRole.USER, password: str = DEFAULT_PASSWORD):
        _create_user(email, password=password, role=role)
        tc = CSRFTestClient(fastapi_app)
        _login(tc, email, password)
        return tc
    return _make


# ----------------------------------------------------------------- helpers

@pytest.fixture()
def current_user_id(client):
    """Return the authenticated user's user_id."""
    return client.get("/api/auth/me").json()["user_id"]


@pytest.fixture()
def subscribe(client):
    """Helper: subscribe the current user to a folio.

    The user_id arg is accepted for backward compatibility with the old tests
    but is ignored — the API derives identity from the JWT.
    """
    def _subscribe(user_id: str = "ignored", folio_id: int = 1, multiplier: int = 1):
        r = client.post(
            "/api/subscriptions",
            json={"user_id": user_id, "folio_id": folio_id, "multiplier": multiplier},
        )
        assert r.status_code == 201, r.text
        return r.json()
    return _subscribe


@pytest.fixture()
def folio_payload(client):
    def _get(folio_id: int = 1):
        r = client.get(f"/api/folios/{folio_id}")
        assert r.status_code == 200, r.text
        return r.json()
    return _get


@pytest.fixture()
def app_db_session():
    """A Session bound to the test engine — for direct DB setup in fixtures."""
    from sqlalchemy.orm import sessionmaker
    from app.db.database import engine
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with SessionLocal() as db:
        yield db