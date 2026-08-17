"""Alternative portrait arrangements of the same dashboard content.

Each renderer here answers a different question about the panel:

* :class:`CompactRenderer` — everything visible at once, one row per section.
* :class:`HeroRenderer` — one giant number per mode, detail demoted below it.
* :class:`SlotsRenderer` — fixed zones, so a section never moves address.
* :class:`CardsRenderer` — lists full width, single stats as tiles.
* :class:`TimelineRenderer` — the day itself, plotted on one vertical axis.

They share the drawing primitives in :mod:`~launchpad.rendering.painter` and
the section copy in :mod:`~launchpad.rendering.summaries`, so a change to what
a section *says* lands in every layout at once. Only arrangement lives here.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw

from launchpad.models.dashboard import DashboardState, Section, SectionState
from launchpad.models.geometry import Orientation, Region, Size
from launchpad.rendering.base import Renderer
from launchpad.rendering.frame import Frame
from launchpad.rendering.painter import (
    BLACK,
    GROUP_GAP,
    MARGIN_X,
    WHITE,
    Fonts,
    Painter,
    load_fonts,
    text_width,
    truncate,
)
from launchpad.rendering.summaries import (
    TimelineEntry,
    detail_lines,
    hero_for,
    one_line,
    stat_for,
    timeline_entries,
    title_for,
)

LONDON = ZoneInfo("Europe/London")

#: Sections rendered as multi-row lists rather than a single summary line.
_LIST_SECTIONS = frozenset({Section.TRAINS, Section.CALENDAR, Section.CALENDAR_TOMORROW})

#: Height reserved at the bottom for the freshness footer.
_FOOTER_H = 26


class _PortraitLayout(Renderer):
    """Shared scaffolding: header, footer, and a body region between them."""

    @property
    def orientation(self) -> Orientation:
        return Orientation.PORTRAIT

    def render(self, state: DashboardState, size: Size) -> Frame:
        image = Image.new("1", (size.width, size.height), WHITE)
        draw = ImageDraw.Draw(image)
        fonts = load_fonts()

        painter = Painter(draw, fonts, Region(0, 0, size.width, size.height - _FOOTER_H))
        painter.header_row(
            f"{state.generated_at:%A %d %B}", f"{state.generated_at:%H:%M}", fonts.meta
        )
        painter.divider()

        self.draw_body(painter, state)
        self._draw_footer(draw, fonts, state, size)
        return Frame(size=size, buffer=image)

    def draw_body(self, painter: Painter, state: DashboardState) -> None:
        """Draw everything below the header. Implemented per layout."""
        raise NotImplementedError

    @staticmethod
    def _draw_footer(
        draw: ImageDraw.ImageDraw, fonts: Fonts, state: DashboardState, size: Size
    ) -> None:
        # On a read-only appliance, staleness is the one failure nobody can
        # otherwise see — so every alternative layout states it outright.
        unavailable = [
            title_for(section)
            for section in state.visible_sections
            if section.data is None
        ]
        text = f"refreshed {state.generated_at:%H:%M}"
        if unavailable:
            text += " · no data: " + ", ".join(unavailable)
        content = truncate(draw, text, fonts.secondary, size.width - 2 * MARGIN_X)
        draw.text((MARGIN_X, size.height - _FOOTER_H + 4), content, font=fonts.secondary, fill=BLACK)


class CompactRenderer(_PortraitLayout):
    """A · Compact stack: one ledger row per section, everything visible."""

    def draw_body(self, painter: Painter, state: DashboardState) -> None:
        now = state.generated_at
        for index, section in enumerate(state.visible_sections):
            if painter.exhausted:
                break
            if index > 0:
                painter.divider()
            if section.section is Section.TRAINS:
                self._draw_train_list(painter, section)
            else:
                painter.row(
                    title_for(section),
                    one_line(section, now),
                    painter.fonts.title,
                    right_font=painter.fonts.secondary,
                )

    @staticmethod
    def _draw_train_list(painter: Painter, section: SectionState) -> None:
        # Trains keep their multi-row form: they are the one true list, and a
        # single "next train" line would hide the fallback options.
        if section.data is None:
            painter.row(
                "Trains", "unavailable", painter.fonts.title, right_font=painter.fonts.secondary
            )
            return
        for index, station in enumerate(section.data):
            if painter.exhausted:
                break
            if index > 0:
                painter.gap(GROUP_GAP)
            painter.line(station.station, painter.fonts.title)
            if station.board is None or not station.board.departures:
                painter.line("No departures", painter.fonts.secondary)
                continue
            for departure in station.board.departures[:3]:
                when = departure.expected or departure.scheduled
                painter.row(
                    departure.destination,
                    f"{when.astimezone(LONDON):%H:%M}",
                    painter.fonts.primary,
                )


class HeroRenderer(_PortraitLayout):
    """B · Hero + ledger: the one number this mode exists to answer."""

    def draw_body(self, painter: Painter, state: DashboardState) -> None:
        now = state.generated_at
        hero = hero_for(state, now)
        hero_section: Section | None = None
        if hero is not None:
            hero_section, stat = hero
            painter.stat(stat.label, stat.value, stat.caption, value_font=painter.fonts.jumbo)
            painter.divider()

        for section in state.visible_sections:
            if painter.exhausted:
                break
            if section.section is hero_section:
                continue
            painter.row(
                title_for(section),
                one_line(section, now),
                painter.fonts.title,
                right_font=painter.fonts.secondary,
            )
            painter.gap(GROUP_GAP)


class SlotsRenderer(_PortraitLayout):
    """C · Fixed slots: the feed strip never changes address."""

    #: Fractions of the body height given to each zone, top to bottom.
    _FEED_FRACTION = 0.16
    _WEATHER_FRACTION = 0.16

    def draw_body(self, painter: Painter, state: DashboardState) -> None:
        now = state.generated_at
        top = painter.y
        available = painter.bottom - top
        feed_h = int(available * self._FEED_FRACTION)
        weather_h = int(available * self._WEATHER_FRACTION)
        middle_h = available - feed_h - weather_h

        self._draw_pinned(
            painter, Region(0, top, painter.width, feed_h), state.get(Section.BABY), now
        )
        self._draw_rotating(
            painter, Region(0, top + feed_h, painter.width, middle_h), state, now
        )
        self._draw_pinned(
            painter,
            Region(0, top + feed_h + middle_h, painter.width, weather_h),
            state.get(Section.WEATHER),
            now,
        )

    def _draw_pinned(
        self, painter: Painter, region: Region, section: SectionState | None, now: datetime
    ) -> None:
        """One fixed strip. Clipped to its own budget, so it never displaces
        the zones below it — the point of the layout."""
        slot = painter.sub(region, margin_x=MARGIN_X)
        if section is None:
            slot.line("—", slot.fonts.secondary)
        else:
            slot.row(
                title_for(section),
                one_line(section, now),
                slot.fonts.title,
                right_font=slot.fonts.secondary,
            )
        painter.draw.line(
            [(MARGIN_X, region.y + region.height - 1),
             (painter.width - MARGIN_X, region.y + region.height - 1)],
            fill=BLACK,
            width=1,
        )

    @staticmethod
    def _draw_rotating(
        painter: Painter, region: Region, state: DashboardState, now: datetime
    ) -> None:
        slot = painter.sub(region, top_margin=GROUP_GAP, margin_x=MARGIN_X)
        rotating = [
            section
            for section in state.visible_sections
            if section.section not in (Section.BABY, Section.WEATHER)
        ]
        for index, section in enumerate(rotating):
            if slot.exhausted:
                break
            if index > 0:
                slot.gap(GROUP_GAP)
            slot.line(title_for(section), slot.fonts.title)
            for line in detail_lines(section, now)[:4]:
                if slot.exhausted:
                    break
                slot.line(line, slot.fonts.primary)


class CardsRenderer(_PortraitLayout):
    """D · Card grid: lists full width, single stats as 2-up tiles."""

    _TILE_GAP = 10
    _TILE_H = 96

    def draw_body(self, painter: Painter, state: DashboardState) -> None:
        now = state.generated_at
        lists = [s for s in state.visible_sections if s.section in _LIST_SECTIONS]
        tiles = [s for s in state.visible_sections if s.section not in _LIST_SECTIONS]

        for index, section in enumerate(lists):
            if painter.exhausted:
                break
            if index > 0:
                painter.divider()
            painter.line(title_for(section), painter.fonts.title)
            for line in detail_lines(section, now)[:4]:
                if painter.exhausted:
                    break
                painter.line(line, painter.fonts.primary)

        if tiles and not painter.exhausted:
            painter.gap(GROUP_GAP)
        self._draw_tiles(painter, tiles, now)

    def _draw_tiles(self, painter: Painter, sections: list[SectionState], now: datetime) -> None:
        usable = painter.width - 2 * MARGIN_X
        tile_w = (usable - self._TILE_GAP) // 2
        for index, section in enumerate(sections):
            column, row = index % 2, index // 2
            y = painter.y + row * (self._TILE_H + self._TILE_GAP)
            if y + self._TILE_H > painter.bottom:
                break
            region = Region(
                MARGIN_X + column * (tile_w + self._TILE_GAP), y, tile_w, self._TILE_H
            )
            painter.box(region)
            stat = stat_for(section, now)
            tile = painter.sub(
                Region(region.x + 8, region.y + 6, region.width - 16, region.height - 12)
            )
            tile.line(stat.label, tile.fonts.label)
            tile.line(stat.value, tile.fonts.card)
            tile.line(stat.caption, tile.fonts.secondary)


class TimelineRenderer(_PortraitLayout):
    """E · Day strip: calendar, trains, and feeds on one vertical time axis."""

    _AXIS_X = 62  # x of the vertical rule; hour labels sit to its left
    _MIN_SPAN = timedelta(hours=6)
    _MIN_LABEL_GAP = 22

    def draw_body(self, painter: Painter, state: DashboardState) -> None:
        now = state.generated_at
        entries = timeline_entries(state, now)

        baby = state.get(Section.BABY)
        if baby is not None:
            painter.row(
                title_for(baby),
                one_line(baby, now),
                painter.fonts.title,
                right_font=painter.fonts.secondary,
            )
            painter.divider()

        start, end = self._window(entries, now)
        top, bottom = painter.y + 6, painter.bottom - 6
        if bottom <= top:
            return
        span = (end - start).total_seconds()

        def y_for(when: datetime) -> int:
            fraction = (when - start).total_seconds() / span
            return int(top + fraction * (bottom - top))

        axis_x = painter.left + self._AXIS_X
        painter.draw.line([(axis_x, top), (axis_x, bottom)], fill=BLACK, width=1)
        self._draw_hour_ticks(painter, start, end, axis_x, y_for)

        # The now-bar goes down first so entry labels near it stay readable
        # on top rather than being painted over.
        self._draw_now(painter, axis_x, y_for(now), top, bottom)

        last_label_y = -self._MIN_LABEL_GAP
        for entry in entries:
            y = max(y_for(entry.when), last_label_y + self._MIN_LABEL_GAP)
            if y > bottom - 12:
                break
            self._draw_entry(painter, entry, axis_x, y)
            last_label_y = y

    def _window(
        self, entries: tuple[TimelineEntry, ...], now: datetime
    ) -> tuple[datetime, datetime]:
        """Frame the axis around today's entries, always including ``now``."""
        moments = [entry.when for entry in entries] + [now]
        start, end = min(moments), max(moments)
        padding = timedelta(minutes=30)
        start, end = start - padding, end + padding
        if end - start < self._MIN_SPAN:
            end = start + self._MIN_SPAN
        return start, end

    @staticmethod
    def _draw_hour_ticks(
        painter: Painter,
        start: datetime,
        end: datetime,
        axis_x: int,
        y_for: Callable[[datetime], int],
    ) -> None:
        tick = start.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        while tick < end:
            y = y_for(tick)
            painter.draw.line([(axis_x - 4, y), (axis_x + 4, y)], fill=BLACK, width=1)
            painter.draw.text(
                (painter.left, y - 8), f"{tick:%H:%M}", font=painter.fonts.secondary, fill=BLACK
            )
            tick += timedelta(hours=1)

    @staticmethod
    def _draw_entry(painter: Painter, entry: TimelineEntry, axis_x: int, y: int) -> None:
        # A feed is a filled dot, anything else hollow — the feed rhythm is
        # what this layout exists to make visible.
        filled = entry.marker == "feed"
        painter.draw.ellipse(
            [(axis_x - 4, y - 4), (axis_x + 4, y + 4)],
            outline=BLACK,
            fill=BLACK if filled else WHITE,
            width=1,
        )
        label = f"{entry.when:%H:%M}  {entry.label}"
        max_width = painter.right - (axis_x + 12)
        painter.draw.text(
            (axis_x + 12, y - 9),
            truncate(painter.draw, label, painter.fonts.secondary, max_width),
            font=painter.fonts.secondary,
            fill=BLACK,
        )

    @staticmethod
    def _draw_now(painter: Painter, axis_x: int, y: int, top: int, bottom: int) -> None:
        y = min(max(y, top), bottom)
        painter.draw.line([(painter.left, y), (painter.right, y)], fill=BLACK, width=2)
        label = "NOW"
        width = text_width(painter.draw, label, painter.fonts.label)
        painter.draw.rectangle(
            [(painter.right - width - 6, y - 9), (painter.right, y + 9)], fill=BLACK
        )
        painter.draw.text(
            (painter.right - width - 3, y - 7), label, font=painter.fonts.label, fill=WHITE
        )
