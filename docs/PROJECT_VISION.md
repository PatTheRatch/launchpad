# Launchpad Project Vision & Planning

## What is Launchpad?

Launchpad is a Raspberry Pi powered e-ink dashboard designed to live near the front door of our home and provide useful information that helps our family start the day smoothly.

The goal is not to build a flashy smart home gadget. The goal is to create a simple, reliable family information hub that subtly improves our daily lives.

Success is defined by this question:

> **One year from now, do I still look at this screen every day, and does it add value to my life?**

If the answer is yes, Launchpad is successful.

---

# Project Philosophy

Launchpad should be:

- Useful
- Reliable
- Easy to glance at
- Family-friendly
- Extensible

Launchpad should **not** become:

- A Bloomberg Terminal
- A distraction
- A maintenance burden
- A collection of random features

The dashboard should provide answers to important daily questions:

- When should I leave?
- What trains are coming?
- What's the weather today?
- What is on my calendar?
- Is there anything fun or important happening?

The ideal interaction:

1. Walk by the dashboard.
2. Glance at it for 5 seconds.
3. Get the information needed.
4. Continue with the day.

---

# Users

## Primary User

Patrick

Use cases:

- Daily London commute
- Checking train times
- Calendar awareness
- Weather awareness
- Basketball updates

## Secondary User

Patrick's wife

Future use cases:

- Shared family calendar
- Family logistics
- Baby-related information

Future features should consider usefulness for both users.

---

# Dashboard Location

Planned location:

- Near the front door
- Around the shoe cabinet area

Reason:

This is where commute information is most useful and naturally fits into existing daily routines.

Mounting approach:

- Initial assumption: leaning on top of the shoe cabinet
- Future possibility: wall mounting after discussion with wife

---

# Hardware Purchased

## Raspberry Pi Components

Purchased:

- Raspberry Pi 5 (4GB RAM)
- Official Raspberry Pi 27W USB-C Power Supply
- Official Raspberry Pi Case
- Existing microSD card (already owned)

## Display

Purchased:

- Waveshare 7.5-inch Black and White E-Ink Display HAT

Reasoning:

Originally considered LED matrix displays.

Ultimately chose e-ink because:

- Cleaner aesthetics
- Better fit for home environment
- Lower power consumption
- Better "wife acceptance factor"
- Supports a calm, glanceable experience

---

# Core Dashboard Features (MVP)

These features should always work.

If experimental features fail, these should continue functioning.

## 1. Train Departures

Highest priority feature.

Stations:

### Elizabeth Line

- Custom House

### DLR

- Royal Victoria

### Jubilee Line

- Canning Town

Display:

- Next two departures for each station

Future enhancements:

- Commute recommendations
- Leave-by calculations

---

## 2. Weather

Display:

- Current temperature
- Weather condition
- Possibly high/low temperatures

Purpose:

Helps prepare before leaving home.

---

## 3. Calendar

Planned integration:

- Shared family calendar

Display:

- Upcoming events
- Important appointments
- Daily reminders

Future use:

- Family scheduling
- Baby appointments
- Travel reminders

---

# Experimental Features

These features are valuable but should never impact core dashboard reliability.

---

## Basketball

Desired features:

### Cleveland Cavaliers

- Next game
- Opponent
- Start time

### Fantasy Basketball

Potential future integrations:

- Current matchup score
- Team performance
- League standings

Existing fantasy basketball codebase may be integrated later.

---

## Baby Dashboard

Not a priority for MVP.

Future possibilities:

### Pull from existing baby tracking apps

Preferred option.

Potential apps:

- Huckleberry
- Nara Baby
- Other baby tracking applications

Possible information:

- Last feeding
- Sleep information
- Diaper changes

### Manual tracking

Possible approaches:

- Simple web interface
- Physical buttons

Current status:

Deferred until real-world need becomes clearer.

---

## Smart Home Integration

Potential future consideration.

Current status:

Not planned for MVP.

Potential integrations:

- Home Assistant
- Nursery temperature
- Household status indicators

---

# Dashboard Behavior

## Adaptive Dashboard

The dashboard should adapt throughout the day.

### Morning (Primary Use Case)

Focus:

- Train departures
- Calendar events
- Weather
- Leave-by recommendations

---

### Evening

Focus:

- Tomorrow's calendar
- Basketball information
- Family information

---

# Refresh Schedule

E-ink displays benefit from less frequent refreshes.

Planned schedule:

## Commute Hours

7:00 AM to 9:00 AM

Refresh every:

- 5 minutes

Reason:

Train information remains useful and accurate.

---

## Daytime

9:00 AM to 5:00 PM

Refresh every:

- 15 minutes

Reason:

Information changes less frequently.

---

## Evening

5:00 PM to 10:00 PM

Refresh every:

- 10 minutes

Reason:

Sports and upcoming schedule become more relevant.

---

## Overnight

10:00 PM to 7:00 AM

Refresh every:

- 60 minutes

Reason:

Preserve display lifespan and reduce unnecessary updates.

---

# Display Layout

Preferred orientation:

- Portrait

Reasoning:

Better suited for front-door placement and information hierarchy.

Future possibility:

- Landscape mode support

Architecture should support both.

---

# Development Philosophy

Launchpad should optimize for:

> Core features are reliable while experimental features can evolve independently.

Reliability level:

### Option C

Core functionality should always work.

Experimental modules should be isolated.

Examples:

Good:

- Fantasy module unavailable
- Dashboard continues functioning

Bad:

- Fantasy module crashes
- Entire dashboard fails

---

# Development Approach

Cursor will be used heavily throughout development.

Development philosophy:

> Cursor is the junior developer. Patrick is the architect.

Approach:

- Small, focused prompts
- Incremental development
- Maintain understanding of system architecture
- Avoid generating massive amounts of code all at once

Estimated coding style:

- 80–90% vibe coding
- Human-guided architectural decisions

---

# Technical Stack

Development Environment:

- Cursor
- Python 3.13
- GitHub (private repository)

Testing:

- pytest
- Unit tests from the start

Containerization:

Initial phase:

- No Docker

Future consideration:

- Docker once the project stabilizes

Deployment:

Raspberry Pi running Python application as a systemd service.

---

# Architecture Principles

Separate concerns.

Data retrieval should not know about display hardware.

Rendering should not know where data comes from.

Display hardware should not know how data is generated.

Desired flow:

Data Sources

↓

Dashboard State

↓

Renderer

↓

Display Hardware

This architecture should make future features easy to add without impacting reliability.

---

# Proposed Folder Structure

launchpad/

src/

services/

models/

renderers/

display/

scheduler.py

main.py

tests/

assets/

docs/

README.md

pyproject.toml

requirements.txt

.env.example

---

# Development Roadmap

## Phase 1

Project scaffolding

- Folder structure
- Interfaces
- Models
- Mock implementations

---

## Phase 2

Mock dashboard generation

Generate dashboard images locally.

---

## Phase 3

Portrait renderer

Refine visual layout.

---

## Phase 4

Train integrations

Replace mock train data.

---

## Phase 5

Weather integration

Replace mock weather data.

---

## Phase 6

Calendar integration

Replace mock calendar data.

---

## Phase 7

Deploy to Raspberry Pi

---

## Phase 8

Integrate E-Ink display

---

## Phase 9

Experimental features

- Basketball
- Fantasy
- Baby integrations
- Smart home features

---

# Definition of Success

Launchpad succeeds if:

- It becomes part of the daily routine.
- It provides useful information quickly.
- It reduces friction in everyday life.
- It remains reliable.
- Patrick and his wife both find value in it.
- It still feels useful one year after launch.

The goal is not to build a cool gadget.

The goal is to build something that quietly makes life better.