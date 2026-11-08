"""Find a user-local VTE when the OS image does not ship the typelib.

Bazzite does not include vte291. MP Liquid Glass needs Vte-2.91 and
libvte-2.91.so.0. Those files live in ~/.local/lib/mp-liquid-glass.
LD_LIBRARY_PATH is read at process start, so a direct python3 launch
re-execs itself once with that path set.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

LOCAL_VTE = Path.home() / ".local" / "lib" / "mp-liquid-glass"


def local_vte_env():
    lib = LOCAL_VTE / "lib"
    typelib = LOCAL_VTE / "girepository-1.0"
    if not (typelib / "Vte-2.91.typelib").is_file():
        return None
    if not (lib / "libvte-2.91.so.0").is_file():
        return None
    env = os.environ.copy()

    def prepend(key, value):
        current = env.get(key, "")
        if current.split(os.pathsep)[0] == value:
            return
        env[key] = value if not current else value + os.pathsep + current

    prepend("LD_LIBRARY_PATH", str(lib))
    prepend("GI_TYPELIB_PATH", str(typelib))
    return env


def reexec_with_local_vte():
    if os.environ.get("MP_VTE_REEXEC") == "1":
        return
    env = local_vte_env()
    if env is None:
        return
    env["MP_VTE_REEXEC"] = "1"
    os.execve(sys.executable, [sys.executable, *sys.argv], env)
