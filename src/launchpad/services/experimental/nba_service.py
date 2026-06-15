"""NBA / Cavaliers service interface and stub (experimental feature)."""

from __future__ import annotations

from abc import abstractmethod

from launchpad.models.experimental.nba import NbaSnapshot
from launchpad.services.base import DataService


class NbaService(DataService[NbaSnapshot]):
    """Retrieves the latest result or next game for the followed team."""

    @abstractmethod
    def fetch(self) -> NbaSnapshot:
        raise NotImplementedError
