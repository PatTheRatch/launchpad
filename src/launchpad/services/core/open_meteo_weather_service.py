"""Live Open-Meteo implementation of :class:`WeatherService` (single location).

Mirrors the TfL service: HTTP via ``httpx`` (no API key needed), with a pure,
network-free parser (:func:`parse_forecast`) and WMO code mapping
(:func:`weather_condition_from_wmo`) that are unit-tested against a fixture.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from launchpad.config.settings import LocationConfig
from launchpad.models.weather import (
    CurrentWeather,
    DailyForecast,
    WeatherCondition,
    WeatherReport,
)
from launchpad.services.base import ServiceError
from launchpad.services.core.weather_service import WeatherService

#: Discrete WMO weather codes. Rain/snow are handled by range checks below.
_WMO_CONDITIONS: dict[int, WeatherCondition] = {
    0: WeatherCondition.CLEAR,
    1: WeatherCondition.CLOUDY,
    2: WeatherCondition.CLOUDY,
    3: WeatherCondition.CLOUDY,
    45: WeatherCondition.FOG,
    48: WeatherCondition.FOG,
    95: WeatherCondition.STORM,
    96: WeatherCondition.STORM,
    99: WeatherCondition.STORM,
}


def weather_condition_from_wmo(code: int) -> WeatherCondition:
    """Map a WMO weather interpretation code to a :class:`WeatherCondition`."""
    if code in _WMO_CONDITIONS:
        return _WMO_CONDITIONS[code]
    if (51 <= code <= 67) or (80 <= code <= 82):
        return WeatherCondition.RAIN
    if (71 <= code <= 77) or code in (85, 86):
        return WeatherCondition.SNOW
    return WeatherCondition.UNKNOWN


def _opt_float(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) else None


def _first(value: Any) -> Any:
    return value[0] if isinstance(value, list) and value else None


def _condition(value: Any) -> WeatherCondition:
    if isinstance(value, (int, float)):
        return weather_condition_from_wmo(int(value))
    return WeatherCondition.UNKNOWN


def _midnight(date_text: str, timezone: str) -> datetime:
    day = date.fromisoformat(date_text)
    return datetime(day.year, day.month, day.day, tzinfo=ZoneInfo(timezone))


def _parse_daily(daily: Any, location: LocationConfig) -> tuple[DailyForecast, ...]:
    if not isinstance(daily, dict):
        return ()
    date_text = _first(daily.get("time"))
    high = _opt_float(_first(daily.get("temperature_2m_max")))
    low = _opt_float(_first(daily.get("temperature_2m_min")))
    if date_text is None or high is None or low is None:
        return ()
    return (
        DailyForecast(
            date=_midnight(str(date_text), location.timezone),
            high_c=high,
            low_c=low,
            condition=_condition(_first(daily.get("weather_code"))),
            precipitation_pct=_opt_float(_first(daily.get("precipitation_probability_max"))),
        ),
    )


def parse_forecast(
    payload: dict[str, Any],
    location: LocationConfig,
    retrieved_at: datetime,
) -> WeatherReport:
    """Map an Open-Meteo forecast response into a :class:`WeatherReport` (pure)."""
    current = payload.get("current")
    if not isinstance(current, dict):
        current = {}
    current_weather = CurrentWeather(
        temperature_c=float(current["temperature_2m"]),
        condition=_condition(current.get("weather_code")),
        feels_like_c=_opt_float(current.get("apparent_temperature")),
        humidity_pct=_opt_float(current.get("relative_humidity_2m")),
        wind_kph=_opt_float(current.get("wind_speed_10m")),
    )
    return WeatherReport(
        location=location.display_name,
        current=current_weather,
        forecast=_parse_daily(payload.get("daily"), location),
        retrieved_at=retrieved_at,
    )


class OpenMeteoWeatherService(WeatherService):
    """Fetches current conditions and today's forecast from Open-Meteo."""

    def __init__(
        self,
        location: LocationConfig,
        timeout_s: float = 8.0,
        base_url: str = "https://api.open-meteo.com/v1/forecast",
        client: httpx.Client | None = None,
    ) -> None:
        self._location = location
        self._timeout_s = timeout_s
        self._base_url = base_url
        self._client = client

    @property
    def name(self) -> str:
        return f"open-meteo:{self._location.display_name}"

    def fetch(self) -> WeatherReport:
        params = {
            "latitude": str(self._location.latitude),
            "longitude": str(self._location.longitude),
            "current": "temperature_2m,apparent_temperature,relative_humidity_2m,"
            "wind_speed_10m,weather_code",
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,"
            "precipitation_probability_max",
            "timezone": self._location.timezone,
            "forecast_days": "1",
            "wind_speed_unit": "kmh",
        }

        client = self._client if self._client is not None else httpx.Client(timeout=self._timeout_s)
        owns_client = self._client is None
        try:
            response = client.get(self._base_url, params=params, timeout=self._timeout_s)
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPError as exc:
            raise ServiceError(
                f"Open-Meteo request failed for {self._location.display_name}."
            ) from exc
        except ValueError as exc:  # invalid JSON (JSONDecodeError subclasses ValueError)
            raise ServiceError(
                f"Invalid Open-Meteo response for {self._location.display_name}."
            ) from exc
        finally:
            if owns_client:
                client.close()

        if not isinstance(payload, dict):
            raise ServiceError("Unexpected Open-Meteo payload (expected a JSON object).")

        try:
            return parse_forecast(
                payload,
                self._location,
                datetime.now(ZoneInfo(self._location.timezone)),
            )
        except (KeyError, ValueError, TypeError, AttributeError, IndexError) as exc:
            raise ServiceError(
                f"Failed to parse Open-Meteo forecast for {self._location.display_name}."
            ) from exc
