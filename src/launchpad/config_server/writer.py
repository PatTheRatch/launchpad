"""The config server's write path: log an event, mirror it, refresh the views.

One successful call does three things, in a deliberate order:

1. write to Huckleberry (single attempt, never retried — see
   :mod:`launchpad.services.experimental.huckleberry_logger`);
2. append the event to the local :class:`~launchpad.logbook.Logbook`, so
   Launchpad keeps its own copy of everything logged through it;
3. invalidate the shared preview cache, so the panel preview, the nightstand
   page, and the widget all reflect the new event on their next poll instead
   of up to 60 seconds later.

The mirror is written only after the upstream write succeeds: the logbook
records what *happened*, not what was attempted.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

from launchpad.logbook import Logbook
from launchpad.services.experimental.huckleberry_logger import (
    FeedLogError,
    HuckleberryLogger,
)

__all__ = ["FeedLogError", "LogWriter", "shared_writer"]

#: Event kinds accepted by ``POST /api/log/<kind>``.
KINDS = ("bottle", "diaper", "sleep")


class LogWriter:
    """Dispatches one validated event through the write→mirror→refresh chain."""

    def __init__(
        self,
        logger: HuckleberryLogger,
        logbook: Logbook,
        on_success: Callable[[], None] | None = None,
    ) -> None:
        self._logger = logger
        self._logbook = logbook
        self._on_success = on_success or (lambda: None)

    def log(self, kind: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Log one event; returns what was recorded.

        Raises ``ValueError`` for invalid input (nothing was written) and
        :class:`FeedLogError` when the upstream write failed (nothing was
        mirrored).
        """
        if kind == "bottle":
            recorded = self._logger.log_bottle(
                amount_ml=payload.get("amount_ml", 0),
                bottle_type=payload.get("bottle_type", "Formula"),
            )
        elif kind == "diaper":
            recorded = self._logger.log_diaper(
                mode=payload.get("mode", ""), notes=payload.get("notes")
            )
        elif kind == "sleep":
            recorded = self._logger.sleep(action=payload.get("action", ""))
        else:
            raise ValueError(f"Unknown event kind {kind!r}. Expected one of: {', '.join(KINDS)}.")

        self._logbook.record(kind, recorded)
        self._on_success()
        return recorded


_shared: LogWriter | None = None
_shared_lock = threading.Lock()


def shared_writer() -> LogWriter | None:
    """The process-wide writer, or ``None`` when logging is not configured.

    Mirrors the read side's gating: requires the ``baby_tracking`` flag and
    the Huckleberry credentials. Settings are read once per process — flip
    the flag, restart ``launchpad-config``.
    """
    global _shared
    with _shared_lock:
        if _shared is None:
            import os

            from launchpad.config.settings import load_settings
            from launchpad.config_server import preview as preview_module

            settings = load_settings()
            email = (os.getenv("HUCKLEBERRY_EMAIL") or "").strip()
            password = (os.getenv("HUCKLEBERRY_PASSWORD") or "").strip()
            if not settings.features.baby_tracking or not email or not password:
                return None
            _shared = LogWriter(
                logger=HuckleberryLogger(email=email, password=password),
                logbook=Logbook(),
                on_success=lambda: preview_module.shared_preview().invalidate(),
            )
        return _shared
