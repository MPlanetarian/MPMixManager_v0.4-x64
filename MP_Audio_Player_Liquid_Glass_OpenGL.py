#!/usr/bin/env python3
"""OpenGL liquid-glass window hosting the unmodified MP Audio Player.

The player script is started as-is inside a VTE terminal. The whole window
is clear still-water glass. The terminal background is clear, so that glass
shows through, and the player's boxed panels are a darker glass underneath.
Supports wider GPU cards like AMD Radeon, Intel, NVIDIA, and older OpenGL hardware.
"""

from __future__ import annotations

import os

# Ensure PyOpenGL uses the GLX platform when running on X11
os.environ.setdefault("PYOPENGL_PLATFORM", "glx")

import signal
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from liquid_glass_opengl import (  # noqa: E402
    LiquidGlassRendererOpenGL,
    read_player_theme,
)

COLS = 120
ROWS = 40


def player_panel_rects(cols, rows, char_w, char_h, origin_x, origin_y, mode="NORMAL"):
    """Pixel boxes for the player panels in ``_draw_frame`` across Normal, Mini, and Micro modes."""
    def box(col, row, box_cols, box_rows):
        return (
            origin_x + col * char_w,
            origin_y + row * char_h,
            box_cols * char_w,
            box_rows * char_h,
        )

    if mode == "MICRO":
        return (
            box(2, 0, min(cols - 4, 70), rows),
            (0.0, 0.0, 0.0, 0.0),
        )
    elif mode == "MINI":
        return (
            box(2, 0, min(cols - 4, 74), 3),
            box(2, 3, min(cols - 4, 74), max(1, rows - 3)),
        )
    else:
        iw = 115 if cols >= 122 else max(20, cols - 6)
        viz_rows = 7 if rows >= 34 else (5 if rows >= 28 else 3)
        before = 4 + 1 + 1 + 3 + viz_rows + 1
        body_rows = max(1, rows - (before + 1) - 4)
        return (
            box(2, 0, iw + 2, 4),
            box(2, before, iw + 2, body_rows + 2),
        )


def _import_gtk():
    os.environ["GDK_BACKEND"] = "x11"
    import gi

    gi.require_version("Gdk", "3.0")
    gi.require_version("Gtk", "3.0")
    gi.require_version("GdkX11", "3.0")
    gi.require_version("Vte", "2.91")
    from gi.repository import GdkX11, GLib, Gtk, Vte

    if not hasattr(GdkX11, "X11Display"):
        raise RuntimeError("GDK X11 backend is required for the liquid-glass window")
    return GLib, Gtk, Vte


def player_argv(mode="NORMAL"):
    cmd = [sys.executable, str(ROOT / "MP_Audio_Player.py"), "--interactive"]
    if mode == "MINI":
        cmd.append("--mini")
    elif mode == "MICRO":
        cmd.append("--micro")
    return cmd


def embed_check_argv():
    code = "import time; print('LIQUID_GLASS_CHILD', flush=True); time.sleep(30)"
    return [sys.executable, "-c", code]


def _child_env():
    env = {key: value for key, value in os.environ.items() if key != "GDK_BACKEND"}
    env["TERM"] = "xterm-256color"
    env["COLORTERM"] = "truecolor"
    env["MP_LIQUID_GLASS"] = "1"
    return [f"{key}={value}" for key, value in env.items()]


class GlassHost:
    """OpenGL glass chrome with a solid terminal window in the centre well."""

    def __init__(self, argv, embed_check=False, mode="NORMAL"):
        self.argv = list(argv)
        self.embed_check = embed_check
        self.mode = mode.upper()
        self.renderer = None
        self.gtk_window = None
        self.terminal = None
        self.child_xid = 0
        self.child_pid = 0
        self.spawn_error = None
        self.child_done = False
        self.is_maximized = False
        self._saved_rect = None
        self._last_top_click = 0.0
        self._last_top_click_x = 0
        self._last_top_click_y = 0
        self._target_cols = 74 if self.mode in ("MINI", "MICRO") else COLS
        self._target_rows = 14 if self.mode == "MINI" else (7 if self.mode == "MICRO" else ROWS)

    def _on_bezel(self, x, y, width, height):
        margin = self.renderer.bezel_px
        return x < margin or y < margin or x >= width - margin or y >= height - margin

    def _on_top_bezel(self, x, y, width, height):
        margin = self.renderer.bezel_px
        return y < margin + 40 and not self._on_close(x, y, width, height)

    def _on_close(self, x, y, width, height):
        margin = self.renderer.bezel_px
        cx = width - margin * 0.72
        cy = margin * 0.62
        radius = margin * 0.30
        return (x - cx) ** 2 + (y - cy) ** 2 <= radius * radius

    def _well_rect(self):
        gx, gy = self.renderer.window_pos()
        width, height = self.renderer.window_size()
        margin = self.renderer.bezel_px
        return (
            gx + margin,
            gy + margin,
            max(32, width - 2 * margin),
            max(32, height - 2 * margin),
        )

    def _place_terminal(self):
        x, y, inner_w, inner_h = self._well_rect()
        if self.gtk_window is not None:
            self.gtk_window.move(int(x), int(y))
            cur_size = getattr(self, "_last_term_size", None)
            if cur_size != (int(inner_w), int(inner_h)):
                self.gtk_window.resize(int(inner_w), int(inner_h))
                self._last_term_size = (int(inner_w), int(inner_h))
        self.renderer.place_terminal(self.child_xid, x, y, inner_w, inner_h)
        self._sync_panels()

    def _sync_panels(self):
        term = self.terminal
        if term is None or self.renderer is None:
            return
        char_w = int(term.get_char_width() or 0)
        char_h = int(term.get_char_height() or 0)
        if char_w < 4 or char_h < 8:
            char_w, char_h = 9, 18
        margin = self.renderer.bezel_px
        cols = getattr(self, "_target_cols", COLS)
        rows = getattr(self, "_target_rows", ROWS)
        self.renderer.set_panels(player_panel_rects(cols, rows, char_w, char_h, margin, margin, mode=self.mode))

    def toggle_maximize(self):
        if self.terminal is None or self.renderer is None:
            return
        char_w = int(self.terminal.get_char_width() or 0)
        char_h = int(self.terminal.get_char_height() or 0)
        if char_w < 4 or char_h < 8:
            char_w, char_h = 9, 18
        margin = self.renderer.bezel_px

        if not self.is_maximized:
            # Save current window position and size
            self._saved_rect = (self.renderer.window_pos(), self.renderer.window_size())
            wx, wy, ww, wh = self.renderer.get_workarea()
            max_cols = max(40, int((ww - 2 * margin) // char_w))
            max_rows = max(10, int((wh - 2 * margin) // char_h))
            self._target_cols = max_cols
            self._target_rows = max_rows
            self.renderer.set_window_pos(wx, wy)
            self.renderer.set_window_size(ww, wh)
            self.terminal.set_size(max_cols, max_rows)
            self._place_terminal()
            self.is_maximized = True
        else:
            # Restore to fixed default / previous size
            pos, size = getattr(self, "_saved_rect", ((72, 64), (1280, 820)))
            if self.mode == "MINI":
                cols, rows = 74, 14
            elif self.mode == "MICRO":
                cols, rows = 74, 7
            else:
                cols, rows = COLS, ROWS
            self._target_cols = cols
            self._target_rows = rows
            win_w = cols * char_w + 2 * margin
            win_h = rows * char_h + 2 * margin
            self.renderer.set_window_pos(pos[0], pos[1])
            self.renderer.set_window_size(win_w, win_h)
            self.terminal.set_size(cols, rows)
            self._place_terminal()
            self.is_maximized = False

    def set_mode(self, mode: str):
        self.mode = mode.upper()
        if self.terminal is None or self.renderer is None:
            return
        if self.is_maximized:
            self.is_maximized = False
        if self.mode == "MINI":
            cols, rows = 74, 14
        elif self.mode == "MICRO":
            cols, rows = 74, 7
        else:
            cols, rows = COLS, ROWS
        self._target_cols = cols
        self._target_rows = rows
        char_w = int(self.terminal.get_char_width() or 0)
        char_h = int(self.terminal.get_char_height() or 0)
        if char_w < 4 or char_h < 8:
            char_w, char_h = 9, 18
        margin = self.renderer.bezel_px
        win_w = cols * char_w + 2 * margin
        win_h = rows * char_h + 2 * margin
        self.renderer.set_window_size(win_w, win_h)
        self.terminal.set_size(cols, rows)
        self._place_terminal()

    def _on_key_press(self, _term, event):
        from gi.repository import Gdk
        keyval = getattr(event, "keyval", 0)
        if keyval in (Gdk.KEY_m, Gdk.KEY_M):
            if self.mode == "NORMAL":
                self.set_mode("MINI")
            elif self.mode == "MINI":
                self.set_mode("MICRO")
            else:
                self.set_mode("NORMAL")
            return False
        return False

    def _terminal_in_well(self):
        """The player must be a solid window over the well, not a faded child of the glass."""
        if not self.child_xid or self.renderer is None:
            return False
        if self.renderer.window_parent(self.child_xid) == self.renderer.x11_window():
            return False
        ox, oy, width, height = self.renderer.window_rect(self.child_xid)
        x, y, inner_w, inner_h = self._well_rect()
        return (
            abs(ox - x) <= 8
            and abs(oy - y) <= 8
            and abs(width - inner_w) <= 8
            and abs(height - inner_h) <= 8
        )

    def _on_spawn(self, _terminal, pid, error, *_rest):
        if error:
            self.spawn_error = str(error)
            if self.renderer is not None:
                self.renderer.request_close()
            return
        self.child_pid = int(pid or 0)

    def _on_child_exit(self, _terminal, _status):
        self.child_done = True
        if self.renderer is not None:
            self.renderer.request_close()

    def _pump_gtk(self, glib):
        context = glib.MainContext.default()
        while context.pending():
            context.iteration(False)

    def _track_drag(self, was_down, dragging, origin, press_screen):
        x, y = self.renderer.cursor
        width, height = self.renderer.window_size()
        down = self.renderer.mouse_down
        if down and not was_down:
            if self._on_close(x, y, width, height):
                self.renderer.request_close()
                dragging = False
            elif self._on_top_bezel(x, y, width, height):
                now = time.monotonic()
                if (now - getattr(self, "_last_top_click", 0.0) < 0.38
                    and abs(x - getattr(self, "_last_top_click_x", 0)) < 25
                    and abs(y - getattr(self, "_last_top_click_y", 0)) < 25):
                    self.toggle_maximize()
                    dragging = False
                    self._last_top_click = 0.0
                else:
                    self._last_top_click = now
                    self._last_top_click_x = x
                    self._last_top_click_y = y
                    if self._on_bezel(x, y, width, height) and not self.is_maximized:
                        dragging = True
                        origin = self.renderer.window_pos()
                        rx, ry = self.renderer.root_pointer()
                        press_screen = (rx, ry) if (rx or ry) else (origin[0] + x, origin[1] + y)
            elif self._on_bezel(x, y, width, height) and not self.is_maximized:
                dragging = True
                origin = self.renderer.window_pos()
                rx, ry = self.renderer.root_pointer()
                press_screen = (rx, ry) if (rx or ry) else (origin[0] + x, origin[1] + y)
        elif down and dragging:
            rx, ry = self.renderer.root_pointer()
            if rx or ry:
                new_x = int(origin[0] + (rx - press_screen[0]))
                new_y = int(origin[1] + (ry - press_screen[1]))
            else:
                new_x = int(origin[0] + (x - (press_screen[0] - origin[0])))
                new_y = int(origin[1] + (y - (press_screen[1] - origin[1])))
            self.renderer.set_window_pos(new_x, new_y)
        else:
            dragging = False
        return down, dragging, origin, press_screen

    def _fit_to_terminal(self, term):
        char_w = int(term.get_char_width() or 0)
        char_h = int(term.get_char_height() or 0)
        if char_w < 4 or char_h < 8:
            char_w, char_h = 9, 18
        margin = self.renderer.bezel_px
        cols = getattr(self, "_target_cols", COLS)
        rows = getattr(self, "_target_rows", ROWS)
        self.renderer.set_window_size(cols * char_w + 2 * margin, rows * char_h + 2 * margin)
        term.set_size(cols, rows)

    def run(self):
        glib, gtk, vte = _import_gtk()
        self.glib = glib
        gtk.init([])
        self.renderer = LiquidGlassRendererOpenGL(1280, 820, "MP Audio Player (Liquid Glass - OpenGL)")
        try:
            return self._run_window(vte, glib)
        finally:
            self.close()

    def _run_window(self, vte, glib):
        self.renderer.open()

        window = self._gtk_terminal_window()
        term = vte.Terminal()
        term.set_audible_bell(False)
        if hasattr(term, "set_scrollback_lines"):
            term.set_scrollback_lines(0)
        window.add(term)
        self._clear_terminal_background(window, term)
        window.show_all()
        term.realize()
        self._pump_gtk(glib)
        self.gtk_window = window
        self.terminal = term
        self._fit_to_terminal(term)
        self.renderer.poll()
        gdk_window = window.get_window()
        self.child_xid = int(gdk_window.get_xid()) if gdk_window is not None else 0
        if self.child_xid <= 0:
            raise RuntimeError("VTE window has no X11 id to place in the glass")
        self._place_terminal()
        self.renderer.focus_window(self.child_xid)
        term.connect("key-press-event", self._on_key_press)
        term.connect("child-exited", self._on_child_exit)
        term.spawn_async(
            vte.PtyFlags.DEFAULT,
            str(ROOT),
            self.argv,
            _child_env(),
            glib.SpawnFlags.DEFAULT,
            None,
            None,
            -1,
            None,
            self._on_spawn,
        )
        term.grab_focus()
        theme = read_player_theme()
        theme_at = 0.0
        was_down = False
        dragging = False
        origin = (0, 0)
        press_screen = (0.0, 0.0)
        started = time.monotonic()
        while not self.renderer.should_close:
            now = time.monotonic()
            if now - theme_at > 0.4:
                theme = read_player_theme()
                theme_at = now
            self._sync_panels()
            self.renderer.draw(theme)
            was_down, dragging, origin, press_screen = self._track_drag(
                was_down, dragging, origin, press_screen
            )
            self._place_terminal()
            self._pump_gtk(glib)
            if self.spawn_error:
                raise RuntimeError(self.spawn_error)
            if self.embed_check and self.child_pid and self._terminal_in_well():
                return True
            if self.embed_check and now - started > 8:
                parent = self.renderer.window_parent(self.child_xid) if self.renderer else 0
                glass = self.renderer.x11_window() if self.renderer else 0
                rect = self.renderer.window_rect(self.child_xid) if self.renderer else ()
                raise RuntimeError(
                    f"VTE window was not placed in the glass well "
                    f"(parent={parent} glass={glass} rect={rect} pid={self.child_pid})"
                )
        return False

    def _gtk_terminal_window(self):
        from gi.repository import Gdk, Gtk

        window = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
        window.set_decorated(False)
        window.set_skip_taskbar_hint(True)
        window.set_skip_pager_hint(True)
        window.set_accept_focus(True)
        window.set_type_hint(Gdk.WindowTypeHint.UTILITY)
        window.set_app_paintable(True)
        visual = window.get_screen().get_rgba_visual()
        if visual is not None:
            window.set_visual(visual)
        return window

    def _clear_terminal_background(self, window, term):
        """Let the still-water glass show through the player cells."""
        from gi.repository import Gdk, Gtk

        rgba = Gdk.RGBA()
        rgba.red = rgba.green = rgba.blue = 0
        rgba.alpha = 0
        if hasattr(term, "set_color_background"):
            term.set_color_background(rgba)
        provider = Gtk.CssProvider()
        provider.load_from_data(b"vte-terminal, window { background-color: transparent; }")
        term.get_style_context().add_provider(provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        window.get_style_context().add_provider(provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def close(self):
        pid = self.child_pid
        self.child_pid = 0
        if pid:
            try:
                os.kill(pid, signal.SIGTERM)
            except OSError:
                pass
        window = self.gtk_window
        self.gtk_window = None
        self.terminal = None
        if window is not None:
            window.destroy()
            self._pump_gtk(self.glib)
        renderer = self.renderer
        self.renderer = None
        if renderer is not None:
            renderer.close()


def main(argv):
    if "--self-test" in argv:
        from liquid_glass_opengl import run_self_test

        run_self_test()
        return 0
    embed = "--embed-check" in argv
    mode = "MINI" if "--mini" in argv else ("MICRO" if "--micro" in argv else "NORMAL")
    command = embed_check_argv() if embed else player_argv(mode=mode)
    if not Path(command[1]).is_file() and not embed:
        raise RuntimeError(f"MP Audio Player was not found at {command[1]}")
    host = GlassHost(command, embed_check=embed, mode=mode)
    ok = host.run()
    if embed:
        if not ok:
            raise RuntimeError("VTE window was not placed in the glass well")
        print("LIQUID_GLASS_EMBED_OK", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except Exception as exc:
        print(f"Liquid Glass (OpenGL): {exc}", file=sys.stderr)
        raise SystemExit(1)
