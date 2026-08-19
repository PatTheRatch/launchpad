# Launchpad — Agent Handoff

> **Audience:** AIsha (Hermes-powered collaborator) and any other agent operating Launchpad.
> **Written:** 2026-08-19, after a full Raspberry Pi rebuild.
> **Companion docs:** [`LAUNCHPAD.md`](../LAUNCHPAD.md) is the canonical system reference
> (architecture, commands, config). This document covers *current state*, *how to get in*, and
> *what recently changed* — the things a fresh operator needs that the reference assumes.

---

## 1. What Launchpad is

A Raspberry Pi 5 e-ink dashboard mounted near the front door. It shows train departures,
weather, the day's calendar, and the baby's last feed on a Waveshare 7.5" V2 panel
(800×480 native, driven in portrait at 480×800).

Treat it as a **household appliance, not a dev server**. The operating priorities, in order:

1. It must not crash. A failing feature degrades to a placeholder; it never takes the panel down.
2. It must be readable in a five-second glance from 1–3 metres.
3. It must recover from failure without a human at the front door.

---

## 2. Current state — READ THIS FIRST

| | |
|---|---|
| Repo | `https://github.com/PatTheRatch/launchpad` |
| Default branch | `main` |
| HEAD at handoff | `d838a57` — *chore(deploy): run the services as a launchpad service account* |
| Checkout on the Pi | `/opt/launchpad` |
| Config UI | `http://launchpad:8080` (over Tailscale) |
| Tests | 216 passing, 1 skipped (the skip is the Pi-only Waveshare driver, expected off-hardware) |
| Checks | `ruff check .` and `mypy src` (strict) both clean |

**The Pi was rebuilt from bare metal on 2026-08-19.** The previous 16 GB drive filled up and
permissions were damaged; the drive was replaced and everything erased. The rebuild is complete
and the dashboard is reported running, but *this state has not been independently verified from
outside the Pi* — **run §7 before assuming anything about live state.**

### Recent history on `main`

```
d838a57  chore(deploy): run the services as a launchpad service account
80160c1  Merge PR #2 — five alternative panel layouts
195185e  feat: five alternative panel layouts, selectable from the config UI
dbb3beb  Merge PR #1 — Huckleberry feed + live preview + hardening
29e399c  fix: harden Huckleberry feed service against silent and crashing failures
6f01d5e  feat: live mode preview and cycling in the config web UI
544f60e  feat: live "last feed" section from Huckleberry baby tracking
```

---

## 3. How to get in

### Network — Tailscale

The Pi is a Tailscale node named **`launchpad`** with MagicDNS. It is *not* exposed to the public
internet and may not be reachable on the LAN by hostname. Everything goes over the tailnet:

```bash
ssh <operator>@launchpad          # shell
curl http://launchpad:8080/api/config    # config API
```

Tailscale SSH is enabled (`tailscale up --ssh`) as the human break-glass path.

> **Agent access note.** Tailscale's default SSH policy uses `"action": "check"`, which requires an
> interactive browser re-authentication. An unattended agent cannot complete that. Agent accounts
> should use a **normal SSH keypair against the Pi's `sshd`** (`~/.ssh/authorized_keys`), keeping
> agent access and human break-glass on separate mechanisms. If SSH hangs or fails for you, this is
> the first thing to check.

### Identity model — who runs it vs. who may change it

This changed in `d838a57` and is the most important operational fact in this document:

- **`launchpad`** — a no-login system account (`--shell /usr/sbin/nologin`) that **owns
  `/opt/launchpad` and runs both services**. Member of `spi` and `gpio` so it can drive the panel.
  Nothing logs in as this account.
- **Operator accounts** — humans and agents (`patrick`, `aisha`, …) are members of the
  `launchpad` **group**. They edit the repository and restart services; they do not run them.

Adding an operator is one command, with no service or repo change:

```bash
sudo usermod -aG launchpad <user>     # takes effect on next login
```

### What an operator account may do with sudo

Exactly two commands, granted to the group in `/etc/sudoers.d/launchpad`:

```
%launchpad ALL=(root) NOPASSWD: /usr/bin/systemctl restart launchpad
%launchpad ALL=(root) NOPASSWD: /usr/bin/systemctl status launchpad
```

**Do not widen this.** The device is on the tailnet and holds live credentials; an unattended agent
account with blanket root is a far larger blast radius than a restart button needs. If you believe
you need more, raise it with Patrick rather than editing sudoers.

### Secrets

`/opt/launchpad/.env` is **gitignored** and is the only content git cannot restore. It holds:

- `TFL_APP_KEY`
- `HUCKLEBERRY_EMAIL`
- `HUCKLEBERRY_PASSWORD`

Ownership matters: `launchpad:launchpad`, mode `640`. At `600` owned by an operator, both services
start normally and then *silently* fail to read them — trains and feeds render as "unavailable"
with no error. Every member of the `launchpad` group can read this file; that is the intended trust
model. **Never commit it, never paste its contents into an issue, PR, chat, or log.**

---

## 4. Layout of the machine

| Path | What |
|---|---|
| `/opt/launchpad` | The one canonical checkout. Do **not** create clones under `/home/*`. |
| `/opt/launchpad/.venv` | Virtualenv, created with `--system-site-packages` |
| `/opt/launchpad/.env` | Secrets (gitignored) |
| `/opt/launchpad/config.json` | Persistent settings — **tracked in git**, written by the config UI |
| `/opt/e-Paper` | Waveshare vendor driver, symlinked into the venv |
| `/etc/systemd/system/launchpad.service` | The dashboard loop |
| `/etc/systemd/system/launchpad-config.service` | The config UI on :8080 |

The venv **must** be created with `--system-site-packages` so the apt-installed `spidev` and
`lgpio` are visible. Install with all extras:

```bash
.venv/bin/pip install -e ".[dev,render,tfl,web,baby]"
```

Extras are load-bearing: `render`→Pillow, `tfl`→httpx + python-dotenv (this is what reads `.env`),
`web`→Flask, `baby`→`huckleberry-api`.

---

## 5. Operating it

```bash
# state
systemctl status launchpad launchpad-config --no-pager
journalctl -u launchpad -f

# restart after a change
sudo systemctl restart launchpad

# one-shot render, no service involved
cd /opt/launchpad
LAUNCHPAD_DISPLAY_DRIVER=mock .venv/bin/python -m launchpad   # writes dashboard.png, safe
LAUNCHPAD_DISPLAY_DRIVER=eink .venv/bin/python -m launchpad   # drives the real panel

# checks — run all three before any push
.venv/bin/python -m pytest -q
.venv/bin/ruff check .
.venv/bin/mypy src
```

### Deploying a change

```bash
cd /opt/launchpad && git pull && sudo systemctl restart launchpad
```

If dependencies changed, re-run the `pip install -e` line first.

### The config UI (`http://launchpad:8080`)

Reads and writes `config.json`, and can restart the dashboard. It also has a **Live Preview** that
renders real frames in the browser — this is the best end-to-end test available, because it
exercises the services, builder, and renderer in one click without touching the panel.

- **Time of day** chips: force any mode (`auto`/`morning`/`daytime`/`evening`/`overnight`).
- **Layout** chips: preview any of the six layouts.
- **Cycle** buttons: step through modes or layouts automatically.
- **Send this view to the panel**: saves layout + mode override and restarts the service. This is
  the only preview control that touches the panel.

API, if driving it programmatically:

```bash
GET  /api/config
POST /api/config                              # full config object, validated
GET  /api/preview/<mode>.png?layout=<layout>  # &refresh=1 to bypass the 60s data cache
POST /api/restart
```

---

## 6. Architecture orientation

```
Services → Result → DashboardStateBuilder → DashboardState → Renderer → Frame → Display
```

**Non-negotiable conventions.** Match these; they are what keep the appliance from crashing:

- Models are immutable `@dataclass(frozen=True, slots=True)`.
- Services only retrieve data, and **isolate their own failures** — every error becomes
  `ServiceError`. Never let another exception type escape a service.
- The orchestrator (`app.py`) wraps every service call in a `Result`
  (`present` / `empty` / `unavailable`). The renderer draws placeholders; nothing raises upward.
- `builder.py` is **pure**: no I/O, no clock reads, no exception handling. Per-mode layout and
  priority live only in `MODE_SECTIONS` there — no per-mode `if` statements anywhere else.
- Experimental features are feature-flagged and cannot affect core sections.

### Key modules

| File | Role |
|---|---|
| `app.py` | Orchestration; `collect_inputs()` / `collect()` / `run_forever()` |
| `factory.py` | Composition root. `build_services()`, `build_renderer()`, `PORTRAIT_LAYOUTS` |
| `builder.py` | Pure state builder, `MODE_SECTIONS`, `ALWAYS_VISIBLE_WHEN_ENABLED` |
| `rendering/painter.py` | Region-bounded drawing primitives shared by every layout |
| `rendering/summaries.py` | **What each section says**, as pure text — shared by every layout |
| `rendering/portrait.py` | The `classic` layout |
| `rendering/layouts.py` | The five alternatives |
| `config_server/preview.py` | Live preview rendering + 60s service-data cache |
| `services/experimental/huckleberry_baby_service.py` | Feed integration |

**If you change what a section *says*, change it in `summaries.py`** — all six layouts read from
there, so the edit lands everywhere at once. `layouts.py` and `portrait.py` handle *arrangement
only*.

### Modes and sections

Modes resolve in Europe/London: morning 07–09, daytime 09–17, evening 17–22, overnight 22–07.
`Section.BABY` appears in **all four** modes (a newborn feeds around the clock).

### Layouts

Set via `display.layout` in `config.json`, or `LAUNCHPAD_DISPLAY_LAYOUT`. All six draw the same
content and differ only in arrangement:

`classic` (default, stacked full detail) · `compact` (one ledger row per section) ·
`hero` (one large number per mode — next train by day, feed timer at night) ·
`slots` (fixed zones; feed and weather never move) · `cards` (lists + stat tiles) ·
`timeline` (the day on one vertical axis)

Recommendation on file: **`hero` during the newborn months**, `slots` as the end-state.

---

## 7. Verify live state yourself

Do not trust §2 — confirm:

```bash
ssh <operator>@launchpad
systemctl is-active launchpad launchpad-config      # expect: active / active
cd /opt/launchpad && git log --oneline -1           # expect d838a57 or later
git status --short                                  # expect clean
.venv/bin/python -m pytest -q                       # expect 216 passed, 1 skipped
journalctl -u launchpad --since "1 hour ago" | tail -30
curl -s -o /dev/null -w '%{http_code}\n' http://launchpad:8080/api/config    # expect 200
```

A rendered preview is the strongest single check:

```bash
curl -s -o /tmp/preview.png "http://launchpad:8080/api/preview/auto.png"
file /tmp/preview.png     # expect: PNG image data, 480 x 800, 1-bit
```

---

## 8. Traps — all of these cost real time to rediscover

1. **Python 3.13 is required** (`requires-python = ">=3.13"`). Raspberry Pi OS on Debian 13
   "Trixie" ships it; Bookworm's 3.11 will not install the package.
2. **`huckleberry-api` is pinned to `0.2.2`.** Versions 0.2.3+ require Python 3.14. Do not upgrade.
3. **The venv needs `--system-site-packages`** or the panel driver cannot see `spidev`/`lgpio`.
4. **Pi 5 uses `lgpio`, not `RPi.GPIO`** — the GPIO hardware changed and the old library simply
   does not work. GPIO/`gpiochip` errors point here.
5. **`.env` must be `launchpad:launchpad` mode `640`** (see §3) or credentials silently fail.
6. **The shared checkout needs `git config core.sharedRepository group`**, or git writes files at
   `644` and other operators can read but not edit them. This is what caused the original
   permissions damage.
7. **`huckleberry-api` swallows Firestore errors** and returns an empty list. The service therefore
   treats an *empty* 7-day lookback as `ServiceError`, not as "no feeds" — a newborn always has
   feeds, so empty means the backend failed. Do not "fix" this by returning an empty snapshot; it
   would show a confidently wrong "No feeds logged yet".
8. **Time since feed is measured from when the feed *ended***: breast = start + both durations,
   bottle = start (parents log a bottle at finish).
9. **If apt reports "dpkg was interrupted"**, run `sudo dpkg --configure -a` then
   `sudo apt-get -f install`. Never delete `/var/lib/dpkg/lock*` — that turns a recoverable state
   into a corrupted package database.
10. **A Pi 5 with an external drive needs the 27 W supply.** Under-powering shows up as the machine
    resetting during sustained I/O (`vcgencmd get_throttled` should read `0x0`).

---

## 9. Open items

- **`.env` has no backup by default.** It is the single point of failure that made the last rebuild
  painful. Confirm a copy exists off the Pi.
- **Calendar is still `MockCalendarService`** — real calendar integration is unimplemented.
- **Landscape renderer is a stub** that raises `NotImplementedError`.
- **The Huckleberry API is unofficial** and may break without notice. Keep the `unavailable`
  fallback path healthy; the section is designed to degrade to "Feeds unavailable", never to crash.
- **Single child only** — `childList[0]`. Multi-child is future work.
- Feature flags currently available: `nba`, `fantasy_basketball`, `baby_tracking`, `world_cup`.
  NBA is live; fantasy is a placeholder; World Cup is mock data.

---

## 10. Working agreements

- Branch for changes; do not push directly to `main` unless Patrick asks.
- Run `pytest`, `ruff check .`, and `mypy src` before every push. All three must be clean.
- Never commit `.env`, credentials, or rendered `*.png`.
- Prefer fixing the root cause over widening permissions.
- When something is broken, report it plainly with the actual output rather than a summary.
