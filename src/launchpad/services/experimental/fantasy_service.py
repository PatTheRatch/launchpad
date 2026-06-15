"""Fantasy basketball service interface and stub (experimental feature)."""

from __future__ import annotations

from abc import abstractmethod

from launchpad.models.experimental.fantasy import FantasySnapshot
from launchpad.services.base import DataService


class FantasyService(DataService[FantasySnapshot]):
    """Retrieves the user's current fantasy matchup and standing."""

    @abstractmethod
    def fetch(self) -> FantasySnapshot:
        raise NotImplementedError
