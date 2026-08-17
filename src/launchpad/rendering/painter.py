"""Drawing primitives shared by every portrait layout.

:class:`Painter` is a top-down cursor bounded by a :class:`Region`, so the
same primitives serve a full-page stack, a fixed slot, or one tile in a grid.
It never draws past its region, which is what keeps a verbose section from
spilling into its neighbours.

Layouts differ in *arrangement* only: what each section says lives in
:mod:`launchpad.rendering.summaries`, and the pixel work lives here.
"""

from __future__ import annotations

from dataclasses import dataclass

from PIL import ImageDraw

from launchpad.models.geometry import Region
from launchpad.rendering.fonts import Font, load_font

# Pixel values for 1-bit images: 1 = white background, 0 = black ink.
WHITE = 1
BLACK = 0

# Typographic scale (px).
JUMBO_PX = 82  # the one number a mode exists to answer
DISPLAY_PX = 52  # secondary hero / tile values
TITLE_PX = 30
CARD_PX = 25
PRIMARY_PX = 23
META_PX = 18
SECONDARY_PX = 17
LABEL_PX = 14  # uppercase eyebrow labels

# Spacing.
MARGIN_X = 18
MARGIN_TOP = 14
LEADING = 7
DIVIDER_PAD = 9

# Train row columns: the time right-aligns to a fixed column so every
# departure time lines up vertically, with the status marker in a reserved
# right-side area beyond it.
TRAIN_STATUS_AREA_W = 150
TRAIN_COL_GAP = 12

#: Vertical gap between groups within a section (smaller than a divider,
#: which separates whole sections).
GROUP_GAP = 8

#: Most of a ledger row's width the label may claim when label and value
#: compete for space. The value takes the truncation instead of the label.
LABEL_MAX_SHARE = 0.5

ELLIPSIS = "..."


@dataclass(frozen=True, slots=True)
class Fonts:
    """One loaded font per role in the typographic scale."""

    title: Font
    primary: Font
    secondary: Font
    meta: Font
    label: Font
    card: Font
    display: Font
    jumbo: Font


def load_fonts() -> Fonts:
    """Load every font tier once per render."""
    return Fonts(
        title=load_font(TITLE_PX, bold=True),
        primary=load_font(PRIMARY_PX),
        secondary=load_font(SECONDARY_PX),
        meta=load_font(META_PX, bold=True),
        label=load_font(LABEL_PX, bold=True),
        card=load_font(CARD_PX, bold=True),
        display=load_font(DISPLAY_PX, bold=True),
        jumbo=load_font(JUMBO_PX, bold=True),
    )


def text_width(draw: ImageDraw.ImageDraw, text: str, font: Font) -> float:
    return draw.textlength(text, font=font)


def truncate(draw: ImageDraw.ImageDraw, text: str, font: Font, max_width: float) -> str:
    """Trim ``text`` from the right and append an ellipsis to fit ``max_width``."""
    if text_width(draw, text, font) <= max_width:
        return text
    if text_width(draw, ELLIPSIS, font) > max_width:
        return ""
    trimmed = text
    while trimmed and text_width(draw, trimmed + ELLIPSIS, font) > max_width:
        trimmed = trimmed[:-1]
    return (trimmed + ELLIPSIS) if trimmed else ELLIPSIS


class Painter:
    """A top-down cursor over one region; never draws past its bounds."""

    def __init__(
        self,
        draw: ImageDraw.ImageDraw,
        fonts: Fonts,
        region: Region,
        *,
        top_margin: int = MARGIN_TOP,
        margin_x: int = MARGIN_X,
    ) -> None:
        self.draw = draw
        self.fonts = fonts
        self.region = region
        self.margin_x = margin_x
        self.left = region.x + margin_x
        self.right = region.x + region.width - margin_x
        self.bottom = region.y + region.height
        self.y = region.y + top_margin

    # -- geometry ---------------------------------------------------------- #

    @property
    def width(self) -> int:
        """Full region width (including margins), for right-edge maths."""
        return self.region.width

    @property
    def height(self) -> int:
        """Bottom edge, in absolute pixels."""
        return self.bottom

    @property
    def content_width(self) -> float:
        return self.right - self.left

    @property
    def exhausted(self) -> bool:
        return self.y >= self.bottom

    @property
    def remaining(self) -> int:
        return max(0, self.bottom - self.y)

    def line_height(self, font: Font) -> int:
        bbox = self.draw.textbbox((0, 0), "Ahgyltpq", font=font)
        return int(bbox[3] - bbox[1]) + LEADING

    def sub(self, region: Region, *, top_margin: int = 0, margin_x: int = 0) -> "Painter":
        """A child painter bounded by ``region`` (for tiles and slots)."""
        return Painter(
            self.draw, self.fonts, region, top_margin=top_margin, margin_x=margin_x
        )

    # -- text -------------------------------------------------------------- #

    def line(self, text: str, font: Font, *, indent: int = 0, reserve_right: int = 0) -> None:
        max_width = self.content_width - indent - reserve_right
        content = truncate(self.draw, text, font, max_width)
        height = self.line_height(font)
        if self.y + height <= self.bottom:
            self.draw.text((self.left + indent, self.y), content, font=font, fill=BLACK)
        self.y += height

    def row(self, left_text: str, right_text: str, font: Font, *, right_font: Font | None = None) -> None:
        """A ledger row: label on the left, value right-aligned on the same line.

        The left text is truncated so it can never collide with the value.
        """
        right_font = right_font or font
        height = self.line_height(font)

        # The label identifies the row, so it is never sacrificed to fit the
        # value: when both cannot fit, the label keeps up to LABEL_MAX_SHARE
        # of the width and the value absorbs the truncation.
        budget = self.content_width - TRAIN_COL_GAP
        left_natural = text_width(self.draw, left_text, font)
        right_natural = text_width(self.draw, right_text, right_font)
        if left_natural + right_natural > budget:
            left_max = min(left_natural, budget * LABEL_MAX_SHARE)
        else:
            left_max = left_natural
        left_content = truncate(self.draw, left_text, font, left_max)
        left_width = text_width(self.draw, left_content, font)
        right_text = truncate(self.draw, right_text, right_font, budget - left_width)
        right_width = text_width(self.draw, right_text, right_font)

        if self.y + height <= self.bottom:
            self.draw.text((self.left, self.y), left_content, font=font, fill=BLACK)
            baseline_gap = max(0, height - LEADING - self.line_height(right_font) + LEADING)
            self.draw.text(
                (self.right - right_width, self.y + baseline_gap // 2),
                right_text,
                font=right_font,
                fill=BLACK,
            )
        self.y += height

    def train_row(self, destination: str, time_text: str, status_text: str) -> None:
        """Draw a departure as fixed columns: destination | time | status.

        The time right-aligns to a constant column so times stack vertically;
        only the destination is truncated, keeping the time and status visible.
        """
        font = self.fonts.primary
        height = self.line_height(font)
        draw_this_row = self.y + height <= self.bottom

        time_right_x = self.right - TRAIN_STATUS_AREA_W
        time_x = time_right_x - text_width(self.draw, time_text, font)
        destination_max = time_x - TRAIN_COL_GAP - self.left
        destination_text = truncate(self.draw, destination, font, destination_max)

        if draw_this_row:
            self.draw.text((self.left, self.y), destination_text, font=font, fill=BLACK)
            self.draw.text((time_x, self.y), time_text, font=font, fill=BLACK)
            if status_text:
                status_x = time_right_x + TRAIN_COL_GAP
                status = truncate(self.draw, status_text, font, self.right - status_x)
                self.draw.text((status_x, self.y), status, font=font, fill=BLACK)
        self.y += height

    def title_with_status(self, title: str, status: str | None) -> None:
        """Draw a section title, with an optional status right-aligned beside it.

        The title uses the title font; the status uses the smaller secondary
        font, vertically centered on the title. The title is truncated so it
        never overlaps the status.
        """
        title_font = self.fonts.title
        height = self.line_height(title_font)
        if not status:
            self.line(title, title_font)
            return

        status_font = self.fonts.secondary
        status_width = text_width(self.draw, status, status_font)
        title_max = self.content_width - status_width - TRAIN_COL_GAP
        title_text = truncate(self.draw, title, title_font, title_max)
        if self.y + height <= self.bottom:
            self.draw.text((self.left, self.y), title_text, font=title_font, fill=BLACK)
            status_h = self.draw.textbbox((0, 0), "Ag", font=status_font)[3]
            status_y = self.y + max(0, (height - LEADING - status_h) // 2)
            self.draw.text(
                (self.right - status_width, status_y), status, font=status_font, fill=BLACK
            )
        self.y += height

    def header_row(self, left: str, right: str, font: Font) -> None:
        height = self.line_height(font)
        if self.y + height <= self.bottom:
            self.draw.text((self.left, self.y), left, font=font, fill=BLACK)
            right_width = text_width(self.draw, right, font)
            self.draw.text((self.right - right_width, self.y), right, font=font, fill=BLACK)
        self.y += height

    def stat(self, label: str, value: str, caption: str, *, value_font: Font | None = None) -> None:
        """An eyebrow label, one large value, and a caption beneath it.

        The value font steps down automatically when the text is too wide for
        the region, so a long value shrinks instead of being cut off.
        """
        if label:
            self.line(label.upper(), self.fonts.label)
        font = value_font or self.fonts.display
        for candidate in (font, self.fonts.display, self.fonts.title, self.fonts.primary):
            if text_width(self.draw, value, candidate) <= self.content_width:
                font = candidate
                break
        self.line(value, font)
        if caption:
            self.line(caption, self.fonts.secondary)

    # -- rules and space --------------------------------------------------- #

    def gap(self, px: int) -> None:
        self.y += px

    def divider(self) -> None:
        self.y += DIVIDER_PAD
        if self.y <= self.bottom:
            self.draw.line([(self.left, self.y), (self.right, self.y)], fill=BLACK, width=1)
        self.y += DIVIDER_PAD

    def box(self, region: Region) -> None:
        """Outline a rectangle (tile borders)."""
        self.draw.rectangle(
            [(region.x, region.y), (region.x + region.width - 1, region.y + region.height - 1)],
            outline=BLACK,
            width=1,
        )
