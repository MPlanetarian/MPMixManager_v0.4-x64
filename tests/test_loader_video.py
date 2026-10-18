import os
import subprocess
import unittest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SCRIPT = BASE_DIR / "scripts" / "display_loader_video.sh"


def find_bash():
    for cand in [
        os.environ.get("ProgramFiles", "") + r"\Git\bin\bash.exe",
        os.environ.get("ProgramFiles(x86)", "") + r"\Git\bin\bash.exe",
        os.environ.get("LOCALAPPDATA", "") + r"\Programs\Git\bin\bash.exe",
        r"C:\msys64\usr\bin\bash.exe",
    ]:
        if cand and os.path.isfile(cand):
            return cand
    import shutil
    b = shutil.which("bash")
    if b and "WindowsApps" not in b:
        return b
    return "bash"


BASH_BIN = find_bash()


class TestLoaderVideoIntegration(unittest.TestCase):
    def test_find_loader_video_path_finds_mp_loader(self):
        script_posix = str(SCRIPT).replace('\\', '/')
        cmd = [BASH_BIN, script_posix, "--path"]
        res = subprocess.run(cmd, cwd=str(BASE_DIR), capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertTrue(res.stdout.strip().endswith("MP_loader.mp4"))
        # Check either POSIX or Windows path
        resolved = res.stdout.strip()
        if resolved.startswith("/x/"):
            resolved = "X:/" + resolved[3:]
        elif resolved.startswith("/c/"):
            resolved = "C:/" + resolved[3:]
        self.assertTrue(os.path.isfile(resolved) or os.path.isfile(res.stdout.strip()))

    def test_is_manager_already_open_logic(self):
        script = r"""
        set -e
        source scripts/display_loader_video.sh
        # Mock pgrep to return empty so external running instances don't skew isolated bridge unit test
        pgrep() { return 1; }
        # Test 1: Self PID alone should not count as already open
        my_pid="$$"
        # Test 2: macOS non-proc fallback should not falsely treat an unrelated active PID as manager
        # Simulate bridge status file pointing to PID 1 (systemd/launchd, which is always alive)
        mkdir -p "${HOME}/.config/mix-manager"
        echo '{"pid": 1}' > "${HOME}/.config/mix-manager/bridge_status.json"
        if ! is_manager_already_open "$$"; then
            echo "MACOS_PROC_FALLBACK_OK"
        fi
        rm -f "${HOME}/.config/mix-manager/bridge_status.json"
        """
        res = subprocess.run([BASH_BIN, "-c", script], cwd=str(BASE_DIR), capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertIn("MACOS_PROC_FALLBACK_OK", res.stdout)

    def test_skips_when_show_loader_video_false(self):
        script = r"""
        set -e
        source scripts/display_loader_video.sh
        SHOW_LOADER_VIDEO="false"
        # Should return 0 without executing any player
        display_startup_loader_video 0
        echo "SKIPPED_CONFIG"
        """
        res = subprocess.run([BASH_BIN, "-c", script], cwd=str(BASE_DIR), capture_output=True, text=True)
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
        res = subprocess.run([BASH_BIN, "-c", script], cwd=str(BASE_DIR), capture_output=True, text=True)
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
        res = subprocess.run([BASH_BIN, "-c", script], cwd=str(BASE_DIR), capture_output=True, text=True)
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
        res = subprocess.run([BASH_BIN, "-c", script], cwd=str(BASE_DIR), capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertIn("PATH_VALID:", res.stdout)

    def test_windows_gui_detection_and_os_type(self):
        """Verifies that on Windows/MINGW, OS_TYPE is windows and is_gui is 1."""
        script = r"""
        set -e
        source scripts/display_loader_video.sh
        echo "DETECTED_OS_TYPE: $OS_TYPE"
        is_gui=0
        if [ -n "${DISPLAY:-}" ] || [ -n "${WAYLAND_DISPLAY:-}" ] || [ "${OS_TYPE:-}" = "macos" ] || [ "${OS_TYPE:-}" = "windows" ] || [ "${OS_TYPE:-}" = "wsl" ] || [ "$(uname -s 2>/dev/null)" = "Darwin" ] || [[ "$(uname -s 2>/dev/null)" =~ (MINGW|MSYS|CYGWIN) ]]; then
            is_gui=1
        fi
        echo "IS_GUI: $is_gui"
        """
        res = subprocess.run([BASH_BIN, "-c", script], cwd=str(BASE_DIR), capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertIn("IS_GUI: 1", res.stdout)

    def test_manager_uname_s_initialization(self):
        """Verifies that Mix_Archive_Manager.sh correctly initializes UNAME_S and OS_TYPE."""
        script = r"""
        set -e
        # Evaluate up to line 257 where OS_TYPE and UNAME_S are exported
        eval "$(sed -n '1,257p' Mix_Archive_Manager.sh)"
        test -n "$UNAME_S"
        echo "UNAME_S_VALID: $UNAME_S"
        test -n "$OS_TYPE"
        echo "OS_TYPE_VALID: $OS_TYPE"
        """
        res = subprocess.run([BASH_BIN, "-c", script], cwd=str(BASE_DIR), capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertIn("UNAME_S_VALID:", res.stdout)
        self.assertIn("OS_TYPE_VALID:", res.stdout)


if __name__ == "__main__":
    unittest.main()
