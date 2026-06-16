"""Unit tests for the Dashboard composition root (no network)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from launchpad.app import CoreServices, Dashboard
from launchpad.config.settings import Settings
from launchpad.display.mock_display import MockDisplay
from launchpad.models.calendar import Agenda, CalendarEvent
from launchpad.models.dashboard import DashboardMode, DashboardState, Section
from launchpad.models.geometry import Size
from launchpad.models.result import Availability
from launchpad.models.train import StationArrivals, TrainBoard, TrainDeparture
from launchpad.models.weather import CurrentWeather, WeatherCondition, WeatherReport
from launchpad.rendering.portrait import PortraitRenderer
from launchpad.services.base import ServiceError
from launchpad.services.core.calendar_service import CalendarService
from launchpad.services.core.train_service import TrainsProvider
from launchpad.services.core.weather_service import WeatherService

LONDON = ZoneInfo("Europe/London")
MORNING = datetime(2026, 6, 15, 8, 15, tzinfo=LONDON)


# --------------------------------------------------------------------------- #
# Fakes (in-test, no network)
# --------------------------------------------------------------------------- #


class FakeTrainsProvider(TrainsProvider):
    """Returns a fixed multi-station tuple: one PRESENT, one UNAVAILABLE."""

    @property
    def name(self) -> str:
        return "fake:trains"

    def fetch_all(self) -> tuple[StationArrivals, ...]:
        board = TrainBoard(
            station="Custom House",
            departures=(
                TrainDeparture(
                    destination="Paddington",
                    scheduled=datetime(2026, 6, 15, 8, 22, tzinfo=LONDON),
                ),
            ),
            retrieved_at=MORNING,
        )
        return (
            StationArrivals("Custom House", Availability.PRESENT, board),
            StationArrivals("Canning Town", Availability.UNAVAILABLE, None),
        )


class FakeWeatherService(WeatherService):
    """Returns a fixed WeatherReport."""

    @property
    def name(self) -> str:
        return "fake:weather"

    def fetch(self) -> WeatherReport:
        return WeatherReport(
            location="London",
            current=CurrentWeather(temperature_c=12.0, condition=WeatherCondition.CLOUDY),
            retrieved_at=MORNING,
        )


class FailingWeatherService(WeatherService):
    """Always fails with ServiceError."""

    @property
    def name(self) -> str:
        return "fake:weather-failing"

    def fetch(self) -> WeatherReport:
        raise ServiceError("boom")


class FakeCalendarService(CalendarService):
    """Returns an Agenda with one event."""

    @property
    def name(self) -> str:
        return "fake:calendar"

    def fetch(self) -> Agenda:
        return Agenda(
            events=(
                CalendarEvent(
                    title="Standup",
                    start=datetime(2026, 6, 15, 9, 30, tzinfo=LONDON),
                ),
            ),
            retrieved_at=MORNING,
        )


class EmptyCalendarService(CalendarService):
    """Returns an empty Agenda (no events)."""

    @property
    def name(self) -> str:
        return "fake:calendar-empty"

    def fetch(self) -> Agenda:
        return Agenda(events=(), retrieved_at=MORNING)


def _make_dashboard(
    weather: WeatherService | None = None,
    calendar: CalendarService | None = None,
    display: MockDisplay | None = None,
    clock_value: datetime = MORNING,
) -> Dashboard:
    core = CoreServices(
        trains=FakeTrainsProvider(),
        weather=weather or FakeWeatherService(),
        calendar=calendar or FakeCalendarService(),
    )
    return Dashboard(
        settings=Settings(),
        core=core,
        renderer=PortraitRenderer(),
        display=display or MockDisplay(Size(480, 800)),
        clock=lambda: clock_value,
    )


# --------------------------------------------------------------------------- #
# collect()
# --------------------------------------------------------------------------- #


def test_collect_returns_dashboard_state_with_injected_mode() -> None:
    state = _make_dashboard().collect()

    assert isinstance(state, DashboardState)
    assert state.mode is DashboardMode.MORNING
    assert state.generated_at == MORNING


def test_collect_present_core_sections() -> None:
    state = _make_dashboard().collect()

    for section in (Section.TRAINS, Section.CALENDAR, Section.WEATHER):
        assert state.is_visible(section)

    assert state.get(Section.TRAINS).availability is Availability.PRESENT  # type: ignore[union-attr]
    assert state.get(Section.WEATHER).availability is Availability.PRESENT  # type: ignore[union-attr]
    assert state.get(Section.CALENDAR).availability is Availability.PRESENT  # type: ignore[union-attr]


def test_collect_wraps_trains_as_present_even_with_unavailable_station() -> None:
    state = _make_dashboard().collect()

    trains = state.get(Section.TRAINS)
    assert trains is not None
    # The whole section is PRESENT; per-station status lives in the data.
    assert trains.availability is Availability.PRESENT
    arrivals = trains.data
    assert [a.availability for a in arrivals] == [
        Availability.PRESENT,
        Availability.UNAVAILABLE,
    ]


# --------------------------------------------------------------------------- #
# Degradation
# --------------------------------------------------------------------------- #


def test_collect_weather_unavailable_does_not_raise() -> None:
    state = _make_dashboard(weather=FailingWeatherService()).collect()

    weather = state.get(Section.WEATHER)
    assert weather is not None
    assert weather.availability is Availability.UNAVAILABLE
    assert weather.data is None


# --------------------------------------------------------------------------- #
# Calendar empty
# --------------------------------------------------------------------------- #


def test_collect_calendar_empty_is_marked_empty() -> None:
    state = _make_dashboard(calendar=EmptyCalendarService()).collect()

    calendar = state.get(Section.CALENDAR)
    assert calendar is not None
    assert calendar.availability is Availability.EMPTY


# --------------------------------------------------------------------------- #
# refresh_once()
# --------------------------------------------------------------------------- #


def test_refresh_once_writes_png(tmp_path: Path) -> None:
    output = tmp_path / "dashboard.png"
    display = MockDisplay(Size(480, 800), output)
    dashboard = _make_dashboard(display=display)

    dashboard.refresh_once()

    assert output.exists()
    assert output.stat().st_size > 0
