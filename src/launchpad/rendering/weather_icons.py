"""Black-and-white weather pictograms for the 1-bit e-ink dashboard.

Newspaper-style glyphs drawn as bold filled silhouettes with thick strokes, so
they read cleanly at ~22-28 px on a "1"-mode image with no anti-aliasing. All
ink is black (``fill=0``) on a white (``1``) background.

The only public entry point is :func:`draw_weather_icon`, which dispatches to a
per-condition helper. :class:`~launchpad.models.weather.WeatherCondition.UNKNOWN`
draws nothing (no fallback glyph).

Every glyph is kept inside an inner box inset by the stroke width, so even thick
strokes never cross the requested ``size`` bounding box.
"""

from __future__ import annotations

import math

from PIL import ImageDraw

from launchpad.models.weather import WeatherCondition

_BLACK = 0


def _stroke(size: int) -> int:
    return max(2, round(size * 0.10))


def _inner(x: int, y: int, size: int) -> tuple[float, float, float, float]:
    """Inset box (left, top, w, h) keeping strokes inside the size bounds."""
    m = _stroke(size)
    return float(x + m), float(y + m), float(size - 2 * m), float(size - 2 * m)


def _cloud(
    draw: ImageDraw.ImageDraw, left: float, top: float, w: float, h: float
) -> None:
    """A filled, blobby cloud silhouette confined to (left, top, w, h)."""
    draw.rounded_rectangle(
        [left, top + 0.55 * h, left + w, top + h], radius=0.22 * h, fill=_BLACK
    )
    for cx_frac, cy_frac, r_frac in (
        (0.28, 0.50, 0.26),
        (0.55, 0.38, 0.34),
        (0.76, 0.52, 0.24),
    ):
        cx = left + cx_frac * w
        cy = top + cy_frac * h
        r = r_frac * h
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=_BLACK)


def _draw_clear(draw: ImageDraw.ImageDraw, x: int, y: int, size: int) -> None:
    left, top, w, h = _inner(x, y, size)
    span = min(w, h)
    cx, cy = left + w / 2, top + h / 2
    r = span * 0.22
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=_BLACK)
    ray_in = r + span * 0.08
    ray_out = span * 0.50
    width = _stroke(size)
    for i in range(8):
        angle = math.pi / 4 * i
        cos_a, sin_a = math.cos(angle), math.sin(angle)
        draw.line(
            [
                (cx + cos_a * ray_in, cy + sin_a * ray_in),
                (cx + cos_a * ray_out, cy + sin_a * ray_out),
            ],
            fill=_BLACK,
            width=width,
        )


def _draw_cloudy(draw: ImageDraw.ImageDraw, x: int, y: int, size: int) -> None:
    left, top, w, h = _inner(x, y, size)
    _cloud(draw, left, top + 0.15 * h, w, 0.70 * h)


def _draw_rain(draw: ImageDraw.ImageDraw, x: int, y: int, size: int) -> None:
    left, top, w, h = _inner(x, y, size)
    _cloud(draw, left, top, w, 0.58 * h)
    width = _stroke(size)
    drop_top = top + 0.66 * h
    for fx in (0.30, 0.52, 0.74):
        sx = left + fx * w
        draw.line(
            [(sx, drop_top), (sx - 0.10 * w, drop_top + 0.30 * h)],
            fill=_BLACK,
            width=width,
        )


def _draw_snow(draw: ImageDraw.ImageDraw, x: int, y: int, size: int) -> None:
    left, top, w, h = _inner(x, y, size)
    _cloud(draw, left, top, w, 0.58 * h)
    width = _stroke(size)
    mark_y = top + 0.80 * h
    r = 0.07 * w
    for fx in (0.30, 0.52, 0.74):
        cx = left + fx * w
        draw.line([(cx - r, mark_y), (cx + r, mark_y)], fill=_BLACK, width=width)
        draw.line([(cx, mark_y - r), (cx, mark_y + r)], fill=_BLACK, width=width)


def _draw_fog(draw: ImageDraw.ImageDraw, x: int, y: int, size: int) -> None:
    left, top, w, h = _inner(x, y, size)
    _cloud(draw, left, top, w, 0.55 * h)
    width = _stroke(size)
    for i, inset in enumerate((0.0, 0.14, 0.0)):
        yy = top + 0.68 * h + i * 0.14 * h
        draw.line(
            [(left + 0.12 * w + inset * w, yy), (left + 0.88 * w - inset * w, yy)],
            fill=_BLACK,
            width=width,
        )


def _draw_storm(draw: ImageDraw.ImageDraw, x: int, y: int, size: int) -> None:
    left, top, w, h = _inner(x, y, size)
    _cloud(draw, left, top, w, 0.55 * h)
    points = [
        (left + 0.54 * w, top + 0.58 * h),
        (left + 0.40 * w, top + 0.80 * h),
        (left + 0.50 * w, top + 0.80 * h),
        (left + 0.42 * w, top + 1.00 * h),
        (left + 0.66 * w, top + 0.72 * h),
        (left + 0.54 * w, top + 0.72 * h),
        (left + 0.62 * w, top + 0.58 * h),
    ]
    draw.polygon(points, fill=_BLACK)


_DISPATCH = {
    WeatherCondition.CLEAR: _draw_clear,
    WeatherCondition.CLOUDY: _draw_cloudy,
    WeatherCondition.RAIN: _draw_rain,
    WeatherCondition.SNOW: _draw_snow,
    WeatherCondition.FOG: _draw_fog,
    WeatherCondition.STORM: _draw_storm,
}


def draw_weather_icon(
    draw: ImageDraw.ImageDraw,
    condition: WeatherCondition,
    x: int,
    y: int,
    size: int,
) -> None:
    """Draw a weather pictogram in the box at ``(x, y)`` of ``size`` px.

    ``UNKNOWN`` draws nothing. ``(x, y)`` is the icon's top-left corner.
    """
    handler = _DISPATCH.get(condition)
    if handler is not None:
        handler(draw, x, y, size)
