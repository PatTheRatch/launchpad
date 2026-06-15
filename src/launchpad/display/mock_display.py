"""Mock display (stub).

Intended for development on any machine: it would persist or preview frames
(e.g. write a PNG) instead of driving real hardware.
"""

from __future__ import annotations

from launchpad.display.base import Display
from launchpad.models.geometry import Size
from launchpad.rendering.frame import Frame


class MockDisplay(Display):
    @property
    def size(self) -> Size:
        raise NotImplementedError

    def show(self, frame: Frame) -> None:
        raise NotImplementedError

    def clear(self) -> None:
        raise NotImplementedError

    def sleep(self) -> None:
        raise NotImplementedError
