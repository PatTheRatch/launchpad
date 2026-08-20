"""Real-time watch on Huckleberry, so logged events appear without polling.

Firestore can push document changes, which is far better than waiting out a
poll interval when someone logs a feed. But the underlying library is not
built to hold a subscription open indefinitely, so this module is written
around three verified constraints:

* Listener callbacks arrive on the Firestore SDK's own background threads,
  not an asyncio loop — so ``on_change`` must be thread-safe.
* Nothing refreshes the auth token in the background. A listener left idle
  simply stops receiving events when its token expires (~1 hour), silently.
* ``refresh_session_token()`` recreates listeners but never clears the
  cached listener client, so recreated listeners reuse credentials built
  from the *old* token.

Rather than depend on that recovery path, each session is torn down and
rebuilt from scratch well before the token expires. The watcher is therefore
an **accelerator, never a source of truth**: when it is working, changes show
up immediately; when it is not, callers fall back to their normal polling and
nothing breaks. Every failure is caught, recorded, and retried with backoff —
this must never take down the config server.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any
from zoneinfo import ZoneInfo

LONDON = ZoneInfo("Europe/London")

_LOGGER = logging.getLogger(__name__)

#: How long one listener session runs before a full rebuild. Firebase ID
#: tokens last about an hour; rebuilding at 40 minutes stays clear of both
#: expiry and the library's unreliable refresh path.
SESSION_SECONDS = 2400.0

#: Backoff between failed session attempts.
_BACKOFF_START = 5.0
_BACKOFF_MAX = 300.0

#: Ignore repeat notifications this close together — one logical write can
#: produce several document updates.
_THROTTLE_SECONDS = 1.0

#: Collections worth watching, in the order they are subscribed.
WATCHED = ("feed", "diaper", "sleep")


@dataclass
class WatcherStatus:
    """Observable state, for the status endpoint and the live indicator."""

    running: bool = False
    connected: bool = False
    sessions: int = 0
    changes: int = 0
    last_change_at: float | None = None
    last_error: str | None = None
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "running": self.running,
                "connected": self.connected,
                "sessions": self.sessions,
                "changes": self.changes,
                "last_change_at": self.last_change_at,
                "last_error": self.last_error,
            }


class FeedWatcher:
    """Keeps a best-effort real-time subscription to the child's documents."""

    def __init__(
        self,
        email: str,
        password: str,
        on_change: Callable[[str], None],
        session_seconds: float = SESSION_SECONDS,
    ) -> None:
        self._email = email
        self._password = password
        self._on_change = on_change
        self._session_seconds = session_seconds
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_fired = 0.0
        self._fire_lock = threading.Lock()
        self.status = WatcherStatus()

    # -- lifecycle --------------------------------------------------------- #

    def start(self) -> None:
        """Start watching in a daemon thread. Safe to call once."""
        if self._thread is not None:
            return
        self.status.running = True
        self._thread = threading.Thread(
            target=self._run_forever, name="huckleberry-watcher", daemon=True
        )
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        """Signal the watcher to shut down and wait briefly for it."""
        self._stop.set()
        thread = self._thread
        if thread is not None:
            thread.join(timeout=timeout)
        self.status.running = False
        self.status.connected = False

    # -- change plumbing --------------------------------------------------- #

    def _notify(self, source: str) -> None:
        """Called from a Firestore SDK thread when a watched document changes."""
        with self._fire_lock:
            now = time.monotonic()
            if now - self._last_fired < _THROTTLE_SECONDS:
                return
            self._last_fired = now
        self.status.changes += 1
        self.status.last_change_at = time.time()
        try:
            self._on_change(source)
        except Exception:
            # A misbehaving subscriber must not kill the watcher thread.
            _LOGGER.exception("Change subscriber raised")

    def _callback_for(self, source: str) -> Callable[[Any], None]:
        """A per-listener callback that ignores its initial snapshot.

        Firestore delivers the current document immediately on subscribe, so
        without this every session rebuild would look like a fresh change.
        """
        seen_first = threading.Event()

        def callback(_document: Any) -> None:
            if not seen_first.is_set():
                seen_first.set()
                return
            self._notify(source)

        return callback

    # -- the supervised loop ----------------------------------------------- #

    def _run_forever(self) -> None:
        import asyncio

        backoff = _BACKOFF_START
        while not self._stop.is_set():
            try:
                asyncio.run(self._one_session())
                backoff = _BACKOFF_START  # a clean session resets backoff
            except Exception as exc:
                self.status.connected = False
                self.status.last_error = f"{type(exc).__name__}: {exc}"
                _LOGGER.warning("Watcher session failed: %s", exc)
                self._stop.wait(backoff)
                backoff = min(backoff * 2, _BACKOFF_MAX)
        self.status.running = False
        self.status.connected = False

    async def _one_session(self) -> None:
        """Hold listeners for one bounded session, then tear everything down."""
        import asyncio

        import aiohttp
        from huckleberry_api import HuckleberryAPI

        async with aiohttp.ClientSession() as session:
            api = HuckleberryAPI(self._email, self._password, LONDON.key, session)
            await api.authenticate()
            user = await api.get_user()
            if user is None or not user.childList:
                raise RuntimeError("Huckleberry account has no child profile")
            child_uid = user.childList[0].cid

            setters = {
                "feed": api.setup_feed_listener,
                "diaper": api.setup_diaper_listener,
                "sleep": api.setup_sleep_listener,
            }
            for source in WATCHED:
                await setters[source](child_uid, self._callback_for(source))

            self.status.sessions += 1
            self.status.connected = True
            self.status.last_error = None
            _LOGGER.info("Watcher session active (%s)", ", ".join(WATCHED))

            try:
                # Sleep in slices so stop() is responsive without threads
                # blocking on a single long await.
                deadline = time.monotonic() + self._session_seconds
                while not self._stop.is_set() and time.monotonic() < deadline:
                    await asyncio.sleep(1.0)
            finally:
                self.status.connected = False
                try:
                    await api.stop_all_listeners()
                except Exception:
                    # Teardown failures are logged, never propagated: the
                    # session is being discarded anyway.
                    _LOGGER.debug("Listener teardown failed", exc_info=True)
