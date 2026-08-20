"""Flask web app for the Launchpad configuration UI.

Runs as a separate process from the dashboard itself (see
``launchpad.config_server.__main__``), so restarting or reloading this server
never touches the running dashboard loop. Configuration reads/writes go
through :mod:`launchpad.config.config_store`; the live preview endpoint
additionally renders dashboard frames in-process (see
:mod:`launchpad.config_server.preview`) — browser-only, never the panel.
"""

from __future__ import annotations

import queue
import subprocess
import time
from typing import Any

from flask import Flask, Response, jsonify, render_template, request

from launchpad.config import config_store
from launchpad.models.dashboard import DashboardMode
from launchpad.models.geometry import Layout, Orientation

app = Flask(__name__)

#: SSE tuning: heartbeat often enough to hold the connection open, and close
#: the stream well before anything upstream decides to time it out.
_SSE_HEARTBEAT_SECONDS = 20.0
_SSE_MAX_SECONDS = 300.0
_SSE_RETRY_MS = 3000

_DRIVERS = ("mock", "eink")
_FEATURE_KEYS = ("nba", "fantasy_basketball", "baby_tracking", "world_cup")


@app.get("/")
def index() -> str:
    """Serve the configuration UI page."""
    return render_template("index.html")


@app.get("/api/config")
def get_config() -> Response:
    """Return the current persisted configuration as JSON."""
    return jsonify(config_store.load_config())


@app.post("/api/config")
def post_config() -> tuple[Response, int] | Response:
    """Validate, persist, and echo back a new configuration."""
    payload = request.get_json(silent=True)
    try:
        config = _validate_config(payload)
    except ValueError as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400

    config_store.save_config(config)
    return jsonify({"status": "ok", "config": config})


@app.get("/api/preview/<mode>.png")
def get_preview(mode: str) -> tuple[Response, int] | Response:
    """Render a live dashboard preview for a mode ("auto" or a real mode).

    ``?layout=`` overrides the saved layout for this render only; ``?refresh=1``
    forces a fresh round of service data instead of the cache.
    """
    from launchpad.config_server import preview as preview_module

    try:
        frame = preview_module.shared_preview().render_png(
            mode,
            refresh="refresh" in request.args,
            layout_name=request.args.get("layout"),
        )
    except preview_module.PreviewError as exc:
        return jsonify({"status": "error", "message": str(exc)}), 404
    except Exception as exc:
        # A preview failure (e.g. missing render extra) must never take the
        # config UI down with it.
        return jsonify({"status": "error", "message": f"Preview failed: {exc}"}), 500

    response = Response(frame.png, mimetype="image/png")
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Launchpad-Mode"] = frame.mode
    response.headers["X-Launchpad-Layout"] = frame.layout
    response.headers["X-Launchpad-Fetched-At"] = frame.fetched_at.isoformat(
        timespec="seconds"
    )
    return response


@app.get("/api/state.json")
def get_state() -> tuple[Response, int] | Response:
    """The current dashboard state as JSON, for the nightstand page and widgets.

    ``?mode=`` forces a time-of-day mode (default "auto"); ``?refresh=1``
    bypasses the shared 60s service-data cache.
    """
    from launchpad.config_server import preview as preview_module
    from launchpad.config_server.state import state_payload

    try:
        resolved = preview_module.shared_preview().resolve_state(
            request.args.get("mode", "auto"), refresh="refresh" in request.args
        )
    except preview_module.PreviewError as exc:
        return jsonify({"status": "error", "message": str(exc)}), 404
    except Exception as exc:
        # A state failure must never take the config UI down with it.
        return jsonify({"status": "error", "message": f"State failed: {exc}"}), 500

    response = jsonify(state_payload(resolved.state, resolved.fetched_at))
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/display")
def display() -> str:
    """Serve the always-on nightstand display page."""
    return render_template("display.html")


@app.get("/api/realtime.json")
def get_realtime() -> Response:
    """Whether real-time watching is active, and what it has seen."""
    from launchpad.config_server import realtime

    response = jsonify(realtime.status())
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/api/events")
def get_events() -> Response:
    """Server-sent events: a version bump whenever Huckleberry changes.

    Clients re-fetch ``/api/state.json`` on each bump, so pushed and polled
    state can never disagree. The stream carries heartbeats and closes itself
    after a bounded lifetime; EventSource reconnects automatically, which
    keeps a long-lived page from pinning a worker thread indefinitely.
    """
    from launchpad.config_server import realtime

    broker = realtime.broker()

    def stream() -> Any:
        subscriber = broker.subscribe()
        try:
            yield f"retry: {_SSE_RETRY_MS}\n\n"
            yield f"event: hello\ndata: {broker.version}\n\n"
            deadline = time.monotonic() + _SSE_MAX_SECONDS
            while time.monotonic() < deadline:
                try:
                    version = subscriber.get(timeout=_SSE_HEARTBEAT_SECONDS)
                    yield f"event: change\ndata: {version}\n\n"
                except queue.Empty:
                    yield ": keep-alive\n\n"
        finally:
            broker.unsubscribe(subscriber)

    response = Response(stream(), mimetype="text/event-stream")
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Accel-Buffering"] = "no"  # defeat proxy buffering
    return response


@app.post("/api/log/<kind>")
def post_log(kind: str) -> tuple[Response, int] | Response:
    """Log a care event (bottle, diaper, sleep) through to Huckleberry.

    Writes are a single attempt, never retried server-side: on failure the
    caller sees the error and a human decides whether to tap again.
    """
    from launchpad.config_server import writer as writer_module

    log_writer = writer_module.shared_writer()
    if log_writer is None:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Logging is not configured: enable baby tracking "
                    "and set the Huckleberry credentials, then restart launchpad-config.",
                }
            ),
            503,
        )

    payload = request.get_json(silent=True) or {}
    try:
        recorded = log_writer.log(kind, payload)
    except ValueError as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400
    except writer_module.FeedLogError as exc:
        return jsonify({"status": "error", "message": str(exc)}), 502
    except Exception as exc:
        return jsonify({"status": "error", "message": f"Logging failed: {exc}"}), 500

    return jsonify({"status": "ok", "kind": kind, "logged": recorded})


@app.get("/api/history.json")
def get_history() -> Response:
    """Launchpad's own mirrored history: feeds, diapers, and sleep.

    ``?days=`` limits how far back (default 7), ``?kind=`` filters
    (repeatable), ``?limit=`` caps rows (default 200).
    """
    from launchpad.config_server import sync as sync_module

    days = request.args.get("days", type=float) or 7.0
    limit = min(request.args.get("limit", type=int) or 200, 2000)
    kinds = request.args.getlist("kind") or None
    since = time.time() - days * 86400

    logbook = sync_module.shared_logbook()
    response = jsonify(
        {
            "days": days,
            "counts": logbook.counts(),
            "span": list(logbook.span()),
            "entries": logbook.history(kinds=kinds, since=since, limit=limit),
        }
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/api/export.csv")
def get_export() -> Response:
    """Export the mirrored history as CSV — the data is yours to take."""
    import csv
    import io

    from launchpad.config_server import sync as sync_module
    from launchpad.services.experimental.huckleberry_sync import export_rows

    days = request.args.get("days", type=float) or 3650.0
    kinds = request.args.getlist("kind") or None
    history = sync_module.shared_logbook().history(
        kinds=kinds, since=time.time() - days * 86400, limit=100_000
    )

    buffer = io.StringIO()
    csv.writer(buffer).writerows(export_rows(history))
    response = Response(buffer.getvalue(), mimetype="text/csv")
    response.headers["Content-Disposition"] = 'attachment; filename="launchpad-history.csv"'
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/api/sync.json")
def get_sync_status() -> tuple[Response, int] | Response:
    """Whether history mirroring is running, and what it last did."""
    from launchpad.config_server import sync as sync_module

    scheduler = sync_module.scheduler()
    if scheduler is None:
        return jsonify({"enabled": False, "counts": sync_module.shared_logbook().counts()})
    return jsonify({"enabled": True, **scheduler.status()})


@app.post("/api/sync")
def post_sync() -> tuple[Response, int] | Response:
    """Mirror upstream history now. ``?days=`` overrides the window."""
    from launchpad.config_server import sync as sync_module
    from launchpad.services.experimental.huckleberry_sync import SyncError

    scheduler = sync_module.scheduler()
    if scheduler is None:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "History mirroring is not configured: enable baby tracking "
                    "and set the Huckleberry credentials, then restart launchpad-config.",
                }
            ),
            503,
        )

    days = request.args.get("days", type=float)
    try:
        report = scheduler.sync_now(days=days)
    except ValueError as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400
    except SyncError as exc:
        return jsonify({"status": "error", "message": str(exc)}), 502
    except Exception as exc:
        return jsonify({"status": "error", "message": f"Sync failed: {exc}"}), 500

    return jsonify({"status": "ok", "report": report})


@app.post("/api/restart")
def post_restart() -> tuple[Response, int] | Response:
    """Restart the launchpad systemd service."""
    try:
        subprocess.run(
            ["sudo", "systemctl", "restart", "launchpad"],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.CalledProcessError as exc:
        message = exc.stderr.strip() or f"systemctl exited with status {exc.returncode}."
        return jsonify({"status": "error", "message": message}), 500
    except (OSError, subprocess.TimeoutExpired) as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500

    return jsonify({"status": "ok"})


def _is_positive_int(value: Any) -> bool:
    # bool is a subclass of int, so it must be excluded explicitly or
    # e.g. {"width": true} would pass as width=1.
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _validate_config(payload: Any) -> dict[str, Any]:
    """Validate a full config payload, raising ``ValueError`` on the first problem."""
    if not isinstance(payload, dict):
        raise ValueError("Request body must be a JSON object.")

    display = payload.get("display")
    if not isinstance(display, dict):
        raise ValueError("'display' must be an object.")

    orientation = display.get("orientation")
    if orientation not in {o.value for o in Orientation}:
        raise ValueError("'display.orientation' must be 'portrait' or 'landscape'.")

    driver = display.get("driver")
    if driver not in _DRIVERS:
        raise ValueError("'display.driver' must be 'mock' or 'eink'.")

    # Older config.json files predate layouts; default rather than reject.
    layout = display.get("layout", Layout.CLASSIC.value)
    if layout not in {item.value for item in Layout}:
        valid = ", ".join(sorted(item.value for item in Layout))
        raise ValueError(f"'display.layout' must be one of: {valid}.")

    width = display.get("width")
    if not _is_positive_int(width):
        raise ValueError("'display.width' must be a positive integer.")

    height = display.get("height")
    if not _is_positive_int(height):
        raise ValueError("'display.height' must be a positive integer.")

    refresh = payload.get("refresh")
    if not isinstance(refresh, dict):
        raise ValueError("'refresh' must be an object.")

    refresh_seconds = refresh.get("refresh_seconds")
    if not _is_positive_int(refresh_seconds):
        raise ValueError("'refresh.refresh_seconds' must be a positive integer.")

    features = payload.get("features")
    if not isinstance(features, dict):
        raise ValueError("'features' must be an object.")

    validated_features: dict[str, bool] = {}
    for key in _FEATURE_KEYS:
        value = features.get(key, False)
        if not isinstance(value, bool):
            raise ValueError(f"'features.{key}' must be a boolean.")
        validated_features[key] = value

    force_mode = payload.get("force_mode")
    valid_modes = {m.value for m in DashboardMode}
    if force_mode is not None and force_mode not in valid_modes:
        raise ValueError(
            f"'force_mode' must be null or one of: {', '.join(sorted(valid_modes))}."
        )

    return {
        "display": {
            "orientation": orientation,
            "width": width,
            "height": height,
            "driver": driver,
            "layout": layout,
        },
        "refresh": {"refresh_seconds": refresh_seconds},
        "features": validated_features,
        "force_mode": force_mode,
    }
