"""Unit tests for the TfL train service (no network)."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import httpx
import pytest

from launchpad.config.settings import CUSTOM_HOUSE
from launchpad.services.base import ServiceError
from launchpad.services.core.tfl_train_service import TflTrainService, parse_arrivals

LONDON = ZoneInfo("Europe/London")
RETRIEVED_AT = datetime(2026, 6, 15, 8, 40, tzinfo=LONDON)
FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "tfl_custom_house_arrivals.json"


def load_fixture() -> list[dict[str, Any]]:
    return json.loads(FIXTURE.read_text())


# --------------------------------------------------------------------------- #
# parse_arrivals (pure)
# --------------------------------------------------------------------------- #


def test_parse_orders_by_time_and_limits_to_max() -> None:
    board = parse_arrivals(load_fixture(), CUSTOM_HOUSE, LONDON, max_departures=2, retrieved_at=RETRIEVED_AT)

    assert len(board.departures) == 2
    assert board.departures[0].destination == "Paddington"  # timeToStation 120
    assert board.departures[1].destination == "Abbey Wood"  # timeToStation 540


def test_parse_converts_utc_to_london() -> None:
    board = parse_arrivals(load_fixture(), CUSTOM_HOUSE, LONDON, max_departures=2, retrieved_at=RETRIEVED_AT)

    paddington = board.departures[0]
    assert paddington.scheduled == datetime(2026, 6, 15, 8, 25, tzinfo=LONDON)
    assert paddington.scheduled.hour == 8
    assert paddington.scheduled.minute == 25
    assert paddington.scheduled.tzinfo is not None
    assert paddington.expected is None


def test_parse_maps_other_fields() -> None:
    board = parse_arrivals(load_fixture(), CUSTOM_HOUSE, LONDON, max_departures=2, retrieved_at=RETRIEVED_AT)

    paddington = board.departures[0]
    assert paddington.platform == "Platform 1"
    assert paddington.line == "Elizabeth line"
    assert board.station == "Custom House"
    assert board.retrieved_at == RETRIEVED_AT


def test_parse_destination_fallbacks() -> None:
    payload = [
        {"towards": "Stratford", "lineId": "elizabeth", "timeToStation": 60,
         "expectedArrival": "2026-06-15T07:10:00Z"},
        {"lineId": "elizabeth", "timeToStation": 90, "expectedArrival": "2026-06-15T07:11:00Z"},
    ]
    board = parse_arrivals(payload, CUSTOM_HOUSE, LONDON, max_departures=5, retrieved_at=RETRIEVED_AT)

    assert board.departures[0].destination == "Stratford"  # falls back to `towards`
    assert board.departures[1].destination == "?"  # no name/towards


def test_parse_filters_out_other_lines() -> None:
    payload = [
        {"destinationName": "Stratford", "lineId": "jubilee", "timeToStation": 30,
         "expectedArrival": "2026-06-15T07:05:00Z"},
        {"destinationName": "Paddington", "lineId": "elizabeth", "timeToStation": 60,
         "expectedArrival": "2026-06-15T07:10:00Z"},
    ]
    board = parse_arrivals(payload, CUSTOM_HOUSE, LONDON, max_departures=5, retrieved_at=RETRIEVED_AT)

    assert [d.destination for d in board.departures] == ["Paddington"]


def test_parse_empty_list_returns_empty_board() -> None:
    board = parse_arrivals([], CUSTOM_HOUSE, LONDON, max_departures=2, retrieved_at=RETRIEVED_AT)

    assert board.station == "Custom House"
    assert board.departures == ()


# --------------------------------------------------------------------------- #
# fetch (transport-mocked, no real network)
# --------------------------------------------------------------------------- #


def _service_with_response(handler: httpx.MockTransport) -> TflTrainService:
    client = httpx.Client(transport=handler)
    return TflTrainService(station=CUSTOM_HOUSE, client=client)


def test_fetch_raises_service_error_on_500() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(500))
    service = _service_with_response(transport)

    with pytest.raises(ServiceError):
        service.fetch()


def test_fetch_success_parses_board() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=load_fixture()))
    service = _service_with_response(transport)

    board = service.fetch()

    assert board.station == "Custom House"
    assert len(board.departures) == 2
    assert board.departures[0].destination == "Paddington"
    assert board.departures[0].scheduled == datetime(2026, 6, 15, 8, 25, tzinfo=LONDON)


def test_fetch_empty_array_returns_empty_board() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=[]))
    service = _service_with_response(transport)

    board = service.fetch()

    assert board.station == "Custom House"
    assert board.departures == ()


def test_name_includes_station() -> None:
    service = TflTrainService(station=CUSTOM_HOUSE)
    assert service.name == "tfl:Custom House"
