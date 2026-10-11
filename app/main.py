"""FastAPI application entry point."""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.logging import build_logger
from app.db.database import Base, SessionLocal, engine
from app.db.seed import seed_folios

# Routers
from app.api.admin import router as admin_router
from app.api.folios import router as folios_router
from app.api.orders import router as orders_router
from app.api.users import router as users_router

logger = build_logger("app.main")
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Import models so metadata is populated before create_all().

    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        created = seed_folios(db)
        if created:
            logger.info("startup: seeded %s folios", created)
        else:
            logger.info("startup: folios already present")

    logger.info("startup complete")
    try:
        yield
    finally:
        engine.dispose()
        logger.info("shutdown complete")


app = FastAPI(
    title=getattr(settings, "app_name", "Folio Management & Auto-Rebalancing Trading System"),
    version=getattr(settings, "app_version", "1.0.0"),
    description=(
        "Basket-trading prototype. Users subscribe to 12-stock **Folios** with "
        "a quantity multiplier; administrators swap stocks inside a Folio and "
        "the change cascades asynchronously via Celery.\n\n"
        "Core invariant: `order_quantity = folio_base_quantity * user_multiplier`."
    ),
    lifespan=lifespan,
)


# ---------------------------------------------------------
# Domain Error Handler
# ---------------------------------------------------------
@app.exception_handler(AppError)
async def domain_error_handler(_request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "message": exc.message, "data": None},
    )


# ---------------------------------------------------------
# Validation Error Handler
# ---------------------------------------------------------
@app.exception_handler(RequestValidationError)
async def validation_error_handler(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    errors: dict[str, str] = {}
    for error in exc.errors():
        loc = error.get("loc") or []
        field = loc[-1] if loc else "body"
        errors[str(field)] = error.get("msg", "invalid")
    return JSONResponse(
        status_code=422,
        content={"message": "Field Validation Error", "errors": errors},
    )


# ---------------------------------------------------------
# Internal Server Error Handler
# ---------------------------------------------------------
@app.exception_handler(Exception)
async def internal_server_error_handler(
    _request: Request, exc: Exception
) -> JSONResponse:
    logger.error("Unhandled exception: %s", exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"success": False, "message": "Internal server error", "data": None},
    )


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(folios_router)
app.include_router(users_router)
app.include_router(orders_router)
app.include_router(admin_router)


# Serve frontend at / (last so /api/* and /docs win).
_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
if _STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(_STATIC_DIR), html=True), name="frontend")
else:
    logger.info("static directory not present; skipping static mount")