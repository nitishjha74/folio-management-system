"""Folio reads — authenticated (either role)."""
from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import CurrentUser, FolioServiceDep, SessionDep
from app.schemas.folio import FolioOut

router = APIRouter(prefix="/api/folios", tags=["folios"])


@router.get("", response_model=list[FolioOut])
def list_folios(
    user: CurrentUser, db: SessionDep, service: FolioServiceDep
) -> list[FolioOut]:
    return service.to_out_many(service.list_folios(db))


@router.get("/{folio_id}", response_model=FolioOut)
def get_folio(
    folio_id: int, user: CurrentUser, db: SessionDep, service: FolioServiceDep
) -> FolioOut:
    return service.to_out(service.get_folio(db, folio_id))