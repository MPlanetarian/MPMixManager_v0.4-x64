import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


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


class TestManagerExitStopsAudioPlayer(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="mp_test_exit_audio_")
        self.config_dir = os.path.join(self.test_dir, ".config", "mix-manager")
        os.makedirs(self.config_dir, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_stop_mp_audio_daemon_cleans_up_state_and_processes(self):
        """Verify _stop_mp_audio_daemon properly removes runtime files and marks state as stopped."""
        pid_file = os.path.join(self.config_dir, "mp_player.pid")
        sock_file = os.path.join(self.config_dir, "mp_audio_player.sock")
        port_file = os.path.join(self.config_dir, "mp_audio_player.port")
        state_file = os.path.join(self.config_dir, "mp_player_state.json")

        with open(pid_file, "w") as f:
            f.write("9999999\n")
        with open(sock_file, "w") as f:
            f.write("")
        with open(port_file, "w") as f:
            f.write("65535\n")
        with open(state_file, "w") as f:
            f.write('{"running": true, "state": "playing"}')

        script = f"""
        HOME="{self.test_dir}"
        UNAME_S="$(uname -s)"
        _AUTOPLAY_PID=""
        eval "$(sed -n '/^_stop_mp_audio_daemon() {{/,/^}}/p' Mix_Archive_Manager.sh)"
        _stop_mp_audio_daemon
        """
        res = subprocess.run(
            [BASH_BIN, "-c", script],
            cwd=str(BASE_DIR),
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, f"Script failed: {res.stderr}")
        self.assertFalse(os.path.exists(pid_file), "pid_file should be deleted")
        self.assertFalse(os.path.exists(sock_file), "sock_file should be deleted")
        self.assertFalse(os.path.exists(port_file), "port_file should be deleted")
        self.assertTrue(os.path.exists(state_file), "state_file should exist")

        with open(state_file, "r") as f:
            data = json.load(f)
        self.assertFalse(data.get("running"), "state should reflect running=false")
        self.assertEqual(data.get("state"), "stopped")

    def test_exit_mix_manager_calls_stop_audio_daemon(self):
        """Verify exit_mix_manager invokes _stop_mp_audio_daemon."""
        script = f"""
        HOME="{self.test_dir}"
        UNAME_S="$(uname -s)"
        _STOP_CALLED=0
        _stop_mp_audio_daemon() {{ _STOP_CALLED=1; }}
        update_mp_bridge_menu() {{ :; }}
        _stop_win_cursor_hider() {{ :; }}
        eval "$(sed -n '/^_IN_EXIT_MIX_MANAGER=0/,/^}}/p' Mix_Archive_Manager.sh)"
        ( exit_mix_manager )
        """
        res = subprocess.run(
            [BASH_BIN, "-c", script],
            cwd=str(BASE_DIR),
            capture_output=True,
            text=True,
        )
        self.assertIn("You are exiting the MP Mix Archive Manager", res.stdout)

    def test_traps_installed_on_main_entrypoint(self):
        """Verify trap on EXIT INT TERM HUP is declared at main entrypoint of Mix_Archive_Manager.sh."""
        with open(BASE_DIR / "Mix_Archive_Manager.sh", "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("trap '_cleanup_mix_manager_exit' EXIT INT TERM HUP", content)
        self.assertIn("MANAGER_MAIN_PID=$BASHPID", content)
        self.assertIn("kill_all_mp_audio_players", content)

    def test_kill_all_mp_audio_players_terminates_multiple_instances(self):
        """Verify _stop_mp_audio_daemon / kill_all_mp_audio_players terminates all active player instances."""
        dummy_pids = []
        try:
            # Spawn two mock processes matching MP_Audio_Player pattern
            for _ in range(2):
                p = subprocess.Popen(
                    ["python3", "-c", "import sys, time; time.sleep(60)", "MP_Audio_Player_mock_test"],
                    cwd=str(BASE_DIR),
                )
                dummy_pids.append(p)

            # Ensure they are running
            for p in dummy_pids:
                self.assertIsNone(p.poll(), "Mock process should be running")

            script = f"""
            HOME="{self.test_dir}"
            UNAME_S="$(uname -s)"
            _AUTOPLAY_PID=""
            eval "$(sed -n '/^_stop_mp_audio_daemon() {{/,/^}}/p' Mix_Archive_Manager.sh)"
            _stop_mp_audio_daemon
            """
            res = subprocess.run(
                [BASH_BIN, "-c", script],
                cwd=str(BASE_DIR),
                capture_output=True,
                text=True,
            )
            self.assertEqual(res.returncode, 0, f"Script failed: {res.stderr}")

            # Verify mock processes have been terminated
            for p in dummy_pids:
                try:
                    p.wait(timeout=2.0)
                except subprocess.TimeoutExpired:
                    p.kill()
                    self.fail("Mock MP_Audio_Player process was not killed on exit")
        finally:
            for p in dummy_pids:
                if p.poll() is None:
                    p.kill()

    def test_stop_mp_audio_daemon_cleans_traktor_s4_midi_service(self):
        """Verify traktor_s4_midi.pid is cleaned up upon manager exit."""
        s4_pid_file = os.path.join(self.config_dir, "traktor_s4_midi.pid")
        with open(s4_pid_file, "w") as f:
            f.write("9999998\n")

        script = f"""
        HOME="{self.test_dir}"
        UNAME_S="$(uname -s)"
        _AUTOPLAY_PID=""
        eval "$(sed -n '/^_stop_mp_audio_daemon() {{/,/^}}/p' Mix_Archive_Manager.sh)"
        _stop_mp_audio_daemon
        """
        res = subprocess.run(
            [BASH_BIN, "-c", script],
            cwd=str(BASE_DIR),
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, f"Script failed: {res.stderr}")
        self.assertFalse(os.path.exists(s4_pid_file), "traktor_s4_midi.pid should be removed on exit")

    def test_exit_mix_manager_preserves_liquid_glass_player(self):
        """Verify exit_mix_manager does NOT terminate MP Liquid Glass Audio Player when open."""
        mock_proc = None
        try:
            # Spawn a mock Liquid Glass process
            mock_proc = subprocess.Popen(
                ["python3", "-c", "import sys, time; time.sleep(60)", "MP_Audio_Player_Liquid_Glass_Mock"],
                cwd=str(BASE_DIR),
            )
            self.assertIsNone(mock_proc.poll(), "Mock Liquid Glass should be running")

            script = f"""
            HOME="{self.test_dir}"
            UNAME_S="$(uname -s)"
            _STOP_CALLED=0
            _stop_mp_audio_daemon() {{ _STOP_CALLED=1; }}
            kill_all_mp_audio_players() {{ _STOP_CALLED=1; }}
            update_mp_bridge_menu() {{ :; }}
            _stop_win_cursor_hider() {{ :; }}
            eval "$(sed -n '/^is_liquid_glass_open() {{/,/^}}/p' Mix_Archive_Manager.sh)"
            eval "$(sed -n '/^is_liquid_glass_pid() {{/,/^}}/p' Mix_Archive_Manager.sh)"
            eval "$(sed -n '/^_IN_EXIT_MIX_MANAGER=0/,/^}}/p' Mix_Archive_Manager.sh)"
            ( exit_mix_manager )
            echo "STOP_CALLED=$_STOP_CALLED"
            """
            res = subprocess.run(
                [BASH_BIN, "-c", script],
                cwd=str(BASE_DIR),
                capture_output=True,
                text=True,
            )
            self.assertEqual(res.returncode, 0, f"Script failed: {res.stderr}")
            self.assertIn("MP Liquid Glass Audio Player is open — leaving playback active", res.stdout)
            self.assertIn("STOP_CALLED=0", res.stdout)
            # Verify the mock Liquid Glass process is still alive and was NOT terminated
            self.assertIsNone(mock_proc.poll(), "Liquid Glass process should remain alive upon manager exit")
        finally:
            if mock_proc and mock_proc.poll() is None:
                mock_proc.kill()
                mock_proc.wait()

    def test_stop_mp_audio_daemon_skips_when_liquid_glass_open(self):
        """Verify _stop_mp_audio_daemon returns immediately without touching state when Liquid Glass is open."""
        mock_proc = None
        try:
            mock_proc = subprocess.Popen(
                ["python3", "-c", "import sys, time; time.sleep(60)", "MP_Audio_Player_Liquid_Glass_Mock2"],
                cwd=str(BASE_DIR),
            )
            state_file = os.path.join(self.config_dir, "mp_player_state.json")
            with open(state_file, "w") as f:
                f.write('{"running": true, "state": "playing"}')

            script = f"""
            HOME="{self.test_dir}"
            UNAME_S="$(uname -s)"
            _AUTOPLAY_PID=""
            eval "$(sed -n '/^is_liquid_glass_open() {{/,/^}}/p' Mix_Archive_Manager.sh)"
            eval "$(sed -n '/^_stop_mp_audio_daemon() {{/,/^}}/p' Mix_Archive_Manager.sh)"
            _stop_mp_audio_daemon
            """
            res = subprocess.run(
                [BASH_BIN, "-c", script],
                cwd=str(BASE_DIR),
                capture_output=True,
                text=True,
            )
            self.assertEqual(res.returncode, 0, f"Script failed: {res.stderr}")
            # State file should still be intact and playing!
            with open(state_file, "r") as f:
                data = json.load(f)
            self.assertTrue(data.get("running"))
            self.assertEqual(data.get("state"), "playing")
        finally:
            if mock_proc and mock_proc.poll() is None:
                mock_proc.kill()
                mock_proc.wait()


if __name__ == "__main__":
    unittest.main()
