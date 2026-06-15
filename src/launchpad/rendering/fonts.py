"""Font loading for the renderer.

Loads bundled TrueType fonts from ``assets/fonts/`` (regular and bold) and
falls back to Pillow's built-in default font — scaled to the requested size —
if the files are missing, so rendering never crashes.
"""

from __future__ import annotations

from pathlib import Path

from PIL import ImageFont

#: Repo-level assets directory (src/launchpad/rendering/fonts.py -> repo root).
FONTS_DIR = Path(__file__).resolve().parents[3] / "assets" / "fonts"

#: Add these TrueType files manually (see assets/fonts/README.md). Until then
#: the loader falls back to ``ImageFont.load_default(size=...)``.
REGULAR_FONT_FILE = FONTS_DIR / "DejaVuSans.ttf"
BOLD_FONT_FILE = FONTS_DIR / "DejaVuSans-Bold.ttf"

Font = ImageFont.FreeTypeFont | ImageFont.ImageFont


def load_font(size: int, *, bold: bool = False) -> Font:
    """Load the bundled TTF at ``size`` px (bold optional), or the default font.

    The default-font fallback is requested *at the same size* so a larger
    ``size`` still produces visibly larger glyphs.
    """
    candidate = BOLD_FONT_FILE if bold else REGULAR_FONT_FILE
    try:
        return ImageFont.truetype(str(candidate), size)
    except OSError:
        return ImageFont.load_default(size=size)


def load_bold_font(size: int) -> Font:
    """Convenience wrapper for the bold weight."""
    return load_font(size, bold=True)
