"""Turns domain intentions into broker calls plus persisted receipts.

Broker calls run through a bounded thread pool so a fan-out of 12 or 120 orders
does not serialise on simulated latency. The caller's Session is touched only
after all calls complete — a SQLAlchemy Session is not thread-safe.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.order import Order
from app.services.broker_service import MockBroker, TradeAction, TradeRequest


@dataclass(slots=True)
class OrderRequest:
    """A domain-level instruction to trade one stock for one user."""

    user_id: str
    stock_id: int
    ticker: str
    action: TradeAction
    quantity: int
    folio_id: int | None = None
    subscription_id: str | None = None
    source: str = "SUBSCRIPTION"
    reason: str | None = None


class OrderService:
    def __init__(self, broker: MockBroker, max_workers: int = 8) -> None:
        self._broker = broker
        self._max_workers = max(1, max_workers)

    def place(self, db: Session, request: OrderRequest) -> Order:
        return self.place_many(db, [request])[0]

    def place_many(self, db: Session, requests: list[OrderRequest]) -> list[Order]:
        """Execute N broker calls concurrently, then persist every receipt.

        The broker is I/O-bound (even when simulated). ``ThreadPoolExecutor``
        keeps 12-order subscribes from serialising. The Session is only
        touched after the pool drains, so it stays on one thread.
        """
        if not requests:
            return []

        def _call(req: OrderRequest):
            return req, self._broker.execute(
                TradeRequest(
                    user_id=req.user_id,
                    ticker=req.ticker,
                    action=req.action,
                    quantity=req.quantity,
                )
            )

        workers = min(self._max_workers, len(requests))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            results = list(pool.map(_call, requests))

        orders: list[Order] = []
        for request, receipt in results:
            order = Order(
                order_id=receipt.order_id,
                user_id=receipt.user_id,
                folio_id=request.folio_id,
                subscription_id=request.subscription_id,
                stock_id=request.stock_id,
                ticker=receipt.ticker,
                action=receipt.action,
                quantity=receipt.quantity,
                status=receipt.status,
                source=request.source,
                reason=request.reason,
                timestamp=receipt.timestamp,
            )
            db.add(order)
            orders.append(order)

        db.flush()
        return orders