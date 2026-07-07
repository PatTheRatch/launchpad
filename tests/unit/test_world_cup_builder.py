"""Builder tests for the experimental World Cup section (EVENING mode)."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from launchpad.builder import DashboardInputs, DashboardStateBuilder
from launchpad.config.features import FeatureFlags
from launchpad.models.dashboard import DashboardMode, Section
from launchpad.models.result import Result
from launchpad.preview import build_mock_world_cup_watchlist

LONDON = ZoneInfo("Europe/London")
EVENING = datetime(2026, 6, 15, 18, 0, tzinfo=LONDON)


def _build(flags: FeatureFlags, world_cup: Result) -> bool:  # type: ignore[type-arg]
    inputs = DashboardInputs(world_cup=world_cup)
    state = DashboardStateBuilder().build(EVENING, inputs, flags)
    assert state.mode is DashboardMode.EVENING
    return state.is_visible(Section.WORLD_CUP)


def test_absent_when_flag_disabled() -> None:
    visible = _build(
        FeatureFlags(world_cup=False),
        Result.present(build_mock_world_cup_watchlist()),
    )
    assert visible is False


def test_present_when_flag_enabled_and_data_present() -> None:
    visible = _build(
        FeatureFlags(world_cup=True),
        Result.present(build_mock_world_cup_watchlist()),
    )
    assert visible is True


def test_absent_when_flag_enabled_but_data_unavailable() -> None:
    visible = _build(FeatureFlags(world_cup=True), Result.unavailable())
    assert visible is False
