# The Phone as a Display

Two free ways to see "time since last feed" on an iPhone, both fed by the
config server on the Pi — no Huckleberry widget subscription involved.

Both need the **Tailscale app** installed and connected on the phone, so
`http://launchpad:8080` resolves anywhere (home WiFi or not).

## 1. Nightstand mode — `/display`

An always-on page designed for a phone propped on a nightstand: pure black
background (OLED pixels off), a huge elapsed-since-feed timer that ticks
locally every 10 seconds, and a night-vision red palette during overnight
mode so a 3am glance doesn't wreck anyone's dark adaptation.

Open **`http://launchpad:8080/display`** in Safari, then:

1. Share → **Add to Home Screen**, and launch it from that icon — it runs
   fullscreen, without Safari chrome.
2. Settings → Display & Brightness → **Auto-Lock → Never** (the page requests
   a wake lock, but that only works over HTTPS; Never is the reliable path).
3. Brightness slider all the way down, then for genuinely-3am dimness:
   Settings → Accessibility → Display & Text Size → **Reduce White Point**.
   Pair it with an Accessibility Shortcut (triple-click) to toggle.
4. Plug the phone in. An old spare phone is ideal for permanent duty —
   batteries dislike being pinned at 100% forever.

Details worth knowing:

- `?mode=overnight` forces the night palette regardless of the clock
  (useful for trying it out); by default the palette follows the dashboard's
  time-of-day mode.
- Tap anywhere to force a data refresh.
- The page drifts its content a few pixels every 90 seconds so a static
  layout can't burn into an OLED overnight.
- The footer shows when data was last fetched and flips to `stale · …` if
  the Pi stops answering — the page never silently shows old data as fresh.

## 2. Home-screen widget — Scriptable

A real iOS widget, free, via the [Scriptable](https://scriptable.app) app:

1. Install Scriptable from the App Store.
2. Create a new script and paste in `docs/scriptable/LastFeedWidget.js`
   (adjust `HOST` if your tailnet name differs).
3. **Run it inside Scriptable first** (the ▶ button). It previews the widget
   and logs to the console, so any problem shows a real reason before you
   put it on the home screen.
4. Long-press the home screen → add a **Scriptable** widget (small) →
   configure it to run the script.

### If the widget shows an error

The widget reports the actual cause on its face rather than failing opaquely:

| Widget says | Means | Fix |
|---|---|---|
| `HTTP 404` | The server is up but has no `/api/state.json` | The Pi is on older code: `cd /opt/launchpad && git pull && sudo systemctl restart launchpad-config` |
| `Got HTML` | Something answered, but with a web page | Usually the same as above, or `HOST` points somewhere else |
| `Unreachable` | The request never completed | Tailscale not connected on the phone, or the Pi is down |
| `No feed` | Server reached, nothing to report | Enable **Baby Tracking** in the config UI, or check the second line for "Feeds unavailable" |

Confirm the endpoint independently from any machine on the tailnet:

```bash
curl -i http://launchpad:8080/api/state.json | head -25
```

A `200` with JSON means the server side is fine and the problem is on the
phone (usually Tailscale, or a `HOST` typo). Anything else is the Pi.

> Scriptable's own error, *"The data couldn't be read because it isn't in the
> correct format"*, means it received something that is not JSON — almost
> always a Flask 404 page because the Pi has not pulled the code that adds
> the endpoint.

The elapsed time ticks live between refreshes — iOS renders the relative
timestamp natively, so the widget doesn't need to wake to stay current. iOS
refreshes the underlying data on its own schedule (typically every 5–15
minutes), which means a *newly logged* feed can take a few minutes to appear;
tapping the widget opens `/display` for the live view.

## Endpoint

Both clients consume `GET /api/state.json`:

```json
{
  "generated_at": "…", "fetched_at": "…", "mode": "overnight",
  "sections": [ {"section": "…", "title": "…", "line": "…", "lines": ["…"]} ],
  "feed": {
    "type": "formula", "ended_at": "…", "amount_ml": 80.0,
    "side": null, "duration_seconds": null, "detail": "Formula · 80ml"
  }
}
```

`feed.ended_at` is the timestamp clients tick from; `feed` is `null` when
tracking is off or the backend is unavailable (see the `baby` section entry
for which). `?mode=` forces a mode; `?refresh=1` bypasses the shared
60-second service-data cache — don't poll with it unconditionally.
