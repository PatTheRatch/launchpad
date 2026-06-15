"""Local preview: build a mock dashboard and render it to a PNG.

The mock :class:`DashboardState` is built here in one place and reused by both
the entry point and the renderer test, so the previewed frame and the tested
frame are always identical. No network calls or real data sources are involved.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from launchpad.builder import DashboardInputs, DashboardStateBuilder
from launchpad.config.features import FeatureFlags
from launchpad.display.mock_display import MockDisplay
from launchpad.models.dashboard import DashboardState
from launchpad.models.geometry import Size
from launchpad.models.result import Result
from launchpad.models.train import DepartureStatus, TrainBoard, TrainDeparture
from launchpad.rendering.frame import Frame
from launchpad.rendering.portrait import PortraitRenderer

LONDON = ZoneInfo("Europe/London")

#: The real portrait panel specification (Waveshare 7.5" e-ink).
PORTRAIT_SIZE = Size(width=480, height=800)

#: Fixed "now" so previews land in MORNING and stay deterministic.
PREVIEW_NOW = datetime(2026, 6, 15, 8, 15, tzinfo=LONDON)

DEFAULT_OUTPUT = "dashboard.png"


def _at(hour: int, minute: int) -> datetime:
    return datetime(2026, 6, 15, hour, minute, tzinfo=LONDON)


def build_mock_train_board() -> TrainBoard:
    """Deterministic departures from Custom House for stable previews/tests."""
    return TrainBoard(
        station="Custom House",
        departures=(
            TrainDeparture(destination="Paddington", scheduled=_at(8, 22)),
            TrainDeparture(destination="Heathrow", scheduled=_at(8, 27)),
            TrainDeparture(
                destination="Reading",
                scheduled=_at(8, 30),
                expected=_at(8, 35),
                status=DepartureStatus.DELAYED,
            ),
        ),
        retrieved_at=PREVIEW_NOW,
    )


def build_mock_state() -> DashboardState:
    """Build a MORNING dashboard state via the real builder."""
    inputs = DashboardInputs(train=Result.present(build_mock_train_board()))
    return DashboardStateBuilder().build(PREVIEW_NOW, inputs, FeatureFlags())


def render_preview() -> Frame:
    """Render the mock state at the true portrait size."""
    return PortraitRenderer().render(build_mock_state(), PORTRAIT_SIZE)


def main() -> int:
    frame = render_preview()
    MockDisplay(PORTRAIT_SIZE, DEFAULT_OUTPUT).show(frame)
    print(f"Wrote {Path(DEFAULT_OUTPUT).resolve()}")
    return 0
