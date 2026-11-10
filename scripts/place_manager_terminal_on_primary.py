#!/usr/bin/env python3
"""Move the Terminal window running MP Mix Manager onto the main display."""

from __future__ import annotations

import ctypes
import subprocess
import sys
import time
from ctypes import Structure, c_double, c_uint32


class CGPoint(Structure):
    _fields_ = [("x", c_double), ("y", c_double)]


class CGSize(Structure):
    _fields_ = [("width", c_double), ("height", c_double)]


class CGRect(Structure):
    _fields_ = [("origin", CGPoint), ("size", CGSize)]


def main_display_bounds() -> tuple[int, int, int, int] | None:
    try:
        core_graphics = ctypes.CDLL(
            "/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics"
        )
        core_graphics.CGMainDisplayID.restype = c_uint32
        core_graphics.CGDisplayBounds.argtypes = [c_uint32]
        core_graphics.CGDisplayBounds.restype = CGRect
        bounds = core_graphics.CGDisplayBounds(core_graphics.CGMainDisplayID())
        return tuple(
            int(round(value))
            for value in (
                bounds.origin.x,
                bounds.origin.y,
                bounds.size.width,
                bounds.size.height,
            )
        )
    except (OSError, AttributeError, ValueError):
        return None


def move_terminal_tab(tty: str, display: tuple[int, int, int, int]) -> bool:
    x, y, width, height = display
    script = f'''on run argv
set targetTTY to item 1 of argv
set displayLeft to {x}
set displayTop to {y}
set displayWidth to {width}
set displayHeight to {height}
tell application "Terminal"
    repeat with candidateWindow in windows
        repeat with candidateTab in tabs of candidateWindow
            try
                if tty of candidateTab is targetTTY then
                    set oldBounds to bounds of candidateWindow
                    set winWidth to item 3 of oldBounds - item 1 of oldBounds
                    set winHeight to item 4 of oldBounds - item 2 of oldBounds
                    if winWidth < 320 then set winWidth to 1000
                    if winHeight < 240 then set winHeight to 700
                    if winWidth > displayWidth - 32 then set winWidth to displayWidth - 32
                    if winHeight > displayHeight - 64 then set winHeight to displayHeight - 64
                    set newLeft to displayLeft + 24
                    set newTop to displayTop + 48
                    set bounds of candidateWindow to {{newLeft, newTop, newLeft + winWidth, newTop + winHeight}}
                    activate
                    return "MOVED"
                end if
            end try
        end repeat
    end repeat
end tell
return "NOT_FOUND"
end run'''
    try:
        result = subprocess.run(
            ["/usr/bin/osascript", "-e", script, tty],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
        return result.returncode == 0 and "MOVED" in result.stdout
    except (OSError, subprocess.TimeoutExpired):
        return False


def main() -> int:
    if sys.platform != "darwin" or len(sys.argv) < 2 or not sys.argv[1].startswith("/dev/"):
        return 0
    display = main_display_bounds()
    if not display:
        return 0
    tty = sys.argv[1]
    # Terminal can finish creating the .command window after its shell starts.
    # Retry through the Manager's initial startup so later windows cannot leave
    # this command's console parked on a secondary display.
    for _ in range(12):
        if move_terminal_tab(tty, display):
            time.sleep(0.35)
        else:
            time.sleep(0.4)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
