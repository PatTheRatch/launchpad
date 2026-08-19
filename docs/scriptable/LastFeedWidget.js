// Launchpad "Last Feed" home-screen widget — for the free Scriptable app (iOS).
//
// Shows how long since the baby's last feed, ticking live on the home screen,
// fed by your own Launchpad server instead of Huckleberry's paid widget.
//
// Setup and troubleshooting: docs/NIGHTSTAND.md in the Launchpad repo.
// Requires the Tailscale app to be connected so the phone can reach the Pi.
//
// Run this script inside Scriptable once before adding the widget: failures
// are reported on the widget face and logged to the console, so you get a
// real reason ("HTTP 404") rather than an opaque parse error.

const HOST = "http://launchpad:8080"; // your Pi, over Tailscale (MagicDNS name)

const NIGHT = { ink: "#B3402E", dim: "#6E2A20" };
const DAY = { ink: "#C9C3B8", dim: "#6E6A62" };

// Returns {state} on success or {error, hint} describing what actually broke.
async function loadState() {
  const url = `${HOST}/api/state.json`;
  let body;
  try {
    const request = new Request(url);
    request.timeoutInterval = 10;
    // Load as text, not JSON: an HTML error page would otherwise surface as
    // "data couldn't be read because it isn't in the correct format", which
    // says nothing about the actual problem.
    body = await request.loadString();
    const status = request.response ? request.response.statusCode : 0;
    if (status && status !== 200) {
      return status === 404
        ? { error: `HTTP 404`, hint: "Update the Pi: git pull" }
        : { error: `HTTP ${status}`, hint: "Check the config server" };
    }
  } catch (networkError) {
    console.log(`Request failed: ${networkError}`);
    return { error: "Unreachable", hint: "Is Tailscale on?" };
  }

  try {
    return { state: JSON.parse(body) };
  } catch (parseError) {
    // Almost always an HTML error page from Flask.
    console.log(`Not JSON. First 200 chars:\n${body.slice(0, 200)}`);
    const looksLikeHtml = body.trim().startsWith("<");
    return {
      error: looksLikeHtml ? "Got HTML" : "Bad response",
      hint: looksLikeHtml ? "Wrong URL, or Pi needs update" : "See Scriptable console",
    };
  }
}

const result = await loadState();
const state = result.state;
const palette = state && state.mode === "overnight" ? NIGHT : DAY;

const widget = new ListWidget();
widget.backgroundColor = new Color("#000000");
widget.setPadding(14, 16, 14, 16);

const label = widget.addText("LAST FEED");
label.font = Font.semiboldSystemFont(10);
label.textColor = new Color(palette.dim);
widget.addSpacer(6);

function addLines(headline, detail) {
  const top = widget.addText(headline);
  top.font = Font.boldSystemFont(18);
  top.textColor = new Color(palette.ink);
  top.minimumScaleFactor = 0.6;
  top.lineLimit = 1;

  widget.addSpacer(6);
  const bottom = widget.addText(detail);
  bottom.font = Font.systemFont(12);
  bottom.textColor = new Color(palette.dim);
  bottom.lineLimit = 2;
}

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
} else if (state) {
  // Reached the server, but it has no feed to report. The baby section says
  // whether tracking is off or the Huckleberry backend is unavailable.
  const baby = (state.sections || []).find((s) => s.section === "baby");
  addLines("No feed", baby ? baby.line : "Feed tracking is off");
} else {
  addLines(result.error, result.hint);
}

// Ask iOS to refresh the underlying data in ~5 minutes (iOS decides the
// actual cadence; the timestamp above ticks regardless).
widget.refreshAfterDate = new Date(Date.now() + 5 * 60 * 1000);
widget.url = `${HOST}/display`; // tapping the widget opens the nightstand page

if (config.runsInWidget) {
  Script.setWidget(widget);
} else {
  if (state) console.log(`OK — mode=${state.mode}, feed=${state.feed ? state.feed.detail : "none"}`);
  widget.presentSmall();
}
Script.complete();
