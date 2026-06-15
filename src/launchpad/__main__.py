"""Console entry point for Launchpad (``python -m launchpad``).

Wiring lives here so that composition (choosing which services, renderer,
and display to use) is separate from the components themselves.
"""

from __future__ import annotations


def main() -> int:
    """Build and run the dashboard. Not implemented yet."""
    raise NotImplementedError


if __name__ == "__main__":
    raise SystemExit(main())
