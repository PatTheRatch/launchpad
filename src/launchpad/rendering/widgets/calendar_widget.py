"""Calendar widget (stub)."""

from __future__ import annotations

from typing import Any

from launchpad.models.calendar import Agenda
from launchpad.models.geometry import Region
from launchpad.rendering.widgets.base import Widget


class CalendarWidget(Widget[Agenda]):
    def draw(self, data: Agenda, surface: Any, region: Region) -> None:
        raise NotImplementedError
