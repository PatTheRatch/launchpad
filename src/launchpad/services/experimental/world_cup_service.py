"""World Cup watchlist service interface (experimental feature)."""

from __future__ import annotations

from abc import abstractmethod

from launchpad.models.experimental.world_cup import WorldCupWatchlist
from launchpad.services.base import DataService


class WorldCupService(DataService[WorldCupWatchlist]):
    """Retrieves a compact watchlist for the followed tournament teams."""

    @abstractmethod
    def fetch(self) -> WorldCupWatchlist:
        raise NotImplementedError
