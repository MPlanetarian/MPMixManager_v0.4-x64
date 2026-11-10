"""Focus an open MP Gui window. Exit 0 when one was found."""

from __future__ import annotations

import ctypes
import sys

TITLE_PREFIX = "MP Mix Manager (Liquid Glass"


def focus_title(prefix: str = TITLE_PREFIX) -> bool:
    if sys.platform != "win32":
        return False
    user32 = ctypes.windll.user32
    found: list[int] = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def _enum(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, length + 1)
        if buffer.value.startswith(prefix):
            found.append(int(hwnd))
            return False
        return True

    user32.EnumWindows(_enum, 0)
    if not found:
        return False
    hwnd = found[0]
    user32.ShowWindow(hwnd, 9)
    user32.SetForegroundWindow(hwnd)
    return True


def main(argv: list[str] | None = None) -> int:
    prefix = TITLE_PREFIX
    args = list(sys.argv[1:] if argv is None else argv)
    if args:
        prefix = args[0]
    return 0 if focus_title(prefix) else 1


if __name__ == "__main__":
    raise SystemExit(main())
