# AIsha Real-Time Interaction with Launchpad

**Proposal — July 2026**

## What This Is

A proposal for how I (AIsha, your Hermes-powered collaborator) can interact with Launchpad in real time — not just SSH in on demand, but actively participate: monitor, alert, contribute content, and make Launchpad feel like a system we both operate together.

Right now, I can only touch Launchpad when you ask me to. This document lays out what it would look like if I could act on my own, in increments that respect the project's philosophy of reliability-first, isolated experimentation.

---

## Current State: What I Can Do Today

When you tell me to, I can:

- SSH into Launchpad via the `aisha` account
- Pull code, install dependencies, provision the venv
- Read logs, check service status, run diagnostics
- Edit code, commit, push
- Restart the systemd service
- Render a dashboard frame and inspect the output

All of this is **reactive** — it happens when you ask, not when the system needs it.

---

## Vision: What "Real-Time" Looks Like

The goal is that I become Launchpad's **operator**, not just its mechanic. In practice, this means three layers:

### Layer 1 — Observability (I can see what's happening)

I know the dashboard's state without you telling me:

- Is the service running? When was the last successful render?
- What's on the screen right now? (content snapshot)
- Are the APIs healthy? (TfL, Open-Meteo response status)
- Any errors or degraded sections?

### Layer 2 — Active Participation (I can put things on the dashboard)

I contribute content directly:

- Push a one-line notification to the dashboard ("Don't forget the nappies run")
- Surface awareness I have that Launchpad doesn't ("RMT strike announced for Thursday — check your trains")
- Add contextual notes to existing sections (weather advisory, calendar alert)

### Layer 3 — Autonomous Operation (I act without being asked)

I monitor and maintain:

- Proactive health checks — if the service is down, I notice and fix it (or tell you)
- Scheduled maintenance — weekly updates, log rotation checks, disk space monitoring
- Smart alerts via Telegram — but only when it matters (service down, API failing repeatedly, disk critical)
- Graduated autonomy — I take more initiative on routine things, less on disruptive things

---

## Technical Design

### New Section: AIsha Feed

The simplest, highest-impact addition: a dedicated dashboard section that I can write to.

```
┌──────────────────────┐
│  💬 AIsha            │
│                      │
│  Umbrella today —    │
│  rain from 3pm       │
│                      │
│  ⚠ RMT strike Thu   │
│  — check TfL site    │
└──────────────────────┘
```

**Implementation:**

```
src/launchpad/services/core/aisha_service.py   # reads from a local file
src/launchpad/models/aisha.py                  # AishaFeed model
src/launchpad/rendering/aisha_section.py       # renders the feed
```

The `AishaService` reads a simple JSON file at `/opt/launchpad/data/aisha_feed.json`:

```json
{
  "messages": [
    {"text": "Umbrella today — rain from 3pm", "level": "info"},
    {"text": "⚠ RMT strike Thursday — check TfL site", "level": "warning"}
  ],
  "updated_at": "2026-07-07T18:30:00+01:00"
}
```

This file is **my territory**. I write to it from my VPS via SSH. Launchpad just reads it at render time. This is the cleanest possible integration — no new protocols, no daemon on either side, no tight coupling. Just a file on disk that I own.

Messages auto-expire: I set a TTL per message, and the renderer drops expired ones. A daily "good morning" message doesn't hang around for three weeks.

**What I'd use it for:**

- Morning briefing: weather advisory, calendar highlight, one thing to remember
- Disruption alerts: tube strikes, line closures, severe weather
- Household notes: "Milkman tomorrow," "Bin collection moved to Friday"
- Sports: "Cavs vs Knicks tonight 7:30pm"

All driven by what I already know from our conversations, my web access, and the daily risk briefing I prepare.

### Health Monitoring via Cron

A cron job on my VPS that runs every 15 minutes:

```bash
# Pseudo: check Launchpad health
launchpad 'systemctl is-active launchpad.service'
launchpad 'stat /opt/launchpad/dashboard.png'  # last render timestamp
launchpad 'journalctl -u launchpad --since "15 min ago" | grep -i error | wc -l'
```

**What it does:**
- Service down for >2 checks → Telegram alert
- Dashboard stale (>3x refresh interval) → Telegram alert, attempt restart
- Errors in recent log → Telegram digest
- Disk above 80% → Telegram alert

**Configuration principles:**
- Telegram alerts only, not email — this is the interrupt-worthy channel per your standing instructions
- Alerts self-resolve: if the problem fixes itself, I tell you it recovered
- Rate-limited: no more than one alert per incident per hour

### Dashboard Content Snapshot

I can pull a snapshot of what's on the dashboard right now:

```
launchpad 'python -m launchpad'  # renders dashboard.png
scp aisha@launchpad:/opt/launchpad/dashboard.png /tmp/lp_snapshot.png
```

This means when you ask "what's on the dashboard?" I can actually show you, not just guess. On-demand only — no scheduled snapshots needed unless we have a reason.

### GitHub → Pi Deploy Pipeline

Right now: you merge a PR, then manually (or ask me to) `git pull` and restart. We can reduce that:

```yaml
# .github/workflows/deploy.yml (optional future)
on:
  workflow_dispatch:  # manual trigger from GitHub UI

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to Launchpad
        uses: appleboy/ssh-action@v1
        with:
          host: launchpad
          username: aisha
          key: ${{ secrets.AISHA_SSH_KEY }}
          script: |
            cd /opt/launchpad
            git pull origin main
            source .venv/bin/activate
            pip install -e ".[render,tfl]"
            sudo systemctl restart launchpad
```

Manual trigger only for now — safer. A bad commit shouldn't auto-deploy. We can add auto-deploy later with a health-check-based rollback.

---

## Implementation Plan

### Phase 1 — Observability (week 1)

**No dashboard code changes needed.** Pure ops on my side.

- Cron job: health check every 15 min
- Telegram alert on: service down, stale dashboard, API errors, disk space
- Command: `launchpad status` — a wrapper script I can run anytime

**Outcome:** I know when Launchpad is unhappy, and so do you (sparingly).

### Phase 2 — AIsha Feed Section (week 2)

New dashboard section. Isolated behind a feature flag like the other experimental sections.

- `data/aisha_feed.json` — the file I own
- `AishaService` — reads it, returns `Result[AishaFeed]`
- `AishaSection` in the portrait renderer — compact strip, inline text, optional icon per message level
- Feature flag: `LAUNCHPAD_FEATURE_AISHA`
- Cron job: daily morning message push (I generate context-aware content at 6:30am)

**Outcome:** I have a voice on the dashboard.

### Phase 3 — Deploy Pipeline (week 3)

- GitHub Actions workflow for manual deploy
- Deploy log so we can see what version is running
- (Optional) auto-deploy with post-deploy health check

### Phase 4 — Autonomous Operation (ongoing, after Phase 1–3 stabilize)

- Graduated autonomy rules document (what I can do without asking)
- Self-healing: auto-restart on known transient failures
- Weekly digest: what I did, what the dashboard did, any issues

---

## Design Decisions and Tradeoffs

### Why a file, not an API?

An HTTP endpoint on the Pi would mean another service, another port, more attack surface, more process management. The file approach:

- Zero new dependencies on the Pi
- Zero running processes beyond what already exists
- The file is my write surface; Launchpad reads it at render time
- If I can't write the file (SSH down), the dashboard shows whatever was last written — degrades gracefully

### Why Telegram for alerts, not dashboard notifications?

The dashboard is glanceable, not urgent. If Launchpad is down, the dashboard can't show anything anyway. Telegram is already your alert channel. One place to watch.

### Why a feature flag for the AIsha section?

Same pattern as World Cup / NBA / baby tracking. Experimental sections are isolated, can fail without affecting core, and are trivial to disable. If my feed section breaks, the rest of the dashboard keeps running. This is already the established architecture.

### Why not have me render entire dashboard frames?

Too heavy. I don't need to be the renderer — I just need a place to put a few lines of text. The Pi's job is to render physically. My job is to know things and contribute timely content.

---

## What This Doesn't Do

- **Doesn't change the dashboard's core reliability model.** The AIsha section is experimental, isolated, feature-flagged.
- **Doesn't require new hardware or services on the Pi.** One JSON file, read at render time. That's it.
- **Doesn't create noise.** Alerts are sparse and self-resolving. The feed is curated, not a firehose.
- **Doesn't replace you.** I propose, you decide. I operate within boundaries we agree on.

---

## Open Questions for Patrick

1. **Auto-deploy or manual deploy?** I lean manual for now, with an eye toward auto-deploy once we have a health-check-based rollback.
2. **How many feed messages max?** I'm thinking 2–3 most recent non-expired messages. Enough to be useful, not enough to dominate the screen.
3. **Feed position on dashboard?** Bottom strip (after core sections, optional). Or top under the header? I'd suggest bottom — core sections are the priority.
4. **What's the autonomy ceiling?** For Phase 1, I'll only alert. For Phase 4, I'd like to auto-restart the service on known transient failures. Where's your comfort line?

---

*Written by AIsha, July 2026.*
*This proposal is for Patrick's review. No code changes have been made.*
