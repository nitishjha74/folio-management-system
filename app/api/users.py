"""Subscription endpoints.

The only user-scoped URL is ``/api/users/{user_id}/subscriptions``; everything
else is subscription-scoped. Kept in one module so the resource boundary is
obvious.
"""
from __future__ import annotations

from fastapi import APIRouter, Query, status

from app.api.deps import SessionDep, SubscriptionServiceDep
from app.schemas.order import OrderOut
from app.schemas.subscription import (
    ExitResponse,
    SubscribeResponse,
    SubscriptionCreate,
    SubscriptionOut,
)

router = APIRouter(tags=["subscriptions"])


@router.post(
    "/api/subscriptions",
    response_model=SubscribeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Subscribe a user to a folio with a quantity multiplier",
)
def create_subscription(
    payload: SubscriptionCreate,
    db: SessionDep,
    service: SubscriptionServiceDep,
) -> SubscribeResponse:
    subscription, orders = service.subscribe(db, payload)
    return SubscribeResponse(
        subscription=service.to_out(subscription),
        orders=[OrderOut.model_validate(o) for o in orders],
    )


@router.get(
    "/api/subscriptions/{subscription_id}",
    response_model=SubscriptionOut,
    summary="Get a subscription",
)
def get_subscription(
    subscription_id: str,
    db: SessionDep,
    service: SubscriptionServiceDep,
) -> SubscriptionOut:
    sub = service.get_subscription(db, subscription_id)
    return service.to_out(sub)


@router.get(
    "/api/users/{user_id}/subscriptions",
    response_model=list[SubscriptionOut],
    summary="List a user's subscriptions",
)
def list_user_subscriptions(
    user_id: str,
    db: SessionDep,
    service: SubscriptionServiceDep,
    active_only: bool = Query(False, description="Only return active subscriptions"),
) -> list[SubscriptionOut]:
    subs = service.list_user_subscriptions(db, user_id, active_only)
    return [service.to_out(s) for s in subs]


@router.post(
    "/api/subscriptions/{subscription_id}/exit",
    response_model=ExitResponse,
    summary="Exit (liquidate) a subscription",
)
def exit_subscription(
    subscription_id: str,
    db: SessionDep,
    service: SubscriptionServiceDep,
) -> ExitResponse:
    sub, orders = service.exit_subscription(db, subscription_id)
    return ExitResponse(
        subscription=service.to_out(sub),
        orders=[OrderOut.model_validate(o) for o in orders],
    )