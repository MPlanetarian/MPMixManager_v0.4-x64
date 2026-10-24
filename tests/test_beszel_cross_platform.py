import os
import shutil
import subprocess
import unittest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SCRIPT_PATH = BASE_DIR / "scripts" / "beszel.sh"
ROOT_SCRIPT_PATH = BASE_DIR / "beszel.sh"


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


class TestBeszelCrossPlatform(unittest.TestCase):
    def test_scripts_exist_and_executable(self):
        self.assertTrue(SCRIPT_PATH.is_file(), f"Script not found at {SCRIPT_PATH}")
        self.assertTrue(os.access(SCRIPT_PATH, os.X_OK), "scripts/beszel.sh is not executable")
        self.assertTrue(ROOT_SCRIPT_PATH.is_file(), f"Root script not found at {ROOT_SCRIPT_PATH}")
        self.assertTrue(os.access(ROOT_SCRIPT_PATH, os.X_OK), "beszel.sh is not executable")

    def test_status_command(self):
        res = subprocess.run(
            [BASH_BIN, str(SCRIPT_PATH), "status"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("BESZEL MONITORING SUITE STATUS", res.stdout)
        self.assertIn("Beszel Hub:", res.stdout)
        self.assertIn("Beszel Agent:", res.stdout)

    def test_linux_execution_does_not_call_powershell(self):
        env = os.environ.copy()
        env["OS_TYPE"] = "linux"
        # Run start-hub with mock environment where podman isn't run or is simulated
        res = subprocess.run(
            [BASH_BIN, str(SCRIPT_PATH), "status"],
            capture_output=True,
            text=True,
            env=env,
            timeout=10,
        )
        self.assertEqual(res.returncode, 0)
        self.assertNotIn("powershell.exe: command not found", res.stderr)
        self.assertNotIn("powershell.exe: command not found", res.stdout)

    def test_windows_conditional_code_detection(self):
        content = SCRIPT_PATH.read_text(encoding="utf-8")
        # Ensure OS_TYPE check exists
        self.assertIn('OS_TYPE="linux"', content)
        self.assertIn('CYGWIN*|MINGW*|MSYS*) OS_TYPE="windows"', content)
        # Ensure powershell.exe is guarded by OS_TYPE = "windows"
        self.assertIn('if [ "$OS_TYPE" = "windows" ]; then', content)
        self.assertIn("start_hub_linux", content)
        self.assertIn("start_hub_windows", content)
        self.assertIn("start_agent_linux", content)
        self.assertIn("start_agent_windows", content)


if __name__ == "__main__":
    unittest.main()
