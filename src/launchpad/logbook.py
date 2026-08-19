"""Local mirror of every event logged through Launchpad.

Every successful write to Huckleberry is also recorded here, in SQLite on the
Pi. That makes Launchpad's copy of the history independent of an unofficial
backend: if the API ever breaks or the account goes away, the data logged
through Launchpad still exists — and a later fully-self-hosted logger can
start from this file with history intact.

Stdlib only (sqlite3); the database lives outside the repository
(``data/logbook.db`` under the working directory, gitignored) so a
``git clean`` can never take the baby's history with it.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

LONDON = ZoneInfo("Europe/London")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    payload TEXT NOT NULL,
    logged_at TEXT NOT NULL
)
"""


class Logbook:
    """Append-only record of events logged through Launchpad."""

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

    def record(self, kind: str, payload: dict[str, Any]) -> None:
        """Append one event. Called only after the upstream write succeeded."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock, sqlite3.connect(self._path) as connection:
            connection.execute(_SCHEMA)
            connection.execute(
                "INSERT INTO events (kind, payload, logged_at) VALUES (?, ?, ?)",
                (kind, json.dumps(payload), self._clock().isoformat(timespec="seconds")),
            )

    def recent(self, limit: int = 20) -> list[dict[str, Any]]:
        """The most recent events, newest first."""
        if not self._path.exists():
            return []
        with self._lock, sqlite3.connect(self._path) as connection:
            rows = connection.execute(
                "SELECT kind, payload, logged_at FROM events ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {"kind": kind, "payload": json.loads(payload), "logged_at": logged_at}
            for kind, payload, logged_at in rows
        ]
