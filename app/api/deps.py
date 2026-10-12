"""FastAPI dependency accessors."""
from __future__ import annotations

from collections.abc import Generator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import decode_access_token
from app.db.database import SessionLocal
from app.models.user import User, UserRole
from app.services.auth_service import AuthService
from app.services.broker_service import MockBroker
from app.services.folio_service import FolioService
from app.services.order_service import OrderService
from app.services.rebalance_service import RebalanceService
from app.services.subscription_service import SubscriptionService


_broker = MockBroker()
_order_service = OrderService(_broker)
_folio_service = FolioService()
_auth_service = AuthService()
_subscription_service = SubscriptionService(_order_service, _folio_service)
_rebalance_service = RebalanceService(_folio_service)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_folio_service() -> FolioService:
    return _folio_service


def get_subscription_service() -> SubscriptionService:
    return _subscription_service


def get_rebalance_service() -> RebalanceService:
    return _rebalance_service


def get_order_service() -> OrderService:
    return _order_service


def get_auth_service() -> AuthService:
    return _auth_service


def get_current_user(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """Read the JWT from the HttpOnly cookie, verify it, load the user."""
    token = request.cookies.get(settings.cookie_name)
    if not token:
        raise UnauthorizedError("Not authenticated")

    payload = decode_access_token(token)
    user_id = payload.get("sub")
    if not user_id:
        raise UnauthorizedError("Invalid token payload")

    user = db.get(User, user_id)
    if user is None:
        raise UnauthorizedError("User no longer exists")
    if not user.is_active:
        raise UnauthorizedError("Account is inactive")
    return user


def require_admin(
    user: Annotated[User, Depends(get_current_user)],
) -> User:
    if user.role != UserRole.ADMIN:
        raise ForbiddenError("Admin privileges required")
    return user


SessionDep = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]
AdminUser = Annotated[User, Depends(require_admin)]
FolioServiceDep = Annotated[FolioService, Depends(get_folio_service)]
SubscriptionServiceDep = Annotated[SubscriptionService, Depends(get_subscription_service)]
RebalanceServiceDep = Annotated[RebalanceService, Depends(get_rebalance_service)]
OrderServiceDep = Annotated[OrderService, Depends(get_order_service)]
AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]