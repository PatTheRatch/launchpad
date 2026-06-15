"""Application settings.

These dataclasses describe *what* is configurable. Loading values (from env,
file, etc.) is deliberately left unimplemented so the source of configuration
stays swappable.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from launchpad.config.features import FeatureFlags
from launchpad.models.geometry import Orientation


@dataclass(frozen=True, slots=True)
class DisplaySettings:
    """How and where to render."""

    orientation: Orientation = Orientation.PORTRAIT
    width: int = 480
    height: int = 800
    driver: str = "mock"  # e.g. "mock" or "eink"


@dataclass(frozen=True, slots=True)
class RefreshSettings:
    """How often to refresh data and redraw."""

    refresh_seconds: int = 300


@dataclass(frozen=True, slots=True)
class StationConfig:
    """A single TfL stop point to fetch arrivals for.

    ``stop_point_id`` may need manual verification/correction against the TfL
    StopPoint API; keep it easy to change here.
    """

    line_id: str
    stop_point_id: str
    display_name: str


#: Default station for the current single-station build (Elizabeth line).
CUSTOM_HOUSE = StationConfig(
    line_id="elizabeth",
    stop_point_id="910GCUSTMHS",
    display_name="Custom House",
)


@dataclass(frozen=True, slots=True)
class Settings:
    """Top-level application configuration."""

    display: DisplaySettings = field(default_factory=DisplaySettings)
    refresh: RefreshSettings = field(default_factory=RefreshSettings)
    features: FeatureFlags = field(default_factory=FeatureFlags)


def load_settings() -> Settings:
    """Load settings from the environment/config files. Not implemented yet."""
    raise NotImplementedError
