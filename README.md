# Launchpad

A Raspberry Pi e-ink family dashboard for the front door.

Launchpad shows a household the few things it needs to start the day smoothly —
**train departures, weather, and the day's calendar** — on an e-ink panel that
can be read in a five-second glance.

> ⚠️ **Status: scaffold.** This repository currently contains only the project
> structure, data models, and interfaces. There is no working functionality
> yet — most methods raise `NotImplementedError`.

## Design principles

- **Core features always work.** Train departures, weather, and calendar are
  never gated and are isolated from anything experimental.
- **Experimental features are isolated.** NBA/Cavs, fantasy basketball, and
  baby tracking are opt-in via feature flags and can fail without affecting the
  core dashboard.
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
  between services and renderers. `DashboardState` aggregates everything needed
  to draw one frame.
- **Renderers** (`launchpad.rendering`) turn a `DashboardState` into a neutral
  `Frame`. Portrait and landscape layouts are separate implementations of the
  same `Renderer` interface; reusable `Widget`s draw individual sections.
- **Displays** (`launchpad.display`) only know how to show a `Frame`. A
  `MockDisplay` runs anywhere for development; an `EinkDisplay` drives the real
  panel on the Pi.
- **Composition** (`launchpad.app`, `launchpad.factory`) wires concrete
  collaborators together based on `Settings`. Everything else depends only on
  abstractions.

This separation is what makes the system extensible: adding a feature means
adding a model + service (+ optional widget) without touching the core, and
swapping orientation or hardware means choosing a different renderer or display.

## Project structure

```
src/launchpad/
├── app.py                  # Dashboard orchestrator (composition root)
├── factory.py              # Build collaborators from settings
├── __main__.py             # `python -m launchpad` entry point
├── config/
│   ├── settings.py         # Settings dataclasses
│   └── features.py         # Experimental feature flags
├── models/
│   ├── geometry.py         # Orientation, Size, Region
│   ├── dashboard.py        # DashboardState (the render view-model)
│   ├── train.py            # Core
│   ├── weather.py          # Core
│   ├── calendar.py         # Core
│   └── experimental/       # nba, fantasy, baby
├── services/
│   ├── base.py             # DataService[T] interface, ServiceError
│   ├── core/               # train, weather, calendar services
│   └── experimental/       # nba, fantasy, baby services
├── rendering/
│   ├── base.py             # Renderer interface
│   ├── frame.py            # Frame (renderer → display boundary)
│   ├── portrait.py         # PortraitRenderer
│   ├── landscape.py        # LandscapeRenderer
│   └── widgets/            # per-section drawers
└── display/
    ├── base.py             # Display interface
    ├── mock_display.py     # Dev/preview display
    └── eink_display.py     # Real e-ink panel
tests/
├── unit/
└── integration/
```

## Requirements

- Python 3.13+

## Getting started

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Run the tests (placeholders are skipped until functionality lands):

```bash
pytest
```

Run the dashboard (not implemented yet):

```bash
python -m launchpad
```

## Roadmap

1. Implement core services (train, weather, calendar) against a mock display.
2. Implement the portrait renderer and core widgets.
3. Add the e-ink display driver on the Raspberry Pi.
4. Layer in experimental features behind their flags.

## License

MIT
