# Real-Time Updates

Launchpad can subscribe to Huckleberry's Firestore documents and learn about
changes as they happen, instead of discovering them on its next poll. When it
is working, a feed logged by anyone — you, your wife in the app, a Siri
shortcut — reaches the nightstand page in about a second.

**It is an accelerator, never a source of truth.** Everything underneath keeps
polling. If the watcher dies, the system gets slower, never wrong.

## Why it is built the way it is

Three properties of `huckleberry-api==0.2.2`, verified by reading it, shape
the design:

1. **Listener callbacks arrive on the Firestore SDK's own threads**, not an
   asyncio loop. The change handler must be thread-safe.
2. **Nothing refreshes the auth token in the background.** A listener left
   idle simply stops receiving events when its token expires (~1 hour), with
   no error — the worst possible failure for an appliance.
3. **`refresh_session_token()` recreates listeners but never clears the
   cached listener client**, so recreated listeners reuse credentials built
   from the *old* token.

Rather than trust that recovery path, `FeedWatcher` rebuilds each session from
scratch — new auth, new client, new listeners — **every 40 minutes**, safely
inside the token's lifetime. Failures are caught and retried with exponential
backoff (5s → 5min). Nothing propagates into the config server.

Two more details that would otherwise cause visible bugs:

- **The initial snapshot is ignored.** Firestore delivers the current document
  the moment you subscribe, so without suppression every 40-minute rebuild
  would look like a fresh feed.
- **Rapid repeats are throttled** to one notification per second, because a
  single logical write can produce several document updates.

## How a change reaches your phone

```
Huckleberry (someone logs a feed)
    │  Firestore push
    ▼
FeedWatcher                      background thread
    │  invalidate the data cache, then bump a version
    ▼
ChangeBroker ──► GET /api/events (SSE) ──► /display re-fetches /api/state.json
```

Clients receive a **version number, not the change itself**, and re-fetch
state through the normal endpoint. There is exactly one way state is produced,
so a pushed update can never disagree with a polled one.

The stream sends a heartbeat every 20 seconds and closes itself after 5
minutes; `EventSource` reconnects automatically, so a page left on all night
never pins a server thread indefinitely. The nightstand page shows a small dot
in the footer when the stream is connected, and keeps its 60-second poll
running regardless.

## Configuration

On by default when baby tracking is enabled and credentials are present.
To turn it off:

```bash
LAUNCHPAD_REALTIME=0
```

It starts from the server entry point, not at import, so importing the app
(in tests, or another process) never opens a network connection.

## Checking on it

```bash
curl -s http://launchpad:8080/api/realtime.json
```

```json
{"enabled": true, "connected": true, "sessions": 3, "changes": 11,
 "last_change_at": 1787000000.0, "last_error": null, "subscribers": 1, "version": 11}
```

- `connected: false` with a rising `sessions` count means it keeps
  reconnecting — check `last_error`.
- `enabled: false` means it never started: check the flag, the credentials,
  and that the `baby` extra is installed.
- Either way the dashboard keeps working on polling alone.

## What deliberately did *not* change

**The e-ink panel still refreshes on its own interval.** A full e-ink refresh
flashes the whole screen for a couple of seconds; doing that every time
someone logs a diaper would be worse than waiting a minute. The panel stays on
its schedule; the phone gets the instant updates.
