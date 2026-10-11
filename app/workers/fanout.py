"""Sync fan-out engine for one rebalance job.

No Celery imports — callable from tests, a CLI repair script, or the task
wrapper. Idempotency: re-running on the same job id re-reads the snapshot
and re-checks `subscription.active` under an advisory lock, so a user who
has exited in the meantime is skipped.

Concurrency: subscriber legs are processed through a bounded ThreadPoolExecutor.
Each leg opens its own Session (SQLAlchemy Sessions are not thread-safe) and
acquires the same subscription-scoped advisory lock used by exit — which is
what makes the exit/rebalance race correct.
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.models.order import OrderSource
from app.models.rebalance import RebalanceJob, RebalanceStatus
from app.models.subscription import Position, Subscription
from app.services.broker_service import MockBroker, OrderStatus, TradeAction
from app.services.locks import subscription_lock
from app.services.order_service import OrderRequest, OrderService
from app.utils.helpers import utcnow

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class _JobContext:
    job_id: str
    folio_id: int
    folio_name: str
    outgoing_stock_id: int
    outgoing_ticker: str
    outgoing_base_quantity: int
    incoming_stock_id: int
    incoming_ticker: str
    incoming_base_quantity: int


@dataclass(slots=True)
class _Outcome:
    processed: bool
    orders: int
    failed: bool = False


def run_rebalance_fanout(
    *,
    job_id: str,
    session_factory: sessionmaker[Session],
    order_service: OrderService,
    concurrency: int | None = None,
) -> dict[str, int]:
    """Process one rebalance job. Idempotent on ``job_id``."""
    concurrency = concurrency or settings.rebalance_concurrency
    broker_workers = min(concurrency, 8)

    # ---- 1. Load job row, flip to RUNNING, grab snapshot -------------------
    with session_factory() as db:
        job = db.get(RebalanceJob, job_id)
        if job is None:
            logger.warning("Rebalance job %s not found", job_id)
            return {"processed": 0, "skipped": 0, "failed": 0, "orders": 0}

        job.status = RebalanceStatus.RUNNING
        job.started_at = utcnow()
        snapshot = list(job.subscriber_snapshot or [])
        context = _JobContext(
            job_id=job.id,
            folio_id=job.folio_id,
            folio_name=job.folio_name,
            outgoing_stock_id=job.outgoing_stock_id,
            outgoing_ticker=job.outgoing_ticker,
            outgoing_base_quantity=job.outgoing_base_quantity,
            incoming_stock_id=job.incoming_stock_id,
            incoming_ticker=job.incoming_ticker,
            incoming_base_quantity=job.incoming_base_quantity,
        )
        db.commit()

    # ---- 2. Fan out with bounded concurrency ------------------------------
    processed = skipped = failed = orders_created = 0
    errors: list[str] = []

    if snapshot:
        with ThreadPoolExecutor(max_workers=broker_workers) as pool:
            futures = {
                pool.submit(
                    _process_subscriber,
                    session_factory=session_factory,
                    order_service=order_service,
                    context=context,
                    entry=entry,
                ): entry
                for entry in snapshot
            }
            for future in as_completed(futures):
                entry = futures[future]
                try:
                    result = future.result()
                except Exception as exc:  # noqa: BLE001
                    failed += 1
                    errors.append(f"{type(exc).__name__}: {exc}")
                    logger.exception(
                        "Rebalance %s failed for subscription %s",
                        context.job_id,
                        entry.get("subscription_id"),
                    )
                    continue

                if result.failed:
                    failed += 1
                elif result.processed:
                    processed += 1
                else:
                    skipped += 1
                orders_created += result.orders

    # ---- 3. Persist the job summary ---------------------------------------
    with session_factory() as db:
        job = db.get(RebalanceJob, job_id)
        if job is None:  # pragma: no cover
            return {"processed": 0, "skipped": 0, "failed": 0, "orders": 0}

        job.subscribers_processed = processed
        job.subscribers_skipped = skipped
        job.subscribers_failed = failed
        job.orders_created = orders_created
        job.status = (
            RebalanceStatus.COMPLETED if not errors else RebalanceStatus.FAILED
        )
        job.error = "; ".join(errors[:5]) if errors else None
        job.completed_at = utcnow()
        db.commit()

    logger.info(
        "Rebalance %s finished: processed=%d skipped=%d failed=%d orders=%d",
        job_id, processed, skipped, failed, orders_created,
    )
    return {
        "processed": processed,
        "skipped": skipped,
        "failed": failed,
        "orders": orders_created,
    }


def _process_subscriber(
    *,
    session_factory: sessionmaker[Session],
    order_service: OrderService,
    context: _JobContext,
    entry: dict,
) -> _Outcome:
    """Execute the SELL-then-BUY leg for one subscriber.

    Runs in its own thread with its own Session. Acquires the same advisory
    lock used by exit_subscription, then re-checks `active` inside the lock.
    """
    subscription_id: str = entry["subscription_id"]

    with session_factory() as db:
        with subscription_lock(db, subscription_id):
            subscription = db.get(Subscription, subscription_id)
            if subscription is None or not subscription.active:
                db.rollback()
                return _Outcome(processed=False, orders=0)

            positions = subscription.position_map()
            multiplier = subscription.multiplier

            # Sell the *actual* holding if present; fall back to base × mult
            # for defence against historical rows missing a Position.
            held = positions.get(context.outgoing_stock_id)
            sell_qty = (
                held.quantity
                if held is not None
                else context.outgoing_base_quantity * multiplier
            )
            buy_qty = context.incoming_base_quantity * multiplier

            if sell_qty <= 0 or buy_qty <= 0:
                db.rollback()
                return _Outcome(processed=False, orders=0)

            reason = (
                f"{context.outgoing_ticker} -> {context.incoming_ticker} "
                f"({context.job_id})"
            )
            orders = order_service.place_many(
                db,
                [
                    OrderRequest(
                        user_id=subscription.user_id,
                        stock_id=context.outgoing_stock_id,
                        ticker=context.outgoing_ticker,
                        action=TradeAction.SELL,
                        quantity=sell_qty,
                        folio_id=context.folio_id,
                        subscription_id=subscription.id,
                        source=OrderSource.REBALANCE,
                        reason=reason,
                    ),
                    OrderRequest(
                        user_id=subscription.user_id,
                        stock_id=context.incoming_stock_id,
                        ticker=context.incoming_ticker,
                        action=TradeAction.BUY,
                        quantity=buy_qty,
                        folio_id=context.folio_id,
                        subscription_id=subscription.id,
                        source=OrderSource.REBALANCE,
                        reason=reason,
                    ),
                ],
            )

            all_executed = all(o.status == OrderStatus.EXECUTED.value for o in orders)
            if not all_executed:
                # Receipts persisted for audit; position left untouched so a
                # retry can be applied safely.
                db.commit()
                logger.warning(
                    "Rebalance %s: broker rejected a leg for subscription %s",
                    context.job_id,
                    subscription.id,
                )
                return _Outcome(processed=False, orders=len(orders), failed=True)

            if held is not None:
                db.delete(held)
            db.add(
                Position(
                    subscription_id=subscription.id,
                    stock_id=context.incoming_stock_id,
                    quantity=buy_qty,
                )
            )
            db.commit()
            return _Outcome(processed=True, orders=len(orders))