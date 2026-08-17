"""Tests for the config server's live preview (no network, mock inputs)."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

pytest.importorskip("flask")

from launchpad.builder import DashboardInputs
from launchpad.config.settings import Settings
from launchpad.config_server import preview as preview_module
from launchpad.config_server.app import app
from launchpad.models.result import Result
from launchpad.preview import (
    build_mock_agenda,
    build_mock_baby_snapshot,
    build_mock_station_arrivals,
    build_mock_weather,
)

LONDON = ZoneInfo("Europe/London")
MORNING = datetime(2026, 6, 15, 8, 15, tzinfo=LONDON)

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


@pytest.fixture(autouse=True)
def isolated_config(monkeypatch: pytest.MonkeyPatch, tmp_path: object) -> None:
    # Point the config store at a missing file so load_settings() returns the
    # documented defaults (mock driver, no force_mode) regardless of the
    # repo's real config.json.
    monkeypatch.setenv("LAUNCHPAD_CONFIG_PATH", f"{tmp_path}/config.json")


def mock_inputs(_settings: Settings) -> DashboardInputs:
    return DashboardInputs(
        train=Result.present(build_mock_station_arrivals()),
        weather=Result.present(build_mock_weather()),
        calendar=Result.present(build_mock_agenda()),
        baby=Result.present(build_mock_baby_snapshot()),
    )


def make_preview(**kwargs: float) -> tuple[preview_module.LivePreview, list[Settings]]:
    calls: list[Settings] = []

    def source(settings: Settings) -> DashboardInputs:
        calls.append(settings)
        return mock_inputs(settings)

    live = preview_module.LivePreview(
        inputs_source=source, clock=lambda: MORNING, **kwargs
    )
    return live, calls


def test_render_png_produces_png_and_resolves_auto_mode() -> None:
    live, _calls = make_preview()

    frame = live.render_png("auto")

    assert frame.png.startswith(PNG_MAGIC)
    assert frame.mode == "morning"  # 08:15 London
    assert frame.fetched_at == MORNING


def test_render_png_honors_explicit_mode_override() -> None:
    live, _calls = make_preview()

    assert live.render_png("overnight").mode == "overnight"
    assert live.render_png("evening").mode == "evening"


def test_service_data_is_cached_across_mode_renders() -> None:
    live, calls = make_preview()

    live.render_png("morning")
    live.render_png("overnight")

    assert len(calls) == 1


def test_refresh_discards_cached_service_data() -> None:
    live, calls = make_preview()

    live.render_png("morning")
    live.render_png("morning", refresh=True)

    assert len(calls) == 2


def test_unknown_mode_raises_preview_error() -> None:
    live, _calls = make_preview()

    with pytest.raises(preview_module.PreviewError, match="afternoon"):
        live.render_png("afternoon")


def test_preview_endpoint_serves_png_with_mode_headers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    live, _calls = make_preview()
    monkeypatch.setattr(preview_module, "_shared", live)

    response = app.test_client().get("/api/preview/overnight.png")

    assert response.status_code == 200
    assert response.mimetype == "image/png"
    assert response.data.startswith(PNG_MAGIC)
    assert response.headers["X-Launchpad-Mode"] == "overnight"
    assert response.headers["Cache-Control"] == "no-store"


def test_preview_endpoint_rejects_unknown_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    live, _calls = make_preview()
    monkeypatch.setattr(preview_module, "_shared", live)

    response = app.test_client().get("/api/preview/bogus.png")

    assert response.status_code == 404
    assert response.get_json()["status"] == "error"
