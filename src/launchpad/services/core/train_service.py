"""Train departure service interfaces (core feature).

``TrainService`` is the single-station component (one :class:`TrainBoard`).
``TrainsProvider`` is the dashboard-facing abstraction: it yields one
:class:`StationArrivals` per station, each degrading independently, so the
renderer can show per-station status instead of one collapsed section.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from launchpad.models.train import StationArrivals, TrainBoard
from launchpad.services.base import DataService


class TrainService(DataService[TrainBoard]):
    """Retrieves upcoming departures for the configured station."""

    @abstractmethod
    def fetch(self) -> TrainBoard:
        raise NotImplementedError


class TrainsProvider(ABC):
    """Produces arrivals for the set of stations shown on the board."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable identifier, used for logging and diagnostics."""
        raise NotImplementedError

    @abstractmethod
    def fetch_all(self) -> tuple[StationArrivals, ...]:
        """Fetch arrivals for every station, degrading each independently."""
        raise NotImplementedError
