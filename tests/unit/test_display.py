"""Tests for the MockDisplay PNG writer."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from launchpad.display.base import DisplayError
from launchpad.display.mock_display import MockDisplay
from launchpad.models.geometry import Size
from launchpad.rendering.frame import Frame

SIZE = Size(width=480, height=800)


def _frame() -> Frame:
    return Frame(size=SIZE, buffer=Image.new("1", (SIZE.width, SIZE.height), 1))


def test_show_writes_non_empty_png(tmp_path: Path) -> None:
    out = tmp_path / "dashboard.png"
    MockDisplay(SIZE, out).show(_frame())

    assert out.exists()
    assert out.stat().st_size > 0
    with Image.open(out) as opened:
        assert opened.format == "PNG"


def test_show_creates_parent_directories(tmp_path: Path) -> None:
    out = tmp_path / "nested" / "dir" / "dashboard.png"
    MockDisplay(SIZE, out).show(_frame())

    assert out.exists()
    assert out.stat().st_size > 0


def test_show_rejects_non_image_buffer(tmp_path: Path) -> None:
    out = tmp_path / "dashboard.png"
    with pytest.raises(DisplayError):
        MockDisplay(SIZE, out).show(Frame(size=SIZE, buffer=b"not an image"))
