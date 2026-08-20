"""Tests for real-time watching: broker fan-out, watcher callbacks, endpoints.

No network: the watcher's callback plumbing is exercised directly, and the
session loop is never started.
"""

from __future__ import annotations

import queue
import time
from typing import Any

import pytest

pytest.importorskip("flask")

from launchpad.config_server import realtime
from launchpad.config_server.app import app
from launchpad.config_server.realtime import ChangeBroker
from launchpad.services.experimental.huckleberry_watcher import FeedWatcher


def a_watcher(on_change: Any = None) -> FeedWatcher:
    return FeedWatcher(
        email="parent@example.com",
        password="hunter2",
        on_change=on_change or (lambda source: None),
    )


# --------------------------------------------------------------------------- #
# Broker
# --------------------------------------------------------------------------- #


def test_publish_bumps_version_and_wakes_subscribers() -> None:
    broker = ChangeBroker()
    first, second = broker.subscribe(), broker.subscribe()

    broker.publish("feed")

    assert broker.version == 1
    assert first.get_nowait() == 1
    assert second.get_nowait() == 1


def test_unsubscribed_clients_stop_receiving() -> None:
    broker = ChangeBroker()
    subscriber = broker.subscribe()
    broker.unsubscribe(subscriber)

    broker.publish("feed")

    assert broker.subscriber_count == 0
    with pytest.raises(queue.Empty):
        subscriber.get_nowait()


def test_a_stalled_subscriber_never_blocks_publishing() -> None:
    # A client that stops reading must not stall the watcher thread or other
    # clients; its queue simply saturates and it catches up on its next poll.
    broker = ChangeBroker()
    stalled = broker.subscribe()
    healthy = broker.subscribe()

    for _ in range(50):
        broker.publish("feed")

    assert broker.version == 50
    assert stalled.qsize() <= 8
    assert healthy.qsize() <= 8


# --------------------------------------------------------------------------- #
# Watcher callback plumbing
# --------------------------------------------------------------------------- #


def test_initial_snapshot_is_ignored() -> None:
    # Firestore delivers the current document on subscribe, so without this
    # every session rebuild would look like a fresh change.
    seen: list[str] = []
    callback = a_watcher(lambda source: seen.append(source))._callback_for("feed")

    callback(object())  # initial snapshot
    assert seen == []

    callback(object())  # a real change
    assert seen == ["feed"]


def test_each_listener_suppresses_its_own_first_snapshot() -> None:
    seen: list[str] = []
    watcher = a_watcher(lambda source: seen.append(source))
    feed = watcher._callback_for("feed")
    diaper = watcher._callback_for("diaper")

    feed(object())
    diaper(object())
    assert seen == []

    feed(object())
    assert seen == ["feed"]


def test_rapid_repeats_are_throttled() -> None:
    # One logical write can produce several document updates.
    seen: list[str] = []
    watcher = a_watcher(lambda source: seen.append(source))
    callback = watcher._callback_for("feed")
    callback(object())  # initial

    for _ in range(5):
        callback(object())

    assert seen == ["feed"]


def test_throttle_releases_after_the_window() -> None:
    seen: list[str] = []
    watcher = a_watcher(lambda source: seen.append(source))
    callback = watcher._callback_for("feed")
    callback(object())  # initial

    callback(object())
    watcher._last_fired -= 5.0  # simulate the window elapsing
    callback(object())

    assert seen == ["feed", "feed"]


def test_a_raising_subscriber_does_not_escape() -> None:
    # The callback runs on a Firestore SDK thread; an exception there would
    # kill the listener silently.
    def explode(_source: str) -> None:
        raise RuntimeError("subscriber blew up")

    callback = a_watcher(explode)._callback_for("feed")
    callback(object())

    callback(object())  # must not raise


def test_status_snapshot_reports_counters() -> None:
    watcher = a_watcher()
    callback = watcher._callback_for("feed")
    callback(object())
    callback(object())

    status = watcher.status.snapshot()
    assert status["changes"] == 1
    assert status["connected"] is False
    assert status["last_change_at"] is not None


# --------------------------------------------------------------------------- #
# Endpoints
# --------------------------------------------------------------------------- #


def test_realtime_status_endpoint_reports_disabled_when_not_running(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(realtime, "_watcher", None)

    body = app.test_client().get("/api/realtime.json").get_json()

    assert body["enabled"] is False
    assert "version" in body


def test_events_stream_opens_with_a_hello_and_registers_a_subscriber() -> None:
    response = app.test_client().get("/api/events", buffered=False)

    assert response.status_code == 200
    assert response.mimetype == "text/event-stream"
    assert response.headers["Cache-Control"] == "no-store"

    stream = response.response
    assert "retry:" in next(stream).decode()
    assert "event: hello" in next(stream).decode()
    response.close()


def test_events_stream_delivers_a_published_change() -> None:
    response = app.test_client().get("/api/events", buffered=False)
    stream = response.response
    next(stream)  # retry
    next(stream)  # hello

    # Publishing from another thread is what the watcher actually does.
    realtime.broker().publish("feed")

    chunk = next(stream).decode()
    assert "event: change" in chunk
    response.close()


def test_stream_unsubscribes_when_the_client_disconnects() -> None:
    before = realtime.broker().subscriber_count
    response = app.test_client().get("/api/events", buffered=False)
    stream = response.response
    next(stream)
    response.close()

    # Closing the generator runs its finally block.
    deadline = time.monotonic() + 2.0
    while realtime.broker().subscriber_count > before and time.monotonic() < deadline:
        time.sleep(0.01)
    assert realtime.broker().subscriber_count == before


def test_start_watcher_declines_when_realtime_is_disabled(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    monkeypatch.setattr(realtime, "_watcher", None)
    monkeypatch.setenv("LAUNCHPAD_REALTIME", "0")

    assert realtime.start_watcher() is None


def test_start_watcher_declines_without_credentials(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    monkeypatch.setattr(realtime, "_watcher", None)
    monkeypatch.setenv("LAUNCHPAD_REALTIME", "1")
    monkeypatch.setenv("LAUNCHPAD_CONFIG_PATH", f"{tmp_path}/config.json")
    monkeypatch.setenv("LAUNCHPAD_FEATURE_BABY_TRACKING", "1")
    monkeypatch.delenv("HUCKLEBERRY_EMAIL", raising=False)
    monkeypatch.delenv("HUCKLEBERRY_PASSWORD", raising=False)

    assert realtime.start_watcher() is None
