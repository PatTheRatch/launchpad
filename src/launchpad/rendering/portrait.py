"""Portrait-orientation renderer.

Renders the dashboard onto a 1-bit (black & white) Pillow image suitable for an
e-ink panel. For this initial vertical slice only the trains section is drawn;
other sections are intentionally ignored.
"""

from __future__ import annotations

from PIL import Image, ImageDraw

from launchpad.models.dashboard import DashboardState, Section, SectionState
from launchpad.models.geometry import Orientation, Size
from launchpad.models.result import Availability
from launchpad.models.train import DepartureStatus
from launchpad.rendering.base import Renderer
from launchpad.rendering.fonts import Font, load_font
from launchpad.rendering.frame import Frame

# Pixel values for 1-bit images: 1 = white background, 0 = black ink.
_WHITE = 1
_BLACK = 0

_MARGIN = 16
_HEADER_PX = 28
_BODY_PX = 22
_LINE_SPACING = 10


class PortraitRenderer(Renderer):
    """Stacks dashboard sections vertically for a tall display."""

    @property
    def orientation(self) -> Orientation:
        return Orientation.PORTRAIT

    def render(self, state: DashboardState, size: Size) -> Frame:
        img = Image.new("1", (size.width, size.height), _WHITE)
        draw = ImageDraw.Draw(img)
        header_font = load_font(_HEADER_PX)
        body_font = load_font(_BODY_PX)

        y_offset = _MARGIN
        trains = next(
            (s for s in state.visible_sections if s.section is Section.TRAINS),
            None,
        )
        if trains is not None:
            y_offset = self._draw_trains(draw, trains, header_font, body_font, y_offset)

        return Frame(size=size, buffer=img)

    @staticmethod
    def _draw_trains(
        draw: ImageDraw.ImageDraw,
        section: SectionState,
        header_font: Font,
        body_font: Font,
        y_offset: int,
    ) -> int:
        x = _MARGIN
        board = section.data

        station = board.station if board is not None else "Trains"
        draw.text((x, y_offset), station, font=header_font, fill=_BLACK)
        y_offset += _HEADER_PX + _LINE_SPACING

        if section.availability is Availability.UNAVAILABLE:
            draw.text((x, y_offset), "Trains unavailable", font=body_font, fill=_BLACK)
            return y_offset + _BODY_PX + _LINE_SPACING

        if section.availability is Availability.EMPTY or board is None or not board.departures:
            draw.text((x, y_offset), "No departures", font=body_font, fill=_BLACK)
            return y_offset + _BODY_PX + _LINE_SPACING

        for departure in board.departures:
            when = departure.expected if departure.expected is not None else departure.scheduled
            # A plain hyphen keeps the line legible with the default font, which
            # lacks an em-dash glyph. Swap to "\u2014" once a real TTF is bundled.
            line = f"{departure.destination} - {when:%H:%M}"
            if departure.status is DepartureStatus.DELAYED:
                line += " (delayed)"
            elif departure.status is DepartureStatus.CANCELLED:
                line += " (cancelled)"
            draw.text((x, y_offset), line, font=body_font, fill=_BLACK)
            y_offset += _BODY_PX + _LINE_SPACING

        return y_offset
