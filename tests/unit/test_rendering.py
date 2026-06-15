"""Tests for the portrait renderer."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from PIL import Image

from launchpad.builder import DashboardInputs, DashboardStateBuilder
from launchpad.config.features import FeatureFlags
from launchpad.models.result import Result
from launchpad.models.train import DepartureStatus, TrainBoard, TrainDeparture
from launchpad.preview import (
    PORTRAIT_SIZE,
    build_mock_agenda,
    build_mock_train_board,
    render_preview,
)
from launchpad.rendering.portrait import PortraitRenderer

LONDON = ZoneInfo("Europe/London")


def test_portrait_render_produces_1bit_frame_at_panel_size() -> None:
    frame = render_preview()

    assert isinstance(frame.buffer, Image.Image)
    assert frame.buffer.mode == "1"
    assert frame.buffer.size == (480, 800)
    assert frame.size == PORTRAIT_SIZE


def test_portrait_render_handles_unavailable_weather() -> None:
    now = datetime(2026, 6, 15, 8, 15, tzinfo=LONDON)
    inputs = DashboardInputs(
        train=Result.present(build_mock_train_board()),
        calendar=Result.present(build_mock_agenda()),
        weather=Result.unavailable(),
    )
    state = DashboardStateBuilder().build(now, inputs, FeatureFlags())

    frame = PortraitRenderer().render(state, PORTRAIT_SIZE)

    assert isinstance(frame.buffer, Image.Image)
    assert frame.buffer.mode == "1"
    assert frame.buffer.size == (480, 800)


def test_portrait_render_handles_long_train_destination() -> None:
    now = datetime(2026, 6, 15, 8, 15, tzinfo=LONDON)
    board = TrainBoard(
        station="Custom House",
        departures=(
            TrainDeparture(
                destination="A Very Long Destination Name That Will Not Fit On One Line",
                scheduled=now,
                expected=now,
                status=DepartureStatus.DELAYED,
            ),
        ),
    )
    inputs = DashboardInputs(train=Result.present(board))
    state = DashboardStateBuilder().build(now, inputs, FeatureFlags())

    frame = PortraitRenderer().render(state, PORTRAIT_SIZE)

    assert isinstance(frame.buffer, Image.Image)
    assert frame.buffer.mode == "1"
    assert frame.buffer.size == (480, 800)
