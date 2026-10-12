"""FastAPI application entry point."""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.admin import router as admin_router
from app.api.auth import router as auth_router
from app.api.folios import router as folios_router
from app.api.orders import router as orders_router
from app.api.users import router as users_router
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.logging import build_logger
from app.db.database import Base, SessionLocal, engine
from app.db.seed import seed_folios

logger = build_logger("app.main")
settings = get_settings()

_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app import models  # noqa: F401
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        created = seed_folios(db)
        if created:
            logger.info("startup: seeded %s folios", created)
        else:
            logger.info("startup: folios present")

    logger.info("startup complete")
    try:
        yield
    finally:
        engine.dispose()
        logger.info("shutdown complete")


app = FastAPI(
    title=getattr(settings, "app_name", "Folio Management"),
    version=getattr(settings, "app_version", "1.0.0"),
    lifespan=lifespan,
)


# ---------------------------------------------------------------- errors

@app.exception_handler(AppError)
async def domain_error_handler(_request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "message": exc.message, "data": None},
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    errors: dict[str, str] = {}
    for error in exc.errors():
        loc = error.get("loc") or []
        field = str(loc[-1]) if loc else "body"
        errors[field] = str(error.get("msg", "invalid"))
    return JSONResponse(
        status_code=422,
        content={"message": "Field Validation Error", "errors": errors},
    )


@app.exception_handler(Exception)
async def internal_server_error_handler(
    _request: Request, exc: Exception
) -> JSONResponse:
    logger.error("Unhandled exception: %s", exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"success": False, "message": "Internal server error", "data": None},
    )


# ---------------------------------------------------------------- health

@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok"}


# ---------------------------------------------------------------- api

app.include_router(auth_router)
app.include_router(folios_router)
app.include_router(users_router)
app.include_router(orders_router)
app.include_router(admin_router)


# ---------------------------------------------------------------- static assets
# Mount under /static so clean URLs like /user/dashboard do not collide.

if _STATIC_DIR.exists():
    app.mount(
        "/static",
        StaticFiles(directory=str(_STATIC_DIR)),
        name="static",
    )


# ---------------------------------------------------------------- pages
# HTML is served through explicit routes so URLs are clean.

def _page(filename: str) -> FileResponse:
    return FileResponse(_STATIC_DIR / filename)


@app.get("/", include_in_schema=False)
def page_login() -> FileResponse:
    return _page("index.html")


@app.get("/login", include_in_schema=False)
def page_login_alias() -> FileResponse:
    return _page("index.html")


@app.get("/register", include_in_schema=False)
def page_register() -> FileResponse:
    return _page("register.html")


@app.get("/user/dashboard", include_in_schema=False)
def page_user_dashboard() -> FileResponse:
    return _page("user-dashboard.html")


@app.get("/admin/dashboard", include_in_schema=False)
def page_admin_dashboard() -> FileResponse:
    return _page("admin-dashboard.html")