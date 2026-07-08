"""E-ink display driver.

Drives a physical Waveshare 7.5" V2 e-paper panel on the Raspberry Pi via the
vendor ``waveshare_epd`` driver. Hardware-specific dependencies stay confined
to this module: the ``waveshare_epd`` package (and the GPIO/SPI libraries it
depends on) is only importable on a Pi, so the import is deferred until a
display is actually constructed. Importing this module on any other machine
must not raise.
"""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from PIL import Image

from launchpad.display.base import Display, DisplayError
from launchpad.models.geometry import Size
from launchpad.rendering.frame import Frame

_NATIVE_SIZE = Size(800, 480)


class EinkDisplay(Display):
    """Drives a Waveshare 7.5" V2 e-paper panel (800x480)."""

    def __init__(self) -> None:
        self._epd = self._create_driver()

    @staticmethod
    def _create_driver() -> Any:
        """Import the vendor driver and initialize the physical display."""
        try:
            from waveshare_epd import epd7in5_V2
        except ImportError as exc:
            raise DisplayError(
                "waveshare_epd library is not installed. It is required to "
                "drive the physical e-ink display and is only available on "
                "the Raspberry Pi (see Waveshare's e-Paper install docs)."
            ) from exc

        try:
            epd = epd7in5_V2.EPD()
            epd.init()
        except Exception as exc:
            raise DisplayError(f"Failed to initialize e-ink display: {exc}") from exc

        return epd

    @property
    def size(self) -> Size:
        """Native pixel dimensions of the 7.5" V2 panel."""
        return _NATIVE_SIZE

    def show(self, frame: Frame) -> None:
        """Present a frame on the physical display."""
        from PIL import Image

        image = frame.buffer
        if not isinstance(image, Image.Image):
            raise DisplayError("Frame.buffer must be a PIL.Image.Image to display.")
        try:
            buffer = self._epd.getbuffer(image)
            self._epd.display(buffer)
        except Exception as exc:
            raise DisplayError(f"Failed to show frame on e-ink display: {exc}") from exc

    def clear(self) -> None:
        """Blank the display to white."""
        try:
            if hasattr(self._epd, "Clear"):
                self._epd.Clear()
            else:
                from PIL import Image

                blank = Image.new("1", (_NATIVE_SIZE.width, _NATIVE_SIZE.height), 1)
                self.show(Frame(size=_NATIVE_SIZE, buffer=blank))
        except DisplayError:
            raise
        except Exception as exc:
            raise DisplayError(f"Failed to clear e-ink display: {exc}") from exc

    def sleep(self) -> None:
        """Put the display into deep sleep to reduce power draw."""
        try:
            self._epd.sleep()
        except Exception as exc:
            raise DisplayError(f"Failed to put e-ink display to sleep: {exc}") from exc
