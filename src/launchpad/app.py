"""Dashboard orchestration.

``Dashboard`` ties the pieces together: it asks (core and enabled
experimental) services for data, wraps each outcome in a
:class:`~launchpad.models.result.Result`, assembles a
:class:`~launchpad.models.dashboard.DashboardState` via the pure builder,
hands it to a renderer, and shows the resulting frame on a display. It depends
only on abstractions, so every collaborator is swappable.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import TypeVar
from zoneinfo import ZoneInfo

from launchpad.builder import DashboardInputs, DashboardStateBuilder
from launchpad.config.settings import Settings
from launchpad.display.base import Display
from launchpad.models.calendar import Agenda
from launchpad.models.dashboard import DashboardState
from launchpad.models.geometry import Size
from launchpad.models.result import Result
from launchpad.models.train import StationArrivals
from launchpad.rendering.base import Renderer
from launchpad.services.base import DataService, ServiceError
from launchpad.services.core.calendar_service import CalendarService
from launchpad.services.core.train_service import TrainsProvider
from launchpad.services.core.weather_service import WeatherService
from launchpad.services.experimental.baby_service import BabyService
from launchpad.services.experimental.fantasy_service import FantasyService
from launchpad.services.experimental.nba_service import NbaService

T = TypeVar("T")

LONDON = ZoneInfo("Europe/London")


@dataclass(slots=True)
class CoreServices:
    """The always-on services."""

    trains: TrainsProvider
    weather: WeatherService
    calendar: CalendarService


@dataclass(slots=True)
class ExperimentalServices:
    """Optional services, present only when their feature flag is enabled."""

    nba: NbaService | None = None
    fantasy: FantasyService | None = None
    baby: BabyService | None = None


class Dashboard:
    """Coordinates data gathering, rendering, and display."""

    def __init__(
        self,
        settings: Settings,
        core: CoreServices,
        renderer: Renderer,
        display: Display,
        experimental: ExperimentalServices | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._settings = settings
        self._core = core
        self._renderer = renderer
        self._display = display
        self._experimental = experimental or ExperimentalServices()
        # A callable evaluated fresh on every collect(), so run_forever() reads a
        # live timestamp each cycle instead of a value frozen at construction.
        self._clock: Callable[[], datetime] = clock or (lambda: datetime.now(LONDON))

    def collect(self) -> DashboardState:
        """Gather data from all active services into a single state.

        Every service call is wrapped into a :class:`Result`; the builder gates
        experimental sections by flag, mode, and presence, so no feature-flag
        checks are needed here.
        """
        now = self._clock()
        inputs = DashboardInputs(
            train=self._collect_trains(),
            weather=self._fetch_result(self._core.weather),
            calendar=self._collect_calendar(),
            nba=self._optional_result(self._experimental.nba),
            fantasy=self._optional_result(self._experimental.fantasy),
            baby=self._optional_result(self._experimental.baby),
        )
        return DashboardStateBuilder().build(now, inputs, self._settings.features)

    def refresh_once(self) -> None:
        """Collect data, render a frame, and show it once."""
        state = self.collect()
        size = Size(self._settings.display.width, self._settings.display.height)
        frame = self._renderer.render(state, size)
        self._display.show(frame)

    def run_forever(self) -> None:
        """Refresh on the configured interval until interrupted.

        TODO: time-tiered refresh scheduling (per the project vision) is a later
        enhancement; for now a single fixed interval is used.
        """
        try:
            while True:
                self.refresh_once()
                time.sleep(self._settings.refresh.refresh_seconds)
        except KeyboardInterrupt:
            self._display.sleep()
            return

    def _collect_trains(self) -> Result[tuple[StationArrivals, ...]]:
        # Always wrap the per-station tuple in ``present`` (even when every
        # station is UNAVAILABLE) so the renderer can show per-station status.
        # ``unavailable`` is reserved for the defensive case where the provider
        # itself raises rather than degrading per station.
        try:
            arrivals = self._core.trains.fetch_all()
        except ServiceError:
            return Result.unavailable()
        return Result.present(arrivals)

    def _collect_calendar(self) -> Result[Agenda]:
        try:
            agenda = self._core.calendar.fetch()
        except ServiceError:
            return Result.unavailable()
        if agenda.events:
            return Result.present(agenda)
        return Result.empty(agenda)

    def _optional_result(self, service: DataService[T] | None) -> Result[T]:
        # Missing experimental services stay at the default unavailable result.
        if service is None:
            return Result.unavailable()
        return self._fetch_result(service)

    @staticmethod
    def _fetch_result(service: DataService[T]) -> Result[T]:
        try:
            value = service.fetch()
        except ServiceError:
            return Result.unavailable()
        else:
            return Result.present(value)
