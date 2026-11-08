import os
import shutil
import subprocess
import unittest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
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


def run_bash(script: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [BASH_BIN, "-c", script],
        cwd=str(BASE_DIR),
        capture_output=True,
        text=True,
        check=True,
    )


class TestNoAutomaticTracklist(unittest.TestCase):
    def test_manager_source_has_no_automatic_tracklist_open(self):
        text = MANAGER.read_text(encoding="utf-8")
        self.assertEqual(text.count("open_tracklist_window("), 1)
        self.assertNotIn('open_tracklist_window "$found_tl"', text)
        self.assertNotIn("Auto-Show Tracklist on Boot", text)
        self.assertNotIn("Toggle Auto-Show Tracklist on Startup", text)
        self.assertIn(
            'AUTO_SHOW_TRACKLIST_ON_STARTUP="${AUTO_SHOW_TRACKLIST_ON_STARTUP:-false}"',
            text,
        )

    def test_startup_autoplay_does_not_open_tracklist_even_when_flag_is_true(self):
        script = r"""
        set -e
        eval "$(sed -n '/^execute_startup_autoplay() {/,/^}/p' Mix_Archive_Manager.sh)"
        AUTO_PLAY_ON_STARTUP="true"
        AUTO_SHOW_COVER_ON_STARTUP="false"
        AUTO_SHOW_TRACKLIST_ON_STARTUP="true"
        AUTO_PLAY_YOUTUBE_ON_STARTUP="false"
        DEFAULT_AUDIO_PLAYER="mp_audio_player"
        PLAY_CALLED=0
        TL_OPENED=0
        FIND_TL=0
        tmp_mix=$(mktemp /tmp/test_startup_mix_XXXXXX.flac)
        echo "audio" > "$tmp_mix"
        trap 'rm -f "$tmp_mix"' EXIT
        mkdir -p "$HOME/.config/mix-manager"
        echo "{\"path\": \"$tmp_mix\", \"position_sec\": 10, \"duration_sec\": 3600}" > "$HOME/.config/mix-manager/playback_resume.json"
        play_audio_file() { PLAY_CALLED=1; }
        select_startup_mix() { echo "$tmp_mix"; }
        is_remote_or_cloud_path() { return 1; }
        same_mix_file() { [ "$1" = "$2" ]; }
        get_connected_displays_count() { echo 1; }
        align_mix_windows_on_screen() { :; }
        find_mix_tracklist() { FIND_TL=$((FIND_TL + 1)); echo "/tmp/should_not_open.txt"; }
        open_tracklist_window() { TL_OPENED=$((TL_OPENED + 1)); }
        get_mp_audio_player_track_info() {
            MP_PLAYER_STATE="stopped"
            MP_PLAYER_RAW_PATH=""
            return 1
        }
        execute_startup_autoplay
        echo "PLAY_CALLED=$PLAY_CALLED"
        echo "TL_OPENED=$TL_OPENED"
        echo "FIND_TL=$FIND_TL"
        """
        res = run_bash(script)
        self.assertIn("PLAY_CALLED=1", res.stdout)
        self.assertIn("TL_OPENED=0", res.stdout)
        self.assertIn("FIND_TL=0", res.stdout)

    def test_playing_a_mix_does_not_open_tracklist_window(self):
        script = r"""
        set -e
        eval "$(sed -n '/^auto_show_playing_mix_assets() {/,/^}/p' Mix_Archive_Manager.sh)"
        AUTO_SHOW_TRACKLIST_ON_STARTUP="true"
        AUTO_PLAY_YOUTUBE_ON_STARTUP="false"
        TL_OPENED=0
        COVER_OPENED=0
        FIND_TL=0
        tmp_dir=$(mktemp -d /tmp/test_assets_XXXXXX)
        mix="$tmp_dir/mix.flac"
        cover="$tmp_dir/cover.png"
        tracklist="$tmp_dir/mix.txt"
        echo "audio" > "$mix"
        echo "cover" > "$cover"
        echo "track one" > "$tracklist"
        trap 'rm -rf "$tmp_dir"' EXIT
        clear() { :; }
        find_mix_cover() { echo "$cover"; }
        open_cover_art_window() { COVER_OPENED=$((COVER_OPENED + 1)); }
        find_mix_tracklist() { FIND_TL=$((FIND_TL + 1)); echo "$tracklist"; }
        open_tracklist_window() { TL_OPENED=$((TL_OPENED + 1)); }
        align_mix_windows_on_screen() { :; }
        get_playing_audio_spec_summary() { echo "FLAC"; }
        get_active_audio_interface_display() { echo "Speakers"; }
        auto_show_playing_mix_assets "$mix" "mp_audio_player"
        echo "TL_OPENED=$TL_OPENED"
        echo "COVER_OPENED=$COVER_OPENED"
        echo "FIND_TL=$FIND_TL"
        """
        res = run_bash(script)
        self.assertIn("TL_OPENED=0", res.stdout)
        self.assertIn("FIND_TL=0", res.stdout)
        self.assertIn("COVER_OPENED=1", res.stdout)
        self.assertNotIn("Tracklist Opened", res.stdout)


if __name__ == "__main__":
    unittest.main()
