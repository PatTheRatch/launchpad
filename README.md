# Launchpad

A Raspberry Pi e-ink family dashboard for the front door.

Launchpad shows a household the few things it needs to start the day smoothly —
**train departures, weather, and the day's calendar** — on an e-ink panel that
can be read in a five-second glance.

**Status: working core, pre-hardware.** The dashboard renders live TfL train
departures and Open-Meteo weather to a PNG via the mock display. The calendar
is still mock data, and the real e-ink panel driver is not yet implemented.

| Feature | Status |
| --- | --- |
| Dashboard orchestration (collect → build → render → show) | ✅ implemented |
| Train departures (TfL, 3 stations, direction-filtered, line status) | ✅ live |
| Weather (Open-Meteo, icons, outerwear hints) | ✅ live |
| Time-of-day modes (morning/daytime/evening/overnight) | ✅ implemented |
| Portrait renderer (480×800, 1-bit) | ✅ implemented |
| Mock display (writes `dashboard.png`) | ✅ implemented |
| Calendar | 🔶 mock data |
| World Cup watchlist (experimental, behind flag) | 🔶 mock data |
| E-ink display driver | ⬜ stub |
| Landscape renderer | ⬜ stub |
| NBA / fantasy basketball / baby tracking (experimental) | ⬜ interfaces only |

### Documentation map

- `README.md` (this file) — project overview and quickstart
- [`LAUNCHPAD.md`](LAUNCHPAD.md) — operator reference: system state, commands, deployment
- [`docs/PROJECT_VISION.md`](docs/PROJECT_VISION.md) — long-term product direction and philosophy

## Design principles

- **Core features always work.** Train departures, weather, and calendar are
  never gated and are isolated from anything experimental.
- **Experimental features are isolated.** They are opt-in via feature flags and
  can fail without affecting the core dashboard.
- **Glanceable.** The layout targets a five-second read.
- **SOLID & swappable.** Each service is independent and replaceable, rendering
  is decoupled from data retrieval, and display hardware is abstracted away.

## Architecture

Data flows in one direction, and each boundary is an interface:

```
Services  ──►  DashboardState  ──►  Renderer  ──►  Frame  ──►  Display
(retrieve)     (plain models)       (lay out)      (image)     (show)
```

- **Services** (`launchpad.services`) only *retrieve* data and return plain
  models. They never render. The generic `DataService[T]` interface keeps every
  service single-responsibility and interchangeable.
- **Models** (`launchpad.models`) are immutable dataclasses — the contract
  between services and renderers. Each result is wrapped in a three-state
  `Result[T]` (present / empty / unavailable) so failures degrade gracefully.
- **Builder** (`launchpad.builder`) is a pure function from gathered results to
  an immutable `DashboardState`: it resolves the time-of-day mode and which
  sections are visible. No I/O, no clock reads.
- **Renderers** (`launchpad.rendering`) turn a `DashboardState` into a neutral
  `Frame`. `PortraitRenderer` is the real one; landscape is a stub.
- **Displays** (`launchpad.display`) only know how to show a `Frame`.
  `MockDisplay` writes `dashboard.png` anywhere for development; `EinkDisplay`
  will drive the real panel on the Pi (not yet implemented).
- **Composition** (`launchpad.app`, `launchpad.factory`) wires concrete
  collaborators together based on `Settings`. Everything else depends only on
  abstractions.

Adding a feature means adding a model + service + renderer section without
touching the core; swapping orientation or hardware means choosing a different
renderer or display.

## Project structure

```
src/launchpad/
├── app.py                  # Dashboard orchestrator (collect/refresh/run)
├── builder.py              # Pure DashboardState builder + mode logic
├── factory.py              # Composition root: settings → collaborators
├── preview.py              # Deterministic mock fixtures for tests/previews
├── __main__.py             # `python -m launchpad` entry point
├── config/                 # Settings, feature flags, station config
├── models/                 # Immutable dataclasses (+ experimental/)
├── services/
│   ├── core/               # TfL trains, Open-Meteo weather, mock calendar
│   └── experimental/       # World Cup (mock); NBA/fantasy/baby interfaces
├── rendering/              # PortraitRenderer, fonts, weather icons
└── display/                # MockDisplay (PNG), EinkDisplay (stub)
tests/
└── unit/
```

## Requirements

- Python 3.13+

## Getting started

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,render,tfl]"
```

The extras matter: `render` brings Pillow, `tfl` brings httpx and python-dotenv.
Installing bare or with `.[dev]` alone will fail at runtime with missing
imports.

Configuration is via environment variables, loaded from a local `.env` file:

```bash
cp .env.example .env   # then fill in values; .env is gitignored
```

Render the dashboard once (writes `dashboard.png`, a gitignored local
artifact):

```bash
python -m launchpad
```

Run continuously on the configured refresh interval (how it runs as a service
on the Pi — see [`LAUNCHPAD.md`](LAUNCHPAD.md) and `deploy/launchpad.service`):

```bash
LAUNCHPAD_RUN_FOREVER=1 python -m launchpad
```

Checks:

```bash
pytest
ruff check .
mypy src
```

## Roadmap

1. ~~Implement core services (train, weather) against a mock display.~~
2. ~~Implement the portrait renderer.~~
3. Replace the mock calendar with a real (shared family) calendar integration.
4. Add the e-ink display driver on the Raspberry Pi.
5. Layer in experimental features behind their flags.

## License

MIT
