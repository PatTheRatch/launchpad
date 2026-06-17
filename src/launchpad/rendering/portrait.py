"""Portrait-orientation renderer.

Renders the dashboard onto a 1-bit (black & white) Pillow image sized for the
480x800 e-ink panel, with a small typographic hierarchy (bold titles, medium
primary lines, small detail lines), a top header (date/time), and thin dividers
between sections.

Layout is driven by ``state.visible_sections`` (already in mode/priority order)
and dispatched per ``section.section`` — switching dashboard mode changes what
is drawn without touching this renderer.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from PIL import Image, ImageDraw

from launchpad.models.dashboard import DashboardState, Section, SectionState
from launchpad.models.geometry import Orientation, Size
from launchpad.models.result import Availability
from launchpad.models.train import DepartureStatus
from launchpad.models.weather import WeatherCondition
from launchpad.rendering.base import Renderer
from launchpad.rendering.fonts import Font, load_font
from launchpad.rendering.frame import Frame
from launchpad.rendering.weather_icons import draw_weather_icon

# Pixel values for 1-bit images: 1 = white background, 0 = black ink.
_WHITE = 1
_BLACK = 0

# Typographic scale (px).
_TITLE_PX = 30
_PRIMARY_PX = 23
_SECONDARY_PX = 17
_META_PX = 18

# Spacing.
_MARGIN_X = 18
_MARGIN_TOP = 14
_LEADING = 7
_DIVIDER_PAD = 9

# Train row columns: the time right-aligns to a fixed column so every
# departure time lines up vertically, with the status marker in a reserved
# right-side area beyond it.
_TRAIN_STATUS_AREA_W = 150
_TRAIN_COL_GAP = 12

# Vertical gap between stations within the trains section (smaller than a
# divider, which separates whole sections).
_STATION_GAP = 8

# Weather icon, drawn beside the primary weather line. Sized to roughly the
# primary text height; the line indents by this width plus a gap so text and
# icon never overlap.
_WEATHER_ICON_PX = 24
_WEATHER_ICON_GAP = 12

_ELLIPSIS = "..."


@dataclass(frozen=True, slots=True)
class _Fonts:
    title: Font
    primary: Font
    secondary: Font
    meta: Font


def _text_width(draw: ImageDraw.ImageDraw, text: str, font: Font) -> float:
    return draw.textlength(text, font=font)


def _truncate(draw: ImageDraw.ImageDraw, text: str, font: Font, max_width: float) -> str:
    """Trim ``text`` from the right and append an ellipsis to fit ``max_width``."""
    if _text_width(draw, text, font) <= max_width:
        return text
    if _text_width(draw, _ELLIPSIS, font) > max_width:
        return ""
    trimmed = text
    while trimmed and _text_width(draw, trimmed + _ELLIPSIS, font) > max_width:
        trimmed = trimmed[:-1]
    return (trimmed + _ELLIPSIS) if trimmed else _ELLIPSIS


class _Painter:
    """A top-down cursor over the image; never draws past the panel height."""

    def __init__(self, draw: ImageDraw.ImageDraw, fonts: _Fonts, width: int, height: int) -> None:
        self.draw = draw
        self.fonts = fonts
        self.width = width
        self.height = height
        self.y = _MARGIN_TOP

    @property
    def exhausted(self) -> bool:
        return self.y >= self.height

    def _line_height(self, font: Font) -> int:
        bbox = self.draw.textbbox((0, 0), "Ahgyltpq", font=font)
        return int(bbox[3] - bbox[1]) + _LEADING

    def line(self, text: str, font: Font, *, indent: int = 0, reserve_right: int = 0) -> None:
        max_width = self.width - 2 * _MARGIN_X - indent - reserve_right
        content = _truncate(self.draw, text, font, max_width)
        line_height = self._line_height(font)
        if self.y + line_height <= self.height:
            self.draw.text((_MARGIN_X + indent, self.y), content, font=font, fill=_BLACK)
        self.y += line_height

    def train_row(self, destination: str, time_text: str, status_text: str) -> None:
        """Draw a departure as fixed columns: destination | time | status.

        The time right-aligns to a constant column so times stack vertically;
        only the destination is truncated, keeping the time and status visible.
        """
        font = self.fonts.primary
        line_height = self._line_height(font)
        draw_this_row = self.y + line_height <= self.height

        time_right_x = self.width - _MARGIN_X - _TRAIN_STATUS_AREA_W
        time_x = time_right_x - _text_width(self.draw, time_text, font)
        destination_max = time_x - _TRAIN_COL_GAP - _MARGIN_X
        destination_text = _truncate(self.draw, destination, font, destination_max)

        if draw_this_row:
            self.draw.text((_MARGIN_X, self.y), destination_text, font=font, fill=_BLACK)
            self.draw.text((time_x, self.y), time_text, font=font, fill=_BLACK)
            if status_text:
                status_x = time_right_x + _TRAIN_COL_GAP
                status_max = (self.width - _MARGIN_X) - status_x
                status = _truncate(self.draw, status_text, font, status_max)
                self.draw.text((status_x, self.y), status, font=font, fill=_BLACK)
        self.y += line_height

    def title_with_status(self, title: str, status: str | None) -> None:
        """Draw a section title, with an optional status right-aligned beside it.

        The title uses the title font; the status uses the smaller secondary
        font, vertically centered on the title. The title is truncated so it
        never overlaps the status.
        """
        title_font = self.fonts.title
        line_height = self._line_height(title_font)
        if not status:
            self.line(title, title_font)
            return

        status_font = self.fonts.secondary
        status_width = _text_width(self.draw, status, status_font)
        title_max = self.width - 2 * _MARGIN_X - status_width - _TRAIN_COL_GAP
        title_text = _truncate(self.draw, title, title_font, title_max)
        if self.y + line_height <= self.height:
            self.draw.text((_MARGIN_X, self.y), title_text, font=title_font, fill=_BLACK)
            status_h = self.draw.textbbox((0, 0), "Ag", font=status_font)[3]
            status_y = self.y + max(0, (line_height - _LEADING - status_h) // 2)
            self.draw.text(
                (self.width - _MARGIN_X - status_width, status_y),
                status,
                font=status_font,
                fill=_BLACK,
            )
        self.y += line_height

    def header_row(self, left: str, right: str, font: Font) -> None:
        line_height = self._line_height(font)
        if self.y + line_height <= self.height:
            self.draw.text((_MARGIN_X, self.y), left, font=font, fill=_BLACK)
            right_width = _text_width(self.draw, right, font)
            self.draw.text(
                (self.width - _MARGIN_X - right_width, self.y), right, font=font, fill=_BLACK
            )
        self.y += line_height

    def gap(self, px: int) -> None:
        self.y += px

    def divider(self) -> None:
        self.y += _DIVIDER_PAD
        if self.y <= self.height:
            self.draw.line(
                [(_MARGIN_X, self.y), (self.width - _MARGIN_X, self.y)], fill=_BLACK, width=1
            )
        self.y += _DIVIDER_PAD


class PortraitRenderer(Renderer):
    """Stacks dashboard sections vertically for a tall display."""

    @property
    def orientation(self) -> Orientation:
        return Orientation.PORTRAIT

    def render(self, state: DashboardState, size: Size) -> Frame:
        img = Image.new("1", (size.width, size.height), _WHITE)
        draw = ImageDraw.Draw(img)
        fonts = _Fonts(
            title=load_font(_TITLE_PX, bold=True),
            primary=load_font(_PRIMARY_PX),
            secondary=load_font(_SECONDARY_PX),
            meta=load_font(_META_PX, bold=True),
        )
        painter = _Painter(draw, fonts, size.width, size.height)

        self._draw_top_header(painter, state.generated_at)
        painter.divider()

        handlers: dict[Section, Callable[[_Painter, SectionState], None]] = {
            Section.TRAINS: self._draw_trains,
            Section.CALENDAR: self._draw_calendar,
            Section.CALENDAR_TOMORROW: self._draw_calendar,
            Section.WEATHER: self._draw_weather,
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
    def _draw_top_header(painter: _Painter, when: datetime) -> None:
        painter.header_row(f"{when:%A %d %B}", f"{when:%H:%M}", painter.fonts.meta)

    @staticmethod
    def _draw_trains(painter: _Painter, section: SectionState) -> None:
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
                painter.gap(_STATION_GAP)
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
    def _draw_calendar(painter: _Painter, section: SectionState) -> None:
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
    def _draw_weather(painter: _Painter, section: SectionState) -> None:
        report = section.data
        title = report.location if report is not None else "Weather"
        painter.line(title, painter.fonts.title)

        # Weather is expected to be PRESENT or UNAVAILABLE; treat anything else
        # (including an unexpected EMPTY) as unavailable.
        if section.availability is not Availability.PRESENT or report is None:
            painter.line("Weather unavailable", painter.fonts.secondary)
            return

        current = report.current
        condition = _condition_text(current.condition)
        primary = f"{round(current.temperature_c)}\u00b0C"
        if condition:
            primary += f"   {condition}"

        # Center the icon on the primary line and indent the text so the glyph
        # reads as part of the weather phrase. UNKNOWN draws no icon.
        draw_icon = current.condition is not WeatherCondition.UNKNOWN
        line_top = painter.y
        if draw_icon:
            visible_h = painter._line_height(painter.fonts.primary) - _LEADING
            icon_y = line_top + max(0, (visible_h - _WEATHER_ICON_PX) // 2)
            draw_weather_icon(
                painter.draw,
                current.condition,
                _MARGIN_X,
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
            details.append(f"Feels {round(current.feels_like_c)}\u00b0C")
        high_c: float | None = None
        precipitation_pct: float | None = None
        if report.forecast:
            forecast = report.forecast[0]
            high_c = forecast.high_c
            precipitation_pct = forecast.precipitation_pct
            details.append(f"H {round(forecast.high_c)}\u00b0  L {round(forecast.low_c)}\u00b0")
            if forecast.precipitation_pct is not None:
                details.append(f"Rain {round(forecast.precipitation_pct)}%")
        if details:
            painter.line("   ".join(details), painter.fonts.secondary)

        hint = _outerwear_hint(
            current.temperature_c,
            current.feels_like_c,
            high_c,
            precipitation_pct,
        )
        if hint:
            painter.line(hint, painter.fonts.secondary)


def _condition_text(condition: WeatherCondition) -> str:
    if condition is WeatherCondition.UNKNOWN:
        return ""
    return str(condition.value).replace("_", " ").title()


def _outerwear_hint(
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
