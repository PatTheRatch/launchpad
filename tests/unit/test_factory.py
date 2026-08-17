"""Unit tests for concrete composition helpers."""

from __future__ import annotations

from dataclasses import replace

import pytest

from launchpad.app import Dashboard
from launchpad.config.settings import DisplaySettings, Settings
from launchpad.display.eink_display import EinkDisplay
from launchpad.display.mock_display import MockDisplay
from launchpad.config.features import FeatureFlags
from launchpad.factory import (
    build_baby_service,
    build_dashboard,
    build_display,
    build_renderer,
)
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
    # The vendor driver only exists on the Raspberry Pi; elsewhere the
    # constructor correctly refuses, so the selection isn't testable.
    pytest.importorskip("waveshare_epd")
    settings = Settings(display=DisplaySettings(driver="eink"))

    assert isinstance(build_display(settings), EinkDisplay)


def test_build_display_rejects_unknown_driver() -> None:
    settings = Settings(display=DisplaySettings(driver="printer"))

    with pytest.raises(ValueError, match="Unknown display driver"):
        build_display(settings)


def test_build_baby_service_requires_flag_and_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from launchpad.services.experimental.huckleberry_baby_service import HuckleberryBabyService

    monkeypatch.setenv("HUCKLEBERRY_EMAIL", "parent@example.com")
    monkeypatch.setenv("HUCKLEBERRY_PASSWORD", "hunter2")

    enabled = Settings(features=FeatureFlags(baby_tracking=True))
    assert isinstance(build_baby_service(enabled), HuckleberryBabyService)
    assert build_baby_service(Settings()) is None


def test_build_baby_service_without_credentials_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # No service is built, so the enabled section stays unavailable and the
    # panel shows its placeholder instead of the dashboard crashing.
    monkeypatch.delenv("HUCKLEBERRY_EMAIL", raising=False)
    monkeypatch.setenv("HUCKLEBERRY_PASSWORD", "hunter2")

    settings = Settings(features=FeatureFlags(baby_tracking=True))
    assert build_baby_service(settings) is None


def test_build_dashboard_composes_real_collaborators() -> None:
    dashboard = build_dashboard(Settings())

    assert isinstance(dashboard, Dashboard)
    assert isinstance(dashboard._core.trains, MultiStationTrainService)
    assert isinstance(dashboard._core.weather, OpenMeteoWeatherService)
    assert isinstance(dashboard._core.calendar, MockCalendarService)
    assert dashboard._experimental.nba is None
    assert dashboard._experimental.fantasy is None
    assert dashboard._experimental.baby is None
