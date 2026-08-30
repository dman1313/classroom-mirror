"""Per-user V2 data directory. Never writes frames."""

from __future__ import annotations

import os
from pathlib import Path


APP_DIR_NAME = "ClassroomMirror"


def data_root(override: str | os.PathLike | None = None) -> Path:
    if override:
        return Path(override).expanduser().resolve()
    env = os.environ.get("CLASSROOM_MIRROR_DATA_DIR")
    if env:
        return Path(env).expanduser().resolve()
    local = os.environ.get("LOCALAPPDATA")
    if local:
        return (Path(local) / APP_DIR_NAME).resolve()
    if os.name == "posix":
        home = Path.home()
        if Path("/System").exists() and (home / "Library").exists():
            return (home / "Library" / "Application Support" / APP_DIR_NAME).resolve()
        return (home / ".local" / "share" / APP_DIR_NAME).resolve()
    return (Path.home() / APP_DIR_NAME).resolve()


def ensure_layout(root: Path | None = None) -> Path:
    base = data_root(root)
    (base / "state").mkdir(parents=True, exist_ok=True)
    (base / "config").mkdir(parents=True, exist_ok=True)
    (base / "logs").mkdir(parents=True, exist_ok=True)
    return base
