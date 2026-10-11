"""Rebalance request/response schemas."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RebalanceRequest(BaseModel):
    folio_id: int = Field(gt=0)
    outgoing_ticker: str = Field(examples=["RELIANCE"])
    incoming_ticker: str = Field(examples=["IDEA"])
    incoming_base_quantity: int | None = Field(
        default=None,
        gt=0,
        description=(
            "Base quantity for the incoming stock. Defaults to the outgoing "
            "stock's base quantity when omitted."
        ),
    )


class RebalanceAccepted(BaseModel):
    job_id: str
    status: str
    folio_id: int
    folio_name: str
    outgoing_ticker: str
    incoming_ticker: str
    incoming_base_quantity: int
    active_subscribers_queued: int
    message: str


class RebalanceJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    folio_id: int
    folio_name: str
    outgoing_ticker: str
    outgoing_base_quantity: int
    incoming_ticker: str
    incoming_base_quantity: int
    status: str
    subscribers_total: int
    subscribers_processed: int
    subscribers_skipped: int
    subscribers_failed: int
    orders_created: int
    error: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None