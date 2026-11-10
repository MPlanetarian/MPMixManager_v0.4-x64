"""Find a real Bash on Windows. The Microsoft Store alias is not Bash."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def _windows_candidates() -> list[Path]:
    program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
    program_files_x86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    local = os.environ.get("LOCALAPPDATA", "")
    return [
        Path(program_files) / "Git" / "bin" / "bash.exe",
        Path(program_files_x86) / "Git" / "bin" / "bash.exe",
        Path(local) / "Programs" / "Git" / "bin" / "bash.exe",
        Path(r"C:\msys64\usr\bin\bash.exe"),
    ]


def _from_path_skipping_store() -> str:
    for entry in os.environ.get("PATH", "").split(os.pathsep):
        if not entry or "windowsapps" in entry.lower():
            continue
        exe = Path(entry) / "bash.exe"
        if exe.is_file():
            return str(exe)
    return ""


def find_bash() -> str:
    """Git Bash or MSYS2. Never the WindowsApps python/bash stub."""
    if sys.platform == "win32":
        for candidate in _windows_candidates():
            if candidate.is_file():
                return str(candidate)
        found = _from_path_skipping_store()
        if found:
            return found
    which = shutil.which("bash") or ""
    if which and "windowsapps" not in which.lower():
        return which
    return "bash"
