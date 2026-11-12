"""Rounded corners for the standalone MP Visualizer window.

Every MP Liquid Player window is a borderless rectangle whose corners are cut
away: XShape on X11, ``SetWindowRgn`` on Windows, and a masked layer on macOS.
The standalone MP Visualizer is bonded directly behind the player at the same
size and position, so its square corners showed through the rounded ones as
black wedges.

This module applies the *same* rounded rectangle to the visualizer window, with
the same radius the Liquid Glass renderers use (``radius_px = 36``), so the two
windows share one silhouette. Fullscreen windows (screen saver, F10/F11 spans,
4K) are left unshaped on purpose: they are meant to fill the screen.
"""
from __future__ import annotations

import ctypes
import sys
from ctypes import c_bool, c_char_p, c_double, c_int, c_uint32, c_uint64, c_void_p
from typing import Optional, Tuple

# Keep in sync with LiquidGlassRenderer.radius_px / LiquidGlassRendererOpenGL.radius_px.
DEFAULT_CORNER_RADIUS = 36

# XShape kind/operation constants: ShapeBounding and ShapeSet are both 0.
SHAPE_BOUNDING = 0
SHAPE_SET = 0


class RoundedWindowShaper:
    """Clip a borderless window to the Liquid Glass rounded rectangle."""

    def __init__(self, radius: int = DEFAULT_CORNER_RADIUS) -> None:
        self.radius = max(8, int(radius))
        self._x11 = None
        self._xext = None
        self._x11_failed = False
        self._own_display = None
        self._applied: Optional[Tuple[int, int, int, bool]] = None

    # -- public -----------------------------------------------------------
    def apply(self, *, width: int, height: int, enabled: bool = True,
              x11_window: int = 0, x11_display=None,
              win32_window: int = 0, cocoa_window: int = 0) -> bool:
        """Shape (or unshape) ``window`` so its corners match the player.

        ``enabled=False`` removes the mask again, which is what a fullscreen
        window needs. Returns True when the platform accepted the request.
        """
        width, height = int(width), int(height)
        if enabled and (width < 8 or height < 8):
            return False
        window_id = int(x11_window or win32_window or cocoa_window or 0)
        key = (window_id, width, height, bool(enabled))
        if key == self._applied:
            return True
        if sys.platform == "win32":
            ok = self._apply_windows(win32_window, width, height, enabled)
        elif sys.platform == "darwin":
            ok = self._apply_macos(cocoa_window, enabled)
        else:
            ok = self._apply_x11(x11_window, x11_display, width, height, enabled)
        if ok:
            self._applied = key
        return ok

    # -- Linux / X11 ------------------------------------------------------
    def _ensure_x11(self) -> bool:
        if self._x11 is not None:
            return True
        if self._x11_failed:
            return False
        try:
            x11 = ctypes.CDLL("libX11.so.6")
            x11.XOpenDisplay.restype = c_void_p
            x11.XOpenDisplay.argtypes = [c_char_p]
            x11.XCloseDisplay.argtypes = [c_void_p]
            x11.XCreatePixmap.argtypes = [c_void_p, c_uint64, c_uint32, c_uint32, c_uint32]
            x11.XCreatePixmap.restype = c_uint64
            x11.XFreePixmap.argtypes = [c_void_p, c_uint64]
            x11.XCreateGC.argtypes = [c_void_p, c_uint64, c_uint64, c_void_p]
            x11.XCreateGC.restype = c_void_p
            x11.XFreeGC.argtypes = [c_void_p, c_void_p]
            x11.XSetForeground.argtypes = [c_void_p, c_void_p, c_uint64]
            x11.XFillRectangle.argtypes = [c_void_p, c_uint64, c_void_p, c_int, c_int, c_uint32, c_uint32]
            x11.XFillArc.argtypes = [c_void_p, c_uint64, c_void_p, c_int, c_int, c_uint32, c_uint32, c_int, c_int]
            x11.XFlush.argtypes = [c_void_p]
            ext = ctypes.CDLL("libXext.so.6")
            ext.XShapeCombineMask.argtypes = [c_void_p, c_uint64, c_int, c_int, c_int, c_uint64, c_int]
            ext.XShapeCombineMask.restype = None
        except (AttributeError, OSError):
            self._x11_failed = True
            return False
        self._x11, self._xext = x11, ext
        return True

    def _apply_x11(self, window: int, display, width: int, height: int, enabled: bool) -> bool:
        if not self._ensure_x11():
            return False
        window = int(window or 0)
        if not window:
            return False
        display = display or self._own_display
        if not display:
            display = self._x11.XOpenDisplay(None)
            if not display:
                return False
            self._own_display = display
        x11, ext = self._x11, self._xext
        if not enabled:
            # Setting a None mask restores the original rectangle.
            ext.XShapeCombineMask(display, window, SHAPE_BOUNDING, 0, 0, 0, SHAPE_SET)
            x11.XFlush(display)
            return True
        radius = max(8, min(self.radius, width // 2 - 1, height // 2 - 1))
        mask = x11.XCreatePixmap(display, window, width, height, 1)
        if not mask:
            return False
        gc = x11.XCreateGC(display, mask, 0, None)
        if not gc:
            x11.XFreePixmap(display, mask)
            return False
        diameter = radius * 2
        x11.XSetForeground(display, gc, 0)
        x11.XFillRectangle(display, mask, gc, 0, 0, width, height)
        x11.XSetForeground(display, gc, 1)
        x11.XFillRectangle(display, mask, gc, radius, 0, width - diameter, height)
        x11.XFillRectangle(display, mask, gc, 0, radius, width, height - diameter)
        x11.XFillArc(display, mask, gc, 0, 0, diameter, diameter, 90 * 64, 90 * 64)
        x11.XFillArc(display, mask, gc, width - diameter, 0, diameter, diameter, 0, 90 * 64)
        x11.XFillArc(display, mask, gc, 0, height - diameter, diameter, diameter, 180 * 64, 90 * 64)
        x11.XFillArc(display, mask, gc, width - diameter, height - diameter, diameter, diameter, 270 * 64, 90 * 64)
        ext.XShapeCombineMask(display, window, SHAPE_BOUNDING, 0, 0, mask, SHAPE_SET)
        x11.XFreeGC(display, gc)
        x11.XFreePixmap(display, mask)
        x11.XFlush(display)
        return True

    # -- Windows ----------------------------------------------------------
    def _apply_windows(self, hwnd: int, width: int, height: int, enabled: bool) -> bool:
        hwnd = int(hwnd or 0)
        if not hwnd:
            return False
        try:
            gdi32 = ctypes.windll.gdi32
            user32 = ctypes.windll.user32
            # Win32 BOOL is a 4-byte int, not a C99 bool.
            user32.SetWindowRgn.argtypes = [c_void_p, c_void_p, c_int]
            user32.SetWindowRgn.restype = c_int
            if not enabled:
                # A NULL region restores the default rectangular window shape.
                return bool(user32.SetWindowRgn(c_void_p(hwnd), None, 1))
            gdi32.CreateRoundRectRgn.argtypes = [c_int, c_int, c_int, c_int, c_int, c_int]
            gdi32.CreateRoundRectRgn.restype = c_void_p
            gdi32.DeleteObject.argtypes = [c_void_p]
            gdi32.DeleteObject.restype = c_int
            radius = max(8, min(self.radius, width // 2 - 1, height // 2 - 1))
            diameter = radius * 2
            region = gdi32.CreateRoundRectRgn(0, 0, width + 1, height + 1, diameter, diameter)
            if not region:
                return False
            if not user32.SetWindowRgn(c_void_p(hwnd), c_void_p(region), 1):
                gdi32.DeleteObject(c_void_p(region))
                return False
            # SetWindowRgn takes ownership of the region on success.
            return True
        except (AttributeError, OSError):
            return False

    # -- macOS ------------------------------------------------------------
    def _apply_macos(self, ns_window: int, enabled: bool) -> bool:
        ns_window = int(ns_window or 0)
        if not ns_window:
            return False
        try:
            objc = ctypes.cdll.LoadLibrary("/usr/lib/libobjc.A.dylib")
            ctypes.cdll.LoadLibrary("/System/Library/Frameworks/AppKit.framework/AppKit")
            addr = ctypes.cast(objc.objc_msgSend, c_void_p).value
            send_id = ctypes.CFUNCTYPE(c_void_p, c_void_p, c_void_p)(addr)
            send_bool = ctypes.CFUNCTYPE(None, c_void_p, c_void_p, c_bool)(addr)
            send_double = ctypes.CFUNCTYPE(None, c_void_p, c_void_p, c_double)(addr)
            send_obj = ctypes.CFUNCTYPE(None, c_void_p, c_void_p, c_void_p)(addr)
            sel = objc.sel_registerName
            sel.restype = c_void_p
            sel.argtypes = [c_char_p]
            ns_color_cls = objc.objc_getClass
            ns_color_cls.restype = c_void_p
            ns_color_cls.argtypes = [c_char_p]
            color_cls = c_void_p(ns_color_cls(b"NSColor"))
        except (AttributeError, OSError):
            return False

        window = c_void_p(ns_window)
        content = send_id(window, sel(b"contentView"))
        if not content:
            return False
        # A layer-backed content view is what makes the radius take effect.
        send_bool(c_void_p(content), sel(b"setWantsLayer:"), True)
        layer = send_id(c_void_p(content), sel(b"layer"))
        if not layer:
            return False
        send_double(c_void_p(layer), sel(b"setCornerRadius:"), float(self.radius) if enabled else 0.0)
        send_bool(c_void_p(layer), sel(b"setMasksToBounds:"), bool(enabled))

        # Without a clear window background the cut-away corners would show
        # the window's own black fill. The Liquid Glass player makes the same
        # trade on macOS: a transparent window with masked corners.
        if not enabled:
            # Rectangle again: restore an opaque window and drop the radius.
            send_bool(window, sel(b"setOpaque:"), True)
            return True
        send_bool(window, sel(b"setOpaque:"), False)
        if color_cls:
            clear = send_id(color_cls, sel(b"clearColor"))
            if clear:
                send_obj(window, sel(b"setBackgroundColor:"), c_void_p(clear))
        return True
