"""Authentication and authorization tests."""
from __future__ import annotations

import time
import jwt
import pytest

from app.core.config import settings
from app.core.security import create_access_token


# --------------------------------------------------------------- helpers

@pytest.fixture
def create_user(app_db_session):
    """Insert a user with a known password. Returns the row."""
    from app.services.auth_service import AuthService
    from app.models.user import UserRole

    service = AuthService()
    def _create(email="user@test.local", password="Passw0rd!", role=UserRole.USER, active=True):
        user = service.create_user(
            app_db_session, email=email, password=password, role=role,
        )
        if not active:
            user.is_active = False
            app_db_session.commit()
        return user
    return _create


# --------------------------------------------------------------- login

def test_login_success_sets_cookies(client, create_user):
    create_user(email="user@test.local", password="Passw0rd!")
    r = client.post("/api/auth/login", json={"email": "user@test.local", "password": "Passw0rd!"})
    assert r.status_code == 200
    body = r.json()
    assert body["user"]["email"] == "user@test.local"
    assert body["user"]["role"] == "USER"
    assert "folio_access_token" in r.cookies
    assert "folio_csrf_token" in r.cookies


def test_login_wrong_password(client, create_user):
    create_user(email="user@test.local", password="Passw0rd!")
    r = client.post("/api/auth/login", json={"email": "user@test.local", "password": "nope"})
    assert r.status_code == 401
    assert "Invalid email or password" in r.json()["message"]


def test_login_unknown_email(client):
    r = client.post("/api/auth/login", json={"email": "no@one.local", "password": "x"})
    assert r.status_code == 401


def test_login_inactive_account(client, create_user):
    create_user(email="dead@test.local", password="Passw0rd!", active=False)
    r = client.post("/api/auth/login", json={"email": "dead@test.local", "password": "Passw0rd!"})
    assert r.status_code == 401
    assert "inactive" in r.json()["message"].lower()


def test_login_role_detection_admin(client, create_user):
    from app.models.user import UserRole
    create_user(email="admin@test.local", password="Passw0rd!", role=UserRole.ADMIN)
    r = client.post("/api/auth/login", json={"email": "admin@test.local", "password": "Passw0rd!"})
    assert r.status_code == 200
    assert r.json()["user"]["role"] == "ADMIN"


# --------------------------------------------------------------- /me

def test_me_requires_auth(client):
    r = client.get("/api/auth/me")
    assert r.status_code == 401


def test_me_with_valid_cookie(client, create_user):
    create_user(email="user@test.local", password="Passw0rd!")
    client.post("/api/auth/login", json={"email": "user@test.local", "password": "Passw0rd!"})
    r = client.get("/api/auth/me")
    assert r.status_code == 200
    assert r.json()["email"] == "user@test.local"


def test_me_with_invalid_token(client):
    client.cookies.set("folio_access_token", "not-a-real-jwt")
    r = client.get("/api/auth/me")
    assert r.status_code == 401


def test_me_with_expired_token(client, create_user):
    user = create_user(email="user@test.local", password="Passw0rd!")
    # Build a token that expires in the past
    expired = jwt.encode(
        {"sub": user.user_id, "role": user.role, "exp": int(time.time()) - 10},
        settings.secret_key, algorithm=settings.jwt_algorithm,
    )
    client.cookies.set("folio_access_token", expired)
    r = client.get("/api/auth/me")
    assert r.status_code == 401


# --------------------------------------------------------------- admin guard

def test_user_cannot_access_admin_rebalance(client, create_user, subscribe):
    create_user(email="user@test.local", password="Passw0rd!")
    client.post("/api/auth/login", json={"email": "user@test.local", "password": "Passw0rd!"})
    r = client.post("/api/admin/rebalance", json={
        "folio_id": 1, "outgoing_ticker": "RELIANCE", "incoming_ticker": "IDEA",
    })
    assert r.status_code == 403


# --------------------------------------------------------------- cross-user isolation

def test_user_cannot_read_another_users_subscriptions(client, create_user, subscribe):
    create_user(email="a@test.local", password="Passw0rd!")
    create_user(email="b@test.local", password="Passw0rd!")
    # Subscribe as user A
    client.post("/api/auth/login", json={"email": "a@test.local", "password": "Passw0rd!"})
    subscribe("user-A-placeholder", folio_id=1, multiplier=1)  # actual id comes from JWT

    # Try to read B's subscriptions with A's cookie
    r = client.get("/api/users/user-B-placeholder/subscriptions")
    assert r.status_code == 403


def test_user_cannot_exit_another_users_subscription(client, create_user):
    # Login as A, try to exit B's subscription id
    create_user(email="a@test.local", password="Passw0rd!")
    client.post("/api/auth/login", json={"email": "a@test.local", "password": "Passw0rd!"})
    r = client.post("/api/subscriptions/sub-nonexistent/exit")
    assert r.status_code in (403, 404)


# --------------------------------------------------------------- privilege escalation

def test_registration_ignores_role_field(client):
    r = client.post("/api/auth/register", json={
        "email": "sneaky@test.local",
        "password": "Passw0rd!",
        "role": "ADMIN",             # should be ignored
    })
    assert r.status_code == 201
    assert r.json()["user"]["role"] == "USER"


# --------------------------------------------------------------- logout

def test_logout_clears_cookies(client, create_user):
    create_user(email="user@test.local", password="Passw0rd!")
    client.post("/api/auth/login", json={"email": "user@test.local", "password": "Passw0rd!"})
    # Logout requires CSRF header — read cookie
    csrf = client.cookies.get("folio_csrf_token")
    r = client.post("/api/auth/logout", headers={"X-CSRF-Token": csrf})
    assert r.status_code == 204
    # After logout, /me should fail
    r2 = client.get("/api/auth/me")
    assert r2.status_code == 401