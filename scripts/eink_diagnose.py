#!/usr/bin/env python3
"""Diagnose the physical e-ink panel connection: SPI, GPIO, and a live clear.

Run this on the Pi when the dashboard looks "stuck" and you suspect the
ribbon cable (e.g. after moving the unit). It does NOT import the launchpad
package or touch config.json — it drives the Waveshare vendor library
directly, in isolation, so a result here means something about the hardware
link specifically, not the app.

Stop the dashboard service first: it holds the same SPI/GPIO lines, and two
processes fighting over them produces misleading (or literally garbled)
results.

    sudo systemctl stop launchpad
    /opt/launchpad/.venv/bin/python3 scripts/eink_diagnose.py
    sudo systemctl start launchpad     # once you're done

Panel wiring assumed (Waveshare 7.5" V2, per LAUNCHPAD.md): SPI CE0, DC=25,
RST=17, BUSY=24. Pi 5 uses lgpio, not RPi.GPIO.
"""

from __future__ import annotations

import grp
import os
import pwd
import sys
import threading
import time

_BUSY_TIMEOUT_S = 15.0


def _check(label: str, ok: bool, detail: str = "") -> bool:
    mark = "OK  " if ok else "FAIL"
    print(f"[{mark}] {label}" + (f" — {detail}" if detail else ""))
    return ok


def check_groups() -> bool:
    user = pwd.getpwuid(os.getuid()).pw_name
    group_names = {grp.getgrgid(g).gr_name for g in os.getgroups()}
    ok = {"spi", "gpio"}.issubset(group_names)
    return _check(
        f"Running as {user!r} with spi+gpio groups",
        ok,
        f"groups: {sorted(group_names)}" if not ok else "",
    )


def check_spi_device() -> bool:
    candidates = [f"/dev/spidev0.{n}" for n in range(2)]
    found = [path for path in candidates if os.path.exists(path)]
    return _check(
        "SPI device node present",
        bool(found),
        f"found {found}" if found else f"none of {candidates} exist — is SPI enabled?",
    )


def check_gpio_chip() -> bool:
    found = [p for p in os.listdir("/dev") if p.startswith("gpiochip")]
    return _check("GPIO chip device present", bool(found), f"/dev/{found}" if found else "")


def run_panel_cycle() -> bool:
    """Init the panel and clear it, with a hard timeout on the BUSY wait.

    The vendor driver polls the BUSY pin in a plain loop with no timeout of
    its own, so a disconnected or non-responding panel hangs this call
    forever. Running it on a background thread lets us time out and report
    that clearly instead of the diagnostic itself getting stuck.
    """
    try:
        from waveshare_epd import epd7in5_V2
    except ImportError as exc:
        return _check("Import waveshare_epd", False, str(exc))
    print("[OK  ] Import waveshare_epd")

    result: dict[str, object] = {}

    def attempt() -> None:
        try:
            epd = epd7in5_V2.EPD()
            epd.init()
            epd.Clear()
            epd.sleep()
            result["ok"] = True
        except Exception as exc:  # noqa: BLE001 - reporting, not handling
            result["ok"] = False
            result["error"] = str(exc)

    worker = threading.Thread(target=attempt, daemon=True)
    started = time.monotonic()
    worker.start()
    worker.join(timeout=_BUSY_TIMEOUT_S)

    if worker.is_alive():
        _check(
            "Panel init + clear",
            False,
            f"still hung after {_BUSY_TIMEOUT_S:.0f}s waiting on BUSY — "
            "the panel never signalled it finished. This is the strongest "
            "signal of a disconnected or half-seated ribbon cable.",
        )
        print(
            "\nThe script will now exit; the hung thread is daemonized and "
            "will not block shutdown, but the SPI bus may be left in a "
            "confused state — power-cycling the Pi after reseating the "
            "cable is the clean way to recover."
        )
        return False

    ok = bool(result.get("ok"))
    elapsed = time.monotonic() - started
    _check(
        "Panel init + clear",
        ok,
        f"{elapsed:.1f}s" if ok else str(result.get("error", "unknown error")),
    )
    if ok:
        print(
            "\nDid the physical panel visibly flash to blank white just now? "
            "If yes, the connection (power, ground, SPI, and all three "
            "control lines) is confirmed good end-to-end — the earlier "
            "'stuck' symptom was very likely a stale process, not hardware. "
            "If the screen did NOT visibly change despite this reporting OK, "
            "the panel itself (not the cable) is the next thing to suspect."
        )
    return ok


def main() -> int:
    print("Launchpad e-ink hardware diagnostic\n" + "-" * 36)
    software_ok = check_groups() & check_spi_device() & check_gpio_chip()
    if not software_ok:
        print(
            "\nA software/config check failed above — fix that first. A "
            "permissions or SPI-enablement problem can look identical to a "
            "loose cable, but reseating a cable will not fix it."
        )
        return 1

    print()
    hardware_ok = run_panel_cycle()
    print()
    if hardware_ok:
        print("Diagnosis: connection looks good.")
        return 0
    print(
        "Diagnosis: likely a physical connection problem. Power down, "
        "reseat the ribbon cable fully on both ends (the panel and the "
        "Pi's SPI header), confirm no bent pins, then power up and re-run "
        "this script before restarting launchpad.service."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
