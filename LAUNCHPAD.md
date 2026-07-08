# LAUNCHPAD

Canonical operations and architecture reference for the Launchpad home dashboard.

This document describes the current observed state of the system in `/opt/launchpad`, how it is intended to be operated, and what remains to be implemented.

## 1. Purpose

Launchpad is a Raspberry Pi-based home information hub designed to power a calm, glanceable e-ink dashboard near the front door.

Design goals:
- reliability
- simplicity
- maintainability
- low power usage
- graceful failure and easy recovery

Launchpad should behave like a household appliance, not a general-purpose development server.

## 2. Canonical project root

Project root:
- `/opt/launchpad`

Repository model:
- There is one shared canonical Git repository
- Patrick and AIsha both work against the same repository
- Do not create separate clones under `/home/patrick` or `/home/aisha` unless explicitly requested

Permissions model:
- shared Linux group: `launchpad`
- repository is group-writable for shared operation

## 3. Current repository status

Git remote:
- `origin = https://github.com/pattheratch/launchpad.git`

Default branch:
- `main`

Documentation roles:
- `README.md` — current project overview and quickstart (rewritten to match reality)
- `LAUNCHPAD.md` (this file) — canonical operator reference: system state, commands, deployment
- `docs/PROJECT_VISION.md` — long-term product direction and philosophy

## 4. Architecture overview

Current architecture:

Services -> Results -> DashboardStateBuilder -> Renderer -> Frame -> Display

Responsibilities:
- Services retrieve data only
- Models are immutable transfer objects
- Builder resolves dashboard mode and visible sections
- Renderer lays out a frame for the target orientation
- Display presents the frame to an output device

Key code paths:
- `src/launchpad/app.py` — dashboard orchestration
- `src/launchpad/factory.py` — composition root / concrete wiring
- `src/launchpad/builder.py` — pure state builder and mode logic
- `src/launchpad/rendering/` — layout/rendering
- `src/launchpad/display/` — output drivers
- `src/launchpad/services/` — data retrieval

## 5. Current implementation status

### Implemented now
- dashboard orchestration
- portrait renderer
- live TfL train integration
- live Open-Meteo weather integration
- mock calendar service
- mock PNG display output
- real e-ink display driver (Waveshare 7.5" V2, July 2026)
- web-based configuration UI (config.json + Flask server, July 2026)
- time-of-day dashboard modes
- optional mock World Cup section behind feature flag

### Partial / stubbed
- landscape renderer
- real calendar integration
- real NBA integration
- real fantasy basketball integration
- real baby tracking integration
- deploy/update automation (systemd unit is checked in; update flow is manual)

## 6. Current core services

### Trains
- provider: TfL arrivals API
- implementation: `MultiStationTrainService`
- configured stations:
  - Custom House
  - Royal Victoria
  - Canning Town
- supports direction filtering and line-status display
- optional `TFL_APP_KEY` supported via environment

### Weather
- provider: Open-Meteo
- implementation: `OpenMeteoWeatherService`
- current default location: London

### Calendar
- current implementation: `MockCalendarService`
- real calendar integration is not yet implemented

## 7. Experimental services

Feature flags exist for:
- NBA
- fantasy basketball
- baby tracking
- World Cup

Current state:
- only World Cup is wired in the factory today
- World Cup currently uses mock data, not a live external API
- NBA / fantasy / baby remain interface-level placeholders for future work

## 8. Display and rendering

### Rendering
- portrait rendering is implemented
- landscape rendering exists as a class but is not implemented

### Display drivers
- `mock`:
  - implemented
  - writes rendered PNG output to `dashboard.png`
- `eink` (implemented July 2026):
  - drives Waveshare 7.5" V2 panel (800×480)
  - lazy-imports hardware libraries so Mac dev environments never fail
  - set `LAUNCHPAD_DISPLAY_DRIVER=eink` to use real hardware
  - uses SPI (CE0) + GPIO pins (DC=25, RST=17, BUSY=24)
  - requires `aisha` user in `spi` and `gpio` groups

### Hardware setup
Waveshare library at `/opt/e-Paper/` (git clone), symlinked into venv.
Venv uses `--system-site-packages` for `spidev`/`RPi.GPIO` visibility.

One-shot render on hardware:
```
cd /opt/launchpad
PYTHONPATH=src LAUNCHPAD_DISPLAY_DRIVER=eink .venv/bin/python3 -m launchpad
```

### Configuration web UI
A Flask-based config server runs alongside the dashboard at
`http://launchpad.local:8080`. It reads/writes `config.json` (persistent
settings) and can restart the dashboard service. See `deploy/launchpad-config.service`.

## 9. Dashboard modes

Resolved in Europe/London time.

Modes:
- morning: 07:00–09:00
- daytime: 09:00–17:00
- evening: 17:00–22:00
- overnight: 22:00–07:00

Current section logic:
- morning/daytime: trains, calendar, weather, optional world cup
- evening: tomorrow calendar, optional experimental sections
- overnight: weather, tomorrow calendar

## 10. Important file locations

Top-level:
- `/opt/launchpad/README.md`
- `/opt/launchpad/pyproject.toml` (single source of dependency truth; `requirements.txt` was removed)
- `/opt/launchpad/.env.example` (documents every supported env var)
- `/opt/launchpad/deploy/launchpad.service` (systemd unit)
- `/opt/launchpad/docs/PROJECT_VISION.md`
- `/opt/launchpad/docs/ESPN_ACCESS_HANDOFF.md`

Source:
- `/opt/launchpad/src/launchpad/`

Tests:
- `/opt/launchpad/tests/`

Assets:
- `/opt/launchpad/assets/fonts/`

Preview output:
- `/opt/launchpad/dashboard.png` — generated by the mock display on each
  render; gitignored local artifact, never committed

## 11. Environment and configuration

Current environment variables implemented in code:
- `LAUNCHPAD_RUN_FOREVER`
- `LAUNCHPAD_DISPLAY_ORIENTATION`
- `LAUNCHPAD_DISPLAY_WIDTH`
- `LAUNCHPAD_DISPLAY_HEIGHT`
- `LAUNCHPAD_DISPLAY_DRIVER`
- `LAUNCHPAD_REFRESH_SECONDS`
- `LAUNCHPAD_FEATURE_NBA`
- `LAUNCHPAD_FEATURE_FANTASY_BASKETBALL`
- `LAUNCHPAD_FEATURE_BABY_TRACKING`
- `LAUNCHPAD_FEATURE_WORLD_CUP`
- `LAUNCHPAD_FORCE_MODE`
- `TFL_APP_KEY`

`.env.example` documents all of the above with defaults and comments; copy it
to `.env` and fill in. Note that `.env` loading requires `python-dotenv`
(installed via the `tfl` extra).

## 12. Dependencies

Declared package model (`pyproject.toml` is the single source of truth):
- base:
  - `tzdata`
- render extra:
  - `pillow`
- tfl extra:
  - `httpx`
  - `python-dotenv`
- dev extra:
  - `pytest`
  - `ruff`
  - `mypy`

Canonical provisioning (run from the repo root):
```bash
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
pip install -e ".[dev,render,tfl,web]"
```

`--system-site-packages` is required on the Pi so the Waveshare SPI/GPIO
libraries (`spidev`, `RPi.GPIO`/`lgpio`) are visible from the venv. On a Mac
dev machine, a plain `python3 -m venv .venv` is fine — the hardware driver
lazy-imports and will never be triggered.

`.venv` is intentionally untracked; it exists per-machine as an operational
convention, not a repo artifact.

## 13. Current run / deploy process

### Runtime modes
The app supports both, and one is the production standard:
- **one-shot render** (default): collect, render, write to the display, exit.
  This is the development workflow.
- **run-forever** (`LAUNCHPAD_RUN_FOREVER=1`): loop on
  `LAUNCHPAD_REFRESH_SECONDS`. This is how production runs under systemd.

With the package installed editable into the venv, no `PYTHONPATH`
manipulation is needed.

One-shot render:
```bash
cd /opt/launchpad
source .venv/bin/activate
python -m launchpad
```

Continuous mode:
```bash
cd /opt/launchpad
source .venv/bin/activate
LAUNCHPAD_RUN_FOREVER=1 python -m launchpad
```

Installed CLI form (equivalent to `python -m launchpad`):
```bash
launchpad
```

### Deployment (systemd)
Two unit files are checked in under `deploy/`:

**Dashboard** (`deploy/launchpad.service`):
Runs the dashboard continuously with `LAUNCHPAD_DISPLAY_DRIVER=eink` as
`User=aisha` / `Group=launchpad`, restarting on failure.

**Config UI** (`deploy/launchpad-config.service`):
Serves the web config UI on port 8080. Runs independently of the dashboard
process so configuration changes and restarts don't take down the UI.

```bash
sudo cp deploy/launchpad.service /etc/systemd/system/launchpad.service
sudo cp deploy/launchpad-config.service /etc/systemd/system/launchpad-config.service
sudo systemctl daemon-reload
sudo systemctl enable --now launchpad launchpad-config
journalctl -u launchpad -f
```

The config UI's "Restart Dashboard" button calls `sudo systemctl restart launchpad`.
For this to work, `/etc/sudoers.d/launchpad` must allow `aisha` passwordless sudo
for those commands:
```
aisha ALL=(root) NOPASSWD: /usr/bin/systemctl restart launchpad
aisha ALL=(root) NOPASSWD: /usr/bin/systemctl status launchpad
```

## 14. Common commands

Repository inspection:
```bash
cd /opt/launchpad
git -c safe.directory=/opt/launchpad status
git -c safe.directory=/opt/launchpad pull
git -c safe.directory=/opt/launchpad log --oneline -n 10
```

Environment inspection:
```bash
cd /opt/launchpad
source .venv/bin/activate
python -V
python -m pip list
```

Run app once:
```bash
cd /opt/launchpad
source .venv/bin/activate
python -m launchpad
```

Run continuously:
```bash
cd /opt/launchpad
source .venv/bin/activate
LAUNCHPAD_RUN_FOREVER=1 python -m launchpad
```

Tests and checks (require the `dev` extra):
```bash
cd /opt/launchpad
source .venv/bin/activate
pytest
ruff check .
mypy src
```

## 15. Troubleshooting notes

### Git "dubious ownership"
Symptom:
- git refuses to operate in `/opt/launchpad` for the `aisha` account

Observed workaround:
```bash
git -c safe.directory=/opt/launchpad status
```

This should eventually be resolved cleanly, but until then it is an operational quirk to remember.

### Missing imports (`httpx`, `dotenv`, `PIL`, `pytest`, `ruff`)
The venv was provisioned without the needed extras. Fix:
```bash
source .venv/bin/activate
pip install -e ".[dev,render,tfl]"
```

Note that a missing `python-dotenv` fails *silently*: the app runs but
ignores `.env` entirely (env vars set in the shell still work).

## 16. Testing state

Current test tree exists and is substantial, mostly unit-level.

Highlights:
- builder tests
- dashboard orchestration tests
- display tests
- TfL parsing/fetch behavior tests
- weather parsing/fetch behavior tests
- rendering tests
- world cup tests

Current gaps:
- tests are unit-level (with fakes/mock transports); no live-API or on-hardware
  integration tests yet

## 17. Current roadmap

Near-term priorities:
1. deploy systemd units to the Pi and run continuously on real hardware
2. replace mock calendar with real calendar integration
3. implement landscape renderer
4. replace mock World Cup with live data
5. add real NBA / fantasy / baby integrations behind feature flags
6. partial refresh support for the e-ink display
7. deploy/update automation (script or CI-triggered)
8. health-check/watchdog behaviour beyond systemd Restart=on-failure

## 18. Future ideas

Potential future features already aligned with project direction:
- shared family calendar integration
- improved commute guidance / leave-by logic
- market/portfolio intelligence section
- baby reminders/information
- shopping reminders
- selected smart-home status
- richer reliability and watchdog behavior
- update/restart automation for safe operations

## 19. Decisions recorded so far

- canonical shared repository location is `/opt/launchpad`
- no separate per-user clones should be created without explicit approval
- Launchpad should be operated as home infrastructure, not as a casual dev box
- architecture should favor isolation between core and experimental features
- documentation should reflect current reality, not just planned intent
