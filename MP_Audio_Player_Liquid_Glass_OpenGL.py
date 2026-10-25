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
        return FONT_CONFIG_FILE.read_text(encoding="utf-8").strip() if FONT_CONFIG_FILE.is_file() else DEFAULT_FONT
    except Exception:
        return DEFAULT_FONT


def set_liquid_glass_font(font_str: str) -> None:
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        FONT_CONFIG_FILE.write_text(f"{str(font_str).strip()}\n", encoding="utf-8")
    except Exception as exc:
        print(f"Warning: {exc}", file=sys.stderr)


def list_liquid_glass_fonts():
    cur = get_liquid_glass_font()
    print("\n\033[1;38;2;0;229;255m══ MP Liquid Glass Player — Available Fonts ══\033[0m\n")
    for idx, (f_name, desc) in enumerate(RECOMMENDED_FONTS, 1):
        star = "\033[1;38;2;0;255;127m★ ACTIVE\033[0m" if f_name == cur else "        "
        print(f"  {star} \033[1;38;2;255;215;0m[{idx}]\033[0m \033[1;38;2;255;255;255m{f_name:<20s}\033[0m — {desc}")
    print(f"\n  \033[38;2;120;215;255mActive Font:\033[0m {cur}\n")


def player_panel_rects(cols, rows, char_w, char_h, origin_x, origin_y, mode="NORMAL"):
    box = lambda c, r, bc, br: (origin_x + c * char_w, origin_y + r * char_h, bc * char_w, br * char_h)
    iw = max(20, cols - 4)
    if mode == "MICRO":
        return box(2, 0, iw, rows), (0.0, 0.0, 0.0, 0.0)
    if mode == "MINI":
        return box(2, 0, iw, 3), box(2, 3, iw, max(1, rows - 3))
    if mode == "TRACKLIST":
        return (box(2, 0, iw, rows), (0.0, 0.0, 0.0, 0.0)) if rows <= 7 else (box(2, 0, iw, 7), box(2, 7, iw, max(1, rows - 7)))
    iw = max(20, cols - 6)
    before = 12 + (7 if rows >= 34 else (5 if rows >= 28 else 3))
    return box(2, 0, iw + 2, 4), box(2, before, iw + 2, max(1, rows - before - 5) + 2)


def _import_gtk():
    global Gdk, Gtk, GLib, Vte
    if sys.platform == "win32" or Gtk is not None:
        return GLib, Gtk, Vte
    os.environ["GDK_BACKEND"] = "x11"
    import gi
    for mod, ver in (("Gdk", "3.0"), ("Gtk", "3.0"), ("GdkX11", "3.0"), ("Vte", "2.91")):
        gi.require_version(mod, ver)
    from gi.repository import Gdk as _Gdk, GdkX11, GLib as _GLib, Gtk as _Gtk, Vte as _Vte
    if not hasattr(GdkX11, "X11Display"):
        raise RuntimeError("GDK X11 required")
    Gdk, Gtk, GLib, Vte = _Gdk, _Gtk, _GLib, _Vte
    return GLib, Gtk, Vte


def player_argv(mode="NORMAL", extra_args=None):
    cmd = [sys.executable, str(ROOT / "MP_Audio_Player.py"), "--interactive"]
    if mode in ("MINI", "MICRO"):
        cmd.append(f"--{mode.lower()}")
    if extra_args:
        cmd.extend(extra_args)
    return cmd


def tracklist_argv(tracklist_path, audio_path=None, theme=None):
    v_sh = next((p for p in (ROOT / "scripts" / "view_tracklist_console.sh", ROOT / "view_tracklist_console.sh") if p.is_file()), None)
    cmd = [shutil.which("bash") or "bash", str(v_sh)]
    if theme:
        cmd.extend(["--theme", str(theme)])
    cmd.append(str(tracklist_path))
    if audio_path:
        cmd.append(str(audio_path))
    return cmd


def _child_env(as_dict=False):
    env = {k: v for k, v in os.environ.items() if k != "GDK_BACKEND"}
    env.update({"TERM": "xterm-256color", "COLORTERM": "truecolor", "MP_LIQUID_GLASS": "1", "MP_LIQUID_GLASS_BACKEND": "opengl"})
    return env if as_dict else [f"{k}={v}" for k, v in env.items()]


def _mode_grid(mode):
    return {"TRACKLIST": (100, 35), "MINI": (74, 14), "MICRO": (74, 7)}.get(mode, (COLS, ROWS))


class GlassHost:
    def __init__(self, argv, embed_check=False, mode="NORMAL", font=None):
        self.argv, self.embed_check, self.mode = list(argv), embed_check, mode.upper()
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
            cols = max(cols, int(self.terminal.get_column_count() or 0))
            rows = max(rows, int(self.terminal.get_row_count() or 0))
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
            cols, rows = _mode_grid("NORMAL" if self.mode == "TRACKLIST" else self.mode)
            self._apply_grid(cols, rows, pos)
            self.is_maximized = False

    def set_mode(self, mode: str):
        self.mode = mode.upper()
        if self.renderer is not None:
            self.is_maximized = False
            self._apply_grid(*_mode_grid("NORMAL" if self.mode == "TRACKLIST" else self.mode))

    def _on_key_press(self, _term, event):
        kv = getattr(event, "keyval", 0)
        if kv in (Gdk.KEY_m, Gdk.KEY_M):
            self.set_mode({"NORMAL": "MINI", "MINI": "MICRO"}.get(self.mode, "NORMAL"))
            return False
        if kv == Gdk.KEY_K or (kv == Gdk.KEY_k and bool(getattr(event, "state", 0) & Gdk.ModifierType.SHIFT_MASK)):
            subprocess.run('pkill -9 -f "MP_Audio_Player"', shell=True)
            return True
        return False

    def _track_drag(self, down, dragging, origin, press):
        x, y = self.renderer.cursor
        w, h = self.renderer.window_size()
        cur_down = self.renderer.mouse_down
        m = max(float(self.renderer.bezel_px), 8.0)
        
        if cur_down and not down:
            if (x - (w - m * 0.72)) ** 2 + (y - m * 0.62) ** 2 <= max(m * 0.30, 4.0) ** 2:
                self.renderer.request_close()
                dragging = False
            elif y < max(float(self.renderer.bezel_px), 24.0) + 48:
                now = time.monotonic()
                if now - self._last_top_click < 0.45 and abs(x - self._last_top_click_x) < 35 and abs(y - self._last_top_click_y) < 35:
                    self.toggle_maximize()
                    dragging, self._last_top_click = False, 0.0
                else:
                    self._last_top_click, self._last_top_click_x, self._last_top_click_y = now, x, y
                    if not self.is_maximized:
                        dragging, origin = True, self.renderer.window_pos()
                        rx, ry = self.renderer.root_pointer()
                        press = (rx, ry) if (rx or ry) else (origin[0] + x, origin[1] + y)
            elif (x < m or y < m or x >= w - m or y >= h - m) and not self.is_maximized:
                dragging, origin = True, self.renderer.window_pos()
                rx, ry = self.renderer.root_pointer()
                press = (rx, ry) if (rx or ry) else (origin[0] + x, origin[1] + y)
        elif cur_down and dragging:
            rx, ry = self.renderer.root_pointer()
            self.renderer.set_window_pos(
                int(origin[0] + (rx - press[0] if (rx or ry) else x - (press[0] - origin[0]))),
                int(origin[1] + (ry - press[1] if (rx or ry) else y - (press[1] - origin[1])))
            )
        else:
            dragging = False
        return cur_down, dragging, origin, press

    def run(self):
        m = LiquidGlassRendererOpenGL.bezel_px
        iw, ih = self._target_cols * 9 + 2 * m, self._target_rows * 18 + 2 * m
        title = "Mix Tracklist Viewer" if self.mode == "TRACKLIST" else "MP Audio Player"
        
        if sys.platform == "win32":
            self.renderer = LiquidGlassRendererOpenGL(iw, ih, title)
            try:
                return self._run_windows()
            finally:
                self.close()
                
        glib, gtk, vte = _import_gtk()
        self.glib = gtk.init([]) or glib
        self.renderer = LiquidGlassRendererOpenGL(iw, ih, title)
        try:
            return self._run_window(vte, glib)
        finally:
            self.close()

    def _run_windows(self):
        self.renderer.open()
        self._sync_panels()
        if self.embed_check:
            self.renderer.draw(read_player_theme())
            return True

        proc = subprocess.Popen(self.argv, cwd=str(ROOT), env=_child_env(as_dict=True), creationflags=0x00000010)
        self.child_pid = proc.pid
        child_hwnd = None
        user32 = ctypes.windll.user32
        
        for _ in range(50):
            if proc.poll() is not None:
                break
            found = []
            user32.EnumWindows(ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)(
                lambda hwnd, _: found.append(hwnd) or True if (pid := ctypes.c_uint32()) and user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid)) and pid.value == proc.pid and user32.IsWindowVisible(hwnd) else True
            ), 0)
            if found:
                child_hwnd = found[0]
                break
            time.sleep(0.02)

        if child_hwnd:
            self.child_xid = child_hwnd
            try:
                user32.SetWindowLongPtrW(child_hwnd, -16, (user32.GetWindowLongPtrW(child_hwnd, -16) & ~(0x00C00000 | 0x00040000)) | 0x80000000)
                if (gh := self.renderer.win32_window()):
                    user32.SetParent(child_hwnd, gh)
            except Exception:
                pass
            self._place_terminal(force=True)

        down = dragging = False
        origin, press, theme, theme_at = self.renderer.window_pos(), (0, 0), read_player_theme(), 0.0
        while not self.renderer.should_close and proc.poll() is None:
            now = time.monotonic()
            if now - theme_at > 0.4:
                theme, theme_at = read_player_theme(), now
            self._sync_panels()
            self.renderer.draw(theme)
            down, dragging, origin, press = self._track_drag(down, dragging, origin, press)
            if dragging:
                self._place_terminal(force=True)
            if not self.renderer.poll():
                break
            time.sleep(0.008)
            
        if proc.poll() is None:
            try: proc.terminate()
            except Exception: pass
        return True

    def _run_window(self, vte, glib):
        self.renderer.open()
        window = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
        window.set_decorated(False)
        window.set_skip_taskbar_hint(window.set_skip_pager_hint(window.set_accept_focus(True) or True) or True)
        window.set_type_hint(Gdk.WindowTypeHint.UTILITY)
        window.set_app_paintable(True)
        if (visual := window.get_screen().get_rgba_visual()):
            window.set_visual(visual)

        term = vte.Terminal()
        term.set_audible_bell(False)
        if hasattr(term, "set_scrollback_lines"):
            term.set_scrollback_lines(0)
        window.add(term)
        
        # Style terminal
        provider = Gtk.CssProvider()
        provider.load_from_data(b"vte-terminal, window { background-color: transparent; padding: 0px; margin: 0px; font-weight: normal; text-shadow: 0 0 3px rgba(0, 229, 255, 0.40); }")
        term.get_style_context().add_provider(provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        window.get_style_context().add_provider(provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        
        window.show_all()
        term.realize()
        while glib.MainContext.default().pending():
            glib.MainContext.default().iteration(False)
            
        self.gtk_window, self.terminal = window, term
        self._apply_grid(self._target_cols, self._target_rows)
        self.renderer.poll()
        
        if (gdk_win := window.get_window()):
            self.child_xid = int(gdk_win.get_xid())
        if self.child_xid <= 0:
            raise RuntimeError("VTE X11 missing")
            
        self._place_terminal(force=True)
        self.renderer.focus_window(self.child_xid)
        
        term.connect("key-press-event", self._on_key_press)
        term.connect("child-exited", lambda *_: setattr(self, "child_done", True) or self.renderer.request_close())
        term.spawn_async(vte.PtyFlags.DEFAULT, str(ROOT), self.argv, _child_env(), glib.SpawnFlags.DEFAULT, None, None, -1, None, 
                         lambda _, p, err, *_: setattr(self, "spawn_error", str(err)) if err else setattr(self, "child_pid", int(p or 0)))
        term.grab_focus()

        theme, theme_at, down, dragging = read_player_theme(), 0.0, False, False
        origin, press, started = (0, 0), (0.0, 0.0), time.monotonic()
        while not self.renderer.should_close:
            now = time.monotonic()
            if now - theme_at > 0.4:
                theme, theme_at = read_player_theme(), now
            self._sync_panels()
            self.renderer.draw(theme)
            down, dragging, origin, press = self._track_drag(down, dragging, origin, press)
            self._place_terminal()
            while glib.MainContext.default().pending():
                glib.MainContext.default().iteration(False)
            if self.spawn_error:
                raise RuntimeError(self.spawn_error)
            if self.embed_check and (self.child_pid and time.monotonic() - started <= 8):
                return True
        return False

    def close(self):
        if self.child_pid:
            try: os.kill(self.child_pid, signal.SIGTERM)
            except OSError: pass
            self.child_pid = 0
        if self.gtk_window is not None:
            self.gtk_window.destroy()
            self.gtk_window = self.terminal = None
        if self.renderer is not None:
            self.renderer.close()
            self.renderer = None


def ensure_random_visualizer_started() -> bool:
    try:
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
                print(f"✔ Default font set to: {val}")
                return 0
            if arg == "--tracklist": tracklist_path = val
            elif arg == "--audio": audio_path = val
            elif arg in ("--theme", "-t"): theme_arg = val
            else: font_arg = val
            i += 2
        elif arg.startswith(tuple(f"{k}=" for k in ("--tracklist", "--audio", "--theme", "--font", "--set-font"))):
            k, val = arg.split("=", 1)
            if k == "--set-font":
                set_liquid_glass_font(val)
                print(f"✔ Default font set to: {val}")
                return 0
            if k == "--tracklist": tracklist_path = val
            elif k == "--audio": audio_path = val
            elif k == "--theme": theme_arg = val
            else: font_arg = val
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
    elif embed:
        command = [sys.executable, "-c", "import time; print('LIQUID_GLASS_CHILD', flush=True); time.sleep(30)"]
    else:
        extra = [a for a in cleaned_argv if a not in ("--self-test", "--embed-check", "--mini", "--micro")]
        if theme_arg and not any(a.startswith("--theme") for a in extra):
            extra.extend(["--theme", theme_arg])
        command = player_argv(mode=mode, extra_args=extra)

    ok = GlassHost(command, embed_check=embed, mode=mode, font=font_arg).run()
    if embed:
        if not ok:
                    raise RuntimeError("VTE embed failed")
        print("LIQUID_GLASS_EMBED_OK", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except Exception as exc:
        print(f"Liquid Glass (OpenGL): {exc}", file=sys.stderr)
        raise SystemExit(1)