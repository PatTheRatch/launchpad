"""Live Cavaliers game data via balldontlie.io + ESPN API (experimental).

Primary source: balldontlie.io (regular season — schedules, scores).
Fallback: ESPN public API (summer league, playoffs, any live game).
"""

from __future__ import annotations

import os
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from launchpad.models.experimental.nba import GameStatus, NbaGame, NbaSnapshot
from launchpad.services.base import ServiceError
from launchpad.services.experimental.nba_service import NbaService

LONDON = ZoneInfo("Europe/London")

CAVS_TEAM_ID = 6
CAVS_ABBREVIATION = "CLE"


# ---------------------------------------------------------------------------
# balldontlie.io helpers
# ---------------------------------------------------------------------------

def _balldontlie_season(now: datetime) -> int:
    """Return the balldontlie season year for the upcoming or current NBA season.

    The NBA season typically starts in October. If we're in Jan–Sep, the
    current calendar year IS the season ending year (e.g. July 2026 → season
    2026 for the 2025–26 season that just ended). If we're in Oct–Dec, the
    *next* calendar year is the ending year."""
    return now.year


def _parse_tip_off(raw: dict[str, Any]) -> datetime | None:
    value = raw.get("datetime")
    if isinstance(value, str) and value:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            pass
    date_text = raw.get("date")
    if isinstance(date_text, str) and date_text:
        try:
            return datetime.fromisoformat(date_text[:10]).replace(tzinfo=ZoneInfo("UTC"))
        except ValueError:
            return None
    return None


def _parse_status(raw: dict[str, Any], now: datetime | None = None) -> GameStatus:
    if raw.get("status") == "Final":
        if now is not None:
            tip_off = _parse_tip_off(raw)
            if tip_off is not None and tip_off > now:
                return GameStatus.SCHEDULED
        return GameStatus.FINAL
    period = raw.get("period") or 0
    if isinstance(period, (int, float)) and period > 0:
        return GameStatus.LIVE
    return GameStatus.SCHEDULED


def _parse_game(raw: dict[str, Any], now: datetime | None = None) -> NbaGame | None:
    home = raw.get("home_team")
    visitor = raw.get("visitor_team")
    if not isinstance(home, dict) or not isinstance(visitor, dict):
        return None
    home_abbr = home.get("abbreviation")
    away_abbr = visitor.get("abbreviation")
    if not isinstance(home_abbr, str) or not isinstance(away_abbr, str):
        return None

    tip_off = _parse_tip_off(raw)
    if tip_off is None:
        return None

    status = _parse_status(raw, now)
    home_score = raw.get("home_team_score") if status is not GameStatus.SCHEDULED else None
    away_score = raw.get("visitor_team_score") if status is not GameStatus.SCHEDULED else None

    return NbaGame(
        home_team=home_abbr,
        away_team=away_abbr,
        tip_off=tip_off,
        status=status,
        home_score=home_score,
        away_score=away_score,
    )


# ---------------------------------------------------------------------------
# ESPN helpers (summer league / live fallback)
# ---------------------------------------------------------------------------

ESPN_SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"


def _fetch_espn_game(now: datetime, timeout_s: float = 8.0) -> NbaGame | None:
    """Try to find today's Cavaliers game from the ESPN public scoreboard."""
    try:
        with httpx.Client(timeout=timeout_s) as client:
            resp = client.get(ESPN_SCOREBOARD)
            resp.raise_for_status()
            payload = resp.json()
    except Exception:
        return None

    events = payload.get("events") or []
    for evt in events:
        comps_list = evt.get("competitions") or []
        if not comps_list:
            continue
        comp = comps_list[0]
        competitors = comp.get("competitors") or []
        abbreviations = [
            (c.get("team") or {}).get("abbreviation", "") for c in competitors
        ]
        if CAVS_ABBREVIATION not in abbreviations:
            continue

        # Build NbaGame from ESPN data.
        status_info = evt.get("status", {}).get("type", {})
        espn_state = status_info.get("state", "")
        espn_detail = status_info.get("detail", "")
        period = comp.get("period", 0) or 0
        clock = status_info.get("displayClock", "")

        if espn_state in ("post", "final"):
            game_status = GameStatus.FINAL
        elif period > 0 or ":" in clock or espn_state == "in":
            game_status = GameStatus.LIVE
        else:
            game_status = GameStatus.SCHEDULED

        # Parse tip-off from ESPN date.
        tip_off = None
        raw_date = evt.get("date", "")
        if raw_date:
            try:
                tip_off = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
            except ValueError:
                tip_off = now

        home_team = ""
        away_team = ""
        home_score = None
        away_score = None
        for c in competitors:
            abbr = (c.get("team") or {}).get("abbreviation", "")
            score_str = c.get("score")
            score = int(score_str) if isinstance(score_str, str) and score_str.isdigit() else None
            if c.get("homeAway") == "home":
                home_team = abbr
                home_score = score
            else:
                away_team = abbr
                away_score = score

        if not home_team or not away_team or tip_off is None:
            continue

        return NbaGame(
            home_team=home_team,
            away_team=away_team,
            tip_off=tip_off,
            status=game_status,
            home_score=home_score,
            away_score=away_score,
        )

    return None


# ---------------------------------------------------------------------------
# Game selection (pure)
# ---------------------------------------------------------------------------

def select_game(games: tuple[NbaGame, ...], now: datetime) -> NbaGame | None:
    """Pick the most relevant game from a set of candidates (pure).

    Preference order: a LIVE/FINAL game today, else a SCHEDULED game today,
    else the next upcoming SCHEDULED game, else ``None``.
    """
    today = now.astimezone(LONDON).date()

    def is_today(game: NbaGame) -> bool:
        return game.tip_off.astimezone(LONDON).date() == today

    live_or_final_today = [g for g in games if is_today(g) and g.status is not GameStatus.SCHEDULED]
    if live_or_final_today:
        return live_or_final_today[0]

    scheduled_today = [g for g in games if is_today(g) and g.status is GameStatus.SCHEDULED]
    if scheduled_today:
        return scheduled_today[0]

    upcoming = sorted(
        (g for g in games if g.status is GameStatus.SCHEDULED and g.tip_off > now),
        key=lambda g: g.tip_off,
    )
    if upcoming:
        return upcoming[0]

    return None


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class LiveNbaService(NbaService):
    """Fetches the Cavaliers' most relevant game from balldontlie + ESPN."""

    def __init__(
        self,
        timeout_s: float = 8.0,
        base_url: str = "https://api.balldontlie.io/v1/games",
        client: httpx.Client | None = None,
        clock: Callable[[], datetime] | None = None,
        api_key: str | None = None,
    ) -> None:
        self._timeout_s = timeout_s
        self._base_url = base_url
        self._client = client
        self._clock = clock or (lambda: datetime.now(LONDON))
        self._api_key = api_key

    @property
    def name(self) -> str:
        return "balldontlie+espn:cavaliers"

    def fetch(self) -> NbaSnapshot:
        now = self._clock()

        # 1. Try balldontlie (regular season schedules + scores).
        game = self._fetch_balldontlie(now)

        # 2. Fall back to ESPN for summer league / live games.
        if game is None:
            game = _fetch_espn_game(now, timeout_s=self._timeout_s)

        return NbaSnapshot(team="Cavaliers", game=game, retrieved_at=now)

    def _fetch_balldontlie(self, now: datetime) -> NbaGame | None:
        api_key = self._api_key if self._api_key is not None else os.getenv("BALLDONTLIE_API_KEY")
        if not api_key:
            raise ServiceError(
                "BALLDONTLIE_API_KEY is not set; cannot fetch Cavaliers game data."
            )

        client = self._client if self._client is not None else httpx.Client(timeout=self._timeout_s)
        owns_client = self._client is None
        try:
            season = _balldontlie_season(now)
            response = client.get(
                self._base_url,
                params=[
                    ("team_ids[]", CAVS_TEAM_ID),
                    ("per_page", 5),
                    ("seasons[]", season),
                ],
                headers={"Authorization": api_key},
                timeout=self._timeout_s,
            )
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPError as exc:
            raise ServiceError("balldontlie request failed for Cavaliers games.") from exc
        except ValueError as exc:
            raise ServiceError("Invalid balldontlie response for Cavaliers games.") from exc
        finally:
            if owns_client:
                client.close()

        if not isinstance(payload, dict):
            raise ServiceError("Unexpected balldontlie payload (expected a JSON object).")
        raw_games = payload.get("data")
        if not isinstance(raw_games, list):
            raise ServiceError("Unexpected balldontlie payload (missing 'data' list).")

        try:
            games = tuple(
                g for g in (_parse_game(raw, now) for raw in raw_games) if g is not None
            )
        except (KeyError, ValueError, TypeError, AttributeError, IndexError) as exc:
            raise ServiceError("Failed to parse balldontlie games payload.") from exc

        return select_game(games, now)
