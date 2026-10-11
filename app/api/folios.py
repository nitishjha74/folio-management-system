"""Folio read endpoints."""
from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import FolioServiceDep, SessionDep
from app.schemas.folio import FolioOut

router = APIRouter(prefix="/api/folios", tags=["folios"])


@router.get("", response_model=list[FolioOut], summary="List all folios")
def list_folios(
    db: SessionDep,
    service: FolioServiceDep,
) -> list[FolioOut]:
    folios = service.list_folios(db)
    return service.to_out_many(folios)


@router.get("/{folio_id}", response_model=FolioOut, summary="Get folio detail")
def get_folio(
    folio_id: int,
    db: SessionDep,
    service: FolioServiceDep,
) -> FolioOut:
    folio = service.get_folio(db, folio_id)
    return service.to_out(folio)