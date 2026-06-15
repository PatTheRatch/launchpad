"""Composition helpers: turn settings into concrete collaborators.

Centralizing construction here keeps the selection logic (which renderer for
the configured orientation, which display driver, which experimental services
to enable) in one place and out of the components themselves.
"""

from __future__ import annotations

from launchpad.app import Dashboard
from launchpad.config.settings import Settings
from launchpad.display.base import Display
from launchpad.rendering.base import Renderer


def build_renderer(settings: Settings) -> Renderer:
    """Select a renderer based on the configured orientation. Not implemented."""
    raise NotImplementedError


def build_display(settings: Settings) -> Display:
    """Select a display driver (mock vs e-ink). Not implemented."""
    raise NotImplementedError


def build_dashboard(settings: Settings) -> Dashboard:
    """Wire settings, services, renderer, and display into a Dashboard."""
    raise NotImplementedError
