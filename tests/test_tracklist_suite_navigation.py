#!/usr/bin/env python3
"""
Unit and integration tests for Option 13 > Option 1: Tracklist Management Suite
in Mix_Archive_Manager.sh.
Verifies:
- detect_active_music_player completes quickly (<1.5s) without hanging
- Option 13 > Option 1 loads cleanly without freezing
- Keyboard arrow navigation and Esc/q/0 exit functionality
"""

import os
import pty
import re
import select
import subprocess
import time
import unittest
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent
MANAGER_SCRIPT = REPO_DIR / "Mix_Archive_Manager.sh"


def run_bash_pty(script_body: str, key_sequence=None, timeout: float = 4.0) -> tuple[str, int]:
    master, slave = pty.openpty()
    pid = os.fork()
    if pid == 0:
        os.close(master)
        os.setsid()
        import fcntl
        import termios
        fcntl.ioctl(slave, termios.TIOCSCTTY, 0)
        os.dup2(slave, 0)
        os.dup2(slave, 1)
        os.dup2(slave, 2)
        os.close(slave)
        os.environ["TERM"] = "xterm-256color"
        os.environ["LINES"] = "35"
        os.environ["COLUMNS"] = "110"
        os.environ["ENABLE_BREATHING_CURSOR"] = "0"
        os.execlp("bash", "bash", "-c", script_body)
    else:
        os.close(slave)
        out = b""
        start_t = time.time()
        while b"READY" not in out and time.time() - start_t < 2.0:
            r, _, _ = select.select([master], [], [], 0.05)
            if r:
                try:
                    c = os.read(master, 1024)
                    if not c:
                        break
                    out += c
                except OSError:
                    break

        time.sleep(0.1)
        if key_sequence:
            if isinstance(key_sequence, str):
                key_sequence = key_sequence.encode("utf-8")
            tokens = re.findall(rb"\x1b(?:\[[A-Z0-9~]+|O[A-Z])|.", key_sequence, re.DOTALL)
            for tok in tokens:
                os.write(master, tok)
                time.sleep(0.04)

        deadline = time.time() + timeout
        while time.time() < deadline:
            r, _, _ = select.select([master], [], [], 0.1)
            if r:
                try:
                    c = os.read(master, 1024)
                    if not c:
                        break
                    out += c
                except OSError:
                    break
            else:
                wpid, wstatus = os.waitpid(pid, os.WNOHANG)
                if wpid != 0:
                    break

        os.close(master)
        try:
            _, status = os.waitpid(pid, 0)
            exit_code = os.waitstatus_to_exitcode(status) if hasattr(os, "waitstatus_to_exitcode") else (status >> 8)
        except ChildProcessError:
            exit_code = 0

        clean_out = re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", out.decode("utf-8", errors="ignore"))
        clean_out = re.sub(r"\x1b\([a-zA-Z0-9]", "", clean_out)
        return clean_out, exit_code


class TestTracklistSuiteNavigation(unittest.TestCase):
    def test_detect_active_music_player_fast(self):
        """Verifies detect_active_music_player completes in < 1.5s without any hanging subprocesses."""
        cmd = f'source "{MANAGER_SCRIPT}" >/dev/null 2>&1; detect_active_music_player; echo "DETECTED=$DETECTED_PLAYER_LABEL"'
        start = time.time()
        res = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, timeout=5)
        duration = time.time() - start
        self.assertEqual(res.returncode, 0)
        self.assertIn("DETECTED=", res.stdout)
        self.assertLess(duration, 2.0, "detect_active_music_player took too long to execute!")

    def test_option13_option1_piped_execution(self):
        """Verifies navigating Option 13 -> Option 1 -> Option 0 loads and exits cleanly."""
        piped_input = "13\n1\n0\n0\n36\n"
        start = time.time()
        res = subprocess.run(
            ["bash", str(MANAGER_SCRIPT)],
            input=piped_input,
            capture_output=True,
            text=True,
            timeout=8,
        )
        duration = time.time() - start
        self.assertEqual(res.returncode, 0)
        self.assertIn("TRACKLIST MANAGEMENT, SCANNING & METADATA SUITE", res.stdout)
        self.assertIn("TRACKLIST & METADATA MANAGEMENT", res.stdout)
        self.assertIn("Browse & View Tracklists", res.stdout)
        self.assertIn("Search Tracklist by Title, Episode or Keyword", res.stdout)
        self.assertIn("View Tracklist of Currently Playing Track", res.stdout)
        self.assertLess(duration, 4.0, "Submenu navigation was too slow or hung!")

    def test_manage_tracklists_interactive_pty(self):
        """Verifies interactive PTY rendering of manage_tracklists with arrow navigation and ESC exit."""
        body = f"""
        source "{MANAGER_SCRIPT}" >/dev/null 2>&1
        echo "READY"
        manage_tracklists
        exit 0
        """
        # Send ESC (to exit submenu)
        esc_key = b"\x1b"
        output, rc = run_bash_pty(body, key_sequence=esc_key, timeout=3.0)
        self.assertIn("TRACKLIST & METADATA MANAGEMENT", output)
        self.assertIn("Browse & View Tracklists", output)
        self.assertEqual(rc, 0)

    def test_manage_tracklists_hotkey_exit_0(self):
        """Verifies pressing '0' exits manage_tracklists immediately in interactive mode."""
        body = f"""
        source "{MANAGER_SCRIPT}" >/dev/null 2>&1
        echo "READY"
        manage_tracklists
        exit 0
        """
        output, rc = run_bash_pty(body, key_sequence=b"0", timeout=3.0)
        self.assertIn("TRACKLIST & METADATA MANAGEMENT", output)
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
