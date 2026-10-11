"""Subscribe / exit. The per-user multiplier invariant lives here.

    order_quantity = folio_base_quantity * user_multiplier

Exit is the subtle case: it must liquidate the user's *current positions*,
not recompute from the folio. Otherwise a concurrent rebalance would cause
the exit to sell stock the user never held.

Every mutation of a subscription's positions is serialised via
``subscription_lock`` — the same advisory lock the rebalance fan-out takes.
"""
from __future__ import annotations

import uuid
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.folio import Folio
from app.models.order import Order, OrderSource
from app.models.subscription import Position, Subscription
from app.schemas.order import OrderOut
from app.schemas.subscription import (
    PositionOut,
    SubscriptionCreate,
    SubscriptionOut,
)
from app.services.broker_service import TradeAction
from app.services.errors import ConflictError, NotFoundError, ValidationError
from app.services.folio_service import FolioService
from app.services.locks import subscription_lock
from app.services.order_service import OrderRequest, OrderService
from app.utils.helpers import utcnow

MAX_MULTIPLIER = 1000


class SubscriptionService:
    def __init__(self, order_service: OrderService, folio_service: FolioService) -> None:
        self._orders = order_service
        self._folios = folio_service

    # ------------------------------------------------------------------ read

    def get_subscription(self, db: Session, subscription_id: str) -> Subscription:
        sub = db.get(Subscription, subscription_id)
        if sub is None:
            raise NotFoundError(f"Subscription '{subscription_id}' was not found")
        return sub

    def list_user_subscriptions(
        self, db: Session, user_id: str, active_only: bool = False
    ) -> Sequence[Subscription]:
        stmt = select(Subscription).where(Subscription.user_id == user_id)
        if active_only:
            stmt = stmt.where(Subscription.active.is_(True))
        stmt = stmt.order_by(Subscription.created_at.desc())
        return list(db.scalars(stmt).unique().all())

    # ------------------------------------------------------------- subscribe

    def subscribe(
        self, db: Session, payload: SubscriptionCreate
    ) -> tuple[Subscription, list[Order]]:
        user_id = payload.user_id.strip()
        if not user_id:
            raise ValidationError("user_id must be present")
        if payload.multiplier <= 0:
            raise ValidationError("multiplier must be a positive integer")
        if payload.multiplier > MAX_MULTIPLIER:
            raise ValidationError(f"multiplier must not exceed {MAX_MULTIPLIER}")

        folio: Folio = self._folios.get_folio(db, payload.folio_id)
        self._folios.validate_composition(folio)

        # Application-level check for a friendly 409; the partial unique index
        # on subscriptions is the real guarantee.
        existing_id = db.scalar(
            select(Subscription.id).where(
                Subscription.user_id == user_id,
                Subscription.folio_id == folio.id,
                Subscription.active.is_(True),
            )
        )
        if existing_id:
            raise ConflictError(
                f"User '{user_id}' already has an active subscription to "
                f"'{folio.name}' ({existing_id}). Exit it before subscribing again."
            )

        subscription = Subscription(
            id=f"sub-{uuid.uuid4().hex[:12]}",
            user_id=user_id,
            folio_id=folio.id,
            multiplier=payload.multiplier,
            active=True,
            created_at=utcnow(),
        )
        db.add(subscription)
        db.flush()  # assign id and make it visible to FK's below

        requests: list[OrderRequest] = []
        for link in folio.stocks:
            qty = link.base_quantity * subscription.multiplier
            subscription.positions.append(
                Position(stock_id=link.stock_id, quantity=qty)
            )
            requests.append(
                OrderRequest(
                    user_id=user_id,
                    stock_id=link.stock_id,
                    ticker=link.stock.ticker,
                    action=TradeAction.BUY,
                    quantity=qty,
                    folio_id=folio.id,
                    subscription_id=subscription.id,
                    source=OrderSource.SUBSCRIPTION,
                    reason=f"Subscribe {folio.name} @ {subscription.multiplier}x",
                )
            )

        orders = self._orders.place_many(db, requests)
        db.commit()
        db.refresh(subscription)
        return subscription, orders

    # ------------------------------------------------------------------ exit

    def exit_subscription(
        self, db: Session, subscription_id: str
    ) -> tuple[Subscription, list[Order]]:
        # Take the same advisory lock the rebalance fan-out uses. Serialises
        # this with any in-flight or queued rebalance for the same subscription.
        with subscription_lock(db, subscription_id):
            subscription = self.get_subscription(db, subscription_id)
            if not subscription.active:
                raise ValidationError(
                    f"Subscription '{subscription_id}' is already inactive"
                )

            folio = self._folios.get_folio(db, subscription.folio_id)
            positions = list(subscription.positions)
            if not positions:
                raise ValidationError(
                    f"Subscription '{subscription_id}' has no open positions"
                )

            # Flip active *before* submitting sells so any rebalance leg that
            # was waiting on the lock observes `active == False` and skips.
            subscription.active = False
            subscription.exited_at = utcnow()
            db.flush()

            requests = [
                OrderRequest(
                    user_id=subscription.user_id,
                    stock_id=p.stock_id,
                    ticker=p.stock.ticker,
                    action=TradeAction.SELL,
                    quantity=p.quantity,
                    folio_id=folio.id,
                    subscription_id=subscription.id,
                    source=OrderSource.EXIT,
                    reason=f"Exit {folio.name} @ {subscription.multiplier}x",
                )
                for p in positions
            ]
            orders = self._orders.place_many(db, requests)

            for p in positions:
                db.delete(p)

            db.commit()
            db.refresh(subscription)
            return subscription, orders

    # ------------------------------------------------------- ORM → schema

    @staticmethod
    def to_out(subscription: Subscription) -> SubscriptionOut:
        return SubscriptionOut(
            id=subscription.id,
            user_id=subscription.user_id,
            folio_id=subscription.folio_id,
            folio_name=subscription.folio.name if subscription.folio else None,
            multiplier=subscription.multiplier,
            active=subscription.active,
            created_at=subscription.created_at,
            updated_at=subscription.updated_at,
            exited_at=subscription.exited_at,
            positions=[
                PositionOut(
                    stock_id=p.stock_id,
                    ticker=p.stock.ticker,
                    quantity=p.quantity,
                )
                for p in subscription.positions
            ],
        )

    @classmethod
    def orders_to_out(cls, orders: list[Order]) -> list[OrderOut]:
        return [OrderOut.model_validate(o) for o in orders]