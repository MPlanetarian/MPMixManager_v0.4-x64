#!/usr/bin/env python3
"""NVIDIA Vulkan liquid-glass window hosting the unmodified MP Audio Player."""
from __future__ import annotations
import ctypes, os, shutil, signal, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from liquid_glass_vulkan import LiquidGlassRenderer, NVIDIA_VENDOR_ID, read_player_theme  # noqa: E402

COLS, ROWS = 120, 40
DEFAULT_FONT = "Monospace 11"
CONFIG_DIR = Path.home() / ".config" / "mix-manager"
FONT_CONFIG_FILE = CONFIG_DIR / "liquid_glass_font"
IS_WIN = sys.platform == "win32"

RECOMMENDED_FONTS = [
    ("Monospace 11", "System Default Monospace (Clean, unbolded standard)"),
    ("Fira Code 11", "Modern Programming Font (Clean shapes, sleek proportions)"),
    ("Hack 11", "Crisp Open-Source Terminal Monospace"),
    ("Adwaita Mono 11", "Modern GNOME Desktop Monospace"),
    ("Liberation Mono 11", "Classic Clean Monospace"),
]


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
    c_head = cur.split()[0]
    print("\n\033[1;38;2;0;229;255m══ MP Liquid Glass Player — Available & Recommended Fonts ══\033[0m\n")
    for idx, (f_name, desc) in enumerate(RECOMMENDED_FONTS, 1):
        star = "\033[1;38;2;0;255;127m★ ACTIVE\033[0m" if (f_name == cur or f_name.split()[0] == c_head) else "        "
        print(f"  {star} \033[1;38;2;255;215;0m[{idx}]\033[0m \033[1;38;2;255;255;255m{f_name:<20s}\033[0m — {desc}")
    print(f"\n  \033[38;2;120;215;255mActive Font:\033[0m {cur}\n\n  \033[38;2;200;200;200mTo try a font on launch:\033[0m\n"
          '    python3 MP_Audio_Player_Liquid_Glass.py --font "Fira Code 11"\n'
          '    python3 MP_Audio_Player_Liquid_Glass.py --font "Hack 11"\n'
          '    python3 MP_Audio_Player_Liquid_Glass.py --font "Monospace 11"\n\n'
          "  \033[38;2;200;200;200mTo set a font as your permanent default:\033[0m\n"
          '    python3 MP_Audio_Player_Liquid_Glass.py --set-font "Fira Code 11"\n')


def player_panel_rects(cols, rows, cw, ch, ox, oy, mode="NORMAL"):
    b = lambda c, r, bc, br: (ox + c * cw, oy + r * ch, bc * cw, br * ch)
    iw = max(20, cols - 4)
    if mode == "MICRO":
        return b(2, 0, iw, rows), (0.0, 0.0, 0.0, 0.0)
    if mode == "MINI":
        return b(2, 0, iw, 3), b(2, 3, iw, max(1, rows - 3))
    if mode == "TRACKLIST":
        return (b(2, 0, iw, rows), (0.0, 0.0, 0.0, 0.0)) if rows <= 7 else (b(2, 0, iw, 7), b(2, 7, iw, max(1, rows - 7)))
    iw = max(20, cols - 6)
    before = 13 + (7 if rows >= 34 else (5 if rows >= 28 else 3))
    return b(2, 0, iw + 2, 4), b(2, before, iw + 2, max(1, rows - before - 5) + 2)


def _import_gtk():
    if IS_WIN:
        return None, None, None
    os.environ["GDK_BACKEND"] = "x11"
    import gi
    for mod, ver in (("Gdk", "3.0"), ("Gtk", "3.0"), ("GdkX11", "3.0"), ("Vte", "2.91")):
        gi.require_version(mod, ver)
    from gi.repository import GdkX11, GLib, Gtk, Vte
    if not hasattr(GdkX11, "X11Display"):
        raise RuntimeError("GDK X11 backend is required for the liquid-glass window")
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
    env.update(TERM="xterm-256color", COLORTERM="truecolor", MP_LIQUID_GLASS="1",
               MP_LIQUID_GLASS_BACKEND="vulkan", MP_LIQUID_GLASS_PLATFORM="win32" if IS_WIN else "linux")
    return env if as_dict else [f"{k}={v}" for k, v in env.items()]


class GlassHost:
    def __init__(self, argv, embed_check=False, mode="NORMAL", cli_theme=None, font=None):
        self.argv = list(argv)
        self.embed_check = embed_check
        self.mode = mode.upper()
        self.cli_theme = cli_theme
        self.font_name = get_liquid_glass_font(font)
        self.renderer = self.gtk_window = self.terminal = self.glib = self.spawn_error = self._saved_rect = self._last_term_size = None
        self.child_xid = self.child_pid = self._last_top_click_x = self._last_top_click_y = 0
        self.child_done = self.is_maximized = self._term_dragging = False
        self._last_top_click = 0.0
        self._target_cols = 100 if self.mode == "TRACKLIST" else (74 if self.mode in ("MINI", "MICRO") else COLS)
        self._target_rows = 35 if self.mode == "TRACKLIST" else (14 if self.mode == "MINI" else (7 if self.mode == "MICRO" else ROWS))

    def _char_dims(self):
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

    def _on_close(self, x, y, w, h):
        m = max(float(self.renderer.bezel_px), 8.0)
        r = max(m * 0.30, 4.0)
        return (x - (w - m * 0.72)) ** 2 + (y - m * 0.62) ** 2 <= r * r

    def _well_rect(self):
        gx, gy = self.renderer.window_pos()
        w, h = self.renderer.window_size()
        m = self.renderer.bezel_px
        return gx + m, gy + m, max(32, w - 2 * m), max(32, h - 2 * m)

    def _place_terminal(self):
        x, y, iw, ih = self._well_rect()
        if self.gtk_window is not None:
            ix, iy, iiw, iih = int(x), int(y), int(iw), int(ih)
            self.gtk_window.move(ix, iy)
            if self._last_term_size != (iiw, iih):
                self.gtk_window.resize(iiw, iih)
                self._last_term_size = (iiw, iih)
        self.renderer.place_terminal(self.child_xid, x, y, iw, ih)
        self._sync_panels()

    def _sync_panels(self):
        r = self.renderer
        if r is None:
            return
        cw, ch = self._char_dims()
        m = r.bezel_px
        cols, rows = self._target_cols, self._target_rows
        t = self.terminal
        if t is not None:
            tc, tr = int(t.get_column_count() or 0), int(t.get_row_count() or 0)
            if tc >= 20:
                cols = tc
            if tr >= 5:
                rows = tr
        r.set_panels(player_panel_rects(cols, rows, cw, ch, m, m, mode=self.mode))

    def toggle_maximize(self):
        if self.renderer is None:
            return
        cw, ch = self._char_dims()
        m = self.renderer.bezel_px
        if not self.is_maximized:
            self._saved_rect = (self.renderer.window_pos(), self.renderer.window_size())
            wx, wy, ww, wh = self.renderer.get_workarea()
            cols, rows = max(40, int((ww - 2 * m) // cw)), max(10, int((wh - 2 * m) // ch))
            self._target_cols, self._target_rows = cols, rows
            self.renderer.set_window_pos(wx, wy)
            self.renderer.set_window_size(ww, wh)
            self.renderer.poll()
            if self.terminal is not None:
                self.terminal.set_size(cols, rows)
            self._place_terminal()
            self.is_maximized = True
        else:
            pos, _ = self._saved_rect or ((72, 64), (1280, 820))
            cols, rows = (74, 14) if self.mode == "MINI" else ((74, 7) if self.mode == "MICRO" else (COLS, ROWS))
            self._target_cols, self._target_rows = cols, rows
            self.renderer.set_window_pos(pos[0], pos[1])
            self.renderer.set_window_size(cols * cw + 2 * m, rows * ch + 2 * m)
            self.renderer.poll()
            if self.terminal is not None:
                self.terminal.set_size(cols, rows)
            self._place_terminal()
            self.is_maximized = False

    def set_mode(self, mode: str):
        self.mode = mode.upper()
        if self.renderer is None:
            return
        self.is_maximized = False
        cols, rows = (74, 14) if self.mode == "MINI" else ((74, 7) if self.mode == "MICRO" else (COLS, ROWS))
        self._target_cols, self._target_rows = cols, rows
        cw, ch = self._char_dims()
        m = self.renderer.bezel_px
        self.renderer.set_window_size(cols * cw + 2 * m, rows * ch + 2 * m)
        if self.terminal is not None:
            self.terminal.set_size(cols, rows)
        self._place_terminal()

    def _on_key_press(self, _term, event):
        from gi.repository import Gdk
        kv, st = getattr(event, "keyval", 0), getattr(event, "state", 0)
        if kv in (Gdk.KEY_m, Gdk.KEY_M):
            self.set_mode("MINI" if self.mode == "NORMAL" else ("MICRO" if self.mode == "MINI" else "NORMAL"))
            return False
        if kv == Gdk.KEY_K or (kv in (Gdk.KEY_k, Gdk.KEY_K) and bool(st & Gdk.ModifierType.SHIFT_MASK)):
            subprocess.run('pkill -9 -f "MP_Audio_Player"', shell=True)
            return True
        return False

    def _terminal_in_well(self):
        if not self.child_xid or not self.renderer or self.renderer.window_parent(self.child_xid) == self.renderer.x11_window():
            return False
        return all(abs(a - b) <= 8 for a, b in zip(self.renderer.window_rect(self.child_xid), self._well_rect()))

    def _on_spawn(self, _t, pid, error, *_):
        if error:
            self.spawn_error = str(error)
            if self.renderer is not None:
                self.renderer.request_close()
        else:
            self.child_pid = int(pid or 0)

    def _on_child_exit(self, *_):
        self.child_done = True
        if self.renderer is not None:
            self.renderer.request_close()

    def _pump_gtk(self, glib):
        ctx = glib.MainContext.default()
        pending, step = ctx.pending, ctx.iteration
        while pending():
            step(False)

    def _on_term_button_press(self, _term, event):
        from gi.repository import Gdk
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
            ox, oy = self._term_drag_origin
            px, py = self._term_drag_press
            self.renderer.set_window_pos(int(ox + cx - px), int(oy + cy - py))
            self._place_terminal()
            return True
        return False

    def _on_term_button_release(self, _term, event):
        if event.button == 1:
            self._term_dragging = False
        return False

    def _track_drag(self, was_down, dragging, origin, press_screen):
        r = self.renderer
        x, y = r.cursor
        w, h = r.window_size()
        down = r.mouse_down
        if down and not was_down:
            if self._on_close(x, y, w, h):
                r.request_close()
                dragging = False
            elif self._on_top_bezel(x, y, w, h):
                now = time.monotonic()
                if now - self._last_top_click < 0.45 and abs(x - self._last_top_click_x) < 35 and abs(y - self._last_top_click_y) < 35:
                    self.toggle_maximize()
                    dragging, self._last_top_click = False, 0.0
                else:
                    self._last_top_click, self._last_top_click_x, self._last_top_click_y = now, x, y
                    if not self.is_maximized:
                        dragging, origin = True, r.window_pos()
                        rx, ry = r.root_pointer()
                        press_screen = (rx, ry) if (rx or ry) else (origin[0] + x, origin[1] + y)
            elif self._on_bezel(x, y, w, h) and not self.is_maximized:
                dragging, origin = True, r.window_pos()
                rx, ry = r.root_pointer()
                press_screen = (rx, ry) if (rx or ry) else (origin[0] + x, origin[1] + y)
        elif down and dragging:
            rx, ry = r.root_pointer()
            if rx or ry:
                r.set_window_pos(int(origin[0] + rx - press_screen[0]), int(origin[1] + ry - press_screen[1]))
            else:
                r.set_window_pos(int(origin[0] + x - (press_screen[0] - origin[0])), int(origin[1] + y - (press_screen[1] - origin[1])))
        else:
            dragging = False
        return down, dragging, origin, press_screen

    def _fit_to_terminal(self, term):
        cw, ch = self._char_dims()
        m = self.renderer.bezel_px
        self.renderer.set_window_size(self._target_cols * cw + 2 * m, self._target_rows * ch + 2 * m)
        term.set_size(self._target_cols, self._target_rows)

    def run(self):
        m = LiquidGlassRenderer.bezel_px
        iw, ih = self._target_cols * 9 + 2 * m, self._target_rows * 18 + 2 * m
        base_t = "Mix Tracklist Viewer" if self.mode == "TRACKLIST" else "MP Audio Player"
        title = f"{base_t} (Liquid Glass{' - Vulkan' if IS_WIN else ''})"
        if IS_WIN:
            self.renderer = LiquidGlassRenderer(iw, ih, title)
            try:
                return self._run_windows()
            finally:
                self.close()
        glib, gtk, vte = _import_gtk()
        self.glib = glib
        gtk.init([])
        self.renderer = LiquidGlassRenderer(iw, ih, title)
        try:
            return self._run_window(vte, glib)
        finally:
            self.close()

    def _run_windows(self):
        r = self.renderer
        r.open()
        m = r.bezel_px
        r.set_window_size(self._target_cols * 9 + 2 * m, self._target_rows * 18 + 2 * m)
        self._sync_panels()
        if self.embed_check:
            r.draw(read_player_theme())
            return True

        proc = subprocess.Popen(self.argv, cwd=str(ROOT), env=_child_env(True), creationflags=0x00000010)
        self.child_pid = proc.pid
        child_hwnd = None
        try:
            u32 = ctypes.windll.user32
            found = []
            @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
            def _enum_win(hwnd, _):
                pid = ctypes.c_uint32()
                u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                if pid.value == proc.pid and u32.IsWindowVisible(hwnd):
                    found.append(hwnd)
                return True
            for _ in range(50):
                if proc.poll() is not None:
                    break
                u32.EnumWindows(_enum_win, 0)
                if found:
                    child_hwnd = found[0]
                    break
                time.sleep(0.02)
            if child_hwnd:
                u32.SetWindowLongPtrW(child_hwnd, -16, (u32.GetWindowLongPtrW(child_hwnd, -16) & ~0x00C40000) | 0x80000000)
                glass_hwnd = r.win32_window()
                if glass_hwnd:
                    u32.SetParent(child_hwnd, glass_hwnd)
        except Exception:
            pass

        self.child_xid = child_hwnd or 0
        if child_hwnd:
            self._place_terminal()

        down = dragging = False
        origin, press_screen, theme, theme_at = r.window_pos(), (0, 0), read_player_theme(), 0.0
        monotonic, sleep, draw, poll = time.monotonic, time.sleep, r.draw, r.poll
        try:
            while not r.should_close and proc.poll() is None:
                now = monotonic()
                if now - theme_at > 0.4:
                    theme, theme_at = read_player_theme(), now
                self._sync_panels()
                draw(theme)
                down, dragging, origin, press_screen = self._track_drag(down, dragging, origin, press_screen)
                if dragging:
                    self._place_terminal()
                if not poll():
                    break
                sleep(0.008)
        finally:
            try:
                if proc.poll() is None:
                    proc.terminate()
            except Exception:
                pass
            self.close()
        return True

    def _run_window(self, vte, glib):
        r = self.renderer
        r.open()
        if not IS_WIN and r.vendor_id != NVIDIA_VENDOR_ID:
            raise RuntimeError(r.summary)

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
        r.poll()
        gdk_win = window.get_window()
        self.child_xid = int(gdk_win.get_xid()) if gdk_win is not None else 0
        if self.child_xid <= 0:
            raise RuntimeError("VTE window has no X11 id to place in the glass")
        self._place_terminal()
        r.focus_window(self.child_xid)

        from gi.repository import Gdk
        term.add_events(Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.BUTTON_RELEASE_MASK |
                        Gdk.EventMask.BUTTON1_MOTION_MASK | Gdk.EventMask.POINTER_MOTION_MASK)
        for sig, cb in (("button-press-event", self._on_term_button_press),
                        ("button-release-event", self._on_term_button_release),
                        ("motion-notify-event", self._on_term_motion_notify),
                        ("key-press-event", self._on_key_press),
                        ("child-exited", self._on_child_exit)):
            term.connect(sig, cb)

        term.spawn_async(vte.PtyFlags.DEFAULT, str(ROOT), self.argv, _child_env(),
                         glib.SpawnFlags.DEFAULT, None, None, -1, None, self._on_spawn)
        term.grab_focus()
        theme, theme_at, was_down, dragging = read_player_theme(), 0.0, False, False
        origin, press_screen, started = (0, 0), (0.0, 0.0), time.monotonic()
        monotonic, draw = time.monotonic, r.draw

        while not r.should_close:
            now = monotonic()
            if now - theme_at > 0.4:
                theme, theme_at = read_player_theme(), now
            self._sync_panels()
            draw(theme)
            was_down, dragging, origin, press_screen = self._track_drag(was_down, dragging, origin, press_screen)
            self._place_terminal()
            self._pump_gtk(glib)
            if self.spawn_error:
                raise RuntimeError(self.spawn_error)
            if self.embed_check:
                if self.child_pid and self._terminal_in_well():
                    return True
                if now - started > 8:
                    raise RuntimeError(f"VTE window was not placed in the glass well (parent={r.window_parent(self.child_xid)} glass={r.x11_window()} rect={r.window_rect(self.child_xid)} pid={self.child_pid})")
        return False

    def _gtk_terminal_window(self):
        from gi.repository import Gdk, Gtk
        icon = ROOT / "assets" / "mp_liquid_glass_icon.png"
        window = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
        if icon.is_file():
            try:
                Gtk.Window.set_default_icon_from_file(str(icon))
                window.set_icon_from_file(str(icon))
            except Exception:
                pass
        window.set_decorated(False)
        window.set_skip_taskbar_hint(True)
        window.set_skip_pager_hint(True)
        window.set_accept_focus(True)
        window.set_type_hint(Gdk.WindowTypeHint.UTILITY)
        window.set_app_paintable(True)
        vis = window.get_screen().get_rgba_visual()
        if vis is not None:
            window.set_visual(vis)
        return window

    def _clear_terminal_background(self, window, term):
        from gi.repository import Gdk, Gtk
        rgba = Gdk.RGBA()
        rgba.red = rgba.green = rgba.blue = rgba.alpha = 0.0
        if hasattr(term, "set_color_background"):
            term.set_color_background(rgba)
        fg = Gdk.RGBA()
        fg.red = fg.green = fg.blue = fg.alpha = 1.0
        if hasattr(term, "set_color_foreground"):
            term.set_color_foreground(fg)
        if hasattr(term, "set_bold_is_bright"):
            term.set_bold_is_bright(False)
        if hasattr(term, "set_allow_bold"):
            term.set_allow_bold(False)
        try:
            import gi
            gi.require_version("Pango", "1.0")
            from gi.repository import Pango
            fd = Pango.FontDescription.from_string(self.font_name)
            fd.set_weight(Pango.Weight.NORMAL)
            term.set_font(fd)
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
        prov = Gtk.CssProvider()
        prov.load_from_data(b"vte-terminal, window { background-color: transparent; padding: 0px; margin: 0px; font-weight: normal; text-shadow: 0 0 3px rgba(0, 229, 255, 0.40), 0 0 7px rgba(176, 88, 255, 0.20); letter-spacing: 0.35px; }")
        term.get_style_context().add_provider(prov, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        window.get_style_context().add_provider(prov, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def close(self):
        pid, self.child_pid = self.child_pid, 0
        if pid:
            try:
                os.kill(pid, signal.SIGTERM)
            except OSError:
                pass
        win, self.gtk_window, self.terminal = self.gtk_window, None, None
        if win is not None:
            win.destroy()
            if self.glib:
                self._pump_gtk(self.glib)
        ren, self.renderer = self.renderer, None
        if ren is not None:
            ren.close()


def ensure_random_visualizer_started() -> bool:
    try:
        if IS_WIN:
            try:
                if subprocess.check_output(['powershell.exe', '-NoProfile', '-Command',
                    'Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*MP_Liquid_Visualizer*" -or $_.CommandLine -like "*mp_liquid_visualizer_vulkan*" } | Select-Object -ExpandProperty ProcessId'],
                    stderr=subprocess.DEVNULL, text=True).strip():
                    return False
            except Exception:
                pass
        elif shutil.which("pgrep") and subprocess.run(["pgrep", "-f", "MP_Liquid_Visualizer|mp_liquid_visualizer_vulkan"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
            return False

        vis_script = next((p for p in (ROOT / "MP_Liquid_Visualizer.py", ROOT / "scripts" / "mp_liquid_visualizer_vulkan.py") if p.is_file()), None)
        if not vis_script:
            return False
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        kw = {"creationflags": 0x00000208} if IS_WIN else {"start_new_session": True}
        with open(CONFIG_DIR / "liquid_visualizer.log", "a") as f:
            subprocess.Popen([sys.executable, str(vis_script), "--preset", "random"], cwd=str(ROOT), stdin=subprocess.DEVNULL, stdout=f, stderr=f, **kw)
        return True
    except Exception:
        return False


def main(argv):
    if "--self-test" in argv:
        from liquid_glass_vulkan import run_self_test
        run_self_test()
        return 0
    if "--list-fonts" in argv:
        list_liquid_glass_fonts()
        return 0

    embed = "--embed-check" in argv
    opts = {"tracklist": None, "audio": None, "theme": None, "font": None, "set-font": None}
    flag_map = {"--tracklist": "tracklist", "--audio": "audio", "--theme": "theme", "-t": "theme",
                "--font": "font", "-f": "font", "--set-font": "set-font"}
    cleaned_argv, i, n = [], 0, len(argv)
    while i < n:
        a = argv[i]
        if a == "--no-visualizer":
            i += 1
        elif a in flag_map and i + 1 < n:
            opts[flag_map[a]] = argv[i + 1]
            i += 2
        elif "=" in a and a.split("=", 1)[0] in flag_map:
            k, v = a.split("=", 1)
            opts[flag_map[k]] = v
            i += 1
        else:
            cleaned_argv.append(a)
            i += 1
        if opts["set-font"] is not None:
            set_liquid_glass_font(opts["set-font"])
            print(f"✔ MP Liquid Glass Player default font set to: {opts['set-font']}")
            return 0

    if not embed and not opts["tracklist"] and "--self-test" not in argv and "--no-visualizer" not in argv:
        ensure_random_visualizer_started()

    mode = "MINI" if "--mini" in argv else ("MICRO" if "--micro" in argv else "NORMAL")
    if opts["tracklist"] and not embed:
        mode = "TRACKLIST"
        command = tracklist_argv(opts["tracklist"], audio_path=opts["audio"], theme=opts["theme"])
        if not Path(command[1]).is_file():
            raise RuntimeError(f"Tracklist viewer script was not found at {command[1]}")
    elif embed:
        command = embed_check_argv()
    else:
        extra = [a for a in cleaned_argv if a not in ("--self-test", "--embed-check", "--mini", "--micro")]
        if opts["theme"] and not any(a == "--theme" or a.startswith("--theme=") for a in extra):
            extra.extend(["--theme", opts["theme"]])
        command = player_argv(mode=mode, extra_args=extra)
        if not Path(command[1]).is_file():
            raise RuntimeError(f"MP Audio Player was not found at {command[1]}")

    ok = GlassHost(command, embed_check=embed, mode=mode, cli_theme=opts["theme"], font=opts["font"]).run()
    if embed:
        if not ok:
            raise RuntimeError("VTE window was not placed in the glass well")
        print("LIQUID_GLASS_EMBED_OK", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except Exception as exc:
        print(f"Liquid Glass: {exc}", file=sys.stderr)
        raise SystemExit(1)