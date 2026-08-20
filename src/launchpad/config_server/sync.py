"""Keep Launchpad's local mirror of the care history current.

Runs one background thread that:

* **backfills** a long window once at startup, so the mirror holds real
  history rather than only what happens from now on;
* **re-syncs a short recent window** on a slow interval, which is enough to
  catch anything logged in the app;
* **syncs immediately when poked** — the real-time watcher pokes it, so an
  entry logged by anyone lands in the mirror within seconds.

Sync is best-effort, like the watcher: failures are recorded and retried, and
nothing here can take down the config server. The mirror falling behind makes
the archive stale, never the dashboard wrong — the dashboard reads live.
"""

from __future__ import annotations

import threading
import time
from typing import Any

from launchpad.logbook import Logbook
from launchpad.services.experimental.huckleberry_sync import HuckleberrySync, SyncError

__all__ = ["SyncError", "SyncScheduler", "scheduler", "start_scheduler", "stop_scheduler"]

#: How much history to pull the first time, so the archive starts populated.
BACKFILL_DAYS = 120.0

#: The routine window. Short, because it is reconciled (deletes included) and
#: runs often; long enough to cover a missed cycle or a clock skew.
RECENT_DAYS = 2.0

#: Time between routine syncs when nothing pokes us.
INTERVAL_SECONDS = 900.0

#: Backoff after a failure, so an outage does not become a hot loop.
_RETRY_SECONDS = 120.0


class SyncScheduler:
    """Backfills once, then keeps a recent window fresh."""

    def __init__(
        self,
        syncer: HuckleberrySync,
        logbook: Logbook,
        interval_seconds: float = INTERVAL_SECONDS,
        backfill_days: float = BACKFILL_DAYS,
        recent_days: float = RECENT_DAYS,
    ) -> None:
        self._syncer = syncer
        self._logbook = logbook
        self._interval = interval_seconds
        self._backfill_days = backfill_days
        self._recent_days = recent_days
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._backfilled = False
        self._last_report: dict[str, Any] | None = None
        self._last_error: str | None = None
        self._last_run_at: float | None = None
        self._runs = 0

    # -- lifecycle --------------------------------------------------------- #

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(
            target=self._loop, name="huckleberry-sync", daemon=True
        )
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        self._wake.set()
        thread = self._thread
        if thread is not None:
            thread.join(timeout=timeout)

    def poke(self) -> None:
        """Ask for a sync as soon as possible (called by the watcher)."""
        self._wake.set()

    # -- work -------------------------------------------------------------- #

    def sync_now(self, days: float | None = None) -> dict[str, Any]:
        """Run one sync synchronously and return its report.

        Raises :class:`SyncError` so callers can report a real reason.
        """
        window = days if days is not None else self._recent_days
        report = self._syncer.sync(days=window)
        with self._lock:
            self._last_report = report.as_dict()
            self._last_error = None
            self._last_run_at = time.time()
            self._runs += 1
        return report.as_dict()

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                if not self._backfilled:
                    self.sync_now(days=self._backfill_days)
                    self._backfilled = True
                else:
                    self.sync_now()
                delay = self._interval
            except Exception as exc:
                with self._lock:
                    self._last_error = f"{type(exc).__name__}: {exc}"
                delay = _RETRY_SECONDS
            self._wake.wait(timeout=delay)
            self._wake.clear()

    # -- observability ----------------------------------------------------- #

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "running": self._thread is not None and self._thread.is_alive(),
                "backfilled": self._backfilled,
                "runs": self._runs,
                "last_run_at": self._last_run_at,
                "last_report": self._last_report,
                "last_error": self._last_error,
                "counts": self._logbook.counts(),
                "span": list(self._logbook.span()),
            }


_scheduler: SyncScheduler | None = None
_lock = threading.Lock()


def scheduler() -> SyncScheduler | None:
    """The running scheduler, or ``None`` when mirroring is not configured."""
    return _scheduler


def shared_logbook() -> Logbook:
    """The process-wide logbook (used by read-only endpoints)."""
    return Logbook()


def start_scheduler() -> SyncScheduler | None:
    """Start mirroring if configured; return the scheduler or ``None``.

    Requires the ``baby_tracking`` flag and Huckleberry credentials, and can
    be disabled with ``LAUNCHPAD_SYNC=0``. Any failure to start is swallowed:
    the mirror is an archive, and the dashboard runs fine without it.
    """
    global _scheduler
    with _lock:
        if _scheduler is not None:
            return _scheduler

        import os

        from launchpad.config.settings import load_settings

        if (os.getenv("LAUNCHPAD_SYNC", "1").strip().lower()) in {"0", "false", "no", "off"}:
            return None

        settings = load_settings()
        email = (os.getenv("HUCKLEBERRY_EMAIL") or "").strip()
        password = (os.getenv("HUCKLEBERRY_PASSWORD") or "").strip()
        if not settings.features.baby_tracking or not email or not password:
            return None

        try:
            logbook = Logbook()
            started = SyncScheduler(
                syncer=HuckleberrySync(email=email, password=password, logbook=logbook),
                logbook=logbook,
            )
            started.start()
            _scheduler = started
        except Exception:
            return None
        return _scheduler


def stop_scheduler() -> None:
    """Stop mirroring, if running (used by tests and shutdown)."""
    global _scheduler
    with _lock:
        if _scheduler is not None:
            _scheduler.stop()
            _scheduler = None
