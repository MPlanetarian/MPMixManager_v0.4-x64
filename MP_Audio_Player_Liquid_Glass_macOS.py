#!/usr/bin/env python3
"""Apple Silicon Metal liquid-glass window hosting the MP Audio Player for macOS.

Runs natively on Apple Silicon (M1/M2/M3/M4 or newer) using Apple's Metal graphics API.
Legacy Intel-based Macs are explicitly not supported.
"""

from __future__ import annotations

import os
import platform
import pty
import select
import signal
import sys
import termios
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from liquid_glass_metal import (  # noqa: E402
    LiquidGlassRendererMetal,
    check_apple_silicon_support,
    is_apple_silicon,
    is_intel_mac,
    is_macos,
    read_player_theme,
)

COLS = 120
ROWS = 40


def player_panel_rects(cols=130, rows=42, char_w=8, char_h=16, origin_x=0, origin_y=0, mode="NORMAL"):
    """Pixel boxes for the player panels in ``_draw_frame`` across Normal, Mini, and Micro modes."""
    def box(col, row, box_cols, box_rows):
        return (
            origin_x + col * char_w,
            origin_y + row * char_h,
            box_cols * char_w,
            box_rows * char_h,
        )

    m = str(mode).upper()
    if m == "MICRO":
        return (
            box(2, 0, max(20, cols - 4), rows),
            (0.0, 0.0, 0.0, 0.0),
        )
    elif m == "MINI":
        return (
            box(2, 0, max(20, cols - 4), 3),
            box(2, 3, max(20, cols - 4), max(1, rows - 3)),
        )
    else:
        iw = max(20, cols - 6)
        viz_rows = 7 if rows >= 34 else (5 if rows >= 28 else 3)
        before = 4 + 1 + 1 + 3 + (viz_rows + 3) + 1
        body_rows = max(1, rows - (before + 1) - 4)
        return (
            box(2, 0, iw + 2, 4),
            box(2, before, iw + 2, body_rows + 2),
        )


def player_argv(mode="NORMAL", extra_args=None):
    cmd = [sys.executable, str(ROOT / "MP_Audio_Player.py"), "--interactive"]
    m = str(mode).upper()
    if m == "MINI":
        cmd.append("--mini")
    elif m == "MICRO":
        cmd.append("--micro")
    if extra_args:
        cmd.extend(extra_args)
    return cmd


def embed_check_argv():
    code = "import time; print('LIQUID_GLASS_CHILD', flush=True); time.sleep(30)"
    return [sys.executable, "-c", code]


def _child_env():
    env = {key: value for key, value in os.environ.items()}
    env["TERM"] = "xterm-256color"
    env["COLORTERM"] = "truecolor"
    env["MP_LIQUID_GLASS"] = "1"
    env["MP_LIQUID_GLASS_BACKEND"] = "metal"
    env["MP_LIQUID_GLASS_PLATFORM"] = "macos-arm64"
    return env


class MetalGlassHost:
    """Apple Silicon Metal liquid-glass host for MP Audio Player."""

    def __init__(self, argv, embed_check=False, mode="NORMAL"):
        self.argv = list(argv)
        self.embed_check = embed_check
        self.mode = mode.upper()
        self.renderer = None
        self.child_pid = 0
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

    def _sync_panels(self):
        if self.renderer is None:
            return
        char_w, char_h = 9, 18
        margin = self.renderer.bezel_px
        cols = getattr(self, "_target_cols", COLS)
        rows = getattr(self, "_target_rows", ROWS)
        self.renderer.set_panels(
            player_panel_rects(cols, rows, char_w, char_h, margin, margin, mode=self.mode)
        )

    def toggle_maximize(self):
        """Toggle fullscreen maximize across active display workarea."""
        if self.renderer is None:
            return
        char_w, char_h = 9, 18
        margin = self.renderer.bezel_px

        if not self.is_maximized:
            self._saved_rect = (self.renderer.window_pos(), self.renderer.window_size())
            wx, wy, ww, wh = self.renderer.get_workarea()
            max_cols = max(40, int((ww - 2 * margin) // char_w))
            max_rows = max(10, int((wh - 2 * margin) // char_h))
            self._target_cols = max_cols
            self._target_rows = max_rows
            self.renderer.set_window_pos(wx, wy)
            self.renderer.set_window_size(ww, wh)
            self._sync_panels()
            self.is_maximized = True
        else:
            pos, size = getattr(self, "_saved_rect", ((72, 64), (1280, 820)))
            if self.mode == "MINI":
                cols, rows = 74, 14
            elif self.mode == "MICRO":
                cols, rows = 74, 7
            else:
                cols, rows = COLS, ROWS
            self._target_cols = cols
            self._target_rows = rows
            self.renderer.set_window_pos(pos[0], pos[1])
            self.renderer.set_window_size(size[0], size[1])
            self._sync_panels()
            self.is_maximized = False

    def cycle_mode(self):
        """Cycle between Normal, Mini, and Micro modes in-place."""
        char_w, char_h = 9, 18
        margin = self.renderer.bezel_px

        if self.mode == "NORMAL":
            self.mode = "MINI"
            self._target_cols, self._target_rows = 74, 14
        elif self.mode == "MINI":
            self.mode = "MICRO"
            self._target_cols, self._target_rows = 74, 7
        else:
            self.mode = "NORMAL"
            self._target_cols, self._target_rows = COLS, ROWS

        ww = self._target_cols * char_w + 2 * margin
        wh = self._target_rows * char_h + 2 * margin
        if self.renderer:
            self.renderer.set_window_size(ww, wh)
            self._sync_panels()

    def run(self):
        """Execute the Metal Liquid Glass player session."""
        check_apple_silicon_support()

        char_w, char_h = 9, 18
        margin = LiquidGlassRendererMetal.bezel_px
        init_w = self._target_cols * char_w + 2 * margin
        init_h = self._target_rows * char_h + 2 * margin

        self.renderer = LiquidGlassRendererMetal(
            width=init_w,
            height=init_h,
            title="MP Audio Player (Liquid Glass - Metal / Apple Silicon)",
        )
        self.renderer.open()
        self._sync_panels()

        if self.embed_check:
            # Headless / self-test validation
            theme = read_player_theme()
            self.renderer.draw(theme)
            return True

        # Spawn player in pseudoterminal on macOS
        master_fd, slave_fd = pty.openpty()
        pid = os.fork()
        if pid == 0:
            # Child process: attach to slave PTY and run player
            os.close(master_fd)
            os.setsid()
            os.dup2(slave_fd, 0)
            os.dup2(slave_fd, 1)
            os.dup2(slave_fd, 2)
            if slave_fd > 2:
                os.close(slave_fd)
            env = _child_env()
            os.execvpe(self.argv[0], self.argv, env)
            sys.exit(1)

        os.close(slave_fd)
        self.child_pid = pid

        theme = read_player_theme()
        theme_at = 0.0

        try:
            while not self.renderer.should_close:
                now = time.monotonic()
                if now - theme_at > 0.4:
                    theme = read_player_theme()
                    theme_at = now

                self._sync_panels()
                self.renderer.draw(theme)

                # Check if child process has exited
                pid_res, _ = os.waitpid(self.child_pid, os.WNOHANG)
                if pid_res == self.child_pid:
                    break

                # Non-blocking poll of terminal I/O
                r, _, _ = select.select([master_fd], [], [], 0.016)
                if master_fd in r:
                    try:
                        data = os.read(master_fd, 4096)
                        if not data:
                            break
                        # Handle in-process 'M' key or commands if applicable
                    except OSError:
                        break
        finally:
            self.close(master_fd)

        return True

    def close(self, master_fd=None):
        if master_fd is not None:
            try:
                os.close(master_fd)
            except OSError:
                pass
        pid = self.child_pid
        self.child_pid = 0
        if pid:
            try:
                os.kill(pid, signal.SIGTERM)
                time.sleep(0.05)
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
        if self.renderer:
            self.renderer.close()
            self.renderer = None


def main(argv):
    # 1. Check Apple Silicon hardware requirement first
    if "--help" not in argv and "-h" not in argv:
        if not is_macos():
            print(
                "Error: MP Audio Player Liquid Glass (macOS Metal) requires Apple Silicon macOS (M1/M2/M3/M4+).\n"
                f"Current operating system is '{sys.platform}'.",
                file=sys.stderr,
            )
            return 1

        if is_intel_mac():
            print(
                "======================================================================\n"
                "  ❌ UNSUPPORTED ARCHITECTURE: INTEL-BASED MAC DETECTED\n"
                "======================================================================\n"
                "  MP Audio Player Liquid Glass (Metal) exclusively supports Apple\n"
                "  Silicon Macs (Apple M1, M2, M3, M4 or newer) running macOS.\n\n"
                "  Legacy Intel x86_64 Macs do not have the required unified memory\n"
                "  Metal pipeline architecture and are not supported.\n"
                "======================================================================",
                file=sys.stderr,
            )
            return 1

        if not is_apple_silicon():
            print(
                f"Error: Unsupported machine architecture '{platform.machine()}'.\n"
                "Apple Silicon (M1/M2/M3/M4+) is required.",
                file=sys.stderr,
            )
            return 1

    if "--self-test" in argv:
        from liquid_glass_metal import run_self_test

        run_self_test()
        return 0

    embed = "--embed-check" in argv
    mode = "MINI" if "--mini" in argv else ("MICRO" if "--micro" in argv else "NORMAL")
    extra = [a for a in argv if a not in ("--self-test", "--embed-check", "--mini", "--micro")]
    command = embed_check_argv() if embed else player_argv(mode=mode, extra_args=extra)
    if not Path(command[1]).is_file() and not embed:
        raise RuntimeError(f"MP Audio Player was not found at {command[1]}")

    host = MetalGlassHost(command, embed_check=embed, mode=mode)
    ok = host.run()
    if embed and ok:
        print("LIQUID_GLASS_METAL_EMBED_OK", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as exc:
        print(f"Liquid Glass (Metal): {exc}", file=sys.stderr)
        sys.exit(1)
