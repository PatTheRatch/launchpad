"""Tests for the alternative portrait layouts and the shared summaries.

Every layout must render a valid frame for every mode and every availability
combination — a layout that crashes on missing data would take the panel down.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from PIL import Image

from launchpad.builder import DashboardInputs, DashboardStateBuilder
from launchpad.config.features import FeatureFlags
from launchpad.config.settings import DisplaySettings, Settings
from launchpad.factory import PORTRAIT_LAYOUTS, build_renderer
from launchpad.models.dashboard import DashboardMode, Section
from launchpad.models.experimental.baby import BabySnapshot, Feed, FeedType
from launchpad.models.geometry import Layout, Size
from launchpad.models.result import Result
from launchpad.preview import (
    build_mock_agenda,
    build_mock_station_arrivals,
    build_mock_weather,
)
from launchpad.rendering.summaries import (
    Stat,
    one_line,
    stat_for,
    timeline_entries,
    title_for,
)

LONDON = ZoneInfo("Europe/London")
NOW = datetime(2026, 6, 15, 8, 15, tzinfo=LONDON)
SIZE = Size(480, 800)

ALL_FLAGS = FeatureFlags(baby_tracking=True)


def a_feed_snapshot(minutes_ago: int = 80) -> BabySnapshot:
    ended = NOW - timedelta(minutes=minutes_ago)
    return BabySnapshot(
        last_feed=Feed(
            feed_type=FeedType.FORMULA,
            started_at=ended,
            ended_at=ended,
            amount_ml=80.0,
        ),
        retrieved_at=NOW,
    )


def full_inputs() -> DashboardInputs:
    return DashboardInputs(
        train=Result.present(build_mock_station_arrivals()),
        calendar=Result.present(build_mock_agenda()),
        weather=Result.present(build_mock_weather()),
        baby=Result.present(a_feed_snapshot()),
    )


def render(layout: Layout, mode: DashboardMode, inputs: DashboardInputs) -> Image.Image:
    state = DashboardStateBuilder().build(NOW, inputs, ALL_FLAGS, mode)
    settings = Settings(display=DisplaySettings(layout=layout))
    frame = build_renderer(settings).render(state, SIZE)
    assert isinstance(frame.buffer, Image.Image)
    return frame.buffer


# --------------------------------------------------------------------------- #
# Every layout renders in every mode and every failure state
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("layout", list(Layout))
@pytest.mark.parametrize("mode", list(DashboardMode))
def test_layout_renders_valid_frame_with_full_data(
    layout: Layout, mode: DashboardMode
) -> None:
    buffer = render(layout, mode, full_inputs())

    assert buffer.mode == "1"
    assert buffer.size == (480, 800)


@pytest.mark.parametrize("layout", list(Layout))
@pytest.mark.parametrize("mode", list(DashboardMode))
def test_layout_renders_when_every_service_is_unavailable(
    layout: Layout, mode: DashboardMode
) -> None:
    # The all-failed case is the one that must never crash the appliance.
    buffer = render(layout, mode, DashboardInputs())

    assert buffer.size == (480, 800)


@pytest.mark.parametrize("layout", list(Layout))
def test_layout_renders_with_no_feeds_logged(layout: Layout) -> None:
    inputs = DashboardInputs(baby=Result.present(BabySnapshot(retrieved_at=NOW)))

    assert render(layout, DashboardMode.OVERNIGHT, inputs).size == (480, 800)


def test_every_layout_value_has_a_renderer() -> None:
    assert set(PORTRAIT_LAYOUTS) == set(Layout)


def test_build_renderer_selects_each_layout() -> None:
    for layout, renderer_type in PORTRAIT_LAYOUTS.items():
        settings = Settings(display=DisplaySettings(layout=layout))
        assert isinstance(build_renderer(settings), renderer_type)


def test_classic_layout_is_the_default() -> None:
    assert Settings().display.layout is Layout.CLASSIC


# --------------------------------------------------------------------------- #
# Shared summaries
# --------------------------------------------------------------------------- #


def a_state(inputs: DashboardInputs, mode: DashboardMode = DashboardMode.MORNING):
    return DashboardStateBuilder().build(NOW, inputs, ALL_FLAGS, mode)


def test_stat_for_baby_reports_elapsed_since_feed() -> None:
    state = a_state(DashboardInputs(baby=Result.present(a_feed_snapshot(80))))
    section = state.get(Section.BABY)
    assert section is not None

    stat = stat_for(section, NOW)

    assert stat.value == "1h 20m"
    assert "Formula" in stat.caption


def test_stat_for_unavailable_section_is_a_placeholder() -> None:
    state = a_state(DashboardInputs())
    section = state.get(Section.WEATHER)
    assert section is not None

    stat = stat_for(section, NOW)

    assert stat == Stat(label="WEATHER", value="—", caption="Weather unavailable")


def test_one_line_summarises_trains_by_next_departure() -> None:
    state = a_state(DashboardInputs(train=Result.present(build_mock_station_arrivals())))
    section = state.get(Section.TRAINS)
    assert section is not None

    assert one_line(section, NOW) == "08:22 Paddington"


def test_one_line_counts_remaining_calendar_events() -> None:
    state = a_state(DashboardInputs(calendar=Result.present(build_mock_agenda())))
    section = state.get(Section.CALENDAR)
    assert section is not None

    assert one_line(section, NOW).endswith("+2 more")


def test_title_for_weather_uses_the_location() -> None:
    state = a_state(DashboardInputs(weather=Result.present(build_mock_weather())))
    section = state.get(Section.WEATHER)
    assert section is not None

    assert title_for(section) == "London"


def test_timeline_entries_are_sorted_and_marked() -> None:
    entries = timeline_entries(a_state(full_inputs()), NOW)

    assert [entry.when for entry in entries] == sorted(entry.when for entry in entries)
    assert {entry.marker for entry in entries} == {"feed", "train", "event"}


def test_timeline_skips_all_day_events() -> None:
    # An all-day event has no position on a time axis.
    entries = timeline_entries(a_state(full_inputs()), NOW)

    assert all("birthday" not in entry.label for entry in entries)
