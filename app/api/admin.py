"""Admin endpoints — every route requires an ADMIN JWT."""
from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.api.deps import AdminUser, RebalanceServiceDep, SessionDep
from app.core.csrf import verify_csrf
from app.schemas.rebalance import (
    RebalanceAccepted, RebalanceJobOut, RebalanceRequest,
)

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.post(
    "/rebalance",
    response_model=RebalanceAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(verify_csrf)],
)
def trigger_rebalance(
    payload: RebalanceRequest,
    admin: AdminUser,          # 403 unless role == ADMIN
    db: SessionDep,
    service: RebalanceServiceDep,
) -> RebalanceAccepted:
    job, queued = service.trigger(db, payload)
    return RebalanceAccepted(
        job_id=job.id, status=job.status,
        folio_id=job.folio_id, folio_name=job.folio_name,
        outgoing_ticker=job.outgoing_ticker,
        incoming_ticker=job.incoming_ticker,
        incoming_base_quantity=job.incoming_base_quantity,
        active_subscribers_queued=queued,
        message=(
            f"Rebalance triggered successfully. "
            f"{job.outgoing_ticker} -> {job.incoming_ticker}. "
            f"Active subscribers queued: {queued}"
        ),
    )


@router.get("/rebalances", response_model=list[RebalanceJobOut])
def list_rebalances(
    admin: AdminUser, db: SessionDep, service: RebalanceServiceDep
) -> list[RebalanceJobOut]:
    return [RebalanceJobOut.model_validate(j) for j in service.list_jobs(db)]


@router.get("/rebalances/{job_id}", response_model=RebalanceJobOut)
def get_rebalance(
    job_id: str, admin: AdminUser, db: SessionDep, service: RebalanceServiceDep
) -> RebalanceJobOut:
    return RebalanceJobOut.model_validate(service.get_job(db, job_id))


@router.get("/tickers", response_model=list[str])
def list_tickers(
    admin: AdminUser, db: SessionDep, service: RebalanceServiceDep
) -> list[str]:
    from app.services.folio_service import FolioService
    return [s.ticker for s in FolioService().list_tickers(db)]