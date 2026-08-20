# Your Own Copy of the History

Steps 1 and 2 made Launchpad log feeds and see changes instantly. This step
makes the data **yours**: a complete local mirror of your child's care
history, kept current automatically, exportable at any time.

Until now the local store only held entries *Launchpad itself* wrote. Anything
your wife logged in the app, and every entry from before Launchpad existed,
lived only in Huckleberry. That is now closed.

## What is stored

`data/logbook.db` (SQLite on the Pi, gitignored) holds two tables:

| Table | What it is |
|---|---|
| `events` | An append-only audit of writes made *through* Launchpad. Never rewritten. |
| `intervals` | A mirror of the authoritative history — feeds, diapers, sleep — logged by **anyone**, in the app or here. |

Each mirrored row keeps both a normalized form (summary, amount, duration) and
the **raw upstream payload**, so a future self-hosted logger can migrate from
this file without losing anything today's mapping happens to drop.

Feeds are normalized through the same code the dashboard uses, so a feed means
exactly the same thing on the panel, in the mirror, and in an export.

## How it stays current

One background thread:

1. **Backfills 120 days** once at startup, so the archive begins populated.
2. **Re-syncs the last 2 days** every 15 minutes.
3. **Syncs immediately when poked** — the real-time watcher pokes it, so
   anything logged by anyone lands in the mirror within seconds.

### The identity problem, and how reconciliation handles it

Feed and diaper entries carry **no stable id** upstream (only sleep does), so
the mirror keys on `(kind, start)` — one child cannot start two feeds in the
same second — and uses `lastUpdated` to decide which version wins.

That gives correct behaviour in all four cases:

| Upstream | Mirror |
|---|---|
| New entry | added |
| Unchanged | left alone (no write) |
| **Edited in the app** | **updated in place, never duplicated** |
| **Deleted in the app** | **removed** |

**Reconciliation is bounded to the synced window.** A routine 2-day sync only
reconciles the last 2 days, so it can never wipe months of archive. This is
covered by a test, because the failure would be silent and catastrophic.

## Endpoints

```bash
# what's mirrored, and how the last run went
curl -s http://launchpad:8080/api/sync.json

# mirrored history (days, kind filters, limit)
curl -s "http://launchpad:8080/api/history.json?days=7&kind=feed"

# sync right now; ?days= overrides the window (use for a bigger backfill)
curl -X POST "http://launchpad:8080/api/sync?days=365"

# the payoff: take your data
curl -s "http://launchpad:8080/api/export.csv" -o launchpad-history.csv
```

The CSV is one row per event with `kind, started_at, ended_at, summary,
amount_ml, duration_minutes, notes` — readable in any spreadsheet, and the
thing to hand a pediatrician who asks about feeding patterns.

## Configuration

On by default when baby tracking is enabled and credentials exist.
`LAUNCHPAD_SYNC=0` disables it. Like real-time watching, it starts from the
server entry point, not at import, so importing the app never opens a
connection.

Mirroring is best-effort: failures are recorded in `/api/sync.json` and
retried. **The mirror falling behind makes the archive stale, never the
dashboard wrong** — the dashboard reads live data, not this table.

## Inspecting it directly

```bash
sqlite3 /opt/launchpad/data/logbook.db \
  "SELECT datetime(start,'unixepoch','localtime'), kind, summary
   FROM intervals ORDER BY start DESC LIMIT 20;"
```

## Backing it up

This file is the one piece of Launchpad that cannot be recreated from GitHub.
Worth a periodic copy off the Pi:

```bash
sqlite3 /opt/launchpad/data/logbook.db ".backup '/tmp/logbook-backup.db'"
```

(`.backup` is safe to run while the server is writing; copying the file
directly is not.)

## Why this matters

The Huckleberry API is unofficial and could break or disappear. When that
happens, the history logged up to that point is already here, in an open
format, on hardware you own — which turns "we lost everything" into "we point
Launchpad at a different backend."
