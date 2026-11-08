import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SCRIPT_PATH = BASE_DIR / "scripts" / "kill_all_mp_audio_players.sh"
DESKTOP_PATH = BASE_DIR / "desktop" / "Kill_All_MP_Audio_Players.desktop"


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


class TestKillAllMPAudioPlayers(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="mp_test_kill_players_")
        self.config_dir = os.path.join(self.test_dir, ".config", "mix-manager")
        os.makedirs(self.config_dir, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_script_and_desktop_file_exist_and_executable(self):
        self.assertTrue(SCRIPT_PATH.is_file(), f"Script not found at {SCRIPT_PATH}")
        self.assertTrue(os.access(SCRIPT_PATH, os.X_OK), "Script is not executable")
        self.assertTrue(DESKTOP_PATH.is_file(), f"Desktop file not found at {DESKTOP_PATH}")

    def test_desktop_file_contents(self):
        content = DESKTOP_PATH.read_text(encoding="utf-8")
        self.assertIn("[Desktop Entry]", content)
        self.assertIn("Name=Kill All MP Audio Players", content)
        self.assertIn("kill_all_mp_audio_players.sh", content)
        self.assertIn("Icon=media-playback-stop", content)

    def test_kill_script_terminates_mock_processes_and_cleans_files(self):
        pid_file = os.path.join(self.config_dir, "mp_player.pid")
        sock_file = os.path.join(self.config_dir, "mp_audio_player.sock")
        port_file = os.path.join(self.config_dir, "mp_audio_player.port")
        state_file = os.path.join(self.config_dir, "mp_player_state.json")

        with open(sock_file, "w") as f:
            f.write("")
        with open(port_file, "w") as f:
            f.write("65535\n")
        with open(state_file, "w") as f:
            f.write('{"running": true, "state": "playing"}')

        # Spawn a mock process matching MP_Audio_Player pattern
        mock_proc = subprocess.Popen(
            ["python3", "-c", "import time; time.sleep(60)", "MP_Audio_Player_unit_test"],
            cwd=str(BASE_DIR),
        )
        try:
            with open(pid_file, "w") as f:
                f.write(f"{mock_proc.pid}\n")

            env = dict(os.environ)
            env["HOME"] = self.test_dir

            res = subprocess.run(
                [BASH_BIN, str(SCRIPT_PATH), "--quiet"],
                cwd=str(BASE_DIR),
                capture_output=True,
                text=True,
                env=env,
            )
            self.assertEqual(res.returncode, 0, f"Script failed: {res.stderr}")

            # Verify mock process was killed
            try:
                mock_proc.wait(timeout=3.0)
            except subprocess.TimeoutExpired:
                mock_proc.kill()
                self.fail("Mock MP_Audio_Player process was not killed by kill_all_mp_audio_players.sh")

            # Verify files removed
            self.assertFalse(os.path.exists(pid_file), "PID file was not removed")
            self.assertFalse(os.path.exists(sock_file), "Socket file was not removed")
            self.assertFalse(os.path.exists(port_file), "Port file was not removed")

            # Verify state file updated to stopped
            with open(state_file, "r", encoding="utf-8") as f:
                state = json.load(f)
            self.assertFalse(state.get("running"), "State 'running' should be False")
            self.assertEqual(state.get("state"), "stopped", "State should be 'stopped'")
        finally:
            if mock_proc.poll() is None:
                mock_proc.kill()


if __name__ == "__main__":
    unittest.main()
