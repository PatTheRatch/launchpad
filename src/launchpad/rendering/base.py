"""Renderer interface.

A renderer maps a dashboard state to a frame for a given surface size. Concrete
renderers implement a specific orientation/layout but share this contract so
they are interchangeable.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from launchpad.models.dashboard import DashboardState
from launchpad.models.geometry import Orientation, Size
from launchpad.rendering.frame import Frame


class Renderer(ABC):
    """Produces a :class:`Frame` from a :class:`DashboardState`."""

    @property
    @abstractmethod
    def orientation(self) -> Orientation:
        """The orientation this renderer lays out for."""
        raise NotImplementedError

    @abstractmethod
    def render(self, state: DashboardState, size: Size) -> Frame:
        """Lay out and draw the dashboard for the given surface size."""
        raise NotImplementedError
