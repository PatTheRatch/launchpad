"""Shared geometry/layout primitives used across config, display, and rendering."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Orientation(str, Enum):
    """Physical orientation of the display."""

    PORTRAIT = "portrait"
    LANDSCAPE = "landscape"


class Layout(str, Enum):
    """How a portrait dashboard arranges its sections.

    Every layout draws the same content (see
    :mod:`launchpad.rendering.summaries`); they differ only in arrangement,
    so switching one is purely a presentation choice.
    """

    CLASSIC = "classic"  # stacked sections, full detail (the original)
    COMPACT = "compact"  # one ledger row per section
    HERO = "hero"  # one giant number per mode, detail below
    SLOTS = "slots"  # fixed zones; a section never moves address
    CARDS = "cards"  # lists full width, single stats as tiles
    TIMELINE = "timeline"  # the day on one vertical time axis


@dataclass(frozen=True, slots=True)
class Size:
    """Pixel dimensions of a drawable surface."""

    width: int
    height: int


@dataclass(frozen=True, slots=True)
class Region:
    """A rectangular area within a surface, in pixels."""

    x: int
    y: int
    width: int
    height: int
