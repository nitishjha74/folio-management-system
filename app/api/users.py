"""Subscription endpoints — identity comes from JWT, never from the request."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import CurrentUser, SessionDep, SubscriptionServiceDep
from app.core.csrf import verify_csrf
from app.core.exceptions import ForbiddenError
from app.schemas.order import OrderOut
from app.schemas.subscription import (
    ExitResponse, SubscribeResponse, SubscriptionCreate, SubscriptionOut,
)

router = APIRouter(tags=["subscriptions"])


@router.post(
    "/api/subscriptions",
    response_model=SubscribeResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_csrf)],
)
def create_subscription(
    payload: SubscriptionCreate,
    user: CurrentUser,
    db: SessionDep,
    service: SubscriptionServiceDep,
) -> SubscribeResponse:
    # Force user_id to the authenticated identity — ignore any client value.
    payload = payload.model_copy(update={"user_id": user.user_id})
    subscription, orders = service.subscribe(db, payload)
    return SubscribeResponse(
        subscription=service.to_out(subscription),
        orders=[OrderOut.model_validate(o) for o in orders],
    )


@router.get("/api/subscriptions/{subscription_id}", response_model=SubscriptionOut)
def get_subscription(
    subscription_id: str,
    user: CurrentUser,
    db: SessionDep,
    service: SubscriptionServiceDep,
) -> SubscriptionOut:
    sub = service.get_subscription(db, subscription_id)
    if sub.user_id != user.user_id:
        raise ForbiddenError("You cannot view another user's subscription")
    return service.to_out(sub)


@router.get(
    "/api/users/{user_id}/subscriptions",
    response_model=list[SubscriptionOut],
)
def list_user_subscriptions(
    user_id: str,
    user: CurrentUser,
    db: SessionDep,
    service: SubscriptionServiceDep,
    active_only: bool = Query(False),
) -> list[SubscriptionOut]:
    if user_id != user.user_id:
        raise ForbiddenError("You cannot view another user's subscriptions")
    subs = service.list_user_subscriptions(db, user_id, active_only)
    return [service.to_out(s) for s in subs]


@router.post(
    "/api/subscriptions/{subscription_id}/exit",
    response_model=ExitResponse,
    dependencies=[Depends(verify_csrf)],
)
def exit_subscription(
    subscription_id: str,
    user: CurrentUser,
    db: SessionDep,
    service: SubscriptionServiceDep,
) -> ExitResponse:
    sub = service.get_subscription(db, subscription_id)
    if sub.user_id != user.user_id:
        raise ForbiddenError("You cannot exit another user's subscription")
    sub, orders = service.exit_subscription(db, subscription_id)
    return ExitResponse(
        subscription=service.to_out(sub),
        orders=[OrderOut.model_validate(o) for o in orders],
    )