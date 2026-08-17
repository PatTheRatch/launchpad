"""What each section says, independent of how a layout arranges it.

Every function here is pure and returns text (or a :class:`Stat`), so all
layouts describe the weather, the next train, or the last feed identically
and only differ in placement. Availability is handled here too: an
unavailable section still produces a sensible title and placeholder.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from launchpad.models.calendar import CalendarEvent
from launchpad.models.dashboard import DashboardMode, DashboardState, Section, SectionState
from launchpad.models.experimental.baby import Feed, FeedType
from launchpad.models.experimental.nba import GameStatus
from launchpad.models.result import Availability
from launchpad.models.train import DepartureStatus
from launchpad.models.weather import WeatherCondition

LONDON = ZoneInfo("Europe/London")

CAVS_ABBREVIATION = "CLE"

#: NBA team abbreviation -> nickname, used to render a friendly opponent name
#: (e.g. "vs Bulls") from the abbreviations the NBA service provides.
NBA_NICKNAMES: dict[str, str] = {
    "ATL": "Hawks", "BOS": "Celtics", "BKN": "Nets", "CHA": "Hornets",
    "CHI": "Bulls", "CLE": "Cavaliers", "DAL": "Mavericks", "DEN": "Nuggets",
    "DET": "Pistons", "GSW": "Warriors", "HOU": "Rockets", "IND": "Pacers",
    "LAC": "Clippers", "LAL": "Lakers", "MEM": "Grizzlies", "MIA": "Heat",
    "MIL": "Bucks", "MIN": "Timberwolves", "NOP": "Pelicans", "NYK": "Knicks",
    "OKC": "Thunder", "ORL": "Magic", "PHI": "76ers", "PHX": "Suns",
    "POR": "Trail Blazers", "SAC": "Kings", "SAS": "Spurs", "TOR": "Raptors",
    "UTA": "Jazz", "WAS": "Wizards",
}

#: Compact display labels for each feed type.
FEED_TYPE_LABELS: dict[FeedType, str] = {
    FeedType.BREAST: "Breast",
    FeedType.BOTTLE: "Bottle",
    FeedType.FORMULA: "Formula",
}


@dataclass(frozen=True, slots=True)
class Stat:
    """A section reduced to one headline number: eyebrow, value, caption."""

    label: str
    value: str
    caption: str = ""


# --------------------------------------------------------------------------- #
# Feed and weather text (shared by every layout)
# --------------------------------------------------------------------------- #


def elapsed_text(elapsed: timedelta) -> str:
    """Humanize the time since the feed ended ("5m ago", "1h 20m ago")."""
    minutes = int(elapsed.total_seconds() // 60)
    if minutes < 1:
        return "Just now"
    hours, minutes = divmod(minutes, 60)
    if hours < 1:
        return f"{minutes}m ago"
    days, hours = divmod(hours, 24)
    if days < 1:
        return f"{hours}h {minutes}m ago" if minutes else f"{hours}h ago"
    return f"{days}d {hours}h ago" if hours else f"{days}d ago"


def elapsed_value(elapsed: timedelta) -> str:
    """The same duration without the "ago" suffix, for hero/tile values."""
    text = elapsed_text(elapsed)
    return text[:-4] if text.endswith(" ago") else text


def feed_detail(feed: Feed) -> str:
    """One compact line: "Formula · 80ml" or "Breast · right · 6m"."""
    parts = [FEED_TYPE_LABELS[feed.feed_type]]
    if feed.feed_type is FeedType.BREAST:
        if feed.side:
            parts.append(feed.side)
        if feed.duration_seconds:
            # Never show a nonsense "0m" for a sub-30-second latch.
            parts.append(f"{max(1, round(feed.duration_seconds / 60))}m")
    elif feed.amount_ml is not None:
        parts.append(f"{round(feed.amount_ml)}ml")
    return " · ".join(parts)


def condition_text(condition: WeatherCondition) -> str:
    if condition is WeatherCondition.UNKNOWN:
        return ""
    return str(condition.value).replace("_", " ").title()


def outerwear_hint(
    temperature_c: float,
    feels_like_c: float | None,
    high_c: float | None,
    precipitation_pct: float | None,
) -> str | None:
    """Return a compact clothing/weather hint when one is useful."""
    feels = feels_like_c if feels_like_c is not None else temperature_c
    high = high_c if high_c is not None else temperature_c

    if precipitation_pct is not None and precipitation_pct >= 55:
        return "Bring an umbrella"
    if feels <= 5:
        return "Wear a warm coat"
    if feels <= 12 or high <= 14:
        return "Bring a jacket"
    if feels <= 17 and high <= 21:
        return "Light jacket"
    return None


# --------------------------------------------------------------------------- #
# Per-section titles, one-liners, and stats
# --------------------------------------------------------------------------- #

_TITLES: dict[Section, str] = {
    Section.TRAINS: "Trains",
    Section.WEATHER: "Weather",
    Section.CALENDAR: "Today",
    Section.CALENDAR_TOMORROW: "Tomorrow",
    Section.NBA: "CAVS",
    Section.FANTASY: "Fantasy",
    Section.BABY: "Last feed",
    Section.WORLD_CUP: "World Cup",
}

_UNAVAILABLE: dict[Section, str] = {
    Section.TRAINS: "Trains unavailable",
    Section.WEATHER: "Weather unavailable",
    Section.CALENDAR: "Calendar unavailable",
    Section.CALENDAR_TOMORROW: "Calendar unavailable",
    Section.NBA: "No upcoming games",
    Section.FANTASY: "Fantasy unavailable",
    Section.BABY: "Feeds unavailable",
    Section.WORLD_CUP: "No watchlist",
}


def title_for(section: SectionState) -> str:
    """The section's heading. Weather uses its location when it has one."""
    if section.section is Section.WEATHER and section.data is not None:
        return str(section.data.location)
    return _TITLES[section.section]


def _is_present(section: SectionState) -> bool:
    return section.availability is Availability.PRESENT and section.data is not None


def next_departure(section: SectionState) -> tuple[str, str, datetime] | None:
    """The soonest upcoming departure as (destination, station, when)."""
    if not _is_present(section):
        return None
    best: tuple[str, str, datetime] | None = None
    for station in section.data:
        if station.availability is not Availability.PRESENT or station.board is None:
            continue
        for departure in station.board.departures:
            if departure.status is DepartureStatus.CANCELLED:
                continue
            when = departure.expected if departure.expected is not None else departure.scheduled
            if best is None or when < best[2]:
                best = (departure.destination, station.station, when)
    return best


def next_event(section: SectionState) -> CalendarEvent | None:
    """The first event on the agenda, if any."""
    if not _is_present(section) or not section.data.events:
        return None
    event: CalendarEvent = section.data.events[0]
    return event


def stat_for(section: SectionState, now: datetime) -> Stat:
    """Reduce a section to a single headline number for tiles and heroes."""
    kind = section.section
    label = _TITLES[kind].upper()
    if not _is_present(section):
        return Stat(label=label, value="—", caption=_UNAVAILABLE[kind])

    if kind is Section.TRAINS:
        departure = next_departure(section)
        if departure is None:
            return Stat(label="NEXT TRAIN", value="—", caption="No departures")
        destination, station, when = departure
        local = when.astimezone(LONDON)
        minutes = int((when - now).total_seconds() // 60)
        countdown = f"in {minutes} min" if 0 <= minutes < 60 else station
        return Stat(
            label="NEXT TRAIN",
            value=f"{local:%H:%M}",
            caption=f"{destination} · {countdown}",
        )

    if kind is Section.WEATHER:
        report = section.data
        current = report.current
        details = [condition_text(current.condition) or "Now"]
        if report.forecast:
            forecast = report.forecast[0]
            details.append(f"H {round(forecast.high_c)}° L {round(forecast.low_c)}°")
        return Stat(
            label=report.location.upper(),
            value=f"{round(current.temperature_c)}°C",
            caption=" · ".join(details),
        )

    if kind in (Section.CALENDAR, Section.CALENDAR_TOMORROW):
        event = next_event(section)
        if event is None:
            return Stat(label=label, value="—", caption="No events")
        remaining = len(section.data.events) - 1
        caption = event.title + (f" +{remaining} more" if remaining > 0 else "")
        value = "All day" if event.all_day else f"{event.start.astimezone(LONDON):%H:%M}"
        return Stat(label=label, value=value, caption=caption)

    if kind is Section.BABY:
        feed = section.data.last_feed
        if feed is None:
            return Stat(label=label, value="—", caption="No feeds logged yet")
        finished = f"{feed.ended_at.astimezone(LONDON):%-I:%M%p}".lower()
        return Stat(
            label="SINCE LAST FEED",
            value=elapsed_value(now - feed.ended_at),
            caption=f"{feed_detail(feed)} · {finished}",
        )

    if kind is Section.NBA:
        game = section.data.game
        if game is None:
            return Stat(label=label, value="—", caption="No upcoming games")
        is_home = game.home_team == CAVS_ABBREVIATION
        opponent = game.away_team if is_home else game.home_team
        nickname = NBA_NICKNAMES.get(opponent, opponent)
        if game.status is GameStatus.SCHEDULED:
            tip_off = game.tip_off.astimezone(LONDON)
            return Stat(label=label, value=f"{tip_off:%a}", caption=f"vs {nickname} {tip_off:%-I:%M%p}".lower())
        cavs = game.home_score if is_home else game.away_score
        other = game.away_score if is_home else game.home_score
        state = "LIVE" if game.status is GameStatus.LIVE else "Final"
        return Stat(label=label, value=f"{cavs}-{other}", caption=f"{state} vs {nickname}")

    if kind is Section.WORLD_CUP:
        teams = section.data.teams
        if not teams:
            return Stat(label=label, value="—", caption="No watchlist")
        team = teams[0]
        return Stat(label=label, value=team.team_code, caption=team.next_match or team.team_name)

    return Stat(label=label, value="—", caption="")


def one_line(section: SectionState, now: datetime) -> str:
    """A single-line summary for ledger rows."""
    kind = section.section
    if not _is_present(section):
        return _UNAVAILABLE[kind]

    if kind is Section.TRAINS:
        departure = next_departure(section)
        if departure is None:
            return "No departures"
        destination, _station, when = departure
        return f"{when.astimezone(LONDON):%H:%M} {destination}"

    if kind is Section.WEATHER:
        report = section.data
        parts = [f"{round(report.current.temperature_c)}°C"]
        condition = condition_text(report.current.condition)
        if condition:
            parts.append(condition)
        hint = outerwear_hint(
            report.current.temperature_c,
            report.current.feels_like_c,
            report.forecast[0].high_c if report.forecast else None,
            report.forecast[0].precipitation_pct if report.forecast else None,
        )
        if hint:
            parts.append(hint.lower())
        return " · ".join(parts)

    if kind in (Section.CALENDAR, Section.CALENDAR_TOMORROW):
        event = next_event(section)
        if event is None:
            return "No events"
        remaining = len(section.data.events) - 1
        time_label = "All day" if event.all_day else f"{event.start.astimezone(LONDON):%H:%M}"
        suffix = f" +{remaining} more" if remaining > 0 else ""
        return f"{time_label} {event.title}{suffix}"

    if kind is Section.BABY:
        feed = section.data.last_feed
        if feed is None:
            return "No feeds logged yet"
        return f"{elapsed_text(now - feed.ended_at)} · {feed_detail(feed)}"

    stat = stat_for(section, now)
    return f"{stat.value} {stat.caption}".strip()


def detail_lines(section: SectionState, now: datetime) -> tuple[str, ...]:
    """The multi-line body of a section, for layouts with room for it."""
    kind = section.section
    if not _is_present(section):
        return (_UNAVAILABLE[kind],)

    if kind in (Section.CALENDAR, Section.CALENDAR_TOMORROW):
        events = section.data.events
        if not events:
            return ("No events",)
        return tuple(
            f"{'All day' if event.all_day else format(event.start.astimezone(LONDON), '%H:%M')}"
            f"   {event.title}"
            for event in events
        )

    if kind is Section.BABY:
        feed = section.data.last_feed
        if feed is None:
            return ("No feeds logged yet",)
        return (elapsed_text(now - feed.ended_at), feed_detail(feed))

    stat = stat_for(section, now)
    return tuple(part for part in (stat.value, stat.caption) if part and part != "—")


# --------------------------------------------------------------------------- #
# Mode heroes and timeline entries
# --------------------------------------------------------------------------- #

#: Which section supplies each mode's headline number. Morning and daytime
#: ask "can I make the train?"; evening and overnight ask "how long since
#: she ate?" — a newborn's night is measured in feeds, not departures.
HERO_SECTION: dict[DashboardMode, Section] = {
    DashboardMode.MORNING: Section.TRAINS,
    DashboardMode.DAYTIME: Section.TRAINS,
    DashboardMode.EVENING: Section.BABY,
    DashboardMode.OVERNIGHT: Section.BABY,
}


def hero_for(state: DashboardState, now: datetime) -> tuple[Section, Stat] | None:
    """The mode's headline section and its stat, when that section is visible."""
    section_kind = HERO_SECTION.get(state.mode)
    if section_kind is None:
        return None
    section = state.get(section_kind)
    if section is None or not section.visible:
        return None
    return section_kind, stat_for(section, now)


@dataclass(frozen=True, slots=True)
class TimelineEntry:
    """One dated thing to plot on the day strip."""

    when: datetime
    label: str
    marker: str  # "event", "feed", or "train"


def timeline_entries(state: DashboardState, now: datetime) -> tuple[TimelineEntry, ...]:
    """Everything on today's strip, in chronological order."""
    entries: list[TimelineEntry] = []

    for kind in (Section.CALENDAR, Section.CALENDAR_TOMORROW):
        section = state.get(kind)
        if section is None or not _is_present(section):
            continue
        for event in section.data.events:
            if event.all_day:
                continue
            entries.append(
                TimelineEntry(event.start.astimezone(LONDON), event.title, "event")
            )

    trains = state.get(Section.TRAINS)
    if trains is not None:
        departure = next_departure(trains)
        if departure is not None:
            destination, _station, when = departure
            entries.append(
                TimelineEntry(when.astimezone(LONDON), f"Train · {destination}", "train")
            )

    baby = state.get(Section.BABY)
    if baby is not None and _is_present(baby) and baby.data.last_feed is not None:
        feed = baby.data.last_feed
        entries.append(
            TimelineEntry(
                feed.ended_at.astimezone(LONDON), f"Feed · {feed_detail(feed)}", "feed"
            )
        )

    return tuple(sorted(entries, key=lambda entry: entry.when))
