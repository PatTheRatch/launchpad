"""Unit tests for concrete composition helpers."""

from __future__ import annotations

from dataclasses import replace

import pytest

from launchpad.app import Dashboard
from launchpad.config.settings import DisplaySettings, Settings
from launchpad.display.eink_display import EinkDisplay
from launchpad.display.mock_display import MockDisplay
from launchpad.factory import build_dashboard, build_display, build_renderer
from launchpad.models.geometry import Orientation
from launchpad.rendering.landscape import LandscapeRenderer
from launchpad.rendering.portrait import PortraitRenderer
from launchpad.services.core.mock_calendar_service import MockCalendarService
from launchpad.services.core.open_meteo_weather_service import OpenMeteoWeatherService
from launchpad.services.core.tfl_train_service import MultiStationTrainService


def test_build_renderer_selects_portrait() -> None:
    settings = Settings(display=DisplaySettings(orientation=Orientation.PORTRAIT))

    assert isinstance(build_renderer(settings), PortraitRenderer)


def test_build_renderer_selects_landscape() -> None:
    settings = Settings(display=DisplaySettings(orientation=Orientation.LANDSCAPE))

    assert isinstance(build_renderer(settings), LandscapeRenderer)


def test_build_renderer_rejects_unknown_orientation() -> None:
    settings = Settings(display=replace(DisplaySettings(), orientation="upside-down"))  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="Unknown display orientation"):
        build_renderer(settings)


def test_build_display_selects_mock_with_configured_size() -> None:
    settings = Settings(display=DisplaySettings(width=123, height=456, driver="mock"))

    display = build_display(settings)

    assert isinstance(display, MockDisplay)
    assert display.size.width == 123
    assert display.size.height == 456


def test_build_display_selects_eink() -> None:
    settings = Settings(display=DisplaySettings(driver="eink"))

    assert isinstance(build_display(settings), EinkDisplay)


def test_build_display_rejects_unknown_driver() -> None:
    settings = Settings(display=DisplaySettings(driver="printer"))

    with pytest.raises(ValueError, match="Unknown display driver"):
        build_display(settings)


def test_build_dashboard_composes_real_collaborators() -> None:
    dashboard = build_dashboard(Settings())

    assert isinstance(dashboard, Dashboard)
    assert isinstance(dashboard._core.trains, MultiStationTrainService)
    assert isinstance(dashboard._core.weather, OpenMeteoWeatherService)
    assert isinstance(dashboard._core.calendar, MockCalendarService)
    assert dashboard._experimental.nba is None
    assert dashboard._experimental.fantasy is None
    assert dashboard._experimental.baby is None
