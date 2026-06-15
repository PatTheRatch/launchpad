"""Live TfL Arrivals implementation of :class:`TrainService` (single station).

This integrates one station (Custom House) end-to-end: HTTP via ``httpx``,
optional app-key auth, JSON parsing, and UTC -> Europe/London conversion. The
JSON-to-model mapping is a pure, network-free helper (:func:`parse_arrivals`)
so it can be unit-tested against a fixture.
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from launchpad.config.settings import StationConfig
from launchpad.models.train import DepartureStatus, TrainBoard, TrainDeparture
from launchpad.services.base import ServiceError
from launchpad.services.core.train_service import TrainService

LONDON = ZoneInfo("Europe/London")


def _parse_iso_utc(value: str, tz: ZoneInfo) -> datetime:
    """Parse an ISO-8601 timestamp (``...Z`` allowed) and convert to ``tz``."""
    text = value[:-1] + "+00:00" if value.endswith("Z") else value
    return datetime.fromisoformat(text).astimezone(tz)


def _time_to_station(prediction: dict[str, Any]) -> float:
    value = prediction.get("timeToStation")
    return float(value) if isinstance(value, (int, float)) else math.inf


def _to_departure(prediction: dict[str, Any], tz: ZoneInfo) -> TrainDeparture:
    destination = prediction.get("destinationName") or prediction.get("towards") or "?"
    return TrainDeparture(
        destination=destination,
        # TfL gives live predictions only, so the predicted arrival is stored as
        # `scheduled` and there is no separate `expected` value.
        scheduled=_parse_iso_utc(prediction["expectedArrival"], tz),
        expected=None,
        platform=prediction.get("platformName"),
        line=prediction.get("lineName"),
        # TfL arrivals carry no per-train delayed/cancelled flag.
        status=DepartureStatus.ON_TIME,
    )


def parse_arrivals(
    payload: list[dict[str, Any]],
    station: StationConfig,
    tz: ZoneInfo,
    max_departures: int,
    retrieved_at: datetime,
) -> TrainBoard:
    """Map a TfL Arrivals JSON array into a :class:`TrainBoard` (pure)."""
    relevant = [p for p in payload if p.get("lineId", station.line_id) == station.line_id]
    relevant.sort(key=_time_to_station)
    departures = tuple(_to_departure(p, tz) for p in relevant[:max_departures])
    return TrainBoard(
        station=station.display_name,
        departures=departures,
        retrieved_at=retrieved_at,
    )


class TflTrainService(TrainService):
    """Fetches live arrivals for one configured station from the TfL API."""

    def __init__(
        self,
        station: StationConfig,
        app_key: str | None = None,
        timeout_s: float = 8.0,
        max_departures: int = 2,
        tz: ZoneInfo = LONDON,
        base_url: str = "https://api.tfl.gov.uk",
        client: httpx.Client | None = None,
    ) -> None:
        self._station = station
        self._app_key = app_key
        self._timeout_s = timeout_s
        self._max_departures = max_departures
        self._tz = tz
        self._base_url = base_url.rstrip("/")
        self._client = client

    @property
    def name(self) -> str:
        return f"tfl:{self._station.display_name}"

    def fetch(self) -> TrainBoard:
        url = f"{self._base_url}/StopPoint/{self._station.stop_point_id}/Arrivals"
        params = {"app_key": self._app_key} if self._app_key else {}

        client = self._client if self._client is not None else httpx.Client(timeout=self._timeout_s)
        owns_client = self._client is None
        try:
            response = client.get(url, params=params, timeout=self._timeout_s)
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPError as exc:
            raise ServiceError(f"TfL request failed for {self._station.display_name}.") from exc
        except ValueError as exc:  # invalid JSON (JSONDecodeError subclasses ValueError)
            raise ServiceError(f"Invalid TfL response for {self._station.display_name}.") from exc
        finally:
            if owns_client:
                client.close()

        if not isinstance(payload, list):
            raise ServiceError("Unexpected TfL payload (expected a JSON array).")

        try:
            return parse_arrivals(
                payload,
                self._station,
                self._tz,
                self._max_departures,
                datetime.now(self._tz),
            )
        except (KeyError, ValueError, TypeError, AttributeError) as exc:
            raise ServiceError(
                f"Failed to parse TfL arrivals for {self._station.display_name}."
            ) from exc
