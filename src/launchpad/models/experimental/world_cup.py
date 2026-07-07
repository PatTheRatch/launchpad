"""World Cup watchlist models (experimental, temporary tournament feature).

These are display-ready summary models, not raw API models: each field is a
short string the renderer can show as-is.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class WorldCupTeamWatch:
    """A compact, glanceable summary for one followed team."""

    team_name: str
    team_code: str
    last_result: str | None = None
    next_match: str | None = None
    group_summary: str | None = None


@dataclass(frozen=True, slots=True)
class WorldCupWatchlist:
    """The set of followed teams for the current tournament."""

    teams: tuple[WorldCupTeamWatch, ...]
    retrieved_at: datetime
