"""Admin-triggered stock replacement.

Contract: accept fast, fan out later.

1. Validate the folio and the current composition.
2. Snapshot the active subscribers (must happen *before* the composition
   changes, otherwise a concurrent subscribe could be double-counted).
3. Mutate the folio and persist the job in one transaction.
4. Hand the job id to Celery. Return 202. Never block on broker I/O.

The folio-level advisory lock serialises concurrent admin swaps so two
overlapping requests cannot both pass validation on stale state.
"""
from __future__ import annotations

import re
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.folio import FolioStock
from app.models.rebalance import RebalanceJob, RebalanceStatus
from app.models.subscription import Subscription
from app.schemas.rebalance import RebalanceRequest
from app.services.errors import NotFoundError, ValidationError
from app.services.folio_service import FolioService
from app.services.locks import folio_lock
from app.utils.helpers import utcnow

TICKER_PATTERN = re.compile(r"^[A-Z][A-Z0-9&.\-]{0,19}$")


class RebalanceService:
    def __init__(self, folio_service: FolioService) -> None:
        self._folios = folio_service

    # -------------------------------------------------------------- helpers

    @staticmethod
    def _normalise_ticker(raw: str, field_name: str) -> str:
        ticker = (raw or "").strip().upper()
        if not TICKER_PATTERN.match(ticker):
            raise ValidationError(f"{field_name} '{raw}' is not a valid ticker symbol")
        return ticker

    # ---------------------------------------------------------------- trigger

    def trigger(
        self, db: Session, payload: RebalanceRequest
    ) -> tuple[RebalanceJob, int]:
        # Folio-scoped advisory lock — serialises overlapping admin swaps.
        with folio_lock(db, payload.folio_id):
            folio = self._folios.get_folio(db, payload.folio_id)
            self._folios.validate_composition(folio)

            outgoing_ticker = self._normalise_ticker(
                payload.outgoing_ticker, "outgoing_ticker"
            )
            incoming_ticker = self._normalise_ticker(
                payload.incoming_ticker, "incoming_ticker"
            )

            outgoing_link = folio.link_for_ticker(outgoing_ticker)
            if outgoing_link is None:
                raise ValidationError(
                    f"Outgoing ticker '{outgoing_ticker}' is not part of "
                    f"folio '{folio.name}'"
                )
            if folio.link_for_ticker(incoming_ticker) is not None:
                raise ValidationError(
                    f"Incoming ticker '{incoming_ticker}' is already part of "
                    f"folio '{folio.name}'"
                )

            incoming_stock = self._folios.get_stock_by_ticker(db, incoming_ticker)

            incoming_base_quantity = (
                payload.incoming_base_quantity
                if payload.incoming_base_quantity is not None
                else outgoing_link.base_quantity
            )
            if incoming_base_quantity <= 0:
                raise ValidationError("incoming_base_quantity must be positive")

            # ---- Snapshot active subscribers before the composition changes.
            rows = db.execute(
                select(
                    Subscription.id, Subscription.user_id, Subscription.multiplier
                ).where(
                    Subscription.folio_id == folio.id,
                    Subscription.active.is_(True),
                )
            ).all()

            job = RebalanceJob(
                id=f"rb-{uuid.uuid4().hex[:12]}",
                folio_id=folio.id,
                folio_name=folio.name,
                outgoing_stock_id=outgoing_link.stock_id,
                outgoing_ticker=outgoing_link.stock.ticker,
                outgoing_base_quantity=outgoing_link.base_quantity,
                incoming_stock_id=incoming_stock.id,
                incoming_ticker=incoming_stock.ticker,
                incoming_base_quantity=incoming_base_quantity,
                status=RebalanceStatus.PENDING,
                subscribers_total=len(rows),
                subscriber_snapshot=[
                    {
                        "subscription_id": r.id,
                        "user_id": r.user_id,
                        "multiplier": r.multiplier,
                    }
                    for r in rows
                ],
                created_at=utcnow(),
            )
            db.add(job)

            # ---- Swap the folio composition in the same transaction.
            # If the incoming stock is already linked to this folio via a
            # concurrent request, the UniqueConstraint fires and this whole
            # transaction rolls back — correct behaviour.
            outgoing_link.stock_id = incoming_stock.id
            outgoing_link.base_quantity = incoming_base_quantity
            db.flush()

            db.commit()

            from app.workers.tasks import rebalance_fanout  

            rebalance_fanout.apply_async(args=[job.id], queue="rebalance")

            return job, len(rows)

    # ---------------------------------------------------------------- reads

    def get_job(self, db: Session, job_id: str) -> RebalanceJob:
        job = db.get(RebalanceJob, job_id)
        if job is None:
            raise NotFoundError(f"Rebalance job '{job_id}' was not found")
        return job

    def list_jobs(self, db: Session, limit: int = 100) -> list[RebalanceJob]:
        stmt = (
            select(RebalanceJob)
            .order_by(RebalanceJob.created_at.desc())
            .limit(limit)
        )
        return list(db.scalars(stmt).all())