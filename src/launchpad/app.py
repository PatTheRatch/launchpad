"""Dashboard orchestration.

``Dashboard`` ties the pieces together: it asks (core and enabled
experimental) services for data, assembles a
:class:`~launchpad.models.dashboard.DashboardState`, hands it to a renderer,
and shows the resulting frame on a display. It depends only on abstractions,
so every collaborator is swappable.
"""

from __future__ import annotations

from dataclasses import dataclass

from launchpad.config.settings import Settings
from launchpad.display.base import Display
from launchpad.models.dashboard import DashboardState
from launchpad.rendering.base import Renderer
from launchpad.services.core.calendar_service import CalendarService
from launchpad.services.core.train_service import TrainService
from launchpad.services.core.weather_service import WeatherService
from launchpad.services.experimental.baby_service import BabyService
from launchpad.services.experimental.fantasy_service import FantasyService
from launchpad.services.experimental.nba_service import NbaService


@dataclass(slots=True)
class CoreServices:
    """The always-on services."""

    trains: TrainService
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
    ) -> None:
        self._settings = settings
        self._core = core
        self._renderer = renderer
        self._display = display
        self._experimental = experimental or ExperimentalServices()

    def collect(self) -> DashboardState:
        """Gather data from all active services into a single state."""
        raise NotImplementedError

    def refresh_once(self) -> None:
        """Collect data, render a frame, and show it once."""
        raise NotImplementedError

    def run_forever(self) -> None:
        """Refresh on the configured interval until interrupted."""
        raise NotImplementedError
