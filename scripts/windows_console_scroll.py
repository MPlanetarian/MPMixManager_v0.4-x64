"""Remove the vertical scrollbar from a Windows console.

Conhost draws that bar when the screen buffer is taller than the window.
The Liquid Player embeds that console, so the bar sits on the right of the
player. Matching the buffer to the visible window removes it.
"""

from __future__ import annotations

import sys

SB_BOTH = 3
WS_HSCROLL = 0x00100000
WS_VSCROLL = 0x00200000
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
SWP_FRAMECHANGED = 0x0020
STD_OUTPUT_HANDLE = -11


def window_cells(left: int, top: int, right: int, bottom: int) -> tuple[int, int]:
    """Inclusive console window rect, in cells."""
    return int(right) - int(left) + 1, int(bottom) - int(top) + 1


def buffer_matches_window(buf_w: int, buf_h: int, left: int, top: int, right: int, bottom: int) -> bool:
    """True when the buffer is exactly the visible window, anchored at 0,0.

    A taller buffer is the scrollbar. A window that does not start at the
    origin still scrolls, so that also needs a fit.
    """
    width, height = window_cells(left, top, right, bottom)
    if width < 1 or height < 1:
        return True
    return int(buf_w) == width and int(buf_h) == height and int(left) == 0 and int(top) == 0


def _fit_buffer(kernel32, handle, buf_w: int, buf_h: int, left: int, top: int, right: int, bottom: int) -> bool:
    width, height = window_cells(left, top, right, bottom)
    if width < 1 or height < 1:
        return False
    if buffer_matches_window(buf_w, buf_h, left, top, right, bottom):
        return False
    import ctypes
    from ctypes import wintypes

    class COORD(ctypes.Structure):
        _fields_ = [("X", ctypes.c_short), ("Y", ctypes.c_short)]

    class SMALL_RECT(ctypes.Structure):
        _fields_ = [
            ("Left", ctypes.c_short),
            ("Top", ctypes.c_short),
            ("Right", ctypes.c_short),
            ("Bottom", ctypes.c_short),
        ]

    kernel32.SetConsoleWindowInfo.argtypes = [wintypes.HANDLE, wintypes.BOOL, ctypes.POINTER(SMALL_RECT)]
    kernel32.SetConsoleWindowInfo.restype = wintypes.BOOL
    kernel32.SetConsoleScreenBufferSize.argtypes = [wintypes.HANDLE, COORD]
    kernel32.SetConsoleScreenBufferSize.restype = wintypes.BOOL
    kernel32.SetConsoleCursorPosition.argtypes = [wintypes.HANDLE, COORD]
    kernel32.SetConsoleCursorPosition.restype = wintypes.BOOL

    # The buffer cannot be smaller than the window. Grow first when the
    # visible window is already larger than the buffer, then pin both.
    if int(buf_w) < width or int(buf_h) < height:
        kernel32.SetConsoleScreenBufferSize(handle, COORD(max(int(buf_w), width), max(int(buf_h), height)))
    kernel32.SetConsoleCursorPosition(handle, COORD(0, 0))
    rect = SMALL_RECT(0, 0, width - 1, height - 1)
    kernel32.SetConsoleWindowInfo(handle, True, ctypes.byref(rect))
    kernel32.SetConsoleScreenBufferSize(handle, COORD(width, height))
    return True


def _hide_scrollbar_style(user32, hwnd: int) -> None:
    import ctypes

    if not hwnd:
        return
    user32.ShowScrollBar.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
    user32.ShowScrollBar.restype = ctypes.c_int
    user32.ShowScrollBar(int(hwnd), SB_BOTH, 0)
    get_long = getattr(user32, "GetWindowLongPtrW", None) or user32.GetWindowLongW
    set_long = getattr(user32, "SetWindowLongPtrW", None) or user32.SetWindowLongW
    get_long.restype = ctypes.c_ssize_t
    get_long.argtypes = [ctypes.c_void_p, ctypes.c_int]
    set_long.restype = ctypes.c_ssize_t
    set_long.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_ssize_t]
    style = int(get_long(int(hwnd), -16) or 0)
    cleared = style & ~WS_HSCROLL & ~WS_VSCROLL
    if cleared == style:
        return
    set_long(int(hwnd), -16, cleared)
    user32.SetWindowPos.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
        ctypes.c_int, ctypes.c_int, ctypes.c_uint,
    ]
    user32.SetWindowPos.restype = ctypes.c_int
    user32.SetWindowPos(
        int(hwnd), 0, 0, 0, 0, 0,
        SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED,
    )


def _valid_handle(handle) -> bool:
    if not handle:
        return False
    try:
        value = int(handle)
    except (TypeError, ValueError):
        return False
    return value not in (0, -1, 0xFFFFFFFF, 0xFFFFFFFFFFFFFFFF)


def _console_output_handle(kernel32):
    """The console screen, even when stdout is a pipe."""
    import ctypes
    from ctypes import wintypes

    kernel32.CreateFileW.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
        wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
    ]
    kernel32.CreateFileW.restype = wintypes.HANDLE
    handle = kernel32.CreateFileW(
        "CONOUT$",
        0x80000000 | 0x40000000,
        0x00000001 | 0x00000002,
        None,
        3,
        0,
        None,
    )
    if _valid_handle(handle):
        return handle, True
    kernel32.GetStdHandle.restype = wintypes.HANDLE
    kernel32.GetStdHandle.argtypes = [wintypes.DWORD]
    return kernel32.GetStdHandle(STD_OUTPUT_HANDLE), False


def _read_buffer(kernel32, handle):
    import ctypes
    from ctypes import wintypes

    class COORD(ctypes.Structure):
        _fields_ = [("X", ctypes.c_short), ("Y", ctypes.c_short)]

    class SMALL_RECT(ctypes.Structure):
        _fields_ = [
            ("Left", ctypes.c_short),
            ("Top", ctypes.c_short),
            ("Right", ctypes.c_short),
            ("Bottom", ctypes.c_short),
        ]

    class INFO(ctypes.Structure):
        _fields_ = [
            ("dwSize", COORD),
            ("dwCursorPosition", COORD),
            ("wAttributes", wintypes.WORD),
            ("srWindow", SMALL_RECT),
            ("dwMaximumWindowSize", COORD),
        ]

    kernel32.GetConsoleScreenBufferInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(INFO)]
    kernel32.GetConsoleScreenBufferInfo.restype = wintypes.BOOL
    info = INFO()
    if not kernel32.GetConsoleScreenBufferInfo(handle, ctypes.byref(info)):
        return None
    return info


def hide_attached_console_scrollbar(extra_hwnd: int = 0) -> bool:
    """Fit the console this process is attached to and hide its scrollbar."""
    if sys.platform != "win32":
        return False
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32.GetConsoleWindow.restype = wintypes.HWND
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    handle, close_handle = _console_output_handle(kernel32)
    if not _valid_handle(handle):
        return False
    try:
        info = _read_buffer(kernel32, handle)
        hwnd = int(kernel32.GetConsoleWindow() or 0)
        if info is not None:
            window = info.srWindow
            _fit_buffer(
                kernel32, handle,
                int(info.dwSize.X), int(info.dwSize.Y),
                int(window.Left), int(window.Top), int(window.Right), int(window.Bottom),
            )
        _hide_scrollbar_style(user32, hwnd)
        if extra_hwnd and int(extra_hwnd) != hwnd:
            _hide_scrollbar_style(user32, int(extra_hwnd))
        return info is not None or bool(hwnd)
    finally:
        if close_handle:
            kernel32.CloseHandle(handle)


def hide_process_console_scrollbar(pid: int, hwnd: int = 0) -> bool:
    """Fit a child console. The caller keeps its own console if it has one."""
    if sys.platform != "win32" or not pid:
        return False
    import ctypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.AttachConsole.argtypes = [ctypes.c_uint32]
    kernel32.AttachConsole.restype = ctypes.c_int
    kernel32.FreeConsole.restype = ctypes.c_int
    if not kernel32.AttachConsole(ctypes.c_uint32(int(pid))):
        if ctypes.get_last_error() != 5:
            if hwnd:
                _hide_scrollbar_style(ctypes.WinDLL("user32", use_last_error=True), int(hwnd))
            return False
        kernel32.FreeConsole()
        if not kernel32.AttachConsole(ctypes.c_uint32(int(pid))):
            if hwnd:
                _hide_scrollbar_style(ctypes.WinDLL("user32", use_last_error=True), int(hwnd))
            return False
    try:
        return hide_attached_console_scrollbar(int(hwnd or 0))
    finally:
        kernel32.FreeConsole()
