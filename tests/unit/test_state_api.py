"""Tests for the JSON state endpoint and its serializer (no network)."""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

pytest.importorskip("flask")

from launchpad.builder import DashboardInputs, DashboardStateBuilder
from launchpad.config.features import FeatureFlags
from launchpad.config.settings import Settings
from launchpad.config_server import preview as preview_module
from launchpad.config_server.app import app
from launchpad.config_server.state import state_payload
from launchpad.models.dashboard import DashboardMode
from launchpad.models.experimental.baby import BabySnapshot, Feed, FeedType
from launchpad.models.result import Result
from launchpad.preview import (
    build_mock_agenda,
    build_mock_station_arrivals,
    build_mock_weather,
)

LONDON = ZoneInfo("Europe/London")
NOW = datetime(2026, 6, 15, 3, 0, tzinfo=LONDON)
FED_AT = NOW - timedelta(hours=2, minutes=40)


@pytest.fixture(autouse=True)
def isolated_config(monkeypatch: pytest.MonkeyPatch, tmp_path: object) -> None:
    # The endpoints resolve feature flags from config.json; the feed block only
    # exists when baby_tracking is enabled there.
    monkeypatch.setenv("LAUNCHPAD_CONFIG_PATH", f"{tmp_path}/config.json")
    monkeypatch.setenv("LAUNCHPAD_FEATURE_BABY_TRACKING", "1")


def a_feed_snapshot() -> BabySnapshot:
    return BabySnapshot(
        last_feed=Feed(
            feed_type=FeedType.FORMULA, started_at=FED_AT, ended_at=FED_AT, amount_ml=80.0
        ),
        retrieved_at=NOW,
    )


def full_inputs() -> DashboardInputs:
    return DashboardInputs(
        train=Result.present(build_mock_station_arrivals()),
        calendar=Result.present(build_mock_agenda()),
        weather=Result.present(build_mock_weather()),
        baby=Result.present(a_feed_snapshot()),
    )


def build_state(inputs: DashboardInputs, mode: DashboardMode = DashboardMode.OVERNIGHT):
    return DashboardStateBuilder().build(NOW, inputs, FeatureFlags(baby_tracking=True), mode)


# --------------------------------------------------------------------------- #
# Serializer
# --------------------------------------------------------------------------- #


def test_payload_carries_structured_feed_for_client_ticking() -> None:
    payload = state_payload(build_state(full_inputs()), NOW)

    assert payload["mode"] == "overnight"
    assert payload["feed"] == {
        "type": "formula",
        "started_at": FED_AT.isoformat(timespec="seconds"),
        "ended_at": FED_AT.isoformat(timespec="seconds"),
        "amount_ml": 80.0,
        "side": None,
        "duration_seconds": None,
        "detail": "Formula · 80ml",
    }


def test_payload_sections_share_the_panel_wording() -> None:
    payload = state_payload(build_state(full_inputs()), NOW)
    by_key = {section["section"]: section for section in payload["sections"]}

    assert by_key["baby"]["title"] == "Last feed"
    assert "2h 40m ago" in by_key["baby"]["line"]
    assert by_key["weather"]["title"] == "London"


def test_payload_feed_is_null_when_unavailable_but_section_explains() -> None:
    payload = state_payload(build_state(DashboardInputs()), NOW)
    by_key = {section["section"]: section for section in payload["sections"]}

    assert payload["feed"] is None
    assert by_key["baby"]["availability"] == "unavailable"
    assert by_key["baby"]["line"] == "Feeds unavailable"


def test_payload_feed_is_null_when_no_feed_logged() -> None:
    inputs = DashboardInputs(baby=Result.present(BabySnapshot(retrieved_at=NOW)))
    payload = state_payload(build_state(inputs), NOW)

    assert payload["feed"] is None


# --------------------------------------------------------------------------- #
# Endpoints
# --------------------------------------------------------------------------- #


def make_preview() -> tuple[preview_module.LivePreview, list[Settings]]:
    calls: list[Settings] = []

    def source(settings: Settings) -> DashboardInputs:
        calls.append(settings)
        return full_inputs()

    return preview_module.LivePreview(inputs_source=source, clock=lambda: NOW), calls


def test_state_endpoint_serves_json(monkeypatch: pytest.MonkeyPatch) -> None:
    live, _calls = make_preview()
    monkeypatch.setattr(preview_module, "_shared", live)

    response = app.test_client().get("/api/state.json?mode=overnight")

    assert response.status_code == 200
    body = response.get_json()
    assert body["mode"] == "overnight"
    assert body["feed"]["detail"] == "Formula · 80ml"
    assert response.headers["Cache-Control"] == "no-store"


def test_state_endpoint_rejects_unknown_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    live, _calls = make_preview()
    monkeypatch.setattr(preview_module, "_shared", live)

    response = app.test_client().get("/api/state.json?mode=brunch")

    assert response.status_code == 404


def test_state_and_preview_share_one_data_fetch(monkeypatch: pytest.MonkeyPatch) -> None:
    live, calls = make_preview()
    monkeypatch.setattr(preview_module, "_shared", live)
    client = app.test_client()

    client.get("/api/state.json")
    client.get("/api/preview/morning.png")

    assert len(calls) == 1


def test_display_page_serves_html() -> None:
    response = app.test_client().get("/display")

    assert response.status_code == 200
    assert b"Since last feed" in response.data
