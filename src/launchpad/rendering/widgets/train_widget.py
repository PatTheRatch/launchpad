"""Train departures widget (stub)."""

from __future__ import annotations

from typing import Any

from launchpad.models.geometry import Region
from launchpad.models.train import TrainBoard
from launchpad.rendering.widgets.base import Widget


class TrainWidget(Widget[TrainBoard]):
    def draw(self, data: TrainBoard, surface: Any, region: Region) -> None:
        raise NotImplementedError
