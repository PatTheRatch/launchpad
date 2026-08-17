"""Portrait-orientation renderer: the classic stacked layout.

Renders the dashboard onto a 1-bit (black & white) Pillow image sized for the
480x800 e-ink panel, with a small typographic hierarchy (bold titles, medium
primary lines, small detail lines), a top header (date/time), and thin dividers
between sections.

Layout is driven by ``state.visible_sections`` (already in mode/priority order)
and dispatched per ``section.section`` — switching dashboard mode changes what
is drawn without touching this renderer. Alternative arrangements of the same
content live in :mod:`launchpad.rendering.layouts`; the drawing primitives and
the section copy are shared via :mod:`~launchpad.rendering.painter` and
:mod:`~launchpad.rendering.summaries`.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw

from launchpad.models.dashboard import DashboardState, Section, SectionState
from launchpad.models.experimental.nba import GameStatus
from launchpad.models.geometry import Orientation, Region, Size
from launchpad.models.result import Availability
from launchpad.models.train import DepartureStatus
from launchpad.models.weather import WeatherCondition
from launchpad.rendering.base import Renderer
from launchpad.rendering.frame import Frame
from launchpad.rendering.painter import (
    GROUP_GAP,
    LEADING,
    WHITE,
    Painter,
    load_fonts,
)
from launchpad.rendering.summaries import (
    CAVS_ABBREVIATION,
    NBA_NICKNAMES,
    condition_text,
    elapsed_text,
    feed_detail,
    outerwear_hint,
)
from launchpad.rendering.weather_icons import draw_weather_icon

LONDON = ZoneInfo("Europe/London")

# Weather icon, drawn beside the primary weather line. Sized to roughly the
# primary text height; the line indents by this width plus a gap so text and
# icon never overlap.
_WEATHER_ICON_PX = 24
_WEATHER_ICON_GAP = 12


class PortraitRenderer(Renderer):
    """Stacks dashboard sections vertically for a tall display."""

    @property
    def orientation(self) -> Orientation:
        return Orientation.PORTRAIT

    def render(self, state: DashboardState, size: Size) -> Frame:
        img = Image.new("1", (size.width, size.height), WHITE)
        draw = ImageDraw.Draw(img)
        painter = Painter(
            draw, load_fonts(), Region(0, 0, size.width, size.height)
        )

        self._draw_top_header(painter, state.generated_at)
        painter.divider()

        handlers: dict[Section, Callable[[Painter, SectionState], None]] = {
            Section.TRAINS: self._draw_trains,
            Section.CALENDAR: self._draw_calendar,
            Section.CALENDAR_TOMORROW: self._draw_calendar,
            Section.WEATHER: self._draw_weather,
            Section.NBA: self._draw_nba,
            # "How long ago" is measured against the frame's own timestamp so
            # the renderer stays a pure function of the state.
            Section.BABY: lambda p, section: self._draw_baby(p, section, state.generated_at),
            Section.WORLD_CUP: self._draw_world_cup,
        }

        drawn = 0
        for section in state.visible_sections:
            if painter.exhausted:
                break
            handler = handlers.get(section.section)
            if handler is None:
                continue
            if drawn > 0:
                painter.divider()
            handler(painter, section)
            drawn += 1

        return Frame(size=size, buffer=img)

    @staticmethod
    def _draw_top_header(painter: Painter, when: datetime) -> None:
        painter.header_row(f"{when:%A %d %B}", f"{when:%H:%M}", painter.fonts.meta)

    @staticmethod
    def _draw_trains(painter: Painter, section: SectionState) -> None:
        # section.data is a tuple of StationArrivals, one per configured station.
        stations = section.data
        if section.availability is Availability.UNAVAILABLE or not stations:
            painter.line("Trains", painter.fonts.title)
            painter.line("Trains unavailable", painter.fonts.secondary)
            return

        for index, station in enumerate(stations):
            if painter.exhausted:
                break
            if index > 0:
                painter.gap(GROUP_GAP)
            # Show line status only when it's a disruption (hide "Good Service").
            status = station.line_status
            status_text = (
                status.description if status is not None and not status.is_good_service else None
            )
            painter.title_with_status(station.station, status_text)

            if station.availability is Availability.UNAVAILABLE or station.board is None:
                painter.line("Unavailable", painter.fonts.secondary)
                continue
            if station.availability is Availability.EMPTY or not station.board.departures:
                painter.line("No departures", painter.fonts.secondary)
                continue

            for departure in station.board.departures:
                if painter.exhausted:
                    break
                when = (
                    departure.expected if departure.expected is not None else departure.scheduled
                )
                status_text = ""
                if departure.status is DepartureStatus.DELAYED:
                    status_text = "(delayed)"
                elif departure.status is DepartureStatus.CANCELLED:
                    status_text = "(cancelled)"
                painter.train_row(departure.destination, f"{when:%H:%M}", status_text)

    @staticmethod
    def _draw_calendar(painter: Painter, section: SectionState) -> None:
        title = "Tomorrow" if section.section is Section.CALENDAR_TOMORROW else "Today"
        painter.line(title, painter.fonts.title)

        if section.availability is Availability.UNAVAILABLE:
            painter.line("Calendar unavailable", painter.fonts.secondary)
            return
        agenda = section.data
        if section.availability is Availability.EMPTY or agenda is None or not agenda.events:
            painter.line("No events", painter.fonts.secondary)
            return

        for event in agenda.events:
            if painter.exhausted:
                break
            time_label = "All day" if event.all_day else f"{event.start:%H:%M}"
            painter.line(f"{time_label}   {event.title}", painter.fonts.primary)

    @staticmethod
    def _draw_world_cup(painter: Painter, section: SectionState) -> None:
        painter.line("WORLD CUP", painter.fonts.title)

        watchlist = section.data
        if (
            section.availability is not Availability.PRESENT
            or watchlist is None
            or not watchlist.teams
        ):
            painter.line("No watchlist", painter.fonts.secondary)
            return

        for index, team in enumerate(watchlist.teams):
            if painter.exhausted:
                break
            if index > 0:
                painter.gap(GROUP_GAP)
            painter.line(team.team_name, painter.fonts.title)
            if team.last_result:
                painter.line(f"Last: {team.last_result}", painter.fonts.secondary)
            if team.next_match:
                painter.line(f"Next: {team.next_match}", painter.fonts.secondary)
            # group_summary is the lowest-priority line; drop it once space runs out.
            if team.group_summary and not painter.exhausted:
                painter.line(team.group_summary, painter.fonts.secondary)

    @staticmethod
    def _draw_nba(painter: Painter, section: SectionState) -> None:
        painter.line("CAVS", painter.fonts.title)

        snapshot = section.data
        game = snapshot.game if snapshot is not None else None
        if section.availability is not Availability.PRESENT or game is None:
            painter.line("No upcoming games", painter.fonts.secondary)
            return

        is_home = game.home_team == CAVS_ABBREVIATION
        opponent_abbr = game.away_team if is_home else game.home_team
        opponent_name = NBA_NICKNAMES.get(opponent_abbr, opponent_abbr)

        if game.status is GameStatus.SCHEDULED:
            painter.line(f"vs {opponent_name}", painter.fonts.primary)
            tip_off_local = game.tip_off.astimezone(LONDON)
            painter.line(f"{tip_off_local:%a %-I:%M %p}", painter.fonts.secondary)
            painter.line("Upcoming", painter.fonts.title)
            return

        cavs_score = game.home_score if is_home else game.away_score
        opponent_score = game.away_score if is_home else game.home_score
        painter.line(
            f"CLE {cavs_score} - {opponent_score} {opponent_abbr}",
            painter.fonts.primary,
        )
        if game.status is GameStatus.LIVE:
            painter.line("LIVE", painter.fonts.title)
        else:
            painter.line("Final", painter.fonts.title)

    @staticmethod
    def _draw_baby(painter: Painter, section: SectionState, now: datetime) -> None:
        snapshot = section.data
        if section.availability is Availability.UNAVAILABLE or snapshot is None:
            painter.line("Last feed", painter.fonts.title)
            painter.line("Feeds unavailable", painter.fonts.secondary)
            return

        feed = snapshot.last_feed
        if feed is None:
            painter.line("Last feed", painter.fonts.title)
            painter.line("No feeds logged yet", painter.fonts.secondary)
            return

        ended_local = feed.ended_at.astimezone(LONDON)
        painter.title_with_status("Last feed", f"{ended_local:%-I:%M%p}".lower())
        painter.line(elapsed_text(now - feed.ended_at), painter.fonts.primary)
        painter.line(feed_detail(feed), painter.fonts.secondary)

    @staticmethod
    def _draw_weather(painter: Painter, section: SectionState) -> None:
        report = section.data
        title = report.location if report is not None else "Weather"
        painter.line(title, painter.fonts.title)

        # Weather is expected to be PRESENT or UNAVAILABLE; treat anything else
        # (including an unexpected EMPTY) as unavailable.
        if section.availability is not Availability.PRESENT or report is None:
            painter.line("Weather unavailable", painter.fonts.secondary)
            return

        current = report.current
        condition = condition_text(current.condition)
        primary = f"{round(current.temperature_c)}°C"
        if condition:
            primary += f"   {condition}"

        # Center the icon on the primary line and indent the text so the glyph
        # reads as part of the weather phrase. UNKNOWN draws no icon.
        draw_icon = current.condition is not WeatherCondition.UNKNOWN
        line_top = painter.y
        if draw_icon:
            visible_h = painter.line_height(painter.fonts.primary) - LEADING
            icon_y = line_top + max(0, (visible_h - _WEATHER_ICON_PX) // 2)
            draw_weather_icon(
                painter.draw,
                current.condition,
                painter.left,
                icon_y,
                _WEATHER_ICON_PX,
            )
            painter.line(
                primary,
                painter.fonts.primary,
                indent=_WEATHER_ICON_PX + _WEATHER_ICON_GAP,
            )
        else:
            painter.line(primary, painter.fonts.primary)

        details: list[str] = []
        if current.feels_like_c is not None:
            details.append(f"Feels {round(current.feels_like_c)}°C")
        high_c: float | None = None
        precipitation_pct: float | None = None
        if report.forecast:
            forecast = report.forecast[0]
            high_c = forecast.high_c
            precipitation_pct = forecast.precipitation_pct
            details.append(f"H {round(forecast.high_c)}°  L {round(forecast.low_c)}°")
            if forecast.precipitation_pct is not None:
                details.append(f"Rain {round(forecast.precipitation_pct)}%")
        if details:
            painter.line("   ".join(details), painter.fonts.secondary)

        hint = outerwear_hint(
            current.temperature_c,
            current.feels_like_c,
            high_c,
            precipitation_pct,
        )
        if hint:
            painter.line(hint, painter.fonts.secondary)
