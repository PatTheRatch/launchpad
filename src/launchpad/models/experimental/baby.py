"""Baby tracking models (experimental feature).

The dashboard shows the baby's most recent milk feed (nursing, pumped
breast milk, or formula) and how long ago it ended. Solids and other event
kinds (sleep, diapers) are out of scope for now.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class FeedType(str, Enum):
    BREAST = "breast"  # direct nursing
    BOTTLE = "bottle"  # pumped breast milk (or other milk) in a bottle
    FORMULA = "formula"  # formula in a bottle


@dataclass(frozen=True, slots=True)
class Feed:
    """A single logged feed.

    ``ended_at`` is the moment the feed finished — "time since last feed" is
    measured from here, not from ``started_at``. For a bottle the two are the
    same instant (parents log the bottle when it is finished); for a breast
    feed ``ended_at`` is the start plus the nursing durations.
    """

    feed_type: FeedType
    started_at: datetime  # timezone-aware
    ended_at: datetime  # timezone-aware
    amount_ml: float | None = None  # bottle/formula only, normalized to ml
    side: str | None = None  # breast only: "left" or "right"
    duration_seconds: float | None = None  # breast only: left + right


@dataclass(frozen=True, slots=True)
class BabySnapshot:
    """The most recent feed, for a quick glance."""

    last_feed: Feed | None = None
    retrieved_at: datetime | None = None
