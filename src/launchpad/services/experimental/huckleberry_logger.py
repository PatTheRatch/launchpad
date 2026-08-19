"""Write path to the Huckleberry backend: log feeds, diapers, and sleep.

The counterpart to :mod:`huckleberry_baby_service` (which only reads). Writes
are riskier than reads — a bug here creates real records of the baby's care —
so this module is deliberately conservative:

* every input is validated before anything touches the network;
* every call is a **single attempt, never retried** — a retried ``log_bottle``
  is a duplicate feed in the history, not a harmless no-op;
* failures raise :class:`FeedLogError` with a user-facing message and are
  reported, not swallowed.

Like the read service, the library is imported lazily (the ``baby`` extra)
and bridged from async with ``asyncio.run()`` per call. Each write performs
its own authentication round trip; at tap-a-button cadence that costs a
couple of seconds and keeps the writer stateless.
"""

from __future__ import annotations

import asyncio
from typing import Any
from zoneinfo import ZoneInfo

LONDON = ZoneInfo("Europe/London")

#: Bottle types the logger accepts (a deliberate subset of Huckleberry's).
BOTTLE_TYPES = ("Formula", "Breast Milk")

#: Huckleberry's diaper modes, verbatim.
DIAPER_MODES = ("pee", "poo", "both", "dry")

#: Sleep is a timer lifecycle, not an instant event.
SLEEP_ACTIONS = ("start", "complete", "cancel")

_SLEEP_METHODS = {"start": "start_sleep", "complete": "complete_sleep", "cancel": "cancel_sleep"}

#: Sanity bound; the biggest newborn bottles are ~300ml.
_MAX_BOTTLE_ML = 500.0


class FeedLogError(Exception):
    """A write could not be completed; the message is user-facing."""


class HuckleberryLogger:
    """Logs care events for the first child on the account."""

    def __init__(self, email: str, password: str) -> None:
        self._email = email
        self._password = password

    def log_bottle(self, amount_ml: float, bottle_type: str = "Formula") -> dict[str, Any]:
        """Log a finished bottle. Returns the payload actually recorded."""
        try:
            amount = float(amount_ml)
        except (TypeError, ValueError):
            raise ValueError("amount_ml must be a number.") from None
        if not 0 < amount <= _MAX_BOTTLE_ML:
            raise ValueError(f"amount_ml must be between 1 and {_MAX_BOTTLE_ML:.0f}.")
        if bottle_type not in BOTTLE_TYPES:
            raise ValueError(f"bottle_type must be one of: {', '.join(BOTTLE_TYPES)}.")

        self._run("log_bottle", amount=amount, bottle_type=bottle_type, units="ml")
        return {"amount_ml": amount, "bottle_type": bottle_type}

    def log_diaper(self, mode: str, notes: str | None = None) -> dict[str, Any]:
        """Log a diaper change. Amount/color detail stays in the app for now."""
        if mode not in DIAPER_MODES:
            raise ValueError(f"mode must be one of: {', '.join(DIAPER_MODES)}.")
        if notes is not None and not isinstance(notes, str):
            raise ValueError("notes must be a string.")

        self._run("log_diaper", mode=mode, notes=notes or None)
        return {"mode": mode, **({"notes": notes} if notes else {})}

    def sleep(self, action: str) -> dict[str, Any]:
        """Drive the sleep timer: start it, complete it, or cancel it."""
        if action not in SLEEP_ACTIONS:
            raise ValueError(f"action must be one of: {', '.join(SLEEP_ACTIONS)}.")

        self._run(_SLEEP_METHODS[action])
        return {"action": action}

    def _run(self, method: str, **kwargs: Any) -> None:
        # Single attempt by design: on any failure the caller reports it and a
        # human decides whether to tap again. Automatic retries would risk
        # duplicate entries in the baby's history.
        if not self._email or not self._password:
            raise FeedLogError("Huckleberry credentials are not configured.")
        try:
            asyncio.run(self._call(method, **kwargs))
        except FeedLogError:
            raise
        except Exception as exc:
            raise FeedLogError(f"Huckleberry write failed: {exc}") from exc

    async def _call(self, method: str, **kwargs: Any) -> None:
        import aiohttp
        from huckleberry_api import HuckleberryAPI

        async with aiohttp.ClientSession() as session:
            api = HuckleberryAPI(self._email, self._password, LONDON.key, session)
            await api.authenticate()
            user = await api.get_user()
            if user is None or not user.childList:
                raise FeedLogError("Huckleberry account has no child profile.")
            await getattr(api, method)(user.childList[0].cid, **kwargs)
