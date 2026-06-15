"""Train departure service interface and stub (core feature)."""

from __future__ import annotations

from abc import abstractmethod

from launchpad.models.train import TrainBoard
from launchpad.services.base import DataService


class TrainService(DataService[TrainBoard]):
    """Retrieves upcoming departures for the configured station."""

    @abstractmethod
    def fetch(self) -> TrainBoard:
        raise NotImplementedError
