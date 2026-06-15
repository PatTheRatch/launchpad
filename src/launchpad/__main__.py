"""Console entry point for Launchpad (``python -m launchpad``).

Wiring lives here so that composition (choosing which services, renderer,
and display to use) is separate from the components themselves. For now this
runs the local preview: build a mock dashboard and render it to a PNG.
"""

from __future__ import annotations

from launchpad.preview import main

if __name__ == "__main__":
    raise SystemExit(main())
