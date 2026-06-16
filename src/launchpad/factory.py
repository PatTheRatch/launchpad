"""Composition helpers: turn settings into concrete collaborators.

Centralizing construction here keeps the selection logic (which renderer for
the configured orientation, which display driver, which experimental services
to enable) in one place and out of the components themselves.
"""

from __future__ import annotations

import os

from launchpad.app import Dashboard
from launchpad.app import CoreServices, ExperimentalServices
from launchpad.config.settings import DEFAULT_STATIONS, LONDON_WEATHER, Settings
from launchpad.display.base import Display
from launchpad.display.eink_display import EinkDisplay
from launchpad.display.mock_display import MockDisplay
from launchpad.models.geometry import Orientation, Size
from launchpad.rendering.base import Renderer
from launchpad.rendering.landscape import LandscapeRenderer
from launchpad.rendering.portrait import PortraitRenderer
from launchpad.services.core.mock_calendar_service import MockCalendarService
from launchpad.services.core.open_meteo_weather_service import OpenMeteoWeatherService
from launchpad.services.core.tfl_train_service import MultiStationTrainService


def build_renderer(settings: Settings) -> Renderer:
    """Select a renderer based on the configured orientation."""
    orientation = settings.display.orientation
    if orientation is Orientation.PORTRAIT:
        return PortraitRenderer()
    if orientation is Orientation.LANDSCAPE:
        return LandscapeRenderer()
    raise ValueError(f"Unknown display orientation: {orientation!r}")


def build_display(settings: Settings) -> Display:
    """Select a display driver (mock vs e-ink)."""
    size = Size(settings.display.width, settings.display.height)
    driver = settings.display.driver
    if driver == "mock":
        return MockDisplay(size, "dashboard.png")
    if driver == "eink":
        return EinkDisplay()
    raise ValueError(f"Unknown display driver: {driver!r}")


def build_dashboard(settings: Settings) -> Dashboard:
    """Wire settings, services, renderer, and display into a Dashboard."""
    app_key = os.getenv("TFL_APP_KEY") or None
    core = CoreServices(
        trains=MultiStationTrainService(DEFAULT_STATIONS, app_key=app_key),
        weather=OpenMeteoWeatherService(LONDON_WEATHER),
        calendar=MockCalendarService(),
    )
    # TODO: Wire experimental services once concrete implementations exist.
    experimental = ExperimentalServices()
    renderer = build_renderer(settings)
    display = build_display(settings)
    return Dashboard(settings, core, renderer, display, experimental)
