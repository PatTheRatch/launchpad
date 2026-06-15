"""Display interface.

Defines the minimal lifecycle a display must support. Implementations must
not assume anything about how the frame was produced.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from launchpad.models.geometry import Size
from launchpad.rendering.frame import Frame


class DisplayError(Exception):
    """Raised when a display cannot complete an operation."""


class Display(ABC):
    """A surface that can show rendered frames."""

    @property
    @abstractmethod
    def size(self) -> Size:
        """Native pixel dimensions of this display."""
        raise NotImplementedError

    @abstractmethod
    def show(self, frame: Frame) -> None:
        """Present a frame to the user."""
        raise NotImplementedError

    @abstractmethod
    def clear(self) -> None:
        """Blank the display."""
        raise NotImplementedError

    @abstractmethod
    def sleep(self) -> None:
        """Put the display into a low-power state (no-op for some displays)."""
        raise NotImplementedError
