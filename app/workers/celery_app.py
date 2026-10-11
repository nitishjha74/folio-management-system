"""The Celery application object.

    celery -A app.workers.celery_app:celery_app worker -Q rebalance --loglevel=info
"""
from __future__ import annotations

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "folio",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_default_retry_delay=5,
    task_max_retries=5,
    result_expires=3600,
    task_always_eager=settings.celery_task_always_eager,
    task_eager_propagates=True,
)

celery_app.conf.task_routes = {
    "rebalance.fanout": {"queue": "rebalance"},
}


celery_app.set_default()