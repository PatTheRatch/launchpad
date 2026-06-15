"""The aggregate view-model rendered by the dashboard.

``DashboardState`` is the single, immutable hand-off point between data
retrieval and rendering. It already encodes every decision a renderer needs:
the current mode, which sections are visible, each section's availability, and
the section data. The renderer must not recompute any of this — it simply
draws what the state describes.

This module deliberately keeps section ``data`` typed as ``Any`` so the
aggregate need not import individual (and especially experimental) models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping

from launchpad.models.result import Availability


class DashboardMode(str, Enum):
    """How the dashboard adapts across the day (Europe/London local time)."""

    MORNING = "morning"
    DAYTIME = "daytime"
    EVENING = "evening"
    OVERNIGHT = "overnight"


class SectionCategory(str, Enum):
    """Core sections must always work; experimental ones may be omitted."""

    CORE = "core"
    EXPERIMENTAL = "experimental"


class Section(str, Enum):
    """An individually renderable area of the dashboard."""

    TRAINS = "trains"
    WEATHER = "weather"
    CALENDAR = "calendar"  # today's agenda
    CALENDAR_TOMORROW = "calendar_tomorrow"  # tomorrow's agenda
    NBA = "nba"
    FANTASY = "fantasy"
    BABY = "baby"


@dataclass(frozen=True, slots=True)
class SectionState:
    """The fully-resolved state of one section, ready to render."""

    section: Section
    category: SectionCategory
    visible: bool
    availability: Availability
    data: Any = None


def _empty_sections() -> Mapping[Section, SectionState]:
    return MappingProxyType({})


@dataclass(frozen=True, slots=True)
class DashboardState:
    """Everything a renderer needs to draw one frame."""

    generated_at: datetime
    mode: DashboardMode
    sections: Mapping[Section, SectionState] = field(default_factory=_empty_sections)

    def get(self, section: Section) -> SectionState | None:
        """Return the state for ``section`` if it is part of the dashboard."""
        return self.sections.get(section)

    def is_visible(self, section: Section) -> bool:
        """Whether ``section`` is present and visible in this state."""
        state = self.sections.get(section)
        return bool(state and state.visible)

    @property
    def visible_sections(self) -> tuple[SectionState, ...]:
        """All visible sections, in resolution order."""
        return tuple(state for state in self.sections.values() if state.visible)
