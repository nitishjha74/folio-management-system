"""Admin rebalance endpoints."""
from __future__ import annotations

from fastapi import APIRouter, status

from app.api.deps import RebalanceServiceDep, SessionDep
from app.schemas.rebalance import (
    RebalanceAccepted,
    RebalanceJobOut,
    RebalanceRequest,
)

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.post(
    "/rebalance",
    response_model=RebalanceAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Swap a stock inside a folio and cascade asynchronously to subscribers",
)
def trigger_rebalance(
    payload: RebalanceRequest,
    db: SessionDep,
    service: RebalanceServiceDep,
) -> RebalanceAccepted:
    job, queued = service.trigger(db, payload)
    return RebalanceAccepted(
        job_id=job.id,
        status=job.status,
        folio_id=job.folio_id,
        folio_name=job.folio_name,
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


@router.get(
    "/rebalances",
    response_model=list[RebalanceJobOut],
    summary="List rebalance jobs (newest first)",
)
def list_rebalances(db: SessionDep, service: RebalanceServiceDep) -> list[RebalanceJobOut]:
    jobs = service.list_jobs(db)
    return [RebalanceJobOut.model_validate(j) for j in jobs]


@router.get(
    "/rebalances/{job_id}",
    response_model=RebalanceJobOut,
    summary="Get a rebalance job",
)
def get_rebalance(
    job_id: str, db: SessionDep, service: RebalanceServiceDep
) -> RebalanceJobOut:
    job = service.get_job(db, job_id)
    return RebalanceJobOut.model_validate(job)


@router.get(
    "/tickers",
    response_model=list[str],
    summary="Ticker universe accepted by the rebalance endpoint",
)
def list_tickers(db: SessionDep, service: RebalanceServiceDep) -> list[str]:
    from app.services.folio_service import FolioService

    return [s.ticker for s in FolioService().list_tickers(db)]