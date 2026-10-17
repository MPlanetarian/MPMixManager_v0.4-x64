#!/usr/bin/env python3
"""
Unit and integration tests for Option 2 Submenus in Mix_Archive_Manager.sh and Make_SOF_FLAC_CONVERSION.sh.
Verifies keyboard navigation (Up/Down arrow keys + Enter to activate), direct hotkeys, and non-interactive fallback.
"""

import os
import pty
import re
import select
import subprocess
import time
import unittest

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONVERSION_SCRIPT = os.path.join(REPO_DIR, "Make_SOF_FLAC_CONVERSION.sh")
MANAGER_SCRIPT = os.path.join(REPO_DIR, "Mix_Archive_Manager.sh")


def run_bash_pty(script_body: str, key_sequence = None, timeout: float = 3.0) -> tuple[str, int]:
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
        os.environ["LINES"] = "30"
        os.environ["COLUMNS"] = "100"
        os.execlp("bash", "bash", "-c", script_body)
    else:
        os.close(slave)
        out = b""
        start_t = time.time()
        # Wait until child signals READY or initial output
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

        time.sleep(0.08)
        if key_sequence:
            if isinstance(key_sequence, (bytes, str)):
                if isinstance(key_sequence, str):
                    key_sequence = key_sequence.encode("utf-8")
                tokens = re.findall(rb"\x1b(?:\[[A-Z0-9~]+|O[A-Z])|.", key_sequence, re.DOTALL)
                for tok in tokens:
                    os.write(master, tok)
                    time.sleep(0.06)
            elif isinstance(key_sequence, list):
                for tok in key_sequence:
                    if isinstance(tok, str):
                        tok = tok.encode("utf-8")
                    os.write(master, tok)
                    time.sleep(0.06)

        while time.time() - start_t < timeout:
            r, _, _ = select.select([master], [], [], 0.2)
            if not r:
                break
            try:
                chunk = os.read(master, 1024)
                if not chunk:
                    break
                out += chunk
            except OSError:
                break
        try:
            _, status = os.waitpid(pid, os.WNOHANG)
            exit_code = os.waitstatus_to_exitcode(status) if status else 0
        except ChildProcessError:
            exit_code = 0
        try:
            os.close(master)
        except OSError:
            pass
        return out.decode("utf-8", "replace"), exit_code


class TestOption2Submenus(unittest.TestCase):
    def test_syntax_check(self):
        """Verify bash syntax check passes for both scripts."""
        for path in [CONVERSION_SCRIPT, MANAGER_SCRIPT, os.path.join(REPO_DIR, "scripts", "Make_SOF_FLAC_CONVERSION.sh")]:
            res = subprocess.run(["bash", "-n", path], capture_output=True, text=True)
            self.assertEqual(res.returncode, 0, f"Syntax error in {path}: {res.stderr}")

    def test_manage_mix_conversion_defined_in_manager(self):
        """Verify manage_mix_conversion function is defined in Mix_Archive_Manager.sh."""
        with open(MANAGER_SCRIPT, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("manage_mix_conversion()", content)
        self.assertIn("STREAM OF FREQUENCY — RUN MIX CONVERSION SUITE", content)
        self.assertIn("manage_mix_conversion ;;", content)

    def test_select_menu_option_non_interactive_fallback(self):
        """Verify select_menu_option returns default key when non-interactive (no TTY)."""
        cmd = f"""
        source "{CONVERSION_SCRIPT}" || true
        items=("flac|FLAC lossless|(Default)" "mp3|MP3 320 kbps|" "0|Cancel|")
        res=""
        select_menu_option "TEST" "Subtitle" items 0 res
        echo "RESULT:$res"
        """
        # Run with stdin=DEVNULL to ensure [ -t 0 ] is false
        res = subprocess.run(["bash", "-c", cmd], stdin=subprocess.DEVNULL, capture_output=True, text=True, cwd=REPO_DIR)
        self.assertIn("RESULT:flac", res.stdout)

    def test_select_menu_option_interactive_enter_default(self):
        """Verify pressing Enter immediately selects the default highlighted option."""
        cmd = f"""
        source "{CONVERSION_SCRIPT}" || true
        items=("flac|FLAC lossless|(Default)" "mp3|MP3 320 kbps|" "0|Cancel|")
        echo "READY"
        res=""
        select_menu_option "OUTPUT FORMAT" "Choose output" items 0 res
        echo "CHOSEN:$res"
        """
        out, _ = run_bash_pty(cmd, key_sequence=b"\n")
        self.assertIn("CHOSEN:flac", out)

    def test_select_menu_option_interactive_down_arrow_select(self):
        """Verify navigating with Down arrow key and pressing Enter selects the second option."""
        cmd = f"""
        source "{CONVERSION_SCRIPT}" || true
        items=("flac|FLAC lossless|(Default)" "mp3|MP3 320 kbps|" "wav|WAV 24-bit|" "0|Cancel|")
        echo "READY"
        res=""
        select_menu_option "OUTPUT FORMAT" "Choose output" items 0 res
        echo "CHOSEN:$res"
        """
        out, _ = run_bash_pty(cmd, key_sequence=[b"\x1b[B", b"\n"])
        self.assertIn("CHOSEN:mp3", out)

    def test_select_menu_option_interactive_up_arrow_wrap(self):
        """Verify navigating with Up arrow wraps to the last option (Cancel)."""
        cmd = f"""
        source "{CONVERSION_SCRIPT}" || true
        items=("flac|FLAC lossless|(Default)" "mp3|MP3 320 kbps|" "wav|WAV 24-bit|" "0|Cancel|")
        echo "READY"
        res=""
        select_menu_option "OUTPUT FORMAT" "Choose output" items 0 res
        echo "CHOSEN:$res"
        """
        out, _ = run_bash_pty(cmd, key_sequence=[b"\x1b[A", b"\n"])
        self.assertIn("CHOSEN:0", out)

    def test_select_menu_option_interactive_direct_hotkey(self):
        """Verify pressing a numeric key directly selects that option."""
        cmd = f"""
        source "{CONVERSION_SCRIPT}" || true
        items=("flac|FLAC lossless|(Default)" "mp3|MP3 320 kbps|" "wav|WAV 24-bit|" "0|Cancel|")
        echo "READY"
        res=""
        select_menu_option "OUTPUT FORMAT" "Choose output" items 0 res
        echo "CHOSEN:$res"
        """
        out, _ = run_bash_pty(cmd, key_sequence=b"3")
        self.assertIn("CHOSEN:wav", out)

    def test_choose_conversion_output_interactive_arrow_navigation(self):
        """Verify choose_conversion_output navigates via Down arrow to select MP4 YouTube Video."""
        cmd = f"""
        export MIX_ARCHIVE_DIR="{REPO_DIR}"
        source "{CONVERSION_SCRIPT}" || true
        echo "READY"
        choose_conversion_output
        echo "OUTPUT_FORMAT:$OUTPUT_FORMAT"
        """
        # Down 3 times (FLAC -> MP3 -> WAV -> MP4), then Enter
        out, _ = run_bash_pty(cmd, key_sequence=[b"\x1b[B", b"\x1b[B", b"\x1b[B", b"\n"])
        self.assertIn("OUTPUT_FORMAT:mp4", out)

    def test_review_converted_tracklist_interactive_continue(self):
        """Verify review_converted_tracklist continues when selecting option 0."""
        cmd = f"""
        export MIX_ARCHIVE_DIR="{REPO_DIR}"
        source "{CONVERSION_SCRIPT}" || true
        tracklist_found=false
        tracklist_path="/tmp/test_sof_tracklist.txt"
        echo "Placeholder" > "$tracklist_path"
        echo "READY"
        review_converted_tracklist
        echo "FINISHED_REVIEW"
        rm -f "$tracklist_path"
        """
        # Down 2 times (1: Generate -> 2: Update -> 0: Continue), then Enter
        out, _ = run_bash_pty(cmd, key_sequence=[b"\x1b[B", b"\x1b[B", b"\n"])
        self.assertIn("FINISHED_REVIEW", out)

    def test_post_conversion_tasks_interactive_skip(self):
        """Verify post_conversion_tasks skips video and Audacity on default Enter."""
        cmd = f"""
        export MIX_ARCHIVE_DIR="{REPO_DIR}"
        source "{CONVERSION_SCRIPT}" || true
        newly_exported_flacs=("/tmp/fake_mix.flac")
        touch "/tmp/fake_mix.flac"
        echo "READY"
        post_conversion_tasks
        echo "FINISHED_POST_TASKS"
        rm -f "/tmp/fake_mix.flac"
        """
        # Press Enter for video prompt (default: skip), then Enter for Audacity (default: skip)
        out, _ = run_bash_pty(cmd, key_sequence=[b"\n", b"\n"])
        self.assertIn("FINISHED_POST_TASKS", out)


if __name__ == "__main__":
    unittest.main()
