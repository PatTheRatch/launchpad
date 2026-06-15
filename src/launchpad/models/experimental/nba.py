"""NBA / Cavaliers models (experimental feature)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class GameStatus(str, Enum):
    SCHEDULED = "scheduled"
    LIVE = "live"
    FINAL = "final"


@dataclass(frozen=True, slots=True)
class NbaGame:
    """A single NBA game involving the followed team."""

    home_team: str
    away_team: str
    tip_off: datetime
    status: GameStatus = GameStatus.SCHEDULED
    home_score: int | None = None
    away_score: int | None = None


@dataclass(frozen=True, slots=True)
class NbaSnapshot:
    """The most relevant game (recent result or next game)."""

    team: str
    game: NbaGame | None = None
    retrieved_at: datetime | None = None
