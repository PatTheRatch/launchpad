"""Weather models (core feature)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class WeatherCondition(str, Enum):
    CLEAR = "clear"
    CLOUDY = "cloudy"
    RAIN = "rain"
    SNOW = "snow"
    FOG = "fog"
    STORM = "storm"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class CurrentWeather:
    """Conditions right now."""

    temperature_c: float
    condition: WeatherCondition = WeatherCondition.UNKNOWN
    feels_like_c: float | None = None
    humidity_pct: float | None = None
    wind_kph: float | None = None


@dataclass(frozen=True, slots=True)
class DailyForecast:
    """A single day's forecast."""

    date: datetime
    high_c: float
    low_c: float
    condition: WeatherCondition = WeatherCondition.UNKNOWN
    precipitation_pct: float | None = None


@dataclass(frozen=True, slots=True)
class WeatherReport:
    """Current conditions plus an optional multi-day forecast."""

    location: str
    current: CurrentWeather
    forecast: tuple[DailyForecast, ...] = ()
    retrieved_at: datetime | None = None
