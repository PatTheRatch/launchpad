"""Unit tests for the black-and-white weather icons."""

from __future__ import annotations

import pytest
from PIL import Image, ImageDraw

from launchpad.models.weather import WeatherCondition
from launchpad.rendering.weather_icons import draw_weather_icon

_BLACK = 0
_ICON_X = 12
_ICON_Y = 12
_ICON_SIZE = 28
_CANVAS = 64

_DRAWN_CONDITIONS = [
    WeatherCondition.CLEAR,
    WeatherCondition.CLOUDY,
    WeatherCondition.RAIN,
    WeatherCondition.SNOW,
    WeatherCondition.FOG,
    WeatherCondition.STORM,
]


def _render(condition: WeatherCondition) -> Image.Image:
    img = Image.new("1", (_CANVAS, _CANVAS), 1)
    draw = ImageDraw.Draw(img)
    draw_weather_icon(draw, condition, _ICON_X, _ICON_Y, _ICON_SIZE)
    return img


def _black_pixels(img: Image.Image) -> list[tuple[int, int]]:
    pixels = img.load()
    assert pixels is not None
    return [
        (px, py)
        for py in range(img.height)
        for px in range(img.width)
        if pixels[px, py] == _BLACK
    ]


@pytest.mark.parametrize("condition", _DRAWN_CONDITIONS)
def test_drawn_conditions_produce_ink(condition: WeatherCondition) -> None:
    assert _black_pixels(_render(condition)), f"{condition} drew no ink"


def test_unknown_draws_nothing() -> None:
    assert _black_pixels(_render(WeatherCondition.UNKNOWN)) == []


@pytest.mark.parametrize("condition", _DRAWN_CONDITIONS)
def test_ink_stays_within_bounding_box(condition: WeatherCondition) -> None:
    for px, py in _black_pixels(_render(condition)):
        assert _ICON_X <= px < _ICON_X + _ICON_SIZE, f"{condition} x={px} out of box"
        assert _ICON_Y <= py < _ICON_Y + _ICON_SIZE, f"{condition} y={py} out of box"
