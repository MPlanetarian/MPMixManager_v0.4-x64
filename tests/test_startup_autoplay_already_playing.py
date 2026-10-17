import subprocess
import unittest


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
        res = subprocess.run(
            ["bash", "-c", script],
            cwd="/home/mplanetarian/MP_Mix_Manager_v0.3",
            capture_output=True,
            text=True,
            check=True,
        )
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
        res = subprocess.run(
            ["bash", "-c", script],
            cwd="/home/mplanetarian/MP_Mix_Manager_v0.3",
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertIn("PLAY_CALLED=1", res.stdout)


if __name__ == "__main__":
    unittest.main()
