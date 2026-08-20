"""Fan out "something changed" to connected clients.

The watcher (:mod:`launchpad.services.experimental.huckleberry_watcher`) knows
when Huckleberry changes; the nightstand page and any other client want to
know immediately. This module is the thread-safe broker between them.

Clients receive a monotonically increasing version rather than the change
itself: on any bump they re-fetch ``/api/state.json`` through the normal path,
so there is exactly one way state is produced and no risk of a pushed payload
disagreeing with a polled one.
"""

from __future__ import annotations

import queue
import threading
from typing import Any

#: Bounded per-subscriber queue: a stalled client drops updates rather than
#: growing without limit. Losing a bump is harmless — the next one, or the
#: client's own poll, still brings it up to date.
_QUEUE_SIZE = 8


class ChangeBroker:
    """A version counter plus a set of subscriber queues."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._version = 0
        self._subscribers: set[queue.Queue[int]] = set()

    @property
    def version(self) -> int:
        with self._lock:
            return self._version

    def publish(self, _source: str = "") -> None:
        """Record a change and wake every subscriber."""
        with self._lock:
            self._version += 1
            version = self._version
            subscribers = list(self._subscribers)
        for subscriber in subscribers:
            try:
                subscriber.put_nowait(version)
            except queue.Full:
                pass  # slow client; it will catch up on its next poll

    def subscribe(self) -> queue.Queue[int]:
        subscriber: queue.Queue[int] = queue.Queue(maxsize=_QUEUE_SIZE)
        with self._lock:
            self._subscribers.add(subscriber)
        return subscriber

    def unsubscribe(self, subscriber: queue.Queue[int]) -> None:
        with self._lock:
            self._subscribers.discard(subscriber)

    @property
    def subscriber_count(self) -> int:
        with self._lock:
            return len(self._subscribers)


_broker = ChangeBroker()
_watcher: Any = None
_watcher_lock = threading.Lock()


def broker() -> ChangeBroker:
    """The process-wide change broker."""
    return _broker


def watcher() -> Any:
    """The running watcher, or ``None`` when real-time is not active."""
    return _watcher


def status() -> dict[str, Any]:
    """Real-time status for the status endpoint and the live indicator."""
    active = _watcher is not None
    payload: dict[str, Any] = {
        "enabled": active,
        "version": _broker.version,
        "subscribers": _broker.subscriber_count,
    }
    if active:
        payload.update(_watcher.status.snapshot())
    return payload


def start_watcher() -> Any:
    """Start real-time watching if it is configured; return the watcher or None.

    Requires the ``baby_tracking`` flag, Huckleberry credentials, and
    ``LAUNCHPAD_REALTIME`` not set to a falsey value. Any failure to start is
    swallowed: real-time is an accelerator, and the server must run without it.
    """
    global _watcher
    with _watcher_lock:
        if _watcher is not None:
            return _watcher

        import os

        from launchpad.config.settings import load_settings

        if (os.getenv("LAUNCHPAD_REALTIME", "1").strip().lower()) in {"0", "false", "no", "off"}:
            return None

        settings = load_settings()
        email = (os.getenv("HUCKLEBERRY_EMAIL") or "").strip()
        password = (os.getenv("HUCKLEBERRY_PASSWORD") or "").strip()
        if not settings.features.baby_tracking or not email or not password:
            return None

        try:
            from launchpad.config_server import preview as preview_module
            from launchpad.services.experimental.huckleberry_watcher import FeedWatcher

            def on_change(source: str) -> None:
                # Drop the cached service data first, so the re-fetch that
                # follows the version bump actually sees the new event.
                preview_module.shared_preview().invalidate()
                _broker.publish(source)
                # Mirror the new entry promptly, whoever logged it.
                from launchpad.config_server import sync as sync_module

                scheduler = sync_module.scheduler()
                if scheduler is not None:
                    scheduler.poke()

            started = FeedWatcher(email=email, password=password, on_change=on_change)
            started.start()
            _watcher = started
        except Exception:
            return None
        return _watcher


def stop_watcher() -> None:
    """Stop the watcher, if one is running (used by tests and shutdown)."""
    global _watcher
    with _watcher_lock:
        if _watcher is not None:
            _watcher.stop()
            _watcher = None
