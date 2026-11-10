"""TTY Audio Mode terminal lifecycle and frame drawing."""

import io
import os
import pty
import sys
import termios
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from mp_tty_runtime import (  # noqa: E402
    arm_terminal,
    consume_resize,
    iter_ndjson,
    note_resize,
    present_lines,
    restore_terminal,
    wait_for_input,
    write_ndjson,
)


class TestTtyRuntime(unittest.TestCase):
    def test_cbreak_keeps_signals_and_restores_termios(self):
        master, slave = pty.openpty()
        try:
            original = termios.tcgetattr(slave)
            self.assertTrue(arm_terminal(fd=slave, raw=False, install_signals=False))
            active = termios.tcgetattr(slave)
            self.assertEqual(active[3] & termios.ICANON, 0)
            self.assertNotEqual(active[3] & termios.ISIG, 0)
            restore_terminal()
            self.assertEqual(termios.tcgetattr(slave), original)
        finally:
            os.close(master)
            os.close(slave)

    def test_raw_mode_restores_too(self):
        master, slave = pty.openpty()
        try:
            original = termios.tcgetattr(slave)
            self.assertTrue(arm_terminal(fd=slave, raw=True, install_signals=False))
            active = termios.tcgetattr(slave)
            self.assertEqual(active[3] & termios.ISIG, 0)
            restore_terminal()
            self.assertEqual(termios.tcgetattr(slave), original)
        finally:
            os.close(master)
            os.close(slave)

    def test_steady_paint_does_not_clear_the_screen(self):
        steady = io.StringIO()
        present_lines(["status", "line"], stream=steady)
        self.assertNotIn("\033[2J", steady.getvalue())
        self.assertIn("\033[H", steady.getvalue())
        self.assertIn("status\nline", steady.getvalue())
        resized = io.StringIO()
        present_lines(["status"], full_clear=True, stream=resized)
        self.assertIn("\033[2J", resized.getvalue())

    def test_sigwinch_is_one_shot(self):
        note_resize()
        self.assertTrue(consume_resize())
        self.assertFalse(consume_resize())

    def test_wait_for_input_idles_then_reads(self):
        read_fd, write_fd = os.pipe()
        try:
            self.assertEqual(wait_for_input(read_fd, 0.05), b"")
            os.write(write_fd, b"q")
            self.assertEqual(wait_for_input(read_fd, 0.2), b"q")
        finally:
            os.close(read_fd)
            os.close(write_fd)

    def test_ndjson_frames_flush_and_reject_a_huge_record(self):
        buf = io.StringIO()
        write_ndjson({"ok": True, "n": 1}, buf)
        write_ndjson({"ok": False}, buf)
        rows = list(iter_ndjson(io.StringIO(buf.getvalue())))
        self.assertEqual(rows, [{"ok": True, "n": 1}, {"ok": False}])
        with self.assertRaises(ValueError):
            write_ndjson({"blob": "x" * 5000}, io.StringIO())


class TestPlayerTTYPaint(unittest.TestCase):
    def test_player_clears_only_after_a_resize_in_tty_mode(self):
        os.environ["MP_MIX_MANAGER_TTY_MODE"] = "1"
        try:
            import MP_Audio_Player as player

            player._TTY_RUNTIME_TRIED = False
            player._TTY_RUNTIME_MOD = None
            runtime = player._load_tty_runtime()
            self.assertIsNotNone(runtime)
            runtime.note_resize()
            first = io.StringIO()
            previous = sys.stdout
            try:
                sys.stdout = first
                player._present_frame(["row"], 40, 2)
            finally:
                sys.stdout = previous
            self.assertIn("\033[2J", first.getvalue())
            second = io.StringIO()
            try:
                sys.stdout = second
                player._present_frame(["row"], 40, 2)
            finally:
                sys.stdout = previous
            self.assertNotIn("\033[2J", second.getvalue())
            self.assertIn("\033[H", second.getvalue())
        finally:
            os.environ.pop("MP_MIX_MANAGER_TTY_MODE", None)
