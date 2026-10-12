"""CSRF protection via the double-submit cookie pattern.

Why double-submit:

* The auth cookie is HttpOnly — JavaScript cannot read it. That's what makes
  it XSS-safe.
* CSRF is the flip side: a malicious site could still make the browser send
  the cookie on a cross-site POST.
* Mitigation: a **separate**, non-HttpOnly cookie holds a random token. JS
  reads it and echoes it in a header. The server verifies cookie == header.
  Cross-site attackers cannot read the cookie (same-origin policy), so they
  cannot forge the header.

The token is refreshed on every successful login. Validation is skipped for
safe methods (GET/HEAD/OPTIONS) — they must not mutate state.
"""
from __future__ import annotations

import hmac
import secrets

from fastapi import Request

from app.core.config import settings
from app.core.exceptions import ForbiddenError

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def generate_csrf_token() -> str:
    """Return a fresh random CSRF token."""
    return secrets.token_urlsafe(settings.csrf_token_length)


def _constant_time_equal(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


def verify_csrf(request: Request) -> None:
    """Raise ForbiddenError if the CSRF header does not match the cookie.

    Attach this as a dependency on every state-changing route:

        @router.post("/foo", dependencies=[Depends(verify_csrf)])
    """
    if request.method in SAFE_METHODS:
        return

    cookie_token = request.cookies.get(settings.csrf_cookie_name)
    header_token = request.headers.get(settings.csrf_header_name)

    if not cookie_token or not header_token:
        raise ForbiddenError("Missing CSRF token")
    if not _constant_time_equal(cookie_token, header_token):
        raise ForbiddenError("Invalid CSRF token")