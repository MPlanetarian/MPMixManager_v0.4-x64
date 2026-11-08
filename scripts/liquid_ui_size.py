"""Player-published Full / Mini / Micro size for the Liquid Glass window.

The glass host must not bind M itself. During search that letter is text, and
the player is the only place that knows the difference. The player writes the
size it actually applied. The host reads it and resizes.
"""
from __future__ import annotations

import os
from pathlib import Path

UI_SIZES = ("NORMAL", "MINI", "MICRO")


def _path(config_dir: Path, pid: int) -> Path:
    return Path(config_dir) / f"liquid_ui_size.{int(pid)}"


def publish_ui_size(config_dir: Path, pid: int, mode: str) -> None:
    mode = str(mode or "").strip().upper()
    if mode not in UI_SIZES or int(pid or 0) <= 0:
        return
    path = _path(config_dir, pid)
    try:
        if path.is_file() and path.read_text(encoding="utf-8").strip().upper() == mode:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.parent / f".liquid_ui_size.{int(pid)}.tmp"
        tmp.write_text(mode + "\n", encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        pass


def read_ui_size(config_dir: Path, pid: int) -> str:
    if int(pid or 0) <= 0:
        return ""
    try:
        mode = _path(config_dir, pid).read_text(encoding="utf-8").strip().upper()
    except OSError:
        return ""
    return mode if mode in UI_SIZES else ""


def clear_ui_size(config_dir: Path, pid: int) -> None:
    if int(pid or 0) <= 0:
        return
    try:
        _path(config_dir, pid).unlink()
    except OSError:
        pass
