"""Feature flags.

Experimental features must be opt-in and individually toggleable so that a
failure in one of them can never affect the core dashboard. Each flag here
maps to an experimental service that the composition root may or may not
register.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FeatureFlags:
    """Toggles for non-core, experimental features.

    Core features (train, weather, calendar) have no flag: they are always on.
    """

    nba: bool = False
    fantasy_basketball: bool = False
    baby_tracking: bool = False
    world_cup: bool = False
