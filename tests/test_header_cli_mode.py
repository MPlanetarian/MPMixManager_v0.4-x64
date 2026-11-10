#!/usr/bin/env python3
"""The main header names the session: CLI Mode, TTY CLI Mode, or neither."""

import os
import pty
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")


def _visible(text: str) -> str:
    return ANSI.sub("", text)


def _render(env=None, stdin=None, stdout=None) -> str:
    script = r"""
    source ./Mix_Archive_Manager.sh >/dev/null 2>&1 || true
    set_theme_colors retro_linux_memories
    _TERM_COLS=120
    _TERM_LINES=40
    MIX_ARCHIVE_CONFIGURED=true
    is_mix_archive_configured() { return 0; }
    get_manager_uptime() { _MANAGER_UPTIME_LINE="  Uptime: 1h"; }
    _s4_hardware_connected() { return 1; }
    render_main_header 116 >/dev/null
    printf '%b\n' "$_RENDERED_MAIN_HEADER"
    """
    proc = subprocess.run(
        ["bash", "--noprofile", "--norc", "-c", script],
        cwd=str(ROOT),
        env=env,
        stdin=stdin,
        stdout=stdout if stdout is not None else subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if stdout is not None:
        return ""
    if proc.returncode != 0:
        raise AssertionError(proc.stderr.decode("utf-8", "replace")[-2000:])
    return proc.stdout.decode("utf-8", "replace")


def _base_env(**extra) -> dict:
    env = os.environ.copy()
    for key in ("MP_GUI_SESSION", "MP_TTY_KIOSK", "MP_HEADER_CLI_MODE", "MP_MIX_MANAGER_TTY_MODE"):
        env.pop(key, None)
    env.update(extra)
    return env


def _fake_tty_env(name: str, **extra) -> dict:
    bindir = tempfile.mkdtemp(prefix="mp-tty-")
    tty_bin = Path(bindir) / "tty"
    tty_bin.write_text(f"#!/bin/sh\nprintf '%s\\n' '{name}'\n", encoding="utf-8")
    tty_bin.chmod(0o755)
    env = _base_env(**extra)
    env["PATH"] = f"{bindir}:{env.get('PATH', '')}"
    return env


class HeaderCliModeTest(unittest.TestCase):
    def test_a_pipe_shows_no_mode(self):
        visible = _visible(_render(env=_base_env()))
        self.assertNotIn("CLI Mode", visible)

    def test_desktop_bash_shows_cli_mode(self):
        master, slave = pty.openpty()
        try:
            script = r"""
            source ./Mix_Archive_Manager.sh >/dev/null 2>&1 || true
            set_theme_colors retro_linux_memories
            _TERM_COLS=120
            _TERM_LINES=40
            MIX_ARCHIVE_CONFIGURED=true
            is_mix_archive_configured() { return 0; }
            get_manager_uptime() { _MANAGER_UPTIME_LINE="  Uptime: 1h"; }
            _s4_hardware_connected() { return 1; }
            render_main_header 116 >/dev/null
            printf '%b\n' "$_RENDERED_MAIN_HEADER"
            """
            proc = subprocess.run(
                ["bash", "--noprofile", "--norc", "-c", script],
                cwd=str(ROOT),
                env=_base_env(),
                stdin=slave,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
        finally:
            os.close(slave)
            os.close(master)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace")[-2000:])
        visible = _visible(proc.stdout.decode("utf-8", "replace"))
        self.assertIn("CLI Mode", visible)
        self.assertNotIn("TTY CLI Mode", visible)
        title = next(line for line in visible.splitlines() if "MP Mix Archive Manager" in line)
        self.assertIn("CLI Mode", title)
        self.assertTrue(title.endswith("│"), title)
        self.assertEqual(len(title), 118, title)

    def test_linux_console_shows_tty_cli_mode(self):
        visible = _visible(_render(env=_fake_tty_env("/dev/tty1")))
        title = next(line for line in visible.splitlines() if "MP Mix Archive Manager" in line)
        self.assertIn("TTY CLI Mode", title)
        self.assertTrue(title.endswith("│"), title)
        self.assertEqual(len(title), 118, title)

    def test_console_device_shows_tty_cli_mode(self):
        visible = _visible(_render(env=_fake_tty_env("/dev/console")))
        self.assertIn("TTY CLI Mode", visible)

    def test_tty_kiosk_shows_tty_cli_mode(self):
        visible = _visible(_render(env=_base_env(MP_TTY_KIOSK="1")))
        self.assertIn("TTY CLI Mode", visible)

    def test_mp_gui_hides_the_label_on_a_terminal(self):
        master, slave = pty.openpty()
        try:
            script = r"""
            source ./Mix_Archive_Manager.sh >/dev/null 2>&1 || true
            set_theme_colors retro_linux_memories
            _TERM_COLS=120
            _TERM_LINES=40
            MIX_ARCHIVE_CONFIGURED=true
            is_mix_archive_configured() { return 0; }
            get_manager_uptime() { _MANAGER_UPTIME_LINE="  Uptime: 1h"; }
            _s4_hardware_connected() { return 1; }
            render_main_header 116 >/dev/null
            printf '%b\n' "$_RENDERED_MAIN_HEADER"
            """
            proc = subprocess.run(
                ["bash", "--noprofile", "--norc", "-c", script],
                cwd=str(ROOT),
                env=_base_env(MP_GUI_SESSION="1"),
                stdin=slave,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
        finally:
            os.close(slave)
            os.close(master)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace")[-2000:])
        visible = _visible(proc.stdout.decode("utf-8", "replace"))
        self.assertNotIn("CLI Mode", visible)

    def test_mp_gui_hides_tty_cli_mode(self):
        visible = _visible(_render(env=_fake_tty_env("/dev/tty1", MP_GUI_SESSION="1")))
        self.assertNotIn("CLI Mode", visible)
        visible = _visible(_render(env=_base_env(MP_GUI_SESSION="1", MP_TTY_KIOSK="1")))
        self.assertNotIn("CLI Mode", visible)

    def test_pts_name_without_a_terminal_is_blank(self):
        visible = _visible(_render(env=_fake_tty_env("/dev/pts/4")))
        self.assertNotIn("CLI Mode", visible)

    def test_narrow_title_still_shows_tty_cli_mode(self):
        script = r"""
        source ./Mix_Archive_Manager.sh >/dev/null 2>&1 || true
        set_theme_colors retro_linux_memories
        _TERM_COLS=40
        _TERM_LINES=24
        MIX_ARCHIVE_CONFIGURED=true
        is_mix_archive_configured() { return 0; }
        get_manager_uptime() { _MANAGER_UPTIME_LINE="  Uptime: 1h"; }
        _s4_hardware_connected() { return 1; }
        render_main_header 36 >/dev/null
        printf '%b\n' "$_RENDERED_MAIN_HEADER"
        """
        proc = subprocess.run(
            ["bash", "--noprofile", "--norc", "-c", script],
            cwd=str(ROOT),
            env=_base_env(MP_HEADER_CLI_MODE="tty"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace")[-2000:])
        visible = _visible(proc.stdout.decode("utf-8", "replace"))
        self.assertIn("TTY CLI Mode", visible)


if __name__ == "__main__":
    unittest.main()
