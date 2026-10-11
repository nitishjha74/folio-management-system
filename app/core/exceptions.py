"""Application exception hierarchy.

`AppError` is the base for every expected domain failure. The FastAPI handler
in `main.py` maps them to `{success, message, data}` responses with the
correct status code. Unexpected exceptions fall through to a 500 handler.
"""
from __future__ import annotations


class AppError(Exception):
    """Base for all application-raised errors."""

    status_code: int = 400
    error_code: str = "app_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ValidationError(AppError):
    """Request is well-formed but semantically invalid."""

    status_code = 400
    error_code = "validation_error"


class NotFoundError(AppError):
    """A referenced entity does not exist."""

    status_code = 404
    error_code = "not_found"


class ConflictError(AppError):
    """Request conflicts with current state."""

    status_code = 409
    error_code = "conflict"