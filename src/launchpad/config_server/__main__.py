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
    app.run(host=host, port=port, debug=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
