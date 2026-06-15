"""Landscape-orientation renderer (stub)."""

from __future__ import annotations

from launchpad.models.dashboard import DashboardState
from launchpad.models.geometry import Orientation, Size
from launchpad.rendering.base import Renderer
from launchpad.rendering.frame import Frame


class LandscapeRenderer(Renderer):
    """Arranges dashboard sections in columns for a wide display."""

    @property
    def orientation(self) -> Orientation:
        return Orientation.LANDSCAPE

    def render(self, state: DashboardState, size: Size) -> Frame:
        raise NotImplementedError
