"""Fantasy basketball models (experimental feature)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class FantasyMatchup:
    """One head-to-head fantasy matchup for the user's team."""

    my_team: str
    opponent_team: str
    my_score: float
    opponent_score: float
    week: int | None = None


@dataclass(frozen=True, slots=True)
class FantasySnapshot:
    """Current fantasy standing for the user's team."""

    league_name: str
    matchup: FantasyMatchup | None = None
    rank: int | None = None
    retrieved_at: datetime | None = None
