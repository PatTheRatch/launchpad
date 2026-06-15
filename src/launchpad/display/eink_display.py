"""E-ink display (stub).

Intended to drive a physical e-ink panel on the Raspberry Pi via a vendor
driver. Hardware-specific dependencies stay confined to this module.
"""

from __future__ import annotations

from launchpad.display.base import Display
from launchpad.models.geometry import Size
from launchpad.rendering.frame import Frame


class EinkDisplay(Display):
    @property
    def size(self) -> Size:
        raise NotImplementedError

    def show(self, frame: Frame) -> None:
        raise NotImplementedError

    def clear(self) -> None:
        raise NotImplementedError

    def sleep(self) -> None:
        raise NotImplementedError
