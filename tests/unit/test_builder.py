"""Unit tests for the DashboardStateBuilder and its mode logic."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from launchpad.builder import (
    LONDON,
    MODE_SECTIONS,
    DashboardInputs,
    DashboardStateBuilder,
    resolve_mode,
)
from launchpad.config.features import FeatureFlags
from launchpad.models.calendar import Agenda
from launchpad.models.dashboard import (
    DashboardMode,
    Section,
    SectionCategory,
)
from launchpad.models.experimental.baby import BabySnapshot
from launchpad.models.experimental.fantasy import FantasySnapshot
from launchpad.models.experimental.nba import NbaSnapshot
from launchpad.models.result import Availability, Result
from launchpad.models.train import TrainBoard
from launchpad.models.weather import CurrentWeather, WeatherReport

UTC = ZoneInfo("UTC")
NEW_YORK = ZoneInfo("America/New_York")


# --------------------------------------------------------------------------- #
# Sample domain data
# --------------------------------------------------------------------------- #


def a_train_board() -> TrainBoard:
    return TrainBoard(station="Custom House")


def a_weather_report() -> WeatherReport:
    return WeatherReport(location="London", current=CurrentWeather(temperature_c=12.0))


def an_agenda() -> Agenda:
    return Agenda()


def an_nba_snapshot() -> NbaSnapshot:
    return NbaSnapshot(team="Cleveland Cavaliers")


def a_fantasy_snapshot() -> FantasySnapshot:
    return FantasySnapshot(league_name="The League")


def a_baby_snapshot() -> BabySnapshot:
    return BabySnapshot()


def london(year: int, month: int, day: int, hour: int, minute: int = 0, second: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, second, tzinfo=LONDON)


@pytest.fixture
def builder() -> DashboardStateBuilder:
    return DashboardStateBuilder()


# --------------------------------------------------------------------------- #
# Dashboard modes
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("when", "expected"),
    [
        (london(2026, 6, 15, 8, 0), DashboardMode.MORNING),
        (london(2026, 6, 15, 12, 0), DashboardMode.DAYTIME),
        (london(2026, 6, 15, 19, 0), DashboardMode.EVENING),
        (london(2026, 6, 15, 2, 0), DashboardMode.OVERNIGHT),
        (london(2026, 6, 15, 23, 30), DashboardMode.OVERNIGHT),
    ],
)
def test_resolve_mode_for_each_mode(when: datetime, expected: DashboardMode) -> None:
    assert resolve_mode(when) is expected


@pytest.mark.parametrize(
    ("when", "expected"),
    [
        # Inclusive starts.
        (london(2026, 6, 15, 7, 0, 0), DashboardMode.MORNING),
        (london(2026, 6, 15, 9, 0, 0), DashboardMode.DAYTIME),
        (london(2026, 6, 15, 17, 0, 0), DashboardMode.EVENING),
        (london(2026, 6, 15, 22, 0, 0), DashboardMode.OVERNIGHT),
        # Exclusive ends (one second before the next window).
        (london(2026, 6, 15, 6, 59, 59), DashboardMode.OVERNIGHT),
        (london(2026, 6, 15, 8, 59, 59), DashboardMode.MORNING),
        (london(2026, 6, 15, 16, 59, 59), DashboardMode.DAYTIME),
        (london(2026, 6, 15, 21, 59, 59), DashboardMode.EVENING),
    ],
)
def test_resolve_mode_boundaries_inclusive_start_exclusive_end(
    when: datetime, expected: DashboardMode
) -> None:
    assert resolve_mode(when) is expected


def test_resolve_mode_requires_timezone_aware() -> None:
    naive = datetime(2026, 6, 15, 8, 0)
    with pytest.raises(ValueError):
        resolve_mode(naive)


# --------------------------------------------------------------------------- #
# Timezone / DST behaviour
# --------------------------------------------------------------------------- #


def test_london_local_time_drives_mode_not_utc() -> None:
    # Same UTC wall-clock (06:30) lands in different modes depending on season,
    # proving the London local time — not UTC — selects the mode.
    summer = datetime(2026, 7, 1, 6, 30, tzinfo=UTC)  # London 07:30 BST
    winter = datetime(2026, 1, 1, 6, 30, tzinfo=UTC)  # London 06:30 GMT

    assert resolve_mode(summer) is DashboardMode.MORNING
    assert resolve_mode(winter) is DashboardMode.OVERNIGHT


def test_mode_respects_dst_transition_day() -> None:
    # Spring forward: 2026-03-29 the UK clocks jump 01:00 GMT -> 02:00 BST.
    # The same 06:30 UTC instant is OVERNIGHT the day before (GMT) and
    # MORNING on/after the switch (BST = 07:30).
    before_switch = datetime(2026, 3, 28, 6, 30, tzinfo=UTC)  # London 06:30 GMT
    after_switch = datetime(2026, 3, 29, 6, 30, tzinfo=UTC)  # London 07:30 BST

    assert resolve_mode(before_switch) is DashboardMode.OVERNIGHT
    assert resolve_mode(after_switch) is DashboardMode.MORNING


def test_mode_uses_london_for_arbitrary_input_zone() -> None:
    # 02:00 in New York (EDT, UTC-4) == 07:00 in London (BST) -> Morning.
    new_york = datetime(2026, 7, 1, 2, 0, tzinfo=NEW_YORK)
    assert resolve_mode(new_york) is DashboardMode.MORNING


# --------------------------------------------------------------------------- #
# Mode -> sections table
# --------------------------------------------------------------------------- #


def test_mode_sections_table_matches_vision() -> None:
    assert MODE_SECTIONS[DashboardMode.MORNING] == (
        Section.TRAINS,
        Section.CALENDAR,
        Section.WEATHER,
    )
    assert MODE_SECTIONS[DashboardMode.DAYTIME] == (
        Section.TRAINS,
        Section.CALENDAR,
        Section.WEATHER,
    )
    assert MODE_SECTIONS[DashboardMode.EVENING] == (
        Section.CALENDAR_TOMORROW,
        Section.NBA,
        Section.FANTASY,
        Section.BABY,
    )
    assert MODE_SECTIONS[DashboardMode.OVERNIGHT] == (
        Section.WEATHER,
        Section.CALENDAR_TOMORROW,
    )


def test_build_sets_mode_and_generated_at(builder: DashboardStateBuilder) -> None:
    now = london(2026, 6, 15, 8, 0)
    state = builder.build(now, DashboardInputs(), FeatureFlags())

    assert state.mode is DashboardMode.MORNING
    assert state.generated_at == now


# --------------------------------------------------------------------------- #
# Core degradation
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("result", "expected_availability", "expects_data"),
    [
        (Result.present(a_train_board()), Availability.PRESENT, True),
        (Result.empty(), Availability.EMPTY, False),
        (Result.unavailable(), Availability.UNAVAILABLE, False),
    ],
)
def test_core_train_section_degrades_gracefully(
    builder: DashboardStateBuilder,
    result: Result,
    expected_availability: Availability,
    expects_data: bool,
) -> None:
    now = london(2026, 6, 15, 8, 0)  # Morning includes trains.
    state = builder.build(now, DashboardInputs(train=result), FeatureFlags())

    section = state.get(Section.TRAINS)
    assert section is not None
    assert section.category is SectionCategory.CORE
    assert section.visible is True
    assert section.availability is expected_availability
    assert (section.data is not None) is expects_data


def test_core_sections_always_present_even_when_all_failed(
    builder: DashboardStateBuilder,
) -> None:
    now = london(2026, 6, 15, 8, 0)
    state = builder.build(now, DashboardInputs(), FeatureFlags())

    for section in (Section.TRAINS, Section.CALENDAR, Section.WEATHER):
        resolved = state.get(section)
        assert resolved is not None
        assert resolved.visible is True
        assert resolved.availability is Availability.UNAVAILABLE
        assert resolved.data is None


def test_core_empty_preserves_empty_container(builder: DashboardStateBuilder) -> None:
    now = london(2026, 6, 15, 8, 0)
    empty_agenda = an_agenda()
    state = builder.build(
        now, DashboardInputs(calendar=Result.empty(empty_agenda)), FeatureFlags()
    )

    section = state.get(Section.CALENDAR)
    assert section is not None
    assert section.availability is Availability.EMPTY
    assert section.data is empty_agenda


# --------------------------------------------------------------------------- #
# Experimental gating
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("flag_enabled", [True, False])
@pytest.mark.parametrize(
    "result",
    [
        Result.present(an_nba_snapshot()),
        Result.empty(),
        Result.unavailable(),
    ],
)
def test_experimental_nba_only_when_flag_and_present(
    builder: DashboardStateBuilder,
    flag_enabled: bool,
    result: Result,
) -> None:
    now = london(2026, 6, 15, 19, 0)  # Evening wants NBA.
    flags = FeatureFlags(nba=flag_enabled)
    state = builder.build(now, DashboardInputs(nba=result), flags)

    expected_visible = flag_enabled and result.is_present
    section = state.get(Section.NBA)

    if expected_visible:
        assert section is not None
        assert section.category is SectionCategory.EXPERIMENTAL
        assert section.visible is True
        assert section.availability is Availability.PRESENT
        assert section.data is result.value
    else:
        assert section is None


def test_experimental_omitted_when_mode_does_not_want_it(
    builder: DashboardStateBuilder,
) -> None:
    # Morning does not include NBA, even when enabled and present.
    now = london(2026, 6, 15, 8, 0)
    flags = FeatureFlags(nba=True)
    state = builder.build(
        now, DashboardInputs(nba=Result.present(an_nba_snapshot())), flags
    )

    assert state.get(Section.NBA) is None


def test_experimental_flag_mapping_for_all_features(
    builder: DashboardStateBuilder,
) -> None:
    now = london(2026, 6, 15, 19, 0)  # Evening wants nba, fantasy, baby.
    flags = FeatureFlags(nba=True, fantasy_basketball=True, baby_tracking=True)
    inputs = DashboardInputs(
        nba=Result.present(an_nba_snapshot()),
        fantasy=Result.present(a_fantasy_snapshot()),
        baby=Result.present(a_baby_snapshot()),
    )

    state = builder.build(now, inputs, flags)

    assert state.is_visible(Section.NBA)
    assert state.is_visible(Section.FANTASY)
    assert state.is_visible(Section.BABY)


def test_experimental_each_flag_independently_gates_its_section(
    builder: DashboardStateBuilder,
) -> None:
    now = london(2026, 6, 15, 19, 0)
    # Only fantasy enabled; nba and baby disabled.
    flags = FeatureFlags(nba=False, fantasy_basketball=True, baby_tracking=False)
    inputs = DashboardInputs(
        nba=Result.present(an_nba_snapshot()),
        fantasy=Result.present(a_fantasy_snapshot()),
        baby=Result.present(a_baby_snapshot()),
    )

    state = builder.build(now, inputs, flags)

    assert state.get(Section.NBA) is None
    assert state.is_visible(Section.FANTASY)
    assert state.get(Section.BABY) is None


# --------------------------------------------------------------------------- #
# All-empty scenario
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("when", "expected_mode"),
    [
        (london(2026, 6, 15, 8, 0), DashboardMode.MORNING),
        (london(2026, 6, 15, 12, 0), DashboardMode.DAYTIME),
        (london(2026, 6, 15, 19, 0), DashboardMode.EVENING),
        (london(2026, 6, 15, 2, 0), DashboardMode.OVERNIGHT),
    ],
)
def test_all_empty_inputs_produce_valid_state(
    builder: DashboardStateBuilder,
    when: datetime,
    expected_mode: DashboardMode,
) -> None:
    state = builder.build(when, DashboardInputs(), FeatureFlags())

    assert state.mode is expected_mode

    # No experimental section should appear (flags off, no data).
    for section in (Section.NBA, Section.FANTASY, Section.BABY):
        assert state.get(section) is None

    # Every visible section is core and marked unavailable; nothing crashes.
    for resolved in state.visible_sections:
        assert resolved.category is SectionCategory.CORE
        assert resolved.availability is Availability.UNAVAILABLE

    # The visible sections are exactly the mode's core sections.
    expected_core = tuple(
        section
        for section in MODE_SECTIONS[expected_mode]
        if section not in (Section.NBA, Section.FANTASY, Section.BABY)
    )
    assert tuple(s.section for s in state.visible_sections) == expected_core
