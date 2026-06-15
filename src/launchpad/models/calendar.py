"""Calendar models (core feature)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class CalendarEvent:
    """A single calendar event."""

    title: str
    start: datetime
    end: datetime | None = None
    all_day: bool = False
    location: str | None = None
    calendar_name: str | None = None


@dataclass(frozen=True, slots=True)
class Agenda:
    """The set of events relevant to the dashboard's current view."""

    events: tuple[CalendarEvent, ...] = ()
    retrieved_at: datetime | None = None
