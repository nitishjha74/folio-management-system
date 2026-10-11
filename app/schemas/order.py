"""Execution receipt read schemas."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    order_id: str
    user_id: str
    folio_id: int | None = None
    subscription_id: str | None = None
    stock_id: int
    ticker: str
    action: str
    quantity: int
    status: str
    source: str
    reason: str | None = None
    timestamp: datetime


class OrderListOut(BaseModel):
    items: list[OrderOut]
    total: int
    limit: int
    offset: int