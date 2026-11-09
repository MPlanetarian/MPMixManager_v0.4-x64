#!/usr/bin/env python3
"""Option 1 must launch a real Python, not the Windows Store alias."""

import os
import shutil
import stat
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
RESOLVER = BASE_DIR / "scripts" / "resolve_mp_python.sh"
MANAGER = BASE_DIR / "Mix_Archive_Manager.sh"


def find_bash():
    for cand in [
        os.environ.get("ProgramFiles", "") + r"\Git\bin\bash.exe",
        os.environ.get("ProgramFiles(x86)", "") + r"\Git\bin\bash.exe",
        os.environ.get("LOCALAPPDATA", "") + r"\Programs\Git\bin\bash.exe",
        r"C:\msys64\usr\bin\bash.exe",
    ]:
        if cand and os.path.isfile(cand):
            return cand
    found = shutil.which("bash")
    if found and "WindowsApps" not in found:
        return found
    return "bash"


BASH_BIN = find_bash()


def _bash(script, env=None, cwd=None):
    merged = os.environ.copy()
    merged.pop("MP_PYTHON", None)
    merged.pop("MP_PYTHON_CANDIDATES", None)
    if env:
        merged.update(env)
    return subprocess.run(
        [BASH_BIN, "--noprofile", "--norc", "-c", script],
        cwd=str(cwd or BASE_DIR),
        capture_output=True,
        text=True,
        env=merged,
    )


class ResolveMpPythonTests(unittest.TestCase):
    def test_manager_uses_resolver_for_play_dj(self):
        text = MANAGER.read_text(encoding="utf-8", errors="replace")
        self.assertIn('source "$SCRIPT_DIR/scripts/resolve_mp_python.sh"', text)
        self.assertIn('py_bin="$(mp_python_bin)"', text)
        self.assertIn('bin="$(mp_python_bin)"', text)
        self.assertNotIn('python3() { py -3 "$@"; }', text)

    def test_skips_store_alias_and_uses_real_interpreter(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stub_dir = root / "WindowsApps"
            stub_dir.mkdir()
            real = root / "real-python"
            real.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            real.chmod(real.stat().st_mode | stat.S_IEXEC)
            stub = stub_dir / "python3"
            stub.write_text("#!/bin/sh\necho 'Python was not found' >&2\nexit 1\n", encoding="utf-8")
            stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
            script = textwrap.dedent(f"""
                export PATH="{stub_dir.as_posix()}:$PATH"
                export SCRIPT_DIR="{root.as_posix()}"
                export MP_PYTHON_CANDIDATES="{real.as_posix()}"
                source "{RESOLVER.as_posix()}"
                resolved="$(resolve_mp_python)"
                printf '%s\\n' "$resolved"
                env -u LINES -u COLUMNS "$resolved" -c 'import sys' >/dev/null
                printf 'env:%s\\n' "$?"
            """)
            res = _bash(script)
        self.assertEqual(res.returncode, 0, res.stderr)
        lines = [line.strip() for line in res.stdout.splitlines() if line.strip()]
        self.assertEqual(lines[0].replace("\\", "/"), real.as_posix())
        self.assertEqual(lines[1], "env:0")

    def test_env_launch_rewrites_bare_python3(self):
        text = MANAGER.read_text(encoding="utf-8", errors="replace")
        start = text.index("_run_mp_audio_player() {")
        end = text.index("\n}", start)
        body = text[start:end + 2]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            real = root / "real-python"
            real.write_text(
                "#!/bin/sh\nprintf '%s\\n' \"$*\" > \"$MP_LAUNCH_LOG\"\nexit 0\n",
                encoding="utf-8",
            )
            real.chmod(real.stat().st_mode | stat.S_IEXEC)
            log = root / "launch.log"
            script = textwrap.dedent(f"""
                export MP_PYTHON="{real.as_posix()}"
                export MP_LAUNCH_LOG="{log.as_posix()}"
                {body}
                mp_python_bin() {{ printf '%s\\n' "$MP_PYTHON"; }}
                _run_mp_audio_player python3 "{(root / 'MP_Audio_Player.py').as_posix()}" --interactive
            """)
            res = _bash(script)
            self.assertEqual(res.returncode, 0, res.stderr)
            logged = log.read_text(encoding="utf-8")
            self.assertIn("--interactive", logged)
            self.assertIn("MP_Audio_Player.py", logged)


if __name__ == "__main__":
    unittest.main()
