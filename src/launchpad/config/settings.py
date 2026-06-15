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
class Settings:
    """Top-level application configuration."""

    display: DisplaySettings = field(default_factory=DisplaySettings)
    refresh: RefreshSettings = field(default_factory=RefreshSettings)
    features: FeatureFlags = field(default_factory=FeatureFlags)


def load_settings() -> Settings:
    """Load settings from the environment/config files. Not implemented yet."""
    raise NotImplementedError
