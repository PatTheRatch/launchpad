"""Tests for the write path: logger validation, logbook mirror, endpoint.

No network anywhere: the Huckleberry call layer is replaced by overriding
``HuckleberryLogger._run``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("flask")

from launchpad.config_server import writer as writer_module
from launchpad.config_server.app import app
from launchpad.config_server.writer import LogWriter
from launchpad.logbook import Logbook
from launchpad.services.experimental.huckleberry_logger import (
    FeedLogError,
    HuckleberryLogger,
)


class FakeLogger(HuckleberryLogger):
    """Records the upstream calls instead of making them; optionally fails."""

    def __init__(self, error: Exception | None = None) -> None:
        super().__init__("parent@example.com", "hunter2")
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self._error = error

    def _run(self, method: str, **kwargs: Any) -> None:
        if self._error is not None:
            raise self._error
        self.calls.append((method, kwargs))


def make_writer(
    tmp_path: Path, error: Exception | None = None
) -> tuple[LogWriter, FakeLogger, Logbook, list[str]]:
    logger = FakeLogger(error=error)
    logbook = Logbook(path=tmp_path / "logbook.db")
    refreshed: list[str] = []
    log_writer = LogWriter(logger, logbook, on_success=lambda: refreshed.append("hit"))
    return log_writer, logger, logbook, refreshed


# --------------------------------------------------------------------------- #
# Logger validation (before anything touches the network)
# --------------------------------------------------------------------------- #


def test_log_bottle_validates_before_writing() -> None:
    logger = FakeLogger()

    with pytest.raises(ValueError, match="between 1 and"):
        logger.log_bottle(amount_ml=0)
    with pytest.raises(ValueError, match="between 1 and"):
        logger.log_bottle(amount_ml=9000)
    with pytest.raises(ValueError, match="must be a number"):
        logger.log_bottle(amount_ml="lots")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="bottle_type"):
        logger.log_bottle(amount_ml=60, bottle_type="Champagne")
    assert logger.calls == []  # nothing reached the write layer


def test_log_bottle_records_normalized_payload() -> None:
    logger = FakeLogger()

    recorded = logger.log_bottle(amount_ml="60", bottle_type="Breast Milk")  # type: ignore[arg-type]

    assert recorded == {"amount_ml": 60.0, "bottle_type": "Breast Milk"}
    assert logger.calls == [
        ("log_bottle", {"amount": 60.0, "bottle_type": "Breast Milk", "units": "ml"})
    ]


def test_log_diaper_validates_mode() -> None:
    logger = FakeLogger()

    with pytest.raises(ValueError, match="mode must be one of"):
        logger.log_diaper(mode="explosive")
    assert logger.log_diaper(mode="both") == {"mode": "both"}
    assert logger.calls == [("log_diaper", {"mode": "both", "notes": None})]


def test_sleep_dispatches_to_timer_lifecycle() -> None:
    logger = FakeLogger()

    for action, method in (
        ("start", "start_sleep"),
        ("complete", "complete_sleep"),
        ("cancel", "cancel_sleep"),
    ):
        assert logger.sleep(action) == {"action": action}
        assert logger.calls[-1] == (method, {})
    with pytest.raises(ValueError, match="action must be one of"):
        logger.sleep("snooze")


def test_missing_credentials_fail_before_any_network() -> None:
    with pytest.raises(FeedLogError, match="credentials"):
        HuckleberryLogger("", "").log_bottle(amount_ml=60)


# --------------------------------------------------------------------------- #
# Write -> mirror -> refresh chain
# --------------------------------------------------------------------------- #


def test_successful_write_is_mirrored_and_refreshes(tmp_path: Path) -> None:
    log_writer, _logger, logbook, refreshed = make_writer(tmp_path)

    recorded = log_writer.log("bottle", {"amount_ml": 60})

    assert recorded == {"amount_ml": 60.0, "bottle_type": "Formula"}
    (entry,) = logbook.recent()
    assert entry["kind"] == "bottle"
    assert entry["payload"] == recorded
    assert refreshed == ["hit"]


def test_failed_write_leaves_no_mirror_entry(tmp_path: Path) -> None:
    log_writer, _logger, logbook, refreshed = make_writer(
        tmp_path, error=FeedLogError("backend down")
    )

    with pytest.raises(FeedLogError):
        log_writer.log("bottle", {"amount_ml": 60})

    # The logbook records what happened, never what was attempted.
    assert logbook.recent() == []
    assert refreshed == []


def test_invalid_input_never_reaches_the_mirror(tmp_path: Path) -> None:
    log_writer, logger, logbook, refreshed = make_writer(tmp_path)

    with pytest.raises(ValueError):
        log_writer.log("bottle", {"amount_ml": -5})
    with pytest.raises(ValueError, match="Unknown event kind"):
        log_writer.log("bath", {})

    assert logger.calls == []
    assert logbook.recent() == []
    assert refreshed == []


def test_logbook_survives_roundtrip_and_orders_newest_first(tmp_path: Path) -> None:
    logbook = Logbook(path=tmp_path / "nested" / "logbook.db")

    logbook.record("bottle", {"amount_ml": 60.0})
    logbook.record("diaper", {"mode": "pee"})

    entries = logbook.recent()
    assert [entry["kind"] for entry in entries] == ["diaper", "bottle"]
    assert entries[1]["payload"] == {"amount_ml": 60.0}


# --------------------------------------------------------------------------- #
# Endpoint
# --------------------------------------------------------------------------- #


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    log_writer, logger, logbook, _refreshed = make_writer(tmp_path)
    monkeypatch.setattr(writer_module, "_shared", log_writer)
    return app.test_client(), logger, logbook


def test_endpoint_logs_bottle(client) -> None:
    test_client, logger, _logbook = client

    response = test_client.post("/api/log/bottle", json={"amount_ml": 60})

    assert response.status_code == 200
    assert response.get_json() == {
        "status": "ok",
        "kind": "bottle",
        "logged": {"amount_ml": 60.0, "bottle_type": "Formula"},
    }
    assert logger.calls[0][0] == "log_bottle"


def test_endpoint_rejects_bad_input_with_400(client) -> None:
    test_client, _logger, _logbook = client

    assert test_client.post("/api/log/bottle", json={"amount_ml": -1}).status_code == 400
    assert test_client.post("/api/log/bath", json={}).status_code == 400


def test_endpoint_maps_backend_failure_to_502(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    log_writer, _logger, _logbook, _refreshed = make_writer(
        tmp_path, error=FeedLogError("backend down")
    )
    monkeypatch.setattr(writer_module, "_shared", log_writer)

    response = app.test_client().post("/api/log/bottle", json={"amount_ml": 60})

    assert response.status_code == 502
    assert "backend down" in response.get_json()["message"]


def test_endpoint_reports_unconfigured_logging_as_503(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Force shared_writer() to resolve fresh with logging disabled.
    monkeypatch.setattr(writer_module, "_shared", None)
    monkeypatch.setenv("LAUNCHPAD_CONFIG_PATH", f"{tmp_path}/config.json")
    monkeypatch.delenv("LAUNCHPAD_FEATURE_BABY_TRACKING", raising=False)
    monkeypatch.delenv("HUCKLEBERRY_EMAIL", raising=False)
    monkeypatch.delenv("HUCKLEBERRY_PASSWORD", raising=False)

    response = app.test_client().post("/api/log/bottle", json={"amount_ml": 60})

    assert response.status_code == 503
