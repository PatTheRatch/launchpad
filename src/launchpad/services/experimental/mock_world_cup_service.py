"""Deterministic mock World Cup watchlist (no external integration).

A temporary tournament feature: returns a fixed watchlist for USA, France, and
Senegal. The real API-Football integration is intentionally deferred.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from zoneinfo import ZoneInfo

from launchpad.models.experimental.world_cup import (
    WorldCupTeamWatch,
    WorldCupWatchlist,
)
from launchpad.services.experimental.world_cup_service import WorldCupService

LONDON = ZoneInfo("Europe/London")


class MockWorldCupService(WorldCupService):
    """Provides realistic World Cup data without any network calls."""

    def __init__(self, clock: Callable[[], datetime] | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(LONDON))

    @property
    def name(self) -> str:
        return "mock:world-cup"

    def fetch(self) -> WorldCupWatchlist:
        return WorldCupWatchlist(
            teams=(
                WorldCupTeamWatch(
                    team_name="USA",
                    team_code="USA",
                    last_result="beat Paraguay 4-1",
                    next_match="vs Australia, Fri 20 Jun",
                    group_summary="Group D: 3 pts",
                ),
                WorldCupTeamWatch(
                    team_name="France",
                    team_code="FRA",
                    last_result="beat Senegal 3-1",
                    next_match="vs Iraq, Mon 22 Jun",
                    group_summary="Group I: 3 pts",
                ),
                WorldCupTeamWatch(
                    team_name="Senegal",
                    team_code="SEN",
                    last_result="lost to France 1-3",
                    next_match="vs Norway, Mon 22 Jun",
                    group_summary="Group I: 0 pts",
                ),
            ),
            retrieved_at=self._clock(),
        )
