"""Authentication endpoints (cookie + CSRF)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status

from app.api.deps import AuthServiceDep, CurrentUser, SessionDep
from app.core.config import settings
from app.core.csrf import generate_csrf_token, verify_csrf
from app.core.security import create_access_token
from app.models.user import UserRole
from app.schemas.auth import (
    LoginRequest, LoginResponse, RegisterRequest, RegisterResponse, UserPublic,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])

_COOKIE_MAX_AGE = settings.access_token_expire_minutes * 60


def _set_auth_cookies(response: Response, user_id: str, role: str) -> None:
    token = create_access_token(subject=user_id, role=role)
    csrf = generate_csrf_token()

    response.set_cookie(
        key=settings.cookie_name, value=token, max_age=_COOKIE_MAX_AGE,
        httponly=True, secure=settings.cookie_secure,
        samesite=settings.cookie_samesite, domain=settings.cookie_domain,
        path=settings.cookie_path,
    )
    response.set_cookie(
        key=settings.csrf_cookie_name, value=csrf, max_age=_COOKIE_MAX_AGE,
        httponly=False, secure=settings.cookie_secure,
        samesite=settings.cookie_samesite, domain=settings.cookie_domain,
        path=settings.cookie_path,
    )


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(settings.cookie_name, path=settings.cookie_path)
    response.delete_cookie(settings.csrf_cookie_name, path=settings.cookie_path)


# ----------------------------------------------------------------- login
# No CSRF check — user has no session yet. Login itself establishes the
# session, so there is nothing to protect against at this stage.

@router.post("/login", response_model=LoginResponse)
def login(
    payload: LoginRequest,
    response: Response,
    db: SessionDep,
    service: AuthServiceDep,
) -> LoginResponse:
    user = service.authenticate(db, payload.email, payload.password)
    _set_auth_cookies(response, user.user_id, user.role)
    return LoginResponse(user=UserPublic.model_validate(user))


# ---------------------------------------------------------------- logout
# CSRF check IS required — user has a live session. Without it, a third-party
# site could force-logout the user (annoying but low-severity).

@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(verify_csrf)],
)
def logout(response: Response) -> Response:
    _clear_auth_cookies(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


# ------------------------------------------------------------------- me
# No CSRF — safe method (GET).

@router.get("/me", response_model=UserPublic)
def me(user: CurrentUser) -> UserPublic:
    return UserPublic.model_validate(user)


# ------------------------------------------------------------- register
# No CSRF check — user has no session yet. Public registration is a
# pre-authentication action; there is nothing to hijack.
# Role is hardcoded to USER so a client cannot escalate.

@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    payload: RegisterRequest,
    response: Response,
    db: SessionDep,
    service: AuthServiceDep,
) -> RegisterResponse:
    user = service.create_user(
        db,
        email=payload.email,
        password=payload.password,
        full_name=payload.full_name,
        role=UserRole.USER,
    )
    _set_auth_cookies(response, user.user_id, user.role)
    return RegisterResponse(user=UserPublic.model_validate(user))