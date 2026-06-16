"""Today-relative mock calendar service."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, time
from zoneinfo import ZoneInfo

from launchpad.models.calendar import Agenda, CalendarEvent
from launchpad.services.core.calendar_service import CalendarService

LONDON = ZoneInfo("Europe/London")


class MockCalendarService(CalendarService):
    """Provides realistic calendar data without external integration."""

    def __init__(self, clock: Callable[[], datetime] | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(LONDON))

    @property
    def name(self) -> str:
        return "mock:calendar"

    def fetch(self) -> Agenda:
        now = self._clock().astimezone(LONDON)
        today = now.date()

        def at(hour: int, minute: int) -> datetime:
            return datetime.combine(today, time(hour, minute), tzinfo=LONDON)

        return Agenda(
            events=(
                CalendarEvent(
                    title="Family day",
                    start=at(0, 0),
                    all_day=True,
                    calendar_name="Home",
                ),
                CalendarEvent(
                    title="School run",
                    start=at(8, 15),
                    end=at(8, 45),
                    location="Custom House",
                    calendar_name="Home",
                ),
                CalendarEvent(
                    title="Dinner",
                    start=at(18, 30),
                    end=at(19, 30),
                    calendar_name="Home",
                ),
            ),
            retrieved_at=now,
        )
