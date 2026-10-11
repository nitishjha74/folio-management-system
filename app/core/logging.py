"""Logger factory so every module logs with the same format."""
from __future__ import annotations

import logging

from app.core.config import get_settings


_CONFIGURED = False


def _configure_root() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-8s %(name)s | %(message)s",
    )
    _CONFIGURED = True


def build_logger(name: str) -> logging.Logger:
    _configure_root()
    return logging.getLogger(name)