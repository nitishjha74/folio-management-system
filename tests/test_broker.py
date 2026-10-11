"""Synthetic broker — pure unit tests, no DB, no client."""
from __future__ import annotations

import pytest

from app.services.broker_service import (
    MockBroker,
    OrderStatus,
    TradeAction,
    TradeRequest,
)


def test_broker_returns_execution_receipt():
    broker = MockBroker()
    receipt = broker.execute(
        TradeRequest(
            user_id="user-1",
            ticker="RELIANCE",
            action=TradeAction.BUY,
            quantity=6,
        )
    )

    assert receipt.order_id.startswith("ord-")
    assert receipt.status == OrderStatus.EXECUTED.value
    assert receipt.user_id == "user-1"
    assert receipt.ticker == "RELIANCE"
    assert receipt.action == "BUY"
    assert receipt.quantity == 6
    assert receipt.timestamp.tzinfo is not None


def test_broker_rejects_non_positive_quantity():
    with pytest.raises(ValueError):
        MockBroker().execute(
            TradeRequest(user_id="u", ticker="TCS", action=TradeAction.SELL, quantity=0)
        )


def test_broker_rejects_empty_ticker():
    with pytest.raises(ValueError):
        MockBroker().execute(
            TradeRequest(user_id="u", ticker="", action=TradeAction.BUY, quantity=1)
        )


def test_broker_returns_rejected_status_after_exhausting_retries():
    # failure_rate=1.0 → every attempt fails; max_retries=1 → 2 attempts total.
    broker = MockBroker(failure_rate=1.0, max_retries=1)
    receipt = broker.execute(
        TradeRequest(user_id="u", ticker="INFY", action=TradeAction.BUY, quantity=3)
    )
    assert receipt.status == OrderStatus.REJECTED.value