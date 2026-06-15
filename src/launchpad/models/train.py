"""Train departure models (core feature)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from launchpad.models.result import Availability


class DepartureStatus(str, Enum):
    ON_TIME = "on_time"
    DELAYED = "delayed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class TrainDeparture:
    """A single upcoming departure from a station."""

    destination: str
    scheduled: datetime
    expected: datetime | None = None
    platform: str | None = None
    line: str | None = None
    status: DepartureStatus = DepartureStatus.ON_TIME


@dataclass(frozen=True, slots=True)
class TrainBoard:
    """A snapshot of departures for one origin station."""

    station: str
    departures: tuple[TrainDeparture, ...] = ()
    retrieved_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class StationArrivals:
    """One station's arrivals plus its own availability.

    Used to assemble a multi-station board where each station degrades
    independently: a single station failing is surfaced as ``UNAVAILABLE``
    without affecting the others.
    """

    station: str
    availability: Availability
    board: TrainBoard | None = None
