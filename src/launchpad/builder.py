"""Build an immutable :class:`DashboardState` from already-retrieved data.

``DashboardStateBuilder`` is a *pure* function over its inputs. It does not
call services, perform I/O, catch service exceptions, or read the wall clock.
Orchestration and error handling live in ``app.py``; this module only combines
results that have already been gathered.

All time logic is interpreted in Europe/London (DST-aware). The caller must
pass a timezone-aware ``now``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time
from types import MappingProxyType
from typing import Any, Mapping
from zoneinfo import ZoneInfo

from launchpad.config.features import FeatureFlags
from launchpad.models.calendar import Agenda
from launchpad.models.dashboard import (
    DashboardMode,
    DashboardState,
    Section,
    SectionCategory,
    SectionState,
)
from launchpad.models.experimental.baby import BabySnapshot
from launchpad.models.experimental.fantasy import FantasySnapshot
from launchpad.models.experimental.nba import NbaSnapshot
from launchpad.models.result import Availability, Result
from launchpad.models.train import TrainBoard
from launchpad.models.weather import WeatherReport

#: All time-of-day logic is anchored to this zone, regardless of the offset of
#: the incoming ``now``.
LONDON = ZoneInfo("Europe/London")

#: Mode boundaries as (inclusive) start times in Europe/London local time.
#: Each window runs up to (but excluding) the next window's start.
_MORNING_START = time(7, 0)
_DAYTIME_START = time(9, 0)
_EVENING_START = time(17, 0)
_OVERNIGHT_START = time(22, 0)

#: Data-driven mode -> ordered sections mapping. Tuning the dashboard's layout
#: per mode happens here and nowhere else; the builder contains no per-mode
#: ``if`` statements. Order is render priority (highest first).
MODE_SECTIONS: Mapping[DashboardMode, tuple[Section, ...]] = MappingProxyType(
    {
        DashboardMode.MORNING: (Section.TRAINS, Section.CALENDAR, Section.WEATHER),
        DashboardMode.DAYTIME: (Section.TRAINS, Section.CALENDAR, Section.WEATHER),
        DashboardMode.EVENING: (
            Section.CALENDAR_TOMORROW,
            Section.NBA,
            Section.FANTASY,
            Section.BABY,
        ),
        DashboardMode.OVERNIGHT: (Section.WEATHER, Section.CALENDAR_TOMORROW),
    }
)

#: Which category each section belongs to (drives degradation behaviour).
SECTION_CATEGORY: Mapping[Section, SectionCategory] = MappingProxyType(
    {
        Section.TRAINS: SectionCategory.CORE,
        Section.WEATHER: SectionCategory.CORE,
        Section.CALENDAR: SectionCategory.CORE,
        Section.CALENDAR_TOMORROW: SectionCategory.CORE,
        Section.NBA: SectionCategory.EXPERIMENTAL,
        Section.FANTASY: SectionCategory.EXPERIMENTAL,
        Section.BABY: SectionCategory.EXPERIMENTAL,
    }
)

#: Experimental sections -> the :class:`FeatureFlags` attribute that gates them.
EXPERIMENTAL_FLAG: Mapping[Section, str] = MappingProxyType(
    {
        Section.NBA: "nba",
        Section.FANTASY: "fantasy_basketball",
        Section.BABY: "baby_tracking",
    }
)


@dataclass(frozen=True, slots=True)
class DashboardInputs:
    """Per-feature results gathered by the orchestrator.

    Every field defaults to ``unavailable`` so a missing or failed feature is
    handled uniformly and a partial set of inputs still builds a valid state.
    Calendar feeds both the "today" and "tomorrow" sections.
    """

    train: Result[TrainBoard] = field(default_factory=Result.unavailable)
    weather: Result[WeatherReport] = field(default_factory=Result.unavailable)
    calendar: Result[Agenda] = field(default_factory=Result.unavailable)
    nba: Result[NbaSnapshot] = field(default_factory=Result.unavailable)
    fantasy: Result[FantasySnapshot] = field(default_factory=Result.unavailable)
    baby: Result[BabySnapshot] = field(default_factory=Result.unavailable)


def resolve_mode(now: datetime) -> DashboardMode:
    """Determine the dashboard mode from ``now`` in Europe/London local time.

    Windows are inclusive of their start and exclusive of their end:

    * Morning   07:00–09:00
    * Daytime   09:00–17:00
    * Evening   17:00–22:00
    * Overnight 22:00–07:00

    Raises:
        ValueError: if ``now`` is not timezone-aware.
    """
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("`now` must be timezone-aware.")

    local_time = now.astimezone(LONDON).time()

    if _MORNING_START <= local_time < _DAYTIME_START:
        return DashboardMode.MORNING
    if _DAYTIME_START <= local_time < _EVENING_START:
        return DashboardMode.DAYTIME
    if _EVENING_START <= local_time < _OVERNIGHT_START:
        return DashboardMode.EVENING
    return DashboardMode.OVERNIGHT


class DashboardStateBuilder:
    """Combines retrieved results into an immutable :class:`DashboardState`."""

    def build(
        self,
        now: datetime,
        inputs: DashboardInputs,
        flags: FeatureFlags,
    ) -> DashboardState:
        """Resolve mode, visibility, availability, and data into one state."""
        mode = resolve_mode(now)

        sections: dict[Section, SectionState] = {}
        for section in MODE_SECTIONS[mode]:
            result = self._result_for(section, inputs)
            if SECTION_CATEGORY[section] is SectionCategory.CORE:
                sections[section] = self._core_state(section, result)
            else:
                experimental = self._experimental_state(section, result, flags)
                if experimental is not None:
                    sections[section] = experimental

        return DashboardState(
            generated_at=now,
            mode=mode,
            sections=MappingProxyType(sections),
        )

    @staticmethod
    def _result_for(section: Section, inputs: DashboardInputs) -> Result[Any]:
        sources: Mapping[Section, Result[Any]] = {
            Section.TRAINS: inputs.train,
            Section.WEATHER: inputs.weather,
            Section.CALENDAR: inputs.calendar,
            Section.CALENDAR_TOMORROW: inputs.calendar,
            Section.NBA: inputs.nba,
            Section.FANTASY: inputs.fantasy,
            Section.BABY: inputs.baby,
        }
        return sources[section]

    @staticmethod
    def _core_state(section: Section, result: Result[Any]) -> SectionState:
        # Core sections are always shown. A missing/failed result is surfaced
        # as an unavailable section (with no data) rather than dropped, so the
        # renderer can show a placeholder and the dashboard never crashes.
        data = None if result.is_unavailable else result.value
        return SectionState(
            section=section,
            category=SectionCategory.CORE,
            visible=True,
            availability=result.availability,
            data=data,
        )

    @staticmethod
    def _experimental_state(
        section: Section,
        result: Result[Any],
        flags: FeatureFlags,
    ) -> SectionState | None:
        # Experimental sections appear only when their flag is enabled, the
        # current mode wants them (guaranteed by the caller iterating
        # MODE_SECTIONS), and their data is actually present. Otherwise they
        # are silently omitted.
        enabled = bool(getattr(flags, EXPERIMENTAL_FLAG[section]))
        if enabled and result.is_present:
            return SectionState(
                section=section,
                category=SectionCategory.EXPERIMENTAL,
                visible=True,
                availability=Availability.PRESENT,
                data=result.value,
            )
        return None
