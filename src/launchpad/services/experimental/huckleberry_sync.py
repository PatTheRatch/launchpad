"""Pull the child's history from Huckleberry into Launchpad's own store.

The write path (:mod:`huckleberry_logger`) mirrors what *we* log, which is
only part of the picture: entries made in the app by anyone else, and all the
history from before Launchpad existed, live only upstream. This module closes
that gap, so the local mirror is a genuine copy rather than a partial diary.

Reads only. Nothing here writes to Huckleberry.

Feeds are normalized through the same mapping the dashboard uses, so a feed
means exactly the same thing in the mirror, on the panel, and in an export.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from launchpad.logbook import Interval, Logbook, SyncCounts
from launchpad.rendering.summaries import feed_detail
from launchpad.services.experimental.huckleberry_baby_service import map_feed_interval

LONDON = ZoneInfo("Europe/London")

#: Kinds mirrored, and the API method that lists each.
KINDS = ("feed", "diaper", "sleep")

_LIST_METHODS = {
    "feed": "list_feed_intervals",
    "diaper": "list_diaper_intervals",
    "sleep": "list_sleep_intervals",
}

_DAY = 86400.0


class SyncError(Exception):
    """A sync could not be completed; the message is user-facing."""


@dataclass(frozen=True, slots=True)
class SyncReport:
    """What one sync run did, per kind."""

    window_days: float
    per_kind: dict[str, SyncCounts] = field(default_factory=dict)
    failed: dict[str, str] = field(default_factory=dict)

    @property
    def changed(self) -> int:
        return sum(counts.changed for counts in self.per_kind.values())

    def as_dict(self) -> dict[str, Any]:
        return {
            "window_days": self.window_days,
            "changed": self.changed,
            "per_kind": {kind: counts.as_dict() for kind, counts in self.per_kind.items()},
            "failed": self.failed,
        }


def _number(value: object) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def _raw(interval: object) -> dict[str, Any]:
    """The upstream row as plain JSON, preserved for future migration."""
    dump = getattr(interval, "model_dump", None)
    if callable(dump):
        try:
            return dict(dump(mode="json"))
        except Exception:
            pass
    return {}


def normalize(kind: str, interval: object) -> Interval | None:
    """Turn one upstream row into a mirror row, or ``None`` if unusable."""
    start = _number(getattr(interval, "start", None))
    if start is None:
        return None
    last_updated = _number(getattr(interval, "lastUpdated", None))
    notes = getattr(interval, "notes", None)
    payload = _raw(interval)

    if kind == "feed":
        feed = map_feed_interval(interval)
        if feed is None:
            return None  # solids and unknown modes are not mirrored as feeds
        return Interval(
            kind="feed",
            start=start,
            ended=feed.ended_at.timestamp(),
            last_updated=last_updated,
            summary=feed_detail(feed),
            amount_ml=feed.amount_ml,
            duration_seconds=feed.duration_seconds,
            notes=notes if isinstance(notes, str) else None,
            payload=payload,
        )

    if kind == "diaper":
        mode = getattr(interval, "mode", None)
        return Interval(
            kind="diaper",
            start=start,
            ended=start,  # diapers are instant events
            last_updated=last_updated,
            summary=f"Diaper · {mode}" if mode else "Diaper",
            notes=notes if isinstance(notes, str) else None,
            payload=payload,
        )

    if kind == "sleep":
        duration = _number(getattr(interval, "duration", None))
        summary = f"Sleep · {round(duration / 60)}m" if duration else "Sleep"
        return Interval(
            kind="sleep",
            start=start,
            ended=start + duration if duration else None,
            last_updated=last_updated,
            summary=summary,
            duration_seconds=duration,
            notes=notes if isinstance(notes, str) else None,
            payload=payload,
        )

    return None


class HuckleberrySync:
    """Mirrors upstream history into the local logbook."""

    def __init__(
        self,
        email: str,
        password: str,
        logbook: Logbook | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._email = email
        self._password = password
        self._logbook = logbook or Logbook()
        self._clock = clock or time.time

    def sync(self, days: float = 2.0) -> SyncReport:
        """Mirror the last ``days`` of history. Returns what changed.

        Each kind is reconciled independently: one failing collection does not
        discard the others, and its error is reported rather than swallowed.
        """
        if days <= 0:
            raise ValueError("days must be positive.")
        if not self._email or not self._password:
            raise SyncError("Huckleberry credentials are not configured.")

        end = self._clock()
        start = end - days * _DAY
        try:
            fetched = asyncio.run(self._fetch(start, end))
        except SyncError:
            raise
        except Exception as exc:
            raise SyncError(f"Huckleberry sync failed: {exc}") from exc

        report = SyncReport(window_days=days)
        for kind in KINDS:
            result = fetched.get(kind)
            if isinstance(result, Exception):
                report.failed[kind] = f"{type(result).__name__}: {result}"
                continue
            rows = [
                row
                for row in (normalize(kind, item) for item in result or ())
                if row is not None
            ]
            report.per_kind[kind] = self._logbook.sync_window(kind, start, end, rows)
        return report

    async def _fetch(self, start: float, end: float) -> dict[str, Any]:
        import aiohttp
        from huckleberry_api import HuckleberryAPI

        async with aiohttp.ClientSession() as session:
            api = HuckleberryAPI(self._email, self._password, LONDON.key, session)
            await api.authenticate()
            user = await api.get_user()
            if user is None or not user.childList:
                raise SyncError("Huckleberry account has no child profile.")
            child_uid = user.childList[0].cid

            fetched: dict[str, Any] = {}
            for kind in KINDS:
                method = getattr(api, _LIST_METHODS[kind], None)
                if method is None:
                    fetched[kind] = RuntimeError(f"library has no {_LIST_METHODS[kind]}")
                    continue
                try:
                    fetched[kind] = list(await method(child_uid, int(start), int(end)))
                except Exception as exc:
                    # One collection failing must not lose the others.
                    fetched[kind] = exc
            return fetched


def export_rows(history: Iterable[dict[str, Any]]) -> list[list[str]]:
    """Flatten mirrored history into CSV rows (header first)."""
    rows = [
        [
            "kind",
            "started_at",
            "ended_at",
            "summary",
            "amount_ml",
            "duration_minutes",
            "notes",
        ]
    ]
    for entry in history:
        duration = entry.get("duration_seconds")
        rows.append(
            [
                str(entry.get("kind") or ""),
                str(entry.get("started_at") or ""),
                str(entry.get("ended_at") or ""),
                str(entry.get("summary") or ""),
                "" if entry.get("amount_ml") is None else f"{entry['amount_ml']:g}",
                "" if duration is None else f"{duration / 60:.0f}",
                str(entry.get("notes") or ""),
            ]
        )
    return rows


def utc_day_bounds(days: float, now: float | None = None) -> tuple[datetime, datetime]:
    """The sync window as timezone-aware datetimes (for display)."""
    end = now if now is not None else time.time()
    return (
        datetime.fromtimestamp(end - days * _DAY, tz=LONDON),
        datetime.fromtimestamp(end, tz=LONDON),
    )
