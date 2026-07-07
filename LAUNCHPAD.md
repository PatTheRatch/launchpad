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

Current documentation reality:
- `README.md` is partially outdated and still describes the project as a scaffold
- actual code now includes working orchestration, portrait rendering, live train/weather integrations, and a mock display pipeline

`LAUNCHPAD.md` is the canonical operational reference and should be kept more current than marketing/project-summary docs.

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
- time-of-day dashboard modes
- optional mock World Cup section behind feature flag

### Partial / stubbed
- landscape renderer
- e-ink hardware display driver
- real calendar integration
- real NBA integration
- real fantasy basketball integration
- real baby tracking integration
- checked-in service/deployment automation

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
- `eink`:
  - class exists
  - real hardware behavior is not yet implemented

Current production implication:
- the codebase is ready for PNG/mock rendering workflows
- it is not yet fully ready for direct real-panel operation without completing the e-ink driver

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
- `/opt/launchpad/pyproject.toml`
- `/opt/launchpad/requirements.txt`
- `/opt/launchpad/.env.example`
- `/opt/launchpad/docs/PROJECT_VISION.md`
- `/opt/launchpad/docs/ESPN_ACCESS_HANDOFF.md`

Source:
- `/opt/launchpad/src/launchpad/`

Tests:
- `/opt/launchpad/tests/`

Assets:
- `/opt/launchpad/assets/fonts/`

Preview output:
- `/opt/launchpad/dashboard.png`

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

Current `.env.example` only documents:
- `TFL_APP_KEY`

Future improvement:
- expand `.env.example` so it reflects all supported runtime configuration that should be user-configurable

## 12. Dependencies

Declared package model:
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

Important current note:
- the repository's `.venv` does not currently appear fully provisioned for the declared workflow
- observed missing tools/modules include:
  - `pytest`
  - `httpx`
  - `python-dotenv`
  - `ruff`
- `launchpad` also does not appear installed editable into the current venv

This means code and packaging metadata are ahead of the currently provisioned environment.

## 13. Current run / deploy process

### What the code supports today
One-shot render:
```bash
cd /opt/launchpad
source .venv/bin/activate
PYTHONPATH=src python -m launchpad
```

Continuous mode:
```bash
cd /opt/launchpad
source .venv/bin/activate
LAUNCHPAD_RUN_FOREVER=1 PYTHONPATH=src python -m launchpad
```

Installed CLI form (once package is installed):
```bash
launchpad
```

### Current deployment reality
Intended deployment target:
- Raspberry Pi
- long-running Python process
- systemd-managed

Current repo state:
- no checked-in systemd unit file
- no checked-in deploy script
- no checked-in restart/update automation

So deployment is currently a design intent rather than a documented, repo-backed operational process.

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
PYTHONPATH=src python -m launchpad
```

Run continuously:
```bash
cd /opt/launchpad
source .venv/bin/activate
LAUNCHPAD_RUN_FOREVER=1 PYTHONPATH=src python -m launchpad
```

Future test command once dev dependencies are installed:
```bash
cd /opt/launchpad
source .venv/bin/activate
pytest
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

### App environment not fully provisioned
Symptoms may include missing imports for:
- `httpx`
- `dotenv`
- `pytest`
- `ruff`

Likely cause:
- `.venv` exists but does not match the project's declared dependency model yet

### README is partially outdated
Do not rely on README alone for current feature status.
Prefer:
- code
- tests
- this document

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
- some placeholder/skipped tests remain
- integration testing is not yet meaningfully completed

## 17. Current roadmap

Near-term priorities suggested by current repo state:
1. document the real current operational state
2. provision the Python environment consistently
3. add a real deployment/service definition
4. replace mock calendar with real calendar integration
5. implement the real e-ink display driver
6. decide whether landscape mode is genuinely needed
7. keep experimental features isolated behind flags

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
