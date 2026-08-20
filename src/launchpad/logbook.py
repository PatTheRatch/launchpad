"""Launchpad's own copy of the child's care history.

Two tables, with different jobs:

``events``
    An append-only audit of writes made *through* Launchpad — what we did,
    and when. Never reconciled or rewritten.

``intervals``
    A mirror of the authoritative history in Huckleberry, kept current by
    :mod:`launchpad.services.experimental.huckleberry_sync`. This is the
    table that makes the data genuinely yours: it captures entries logged in
    the app by anyone, not just the ones we wrote, so it survives the
    unofficial API breaking and is the seed for a fully self-hosted logger.

Feed and diaper intervals carry **no stable id** upstream (only sleep does),
so ``(kind, start)`` is the natural key — one child cannot start two feeds in
the same second. ``last_updated`` decides which version wins, so editing an
entry in the app updates the mirror rather than duplicating it.

Stdlib only (sqlite3); the database lives outside the repository
(``data/logbook.db`` by default, gitignored) so a ``git clean`` can never take
the history with it.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

LONDON = ZoneInfo("Europe/London")

_SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        kind TEXT NOT NULL,
        payload TEXT NOT NULL,
        logged_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS intervals (
        kind TEXT NOT NULL,
        start REAL NOT NULL,
        ended REAL,
        last_updated REAL,
        summary TEXT,
        amount_ml REAL,
        duration_seconds REAL,
        notes TEXT,
        payload TEXT NOT NULL,
        synced_at TEXT NOT NULL,
        PRIMARY KEY (kind, start)
    )
    """,
    "CREATE INDEX IF NOT EXISTS intervals_by_start ON intervals (start DESC)",
)


@dataclass(frozen=True, slots=True)
class Interval:
    """One normalized care event from the upstream history."""

    kind: str  # "feed" | "diaper" | "sleep"
    start: float  # unix seconds; natural key with kind
    ended: float | None = None
    last_updated: float | None = None
    summary: str = ""
    amount_ml: float | None = None
    duration_seconds: float | None = None
    notes: str | None = None
    payload: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class SyncCounts:
    """What one reconciliation changed."""

    added: int = 0
    updated: int = 0
    removed: int = 0

    @property
    def changed(self) -> int:
        return self.added + self.updated + self.removed

    def as_dict(self) -> dict[str, int]:
        return {"added": self.added, "updated": self.updated, "removed": self.removed}


class Logbook:
    """Launchpad's local history store."""

    def __init__(
        self,
        path: str | os.PathLike[str] | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if path is None:
            path = os.getenv("LAUNCHPAD_LOGBOOK_PATH", "data/logbook.db")
        self._path = Path(path)
        self._clock = clock or (lambda: datetime.now(LONDON))
        self._lock = threading.Lock()

    @property
    def path(self) -> Path:
        return self._path

    def _connect(self) -> sqlite3.Connection:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self._path)
        for statement in _SCHEMA:
            connection.execute(statement)
        return connection

    # -- events: our own writes -------------------------------------------- #

    def record(self, kind: str, payload: dict[str, Any]) -> None:
        """Append one event. Called only after the upstream write succeeded."""
        with self._lock, self._connect() as connection:
            connection.execute(
                "INSERT INTO events (kind, payload, logged_at) VALUES (?, ?, ?)",
                (kind, json.dumps(payload), self._clock().isoformat(timespec="seconds")),
            )

    def recent(self, limit: int = 20) -> list[dict[str, Any]]:
        """The most recent events we wrote, newest first."""
        if not self._path.exists():
            return []
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                "SELECT kind, payload, logged_at FROM events ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {"kind": kind, "payload": json.loads(payload), "logged_at": logged_at}
            for kind, payload, logged_at in rows
        ]

    # -- intervals: the mirrored history ----------------------------------- #

    def sync_window(
        self, kind: str, start: float, end: float, intervals: Iterable[Interval]
    ) -> SyncCounts:
        """Reconcile one kind over ``[start, end)`` against upstream.

        Rows newer than what we hold are written; rows that vanished upstream
        are removed, so an entry deleted in the app does not linger here.
        Reconciliation is bounded to the window: history outside it is never
        touched, so a short sync can never wipe the archive.
        """
        synced_at = self._clock().isoformat(timespec="seconds")
        incoming = {interval.start: interval for interval in intervals}
        added = updated = removed = 0

        with self._lock, self._connect() as connection:
            existing = {
                row[0]: row[1]
                for row in connection.execute(
                    "SELECT start, last_updated FROM intervals "
                    "WHERE kind = ? AND start >= ? AND start < ?",
                    (kind, start, end),
                ).fetchall()
            }

            for moment, interval in incoming.items():
                if moment not in existing:
                    added += 1
                elif (interval.last_updated or 0) <= (existing[moment] or 0):
                    continue  # unchanged upstream
                else:
                    updated += 1
                connection.execute(
                    """
                    INSERT INTO intervals
                        (kind, start, ended, last_updated, summary, amount_ml,
                         duration_seconds, notes, payload, synced_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(kind, start) DO UPDATE SET
                        ended = excluded.ended,
                        last_updated = excluded.last_updated,
                        summary = excluded.summary,
                        amount_ml = excluded.amount_ml,
                        duration_seconds = excluded.duration_seconds,
                        notes = excluded.notes,
                        payload = excluded.payload,
                        synced_at = excluded.synced_at
                    """,
                    (
                        interval.kind,
                        interval.start,
                        interval.ended,
                        interval.last_updated,
                        interval.summary,
                        interval.amount_ml,
                        interval.duration_seconds,
                        interval.notes,
                        json.dumps(interval.payload or {}),
                        synced_at,
                    ),
                )

            vanished = [moment for moment in existing if moment not in incoming]
            for moment in vanished:
                connection.execute(
                    "DELETE FROM intervals WHERE kind = ? AND start = ?", (kind, moment)
                )
                removed += 1

        return SyncCounts(added=added, updated=updated, removed=removed)

    def history(
        self, kinds: Sequence[str] | None = None, since: float | None = None, limit: int = 200
    ) -> list[dict[str, Any]]:
        """Mirrored history, newest first."""
        if not self._path.exists():
            return []
        clauses: list[str] = []
        params: list[Any] = []
        if kinds:
            clauses.append(f"kind IN ({','.join('?' * len(kinds))})")
            params.extend(kinds)
        if since is not None:
            clauses.append("start >= ?")
            params.append(since)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)

        with self._lock, self._connect() as connection:
            rows = connection.execute(
                "SELECT kind, start, ended, summary, amount_ml, duration_seconds, notes "
                f"FROM intervals {where} ORDER BY start DESC LIMIT ?",
                params,
            ).fetchall()

        return [
            {
                "kind": kind,
                "started_at": datetime.fromtimestamp(start, tz=LONDON).isoformat(
                    timespec="seconds"
                ),
                "ended_at": (
                    datetime.fromtimestamp(ended, tz=LONDON).isoformat(timespec="seconds")
                    if ended
                    else None
                ),
                "summary": summary,
                "amount_ml": amount_ml,
                "duration_seconds": duration_seconds,
                "notes": notes,
            }
            for kind, start, ended, summary, amount_ml, duration_seconds, notes in rows
        ]

    def counts(self) -> dict[str, int]:
        """How many mirrored rows exist per kind."""
        if not self._path.exists():
            return {}
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                "SELECT kind, COUNT(*) FROM intervals GROUP BY kind"
            ).fetchall()
        return {kind: count for kind, count in rows}

    def span(self) -> tuple[str | None, str | None]:
        """The oldest and newest mirrored moments, as ISO strings."""
        if not self._path.exists():
            return (None, None)
        with self._lock, self._connect() as connection:
            row = connection.execute("SELECT MIN(start), MAX(start) FROM intervals").fetchone()
        if not row or row[0] is None:
            return (None, None)
        return tuple(  # type: ignore[return-value]
            datetime.fromtimestamp(value, tz=LONDON).isoformat(timespec="seconds")
            for value in row
        )
