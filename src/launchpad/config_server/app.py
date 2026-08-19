"""Flask web app for the Launchpad configuration UI.

Runs as a separate process from the dashboard itself (see
``launchpad.config_server.__main__``), so restarting or reloading this server
never touches the running dashboard loop. Configuration reads/writes go
through :mod:`launchpad.config.config_store`; the live preview endpoint
additionally renders dashboard frames in-process (see
:mod:`launchpad.config_server.preview`) — browser-only, never the panel.
"""

from __future__ import annotations

import subprocess
from typing import Any

from flask import Flask, Response, jsonify, render_template, request

from launchpad.config import config_store
from launchpad.models.dashboard import DashboardMode
from launchpad.models.geometry import Layout, Orientation

app = Flask(__name__)

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
