"""Tests for the mirrored history: reconciliation, normalization, endpoints.

No network: the upstream fetch is replaced by overriding ``HuckleberrySync._fetch``.
The reconciliation cases matter most — that is where silent data loss would hide.
"""

from __future__ import annotations

import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

pytest.importorskip("flask")

from launchpad.config_server import sync as sync_module
from launchpad.config_server.app import app
from launchpad.logbook import Interval, Logbook
from launchpad.services.experimental.huckleberry_sync import (
    HuckleberrySync,
    SyncError,
    export_rows,
    normalize,
)

NOW = 1_787_000_000.0
DAY = 86400.0


def bottle(start: float, amount: float = 60.0, updated: float = 1.0) -> SimpleNamespace:
    return SimpleNamespace(
        mode="bottle", start=start, bottleType="Formula", amount=amount,
        units="ml", lastUpdated=updated, notes=None,
    )


def a_logbook(tmp_path: Path) -> Logbook:
    return Logbook(path=tmp_path / "logbook.db")


def an_interval(start: float, updated: float = 1.0, summary: str = "Formula · 60ml") -> Interval:
    return Interval(
        kind="feed", start=start, ended=start, last_updated=updated,
        summary=summary, amount_ml=60.0, payload={"mode": "bottle"},
    )


# --------------------------------------------------------------------------- #
# Reconciliation
# --------------------------------------------------------------------------- #


def test_new_rows_are_added(tmp_path: Path) -> None:
    logbook = a_logbook(tmp_path)

    counts = logbook.sync_window("feed", NOW - DAY, NOW, [an_interval(NOW - 100)])

    assert counts.as_dict() == {"added": 1, "updated": 0, "removed": 0}
    assert logbook.counts() == {"feed": 1}


def test_unchanged_rows_are_left_alone(tmp_path: Path) -> None:
    logbook = a_logbook(tmp_path)
    logbook.sync_window("feed", NOW - DAY, NOW, [an_interval(NOW - 100, updated=5.0)])

    counts = logbook.sync_window("feed", NOW - DAY, NOW, [an_interval(NOW - 100, updated=5.0)])

    assert counts.as_dict() == {"added": 0, "updated": 0, "removed": 0}


def test_edited_entries_update_rather_than_duplicate(tmp_path: Path) -> None:
    # Feeds have no stable upstream id, so (kind, start) is the natural key.
    # Editing an entry in the app must not create a second row.
    logbook = a_logbook(tmp_path)
    logbook.sync_window("feed", NOW - DAY, NOW, [an_interval(NOW - 100, updated=5.0)])

    counts = logbook.sync_window(
        "feed", NOW - DAY, NOW,
        [an_interval(NOW - 100, updated=9.0, summary="Formula · 90ml")],
    )

    assert counts.as_dict() == {"added": 0, "updated": 1, "removed": 0}
    assert logbook.counts() == {"feed": 1}
    assert logbook.history()[0]["summary"] == "Formula · 90ml"


def test_entries_deleted_upstream_are_removed(tmp_path: Path) -> None:
    logbook = a_logbook(tmp_path)
    logbook.sync_window(
        "feed", NOW - DAY, NOW, [an_interval(NOW - 100), an_interval(NOW - 200)]
    )

    counts = logbook.sync_window("feed", NOW - DAY, NOW, [an_interval(NOW - 100)])

    assert counts.as_dict() == {"added": 0, "updated": 0, "removed": 1}
    assert logbook.counts() == {"feed": 1}


def test_reconciliation_never_touches_history_outside_the_window(tmp_path: Path) -> None:
    # The whole archive must survive a short recent sync — otherwise a routine
    # 2-day sync would wipe months of history.
    logbook = a_logbook(tmp_path)
    old, recent = NOW - 90 * DAY, NOW - 100
    logbook.sync_window("feed", NOW - 120 * DAY, NOW, [an_interval(old), an_interval(recent)])

    logbook.sync_window("feed", NOW - 2 * DAY, NOW, [an_interval(recent)])

    starts = {entry["summary"] for entry in logbook.history()}
    assert logbook.counts() == {"feed": 2}
    assert starts  # both rows survived


def test_kinds_are_reconciled_independently(tmp_path: Path) -> None:
    logbook = a_logbook(tmp_path)
    logbook.sync_window("feed", NOW - DAY, NOW, [an_interval(NOW - 100)])

    logbook.sync_window("diaper", NOW - DAY, NOW, [])

    assert logbook.counts() == {"feed": 1}


# --------------------------------------------------------------------------- #
# Normalization
# --------------------------------------------------------------------------- #


def test_feeds_normalize_through_the_dashboard_mapping() -> None:
    row = normalize("feed", bottle(NOW - 100, amount=80.0))

    assert row is not None
    assert row.kind == "feed"
    assert row.summary == "Formula · 80ml"
    assert row.amount_ml == 80.0
    assert row.ended == NOW - 100  # a bottle is logged at finish


def test_solids_are_not_mirrored_as_feeds() -> None:
    assert normalize("feed", SimpleNamespace(mode="solids", start=NOW, lastUpdated=1.0)) is None


def test_sleep_normalizes_duration() -> None:
    row = normalize("sleep", SimpleNamespace(start=NOW, duration=5400.0, lastUpdated=1.0))

    assert row is not None
    assert row.summary == "Sleep · 90m"
    assert row.ended == NOW + 5400.0


def test_diaper_normalizes_mode() -> None:
    row = normalize("diaper", SimpleNamespace(start=NOW, mode="both", lastUpdated=1.0))

    assert row is not None and row.summary == "Diaper · both"


def test_rows_without_a_start_are_skipped() -> None:
    assert normalize("feed", SimpleNamespace(mode="bottle", start=None)) is None


# --------------------------------------------------------------------------- #
# Sync orchestration
# --------------------------------------------------------------------------- #


class FakeSync(HuckleberrySync):
    def __init__(self, logbook: Logbook, fetched: dict[str, Any]) -> None:
        super().__init__("parent@example.com", "hunter2", logbook=logbook, clock=lambda: NOW)
        self._fetched = fetched

    async def _fetch(self, start: float, end: float) -> dict[str, Any]:
        return self._fetched


def test_sync_mirrors_each_kind(tmp_path: Path) -> None:
    logbook = a_logbook(tmp_path)
    syncer = FakeSync(logbook, {
        "feed": [bottle(NOW - 100)],
        "diaper": [SimpleNamespace(start=NOW - 200, mode="pee", lastUpdated=1.0)],
        "sleep": [SimpleNamespace(start=NOW - 300, duration=600.0, lastUpdated=1.0)],
    })

    report = syncer.sync(days=1)

    assert report.changed == 3
    assert logbook.counts() == {"feed": 1, "diaper": 1, "sleep": 1}


def test_one_failing_collection_does_not_lose_the_others(tmp_path: Path) -> None:
    logbook = a_logbook(tmp_path)
    syncer = FakeSync(logbook, {
        "feed": [bottle(NOW - 100)],
        "diaper": RuntimeError("diaper query exploded"),
        "sleep": [],
    })

    report = syncer.sync(days=1)

    assert logbook.counts() == {"feed": 1}
    assert "diaper" in report.failed
    assert "exploded" in report.failed["diaper"]


def test_sync_requires_credentials_and_a_positive_window(tmp_path: Path) -> None:
    logbook = a_logbook(tmp_path)
    with pytest.raises(ValueError):
        FakeSync(logbook, {}).sync(days=0)
    with pytest.raises(SyncError, match="credentials"):
        HuckleberrySync("", "", logbook=logbook).sync(days=1)


# --------------------------------------------------------------------------- #
# Export
# --------------------------------------------------------------------------- #


def test_export_rows_start_with_a_header_and_flatten_entries(tmp_path: Path) -> None:
    logbook = a_logbook(tmp_path)
    logbook.sync_window("feed", NOW - DAY, NOW, [an_interval(NOW - 100)])

    rows = export_rows(logbook.history())

    assert rows[0][0] == "kind" and "amount_ml" in rows[0]
    assert rows[1][0] == "feed"
    assert rows[1][4] == "60"


# --------------------------------------------------------------------------- #
# Endpoints
# --------------------------------------------------------------------------- #


@pytest.fixture
def mirrored(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Logbook:
    logbook = a_logbook(tmp_path)
    logbook.sync_window("feed", time.time() - DAY, time.time() + 60, [
        an_interval(time.time() - 100)
    ])
    monkeypatch.setattr(sync_module, "shared_logbook", lambda: logbook)
    return logbook


def test_history_endpoint_returns_mirrored_entries(mirrored: Logbook) -> None:
    body = app.test_client().get("/api/history.json?days=7").get_json()

    assert body["counts"] == {"feed": 1}
    assert body["entries"][0]["summary"] == "Formula · 60ml"


def test_export_endpoint_serves_a_csv_attachment(mirrored: Logbook) -> None:
    response = app.test_client().get("/api/export.csv")

    assert response.status_code == 200
    assert response.mimetype == "text/csv"
    assert "attachment" in response.headers["Content-Disposition"]
    assert b"kind,started_at" in response.data
    assert b"feed" in response.data


def test_sync_endpoint_reports_unconfigured_as_503(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sync_module, "_scheduler", None)

    response = app.test_client().post("/api/sync")

    assert response.status_code == 503


def test_sync_status_endpoint_works_without_a_scheduler(
    monkeypatch: pytest.MonkeyPatch, mirrored: Logbook
) -> None:
    monkeypatch.setattr(sync_module, "_scheduler", None)

    body = app.test_client().get("/api/sync.json").get_json()

    assert body["enabled"] is False
    assert body["counts"] == {"feed": 1}
