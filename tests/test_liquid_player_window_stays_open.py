"""Manager startup resumes a mix by passing --play into the Liquid Glass host.

The host embeds MP_Audio_Player.py --interactive and forwards those arguments.
--play used to start the mix and exit. The embedded terminal then quit, and the
glass window closed. The desktop shortcut stays open because it passes no --play.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from MP_Audio_Player_Liquid_Glass_OpenGL import player_argv  # noqa: E402


def _run_player(argv_tail, daemon=False, status=None):
    home = tempfile.mkdtemp(prefix="mp_liquid_stay_")
    try:
        result_path = Path(home) / "result.json"
        audio = Path(home) / "resume_mix.flac"
        audio.write_bytes(b"not really audio")
        argv = ["MP_Audio_Player.py"] + [part.replace("{audio}", str(audio)) for part in argv_tail]
        scenario = {"argv": argv, "daemon": daemon, "status": status}
        env = os.environ.copy()
        env["HOME"] = home
        env["MP_LIQUID_STAY_OPEN_CHILD"] = "1"
        env["MP_SCENARIO"] = json.dumps(scenario)
        env["MP_RESULT"] = str(result_path)
        proc = subprocess.run(
            [sys.executable, str(Path(__file__).resolve())],
            cwd=str(ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if proc.returncode != 0 or not result_path.is_file():
            raise AssertionError(
                f"player harness failed ({proc.returncode})\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
            )
        data = json.loads(result_path.read_text(encoding="utf-8"))
        data["audio"] = str(audio.resolve())
        return data
    finally:
        shutil.rmtree(home, ignore_errors=True)


def _child():
    import MP_Audio_Player as player

    scenario = json.loads(os.environ["MP_SCENARIO"])
    result = {"ui": False, "spawn": None, "ipc": []}

    class EmptyScanner:
        def __init__(self, *args, **kwargs):
            self.mixes = []

        def get_mixes(self, *args, **kwargs):
            return []

        def get_latest_mix(self):
            return None

    player.MixArchiveScanner = EmptyScanner
    player.MusicFolderPlaylistScanner = EmptyScanner
    player.time.sleep = lambda *args, **kwargs: None
    player._retire_extra_player_daemons = lambda *args, **kwargs: None

    def fake_spawn(file_path=None, auto_bluetooth=True, mode="MIX_ARCHIVE", music_folder=None, playlist_path=None, seek_to=None):
        result["spawn"] = {
            "file": file_path,
            "seek_to": seek_to,
            "mode": mode,
            "music_folder": music_folder,
            "playlist_path": playlist_path,
        }
        return 4242

    player._spawn_player_daemon = fake_spawn
    player.is_player_daemon_running = lambda: bool(scenario.get("daemon"))

    def fake_ipc(cmd, **kwargs):
        result["ipc"].append({"cmd": cmd, "kwargs": kwargs})
        if cmd == "status":
            return scenario.get("status")
        return {"status": "ok"}

    player.send_ipc_command = fake_ipc

    class FakeUI:
        def __init__(self, *args, **kwargs):
            result["ui_mode"] = kwargs.get("ui_size_mode")
            result["keep_library"] = kwargs.get("keep_library")
            result["mode"] = kwargs.get("mode")

        def run(self):
            result["ui"] = True

    player.TerminalPlayerUI = FakeUI
    sys.argv = scenario["argv"]
    code = 0
    try:
        player.main()
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
    result["exit"] = code
    Path(os.environ["MP_RESULT"]).write_text(json.dumps(result), encoding="utf-8")


class TestLiquidPlayerStaysOpen(unittest.TestCase):
    def test_opengl_host_forwards_play_into_the_interactive_player(self):
        cmd = player_argv(extra_args=["--play", "/mixes/resume.flac", "--seek-to", "88.5", "--music-mode"])
        self.assertIn("--interactive", cmd)
        forwarded = cmd[cmd.index("--interactive") + 1:]
        self.assertEqual(forwarded, ["--play", "/mixes/resume.flac", "--seek-to", "88.5", "--music-mode"])

    def test_manager_launch_passes_play_to_liquid_glass(self):
        text = (ROOT / "Mix_Archive_Manager.sh").read_text(encoding="utf-8")
        self.assertIn('[ -n "$audio_file" ] && py_args=("--play" "$audio_file")', text)
        self.assertIn('py_args+=(--seek-to "$seek_pos")', text)

    def test_interactive_play_stays_in_the_ui_and_seeks(self):
        data = _run_player([
            "--interactive",
            "--play",
            "{audio}",
            "--seek-to",
            "88.5",
            "--music-mode",
        ])
        self.assertTrue(data["ui"], data)
        self.assertEqual(data["exit"], 0)
        self.assertEqual(data["spawn"]["file"], data["audio"])
        self.assertEqual(data["spawn"]["seek_to"], 88.5)
        self.assertEqual(data["spawn"]["mode"], "MUSIC")
        self.assertNotIn("play", [item["cmd"] for item in data["ipc"]])

    def test_interactive_play_uses_the_running_daemon_without_leaving_the_ui(self):
        data = _run_player(
            ["--interactive", "--play", "{audio}", "--seek-to", "88.5"],
            daemon=True,
            status={
                "status": "ok",
                "data": {
                    "state": "playing",
                    "path": "/already-playing.flac",
                    "mode": "MIX_ARCHIVE",
                    "running": True,
                },
            },
        )
        self.assertTrue(data["ui"], data)
        self.assertEqual(data["exit"], 0)
        self.assertIsNone(data["spawn"])
        plays = [item for item in data["ipc"] if item["cmd"] == "play"]
        self.assertEqual(len(plays), 1)
        self.assertEqual(plays[0]["kwargs"]["file"], data["audio"])
        self.assertEqual(plays[0]["kwargs"]["position"], 88.5)

    def test_plain_play_still_exits_without_opening_the_ui(self):
        data = _run_player(["--play", "{audio}", "--seek-to", "88.5"])
        self.assertFalse(data["ui"], data)
        self.assertEqual(data["exit"], 0)
        self.assertEqual(data["spawn"]["file"], data["audio"])
        self.assertEqual(data["spawn"]["seek_to"], 88.5)

    def test_music_folder_launch_loads_the_library_while_a_mix_is_playing(self):
        data = _run_player(
            ["--interactive", "--music-mode", "--music-folder", "ALL", "--playlist", "/libraries/ALL.json"],
            daemon=True,
            status={
                "status": "ok",
                "data": {
                    "state": "playing",
                    "path": "/mixes/current_mix.flac",
                    "mode": "MIX_ARCHIVE",
                    "running": True,
                },
            },
        )
        self.assertTrue(data["ui"], data)
        self.assertEqual(data["mode"], "MUSIC")
        self.assertTrue(data["keep_library"])
        self.assertIsNone(data["spawn"])
        loads = [item for item in data["ipc"] if item["cmd"] == "load_playlist"]
        self.assertEqual(len(loads), 1, data)
        self.assertEqual(loads[0]["kwargs"]["mode"], "MUSIC")
        self.assertEqual(loads[0]["kwargs"]["folder_name"], "ALL")
        self.assertEqual(loads[0]["kwargs"]["playlist_path"], "/libraries/ALL.json")
        self.assertTrue(loads[0]["kwargs"]["play"])
        self.assertNotIn("play", [item["cmd"] for item in data["ipc"]])

    def test_music_folder_launch_does_not_restart_music_already_playing(self):
        data = _run_player(
            ["--interactive", "--music-mode", "--music-folder", "ALL", "--playlist", "/libraries/ALL.json"],
            daemon=True,
            status={
                "status": "ok",
                "data": {
                    "state": "playing",
                    "path": "/music/track.flac",
                    "mode": "MUSIC",
                    "running": True,
                },
            },
        )
        self.assertTrue(data["ui"], data)
        self.assertTrue(data["keep_library"])
        self.assertNotIn("load_playlist", [item["cmd"] for item in data["ipc"]])
        self.assertNotIn("play", [item["cmd"] for item in data["ipc"]])

    def test_music_window_keeps_its_library_when_mix_status_arrives(self):
        import MP_Audio_Player as player
        from unittest import mock

        library = player.MusicFolderPlaylistScanner.__new__(player.MusicFolderPlaylistScanner)
        ui = player.TerminalPlayerUI.__new__(player.TerminalPlayerUI)
        ui.mode = "MUSIC"
        ui.keep_library = True
        ui.scanner = library
        ui.folder_name = "ALL"
        ui._sync_mode_scanner("MIX_ARCHIVE")
        self.assertIs(ui.scanner, library)
        self.assertEqual(ui.mode, "MUSIC")

        ui.keep_library = False
        with mock.patch.object(player, "MixArchiveScanner", return_value="archive-scanner"):
            ui._sync_mode_scanner("MIX_ARCHIVE")
        self.assertEqual(ui.scanner, "archive-scanner")
        self.assertEqual(ui.mode, "MIX_ARCHIVE")

    def test_interactive_attach_does_not_restart_current_playback(self):
        data = _run_player(
            ["--interactive"],
            daemon=True,
            status={
                "status": "ok",
                "data": {
                    "state": "playing",
                    "path": "/already-playing.flac",
                    "mode": "MIX_ARCHIVE",
                    "running": True,
                },
            },
        )
        self.assertTrue(data["ui"], data)
        self.assertIsNone(data["spawn"])
        self.assertNotIn("play", [item["cmd"] for item in data["ipc"]])


if __name__ == "__main__":
    if os.environ.get("MP_LIQUID_STAY_OPEN_CHILD") == "1":
        _child()
    else:
        unittest.main()
