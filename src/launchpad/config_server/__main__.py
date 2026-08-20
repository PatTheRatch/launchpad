"""Entry point for the configuration web server (``python -m launchpad.config_server``).

Runs independently of the dashboard process itself; see ``deploy/`` for how it
is expected to be deployed alongside the ``launchpad`` systemd service.
"""

from __future__ import annotations

import os

from launchpad.config_server.app import app


def main() -> int:
    host = os.getenv("LAUNCHPAD_CONFIG_HOST", "0.0.0.0")
    port = int(os.getenv("LAUNCHPAD_CONFIG_PORT", "8080"))

    # Real-time watching starts here rather than at import, so importing the
    # app (in tests, or another process) never opens a network connection.
    # It is best-effort: if it cannot start, the server runs on polling alone.
    from launchpad.config_server import realtime, sync

    realtime.start_watcher()
    sync.start_scheduler()
    try:
        app.run(host=host, port=port, debug=False)
    finally:
        realtime.stop_watcher()
        sync.stop_scheduler()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
