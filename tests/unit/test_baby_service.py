"""Unit tests for the Huckleberry baby service mapping and error handling.

The huckleberry-api library is never imported here: intervals are faked with
plain attribute objects shaped like the library's pydantic rows, and the
service's network layer is replaced by overriding ``_list_recent_intervals``.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from launchpad.models.experimental.baby import FeedType
from launchpad.services.base import ServiceError
from launchpad.services.experimental.huckleberry_baby_service import (
    HuckleberryBabyService,
    latest_feed,
    map_feed_interval,
)

LONDON = ZoneInfo("Europe/London")

FIXED_NOW = datetime(2026, 8, 17, 12, 0, tzinfo=LONDON)

#: 2026-08-17 09:00:00 Europe/London as a unix timestamp.
START_TS = datetime(2026, 8, 17, 9, 0, tzinfo=LONDON).timestamp()


def breast_interval(
    start: float = START_TS,
    last_side: str = "right",
    left: float = 0.0,
    right: float = 360.0,
) -> SimpleNamespace:
    return SimpleNamespace(
        mode="breast",
        start=start,
        lastSide=last_side,
        leftDuration=left,
        rightDuration=right,
    )


def bottle_interval(
    start: float = START_TS,
    bottle_type: str = "Formula",
    amount: float = 80.0,
    units: str = "ml",
) -> SimpleNamespace:
    return SimpleNamespace(
        mode="bottle",
        start=start,
        bottleType=bottle_type,
        amount=amount,
        units=units,
    )


# --------------------------------------------------------------------------- #
# Interval -> Feed mapping
# --------------------------------------------------------------------------- #


def test_breast_interval_maps_type_side_and_duration() -> None:
    feed = map_feed_interval(breast_interval(left=120.0, right=360.0))

    assert feed is not None
    assert feed.feed_type is FeedType.BREAST
    assert feed.side == "right"
    assert feed.duration_seconds == 480.0
    assert feed.amount_ml is None


def test_breast_feed_ends_at_start_plus_both_durations() -> None:
    feed = map_feed_interval(breast_interval(left=120.0, right=360.0))

    assert feed is not None
    assert feed.started_at == datetime.fromtimestamp(START_TS, tz=LONDON)
    assert feed.ended_at == feed.started_at + timedelta(seconds=480)


def test_breast_side_none_marker_becomes_no_side() -> None:
    # The API can report lastSide="none" around side transitions.
    feed = map_feed_interval(breast_interval(last_side="none"))

    assert feed is not None
    assert feed.side is None


def test_formula_bottle_maps_to_formula_with_amount() -> None:
    feed = map_feed_interval(bottle_interval(bottle_type="Formula", amount=80.0))

    assert feed is not None
    assert feed.feed_type is FeedType.FORMULA
    assert feed.amount_ml == 80.0
    assert feed.side is None
    assert feed.duration_seconds is None


def test_breast_milk_bottle_maps_to_bottle() -> None:
    feed = map_feed_interval(bottle_interval(bottle_type="Breast Milk"))

    assert feed is not None
    assert feed.feed_type is FeedType.BOTTLE


def test_unknown_bottle_type_maps_to_bottle() -> None:
    feed = map_feed_interval(bottle_interval(bottle_type="Cow Milk"))

    assert feed is not None
    assert feed.feed_type is FeedType.BOTTLE


def test_bottle_feed_ends_when_it_starts() -> None:
    # Parents log the bottle at finish, so start is the end of the feed.
    feed = map_feed_interval(bottle_interval())

    assert feed is not None
    assert feed.ended_at == feed.started_at


def test_ounces_normalize_to_millilitres() -> None:
    feed = map_feed_interval(bottle_interval(amount=4.0, units="oz"))

    assert feed is not None
    assert feed.amount_ml == pytest.approx(118.294)


def test_solids_interval_is_ignored() -> None:
    assert map_feed_interval(SimpleNamespace(mode="solids", start=START_TS)) is None


def test_unrecognized_shape_is_ignored() -> None:
    assert map_feed_interval(SimpleNamespace(mode="breast", start="not-a-number")) is None
    assert map_feed_interval(object()) is None


def test_feed_timestamps_are_timezone_aware() -> None:
    feed = map_feed_interval(breast_interval())

    assert feed is not None
    assert feed.started_at.tzinfo is not None
    assert feed.ended_at.tzinfo is not None


# --------------------------------------------------------------------------- #
# Latest-feed selection
# --------------------------------------------------------------------------- #


def test_latest_feed_picks_most_recently_ended_not_started() -> None:
    # The breast feed starts before the bottle but its nursing durations run
    # past it, so it ended later and wins.
    bottle = bottle_interval(start=START_TS + 100)
    breast = breast_interval(start=START_TS, left=0.0, right=600.0)

    feed = latest_feed([bottle, breast])

    assert feed is not None
    assert feed.feed_type is FeedType.BREAST


def test_latest_feed_skips_unmappable_intervals() -> None:
    feed = latest_feed([SimpleNamespace(mode="solids", start=START_TS + 999), bottle_interval()])

    assert feed is not None
    assert feed.feed_type is FeedType.FORMULA


def test_latest_feed_of_nothing_is_none() -> None:
    assert latest_feed([]) is None
    assert latest_feed([SimpleNamespace(mode="solids", start=START_TS)]) is None


# --------------------------------------------------------------------------- #
# Service behaviour (fetch/error isolation), via a faked network layer
# --------------------------------------------------------------------------- #


class FakeHuckleberryBabyService(HuckleberryBabyService):
    """Overrides the network layer with canned intervals or a canned error."""

    def __init__(self, intervals: list[Any] | None = None, error: Exception | None = None) -> None:
        super().__init__("parent@example.com", "hunter2", clock=lambda: FIXED_NOW)
        self._intervals = intervals or []
        self._error = error

    async def _list_recent_intervals(self) -> list[Any]:
        if self._error is not None:
            raise self._error
        return self._intervals


def test_fetch_returns_snapshot_with_latest_feed() -> None:
    service = FakeHuckleberryBabyService(intervals=[bottle_interval(), breast_interval()])

    snapshot = service.fetch()

    assert snapshot.last_feed is not None
    assert snapshot.retrieved_at == FIXED_NOW


def test_fetch_with_no_mappable_feeds_raises_service_error() -> None:
    # huckleberry-api 0.2.2 swallows Firestore errors into an empty/partial
    # list; a newborn's lookback window always has milk feeds, so an empty
    # window is treated as a backend failure ("Feeds unavailable"), never as
    # a valid "No feeds logged yet".
    with pytest.raises(ServiceError):
        FakeHuckleberryBabyService(intervals=[]).fetch()

    solids_only = [SimpleNamespace(mode="solids", start=START_TS)]
    with pytest.raises(ServiceError):
        FakeHuckleberryBabyService(intervals=solids_only).fetch()


def test_fetch_wraps_mapping_errors_in_service_error() -> None:
    # A schema-valid but pathological row must degrade to unavailable, not
    # escape fetch() and crash the dashboard loop (start + 1e30 seconds
    # overflows timedelta during mapping).
    corrupt = breast_interval(left=1e30, right=0.0)

    with pytest.raises(ServiceError):
        FakeHuckleberryBabyService(intervals=[corrupt]).fetch()


def test_fetch_wraps_unexpected_errors_in_service_error() -> None:
    service = FakeHuckleberryBabyService(error=ConnectionError("firebase down"))

    with pytest.raises(ServiceError):
        service.fetch()


def test_fetch_passes_service_errors_through() -> None:
    service = FakeHuckleberryBabyService(error=ServiceError("no child profile"))

    with pytest.raises(ServiceError, match="no child profile"):
        service.fetch()


def test_fetch_without_credentials_raises_service_error() -> None:
    service = HuckleberryBabyService(email="", password="")

    with pytest.raises(ServiceError, match="credentials"):
        service.fetch()


def test_name() -> None:
    assert HuckleberryBabyService("e", "p").name == "huckleberry:baby"
