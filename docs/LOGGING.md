# Logging Feeds from Your Phone

Launchpad can now *write* to Huckleberry, not just read: bottles, diapers,
and the sleep timer, via `POST /api/log/<kind>` on the config server. Combined
with iOS Shortcuts this replaces the app for the everyday cases — one tap on a
widget, or "Hey Siri, log a bottle", while holding the baby.

Everything logged this way is **also mirrored to SQLite on the Pi**
(`data/logbook.db`), so Launchpad keeps its own copy of the history,
independent of the unofficial backend.

## The endpoints

```bash
# a finished bottle (bottle_type: "Formula" | "Breast Milk"; default Formula)
curl -X POST http://launchpad:8080/api/log/bottle \
  -H 'Content-Type: application/json' -d '{"amount_ml": 60}'

# a diaper change (mode: "pee" | "poo" | "both" | "dry"; optional "notes")
curl -X POST http://launchpad:8080/api/log/diaper \
  -H 'Content-Type: application/json' -d '{"mode": "both"}'

# the sleep timer (action: "start" | "complete" | "cancel")
curl -X POST http://launchpad:8080/api/log/sleep \
  -H 'Content-Type: application/json' -d '{"action": "start"}'
```

A success answers `{"status": "ok", "kind": …, "logged": {…}}` and the
dashboard preview, nightstand page, and widget pick the new event up on their
next poll (the shared cache is invalidated on every successful write).

With real-time watching active (see `docs/REALTIME.md`) the nightstand page
updates within a second of *anyone* logging — you, your wife in the app, or a
shortcut — instead of waiting out a poll.

**Semantics that matter:**

- **Writes are never retried server-side.** A failure returns an error and a
  human decides whether to tap again — an automatic retry of `log_bottle`
  would be a *duplicate feed* in your daughter's history, not a no-op.
- Sleep is a timer, not an event: `start` it when she goes down, `complete`
  it when she wakes (or `cancel` to discard). Completing with no timer
  running is reported as an upstream error — nothing is invented.
- Requires the `baby_tracking` flag and Huckleberry credentials, else `503`.

## iOS Shortcuts (the recommended path)

Shortcuts needs no code, and one shortcut gives you all four surfaces at
once: a home-screen icon, a home-screen *widget* with buttons, Siri, and the
Action Button. The phone must be on Tailscale, same as the nightstand page.

Create one shortcut per action. For **Log 60ml Bottle**:

1. Shortcuts app → **+** → rename to "Log 60ml Bottle".
2. Add action **Get Contents of URL**:
   - URL: `http://launchpad:8080/api/log/bottle`
   - Show More → Method **POST** → Request Body **JSON** →
     add field `amount_ml` = Number `60`.
3. Add **Get Dictionary from Input**, then **Get Dictionary Value** for key
   `status`, then an **If** on it: "ok" → **Show Notification** "Logged 60ml
   bottle ✓"; Otherwise → **Show Notification** "Failed — open Launchpad".
4. Say "Hey Siri, log sixty mil bottle" — the shortcut's name *is* the Siri
   phrase, so name it something you can say while holding a baby.

Duplicate it for the amounts you actually use (60/90/120), for
`/api/log/diaper` with `mode`, and for sleep `start`/`complete`. Then
long-press the home screen → **Shortcuts widget** → pick a folder of these,
and you have a tap-to-log grid — the thing the Huckleberry widget charges for.

For a variable amount, add **Ask for Input** (Number) as the first action and
pass the result into `amount_ml`. Slower, but one shortcut covers everything.

## Scriptable alternative

`docs/scriptable/LogFeed.js` is an interactive logger for Scriptable: run it
(or add it as a widget tap target) and it presents amount choices, asks for
confirmation, POSTs, and shows the result. Same endpoint, same semantics.

## Trust model, stated plainly

The config server has **no authentication** — these endpoints accept a POST
from anything that can reach port 8080. Today that is the tailnet (plus the
Pi's LAN address if exposed), which is the existing trust model for
`/api/restart` and the config UI. Everyone on your tailnet is family; if that
ever changes, add auth before adding people.

## Verifying your first write

Do one deliberate test rather than trusting it blind:

1. `curl` a bottle with an obviously fake amount (e.g. `{"amount_ml": 1}`).
2. Open the Huckleberry app and confirm a 1ml bottle appeared.
3. Delete it in the app, and log a real one from a shortcut.

The mirror can be inspected on the Pi at any time:

```bash
sqlite3 /opt/launchpad/data/logbook.db \
  'SELECT logged_at, kind, payload FROM events ORDER BY id DESC LIMIT 10;'
```
