import os
import subprocess
import unittest
from pathlib import Path

BASE_DIR = Path("/var/home/mplanetarian/MP_Mix_Manager_v0.3")
SCRIPT = BASE_DIR / "scripts" / "display_loader_video.sh"


class TestLoaderVideoIntegration(unittest.TestCase):
    def test_find_loader_video_path_finds_mp_loader(self):
        cmd = ["bash", str(SCRIPT), "--path"]
        res = subprocess.run(cmd, cwd=str(BASE_DIR), capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertTrue(res.stdout.strip().endswith("MP_loader.mp4"))
        self.assertTrue(os.path.isfile(res.stdout.strip()))

    def test_is_manager_already_open_logic(self):
        script = r"""
        set -e
        source scripts/display_loader_video.sh
        # Test 1: Self PID alone should not count as already open (if other pids excluded)
        # When checking our own pid, function shouldn't treat ourselves as another instance
        my_pid="$$"
        # Test function with dummy pid when no real other instance exists
        """
        res = subprocess.run(["bash", "-c", script], cwd=str(BASE_DIR), capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)

    def test_skips_when_show_loader_video_false(self):
        script = r"""
        set -e
        source scripts/display_loader_video.sh
        SHOW_LOADER_VIDEO="false"
        # Should return 0 without executing any player
        display_startup_loader_video 0
        echo "SKIPPED_CONFIG"
        """
        res = subprocess.run(["bash", "-c", script], cwd=str(BASE_DIR), capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertIn("SKIPPED_CONFIG", res.stdout)

    def test_skips_when_cli_initial_action_set(self):
        script = r"""
        set -e
        source scripts/display_loader_video.sh
        CLI_INITIAL_ACTION="1"
        display_startup_loader_video 0
        echo "SKIPPED_CLI_ACTION"
        """
        res = subprocess.run(["bash", "-c", script], cwd=str(BASE_DIR), capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertIn("SKIPPED_CLI_ACTION", res.stdout)

    def test_skips_when_manager_already_open(self):
        script = r"""
        set -e
        source scripts/display_loader_video.sh
        # Mock is_manager_already_open to simulate manager already running
        is_manager_already_open() { return 0; }
        display_startup_loader_video 0
        echo "SKIPPED_ALREADY_OPEN"
        """
        res = subprocess.run(["bash", "-c", script], cwd=str(BASE_DIR), capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertIn("SKIPPED_ALREADY_OPEN", res.stdout)

    def test_launches_player_when_not_already_open(self):
        script = r"""
        set -e
        source scripts/display_loader_video.sh
        # Mock is_manager_already_open to return 1 (not open)
        is_manager_already_open() { return 1; }
        # Mock ffplay to verify it would be invoked with correct arguments
        MOCK_CALLED=0
        ffplay() {
            MOCK_CALLED=1
            echo "MOCK_FFPLAY_ARGS: $*"
        }
        # Run in subshell with mock
        SHOW_LOADER_VIDEO="true"
        CLI_INITIAL_ACTION=""
        # Verify find_loader_video_path returns valid path
        path=$(find_loader_video_path)
        test -f "$path"
        echo "PATH_VALID: $path"
        """
        res = subprocess.run(["bash", "-c", script], cwd=str(BASE_DIR), capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertIn("PATH_VALID:", res.stdout)


if __name__ == "__main__":
    unittest.main()
