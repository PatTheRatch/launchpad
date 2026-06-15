"""The neutral artifact passed from a renderer to a display.

A ``Frame`` is a fully-rendered image buffer plus its dimensions. It is the
contract boundary between rendering and display: renderers produce frames,
displays consume them, and neither needs to know about the other's internals.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from launchpad.models.geometry import Size


@dataclass(frozen=True, slots=True)
class Frame:
    """A rendered image ready to be shown on a display.

    ``buffer`` is intentionally typed loosely for now; the concrete pixel
    representation (e.g. a Pillow image or a raw byte buffer) is an
    implementation detail to be fixed later.
    """

    size: Size
    buffer: Any = None
