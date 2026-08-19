// Launchpad "Last Feed" home-screen widget — for the free Scriptable app (iOS).
//
// Shows how long since the baby's last feed, ticking live on the home screen,
// fed by your own Launchpad server instead of Huckleberry's paid widget.
//
// Setup: see docs/NIGHTSTAND.md in the Launchpad repo. Requires the Tailscale
// app to be connected so the phone can reach the Pi.

const HOST = "http://launchpad:8080"; // your Pi, over Tailscale (MagicDNS name)

const NIGHT = { bg: "#000000", ink: "#B3402E", dim: "#6E2A20" };
const DAY = { bg: "#000000", ink: "#C9C3B8", dim: "#6E6A62" };

let state = null;
try {
  const request = new Request(`${HOST}/api/state.json`);
  request.timeoutInterval = 10;
  state = await request.loadJSON();
} catch (error) {
  // Leave state null; the widget renders its unavailable form below.
}

const palette = state && state.mode === "overnight" ? NIGHT : DAY;
const widget = new ListWidget();
widget.backgroundColor = new Color(palette.bg);
widget.setPadding(14, 16, 14, 16);

const label = widget.addText("LAST FEED");
label.font = Font.semiboldSystemFont(10);
label.textColor = new Color(palette.dim);

widget.addSpacer(6);

if (state && state.feed) {
  // A live-ticking relative timestamp: iOS keeps this counting up between
  // widget refreshes, so the elapsed time is never stale.
  const since = widget.addDate(new Date(state.feed.ended_at));
  since.applyRelativeStyle();
  since.font = Font.boldSystemFont(30);
  since.textColor = new Color(palette.ink);
  since.minimumScaleFactor = 0.5;
  since.lineLimit = 1;

  widget.addSpacer(6);
  const detail = widget.addText(state.feed.detail);
  detail.font = Font.systemFont(12);
  detail.textColor = new Color(palette.dim);
  detail.lineLimit = 1;
} else {
  const message = widget.addText(state ? "No feeds in window" : "Unreachable");
  message.font = Font.boldSystemFont(18);
  message.textColor = new Color(palette.ink);

  widget.addSpacer(6);
  const hint = widget.addText(state ? "Check Huckleberry" : "Is Tailscale on?");
  hint.font = Font.systemFont(12);
  hint.textColor = new Color(palette.dim);
}

// Ask iOS to refresh the underlying data in ~5 minutes (iOS decides the
// actual cadence; the timestamp above ticks regardless).
widget.refreshAfterDate = new Date(Date.now() + 5 * 60 * 1000);
widget.url = `${HOST}/display`; // tapping the widget opens the nightstand page

if (config.runsInWidget) {
  Script.setWidget(widget);
} else {
  widget.presentSmall();
}
Script.complete();
