"""Immutable execution receipts returned by the synthetic broker.

A row here is treated as an audit record. Both `stock_id` (FK, for joins)
and `ticker` (denormalised snapshot, for history) are stored. If a Stock is
ever renamed, historical receipts still show what was actually traded.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class OrderAction:
    BUY = "BUY"
    SELL = "SELL"

    ALL: tuple[str, ...] = (BUY, SELL)


class OrderStatus:
    EXECUTED = "EXECUTED"
    REJECTED = "REJECTED"


class OrderSource:
    SUBSCRIPTION = "SUBSCRIPTION"
    EXIT = "EXIT"
    REBALANCE = "REBALANCE"

    ALL: tuple[str, ...] = (SUBSCRIPTION, EXIT, REBALANCE)


class Order(Base):
    __tablename__ = "orders"

    order_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    folio_id: Mapped[int | None] = mapped_column(
        ForeignKey("folios.id"), index=True, nullable=True
    )
    subscription_id: Mapped[str | None] = mapped_column(
        ForeignKey("subscriptions.id"), index=True, nullable=True
    )
    stock_id: Mapped[int] = mapped_column(
        ForeignKey("stocks.id"), index=True, nullable=False
    )

    ticker: Mapped[str] = mapped_column(String(20), index=True, nullable=False)

    action: Mapped[str] = mapped_column(String(8), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    source: Mapped[str] = mapped_column(String(24), index=True, nullable=False)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, nullable=False
    )

    def __repr__(self) -> str: 
        return (
            f"Order(id={self.order_id!r}, user={self.user_id!r}, "
            f"{self.action} {self.ticker} x{self.quantity} [{self.status}])"
        )