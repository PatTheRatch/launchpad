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
