"""Persistent JSON-backed configuration store.

``config.json`` lives at the process's working directory by default, mirroring
how ``.env`` loading already relies on cwd (the systemd unit sets
``WorkingDirectory`` to the repo root). ``LAUNCHPAD_CONFIG_PATH`` overrides the
location, e.g. for tests.
"""

from __future__ import annotations

import copy
import json
import os
import tempfile
from pathlib import Path
from typing import Any

#: Defaults used when config.json is missing or unreadable. Mirrors the
#: hardcoded defaults in :mod:`launchpad.config.settings`.
DEFAULT_CONFIG: dict[str, Any] = {
    "display": {"orientation": "portrait", "width": 480, "height": 800, "driver": "mock"},
    "refresh": {"refresh_seconds": 300},
    "features": {
        "nba": False,
        "fantasy_basketball": False,
        "baby_tracking": False,
        "world_cup": False,
    },
    "force_mode": None,
}


def config_path() -> Path:
    """Resolve the config.json location, honoring ``LAUNCHPAD_CONFIG_PATH``."""
    return Path(os.getenv("LAUNCHPAD_CONFIG_PATH", "config.json"))


def load_config() -> dict[str, Any]:
    """Read and parse config.json.

    Returns a copy of :data:`DEFAULT_CONFIG` if the file is missing or its
    contents are not valid JSON, so callers always get a usable dict.
    """
    path = config_path()
    try:
        raw = path.read_text()
    except OSError:
        return copy.deepcopy(DEFAULT_CONFIG)

    try:
        config = json.loads(raw)
    except json.JSONDecodeError:
        return copy.deepcopy(DEFAULT_CONFIG)

    if not isinstance(config, dict):
        return copy.deepcopy(DEFAULT_CONFIG)
    return config


def save_config(config: dict[str, Any]) -> None:
    """Write ``config`` to config.json atomically (temp file + rename)."""
    path = config_path()

    fd, tmp_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w") as tmp_file:
            json.dump(config, tmp_file, indent=2)
            tmp_file.write("\n")
        os.rename(tmp_name, path)
    except BaseException:
        os.unlink(tmp_name)
        raise
