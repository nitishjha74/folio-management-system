"""Celery task definitions. Thin wrapper — no business logic here."""
from __future__ import annotations

from celery import shared_task

from app.core.logging import build_logger
from app.db.database import SessionLocal
from app.services.broker_service import MockBroker
from app.services.order_service import OrderService
from app.workers.celery_app import celery_app  # noqa: F401 — register app
from app.workers.fanout import run_rebalance_fanout

logger = build_logger("app.workers.tasks")


@shared_task(
    bind=True,
    name="rebalance.fanout",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=60,
    retry_jitter=True,
    max_retries=5,
    acks_late=True,
)
def rebalance_fanout(self, job_id: str) -> dict[str, int]:
    logger.info("rebalance.fanout start job_id=%s attempt=%s", job_id, self.request.retries)

    order_service = OrderService(MockBroker())

    try:
        result = run_rebalance_fanout(
            job_id=job_id,
            session_factory=SessionLocal,
            order_service=order_service,
        )
    except Exception:
        logger.exception("rebalance.fanout crashed job_id=%s", job_id)
        raise

    logger.info("rebalance.fanout done job_id=%s result=%s", job_id, result)
    return result