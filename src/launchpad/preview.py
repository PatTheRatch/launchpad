"""Local preview: build a mock dashboard and render it to a PNG.

The mock :class:`DashboardState` is built here in one place and reused by both
the entry point and the renderer test, so the previewed frame and the tested
frame are always identical. No network calls or real data sources are involved.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

from launchpad.builder import DashboardInputs, DashboardStateBuilder
from launchpad.config.features import FeatureFlags
from launchpad.config.settings import DEFAULT_STATIONS, StationConfig
from launchpad.display.mock_display import MockDisplay
from launchpad.models.calendar import Agenda, CalendarEvent
from launchpad.models.dashboard import DashboardState
from launchpad.models.geometry import Size
from launchpad.models.result import Availability, Result
from launchpad.models.train import (
    DepartureStatus,
    StationArrivals,
    TrainBoard,
    TrainDeparture,
)
from launchpad.models.weather import (
    CurrentWeather,
    DailyForecast,
    WeatherCondition,
    WeatherReport,
)
from launchpad.rendering.frame import Frame
from launchpad.rendering.portrait import PortraitRenderer
from launchpad.services.core.tfl_train_service import MultiStationTrainService

LONDON = ZoneInfo("Europe/London")

#: The real portrait panel specification (Waveshare 7.5" e-ink).
PORTRAIT_SIZE = Size(width=480, height=800)

#: Fixed "now" so previews land in MORNING and stay deterministic.
PREVIEW_NOW = datetime(2026, 6, 15, 8, 15, tzinfo=LONDON)

DEFAULT_OUTPUT = "dashboard.png"


def _at(hour: int, minute: int) -> datetime:
    return datetime(2026, 6, 15, hour, minute, tzinfo=LONDON)


def build_mock_train_board() -> TrainBoard:
    """Deterministic departures from Custom House for stable previews/tests."""
    return TrainBoard(
        station="Custom House",
        departures=(
            TrainDeparture(destination="Paddington", scheduled=_at(8, 22)),
            TrainDeparture(destination="Heathrow", scheduled=_at(8, 27)),
            TrainDeparture(
                destination="Reading",
                scheduled=_at(8, 30),
                expected=_at(8, 35),
                status=DepartureStatus.DELAYED,
            ),
        ),
        retrieved_at=PREVIEW_NOW,
    )


def build_mock_station_arrivals() -> tuple[StationArrivals, ...]:
    """Deterministic multi-station board exercising every availability path."""
    return (
        StationArrivals("Custom House", Availability.PRESENT, build_mock_train_board()),
        StationArrivals(
            "Royal Victoria", Availability.EMPTY, TrainBoard(station="Royal Victoria")
        ),
        StationArrivals("Canning Town", Availability.UNAVAILABLE, None),
    )


def build_mock_agenda() -> Agenda:
    """Deterministic agenda for 2026-06-15 (one all-day + two timed events)."""
    return Agenda(
        events=(
            CalendarEvent(title="Sophie's birthday", start=_at(0, 0), all_day=True),
            CalendarEvent(title="Team standup", start=_at(9, 30), end=_at(9, 45)),
            CalendarEvent(
                title="Dentist appointment",
                start=_at(14, 0),
                end=_at(14, 30),
                location="Stratford",
            ),
        ),
        retrieved_at=PREVIEW_NOW,
    )


def build_mock_weather() -> WeatherReport:
    """Deterministic London weather with current conditions and a forecast."""
    return WeatherReport(
        location="London",
        current=CurrentWeather(
            temperature_c=12.4,
            condition=WeatherCondition.CLOUDY,
            feels_like_c=10.1,
            humidity_pct=72.0,
            wind_kph=14.0,
        ),
        forecast=(
            DailyForecast(
                date=_at(0, 0),
                high_c=15.0,
                low_c=8.0,
                condition=WeatherCondition.CLOUDY,
                precipitation_pct=20.0,
            ),
        ),
        retrieved_at=PREVIEW_NOW,
    )


def build_mock_state() -> DashboardState:
    """Build a MORNING dashboard state via the real builder."""
    inputs = DashboardInputs(
        train=Result.present(build_mock_station_arrivals()),
        calendar=Result.present(build_mock_agenda()),
        weather=Result.present(build_mock_weather()),
    )
    return DashboardStateBuilder().build(PREVIEW_NOW, inputs, FeatureFlags())


def render_preview() -> Frame:
    """Render the mock state at the true portrait size."""
    return PortraitRenderer().render(build_mock_state(), PORTRAIT_SIZE)


def fetch_live_trains(
    stations: tuple[StationConfig, ...],
    app_key: str | None,
) -> tuple[Result[tuple[StationArrivals, ...]], str]:
    """Fetch live arrivals for all stations, degrading each independently.

    Returns a ``Result`` plus a human-readable per-station status summary. The
    section is only fully ``unavailable`` if *every* station failed.
    """
    arrivals = MultiStationTrainService(stations, app_key=app_key).fetch_all()
    summary = ", ".join(f"{a.station}={a.availability.value}" for a in arrivals)
    if all(a.availability is Availability.UNAVAILABLE for a in arrivals):
        return Result.unavailable(), f"all stations unavailable ({summary})"
    return Result.present(arrivals), summary


def main() -> int:
    # Load .env at the entry point (not inside the service). The key is optional.
    load_dotenv()
    app_key = os.getenv("TFL_APP_KEY") or None

    train_result, train_status = fetch_live_trains(DEFAULT_STATIONS, app_key)

    # Trains are live; weather and calendar stay mocked for this step.
    inputs = DashboardInputs(
        train=train_result,
        calendar=Result.present(build_mock_agenda()),
        weather=Result.present(build_mock_weather()),
    )
    state = DashboardStateBuilder().build(PREVIEW_NOW, inputs, FeatureFlags())
    frame = PortraitRenderer().render(state, PORTRAIT_SIZE)

    MockDisplay(PORTRAIT_SIZE, DEFAULT_OUTPUT).show(frame)
    print(f"Rendered {train_status}.")
    print(f"Wrote {Path(DEFAULT_OUTPUT).resolve()}")
    return 0
