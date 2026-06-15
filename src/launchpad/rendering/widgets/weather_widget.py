"""Weather widget (stub)."""

from __future__ import annotations

from typing import Any

from launchpad.models.geometry import Region
from launchpad.models.weather import WeatherReport
from launchpad.rendering.widgets.base import Widget


class WeatherWidget(Widget[WeatherReport]):
    def draw(self, data: WeatherReport, surface: Any, region: Region) -> None:
        raise NotImplementedError
