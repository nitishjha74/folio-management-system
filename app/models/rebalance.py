"""Durable record of an admin-triggered stock replacement and its fan-out.

The ``subscriber_snapshot`` column is the load-bearing piece: taken at trigger
time, before the folio composition changes, it captures exactly who was
subscribed and at what multiplier. A user who subscribes *after* the trigger
is therefore not rebalanced against a basket they never held.

``JSONB`` (not ``JSON``) because: it validates on insert, indexes cleanly, and
stores more compactly.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class RebalanceStatus:
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

    TERMINAL: tuple[str, ...] = (COMPLETED, FAILED)


class RebalanceJob(Base):
    __tablename__ = "rebalance_jobs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    folio_id: Mapped[int] = mapped_column(
        ForeignKey("folios.id"), index=True, nullable=False
    )
    folio_name: Mapped[str] = mapped_column(String(120), nullable=False)


    outgoing_stock_id: Mapped[int] = mapped_column(
        ForeignKey("stocks.id"), nullable=False
    )
    outgoing_ticker: Mapped[str] = mapped_column(String(20), nullable=False)
    outgoing_base_quantity: Mapped[int] = mapped_column(Integer, nullable=False)

    incoming_stock_id: Mapped[int] = mapped_column(
        ForeignKey("stocks.id"), nullable=False
    )
    incoming_ticker: Mapped[str] = mapped_column(String(20), nullable=False)
    incoming_base_quantity: Mapped[int] = mapped_column(Integer, nullable=False)

    status: Mapped[str] = mapped_column(
        String(16), default=RebalanceStatus.PENDING, nullable=False, index=True
    )

    subscribers_total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    subscribers_processed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    subscribers_skipped: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    subscribers_failed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    orders_created: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # [{"subscription_id": "sub-…", "user_id": "user-…", "multiplier": 3}, …]
    subscriber_snapshot: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, default=list, nullable=False
    )

    error: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str: 
        return (
            f"RebalanceJob(id={self.id!r}, {self.outgoing_ticker}->"
            f"{self.incoming_ticker}, status={self.status})"
        )