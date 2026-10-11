"""Folio read + validation service.

Reads return ORM models so callers can compose further queries; API-layer
conversion happens through ``to_out()`` helpers that keep schemas free of ORM
imports. This is the only place where folio composition rules are enforced —
every write path (subscribe, rebalance) funnels through ``validate_composition``.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.folio import FOLIO_SIZE, Folio, FolioStock, Stock
from app.schemas.folio import FolioOut, FolioStockOut
from app.services.errors import NotFoundError, ValidationError


class FolioService:
    """Stateless — safe to instantiate per request."""

    # ------------------------------------------------------------------ read

    def list_folios(self, db: Session) -> list[Folio]:
        stmt = select(Folio).order_by(Folio.name)
        return list(db.scalars(stmt).unique().all())

    def get_folio(self, db: Session, folio_id: int) -> Folio:
        folio = db.get(Folio, folio_id)
        if folio is None:
            raise NotFoundError(f"Folio {folio_id} was not found")
        return folio

    def get_stock_by_ticker(self, db: Session, ticker: str) -> Stock:
        """Look up a Stock by ticker. Raises 404 if it does not exist."""
        upper = ticker.strip().upper()
        stock = db.scalar(select(Stock).where(Stock.ticker == upper))
        if stock is None:
            raise NotFoundError(f"Stock '{upper}' is not in the ticker universe")
        return stock

    def list_tickers(self, db: Session) -> list[Stock]:
        stmt = select(Stock).order_by(Stock.ticker)
        return list(db.scalars(stmt).all())

    # ----------------------------------------------------------- validation

    @staticmethod
    def validate_composition(folio: Folio) -> None:
        """Enforce the invariant that every folio holds exactly 12 valid stocks.

        Called by subscribe and rebalance. Raises ValidationError (HTTP 400)
        if the folio is corrupted — which should be impossible given the
        seeder and rebalance service, but this is the backstop.
        """
        if len(folio.stocks) != FOLIO_SIZE:
            raise ValidationError(
                f"Folio '{folio.name}' must contain exactly {FOLIO_SIZE} stocks "
                f"(found {len(folio.stocks)})"
            )
        for link in folio.stocks:
            if link.stock is None or not link.stock.ticker:
                raise ValidationError(
                    f"Folio '{folio.name}' has a folio_stock row with no linked stock"
                )
            if link.base_quantity <= 0:
                raise ValidationError(
                    f"Folio '{folio.name}' stock '{link.stock.ticker}' "
                    f"must have a positive base quantity"
                )

    # ------------------------------------------------------- ORM → schema

    @staticmethod
    def to_out(folio: Folio) -> FolioOut:
        """Flatten Folio + FolioStock + Stock into the API response shape."""
        return FolioOut(
            id=folio.id,
            name=folio.name,
            description=folio.description,
            created_at=folio.created_at,
            updated_at=folio.updated_at,
            stocks=[
                FolioStockOut(
                    stock_id=link.stock_id,
                    ticker=link.stock.ticker,
                    name=link.stock.name,
                    base_quantity=link.base_quantity,
                )
                for link in folio.stocks
            ],
        )

    @classmethod
    def to_out_many(cls, folios: list[Folio]) -> list[FolioOut]:
        return [cls.to_out(f) for f in folios]