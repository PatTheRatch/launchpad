const form = document.getElementById("config-form");
const statusEl = document.getElementById("status");
const restartBtn = document.getElementById("restart-btn");

function showStatus(message, kind) {
  statusEl.textContent = message;
  statusEl.className = `status visible ${kind}`;
}

function applyConfig(config) {
  const orientation = config.display.orientation;
  const radio = form.querySelector(`input[name="orientation"][value="${orientation}"]`);
  if (radio) radio.checked = true;

  form.driver.value = config.display.driver;
  form.width.value = config.display.width;
  form.height.value = config.display.height;
  form.refresh_seconds.value = config.refresh.refresh_seconds;

  form.nba.checked = Boolean(config.features.nba);
  form.fantasy_basketball.checked = Boolean(config.features.fantasy_basketball);
  form.baby_tracking.checked = Boolean(config.features.baby_tracking);
  form.world_cup.checked = Boolean(config.features.world_cup);

  form.force_mode.value = config.force_mode ?? "";
}

function collectConfig() {
  const orientation = form.querySelector('input[name="orientation"]:checked');
  return {
    display: {
      orientation: orientation ? orientation.value : "portrait",
      driver: form.driver.value,
      width: Number.parseInt(form.width.value, 10),
      height: Number.parseInt(form.height.value, 10),
    },
    refresh: {
      refresh_seconds: Number.parseInt(form.refresh_seconds.value, 10),
    },
    features: {
      nba: form.nba.checked,
      fantasy_basketball: form.fantasy_basketball.checked,
      baby_tracking: form.baby_tracking.checked,
      world_cup: form.world_cup.checked,
    },
    force_mode: form.force_mode.value || null,
  };
}

async function loadConfig() {
  try {
    const response = await fetch("/api/config");
    const config = await response.json();
    applyConfig(config);
  } catch (err) {
    showStatus(`Failed to load configuration: ${err}`, "error");
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const response = await fetch("/api/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(collectConfig()),
    });
    const result = await response.json();
    if (response.ok && result.status === "ok") {
      applyConfig(result.config);
      showStatus("Configuration saved.", "success");
    } else {
      showStatus(result.message || "Failed to save configuration.", "error");
    }
  } catch (err) {
    showStatus(`Failed to save configuration: ${err}`, "error");
  }
});

form.querySelectorAll(".preset").forEach((button) => {
  button.addEventListener("click", () => {
    form.refresh_seconds.value = button.dataset.seconds;
  });
});

// ---------------------------------------------------------------------------
// Live preview: render any mode in the browser; optionally push it to the
// panel by saving force_mode and restarting the dashboard service.
// ---------------------------------------------------------------------------

const CYCLE_MODES = ["morning", "daytime", "evening", "overnight"];
const CYCLE_INTERVAL_MS = 6000;

const previewPanel = document.getElementById("preview-panel");
const previewImg = document.getElementById("preview-img");
const previewMeta = document.getElementById("preview-meta");
const cycleBtn = document.getElementById("cycle-btn");
const previewRefreshBtn = document.getElementById("preview-refresh");
const applyModeBtn = document.getElementById("apply-mode-btn");
const modeTabs = Array.from(document.querySelectorAll(".mode-tab"));

let currentPreviewMode = "auto";
let cycleTimer = null;
let previewSeq = 0;

async function loadPreview(mode, { refresh = false } = {}) {
  currentPreviewMode = mode;
  modeTabs.forEach((tab) => tab.classList.toggle("active", tab.dataset.mode === mode));

  const seq = ++previewSeq;
  previewPanel.classList.add("loading");
  try {
    const response = await fetch(`/api/preview/${mode}.png${refresh ? "?refresh=1" : ""}`);
    if (!response.ok) {
      const result = await response.json().catch(() => ({}));
      throw new Error(result.message || `HTTP ${response.status}`);
    }
    const blob = await response.blob();
    if (seq !== previewSeq) return; // a newer request superseded this one

    const url = URL.createObjectURL(blob);
    previewImg.onload = () => URL.revokeObjectURL(url);
    previewImg.src = url;

    const resolved = response.headers.get("X-Launchpad-Mode") || mode;
    const fetchedAt = response.headers.get("X-Launchpad-Fetched-At");
    const fetchedText = fetchedAt
      ? new Date(fetchedAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })
      : "unknown";
    previewMeta.textContent = `Showing ${resolved} · data fetched ${fetchedText}`;
  } catch (err) {
    if (seq === previewSeq) previewMeta.textContent = `Preview failed: ${err.message}`;
  } finally {
    if (seq === previewSeq) previewPanel.classList.remove("loading");
  }
}

function stopCycle() {
  if (cycleTimer === null) return;
  clearInterval(cycleTimer);
  cycleTimer = null;
  cycleBtn.textContent = "▶ Cycle modes";
  cycleBtn.classList.remove("active");
}

function startCycle() {
  let index = Math.max(0, CYCLE_MODES.indexOf(currentPreviewMode));
  loadPreview(CYCLE_MODES[index]);
  cycleTimer = setInterval(() => {
    index = (index + 1) % CYCLE_MODES.length;
    loadPreview(CYCLE_MODES[index]);
  }, CYCLE_INTERVAL_MS);
  cycleBtn.textContent = "⏸ Stop cycling";
  cycleBtn.classList.add("active");
}

cycleBtn.addEventListener("click", () => {
  if (cycleTimer === null) startCycle();
  else stopCycle();
});

modeTabs.forEach((tab) => {
  tab.addEventListener("click", () => {
    stopCycle();
    loadPreview(tab.dataset.mode);
  });
});

previewRefreshBtn.addEventListener("click", () => {
  loadPreview(currentPreviewMode, { refresh: true });
});

applyModeBtn.addEventListener("click", async () => {
  const forced = currentPreviewMode === "auto" ? null : currentPreviewMode;
  const label = forced ? `force ${forced} mode` : "return to the time-based schedule";
  if (!confirm(`Save the configuration, ${label}, and restart the dashboard?`)) return;

  applyModeBtn.disabled = true;
  try {
    const config = collectConfig();
    config.force_mode = forced;
    const saveResponse = await fetch("/api/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(config),
    });
    const saveResult = await saveResponse.json();
    if (!saveResponse.ok || saveResult.status !== "ok") {
      throw new Error(saveResult.message || "Failed to save configuration.");
    }
    applyConfig(saveResult.config);

    const restartResponse = await fetch("/api/restart", { method: "POST" });
    const restartResult = await restartResponse.json();
    if (!restartResponse.ok || restartResult.status !== "ok") {
      throw new Error(restartResult.message || "Saved, but the restart failed.");
    }
    showStatus(
      forced
        ? `Panel set to ${forced} mode (restarting).`
        : "Panel returned to the time-based schedule (restarting).",
      "success",
    );
  } catch (err) {
    showStatus(`${err.message}`, "error");
  } finally {
    applyModeBtn.disabled = false;
  }
});

restartBtn.addEventListener("click", async () => {
  if (!confirm("Restart the Launchpad dashboard service now?")) return;

  restartBtn.disabled = true;
  try {
    const response = await fetch("/api/restart", { method: "POST" });
    const result = await response.json();
    if (response.ok && result.status === "ok") {
      showStatus("Dashboard restart requested.", "success");
    } else {
      showStatus(result.message || "Failed to restart dashboard.", "error");
    }
  } catch (err) {
    showStatus(`Failed to restart dashboard: ${err}`, "error");
  } finally {
    restartBtn.disabled = false;
  }
});

loadConfig();
loadPreview("auto");
