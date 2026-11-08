#!/usr/bin/env python3
"""Raise the MP Liquid Player and put the pointer inside it.

Keyboard focus alone leaves the pointer over MP Gui. On a focus-follows-mouse
desktop the player then never becomes the mouse window. This raises the glass
frame, stacks the terminal above that frame, moves the pointer into the
terminal, and asks the window manager to activate the frame.
"""

from __future__ import annotations

import ctypes
import shutil
import subprocess
import sys
from ctypes import byref, c_int, c_uint32, c_uint64, c_void_p

PLAYER_TITLE = "MP Audio Player (Liquid Glass"
MANAGER_MARK = "Mix Manager"


def parse_wmctrl_lp(text: str) -> list[dict]:
    """Parse `wmctrl -lp` rows into id, pid, and title."""
    rows = []
    for line in text.splitlines():
        parts = line.split(None, 4)
        if len(parts) < 4:
            continue
        try:
            window_id = int(parts[0], 16)
            pid = int(parts[2])
        except ValueError:
            continue
        rows.append({
            "id": window_id,
            "pid": pid,
            "title": parts[4] if len(parts) > 4 else "",
        })
    return rows


def choose_focus_target(rows: list[dict]) -> tuple[int, int]:
    """Return (glass frame id, pointer window id).

    The pointer window is the player's terminal when wmctrl lists it as
    another window of the same process. The manager window is never chosen.
    """
    glass = 0
    pid = 0
    for row in rows:
        title = row.get("title") or ""
        if PLAYER_TITLE in title and MANAGER_MARK not in title:
            glass = int(row["id"])
            pid = int(row["pid"])
            break
    if not glass:
        return 0, 0
    pointer = glass
    for row in rows:
        title = row.get("title") or ""
        if int(row["pid"]) != pid or int(row["id"]) == glass:
            continue
        if MANAGER_MARK in title or PLAYER_TITLE in title:
            continue
        pointer = int(row["id"])
        break
    return glass, pointer


def _wmctrl_text() -> str:
    if not shutil.which("wmctrl"):
        return ""
    try:
        result = subprocess.run(
            ["wmctrl", "-lp"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return result.stdout or ""


def _wmctrl_activate(window_id: int) -> None:
    if window_id <= 0 or not shutil.which("wmctrl"):
        return
    try:
        subprocess.run(
            ["wmctrl", "-i", "-a", f"0x{int(window_id):08x}"],
            capture_output=True,
            timeout=2,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        pass


def _ensure_x11_focus_api(x11) -> None:
    if not isinstance(x11, ctypes.CDLL) or getattr(x11, "_mp_mouse_focus_bound", False):
        return
    x11.XRaiseWindow.argtypes = [c_void_p, c_uint64]
    x11.XSetInputFocus.argtypes = [c_void_p, c_uint64, c_int, c_uint64]
    x11.XWarpPointer.argtypes = [
        c_void_p, c_uint64, c_uint64, c_int, c_int, c_uint32, c_uint32, c_int, c_int,
    ]
    x11.XWarpPointer.restype = c_int
    x11.XFlush.argtypes = [c_void_p]
    x11.XGetGeometry.argtypes = [
        c_void_p, c_uint64, ctypes.POINTER(c_uint64), ctypes.POINTER(c_int), ctypes.POINTER(c_int),
        ctypes.POINTER(c_uint32), ctypes.POINTER(c_uint32), ctypes.POINTER(c_uint32), ctypes.POINTER(c_uint32),
    ]
    x11.XGetGeometry.restype = c_int
    x11._mp_mouse_focus_bound = True


def _window_size(x11, display, window_id: int) -> tuple[int, int]:
    root = c_uint64()
    x = c_int()
    y = c_int()
    width = c_uint32()
    height = c_uint32()
    border = c_uint32()
    depth = c_uint32()
    ok = x11.XGetGeometry(
        display, c_uint64(int(window_id)), byref(root), byref(x), byref(y),
        byref(width), byref(height), byref(border), byref(depth),
    )
    if not ok:
        return 0, 0
    return int(width.value), int(height.value)


def stack_and_point(x11, display, frame_id: int, pointer_id: int, warp: bool = True) -> bool:
    """Raise the frame, stack the pointer window above it, and focus that window."""
    _ensure_x11_focus_api(x11)
    frame_id = int(frame_id or 0)
    pointer_id = int(pointer_id or frame_id or 0)
    if not display or pointer_id <= 0:
        return False
    width, height = _window_size(x11, display, pointer_id)
    if width < 8 or height < 8:
        return False
    if frame_id:
        x11.XRaiseWindow(display, c_uint64(frame_id))
    if pointer_id != frame_id:
        x11.XRaiseWindow(display, c_uint64(pointer_id))
    # 2 is RevertToParent. 0 is CurrentTime.
    x11.XSetInputFocus(display, c_uint64(pointer_id), 2, 0)
    if warp:
        x11.XWarpPointer(
            display, 0, c_uint64(pointer_id), 0, 0, 0, 0, width // 2, height // 2,
        )
    x11.XFlush(display)
    return True


def _open_display(x11):
    x11.XOpenDisplay.restype = c_void_p
    x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
    x11.XCloseDisplay.argtypes = [c_void_p]
    display = x11.XOpenDisplay(None)
    if not display:
        return None
    error = ctypes.CFUNCTYPE(c_int, c_void_p, c_void_p)(lambda *_args: 0)
    x11.XSetErrorHandler.argtypes = [c_void_p]
    x11.XSetErrorHandler.restype = c_void_p
    x11.XSetErrorHandler(ctypes.cast(error, c_void_p))
    x11._mp_mouse_focus_error = error
    return display


def _win32_claim(window_id: int, warp: bool) -> bool:
    if window_id <= 0:
        return False
    try:
        user32 = ctypes.windll.user32
    except (AttributeError, OSError):
        return False
    user32.SetForegroundWindow(int(window_id))
    if not warp:
        return True

    class RECT(ctypes.Structure):
        _fields_ = [("left", c_int), ("top", c_int), ("right", c_int), ("bottom", c_int)]

    rect = RECT()
    if not user32.GetWindowRect(int(window_id), byref(rect)):
        return True
    user32.SetCursorPos((rect.left + rect.right) // 2, (rect.top + rect.bottom) // 2)
    return True


def claim_mouse_focus(frame_id: int, child_id: int = 0, warp: bool = True, x11=None, display=None) -> bool:
    """Activate the player frame and put the pointer in the terminal window."""
    frame_id = int(frame_id or 0)
    child_id = int(child_id or 0)
    if sys.platform == "win32":
        return _win32_claim(child_id or frame_id, warp)
    pointer_id = child_id or frame_id
    if pointer_id <= 0:
        return False
    if frame_id:
        _wmctrl_activate(frame_id)
    owns_display = False
    if x11 is None or not display:
        try:
            x11 = ctypes.CDLL("libX11.so.6")
        except OSError:
            return False
        display = _open_display(x11)
        if not display:
            return False
        owns_display = True
    try:
        return stack_and_point(x11, display, frame_id, pointer_id, warp=warp)
    finally:
        if owns_display:
            x11.XCloseDisplay(display)


def focus_player_window(warp: bool = True) -> int:
    """Focus the open Liquid Player.

    Returns 0 when the pointer was moved into the player, 1 when the player
    window is not listed yet, and 2 when wmctrl is not available.
    """
    if not shutil.which("wmctrl"):
        return 2
    glass, pointer = choose_focus_target(parse_wmctrl_lp(_wmctrl_text()))
    if not glass:
        return 1
    child = pointer if pointer != glass else 0
    return 0 if claim_mouse_focus(glass, child_id=child, warp=warp) else 1


def main(argv: list[str] | None = None) -> int:
    del argv
    try:
        return focus_player_window(warp=True)
    except Exception:
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
