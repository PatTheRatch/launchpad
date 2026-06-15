"""Mock display.

Persists rendered frames as PNG files instead of driving real hardware, so the
full pipeline can be exercised on any machine.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from launchpad.display.base import Display, DisplayError
from launchpad.models.geometry import Size
from launchpad.rendering.frame import Frame


class MockDisplay(Display):
    """A development display that writes frames to disk as PNGs."""

    def __init__(self, size: Size, output_path: str | Path = "dashboard.png") -> None:
        self._size = size
        self._output_path = Path(output_path)

    @property
    def size(self) -> Size:
        return self._size

    def show(self, frame: Frame) -> None:
        image = frame.buffer
        if not isinstance(image, Image.Image):
            raise DisplayError("Frame.buffer must be a PIL.Image.Image to display.")
        self._output_path.parent.mkdir(parents=True, exist_ok=True)
        image.save(self._output_path, format="PNG")

    def clear(self) -> None:
        blank = Image.new("1", (self._size.width, self._size.height), 1)
        self.show(Frame(size=self._size, buffer=blank))

    def sleep(self) -> None:
        return None
