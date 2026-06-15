"""Baby tracking models (experimental feature)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class BabyEventType(str, Enum):
    FEED = "feed"
    SLEEP = "sleep"
    DIAPER = "diaper"


@dataclass(frozen=True, slots=True)
class BabyEvent:
    """A single logged baby-care event."""

    type: BabyEventType
    occurred_at: datetime
    note: str | None = None


@dataclass(frozen=True, slots=True)
class BabySnapshot:
    """Most recent events by type, for a quick glance."""

    last_feed: BabyEvent | None = None
    last_sleep: BabyEvent | None = None
    last_diaper: BabyEvent | None = None
    retrieved_at: datetime | None = None
