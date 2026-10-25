#!/usr/bin/env python3
"""OpenGL liquid-glass window hosting the unmodified MP Audio Player."""

from __future__ import annotations
import ctypes, os, shutil, signal, subprocess, sys, time
from pathlib import Path

os.environ.setdefault("PYOPENGL_PLATFORM", "wgl" if sys.platform == "win32" else "glx")

ROOT = Path(__file__).resolve().parent
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from liquid_glass_opengl import LiquidGlassRendererOpenGL, read_player_theme  # noqa: E402

COLS, ROWS = 120, 40
DEFAULT_FONT = "Monospace 11"
CONFIG_DIR = Path.home() / ".config" / "mix-manager"
FONT_CONFIG_FILE = CONFIG_DIR / "liquid_glass_font"

RECOMMENDED_FONTS = [
    ("Monospace 11", "System Default Monospace (Clean, unbolded standard)"),
    ("Fira Code 11", "Modern Programming Font (Clean shapes, sleek proportions)"),
    ("Hack 11", "Crisp Open-Source Terminal Monospace"),
    ("Adwaita Mono 11", "Modern GNOME Desktop Monospace"),
    ("Liberation Mono 11", "Classic Clean Monospace"),
]

Gdk = Gtk = GLib = Vte = None


def get_liquid_glass_font(cli_font=None):
    if cli_font and str(cli_font).strip():
        return str(cli_font).strip()
    env_f = (os.environ.get("MP_LIQUID_GLASS_FONT") or os.environ.get("LIQUID_GLASS_FONT") or "").strip()
    if env_f:
        return env_f
    try:
        if FONT_CONFIG_FILE.is_file():
            return FONT_CONFIG_FILE.read_text(encoding="utf-8").strip() or DEFAULT_FONT
    except Exception:
        pass
    return DEFAULT_FONT


def set_liquid_glass_font(font_str: str) -> None:
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        FONT_CONFIG_FILE.write_text(f"{str(font_str).strip()}\n", encoding="utf-8")
    except Exception as exc:
        print(f"Warning: could not save font to {FONT_CONFIG_FILE}: {exc}", file=sys.stderr)


def list_liquid_glass_fonts():
    cur = get_liquid_glass_font()
    cur_prefix = cur.split()[0] if cur else ""
    print("\n\033[1;38;2;0;229;255m══ MP Liquid Glass Player — Available & Recommended Fonts ══\033[0m\n")
    for idx, (f_name, desc) in enumerate(RECOMMENDED_FONTS, 1):
        star = "\033[1;38;2;0;255;127m★ ACTIVE\033[0m" if (f_name == cur or f_name.split()[0] == cur_prefix) else "        "
        print(f"  {star} \033[1;38;2;255;215;0m[{idx}]\033[0m \033[1;38;2;255;255;255m{f_name:<20s}\033[0m — {desc}")
    print(
        f"\n  \033[38;2;120;215;255mActive Font:\033[0m {cur}\n\n"
        "  \033[38;2;200;200;200mTo try a font on launch:\033[0m\n"
        '    python3 MP_Audio_Player_Liquid_Glass_OpenGL.py --font "Fira Code 11"\n'
        '    python3 MP_Audio_Player_Liquid_Glass_OpenGL.py --font "Hack 11"\n'
        '    python3 MP_Audio_Player_Liquid_Glass_OpenGL.py --font "Monospace 11"\n\n'
        "  \033[38;2;200;200;200mTo set a font as your permanent default:\033[0m\n"
        '    python3 MP_Audio_Player_Liquid_Glass_OpenGL.py --set-font "Fira Code 11"\n'
    )


def player_panel_rects(cols, rows, char_w, char_h, origin_x, origin_y, mode="NORMAL"):
    def box(c, r, bc, br):
        return (origin_x + c * char_w, origin_y + r * char_h, bc * char_w, br * char_h)

    iw = max(20, cols - 4)
    if mode == "MICRO":
        return (box(2, 0, iw, rows), (0.0, 0.0, 0.0, 0.0))
    if mode == "MINI":
        return (box(2, 0, iw, 3), box(2, 3, iw, max(1, rows - 3)))
    if mode == "TRACKLIST":
        return (box(2, 0, iw, rows), (0.0, 0.0, 0.0, 0.0)) if rows <= 7 else (box(2, 0, iw, 7), box(2, 7, iw, max(1, rows - 7)))
    iw = max(20, cols - 6)
    before = 12 + (7 if rows >= 34 else (5 if rows >= 28 else 3))
    return (box(2, 0, iw + 2, 4), box(2, before, iw + 2, max(1, rows - before - 5) + 2))


def _import_gtk():
    global Gdk, Gtk, GLib, Vte
    if sys.platform == "win32":
        return None, None, None
    if Gtk is not None:
        return GLib, Gtk, Vte
    os.environ["GDK_BACKEND"] = "x11"
    import gi
    for mod, ver in (("Gdk", "3.0"), ("Gtk", "3.0"), ("GdkX11", "3.0"), ("Vte", "2.91")):
        gi.require_version(mod, ver)
    from gi.repository import Gdk as _Gdk, GdkX11, GLib as _GLib, Gtk as _Gtk, Vte as _Vte
    if not hasattr(GdkX11, "X11Display"):
        raise RuntimeError("GDK X11 backend is required for the liquid-glass window")
    Gdk, Gtk, GLib, Vte = _Gdk, _Gtk, _GLib, _Vte
    return GLib, Gtk, Vte


def player_argv(mode="NORMAL", extra_args=None):
    cmd = [sys.executable, str(ROOT / "MP_Audio_Player.py"), "--interactive"]
    if mode in ("MINI", "MICRO"):
        cmd.append(f"--{mode.lower()}")
    if extra_args:
        cmd.extend(extra_args)
    return cmd


def embed_check_argv():
    return [sys.executable, "-c", "import time; print('LIQUID_GLASS_CHILD', flush=True); time.sleep(30)"]


def tracklist_argv(tracklist_path, audio_path=None, theme=None):
    v_sh = ROOT / "scripts" / "view_tracklist_console.sh"
    if not v_sh.is_file():
        v_sh = ROOT / "view_tracklist_console.sh"
    cmd = [shutil.which("bash") or "bash", str(v_sh)]
    if theme:
        cmd.extend(["--theme", str(theme)])
    cmd.append(str(tracklist_path))
    if audio_path:
        cmd.append(str(audio_path))
    return cmd


def _child_env(as_dict=False):
    env = {k: v for k, v in os.environ.items() if k != "GDK_BACKEND"}
    env.update({
        "TERM": "xterm-256color",
        "COLORTERM": "truecolor",
        "MP_LIQUID_GLASS": "1",
        "MP_LIQUID_GLASS_BACKEND": "opengl",
        "MP_LIQUID_GLASS_PLATFORM": "win32" if sys.platform == "win32" else "linux",
    })
    return env if as_dict else [f"{k}={v}" for k, v in env.items()]


def _mode_grid(mode):
    if mode == "TRACKLIST":
        return 100, 35
    if mode == "MINI":
        return 74, 14
    if mode == "MICRO":
        return 74, 7
    return COLS, ROWS


class GlassHost:
    def __init__(self, argv, embed_check=False, mode="NORMAL", cli_theme=None, font=None):
        self.argv = list(argv)
        self.embed_check = embed_check
        self.mode = mode.upper()
        self.cli_theme = cli_theme
        self.font_name = get_liquid_glass_font(font)
        self.renderer = self.gtk_window = self.terminal = self.glib = self.spawn_error = self._saved_rect = None
        self.child_xid = self.child_pid = self._last_top_click_x = self._last_top_click_y = 0
        self.child_done = self.is_maximized = self._term_dragging = False
        self._last_top_click = 0.0
        self._target_cols, self._target_rows = _mode_grid(self.mode)
        self._last_well = self._last_panel_state = None

    def _dims(self):
        if self.terminal is not None:
            cw, ch = int(self.terminal.get_char_width() or 0), int(self.terminal.get_char_height() or 0)
            if cw >= 4 and ch >= 8:
                return cw, ch
        return 9, 18

    def _on_bezel(self, x, y, w, h):
        m = max(float(self.renderer.bezel_px), 24.0)
        return x < m or y < m or x >= w - m or y >= h - m

    def _on_top_bezel(self, x, y, w, h):
        return y < max(float(self.renderer.bezel_px), 24.0) + 48 and not self._on_close(x, y, w, h)

    def _on_close(self, x, y, w, _h):
        m = max(float(self.renderer.bezel_px), 8.0)
        return (x - (w - m * 0.72)) ** 2 + (y - m * 0.62) ** 2 <= max(m * 0.30, 4.0) ** 2

    def _well_rect(self):
        gx, gy = self.renderer.window_pos()
        w, h = self.renderer.window_size()
        m = self.renderer.bezel_px
        return gx + m, gy + m, max(32, w - 2 * m), max(32, h - 2 * m)

    def _place_terminal(self, force=False):
        rect = self._well_rect()
        if not force and rect == self._last_well:
            self._sync_panels()
            return
        self._last_well = rect
        x, y, iw, ih = rect
        if self.gtk_window is not None:
            self.gtk_window.move(int(x), int(y))
            if getattr(self, "_last_term_size", None) != (int(iw), int(ih)):
                self.gtk_window.resize(int(iw), int(ih))
                self._last_term_size = (int(iw), int(ih))
        self.renderer.place_terminal(self.child_xid, x, y, iw, ih)
        self._sync_panels()

    def _sync_panels(self):
        if self.renderer is None:
            return
        cw, ch = self._dims()
        m = self.renderer.bezel_px
        cols, rows = self._target_cols, self._target_rows
        if self.terminal is not None:
            tc, tr = int(self.terminal.get_column_count() or 0), int(self.terminal.get_row_count() or 0)
            if tc >= 20:
                cols = tc
            if tr >= 5:
                rows = tr
        state = (cols, rows, cw, ch, m, self.mode)
        if state != self._last_panel_state:
            self._last_panel_state = state
            self.renderer.set_panels(player_panel_rects(cols, rows, cw, ch, m, m, mode=self.mode))

    def _apply_grid(self, cols, rows, pos=None, size=None):
        cw, ch = self._dims()
        m = self.renderer.bezel_px
        self._target_cols, self._target_rows = cols, rows
        if pos:
            self.renderer.set_window_pos(pos[0], pos[1])
        self.renderer.set_window_size(*(size or (cols * cw + 2 * m, rows * ch + 2 * m)))
        self.renderer.poll()
        if self.terminal is not None:
            self.terminal.set_size(cols, rows)
        self._place_terminal(force=True)

    def toggle_maximize(self):
        if self.renderer is None:
            return
        cw, ch = self._dims()
        m = self.renderer.bezel_px
        if not self.is_maximized:
            self._saved_rect = (self.renderer.window_pos(), self.renderer.window_size())
            wx, wy, ww, wh = self.renderer.get_workarea()
            self._apply_grid(max(40, int((ww - 2 * m) // cw)), max(10, int((wh - 2 * m) // ch)), (wx, wy), (ww, wh))
            self.is_maximized = True
        else:
            pos, _ = self._saved_rect or ((72, 64), (1280, 820))
            cols, rows = _mode_grid(self.mode if self.mode != "TRACKLIST" else "NORMAL")
            self._apply_grid(cols, rows, pos)
            self.is_maximized = False

    def set_mode(self, mode: str):
        self.mode = mode.upper()
        if self.renderer is None:
            return
        self.is_maximized = False
        cols, rows = _mode_grid(self.mode if self.mode != "TRACKLIST" else "NORMAL")
        self._apply_grid(cols, rows)

    def _on_key_press(self, _term, event):
        kv = getattr(event, "keyval", 0)
        if kv in (Gdk.KEY_m, Gdk.KEY_M):
            self.set_mode("MINI" if self.mode == "NORMAL" else ("MICRO" if self.mode == "MINI" else "NORMAL"))
            return False
        if kv == Gdk.KEY_K or (kv == Gdk.KEY_k and bool(getattr(event, "state", 0) & Gdk.ModifierType.SHIFT_MASK)):
            subprocess.run('pkill -9 -f "MP_Audio_Player"', shell=True)
            return True
        return False

    def _terminal_in_well(self):
        if not self.child_xid or self.renderer is None or self.renderer.window_parent(self.child_xid) == self.renderer.x11_window():
            return False
        ox, oy, w, h = self.renderer.window_rect(self.child_xid)
        x, y, iw, ih = self._well_rect()
        return abs(ox - x) <= 8 and abs(oy - y) <= 8 and abs(w - iw) <= 8 and abs(h - ih) <= 8

    def _on_spawn(self, _terminal, pid, error, *_rest):
        if error:
            self.spawn_error = str(error)
            if self.renderer is not None:
                self.renderer.request_close()
        else:
            self.child_pid = int(pid or 0)

    def _on_child_exit(self, _terminal, _status):
        self.child_done = True
        if self.renderer is not None:
            self.renderer.request_close()

    def _pump_gtk(self, glib):
        ctx = glib.MainContext.default()
        while ctx.pending():
            ctx.iteration(False)

    def _on_term_button_press(self, _term, event):
        if event.button == 1:
            if event.type == getattr(Gdk.EventType, "_2BUTTON_PRESS", 5) and event.y <= 90:
                self.toggle_maximize()
                self._term_dragging = False
                return True
            mods = getattr(Gdk.ModifierType, "MOD1_MASK", 8) | getattr(Gdk.ModifierType, "SUPER_MASK", 0x4000000)
            if (event.y <= 90 or bool(getattr(event, "state", 0) & mods)) and not self.is_maximized:
                self._term_dragging = True
                self._term_drag_origin = self.renderer.window_pos()
                rx, ry = self.renderer.root_pointer()
                self._term_drag_press = (rx, ry) if (rx or ry) else (int(event.x_root), int(event.y_root))
                return True
        return False

    def _on_term_motion_notify(self, _term, event):
        if self._term_dragging and not self.is_maximized:
            rx, ry = self.renderer.root_pointer()
            cx, cy = (rx, ry) if (rx or ry) else (int(event.x_root), int(event.y_root))
            self.renderer.set_window_pos(
                int(self._term_drag_origin[0] + cx - self._term_drag_press[0]),
                int(self._term_drag_origin[1] + cy - self._term_drag_press[1]),
            )
            self._place_terminal(force=True)
            return True
        return False

    def _on_term_button_release(self, _term, event):
        if event.button == 1:
            self._term_dragging = False
        return False

    def _track_drag(self, was_down, dragging, origin, press_screen):
        x, y = self.renderer.cursor
        w, h = self.renderer.window_size()
        down = self.renderer.mouse_down
        if down and not was_down:
            if self._on_close(x, y, w, h):
                self.renderer.request_close()
                dragging = False
            elif self._on_top_bezel(x, y, w, h):
                now = time.monotonic()
                if now - self._last_top_click < 0.45 and abs(x - self._last_top_click_x) < 35 and abs(y - self._last_top_click_y) < 35:
                    self.toggle_maximize()
                    dragging, self._last_top_click = False, 0.0
                else:
                    self._last_top_click, self._last_top_click_x, self._last_top_click_y = now, x, y
                    if not self.is_maximized:
                        dragging, origin = True, self.renderer.window_pos()
                        rx, ry = self.renderer.root_pointer()
                        press_screen = (rx, ry) if (rx or ry) else (origin[0] + x, origin[1] + y)
            elif self._on_bezel(x, y, w, h) and not self.is_maximized:
                dragging, origin = True, self.renderer.window_pos()
                rx, ry = self.renderer.root_pointer()
                press_screen = (rx, ry) if (rx or ry) else (origin[0] + x, origin[1] + y)
        elif down and dragging:
            rx, ry = self.renderer.root_pointer()
            nx = origin[0] + (rx - press_screen[0] if (rx or ry) else x - (press_screen[0] - origin[0]))
            ny = origin[1] + (ry - press_screen[1] if (rx or ry) else y - (press_screen[1] - origin[1]))
            self.renderer.set_window_pos(int(nx), int(ny))
        else:
            dragging = False
        return down, dragging, origin, press_screen

    def _fit_to_terminal(self, term):
        cw, ch = self._dims()
        m = self.renderer.bezel_px
        self.renderer.set_window_size(self._target_cols * cw + 2 * m, self._target_rows * ch + 2 * m)
        term.set_size(self._target_cols, self._target_rows)

    def run(self):
        m = LiquidGlassRendererOpenGL.bezel_px
        iw, ih = self._target_cols * 9 + 2 * m, self._target_rows * 18 + 2 * m
        title = "Mix Tracklist Viewer (Liquid Glass - OpenGL)" if self.mode == "TRACKLIST" else "MP Audio Player (Liquid Glass - OpenGL)"
        if sys.platform == "win32":
            self.renderer = LiquidGlassRendererOpenGL(iw, ih, title)
            try:
                return self._run_windows()
            finally:
                self.close()
        glib, gtk, vte = _import_gtk()
        self.glib = glib
        gtk.init([])
        self.renderer = LiquidGlassRendererOpenGL(iw, ih, title)
        try:
            return self._run_window(vte, glib)
        finally:
            self.close()

    def _run_windows(self):
        self.renderer.open()
        m = self.renderer.bezel_px
        self.renderer.set_window_size(self._target_cols * 9 + 2 * m, self._target_rows * 18 + 2 * m)
        self._sync_panels()
        if self.embed_check:
            self.renderer.draw(read_player_theme())
            return True

        proc = subprocess.Popen(self.argv, cwd=str(ROOT), env=_child_env(as_dict=True), creationflags=0x00000010)
        self.child_pid = proc.pid
        child_hwnd = None
        try:
            user32 = ctypes.windll.user32
            ENUM_PROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
            found = []

            def _enum_win(hwnd, _lparam):
                pid = ctypes.c_uint32()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                if pid.value == proc.pid and user32.IsWindowVisible(hwnd):
                    found.append(hwnd)
                return True

            cb = ENUM_PROC(_enum_win)
            for _ in range(50):
                if proc.poll() is not None:
                    break
                user32.EnumWindows(cb, 0)
                if found:
                    child_hwnd = found[0]
                    break
                time.sleep(0.02)
        except Exception:
            pass

        self.child_xid = child_hwnd or 0
        if child_hwnd:
            try:
                style = (user32.GetWindowLongPtrW(child_hwnd, -16) & ~(0x00C00000 | 0x00040000)) | 0x80000000
                user32.SetWindowLongPtrW(child_hwnd, -16, style)
                glass_hwnd = self.renderer.win32_window()
                if glass_hwnd:
                    user32.SetParent(child_hwnd, glass_hwnd)
            except Exception:
                pass
            self._place_terminal(force=True)

        down = dragging = False
        origin, press_screen, theme, theme_at = self.renderer.window_pos(), (0, 0), read_player_theme(), 0.0
        try:
            while not self.renderer.should_close and proc.poll() is None:
                now = time.monotonic()
                if now - theme_at > 0.4:
                    theme, theme_at = read_player_theme(), now
                self._sync_panels()
                self.renderer.draw(theme)
                down, dragging, origin, press_screen = self._track_drag(down, dragging, origin, press_screen)
                if dragging:
                    self._place_terminal(force=True)
                if not self.renderer.poll():
                    break
                time.sleep(0.008)
        finally:
            try:
                if proc.poll() is None:
                    proc.terminate()
            except Exception:
                pass
            self.close()
        return True

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
        self.gtk_window, self.terminal = window, term
        self._fit_to_terminal(term)
        self.renderer.poll()
        gdk_win = window.get_window()
        self.child_xid = int(gdk_win.get_xid()) if gdk_win is not None else 0
        if self.child_xid <= 0:
            raise RuntimeError("VTE window has no X11 id to place in the glass")
        self._place_terminal(force=True)
        self.renderer.focus_window(self.child_xid)
        term.add_events(
            Gdk.EventMask.BUTTON_PRESS_MASK
            | Gdk.EventMask.BUTTON_RELEASE_MASK
            | Gdk.EventMask.BUTTON1_MOTION_MASK
            | Gdk.EventMask.POINTER_MOTION_MASK
        )
        term.connect("button-press-event", self._on_term_button_press)
        term.connect("button-release-event", self._on_term_button_release)
        term.connect("motion-notify-event", self._on_term_motion_notify)
        term.connect("key-press-event", self._on_key_press)
        term.connect("child-exited", self._on_child_exit)
        term.spawn_async(
            vte.PtyFlags.DEFAULT, str(ROOT), self.argv, _child_env(),
            glib.SpawnFlags.DEFAULT, None, None, -1, None, self._on_spawn,
        )
        term.grab_focus()
        theme, theme_at, was_down, dragging = read_player_theme(), 0.0, False, False
        origin, press_screen, started = (0, 0), (0.0, 0.0), time.monotonic()
        while not self.renderer.should_close:
            now = time.monotonic()
            if now - theme_at > 0.4:
                theme, theme_at = read_player_theme(), now
            self._sync_panels()
            self.renderer.draw(theme)
            was_down, dragging, origin, press_screen = self._track_drag(was_down, dragging, origin, press_screen)
            self._place_terminal()
            self._pump_gtk(glib)
            if self.spawn_error:
                raise RuntimeError(self.spawn_error)
            if self.embed_check:
                if self.child_pid and self._terminal_in_well():
                    return True
                if now - started > 8:
                    raise RuntimeError(
                        f"VTE window was not placed in the glass well "
                        f"(parent={self.renderer.window_parent(self.child_xid)} "
                        f"glass={self.renderer.x11_window()} rect={self.renderer.window_rect(self.child_xid)} pid={self.child_pid})"
                    )
        return False

    def _gtk_terminal_window(self):
        icon_path = ROOT / "assets" / "mp_liquid_glass_icon.png"
        window = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
        if icon_path.is_file():
            try:
                Gtk.Window.set_default_icon_from_file(str(icon_path))
                window.set_icon_from_file(str(icon_path))
            except Exception:
                pass
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
        if hasattr(term, "set_color_background"):
            term.set_color_background(Gdk.RGBA(0, 0, 0, 0))
        if hasattr(term, "set_color_foreground"):
            term.set_color_foreground(Gdk.RGBA(1.0, 1.0, 1.0, 1.0))
        if hasattr(term, "set_bold_is_bright"):
            term.set_bold_is_bright(False)
        if hasattr(term, "set_allow_bold"):
            term.set_allow_bold(False)
        try:
            import gi
            gi.require_version("Pango", "1.0")
            from gi.repository import Pango
            font_desc = Pango.FontDescription.from_string(self.font_name)
            font_desc.set_weight(Pango.Weight.NORMAL)
            term.set_font(font_desc)
        except Exception:
            pass
        try:
            import cairo, gi
            gi.require_version("PangoCairo", "1.0")
            from gi.repository import PangoCairo
            fo = cairo.FontOptions()
            fo.set_antialias(cairo.ANTIALIAS_GRAY)
            fo.set_hint_style(cairo.HINT_STYLE_SLIGHT)
            fo.set_hint_metrics(cairo.HINT_METRICS_ON)
            if window.get_screen() is not None:
                window.get_screen().set_font_options(fo)
            if term.get_pango_context() is not None:
                PangoCairo.context_set_font_options(term.get_pango_context(), fo)
        except Exception:
            pass
        provider = Gtk.CssProvider()
        provider.load_from_data(
            b"vte-terminal, window { background-color: transparent; padding: 0px; margin: 0px; font-weight: normal; "
            b"text-shadow: 0 0 3px rgba(0, 229, 255, 0.40), 0 0 7px rgba(176, 88, 255, 0.20); letter-spacing: 0.35px; }"
        )
        term.get_style_context().add_provider(provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        window.get_style_context().add_provider(provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def close(self):
        pid, self.child_pid = self.child_pid, 0
        if pid:
            try:
                os.kill(pid, signal.SIGTERM)
            except OSError:
                pass
        window, self.gtk_window, self.terminal = self.gtk_window, None, None
        if window is not None:
            window.destroy()
            if self.glib:
                self._pump_gtk(self.glib)
        renderer, self.renderer = self.renderer, None
        if renderer is not None:
            renderer.close()


def ensure_random_visualizer_started() -> bool:
    try:
        if sys.platform == "win32":
            try:
                out = subprocess.check_output(
                    ["powershell.exe", "-NoProfile", "-Command",
                     'Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*MP_Liquid_Visualizer*" -or $_.CommandLine -like "*mp_liquid_visualizer_vulkan*" } | Select-Object -ExpandProperty ProcessId'],
                    stderr=subprocess.DEVNULL, text=True,
                ).strip()
                if out:
                    return False
            except Exception:
                pass
        elif shutil.which("pgrep"):
            if subprocess.run(["pgrep", "-f", "MP_Liquid_Visualizer|mp_liquid_visualizer_vulkan"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
                return False

        vis_script = next((p for p in (ROOT / "MP_Liquid_Visualizer.py", ROOT / "scripts" / "mp_liquid_visualizer_vulkan.py") if p.is_file()), None)
        if not vis_script:
            return False

        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        extra_kw = {"creationflags": 0x00000208} if sys.platform == "win32" else {"start_new_session": True}
        with open(CONFIG_DIR / "liquid_visualizer.log", "a") as f:
            subprocess.Popen([sys.executable, str(vis_script), "--preset", "random"], cwd=str(ROOT), stdin=subprocess.DEVNULL, stdout=f, stderr=f, **extra_kw)
        return True
    except Exception:
        return False


def main(argv):
    if "--self-test" in argv:
        from liquid_glass_opengl import run_self_test
        run_self_test()
        return 0
    if "--list-fonts" in argv:
        list_liquid_glass_fonts()
        return 0

    embed = "--embed-check" in argv
    tracklist_path = audio_path = theme_arg = font_arg = None
    cleaned_argv = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--no-visualizer":
            i += 1
        elif arg in ("--tracklist", "--audio", "--theme", "-t", "--font", "-f", "--set-font") and i + 1 < len(argv):
            val = argv[i + 1]
            if arg == "--set-font":
                set_liquid_glass_font(val)
                print(f"✔ MP Liquid Glass Player default font set to: {val}")
                return 0
            if arg == "--tracklist":
                tracklist_path = val
            elif arg == "--audio":
                audio_path = val
            elif arg in ("--theme", "-t"):
                theme_arg = val
            else:
                font_arg = val
            i += 2
        elif arg.startswith(("--tracklist=", "--audio=", "--theme=", "--font=", "--set-font=")):
            k, val = arg.split("=", 1)
            if k == "--set-font":
                set_liquid_glass_font(val)
                print(f"✔ MP Liquid Glass Player default font set to: {val}")
                return 0
            if k == "--tracklist":
                tracklist_path = val
            elif k == "--audio":
                audio_path = val
            elif k == "--theme":
                theme_arg = val
            else:
                font_arg = val
            i += 1
        else:
            cleaned_argv.append(arg)
            i += 1

    if not embed and not tracklist_path and "--no-visualizer" not in argv:
        ensure_random_visualizer_started()

    mode = "MINI" if "--mini" in argv else ("MICRO" if "--micro" in argv else "NORMAL")
    if tracklist_path and not embed:
        mode = "TRACKLIST"
        command = tracklist_argv(tracklist_path, audio_path=audio_path, theme=theme_arg)
        if not Path(command[1]).is_file():
            raise RuntimeError(f"Tracklist viewer script was not found at {command[1]}")
    elif embed:
        command = embed_check_argv()
    else:
        extra = [a for a in cleaned_argv if a not in ("--self-test", "--embed-check", "--mini", "--micro")]
        if theme_arg and not any(a == "--theme" or a.startswith("--theme=") for a in extra):
            extra.extend(["--theme", theme_arg])
        command = player_argv(mode=mode, extra_args=extra)
        if not Path(command[1]).is_file():
            raise RuntimeError(f"MP Audio Player was not found at {command[1]}")

    ok = GlassHost(command, embed_check=embed, mode=mode, cli_theme=theme_arg, font=font_arg).run()
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