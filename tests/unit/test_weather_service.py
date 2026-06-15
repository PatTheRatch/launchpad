"""Unit tests for the Open-Meteo weather service (no network)."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import httpx
import pytest

from launchpad.config.settings import LONDON_WEATHER
from launchpad.models.weather import WeatherCondition, WeatherReport
from launchpad.services.base import ServiceError
from launchpad.services.core.open_meteo_weather_service import (
    OpenMeteoWeatherService,
    parse_forecast,
    weather_condition_from_wmo,
)

LONDON = ZoneInfo("Europe/London")
RETRIEVED_AT = datetime(2026, 6, 15, 8, 40, tzinfo=LONDON)
FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "open_meteo_london.json"


def load_fixture() -> dict[str, Any]:
    return json.loads(FIXTURE.read_text())


# --------------------------------------------------------------------------- #
# parse_forecast (pure)
# --------------------------------------------------------------------------- #


def test_parse_maps_current_conditions() -> None:
    payload = load_fixture()
    report = parse_forecast(payload, LONDON_WEATHER, RETRIEVED_AT)

    current = payload["current"]
    assert report.current.temperature_c == float(current["temperature_2m"])
    assert report.current.feels_like_c == float(current["apparent_temperature"])
    assert report.current.humidity_pct == float(current["relative_humidity_2m"])
    assert report.current.wind_kph == float(current["wind_speed_10m"])
    assert report.location == "London"
    assert report.retrieved_at == RETRIEVED_AT


def test_parse_creates_single_daily_forecast() -> None:
    payload = load_fixture()
    report = parse_forecast(payload, LONDON_WEATHER, RETRIEVED_AT)

    daily = payload["daily"]
    assert len(report.forecast) == 1
    forecast = report.forecast[0]
    assert forecast.high_c == float(daily["temperature_2m_max"][0])
    assert forecast.low_c == float(daily["temperature_2m_min"][0])
    assert forecast.precipitation_pct == float(daily["precipitation_probability_max"][0])


def test_parse_forecast_date_is_tz_aware_midnight() -> None:
    payload = load_fixture()
    report = parse_forecast(payload, LONDON_WEATHER, RETRIEVED_AT)

    forecast_date = report.forecast[0].date
    assert isinstance(forecast_date, datetime)
    assert forecast_date.tzinfo is not None
    assert forecast_date == datetime(2026, 6, 15, tzinfo=LONDON)


def test_parse_missing_daily_returns_empty_forecast() -> None:
    payload = load_fixture()
    del payload["daily"]
    report = parse_forecast(payload, LONDON_WEATHER, RETRIEVED_AT)

    assert report.forecast == ()
    assert report.current.temperature_c == 13.8  # current preserved


def test_parse_empty_daily_arrays_returns_empty_forecast() -> None:
    payload = load_fixture()
    payload["daily"] = {
        "time": [],
        "weather_code": [],
        "temperature_2m_max": [],
        "temperature_2m_min": [],
        "precipitation_probability_max": [],
    }
    report = parse_forecast(payload, LONDON_WEATHER, RETRIEVED_AT)

    assert report.forecast == ()
    assert report.current.temperature_c == 13.8


# --------------------------------------------------------------------------- #
# weather_condition_from_wmo (pure)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        (0, WeatherCondition.CLEAR),
        (3, WeatherCondition.CLOUDY),
        (48, WeatherCondition.FOG),
        (61, WeatherCondition.RAIN),
        (71, WeatherCondition.SNOW),
        (95, WeatherCondition.STORM),
        (7, WeatherCondition.UNKNOWN),
    ],
)
def test_wmo_mapping(code: int, expected: WeatherCondition) -> None:
    assert weather_condition_from_wmo(code) == expected


# --------------------------------------------------------------------------- #
# fetch (transport-mocked, no real network)
# --------------------------------------------------------------------------- #


def _service_with_response(handler: httpx.MockTransport) -> OpenMeteoWeatherService:
    client = httpx.Client(transport=handler)
    return OpenMeteoWeatherService(LONDON_WEATHER, client=client)


def test_fetch_raises_service_error_on_500() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(500))
    service = _service_with_response(transport)

    with pytest.raises(ServiceError):
        service.fetch()


def test_fetch_success_returns_report() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=load_fixture()))
    service = _service_with_response(transport)

    report = service.fetch()

    assert isinstance(report, WeatherReport)
    assert report.location == "London"
    assert report.current.temperature_c == 13.8
    assert len(report.forecast) == 1


def test_name_includes_location() -> None:
    service = OpenMeteoWeatherService(LONDON_WEATHER)
    assert service.name == "open-meteo:London"
