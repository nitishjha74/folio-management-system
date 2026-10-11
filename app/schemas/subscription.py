"""Subscription request/response schemas."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.order import OrderOut


class PositionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    stock_id: int
    ticker: str
    quantity: int


class SubscriptionCreate(BaseModel):
    user_id: str = Field(min_length=1, description="Opaque user identifier")
    folio_id: int = Field(gt=0, description="Target folio id")
    multiplier: int = Field(
        gt=0,
        le=1000,
        description="Positive integer multiplier applied to every base quantity",
        examples=[3],
    )


class SubscriptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    folio_id: int
    folio_name: str | None = None
    multiplier: int
    active: bool
    created_at: datetime
    updated_at: datetime
    exited_at: datetime | None = None
    positions: list[PositionOut] = Field(default_factory=list)


class SubscribeResponse(BaseModel):
    subscription: SubscriptionOut
    orders: list[OrderOut]


class ExitResponse(BaseModel):
    subscription: SubscriptionOut
    orders: list[OrderOut]