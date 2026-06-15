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

    def line(self, text: str, font: Font, *, indent: int = 0) -> None:
        max_width = self.width - 2 * _MARGIN_X - indent
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

    def header_row(self, left: str, right: str, font: Font) -> None:
        line_height = self._line_height(font)
        if self.y + line_height <= self.height:
            self.draw.text((_MARGIN_X, self.y), left, font=font, fill=_BLACK)
            right_width = _text_width(self.draw, right, font)
            self.draw.text(
                (self.width - _MARGIN_X - right_width, self.y), right, font=font, fill=_BLACK
            )
        self.y += line_height

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
        board = section.data
        title = board.station if board is not None else "Trains"
        painter.line(title, painter.fonts.title)

        if section.availability is Availability.UNAVAILABLE:
            painter.line("Trains unavailable", painter.fonts.secondary)
            return
        if section.availability is Availability.EMPTY or board is None or not board.departures:
            painter.line("No departures", painter.fonts.secondary)
            return

        for departure in board.departures:
            if painter.exhausted:
                break
            when = departure.expected if departure.expected is not None else departure.scheduled
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
        painter.line(primary, painter.fonts.primary)

        details: list[str] = []
        if current.feels_like_c is not None:
            details.append(f"Feels {round(current.feels_like_c)}\u00b0C")
        if report.forecast:
            forecast = report.forecast[0]
            details.append(f"H {round(forecast.high_c)}\u00b0  L {round(forecast.low_c)}\u00b0")
        if details:
            painter.line("   ".join(details), painter.fonts.secondary)


def _condition_text(condition: WeatherCondition) -> str:
    if condition is WeatherCondition.UNKNOWN:
        return ""
    return str(condition.value).replace("_", " ").title()
