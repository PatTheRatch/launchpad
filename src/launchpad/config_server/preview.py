"""Live dashboard preview rendering for the config UI.

Renders the same frame the panel would show — real services, real builder,
real renderer — into a PNG for the browser, for any time-of-day mode. One
round of collected service data is cached for a short TTL so cycling through
modes reuses a single set of TfL/Open-Meteo/Huckleberry calls instead of
refetching per click.

This never touches the display: frames are rendered in-process and returned
as bytes, so previewing (unlike ``force_mode`` + restart) has no effect on
the physical panel or the running dashboard service.

The rendering/service stack is imported lazily so the config server's other
routes keep working even when the ``render`` extra is not installed.
"""

from __future__ import annotations

import io
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

if TYPE_CHECKING:
    from launchpad.builder import DashboardInputs
    from launchpad.config.settings import Settings
    from launchpad.models.dashboard import DashboardState

LONDON = ZoneInfo("Europe/London")

#: How long one round of live service data is reused across preview renders.
_CACHE_TTL_SECONDS = 60.0

#: Pseudo-mode meaning "whatever the panel would show right now" — the saved
#: ``force_mode`` if set, otherwise the time-of-day schedule.
MODE_AUTO = "auto"


class PreviewError(Exception):
    """A preview could not be rendered; the message is user-facing."""


@dataclass(frozen=True, slots=True)
class ResolvedState:
    """A built dashboard state plus how it was produced — shared by the PNG
    preview and the JSON state endpoint so both draw from one data cache."""

    state: "DashboardState"
    settings: "Settings"
    fetched_at: datetime


@dataclass(frozen=True, slots=True)
class PreviewFrame:
    """One rendered preview: PNG bytes plus what and when it shows."""

    png: bytes
    mode: str  # the resolved mode that was actually rendered
    layout: str  # the layout that was actually rendered
    fetched_at: datetime  # when the underlying service data was collected


def _collect_live_inputs(settings: Settings) -> DashboardInputs:
    """Fetch one round of data through the real service stack.

    Reuses the Dashboard's collection (and therefore its Result-wrapping
    error isolation) with a throwaway mock display — the e-ink driver must
    never be initialised from the config server process, as the panel belongs
    to the dashboard service.
    """
    from launchpad.app import Dashboard
    from launchpad.display.mock_display import MockDisplay
    from launchpad.factory import build_renderer, build_services
    from launchpad.models.geometry import Size

    core, experimental = build_services(settings)
    size = Size(settings.display.width, settings.display.height)
    dashboard = Dashboard(
        settings, core, build_renderer(settings), MockDisplay(size, "preview-unused.png"),
        experimental,
    )
    return dashboard.collect_inputs()


class LivePreview:
    """Renders preview PNGs for any mode from one cached round of live data."""

    def __init__(
        self,
        ttl_seconds: float = _CACHE_TTL_SECONDS,
        inputs_source: Callable[[Settings], DashboardInputs] | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._ttl = ttl_seconds
        self._inputs_source = inputs_source or _collect_live_inputs
        self._clock = clock or (lambda: datetime.now(LONDON))
        self._lock = threading.Lock()
        self._cached: tuple[DashboardInputs, datetime] | None = None

    def resolve_state(self, mode_name: str = MODE_AUTO, refresh: bool = False) -> ResolvedState:
        """Collect (or reuse cached) service data and build the state for a mode.

        ``refresh=True`` discards the cached service data first. Raises
        :class:`PreviewError` for unknown modes; service failures never raise
        (they arrive as unavailable Results inside the state).
        """
        from launchpad.builder import DashboardStateBuilder
        from launchpad.config.settings import load_settings
        from launchpad.models.dashboard import DashboardMode

        if mode_name == MODE_AUTO:
            override = None
        else:
            try:
                override = DashboardMode(mode_name)
            except ValueError:
                valid = ", ".join([MODE_AUTO, *(m.value for m in DashboardMode)])
                raise PreviewError(f"Unknown mode {mode_name!r}. Expected one of: {valid}.")

        now = self._clock()
        # Settings reload every render so a freshly saved config.json (flags,
        # size, force_mode) is honored without restarting the config server.
        settings = load_settings()
        with self._lock:
            cached = self._cached
            if refresh or cached is None or (now - cached[1]).total_seconds() > self._ttl:
                cached = (self._inputs_source(settings), now)
                self._cached = cached
            inputs, fetched_at = cached

        if override is None:
            override = settings.force_mode
        state = DashboardStateBuilder().build(now, inputs, settings.features, override)
        return ResolvedState(state=state, settings=settings, fetched_at=fetched_at)

    def render_png(
        self, mode_name: str, refresh: bool = False, layout_name: str | None = None
    ) -> PreviewFrame:
        """Render ``mode_name`` ("auto" or a DashboardMode value) as a PNG.

        ``layout_name`` overrides the saved layout for this render only, so
        layouts can be compared without touching the panel's configuration.
        Raises :class:`PreviewError` for unknown modes or layouts.
        """
        from dataclasses import replace

        from launchpad.factory import build_renderer
        from launchpad.models.geometry import Layout, Size

        layout: Layout | None = None
        if layout_name is not None:
            try:
                layout = Layout(layout_name)
            except ValueError:
                valid = ", ".join(item.value for item in Layout)
                raise PreviewError(
                    f"Unknown layout {layout_name!r}. Expected one of: {valid}."
                )

        resolved = self.resolve_state(mode_name, refresh=refresh)
        settings, state, fetched_at = resolved.settings, resolved.state, resolved.fetched_at
        if layout is not None:
            settings = replace(settings, display=replace(settings.display, layout=layout))

        size = Size(settings.display.width, settings.display.height)
        frame = build_renderer(settings).render(state, size)

        buffer = io.BytesIO()
        frame.buffer.save(buffer, format="PNG")
        return PreviewFrame(
            png=buffer.getvalue(),
            mode=state.mode.value,
            layout=settings.display.layout.value,
            fetched_at=fetched_at,
        )


_shared: LivePreview | None = None
_shared_lock = threading.Lock()


def shared_preview() -> LivePreview:
    """The process-wide preview instance used by the Flask routes."""
    global _shared
    with _shared_lock:
        if _shared is None:
            _shared = LivePreview()
        return _shared
