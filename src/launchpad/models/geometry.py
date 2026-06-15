"""Shared geometry/layout primitives used across config, display, and rendering."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Orientation(str, Enum):
    """Physical orientation of the display."""

    PORTRAIT = "portrait"
    LANDSCAPE = "landscape"


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
