"""Weather service interface and stub (core feature)."""

from __future__ import annotations

from abc import abstractmethod

from launchpad.models.weather import WeatherReport
from launchpad.services.base import DataService


class WeatherService(DataService[WeatherReport]):
    """Retrieves current conditions and forecast for the configured location."""

    @abstractmethod
    def fetch(self) -> WeatherReport:
        raise NotImplementedError
