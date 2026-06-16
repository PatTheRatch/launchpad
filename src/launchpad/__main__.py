"""Console entry point for Launchpad (``python -m launchpad``).

Renders once by default (handy for dev); set ``LAUNCHPAD_RUN_FOREVER`` to loop
on the configured refresh interval (how it runs as a service on the Pi).
"""

from __future__ import annotations

import os

from launchpad.config.settings import load_settings
from launchpad.factory import build_dashboard


def main() -> int:
    settings = load_settings()
    dashboard = build_dashboard(settings)
    if os.getenv("LAUNCHPAD_RUN_FOREVER"):
        dashboard.run_forever()
    else:
        dashboard.refresh_once()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
