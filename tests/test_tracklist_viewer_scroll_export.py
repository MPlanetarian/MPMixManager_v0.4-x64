#!/usr/bin/env python3
"""Tracklist viewer scrolling and HTML/TEXT export.

The viewer used to print the whole file, so a tracklist taller than the window
began part way down and could not be scrolled. It now draws a fixed viewport
that starts at line 1 and supports arrows, PgUp/PgDn, Home/End and the mouse
wheel. Both the viewer and MP_Audio_Player.py export to
``<program folder>/TRACKLIST_EXPORTS``.
"""

import fcntl
import os
import pty
import re
import select
import struct
import sys
import tempfile
import termios
import time
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import MP_Audio_Player as mp_player  # noqa: E402
import tracklist_export  # noqa: E402

VIEWER = REPO_ROOT / "scripts" / "view_tracklist_console.sh"
ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]")


def strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", text)


def write_long_tracklist(path: Path, tracks: int = 60) -> Path:
    lines = [
        "RELEASE INFO",
        "Title: Bitstream Odyssey",
        "Artist: MPlanetarian",
        "=== TRACKLIST ===",
    ]
    lines += [f"{i:02d}. Artist {i} - Track Title {i} (Name {i} Remix)" for i in range(1, tracks + 1)]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def run_viewer(tracklist: Path, keys=(), rows: int = 30, columns: int = 100,
               env=None, timeout: float = 4.0) -> str:
    """Drive the viewer inside a real PTY and return the raw output."""
    master, slave = pty.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", rows, columns, 0, 0))
    pid = os.fork()
    if pid == 0:  # pragma: no cover - child process
        os.close(master)
        os.setsid()
        fcntl.ioctl(slave, termios.TIOCSCTTY, 0)
        for fd in (0, 1, 2):
            os.dup2(slave, fd)
        os.close(slave)
        os.environ.update({"TERM": "xterm-256color", "LINES": str(rows), "COLUMNS": str(columns)})
        if env:
            os.environ.update(env)
        os.execlp("bash", "bash", str(VIEWER), str(tracklist))

    os.close(slave)
    out = b""

    def drain(delay: float = 0.12) -> None:
        nonlocal out
        while True:
            ready, _, _ = select.select([master], [], [], delay)
            if not ready:
                return
            try:
                chunk = os.read(master, 65536)
            except OSError:
                return
            if not chunk:
                return
            out += chunk

    drain(0.9)
    for key in keys:
        os.write(master, key)
        drain(0.18)
    os.write(master, b"q")
    drain(0.4)
    try:
        os.close(master)
    except OSError:
        pass
    try:
        os.waitpid(pid, 0)
    except ChildProcessError:
        pass
    return out.decode("utf-8", "ignore")


def viewport(output: str):
    matches = re.findall(r"Lines (\d+)-(\d+) of (\d+)", strip_ansi(output))
    return tuple(int(v) for v in matches[-1]) if matches else None


class TestTracklistViewport(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.tracklist = write_long_tracklist(self.base / "Mix_Long.txt")

    def tearDown(self):
        self.tmp.cleanup()

    def test_first_screen_starts_at_line_one(self):
        raw = run_viewer(self.tracklist)
        text = strip_ansi(raw)
        self.assertIn("RELEASE INFO", text)
        self.assertIn("01. Artist 1 - Track Title 1", text)
        self.assertIn("Title: Bitstream Odyssey", text)
        self.assertEqual(viewport(raw), (1, 14, 64))

    def test_long_tracklist_is_clipped_to_the_window(self):
        raw = run_viewer(self.tracklist)
        text = strip_ansi(raw)
        # Nothing from far down the file may leak into the first screen.
        self.assertNotIn("30. Artist 30", text)
        self.assertLessEqual(len(text.splitlines()), 30)

    def test_arrow_keys_scroll_one_line(self):
        raw = run_viewer(self.tracklist, keys=[b"\x1b[B" * 3])
        self.assertEqual(viewport(raw), (4, 17, 64))

    def test_scrolling_up_clamps_at_the_first_line(self):
        raw = run_viewer(self.tracklist, keys=[b"\x1b[A" * 4])
        self.assertEqual(viewport(raw), (1, 14, 64))

    def test_page_keys_scroll_a_full_page(self):
        raw = run_viewer(self.tracklist, keys=[b"\x1b[6~"])
        self.assertEqual(viewport(raw), (15, 28, 64))
        raw = run_viewer(self.tracklist, keys=[b"\x1b[6~", b"\x1b[5~"])
        self.assertEqual(viewport(raw), (1, 14, 64))

    def test_home_and_end_jump(self):
        end = viewport(run_viewer(self.tracklist, keys=[b"\x1b[F"]))
        self.assertEqual(end[1], 64)
        home = viewport(run_viewer(self.tracklist, keys=[b"\x1b[F", b"\x1b[H"]))
        self.assertEqual(home, (1, 14, 64))

    def test_mouse_wheel_scrolls(self):
        down = viewport(run_viewer(self.tracklist, keys=[b"\x1b[<65;20;10M"]))
        self.assertGreater(down[0], 1)
        up = viewport(run_viewer(self.tracklist, keys=[b"\x1b[<64;20;10M"]))
        self.assertEqual(up, (1, 14, 64))

    def test_short_terminal_still_renders_from_the_top(self):
        raw = run_viewer(self.tracklist, rows=14, columns=44)
        text = strip_ansi(raw)
        self.assertIn("RELEASE INFO", text)
        first, last, total = viewport(raw)
        self.assertEqual(first, 1)
        self.assertEqual(total, 64)
        self.assertLessEqual(len(text.splitlines()), 14)

    def test_scroll_help_is_shown(self):
        text = strip_ansi(run_viewer(self.tracklist))
        for token in ("[↑/↓]", "[PgUp/PgDn]", "[Home/End]", "[Wheel]", "[X]", "[Y]"):
            self.assertIn(token, text)


class TestTracklistExport(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.tracklist = write_long_tracklist(self.base / "Mix_Export.txt", tracks=3)
        self.program = self.base / "MPMixManager"
        self.program.mkdir()
        self.sample = self.base / "sample.txt"
        self.sample.write_text("hello", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_export_html_lands_in_program_tracklist_exports(self):
        saved = tracklist_export.export_html(self.tracklist, base_dir=self.program)
        self.assertEqual(saved.parent, self.program / "TRACKLIST_EXPORTS")
        self.assertTrue(saved.is_file())
        html = saved.read_text(encoding="utf-8")
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn("Artist 1", html)
        self.assertIn('class="remix"', html)
        self.assertIn("3 tracks", html)

    def test_export_text_is_a_clean_copy(self):
        saved = tracklist_export.export_text(self.tracklist, base_dir=self.program)
        self.assertEqual(saved.parent, self.program / "TRACKLIST_EXPORTS")
        self.assertEqual(saved.read_text(encoding="utf-8"), self.tracklist.read_text(encoding="utf-8"))

    def test_export_rejects_unknown_format(self):
        with self.assertRaises(ValueError):
            tracklist_export.export_tracklist(self.tracklist, "pdf", base_dir=self.program)

    def test_export_creates_missing_destination(self):
        saved = tracklist_export.export_tracklist(
            self.tracklist, "html", output_dir=self.base / "nested" / "dest")
        self.assertTrue(saved.is_file())

    def test_cli_prints_saved_path(self):
        import subprocess
        res = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "tracklist_export.py"), str(self.tracklist),
             "--format", "html", "--base-dir", str(self.program)],
            capture_output=True, text=True, timeout=20,
        )
        self.assertEqual(res.returncode, 0, res.stderr)
        saved = Path(res.stdout.strip())
        self.assertTrue(saved.is_file())
        self.assertEqual(saved.parent, self.program / "TRACKLIST_EXPORTS")

    def test_player_helper_exports_to_program_folder(self):
        ok, saved = mp_player.export_tracklist_file(self.tracklist, "html", base_dir=self.program)
        self.assertTrue(ok, saved)
        self.assertTrue(Path(saved).is_file())
        self.assertEqual(Path(saved).parent, self.program / "TRACKLIST_EXPORTS")

    def test_player_helper_reports_missing_tracklist(self):
        ok, message = mp_player.export_tracklist_file(self.base / "missing.txt", "html", base_dir=self.program)
        self.assertFalse(ok)
        self.assertIn("not found", message)

    def test_viewer_export_flag_html(self):
        import subprocess
        res = subprocess.run(
            ["bash", str(VIEWER), "--export", "html", str(self.tracklist)],
            capture_output=True, text=True, timeout=20,
        )
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("Tracklist exported (html)", res.stdout)
        exported = REPO_ROOT / "TRACKLIST_EXPORTS" / "Mix_Export.html"
        self.assertTrue(exported.is_file())

    def test_viewer_export_flag_text(self):
        import subprocess
        res = subprocess.run(
            ["bash", str(VIEWER), "--export", "text", str(self.tracklist)],
            capture_output=True, text=True, timeout=20,
        )
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("Tracklist exported (text)", res.stdout)
        self.assertTrue((REPO_ROOT / "TRACKLIST_EXPORTS" / "Mix_Export.txt").is_file())

    def test_viewer_x_and_y_keys_export(self):
        raw = run_viewer(self.tracklist, keys=[b"x", b"y"])
        text = strip_ansi(raw)
        self.assertIn("Tracklist exported (HTML)", text)
        self.assertIn("Tracklist exported (TEXT)", text)
        exports = REPO_ROOT / "TRACKLIST_EXPORTS"
        self.assertTrue((exports / "Mix_Export.html").is_file())
        self.assertTrue((exports / "Mix_Export.txt").is_file())

    def test_html_escapes_user_content(self):
        risky = self.base / "Mix_Risky.txt"
        risky.write_text("01. <script>alert('x')</script> - Track & Title\n", encoding="utf-8")
        saved = tracklist_export.export_html(risky, base_dir=self.program)
        html = saved.read_text(encoding="utf-8")
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("Track &amp; Title", html)


if __name__ == "__main__":
    unittest.main()
