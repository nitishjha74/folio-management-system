"""Timezone-safe datetime helpers.
"""
from __future__ import annotations

from datetime import datetime, timezone


def utcnow() -> datetime:
    """Aware current UTC time."""
    return datetime.now(timezone.utc)


def to_utc(value: datetime) -> datetime:
    """Normalise any datetime to aware UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def iso_utc(value: datetime) -> str:
    """RFC3339 string with trailing Z, e.g. `2026-08-22T12:00:00Z`."""
    return to_utc(value).isoformat().replace("+00:00", "Z")