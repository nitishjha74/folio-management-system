from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.utils.helpers import utcnow

FOLIO_SIZE = 12


class Folio(Base):
    __tablename__ = "folios"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    stocks: Mapped[list["FolioStock"]] = relationship(
        back_populates="folio",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="FolioStock.id",
    )

    # ---------------------------------------------------------------- helpers

    def stock_ids(self) -> list[int]:
        return [link.stock_id for link in self.stocks]

    def tickers(self) -> list[str]:
        return [link.stock.ticker for link in self.stocks]

    def link_for_ticker(self, ticker: str) -> "FolioStock | None":
        upper = ticker.upper()
        for link in self.stocks:
            if link.stock.ticker == upper:
                return link
        return None

    def __repr__(self) -> str:  
        return f"Folio(id={self.id}, name={self.name!r})"


class Stock(Base):
    __tablename__ = "stocks"

    id: Mapped[int] = mapped_column(primary_key=True)
    ticker: Mapped[str] = mapped_column(
        String(20), unique=True, nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    def __repr__(self) -> str: 
        return f"Stock(id={self.id}, ticker={self.ticker!r})"


class FolioStock(Base):
    __tablename__ = "folio_stocks"
    __table_args__ = (
        UniqueConstraint("folio_id", "stock_id", name="uq_folio_stock"),
        CheckConstraint("base_quantity > 0", name="ck_folio_stock_qty_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    folio_id: Mapped[int] = mapped_column(
        ForeignKey("folios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    stock_id: Mapped[int] = mapped_column(
        ForeignKey("stocks.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    base_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    folio: Mapped[Folio] = relationship(back_populates="stocks")
    stock: Mapped[Stock] = relationship(lazy="joined")

    def __repr__(self) -> str: 
        return (
            f"FolioStock(folio_id={self.folio_id}, "
            f"stock_id={self.stock_id}, qty={self.base_quantity})"
        )