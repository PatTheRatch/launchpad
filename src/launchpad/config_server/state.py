"""Serialize a DashboardState for JSON clients.

Powers ``GET /api/state.json`` — consumed by the nightstand display page
(``/display``) and by home-screen widgets (see ``docs/scriptable/``). The
text comes from :mod:`launchpad.rendering.summaries`, so JSON clients say
exactly what the panel says.

The ``feed`` block is deliberately structured (not just prose): clients tick
"time since feed" locally from ``ended_at`` between polls, so the number on a
nightstand is never staler than the clock it is read by.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from launchpad.models.dashboard import DashboardState, Section
from launchpad.rendering import summaries


def _feed_payload(state: DashboardState) -> dict[str, Any] | None:
    """The last feed as structured data, or ``None`` when there is none."""
    section = state.get(Section.BABY)
    if section is None or section.data is None:
        return None
    feed = section.data.last_feed
    if feed is None:
        return None
    return {
        "type": feed.feed_type.value,
        "started_at": feed.started_at.isoformat(timespec="seconds"),
        "ended_at": feed.ended_at.isoformat(timespec="seconds"),
        "amount_ml": feed.amount_ml,
        "side": feed.side,
        "duration_seconds": feed.duration_seconds,
        "detail": summaries.feed_detail(feed),
    }


def state_payload(state: DashboardState, fetched_at: datetime) -> dict[str, Any]:
    """One dashboard state as a JSON-ready dict.

    ``generated_at`` is when the state was built; ``fetched_at`` is when the
    underlying service data was collected — clients compare it against their
    own clock to flag stale data.
    """
    now = state.generated_at
    sections = [
        {
            "section": section.section.value,
            "availability": section.availability.value,
            "title": summaries.title_for(section),
            "line": summaries.one_line(section, now),
            "lines": list(summaries.detail_lines(section, now)),
        }
        for section in state.visible_sections
    ]
    return {
        "generated_at": now.isoformat(timespec="seconds"),
        "fetched_at": fetched_at.isoformat(timespec="seconds"),
        "mode": state.mode.value,
        "sections": sections,
        "feed": _feed_payload(state),
    }
