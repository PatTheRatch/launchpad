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
  form.layout.value = config.display.layout ?? "classic";
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
      layout: form.layout.value,
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
const CYCLE_LAYOUTS = ["classic", "compact", "hero", "slots", "cards", "timeline"];
const CYCLE_INTERVAL_MS = 6000;

const previewPanel = document.getElementById("preview-panel");
const previewImg = document.getElementById("preview-img");
const previewMeta = document.getElementById("preview-meta");
const previewRefreshBtn = document.getElementById("preview-refresh");
const applyModeBtn = document.getElementById("apply-mode-btn");
const cycleButtons = Array.from(document.querySelectorAll("[data-axis]"));
const modeTabs = Array.from(document.querySelectorAll(".mode-tab"));
const layoutTabs = Array.from(document.querySelectorAll(".layout-tab"));

let currentPreviewMode = "auto";
let currentPreviewLayout = "classic";
let cycleTimer = null;
let cycleAxis = null;
let previewSeq = 0;

async function loadPreview({ refresh = false } = {}) {
  modeTabs.forEach((tab) => tab.classList.toggle("active", tab.dataset.mode === currentPreviewMode));
  layoutTabs.forEach((tab) =>
    tab.classList.toggle("active", tab.dataset.layout === currentPreviewLayout),
  );

  const seq = ++previewSeq;
  previewPanel.classList.add("loading");
  try {
    const query = new URLSearchParams({ layout: currentPreviewLayout });
    if (refresh) query.set("refresh", "1");
    const response = await fetch(`/api/preview/${currentPreviewMode}.png?${query}`);
    if (!response.ok) {
      const result = await response.json().catch(() => ({}));
      throw new Error(result.message || `HTTP ${response.status}`);
    }
    const blob = await response.blob();
    if (seq !== previewSeq) return; // a newer request superseded this one

    const url = URL.createObjectURL(blob);
    previewImg.onload = () => URL.revokeObjectURL(url);
    previewImg.src = url;

    const mode = response.headers.get("X-Launchpad-Mode") || currentPreviewMode;
    const layout = response.headers.get("X-Launchpad-Layout") || currentPreviewLayout;
    const fetchedAt = response.headers.get("X-Launchpad-Fetched-At");
    const fetchedText = fetchedAt
      ? new Date(fetchedAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })
      : "unknown";
    previewMeta.textContent = `${layout} layout · ${mode} · data fetched ${fetchedText}`;
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
  cycleAxis = null;
  cycleButtons.forEach((button) => {
    button.textContent = button.dataset.axis === "mode" ? "▶ Cycle times of day" : "▶ Cycle layouts";
    button.classList.remove("active");
  });
}

function startCycle(button) {
  const axis = button.dataset.axis;
  const values = axis === "mode" ? CYCLE_MODES : CYCLE_LAYOUTS;
  const current = axis === "mode" ? currentPreviewMode : currentPreviewLayout;
  let index = Math.max(0, values.indexOf(current));

  const show = () => {
    if (axis === "mode") currentPreviewMode = values[index];
    else currentPreviewLayout = values[index];
    loadPreview();
  };

  cycleAxis = axis;
  show();
  cycleTimer = setInterval(() => {
    index = (index + 1) % values.length;
    show();
  }, CYCLE_INTERVAL_MS);
  button.textContent = axis === "mode" ? "⏸ Stop cycling" : "⏸ Stop cycling";
  button.classList.add("active");
}

cycleButtons.forEach((button) => {
  button.addEventListener("click", () => {
    const wasRunning = cycleAxis === button.dataset.axis;
    stopCycle();
    if (!wasRunning) startCycle(button);
  });
});

modeTabs.forEach((tab) => {
  tab.addEventListener("click", () => {
    stopCycle();
    currentPreviewMode = tab.dataset.mode;
    loadPreview();
  });
});

layoutTabs.forEach((tab) => {
  tab.addEventListener("click", () => {
    stopCycle();
    currentPreviewLayout = tab.dataset.layout;
    loadPreview();
  });
});

previewRefreshBtn.addEventListener("click", () => loadPreview({ refresh: true }));

applyModeBtn.addEventListener("click", async () => {
  const forced = currentPreviewMode === "auto" ? null : currentPreviewMode;
  const scope = forced ? `force ${forced} mode` : "return to the time-based schedule";
  if (!confirm(`Save the ${currentPreviewLayout} layout, ${scope}, and restart the dashboard?`)) return;

  applyModeBtn.disabled = true;
  try {
    const config = collectConfig();
    config.force_mode = forced;
    config.display.layout = currentPreviewLayout;
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
      `Panel set to the ${currentPreviewLayout} layout, ${forced ? `${forced} mode` : "time-based schedule"} (restarting).`,
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

// Start the preview on the saved layout so the page opens showing the panel.
loadConfig().then(() => {
  currentPreviewLayout = form.layout.value || "classic";
  loadPreview();
});
