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

    ``direction`` restricts arrivals to a single travel direction (the TfL
    ``direction`` value, e.g. ``"inbound"``/``"outbound"``). When the home
    dashboard only ever uses one direction, this drops the return-trip noise.
    ``None`` keeps both directions. Trains whose direction TfL leaves blank are
    kept regardless, so a quirky empty value never hides a wanted train.
    """

    line_id: str
    stop_point_id: str
    display_name: str
    direction: str | None = None


#: The three commute stations from the project vision. Each is pinned to the
#: "into the city" direction, since that is the only way taken from home.
CUSTOM_HOUSE = StationConfig(
    line_id="elizabeth",
    stop_point_id="910GCUSTMHS",
    display_name="Custom House",
    direction="outbound",  # towards Paddington (not Abbey Wood)
)
ROYAL_VICTORIA = StationConfig(
    line_id="dlr",
    stop_point_id="940GZZDLRVC",
    display_name="Royal Victoria",
    direction="inbound",  # towards Canning Town / Bank (not Beckton)
)
CANNING_TOWN = StationConfig(
    line_id="jubilee",
    stop_point_id="940GZZLUCGT",
    display_name="Canning Town",
    direction="inbound",  # westbound into the city (not Stratford)
)

#: Stations shown on the train board, in display order.
DEFAULT_STATIONS: tuple[StationConfig, ...] = (CUSTOM_HOUSE, ROYAL_VICTORIA, CANNING_TOWN)


@dataclass(frozen=True, slots=True)
class LocationConfig:
    """A geographic point to fetch weather for."""

    latitude: float
    longitude: float
    display_name: str
    timezone: str = "Europe/London"


#: Default weather location for the current single-location build.
LONDON_WEATHER = LocationConfig(
    latitude=51.5074,
    longitude=-0.1278,
    display_name="London",
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
