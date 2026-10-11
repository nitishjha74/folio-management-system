"""Backwards-compatible re-exports.

Domain errors now live in `app.core.exceptions`. This module exists so that
services and workers can keep importing from `app.services.errors` without
churn. New code should import directly from `app.core.exceptions`.
"""
from __future__ import annotations

from app.core.exceptions import (
    AppError,
    ConflictError,
    NotFoundError,
    ValidationError,
)

# Historical alias — some services imported `DomainError`.
DomainError = AppError

__all__ = [
    "AppError",
    "ConflictError",
    "DomainError",
    "NotFoundError",
    "ValidationError",
]