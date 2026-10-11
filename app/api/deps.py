"""FastAPI dependency accessors.

`get_db` yields a Session per request; every service is constructed per
request from a shared MockBroker. Services are stateless, so this is cheap
and keeps tests simple (no global app-state to reset).
"""
from __future__ import annotations

from collections.abc import Generator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.services.broker_service import MockBroker
from app.services.folio_service import FolioService
from app.services.order_service import OrderService
from app.services.rebalance_service import RebalanceService
from app.services.subscription_service import SubscriptionService


# The broker is deterministic and stateless — one instance per process is fine.
_broker = MockBroker()
_order_service = OrderService(_broker)
_folio_service = FolioService()
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


SessionDep = Annotated[Session, Depends(get_db)]
FolioServiceDep = Annotated[FolioService, Depends(get_folio_service)]
SubscriptionServiceDep = Annotated[SubscriptionService, Depends(get_subscription_service)]
RebalanceServiceDep = Annotated[RebalanceService, Depends(get_rebalance_service)]
OrderServiceDep = Annotated[OrderService, Depends(get_order_service)]