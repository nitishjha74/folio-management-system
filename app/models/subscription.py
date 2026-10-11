"""Subscription and Position models.

Positions are the source of truth for what a user actually holds. They are
written on subscribe, mutated on rebalance, and deleted on exit. Deriving
holdings from the folio at read time would be wrong under a concurrent
rebalance — the exit would liquidate stock the user never owned.

Two partial indexes encode business rules at the storage layer:

* ``uq_active_subscription_per_user_folio`` — one *active* subscription per
  (user, folio). Concurrent subscribes cannot slip past the application-level
  check; the DB rejects the second insert.
* ``ix_active_subscriptions_by_folio`` — the rebalance fan-out query scans
  only live rows.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.folio import Folio, Stock
from app.utils.helpers import utcnow


class Subscription(Base):
    __tablename__ = "subscriptions"
    __table_args__ = (
        CheckConstraint("multiplier > 0", name="ck_subscription_multiplier_positive"),
        Index(
            "uq_active_subscription_per_user_folio",
            "user_id",
            "folio_id",
            unique=True,
            postgresql_where=text("active"),
        ),
        Index(
            "ix_active_subscriptions_by_folio",
            "folio_id",
            postgresql_where=text("active"),
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    folio_id: Mapped[int] = mapped_column(
        ForeignKey("folios.id"), index=True, nullable=False
    )
    multiplier: Mapped[int] = mapped_column(Integer, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
    exited_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    folio: Mapped[Folio] = relationship(lazy="selectin")
    positions: Mapped[list["Position"]] = relationship(
        back_populates="subscription",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="Position.stock_id",
    )

    def position_map(self) -> dict[int, "Position"]:
        """stock_id → Position."""
        return {p.stock_id: p for p in self.positions}

    def __repr__(self) -> str: 
        return (
            f"Subscription(id={self.id!r}, user={self.user_id!r}, "
            f"folio={self.folio_id}, mult={self.multiplier}, active={self.active})"
        )


class Position(Base):
    __tablename__ = "positions"
    __table_args__ = (
        UniqueConstraint(
            "subscription_id", "stock_id", name="uq_position_subscription_stock"
        ),
        CheckConstraint("quantity > 0", name="ck_position_quantity_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    subscription_id: Mapped[str] = mapped_column(
        ForeignKey("subscriptions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    stock_id: Mapped[int] = mapped_column(
        ForeignKey("stocks.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    subscription: Mapped[Subscription] = relationship(back_populates="positions")
    stock: Mapped[Stock] = relationship(lazy="joined")

    def __repr__(self) -> str: 
        return (
            f"Position(sub={self.subscription_id!r}, "
            f"stock_id={self.stock_id}, qty={self.quantity})"
        )