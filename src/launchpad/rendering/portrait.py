"""Portrait-orientation renderer (stub)."""

from __future__ import annotations

from launchpad.models.dashboard import DashboardState
from launchpad.models.geometry import Orientation, Size
from launchpad.rendering.base import Renderer
from launchpad.rendering.frame import Frame


class PortraitRenderer(Renderer):
    """Stacks dashboard sections vertically for a tall display."""

    @property
    def orientation(self) -> Orientation:
        return Orientation.PORTRAIT

    def render(self, state: DashboardState, size: Size) -> Frame:
        raise NotImplementedError
