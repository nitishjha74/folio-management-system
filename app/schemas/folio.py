"""Folio read schemas."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class StockOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticker: str
    name: str


class FolioStockOut(BaseModel):
    """A folio's view of one stock: the ticker, the name, and its base qty."""

    model_config = ConfigDict(from_attributes=True)

    stock_id: int
    ticker: str
    name: str
    base_quantity: int


class FolioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None = None
    created_at: datetime
    updated_at: datetime
    stocks: list[FolioStockOut] = Field(default_factory=list)