"""Font loading for the renderer.

Loads a bundled TrueType font from ``assets/fonts/`` and falls back to Pillow's
built-in default font if the file is missing, so rendering never crashes.
"""

from __future__ import annotations

from pathlib import Path

from PIL import ImageFont

#: Repo-level assets directory (src/launchpad/rendering/fonts.py -> repo root).
FONTS_DIR = Path(__file__).resolve().parents[3] / "assets" / "fonts"

#: TODO: add this TrueType file (see assets/fonts/README.md). Until then the
#: loader falls back to ``ImageFont.load_default()``.
DEFAULT_FONT_FILE = FONTS_DIR / "DejaVuSans.ttf"

Font = ImageFont.FreeTypeFont | ImageFont.ImageFont


def load_font(size: int, path: Path | None = None) -> Font:
    """Load a TrueType font at ``size`` px, or the default font if unavailable."""
    candidate = path if path is not None else DEFAULT_FONT_FILE
    try:
        return ImageFont.truetype(str(candidate), size)
    except OSError:
        return ImageFont.load_default()
