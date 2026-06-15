"""Tests for the portrait renderer."""

from __future__ import annotations

from PIL import Image

from launchpad.preview import PORTRAIT_SIZE, render_preview


def test_portrait_render_produces_1bit_frame_at_panel_size() -> None:
    frame = render_preview()

    assert isinstance(frame.buffer, Image.Image)
    assert frame.buffer.mode == "1"
    assert frame.buffer.size == (480, 800)
    assert frame.size == PORTRAIT_SIZE
