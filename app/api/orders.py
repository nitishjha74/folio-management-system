"""Order feed — scoped to the authenticated user."""
from __future__ import annotations

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from app.api.deps import CurrentUser, SessionDep
from app.models.order import Order
from app.schemas.order import OrderListOut, OrderOut

router = APIRouter(prefix="/api", tags=["orders"])


@router.get("/orders", response_model=OrderListOut)
def list_orders(
    user: CurrentUser,
    db: SessionDep,
    folio_id: int | None = Query(None),
    subscription_id: str | None = Query(None),
    ticker: str | None = Query(None),
    source: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> OrderListOut:
    # Always filtered to the caller — a user cannot see other users' orders.
    filters = [Order.user_id == user.user_id]
    if folio_id is not None:
        filters.append(Order.folio_id == folio_id)
    if subscription_id:
        filters.append(Order.subscription_id == subscription_id)
    if ticker:
        filters.append(Order.ticker == ticker.upper())
    if source:
        filters.append(Order.source == source.upper())

    total = db.scalar(select(func.count()).select_from(Order).where(*filters)) or 0

    stmt = (
        select(Order)
        .where(*filters)
        .order_by(Order.timestamp.desc(), Order.order_id.desc())
        .limit(limit)
        .offset(offset)
    )
    orders = list(db.scalars(stmt).all())

    return OrderListOut(
        items=[OrderOut.model_validate(o) for o in orders],
        total=total, limit=limit, offset=offset,
    )