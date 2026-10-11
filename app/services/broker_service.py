"""Synthetic broker.

Deterministic in-process mock. Configurable latency and failure rate so tests
can exercise the retry path without touching a real exchange.
"""
from __future__ import annotations

import random
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from app.utils.helpers import utcnow


class TradeAction(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderStatus(str, Enum):
    EXECUTED = "EXECUTED"
    REJECTED = "REJECTED"


@dataclass(slots=True)
class TradeRequest:
    user_id: str
    ticker: str
    action: TradeAction
    quantity: int


@dataclass(slots=True)
class ExecutionReceipt:
    order_id: str
    status: str
    timestamp: datetime
    user_id: str
    ticker: str
    action: str
    quantity: int


class MockBroker:
    """Fake broker. Every call returns a receipt; no external I/O."""

    def __init__(
        self,
        latency_ms: int = 0,
        failure_rate: float = 0.0,
        max_retries: int = 2,
    ) -> None:
        self._latency_s = max(latency_ms, 0) / 1000.0
        self._failure_rate = min(max(failure_rate, 0.0), 1.0)
        self._max_retries = max(max_retries, 0)

    def execute(self, request: TradeRequest) -> ExecutionReceipt:
        if request.quantity <= 0:
            raise ValueError("quantity must be a positive integer")
        if not request.ticker:
            raise ValueError("ticker must not be empty")

        attempt = 0
        while True:
            if self._latency_s:
                time.sleep(self._latency_s)

            if self._failure_rate and random.random() < self._failure_rate:
                if attempt < self._max_retries:
                    attempt += 1
                    time.sleep(0.05 * attempt)
                    continue
                status = OrderStatus.REJECTED.value
            else:
                status = OrderStatus.EXECUTED.value

            return ExecutionReceipt(
                order_id=f"ord-{uuid.uuid4().hex[:12]}",
                status=status,
                timestamp=utcnow(),
                user_id=request.user_id,
                ticker=request.ticker,
                action=request.action.value,
                quantity=request.quantity,
            )