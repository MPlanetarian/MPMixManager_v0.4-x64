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


def run_bash(script: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [BASH_BIN, "-c", script],
        cwd=str(BASE_DIR),
        capture_output=True,
        text=True,
        check=True,
    )


class TestPlaybackResume(unittest.TestCase):
    def test_save_playback_resume_state_from_mp_player(self):
        tmp = tempfile.mkdtemp(prefix="mp_resume_test_")
        try:
            home = tmp.replace("\\", "/")
            if len(home) >= 2 and home[1] == ":":
                home = "/" + home[0].lower() + home[2:]
            mix_file = Path(tmp) / "current_playing.flac"
            mix_file.write_text("audio content")
            script = f"""
            set -e
            export HOME="{home}"
            eval "$(sed -n '/^save_playback_resume_state() {{/,/^}}/p' Mix_Archive_Manager.sh)"
            get_mp_audio_player_track_info() {{
                MP_PLAYER_RAW_PATH="{mix_file.as_posix()}"
                MP_PLAYER_POS_SEC=321.5
                MP_PLAYER_DUR_SEC=3600.0
                MP_PLAYER_TITLE="My Mix Title"
                MP_PLAYER_MODE="MIX_ARCHIVE"
                return 0
            }}
            save_playback_resume_state
            """
            run_bash(script)
            resume_file = Path(tmp) / ".config" / "mix-manager" / "playback_resume.json"
            self.assertTrue(resume_file.is_file())
            data = json.loads(resume_file.read_text(encoding="utf-8"))
            self.assertEqual(data["path"], mix_file.as_posix())
            self.assertEqual(data["position_sec"], 321.5)
            self.assertEqual(data["duration_sec"], 3600.0)
            self.assertEqual(data["title"], "My Mix Title")
            self.assertEqual(data["player"], "mp_audio_player")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_execute_startup_autoplay_resumes_saved_mix_and_position(self):
        tmp = tempfile.mkdtemp(prefix="mp_resume_test_")
        try:
            home = tmp.replace("\\", "/")
            if len(home) >= 2 and home[1] == ":":
                home = "/" + home[0].lower() + home[2:]
            state_dir = Path(tmp) / ".config" / "mix-manager"
            state_dir.mkdir(parents=True)
            resume_file = state_dir / "playback_resume.json"
            mix_file = Path(tmp) / "summer_session_001.flac"
            mix_file.write_text("audio")
            resume_file.write_text(
                json.dumps({
                    "path": mix_file.as_posix(),
                    "position_sec": 75.0,
                    "duration_sec": 1800.0,
                    "player": "mp_audio_player",
                    "mode": "MUSIC"
                }),
                encoding="utf-8"
            )
            script = f"""
            set -e
            export HOME="{home}"
            _fmt_sec() {{ local t=${{1:-0}}; ((t<0)) && t=0; ((t>=3600)) && printf "%02d:%02d:%02d" $((t/3600)) $(((t%3600)/60)) $((t%60)) || printf "%02d:%02d" $(((t%3600)/60)) $((t%60)); }}
            eval "$(sed -n '/^execute_startup_autoplay() {{/,/^}}/p' Mix_Archive_Manager.sh)"
            AUTO_PLAY_ON_STARTUP="true"
            DEFAULT_AUDIO_PLAYER="mp_audio_player"
            PLAY_CALLED=0
            PLAYED_FILE=""
            SEEK_POS=""
            MODE_ARG=""
            play_audio_file() {{ PLAY_CALLED=1; PLAYED_FILE="$2"; SEEK_POS="$3"; MODE_ARG="$4"; }}
            is_remote_or_cloud_path() {{ return 1; }}
            align_mix_windows_on_screen() {{ :; }}
            get_mp_audio_player_track_info() {{ return 1; }}
            get_audacious_track_info() {{ return 1; }}
            get_strawberry_track_info() {{ return 1; }}
            get_cliamp_track_info() {{ return 1; }}
            detect_currently_playing_mix() {{ return 1; }}
            execute_startup_autoplay
            echo "PLAY_CALLED=$PLAY_CALLED"
            echo "PLAYED_FILE=$PLAYED_FILE"
            echo "SEEK_POS=$SEEK_POS"
            echo "MODE_ARG=$MODE_ARG"
            echo "NOTICE=$STARTUP_AUTOPLAY_NOTICE"
            """
            res = run_bash(script)
            self.assertIn("PLAY_CALLED=1", res.stdout)
            self.assertIn(f"PLAYED_FILE={mix_file.as_posix()}", res.stdout)
            self.assertIn("SEEK_POS=75.0", res.stdout)
            self.assertIn("MODE_ARG=MUSIC", res.stdout)
            self.assertIn("Resumed playback: summer_session_001.flac at 01:15 (MP Audio Player)", res.stdout)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_save_playback_resume_state_zero_pos_protection(self):
        tmp = tempfile.mkdtemp(prefix="mp_resume_test_")
        try:
            home = tmp.replace("\\", "/")
            if len(home) >= 2 and home[1] == ":":
                home = "/" + home[0].lower() + home[2:]
            state_dir = Path(tmp) / ".config" / "mix-manager"
            state_dir.mkdir(parents=True)
            resume_file = state_dir / "playback_resume.json"
            mix_file = Path(tmp) / "protect_mix.flac"
            mix_file.write_text("audio content")
            resume_file.write_text(
                json.dumps({
                    "path": mix_file.as_posix(),
                    "position_sec": 240.5,
                    "duration_sec": 3600.0,
                    "player": "mp_audio_player",
                    "mode": "MIX_ARCHIVE"
                }),
                encoding="utf-8"
            )
            script = f"""
            set -e
            export HOME="{home}"
            eval "$(sed -n '/^save_playback_resume_state() {{/,/^}}/p' Mix_Archive_Manager.sh)"
            get_mp_audio_player_track_info() {{
                MP_PLAYER_RAW_PATH="{mix_file.as_posix()}"
                MP_PLAYER_POS_SEC=0.0
                MP_PLAYER_DUR_SEC=3600.0
                MP_PLAYER_TITLE="Protect Mix"
                MP_PLAYER_MODE="MIX_ARCHIVE"
                return 0
            }}
            save_playback_resume_state
            """
            run_bash(script)
            data = json.loads(resume_file.read_text(encoding="utf-8"))
            self.assertEqual(data["position_sec"], 240.5)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_play_audio_file_music_mode_flag(self):
        tmp = tempfile.mkdtemp(prefix="mp_resume_test_")
        try:
            home = tmp.replace("\\", "/")
            if len(home) >= 2 and home[1] == ":":
                home = "/" + home[0].lower() + home[2:]
            mix_file = Path(tmp) / "track.mp3"
            mix_file.write_text("audio")
            script = f"""
            set -e
            export HOME="{home}"
            SCRIPT_DIR="{tmp}"
            eval "$(sed -n '/^play_audio_file() {{/,/^}}/p' Mix_Archive_Manager.sh)"
            auto_show_playing_mix_assets() {{ :; }}
            python3() {{
                echo "ARGS: $*"
            }}
            touch "{tmp}/MP_Audio_Player.py"
            play_audio_file "mp_audio_player" "{mix_file.as_posix()}" "123.4" "MUSIC"
            """
            res = run_bash(script)
            self.assertIn("--play", res.stdout)
            self.assertIn("--seek-to 123.4", res.stdout)
            self.assertIn("--music-mode", res.stdout)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_startup_autoplay_does_not_play_latest_converted_mix_if_no_resume(self):
        tmp = tempfile.mkdtemp(prefix="mp_resume_test_")
        try:
            home = tmp.replace("\\", "/")
            if len(home) >= 2 and home[1] == ":":
                home = "/" + home[0].lower() + home[2:]
            script = f"""
            set -e
            export HOME="{home}"
            eval "$(sed -n '/^execute_startup_autoplay() {{/,/^}}/p' Mix_Archive_Manager.sh)"
            AUTO_PLAY_ON_STARTUP="true"
            DEFAULT_AUDIO_PLAYER="mp_audio_player"
            PLAY_CALLED=0
            play_audio_file() {{ PLAY_CALLED=1; }}
            select_startup_mix() {{ echo "/tmp/latest_mix_that_should_not_play.flac"; }}
            get_mp_audio_player_track_info() {{ return 1; }}
            get_audacious_track_info() {{ return 1; }}
            get_strawberry_track_info() {{ return 1; }}
            get_cliamp_track_info() {{ return 1; }}
            detect_currently_playing_mix() {{ return 1; }}
            execute_startup_autoplay
            echo "PLAY_CALLED=$PLAY_CALLED"
            echo "NOTICE=$STARTUP_AUTOPLAY_NOTICE"
            """
            res = run_bash(script)
            self.assertIn("PLAY_CALLED=0", res.stdout)
            self.assertEqual(res.stdout.strip().splitlines()[-1], "NOTICE=")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_mp_audio_player_resume_flag_syntax(self):
        res = subprocess.run(
            ["python3", "MP_Audio_Player.py", "--help"],
            cwd=str(BASE_DIR),
            capture_output=True,
            text=True,
            check=True
        )
        self.assertIn("--resume", res.stdout)
        self.assertIn("--seek-to", res.stdout)


if __name__ == "__main__":
    unittest.main()
