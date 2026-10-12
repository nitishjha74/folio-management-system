"""Password hashing and JWT helpers."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt

from app.core.config import settings
from app.core.exceptions import UnauthorizedError

# bcrypt has a hard 72-byte limit on the input. Truncate deterministically
# so hashing never raises on long passwords.
_BCRYPT_MAX_BYTES = 72


def _to_bcrypt_bytes(password: str) -> bytes:
    return password.encode("utf-8")[:_BCRYPT_MAX_BYTES]


def hash_password(plain: str) -> str:
    if not plain:
        raise ValueError("password must not be empty")
    return bcrypt.hashpw(_to_bcrypt_bytes(plain), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    if not plain or not hashed:
        return False
    try:
        return bcrypt.checkpw(_to_bcrypt_bytes(plain), hashed.encode("utf-8"))
    except Exception:
        return False


def create_access_token(
    *,
    subject: str,
    role: str,
    expires_delta: timedelta | None = None,
) -> str:
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=settings.access_token_expire_minutes))
    payload: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    if not token:
        raise UnauthorizedError("Missing authentication token")
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError:
        raise UnauthorizedError("Authentication token has expired")
    except jwt.InvalidTokenError:
        raise UnauthorizedError("Invalid authentication token")