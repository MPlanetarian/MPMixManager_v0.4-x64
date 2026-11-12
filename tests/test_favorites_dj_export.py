#!/usr/bin/env python3
"""Favorites DJ set exporter: copy, verify, tracklist, m3u8 and Traktor playlist."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import MagicMock, patch

import MP_Audio_Player as player
from scripts import MP_Fav_Playlist_Track_Exporter as exporter


def _ffmpeg() -> bool:
    return bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def _make_audio(path: Path, frequency: int = 440) -> None:
    subprocess.run(
        [
            "ffmpeg", "-loglevel", "error", "-f", "lavfi",
            "-i", f"sine=frequency={frequency}:duration=1",
            "-c:a", "flac", str(path), "-y",
        ],
        check=True,
    )


def _nml_entry(filename: str, artist: str, title: str, key: str = "8m", mval: str = "21") -> str:
    return (
        f'<ENTRY TITLE="{title}" ARTIST="{artist}">'
        f'<LOCATION DIR="/:music/:" FILE="{filename}" VOLUME=""/>'
        f'<INFO KEY="{key}" PLAYTIME="300"/>'
        f'<TEMPO BPM="138.0"/>'
        f'<MUSICAL_KEY VALUE="{mval}"/>'
        "</ENTRY>"
    )


class ExporterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.src = self.root / "src"
        self.src.mkdir()
        self.audio = [self.src / "Airbase - Escape.flac", self.src / "Gai Barone - Lonely Keys.flac"]
        if _ffmpeg():
            _make_audio(self.audio[0], 440)
            _make_audio(self.audio[1], 330)
        else:
            for path in self.audio:
                path.write_bytes(b"fLaC" + b"\x00" * 4096)
        self.favorites = self.root / "favorites.json"
        self.favorites.write_text(
            json.dumps(
                {
                    "version": 1,
                    "name": "Favorites",
                    "tracks": [
                        {"name": path.name, "path": str(path), "ext": "FLAC"} for path in self.audio
                    ],
                }
            ),
            encoding="utf-8",
        )
        self.env = patch.dict(
            os.environ,
            {"MP_FAVORITES_FILE": str(self.favorites), "FAV_EXPORT_SMB_HOST": "", "FAV_EXPORT_SMB_MOUNT": ""},
            clear=False,
        )
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def test_empty_favorites_refuses_to_export(self):
        result = exporter.export_favorites([], destination=str(self.root / "out"))
        self.assertFalse(result["ok"])
        self.assertIn("empty", " ".join(result["errors"]).lower())
        self.assertFalse((self.root / "out").exists())

    def test_playlist_name_uses_the_date_and_twelve_characters(self):
        name = exporter.new_playlist_name()
        self.assertRegex(name, r"^MP_Fav_Set_\d{4}-\d{2}-\d{2}_[A-Z0-9]{12}$")
        self.assertEqual(exporter.new_playlist_name("My Set"), "My Set")

    def test_local_export_copies_verifies_and_writes_the_tracklist(self):
        result = exporter.export_favorites(self.audio, destination=str(self.root / "out"))
        self.assertTrue(result["ok"], result.get("errors"))
        self.assertEqual(len(result["copied"]), 2)
        folder = Path(result["dest"])
        self.assertTrue((folder / self.audio[0].name).is_file())
        self.assertEqual(
            (folder / self.audio[0].name).stat().st_size, self.audio[0].stat().st_size
        )
        self.assertGreaterEqual(result["playable_files"], 1)
        tracklist = Path(result["tracklist"])
        self.assertEqual(tracklist.parent, folder)
        content = tracklist.read_text(encoding="utf-8")
        self.assertIn("RELEASE INFO & SOURCE MANIFEST", content)
        self.assertIn("TRACKLIST", content)
        self.assertIn("Airbase - Escape", content)
        self.assertIn("Gai Barone - Lonely Keys", content)
        self.assertRegex(content, r"(?m)^01\. ")
        m3u8 = Path(result["m3u8"])
        self.assertTrue(m3u8.is_file())
        self.assertIn("#EXTM3U", m3u8.read_text(encoding="utf-8"))

    def test_mounted_smb_export_writes_the_tracklist_into_the_mount(self):
        mount = self.root / "mount"
        mount.mkdir()
        settings = {
            "host": "nas.local",
            "share": "Music",
            "user": "u",
            "password": "p",
            "path": "DJ Sets",
            "mount": str(mount),
            "kind": "smb",
        }
        result = exporter.export_favorites(self.audio, smb=settings, playlist_name="Mount Night")
        self.assertTrue(result["ok"], result.get("errors"))
        folder = mount / "DJ Sets" / "Mount Night"
        self.assertTrue((folder / "Mount Night.txt").is_file())
        self.assertTrue((folder / "Mount Night.m3u8").is_file())
        self.assertEqual(Path(result["tracklist"]).parent, folder)
        self.assertTrue(result["dest"].startswith("smb://nas.local/Music/"))

    def test_custom_tracklist_name_is_used_for_file_and_folder(self):
        result = exporter.export_favorites(
            self.audio, destination=str(self.root / "out"), tracklist_name="Friday Warmup"
        )
        self.assertTrue(result["ok"], result.get("errors"))
        self.assertEqual(Path(result["tracklist"]).name, "Friday Warmup.txt")
        self.assertEqual(Path(result["dest"]).name, "Friday Warmup")

    def test_missing_source_is_reported_and_does_not_stop_the_export(self):
        missing = {"name": "Gone.flac", "path": str(self.src / "Gone.flac"), "ext": "FLAC"}
        result = exporter.export_favorites(
            [self.audio[0], missing], destination=str(self.root / "out")
        )
        self.assertTrue(result["ok"], result.get("errors"))
        self.assertEqual(len(result["copied"]), 1)
        self.assertEqual(result["failed"][0]["name"], "Gone.flac")

    def test_truncated_copy_fails_verification(self):
        destination = self.root / "out"
        with patch.object(exporter.shutil, "copy2", lambda src, dst: Path(dst).write_bytes(b"x" * 10)):
            result = exporter.export_favorites(self.audio, destination=str(destination))
        self.assertFalse(result["ok"])
        self.assertTrue(result["failed"])

    def test_unplayable_copies_are_treated_as_failed(self):
        bogus = self.src / "Not Audio.flac"
        bogus.write_bytes(b"not audio at all")
        with patch.object(exporter, "probe_audio", lambda path: {"playable": False}):
            result = exporter.export_favorites([bogus], destination=str(self.root / "out"))
        self.assertFalse(result["ok"])
        self.assertIn("could be opened as audio", " ".join(result["errors"]))


class TraktorPlaylistTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.history_dir = self.root / "History"
        self.history_dir.mkdir()
        self.collection = self.root / "collection.nml"
        self.collection.write_text(
            '<?xml version="1.0" encoding="UTF-8"?><NML VERSION="19">'
            "<COLLECTION ENTRIES=\"2\">"
            + _nml_entry("Airbase - Escape.flac", "Airbase", "Escape", "8m", "21")
            + _nml_entry("Gai Barone - Lonely Keys.flac", "Gai Barone", "Lonely Keys", "9d", "0")
            + "</COLLECTION>"
            '<PLAYLISTS><NODE TYPE="FOLDER" NAME="$ROOT"><SUBNODES COUNT="0"/></NODE></PLAYLISTS>'
            "</NML>",
            encoding="utf-8",
        )
        self.history = self.history_dir / "history_2026y11m12d_01h00m00s.nml"
        self.history.write_text(
            '<?xml version="1.0" encoding="UTF-8"?><NML VERSION="19">'
            "<COLLECTION ENTRIES=\"2\">"
            + _nml_entry("Gai Barone - Lonely Keys.flac", "Gai Barone", "Lonely Keys", "9d", "0")
            + _nml_entry("Airbase - Escape.flac", "Airbase", "Escape", "8m", "21")
            + "</COLLECTION>"
            '<PLAYLISTS><NODE TYPE="PLAYLIST" NAME="History"><PLAYLIST ENTRIES="2" TYPE="LIST">'
            '<ENTRY><PRIMARYKEY TYPE="TRACK" KEY="/:music/:Gai Barone - Lonely Keys.flac"/></ENTRY>'
            '<ENTRY><PRIMARYKEY TYPE="TRACK" KEY="/:music/:Airbase - Escape.flac"/></ENTRY>'
            "</PLAYLIST></NODE></PLAYLISTS></NML>",
            encoding="utf-8",
        )
        self.env = patch.dict(
            os.environ,
            {
                "TRAKTOR_COLLECTION_PATH": str(self.collection),
                "TRAKTOR_HISTORY_DIR": str(self.history_dir),
                "TRAKTOR_ENABLED": "true",
            },
            clear=False,
        )
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def test_ready_reports_collection_and_history(self):
        ready, reason = exporter.traktor_ready()
        self.assertTrue(ready, reason)

    def test_playlist_is_written_key_sorted_with_a_backup(self):
        result = exporter.create_traktor_playlist(
            ["Airbase - Escape.flac", "Gai Barone - Lonely Keys.flac"],
            "Fav Test",
            "history_2026y11m12d_01h00m00s.nml",
        )
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["matched"], 2)
        backups = list(self.root.glob("collection.nml.bak_*"))
        self.assertTrue(backups)
        root = ET.parse(self.collection).getroot()
        nodes = [n for n in root.findall(".//PLAYLISTS//NODE") if n.attrib.get("TYPE") == "PLAYLIST"]
        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0].attrib["NAME"], "Fav Test")
        keys = [pk.attrib["KEY"] for pk in nodes[0].findall(".//PRIMARYKEY")]
        # Key ascending: 8m (Airbase) before 9d (Gai Barone).
        self.assertEqual(keys[0], "/:music/:Airbase - Escape.flac")
        self.assertEqual(keys[1], "/:music/:Gai Barone - Lonely Keys.flac")

    def test_missing_history_is_reported(self):
        ready, _ = exporter.traktor_ready()
        self.assertTrue(ready)
        (self.history).unlink()
        ready, reason = exporter.traktor_ready()
        self.assertFalse(ready)
        self.assertIn("History", reason)

    def test_favorites_outside_the_session_fall_back_to_the_collection(self):
        self.history.write_text(
            '<?xml version="1.0" encoding="UTF-8"?><NML VERSION="19">'
            + '<COLLECTION ENTRIES="1">'
            + _nml_entry("Other Track.flac", "Someone", "Other", "1m", "0")
            + "</COLLECTION>"
            + '<PLAYLISTS><NODE TYPE="PLAYLIST" NAME="History"><PLAYLIST ENTRIES="1" TYPE="LIST">'
            + '<ENTRY><PRIMARYKEY TYPE="TRACK" KEY="/:music/:Other Track.flac"/></ENTRY>'
            + "</PLAYLIST></NODE></PLAYLISTS></NML>",
            encoding="utf-8",
        )
        result = exporter.create_traktor_playlist(["Airbase - Escape.flac"], "Fallback")
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["matched"], 1)

    def test_track_in_neither_session_nor_collection_is_reported(self):
        result = exporter.create_traktor_playlist(["Unknown - Track.flac"], "No Match")
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "no_match")
        self.assertIn("Unknown - Track.flac", result["missing"])


def _track(name, path):
    return {"name": name, "path": path, "ext": "FLAC", "size_mb": 1.0}


class _Scanner:
    def __init__(self, mixes):
        self.mixes = list(mixes)
        self.base_dir = Path("/tmp/mix-archive")

    def get_mixes(self, query=""):
        return list(self.mixes)

    def get_latest_mix(self):
        return self.mixes[0] if self.mixes else None


class FavoritesPlayerExportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = player.FavoritesStore(Path(self.tmp.name) / "favorites.json")
        self.ui = player.TerminalPlayerUI.__new__(player.TerminalPlayerUI)
        self.ui.mode = "FAVORITES"
        self.ui.folder_name = "ALL"
        self.ui.keep_library = True
        self.ui._user_library_mode = "FAVORITES"
        self.ui.is_remote = False
        self.ui.engine = MagicMock()
        self.ui.engine.current_track = None
        self.ui.engine.playlist = []
        self.ui.engine.current_index = 0
        self.ui.engine.get_status_dict.return_value = {"path": "", "title": "", "mode": "FAVORITES"}
        self.ui.scanner = _Scanner([])
        self.ui.export_mode = False
        self.ui.eq_naming_mode = False
        self.ui.search_mode = False
        self.ui.search_query = ""
        self.ui.selected_row = self.ui.scroll_offset = 0
        self.ui.cached_status = {"mode": "FAVORITES"}
        self.ui.notification_msg = ""
        self.ui.notification_time = 0.0
        self.ui.equalizer_hud_active = False
        self.ui.inspector_hud_active = False
        self.ui.ui_size_mode = "NORMAL"
        self.ui._playlist_clear_armed = False
        self.ui._inbuf = b""
        self.ui.favorites = self.store
        self.ui.favorites_clear_confirm = False
        self.ui.fav_export_mode = ""
        self.ui.fav_export_dest = ""
        self.ui.fav_export_name = ""
        self.ui.fav_export_kind = "local"
        self.ui.traktor_offer_paths = None
        self.ui.traktor_offer_name = ""
        self.ui.traktor_input_mode = ""
        self.ui.traktor_playlist_name = ""
        self.ui.traktor_history_id = ""
        self.ui._reset_click_targets()

    def tearDown(self):
        self.tmp.cleanup()

    def test_export_requires_at_least_one_favorite(self):
        self.ui._favorites_export_begin()
        self.assertEqual(self.ui.fav_export_mode, "")
        self.assertIn("empty", self.ui.notification_msg.lower())

    def test_j_opens_the_dj_export_decision_window(self):
        self.store.toggle(_track("Mix A.flac", "/mixes/a.flac"))
        with patch.object(player.TerminalPlayerUI, "_fav_exporter_module") as module:
            module.return_value.traktor_ready.return_value = (False, "not configured")
            self.ui._process_key(b"J")
        self.assertEqual(self.ui.fav_export_mode, "choose")
        self.assertIn("DJ export", self.ui.notification_msg)

    def test_lowercase_j_still_scrolls_the_favorites_list(self):
        self.store.toggle(_track("Mix A.flac", "/mixes/a.flac"))
        self.ui.scanner = _Scanner([_track("Mix A.flac", "/mixes/a.flac")])
        self.ui._process_key(b"j")
        self.assertEqual(self.ui.fav_export_mode, "")

    def test_clicking_the_footer_export_label_opens_the_window(self):
        self.store.toggle(_track("Mix A.flac", "/mixes/a.flac"))
        self.ui._fav_export_button = (20, 30, 44)
        with patch.object(player.TerminalPlayerUI, "_fav_exporter_module") as module:
            module.return_value.traktor_ready.return_value = (False, "not configured")
            self.ui._process_key(b"\x1b[<0;36;20M")
        self.assertEqual(self.ui.fav_export_mode, "choose")

    def test_export_flow_prompts_for_the_tracklist_name_then_the_folder(self):
        self.store.toggle(_track("Mix A.flac", "/mixes/a.flac"))
        with patch.object(player.TerminalPlayerUI, "_fav_exporter_module") as module:
            module.return_value.traktor_ready.return_value = (False, "not configured")
            module.return_value.DEFAULT_LOCAL_DIR = Path("/tmp/fav-default")
            self.ui.fav_export_mode = "choose"
            self.ui._process_key(b"1")
            self.assertEqual(self.ui.fav_export_mode, "tracklist_name")
            for char in b"My Set":
                self.ui._process_key(bytes([char]))
            self.ui._process_key(b"\r")
        self.assertEqual(self.ui.fav_export_mode, "dest_path")
        self.assertEqual(self.ui.fav_export_name, "My Set")
        self.assertTrue(self.ui.fav_export_dest)

    def test_clear_in_favorites_opens_a_decision_window(self):
        self.store.toggle(_track("Mix A.flac", "/mixes/a.flac"))
        self.ui._arm_playlist_clear()
        self.assertTrue(self.ui.favorites_clear_confirm)
        self.assertIn("Clear the Favorites", self.ui.notification_msg)
        self.assertEqual(len(self.store), 1)

    def test_clear_on_an_empty_favorites_list_says_so(self):
        self.ui._arm_playlist_clear()
        self.assertFalse(self.ui.favorites_clear_confirm)
        self.assertIn("already empty", self.ui.notification_msg)

    def test_clear_is_cancelled_by_n_or_escape(self):
        self.store.toggle(_track("Mix A.flac", "/mixes/a.flac"))
        self.ui.favorites_clear_confirm = True
        self.ui._process_key(b"n")
        self.assertFalse(self.ui.favorites_clear_confirm)
        self.assertEqual(len(self.store), 1)
        self.ui.favorites_clear_confirm = True
        self.ui._process_key(b"\x1b")
        self.assertEqual(len(self.store), 1)

    def test_y_confirms_and_clears_only_the_playlist(self):
        self.store.toggle(_track("Mix A.flac", "/mixes/a.flac"))
        self.ui.favorites_clear_confirm = True
        with patch.object(player.TerminalPlayerUI, "_fav_exporter_module") as module:
            module.return_value.traktor_ready.return_value = (False, "not configured")
            self.ui._process_key(b"y")
        self.assertFalse(self.ui.favorites_clear_confirm)
        self.assertEqual(len(self.store), 0)
        self.assertIn("cleared", self.ui.notification_msg)

    def test_clear_then_offers_a_traktor_playlist_when_ready(self):
        self.store.toggle(_track("Mix A.flac", "/mixes/a.flac"))
        self.ui.favorites_clear_confirm = True
        with patch.object(player.TerminalPlayerUI, "_fav_exporter_module") as module:
            module.return_value.traktor_ready.return_value = (True, "ready")
            self.ui._process_key(b"y")
        self.assertEqual(len(self.store), 0)
        self.assertEqual(self.ui.traktor_offer_paths, ["/mixes/a.flac"])
        self.assertIn("Traktor playlist", self.ui.notification_msg)

    def test_clear_key_uses_the_decision_window_in_favorites(self):
        self.store.toggle(_track("Mix A.flac", "/mixes/a.flac"))
        self.ui._process_key(b"D")
        self.assertTrue(self.ui.favorites_clear_confirm)
        self.assertFalse(self.ui._playlist_clear_armed)

    def test_clear_key_keeps_the_two_step_arm_in_other_libraries(self):
        self.ui.mode = "MUSIC"
        self.ui.scanner = _Scanner([_track("Track A.flac", "/music/a.flac")])
        self.ui._process_key(b"D")
        self.assertTrue(self.ui._playlist_clear_armed)
        self.assertFalse(self.ui.favorites_clear_confirm)

    def test_traktor_offer_is_only_shown_when_ready(self):
        self.ui.traktor_offer_paths = ["/mixes/a.flac"]
        self.ui.traktor_playlist_name = "Favs"
        self.assertIn("Traktor is ready", self.ui._favorites_prompt_line())
        self.ui.traktor_offer_paths = None
        self.assertEqual(self.ui._favorites_prompt_line(), "")

    def test_decline_traktor_keeps_the_export(self):
        self.ui.traktor_offer_paths = ["/mixes/a.flac"]
        self.ui._process_key(b"n")
        self.assertIsNone(self.ui.traktor_offer_paths)
        self.assertIn("skipped", self.ui.notification_msg)

    def test_accept_traktor_asks_for_name_then_history(self):
        self.ui.traktor_offer_paths = ["/mixes/a.flac"]
        self.ui.traktor_offer_name = "Set 1"
        self.ui._process_key(b"y")
        self.assertEqual(self.ui.traktor_input_mode, "playlist_name")
        self.ui._process_key(b"\r")
        self.assertEqual(self.ui.traktor_input_mode, "history_id")
        self.assertEqual(self.ui.traktor_playlist_name, "Set 1")


if __name__ == "__main__":
    unittest.main()
