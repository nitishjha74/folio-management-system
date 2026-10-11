"""Per-subscription mutual exclusion via Postgres advisory locks.

``pg_advisory_xact_lock`` is *transaction-scoped*: held until the surrounding
transaction commits or rolls back, released automatically on connection loss.
That makes it safe under Celery workers, multiple Uvicorn workers, and process
crashes — unlike a Python ``threading.Lock``.

The lock key is ``hashtext('sub:<id>')::bigint``, fitting Postgres's bigint
advisory-lock namespace. Hash collisions are possible in theory (32-bit) but
immaterial here: two unrelated subscriptions sharing a lock only serialise,
they never corrupt.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import text
from sqlalchemy.orm import Session


_LOCK_SQL = text("SELECT pg_advisory_xact_lock(hashtext(:k)::bigint)")


@contextmanager
def subscription_lock(session: Session, subscription_id: str) -> Iterator[None]:
    """Acquire the advisory lock for ``subscription_id``.

    The caller must be inside a transaction that commits or rolls back —
    the lock is released when that transaction ends.
    """
    session.execute(_LOCK_SQL, {"k": f"sub:{subscription_id}"})
    yield


@contextmanager
def folio_lock(session: Session, folio_id: int) -> Iterator[None]:
    """Advisory lock keyed on a folio. Used to serialise concurrent admin swaps."""
    session.execute(_LOCK_SQL, {"k": f"folio:{folio_id}"})
    yield