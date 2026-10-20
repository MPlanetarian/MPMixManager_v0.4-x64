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


def run_bash(script: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [BASH_BIN, "-c", script],
        cwd=str(BASE_DIR),
        capture_output=True,
        text=True,
        check=True,
    )


class TestStartupAutoplayAlreadyPlaying(unittest.TestCase):
    def test_skips_autoplay_when_mp_audio_player_already_playing(self):
        script = r"""
        set -e
        eval "$(sed -n '/^execute_startup_autoplay() {/,/^}/p' Mix_Archive_Manager.sh)"
        AUTO_PLAY_ON_STARTUP="true"
        DEFAULT_AUDIO_PLAYER="mp_audio_player"
        PLAY_CALLED=0
        play_audio_file() { PLAY_CALLED=1; }
        select_startup_mix() { echo "/tmp/new_startup_mix.flac"; }
        get_mp_audio_player_track_info() {
            MP_PLAYER_STATE="playing"
            MP_PLAYER_RAW_PATH="/tmp/already_playing_mix.flac"
            return 0
        }
        execute_startup_autoplay
        echo "PLAY_CALLED=$PLAY_CALLED"
        echo "NOTICE=$STARTUP_AUTOPLAY_NOTICE"
        """
        res = run_bash(script)
        self.assertIn("PLAY_CALLED=0", res.stdout)
        self.assertIn("Already playing: already_playing_mix.flac (MP Audio Player)", res.stdout)

    def test_plays_startup_mix_when_mp_audio_player_not_playing(self):
        script = r"""
        set -e
        eval "$(sed -n '/^execute_startup_autoplay() {/,/^}/p' Mix_Archive_Manager.sh)"
        AUTO_PLAY_ON_STARTUP="true"
        AUTO_SHOW_COVER_ON_STARTUP="false"
        AUTO_SHOW_TRACKLIST_ON_STARTUP="false"
        AUTO_PLAY_YOUTUBE_ON_STARTUP="false"
        DEFAULT_AUDIO_PLAYER="mp_audio_player"
        PLAY_CALLED=0
        PLAYED_FILE=""
        tmp_mix=$(mktemp /tmp/test_startup_mix_XXXXXX.flac)
        echo "audio" > "$tmp_mix"
        trap 'rm -f "$tmp_mix"' EXIT
        play_audio_file() { PLAY_CALLED=1; PLAYED_FILE="$2"; }
        select_startup_mix() { echo "$tmp_mix"; }
        is_remote_or_cloud_path() { return 1; }
        same_mix_file() { [ "$1" = "$2" ]; }
        get_connected_displays_count() { echo 2; }
        align_mix_windows_on_screen() { :; }
        get_mp_audio_player_track_info() {
            MP_PLAYER_STATE="stopped"
            MP_PLAYER_RAW_PATH=""
            return 1
        }
        execute_startup_autoplay
        echo "PLAY_CALLED=$PLAY_CALLED"
        echo "PLAYED_FILE=$PLAYED_FILE"
        """
        res = run_bash(script)
        self.assertIn("PLAY_CALLED=1", res.stdout)

    def test_newline_less_state_file_skips_second_manager_autoplay(self):
        """Python writes mp_player_state.json with no trailing newline.

        Bash read then returns EOF. Treating that as 'player not running'
        made a second Manager instance start a new mix over one already playing.
        """
        tmp = tempfile.mkdtemp(prefix="mp_autoplay_")
        try:
            state_dir = Path(tmp) / ".config" / "mix-manager"
            state_dir.mkdir(parents=True)
            state_file = state_dir / "mp_player_state.json"
            state_file.write_bytes(
                b'{"running": true, "state": "playing", "path": "/tmp/already_playing_mix.flac", "pid": 0}'
            )
            home = tmp.replace("\\", "/")
            if len(home) >= 2 and home[1] == ":":
                home = "/" + home[0].lower() + home[2:]
            script = f"""
            set -e
            export HOME="{home}"
            _CACHED_PLAYER_CHECK_TIME=-10
            _CACHED_PLAYER_ACTIVE_RES=1
            eval "$(sed -n '/^get_mp_audio_player_track_info() {{/,/^}}/p' Mix_Archive_Manager.sh)"
            eval "$(sed -n '/^execute_startup_autoplay() {{/,/^}}/p' Mix_Archive_Manager.sh)"
            AUTO_PLAY_ON_STARTUP="true"
            DEFAULT_AUDIO_PLAYER="mp_audio_player"
            PLAY_CALLED=0
            play_audio_file() {{ PLAY_CALLED=1; }}
            select_startup_mix() {{ echo "/tmp/new_startup_mix.flac"; }}
            execute_startup_autoplay
            echo "PLAY_CALLED=$PLAY_CALLED"
            echo "NOTICE=$STARTUP_AUTOPLAY_NOTICE"
            echo "STATE=$MP_PLAYER_STATE"
            """
            res = run_bash(script)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        self.assertIn("STATE=playing", res.stdout)
        self.assertIn("PLAY_CALLED=0", res.stdout)
        self.assertIn("Already playing: already_playing_mix.flac (MP Audio Player)", res.stdout)


if __name__ == "__main__":
    unittest.main()
