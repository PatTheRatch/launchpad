"""Live "last feed" data from the Huckleberry baby-tracking app.

Talks to Huckleberry's Firebase backend through the unofficial
``huckleberry-api`` library using the normal account email/password (the
library bundles the Firebase client config, so no extra credentials are
needed). Parents keep logging feeds in the app; this service only reads.

The library is async (aiohttp) while the service contract is synchronous, so
``fetch()`` bridges with ``asyncio.run()`` — a fresh event loop per refresh is
fine at the dashboard's cadence. The dependency is optional (the ``baby``
extra, pinned to ``huckleberry-api==0.2.2``: later versions require Python
3.14) and imported lazily so the rest of the application runs without it.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterable
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from launchpad.models.experimental.baby import BabySnapshot, Feed, FeedType
from launchpad.services.base import ServiceError
from launchpad.services.experimental.baby_service import BabyService

LONDON = ZoneInfo("Europe/London")

#: One fluid ounce in millilitres, for normalising bottle amounts to ml.
_ML_PER_OZ = 29.5735

#: Huckleberry ``bottleType`` value meaning formula; every other bottle type
#: ("Breast Milk", "Cow Milk", ...) is shown as a plain bottle feed.
_FORMULA_BOTTLE_TYPE = "Formula"


def _number(value: object) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def map_feed_interval(interval: object) -> Feed | None:
    """Map one Huckleberry feed interval to a :class:`Feed` (pure).

    Intervals are the rows returned by ``HuckleberryAPI.list_feed_intervals``
    (pydantic models with ``mode``/``start``/... attributes). Fields are read
    defensively via ``getattr`` so an unexpected upstream shape degrades to
    ``None`` instead of raising. ``mode="solids"`` rows — and anything else
    unrecognized — are ignored: the section tracks milk feeds only.
    """
    start = _number(getattr(interval, "start", None))
    if start is None:
        return None
    started_at = datetime.fromtimestamp(start, tz=LONDON)
    mode = getattr(interval, "mode", None)

    if mode == "breast":
        # Durations are seconds per side; the feed ends once both are done.
        left = _number(getattr(interval, "leftDuration", None)) or 0.0
        right = _number(getattr(interval, "rightDuration", None)) or 0.0
        duration = left + right
        side = getattr(interval, "lastSide", None)
        return Feed(
            feed_type=FeedType.BREAST,
            started_at=started_at,
            ended_at=started_at + timedelta(seconds=duration),
            side=side if side in ("left", "right") else None,
            duration_seconds=duration,
        )

    if mode == "bottle":
        bottle_type = getattr(interval, "bottleType", None)
        feed_type = FeedType.FORMULA if bottle_type == _FORMULA_BOTTLE_TYPE else FeedType.BOTTLE
        amount = _number(getattr(interval, "amount", None))
        if amount is not None and getattr(interval, "units", None) == "oz":
            amount *= _ML_PER_OZ
        # Parents log a bottle when it is finished, so start ~= ended.
        return Feed(
            feed_type=feed_type,
            started_at=started_at,
            ended_at=started_at,
            amount_ml=amount,
        )

    return None


def latest_feed(intervals: Iterable[object]) -> Feed | None:
    """The most recently *ended* mappable feed, or ``None`` when there is none."""
    feeds = [feed for feed in map(map_feed_interval, intervals) if feed is not None]
    if not feeds:
        return None
    return max(feeds, key=lambda feed: feed.ended_at)


class HuckleberryBabyService(BabyService):
    """Reads the most recent feed for the first child on the account."""

    def __init__(
        self,
        email: str,
        password: str,
        lookback_days: int = 7,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._email = email
        self._password = password
        self._lookback_days = lookback_days
        self._clock = clock or (lambda: datetime.now(LONDON))

    @property
    def name(self) -> str:
        return "huckleberry:baby"

    def fetch(self) -> BabySnapshot:
        if not self._email or not self._password:
            raise ServiceError("Huckleberry credentials are not configured.")
        try:
            intervals = asyncio.run(self._list_recent_intervals())
            last = latest_feed(intervals)
        except ServiceError:
            raise
        except Exception as exc:
            # Unofficial API: auth, network, and parse failures are all equally
            # expected — every one degrades to an unavailable section. Mapping
            # stays inside this boundary too, so a pathological interval value
            # can never escape as a non-ServiceError and kill the dashboard.
            raise ServiceError("Huckleberry feed retrieval failed.") from exc
        if last is None:
            # The library swallows Firestore/validation errors and returns an
            # empty or partial list (huckleberry-api 0.2.2). A newborn's
            # lookback window always contains milk feeds, so "no feeds" is far
            # more likely an upstream failure than the truth — surface the
            # honest "Feeds unavailable" placeholder rather than a misleading
            # "No feeds logged yet".
            raise ServiceError("No feed intervals in the lookback window.")
        return BabySnapshot(last_feed=last, retrieved_at=self._clock())

    async def _list_recent_intervals(self) -> list[Any]:
        import aiohttp
        from huckleberry_api import HuckleberryAPI

        now = int(self._clock().timestamp())
        start = now - self._lookback_days * 86400
        async with aiohttp.ClientSession() as session:
            api = HuckleberryAPI(self._email, self._password, LONDON.key, session)
            await api.authenticate()
            user = await api.get_user()
            if user is None or not user.childList:
                raise ServiceError("Huckleberry account has no child profile.")
            child_uid = user.childList[0].cid
            return list(await api.list_feed_intervals(child_uid, start, now))
