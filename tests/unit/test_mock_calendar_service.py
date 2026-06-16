"""Unit tests for the today-relative mock calendar."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from launchpad.services.core.mock_calendar_service import MockCalendarService

LONDON = ZoneInfo("Europe/London")


def test_mock_calendar_anchors_events_to_clock_date() -> None:
    service = MockCalendarService(lambda: datetime(2026, 6, 16, 10, 5, tzinfo=LONDON))

    agenda = service.fetch()

    assert service.name == "mock:calendar"
    assert agenda.retrieved_at == datetime(2026, 6, 16, 10, 5, tzinfo=LONDON)
    assert len(agenda.events) == 3
    assert {event.start.date() for event in agenda.events} == {
        datetime(2026, 6, 16, tzinfo=LONDON).date()
    }
    assert any(event.all_day for event in agenda.events)
    assert any(not event.all_day and event.end is not None for event in agenda.events)


def test_mock_calendar_evaluates_clock_on_each_fetch() -> None:
    calls = [
        datetime(2026, 6, 16, 10, 0, tzinfo=LONDON),
        datetime(2026, 6, 17, 10, 0, tzinfo=LONDON),
    ]

    service = MockCalendarService(lambda: calls.pop(0))

    first = service.fetch()
    second = service.fetch()

    assert first.events[0].start.date() != second.events[0].start.date()
