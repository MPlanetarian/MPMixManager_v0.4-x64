"""Move the borderless MP Liquid window on Windows after the console is showing.

The glass window has no title bar. Dragging is the top strip, the outer bezel,
or Alt / the Windows key. Once the player console is placed over the glass,
those clicks land on the console (owned by conhost, so its window procedure
cannot be replaced) and the glass never hears them.

While the pointer is in that drag strip, the console lets the click through.
The glass window then runs the standard borderless move (SC_MOVE). The console
is repositioned on every move so it stays in the well. If the console refuses
click-through, the same strip is dragged by polling the mouse button.
"""
from __future__ import annotations

import ctypes
import sys
import time

HEADER_DRAG_PX = 90
DOUBLE_CLICK_SEC = 0.45
DOUBLE_CLICK_SLOP = 35
SLIDER_BAND = 44
SLIDER_MARGIN = 40

WM_WINDOWPOSCHANGED = 0x0047
WM_SYSCOMMAND = 0x0112
WM_NCHITTEST = 0x0084
WM_NCLBUTTONDOWN = 0x00A1
SC_SIZE = 0xF000
SC_MOVE = 0xF010
SC_MAXIMIZE = 0xF030
SC_RESTORE = 0xF120
HTCLIENT = 1
HTCAPTION = 2
GWLP_WNDPROC = -4
GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x00000020
SWP_FRAME_ONLY = 0x0001 | 0x0002 | 0x0004 | 0x0010 | 0x0020  # NOSIZE NOMOVE NOZORDER NOACTIVATE FRAMECHANGED

_USER32 = None
_KERNEL32 = None


class _POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class _RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


def _user32():
    global _USER32
    if _USER32 is None:
        dll = ctypes.WinDLL("user32", use_last_error=True)
        dll.GetCursorPos.argtypes = [ctypes.POINTER(_POINT)]
        dll.GetCursorPos.restype = ctypes.c_int
        dll.GetWindowRect.argtypes = [ctypes.c_void_p, ctypes.POINTER(_RECT)]
        dll.GetWindowRect.restype = ctypes.c_int
        dll.GetAsyncKeyState.argtypes = [ctypes.c_int]
        dll.GetAsyncKeyState.restype = ctypes.c_short
        dll.WindowFromPoint.argtypes = [_POINT]
        dll.WindowFromPoint.restype = ctypes.c_void_p
        dll.GetParent.argtypes = [ctypes.c_void_p]
        dll.GetParent.restype = ctypes.c_void_p
        dll.GetWindowLongPtrW.argtypes = [ctypes.c_void_p, ctypes.c_int]
        dll.GetWindowLongPtrW.restype = ctypes.c_ssize_t
        dll.SetWindowLongPtrW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_ssize_t]
        dll.SetWindowLongPtrW.restype = ctypes.c_ssize_t
        dll.SetWindowPos.argtypes = [
            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint,
        ]
        dll.SetWindowPos.restype = ctypes.c_int
        dll.CallWindowProcW.argtypes = [
            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t,
        ]
        dll.CallWindowProcW.restype = ctypes.c_ssize_t
        dll.DefWindowProcW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t]
        dll.DefWindowProcW.restype = ctypes.c_ssize_t
        dll.ReleaseCapture.argtypes = []
        dll.ReleaseCapture.restype = ctypes.c_int
        _USER32 = dll
    return _USER32


def _kernel32():
    global _KERNEL32
    if _KERNEL32 is None:
        dll = ctypes.WinDLL("kernel32", use_last_error=True)
        dll.SetLastError.argtypes = [ctypes.c_uint32]
        _KERNEL32 = dll
    return _KERNEL32


def _clear_error() -> None:
    _kernel32().SetLastError(0)


_WNDPROC = ctypes.WINFUNCTYPE(
    ctypes.c_ssize_t, ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t,
)


def as_hwnd(value) -> int:
    if value is None or isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return int(value)
    raw = getattr(value, "value", None)
    try:
        return int(raw or 0)
    except (TypeError, ValueError):
        return 0


def unpack_point(lparam) -> tuple[int, int]:
    val = int(lparam) & 0xFFFFFFFF
    x = val & 0xFFFF
    y = (val >> 16) & 0xFFFF
    if x >= 0x8000:
        x -= 0x10000
    if y >= 0x8000:
        y -= 0x10000
    return x, y


def pack_point(x: int, y: int) -> int:
    return (int(x) & 0xFFFF) | ((int(y) & 0xFFFF) << 16)


def outer_bezel(x, y, width, height, bezel_px) -> bool:
    margin = max(float(bezel_px), 1.0)
    return x < margin or y < margin or x >= width - margin or y >= height - margin


def on_opacity_slider(x, y, width, height, enabled) -> bool:
    if not enabled:
        return False
    return y >= height - SLIDER_BAND and SLIDER_MARGIN <= x <= width - SLIDER_MARGIN


def glass_hit(x, y, width, height, *, on_close, on_slider, on_outer, alt_down, maximized) -> int:
    """Hit-test result for a point in glass client coordinates.

    HTCAPTION is the drag strip. The close button and the opacity slider stay
    client clicks. A maximized window still reports HTCAPTION so a second click
    can restore it; the move command itself is refused while maximized.
    """
    del maximized
    if on_close:
        return HTCLIENT
    if on_slider and not alt_down:
        return HTCLIENT
    if alt_down or y <= HEADER_DRAG_PX or on_outer:
        return HTCAPTION
    return HTCLIENT


def console_should_pass_clicks(y, *, alt_down) -> bool:
    """True when the console overlay should ignore the pointer.

    The style is per window. It is turned on only while the pointer is already
    in the drag strip (or Alt is held), so the rest of the console still
    receives clicks.
    """
    if alt_down:
        return True
    return y <= HEADER_DRAG_PX


def moved_origin(origin, press, cursor) -> tuple[int, int]:
    return (int(origin[0] + cursor[0] - press[0]), int(origin[1] + cursor[1] - press[1]))


def left_button_held() -> bool:
    if sys.platform != "win32":
        return False
    return bool(_user32().GetAsyncKeyState(0x01) & 0x8000)


def release_stuck_mouse(renderer) -> None:
    """Drop a GLFW button that never received mouse-up.

    After the console covers the glass, the release is delivered to the console.
    GLFW would otherwise keep mouse_down set and pin the window in place.
    """
    if renderer is None or not getattr(renderer, "mouse_down", False):
        return
    try:
        held = left_button_held()
    except Exception:
        return
    if not held:
        renderer.mouse_down = False


def install_on_host(host):
    if sys.platform != "win32":
        return None
    drag = getattr(host, "_glass_drag", None)
    if drag is None:
        drag = GlassWindowDrag(host)
        host._glass_drag = drag
    renderer = getattr(host, "renderer", None)
    glass = 0
    if renderer is not None and hasattr(renderer, "win32_window"):
        try:
            glass = as_hwnd(renderer.win32_window())
        except Exception:
            glass = 0
    drag.attach(glass, as_hwnd(getattr(host, "child_xid", 0)))
    return drag


def release_on_host(host) -> None:
    drag = getattr(host, "_glass_drag", None)
    if drag is None:
        return
    host._glass_drag = None
    try:
        drag.close()
    except Exception:
        pass


class GlassWindowDrag:
    def __init__(self, host):
        self.host = host
        self.glass_hwnd = 0
        self.console_hwnd = 0
        self._proc = None
        self._old_proc = 0
        self._subclassed = False
        self._through = None
        self._click_through_works = True
        self._moving = False
        self._in_follow = False
        self._last_caption = 0.0
        self._last_caption_at = (0, 0)
        self._poll_dragging = False
        self._poll_armed = False
        self._origin = (0, 0)
        self._press = (0, 0)

    def attach(self, glass_hwnd, console_hwnd=0) -> None:
        glass_hwnd = as_hwnd(glass_hwnd)
        console_hwnd = as_hwnd(console_hwnd)
        if glass_hwnd:
            self.glass_hwnd = glass_hwnd
        if console_hwnd and console_hwnd != self.console_hwnd:
            self.console_hwnd = console_hwnd
            self._through = None
        if self.glass_hwnd and not self._subclassed:
            self._subclass()

    def close(self) -> None:
        try:
            if self.console_hwnd:
                self._set_click_through(False)
        except Exception:
            pass
        self._unsubclass()
        self._poll_dragging = False
        self.host._os_dragging = False

    def update(self) -> None:
        """Call from the player frame, before GLFW polls events."""
        if not self.glass_hwnd:
            return
        use_poll = not self._subclassed or not self._click_through_works
        if self.console_hwnd:
            try:
                over = self._cursor_over_player()
            except Exception:
                over = False
            want = False
            if over:
                try:
                    want = self._want_pass()
                except Exception:
                    want = False
            if not self._set_click_through(want):
                use_poll = True
        if self._poll_dragging:
            use_poll = True
        if use_poll:
            self._poll_from_cursor()

    def poll_pointer(self, held: bool, sx: int, sy: int, on_console: bool) -> str:
        """Drag the glass from the console when click-through is unavailable."""
        if self._poll_dragging:
            if not held:
                self._poll_dragging = False
                self._poll_armed = False
                self.host._os_dragging = False
                self._move_to(sx, sy)
                return "drop"
            self._move_to(sx, sy)
            return "drag"
        if not held:
            self._poll_armed = False
            return "pass"
        if self._poll_armed or not on_console:
            self._poll_armed = True
            return "pass"
        self._poll_armed = True
        try:
            x, y, width, height = self._client_box(sx, sy)
            caption = self._is_caption(x, y, width, height)
        except Exception:
            return "pass"
        if caption and self._is_double_caption(sx, sy):
            self._last_caption = 0.0
            self.host._os_dragging = False
            self.host.toggle_maximize()
            return "toggle"
        if not caption:
            return "pass"
        self._remember_caption(sx, sy)
        if getattr(self.host, "is_maximized", False):
            return "pass"
        self._poll_dragging = True
        self.host._os_dragging = True
        self._origin = tuple(self.host.renderer.window_pos())
        self._press = (int(sx), int(sy))
        return "drag"

    def _dispatch(self, hwnd, msg, wparam, lparam):
        if msg == WM_NCHITTEST:
            sx, sy = unpack_point(lparam)
            x, y, width, height = self._client_box(sx, sy)
            return self._hit_value(x, y, width, height)
        if msg == WM_NCLBUTTONDOWN and int(wparam) == HTCAPTION:
            return self._on_caption_down(hwnd, lparam)
        if msg == WM_SYSCOMMAND:
            command = int(wparam) & 0xFFF0
            if command == SC_MOVE and getattr(self.host, "is_maximized", False):
                return 0
            if command in (SC_MAXIMIZE, SC_RESTORE, SC_SIZE):
                return 0
            return self._call_old(hwnd, msg, wparam, lparam)
        if msg == WM_WINDOWPOSCHANGED:
            result = self._call_old(hwnd, msg, wparam, lparam)
            self._follow()
            return result
        return self._call_old(hwnd, msg, wparam, lparam)

    def _on_caption_down(self, hwnd, lparam) -> int:
        sx, sy = unpack_point(lparam)
        if self._is_double_caption(sx, sy):
            self._last_caption = 0.0
            self.host.toggle_maximize()
            return 0
        self._remember_caption(sx, sy)
        if getattr(self.host, "is_maximized", False) or self._moving:
            return 0
        self._moving = True
        try:
            self._start_system_move(hwnd)
        finally:
            self._moving = False
        return 0

    def _start_system_move(self, hwnd) -> None:
        # Call DefWindowProc directly. GLFW's own procedure does not start a move
        # on a borderless window, and SC_MOVE | HTCAPTION is the borderless drag.
        user32 = _user32()
        user32.ReleaseCapture()
        user32.DefWindowProcW(int(hwnd), WM_SYSCOMMAND, 0xF012, 0)

    def _wndproc(self, hwnd, msg, wparam, lparam):
        try:
            return self._dispatch(hwnd, int(msg), wparam, lparam)
        except Exception:
            try:
                return self._call_old(hwnd, msg, wparam, lparam)
            except Exception:
                return 0

    def _subclass(self) -> None:
        if self._subclassed or not self.glass_hwnd or sys.platform != "win32":
            return
        try:
            self._proc = _WNDPROC(self._wndproc)
            user32 = _user32()
            _clear_error()
            previous = user32.SetWindowLongPtrW(
                self.glass_hwnd, GWLP_WNDPROC, ctypes.cast(self._proc, ctypes.c_void_p).value or 0,
            )
            if not previous and ctypes.get_last_error():
                self._proc = None
                return
            self._old_proc = int(previous or 0)
            self._subclassed = bool(self._old_proc)
        except Exception:
            self._proc = None
            self._subclassed = False

    def _unsubclass(self) -> None:
        if not self._subclassed or not self._old_proc or not self.glass_hwnd:
            self._subclassed = False
            self._proc = None
            return
        try:
            _user32().SetWindowLongPtrW(self.glass_hwnd, GWLP_WNDPROC, int(self._old_proc))
        except Exception:
            pass
        self._subclassed = False
        self._old_proc = 0
        self._proc = None

    def _call_old(self, hwnd, msg, wparam, lparam):
        user32 = _user32()
        if self._old_proc:
            return int(user32.CallWindowProcW(
                ctypes.c_void_p(int(self._old_proc)), hwnd, int(msg), int(wparam), int(lparam),
            ) or 0)
        return int(user32.DefWindowProcW(hwnd, int(msg), int(wparam), int(lparam)) or 0)

    def _follow(self) -> None:
        if self._in_follow:
            return
        self._in_follow = True
        try:
            renderer = getattr(self.host, "renderer", None)
            if renderer is None:
                return
            rect = self._window_rect(self.glass_hwnd) if self.glass_hwnd else None
            if rect:
                renderer._cur_pos = (int(rect[0]), int(rect[1]))
            place = getattr(self.host, "_place_terminal", None)
            if place is None or not as_hwnd(getattr(self.host, "child_xid", 0)):
                return
            try:
                place(force=True)
            except TypeError:
                place()
        finally:
            self._in_follow = False

    def _set_click_through(self, enabled: bool) -> bool:
        if not self.console_hwnd:
            return True
        if self._through is enabled and self._click_through_works:
            return True
        if sys.platform != "win32":
            self._click_through_works = False
            return False
        try:
            user32 = _user32()
            _clear_error()
            style = int(user32.GetWindowLongPtrW(self.console_hwnd, GWL_EXSTYLE) or 0)
            new_style = (style | WS_EX_TRANSPARENT) if enabled else (style & ~WS_EX_TRANSPARENT)
            _clear_error()
            previous = user32.SetWindowLongPtrW(self.console_hwnd, GWL_EXSTYLE, new_style)
            if not previous and ctypes.get_last_error():
                self._click_through_works = False
                return False
            user32.SetWindowPos(self.console_hwnd, None, 0, 0, 0, 0, SWP_FRAME_ONLY)
        except Exception:
            self._click_through_works = False
            return False
        self._through = enabled
        self._click_through_works = True
        return True

    def _poll_from_cursor(self) -> None:
        pos = self._cursor_pos()
        if pos is None:
            return
        sx, sy = pos
        try:
            on_console = self._cursor_on_console(sx, sy)
        except Exception:
            on_console = False
        self.poll_pointer(self._button_down(), sx, sy, on_console)

    def _want_pass(self) -> bool:
        pos = self._cursor_pos()
        if pos is None:
            return False
        sx, sy = pos
        _x, y, _w, _h = self._client_box(sx, sy)
        return console_should_pass_clicks(y, alt_down=self._alt_down())

    def _cursor_over_player(self) -> bool:
        pos = self._cursor_pos()
        if pos is None:
            return False
        ox, oy, width, height = self._metrics()
        sx, sy = pos
        return ox <= sx < ox + width and oy <= sy < oy + height

    def _client_box(self, sx, sy):
        ox, oy, width, height = self._metrics()
        return sx - ox, sy - oy, width, height

    def _metrics(self):
        if self.glass_hwnd:
            rect = self._window_rect(self.glass_hwnd)
            if rect:
                return rect
        renderer = self.host.renderer
        pos = renderer.window_pos()
        size = renderer.window_size()
        return int(pos[0]), int(pos[1]), int(size[0]), int(size[1])

    def _hit_value(self, x, y, width, height) -> int:
        return glass_hit(
            x, y, width, height,
            on_close=self._close(x, y, width, height),
            on_slider=on_opacity_slider(x, y, width, height, hasattr(self.host, "_slider_dragging")),
            on_outer=outer_bezel(x, y, width, height, getattr(self.host.renderer, "bezel_px", 7)),
            alt_down=self._alt_down(),
            maximized=bool(getattr(self.host, "is_maximized", False)),
        )

    def _is_caption(self, x, y, width, height) -> bool:
        return self._hit_value(x, y, width, height) == HTCAPTION

    def _close(self, x, y, width, height) -> bool:
        closer = getattr(self.host, "_on_close", None)
        if closer is None:
            return False
        try:
            return bool(closer(x, y, width, height))
        except Exception:
            return False

    def _is_double_caption(self, sx, sy) -> bool:
        if not self._last_caption:
            return False
        if time.monotonic() - self._last_caption >= DOUBLE_CLICK_SEC:
            return False
        px, py = self._last_caption_at
        return abs(sx - px) < DOUBLE_CLICK_SLOP and abs(sy - py) < DOUBLE_CLICK_SLOP

    def _remember_caption(self, sx, sy) -> None:
        self._last_caption = time.monotonic()
        self._last_caption_at = (int(sx), int(sy))

    def _move_to(self, sx, sy) -> None:
        renderer = getattr(self.host, "renderer", None)
        if renderer is None:
            return
        renderer.set_window_pos(*moved_origin(self._origin, self._press, (sx, sy)))
        self._follow()

    def _window_rect(self, hwnd):
        if sys.platform != "win32" or not hwnd:
            return None
        rect = _RECT()
        if not _user32().GetWindowRect(int(hwnd), ctypes.byref(rect)):
            return None
        return int(rect.left), int(rect.top), int(rect.right - rect.left), int(rect.bottom - rect.top)

    def _cursor_pos(self):
        if sys.platform != "win32":
            return None
        point = _POINT()
        if not _user32().GetCursorPos(ctypes.byref(point)):
            return None
        return int(point.x), int(point.y)

    def _button_down(self) -> bool:
        return left_button_held()

    def _alt_down(self) -> bool:
        if sys.platform != "win32":
            return False
        user32 = _user32()
        for key in (0x12, 0x5B, 0x5C):  # Alt, left Windows, right Windows
            if user32.GetAsyncKeyState(key) & 0x8000:
                return True
        return False

    def _cursor_on_console(self, sx, sy) -> bool:
        if not self.console_hwnd or sys.platform != "win32":
            return False
        user32 = _user32()
        hwnd = as_hwnd(user32.WindowFromPoint(_POINT(int(sx), int(sy))))
        target = int(self.console_hwnd)
        seen = set()
        while hwnd and hwnd not in seen:
            seen.add(hwnd)
            if hwnd == target:
                return True
            parent = as_hwnd(user32.GetParent(hwnd))
            if parent == hwnd:
                break
            hwnd = parent
        return False
