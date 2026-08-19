// Launchpad interactive logger — for the free Scriptable app (iOS).
//
// Run it (or wire it to a widget tap / share sheet) and it walks through:
// what to log -> details -> confirm -> POST -> result. Same endpoints and
// semantics as docs/LOGGING.md; the server never retries a write.

const HOST = "http://launchpad:8080"; // your Pi, over Tailscale

async function choose(title, options) {
  const alert = new Alert();
  alert.title = title;
  for (const option of options) alert.addAction(option);
  alert.addCancelAction("Cancel");
  const index = await alert.presentSheet();
  return index === -1 ? null : options[index];
}

async function post(kind, payload) {
  const request = new Request(`${HOST}/api/log/${kind}`);
  request.method = "POST";
  request.headers = { "Content-Type": "application/json" };
  request.body = JSON.stringify(payload);
  request.timeoutInterval = 15;
  const body = await request.loadString();
  const status = request.response ? request.response.statusCode : 0;
  let parsed = null;
  try { parsed = JSON.parse(body); } catch (parseError) { /* handled below */ }
  return { ok: status === 200 && parsed && parsed.status === "ok", parsed, status };
}

function notify(title, body) {
  const alert = new Alert();
  alert.title = title;
  alert.message = body;
  alert.addAction("OK");
  return alert.present();
}

async function pickEvent() {
  const kind = await choose("Log what?", ["Bottle", "Diaper", "Sleep"]);
  if (kind === null) return null;

  if (kind === "Bottle") {
    const amount = await choose("How much?", ["60 ml", "90 ml", "120 ml", "150 ml"]);
    if (amount === null) return null;
    const type = await choose("What kind?", ["Formula", "Breast Milk"]);
    if (type === null) return null;
    return {
      endpoint: "bottle",
      payload: { amount_ml: Number.parseInt(amount, 10), bottle_type: type },
      summary: `${amount} ${type.toLowerCase()}`,
    };
  }
  if (kind === "Diaper") {
    const mode = await choose("What's in it?", ["pee", "poo", "both", "dry"]);
    if (mode === null) return null;
    return { endpoint: "diaper", payload: { mode }, summary: `${mode} diaper` };
  }
  const action = await choose("Sleep timer", ["start", "complete", "cancel"]);
  if (action === null) return null;
  return { endpoint: "sleep", payload: { action }, summary: `sleep ${action}` };
}

async function main() {
  const event = await pickEvent();
  if (event === null) return;

  // Confirm before writing: this creates a real record in the history.
  const confirm = new Alert();
  confirm.title = `Log ${event.summary}?`;
  confirm.addAction("Log it");
  confirm.addCancelAction("Cancel");
  if ((await confirm.present()) === -1) return;

  const result = await post(event.endpoint, event.payload);
  if (result.ok) {
    await notify("Logged ✓", `${event.summary} — the dashboard will update on its next poll.`);
  } else {
    const message = result.parsed && result.parsed.message
      ? result.parsed.message
      : `HTTP ${result.status || "—"} (is Tailscale on?)`;
    // Never auto-retry: if this DID land upstream, tapping again would
    // duplicate it. Check the dashboard or the app before retrying.
    await notify("Not logged", `${message}\n\nNothing was mirrored locally.`);
  }
}

await main();
Script.complete();
