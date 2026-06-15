"""Widget interface.

A widget draws a single model of type ``T`` into a region of a drawing
surface. The surface type is left loose for now so the drawing backend stays
swappable.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

from launchpad.models.geometry import Region

T = TypeVar("T")


class Widget(ABC, Generic[T]):
    """Draws one dashboard section."""

    @abstractmethod
    def draw(self, data: T, surface: Any, region: Region) -> None:
        """Render ``data`` onto ``surface`` within ``region``."""
        raise NotImplementedError
