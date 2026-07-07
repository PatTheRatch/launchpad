"""Rendering tests for the experimental World Cup section."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from PIL import Image

from launchpad.builder import DashboardInputs, DashboardStateBuilder
from launchpad.config.features import FeatureFlags
from launchpad.models.result import Result
from launchpad.preview import PORTRAIT_SIZE, build_mock_world_cup_watchlist
from launchpad.rendering.portrait import PortraitRenderer

LONDON = ZoneInfo("Europe/London")
EVENING = datetime(2026, 6, 15, 18, 0, tzinfo=LONDON)


def test_world_cup_section_renders_valid_frame() -> None:
    inputs = DashboardInputs(
        world_cup=Result.present(build_mock_world_cup_watchlist()),
    )
    state = DashboardStateBuilder().build(EVENING, inputs, FeatureFlags(world_cup=True))

    frame = PortraitRenderer().render(state, PORTRAIT_SIZE)

    assert isinstance(frame.buffer, Image.Image)
    assert frame.buffer.mode == "1"
    assert frame.buffer.size == (480, 800)
