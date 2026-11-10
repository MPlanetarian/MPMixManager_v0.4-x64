"""VTE font for MP Liquid Player and MP Gui.

On Linux the host uses Hack at 11 pt when that family is installed.
Otherwise it uses the generic Monospace face at the same size.
"""
from __future__ import annotations

import shutil
import subprocess
import sys

HACK_FONT = "Hack 11"
FALLBACK_FONT = "Monospace 11"


def hack_font_installed() -> bool:
    """True when fontconfig has the Hack family. Other platforms stay false."""
    if not sys.platform.startswith("linux"):
        return False
    fc_list = shutil.which("fc-list")
    if not fc_list:
        return False
    try:
        proc = subprocess.run(
            [fc_list, ":family=Hack", "file"],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return proc.returncode == 0 and bool(proc.stdout.strip())


def default_liquid_glass_font() -> str:
    """Hack 11 on Linux when Hack is installed, otherwise Monospace 11."""
    if hack_font_installed():
        return HACK_FONT
    return FALLBACK_FONT
