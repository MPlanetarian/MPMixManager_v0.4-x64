#!/usr/bin/env python3
"""B in Mix Manager opens a Bash prompt in the same terminal. B at that prompt returns."""

import os
import pty
import select
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANAGER = ROOT / "Mix_Archive_Manager.sh"


def _function_source() -> str:
    text = MANAGER.read_text(encoding="utf-8")
    start = text.index("enter_manager_bash_terminal() {")
    end = text.index("\nrun_interactive_submenu() {", start)
    return text[start:end]


def _pty_session(script: str, steps, timeout=8.0):
    """Run script on a pty. steps is a list of (wait_for, send) byte pairs."""
    pid, master = pty.fork()
    if pid == 0:
        os.environ["MP_MANAGER_BASH_NORC"] = "1"
        os.environ["TERM"] = "xterm-256color"
        os.execvp("bash", ["bash", "--noprofile", "--norc", "-c", script])
    buf = b""
    child_done = False

    def read_until(needle: bytes, limit: float) -> bool:
        nonlocal buf, child_done
        end = time.time() + limit
        while time.time() < end:
            if needle in buf:
                return True
            if child_done and not select.select([master], [], [], 0)[0]:
                return needle in buf
            ready, _, _ = select.select([master], [], [], 0.1)
            if ready:
                try:
                    chunk = os.read(master, 4096)
                except OSError:
                    child_done = True
                    break
                if not chunk:
                    child_done = True
                    break
                buf += chunk
            else:
                waited, _ = os.waitpid(pid, os.WNOHANG)
                if waited:
                    child_done = True
        return needle in buf

    ok = True
    try:
        for needle, payload in steps:
            if needle and not read_until(needle, timeout):
                ok = False
                break
            if payload:
                os.write(master, payload)
        if ok:
            ok = read_until(b"RETURNED", timeout)
        status = 1
        if not child_done:
            _, status = os.waitpid(pid, 0)
        else:
            _, status = os.waitpid(pid, os.WNOHANG)
        code = os.waitstatus_to_exitcode(status) if status else 0
    finally:
        os.close(master)
    return ok, code, buf.decode("utf-8", "replace")


class TestManagerBashToggle(unittest.TestCase):
    def test_menu_hooks_b_to_the_shell(self):
        text = MANAGER.read_text(encoding="utf-8")
        self.assertIn("enter_manager_bash_terminal() {", text)
        self.assertIn(
            'if [ -z "$typed_buffer" ] && { [ "$ch" = "b" ] || [ "$ch" = "B" ]; }; then',
            text,
        )
        self.assertIn("enter_manager_bash_terminal; typed_buffer=\"\"", text)
        self.assertIn("[B] Bash, [C] Theme", text)
        self.assertIn("[B] Bash, [Esc] to return", text)
        self.assertNotIn('typed_buffer" = "b"', text)
        self.assertIn("_nav_just_arrowed; then continue; fi; if [ -z \"$typed_buffer\" ]", text)

    def test_b_on_empty_prompt_returns_to_the_manager(self):
        script = _function_source() + "\nenter_manager_bash_terminal\nprintf 'RETURNED\\n' >/dev/tty\n"
        ok, code, out = _pty_session(script, [(b"press B to return to MP Manager", b"B")])
        self.assertTrue(ok, out)
        self.assertEqual(code, 0, out)
        self.assertIn("RETURNED", out)

    def test_b_inside_a_command_is_typed(self):
        script = _function_source() + "\nenter_manager_bash_terminal\nprintf 'RETURNED\\n' >/dev/tty\n"
        ok, code, out = _pty_session(
            script,
            [
                (b"press B to return to MP Manager", b"echo ecBho\n"),
                (b"ecBho", b"B"),
            ],
        )
        self.assertTrue(ok, out)
        self.assertEqual(code, 0, out)
        self.assertIn("ecBho", out)
        self.assertIn("RETURNED", out)

    def test_g_on_empty_prompt_opens_mp_gui_and_stays(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            stub = tmp_path / "MP_Gui.sh"
            marker = tmp_path / "launched"
            stub.write_text(
                "#!/bin/bash\nprintf 'GUI_LAUNCHED\\n' >> \"${MP_GUI_STUB_OUT}\"\n",
                encoding="utf-8",
            )
            script = (
                f"export SCRIPT_DIR={str(tmp_path)!r}\n"
                f"export MP_GUI_STUB_OUT={str(marker)!r}\n"
                + _function_source()
                + "\nenter_manager_bash_terminal\nprintf 'RETURNED\\n' >/dev/tty\n"
            )
            ok, code, out = _pty_session(
                script,
                [
                    (b"press B to return to MP Manager", b"G"),
                    (b"Opened MP Gui", b"B"),
                ],
            )
            self.assertTrue(ok, out)
            self.assertEqual(code, 0, out)
            self.assertIn("RETURNED", out)
            self.assertIn("Opened MP Gui", out)
            deadline = time.time() + 2
            text = ""
            while time.time() < deadline:
                if marker.exists():
                    text = marker.read_text(encoding="utf-8")
                    if "GUI_LAUNCHED" in text:
                        break
                time.sleep(0.05)
            self.assertIn("GUI_LAUNCHED", text)


if __name__ == "__main__":
    unittest.main()
