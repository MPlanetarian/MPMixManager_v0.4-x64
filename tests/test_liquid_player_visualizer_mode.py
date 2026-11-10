#!/usr/bin/env python3
"""The Liquid Player becomes the MP Visualizer in full, mini, and micro mode."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

BASE = Path(__file__).resolve().parent.parent
SCRIPTS = BASE / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import MP_Audio_Player as player
import liquid_player_visualizer as vis


def _track(name, path):
    return {"name": name, "path": path, "ext": "FLAC", "size_mb": 12.0}


class _ListScanner:
    def __init__(self, mixes):
        self.mixes = list(mixes)
        self.base_dir = Path("/tmp/mix-archive")

    def get_mixes(self, query=""):
        if not query:
            return list(self.mixes)
        q = query.lower()
        return [track for track in self.mixes if q in track["name"].lower() or q in track["path"].lower()]

    def get_latest_mix(self):
        return self.mixes[0] if self.mixes else None


def _status():
    return {
        "title": "Trance Roots 2026.flac",
        "path": "/mixes/a.flac",
        "state": "playing",
        "mode": "MIX_ARCHIVE",
        "position_fmt": "01:02",
        "duration_fmt": "06:40",
        "progress_pct": 15.0,
        "volume": 80,
        "muted": False,
        "pitch_percent": 0,
        "shuffle": False,
        "repeat": "all",
        "channels": 2,
        "sample_rate": 48000,
        "recording": False,
        "bluetooth_connected": False,
        "output_device": "Speakers",
        "queue_len": 0,
        "queue": [],
        "levels": [0.2] * 24,
        "peaks": [0.3] * 24,
        "levels_left": [0.2] * 24,
        "levels_right": [0.2] * 24,
        "peaks_left": [0.3] * 24,
        "peaks_right": [0.3] * 24,
        "rms_level": 0.1,
        "peak_db": -8.0,
    }


class LiquidPlayerVisualizerModeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.state = Path(self.tmp.name) / "liquid_player_visualizer.json"
        self._env = patch.dict(os.environ, {"MP_LIQUID_VISUALIZER_STATE": str(self.state)})
        self._env.start()
        vis._CACHE.update(path="", mtime=None, state=None)
        self.preset_file = Path.home() / ".config" / "mix-manager" / "visualizer_preset"
        self.preset_before = self.preset_file.read_text(encoding="utf-8") if self.preset_file.is_file() else None

    def tearDown(self):
        self._env.stop()
        self.tmp.cleanup()
        vis._CACHE.update(path="", mtime=None, state=None)
        after = self.preset_file.read_text(encoding="utf-8") if self.preset_file.is_file() else None
        self.assertEqual(after, self.preset_before)

    def _clear_state(self):
        vis._CACHE.update(path="", mtime=None, state=None)
        if self.state.exists():
            self.state.unlink()

    def _ui(self, liquid=False):
        env = {"MP_LIQUID_GLASS": "1"} if liquid else {"MP_LIQUID_GLASS": "0"}
        with patch.dict(os.environ, env):
            engine = MagicMock()
            engine.current_track = None
            engine.playlist = []
            engine.mode = "MIX_ARCHIVE"
            engine.muted = False
            engine.volume = 0.80
            engine.get_status_dict.return_value = _status()
            ui = player.TerminalPlayerUI(
                engine,
                _ListScanner([_track("Mix A.flac", "/mixes/a.flac")]),
                is_remote=False,
            )
        ui.favorites = player.FavoritesStore(Path(self.tmp.name) / "favorites.json")
        ui.cached_status = _status()
        return ui

    def _click(self, ui, col, row):
        ui._process_key(f"\x1b[<0;{int(col)};{int(row)}M".encode())

    def _draw(self, ui, kind):
        captured = []
        with patch.dict(os.environ, {"MP_LIQUID_GLASS": "1"}), \
             patch("MP_Audio_Player._present_frame", side_effect=lambda lines, w, h: captured.extend(lines)), \
             patch("MP_Audio_Player._win_visible_size", return_value=(100, 36)), \
             patch("sys.stdout.write"), \
             patch("sys.stdout.flush"):
            if kind == "full":
                ui.ui_size_mode = "NORMAL"
                ui._draw_frame()
            elif kind == "mini":
                ui._draw_mini_frame(74, 14, _status())
            else:
                ui._draw_micro_frame(74, 12, _status())
        return "\n".join(captured)

    def test_shift_v_still_lowers_volume_outside_the_liquid_player(self):
        ui = self._ui(liquid=False)
        ui.cached_status["volume"] = 80
        ui._process_key(b"V")
        self.assertEqual(ui.cached_status["volume"], 75)
        self.assertFalse(ui.mp_visualizer_on)
        self.assertFalse(self.state.is_file())

    def test_shift_v_toggles_the_visualizer_without_changing_volume(self):
        with patch.dict(os.environ, {"MP_LIQUID_GLASS": "1"}):
            ui = self._ui(liquid=True)
            ui.cached_status["volume"] = 80
            ui._process_key(b"V")
            self.assertTrue(ui.mp_visualizer_on)
            self.assertEqual(ui.cached_status["volume"], 80)
            self.assertIn("MP Visualizer", ui.notification_msg)
            saved = json.loads(self.state.read_text(encoding="utf-8"))
            self.assertTrue(saved["active"])
            self.assertEqual(saved["preset_id"], 0)
            self.assertEqual(saved["preset_name"], "Cosmic Dreamworlds (Liquid)")
            ui._process_key(b"V")
            self.assertFalse(ui.mp_visualizer_on)
            saved = json.loads(self.state.read_text(encoding="utf-8"))
            self.assertFalse(saved["active"])
            self.assertIn("Liquid glass restored", ui.notification_msg)

    def test_number_keys_change_theme_only_while_the_visualizer_is_on(self):
        with patch.dict(os.environ, {"MP_LIQUID_GLASS": "1"}):
            ui = self._ui(liquid=True)
            ui.mode = "MIX_ARCHIVE"
            with patch.object(ui, "_switch_library_mode") as switch, patch.object(ui, "_send_cmd") as send:
                ui._process_key(b"1")
                ui._process_key(b"2")
                ui._process_key(b"0")
                switch.assert_any_call("MIX_ARCHIVE")
                switch.assert_any_call("MUSIC")
                send.assert_any_call("reset_pitch")
                ui._process_key(b"V")
                switch.reset_mock()
                send.reset_mock()
                ui._process_key(b"2")
                ui._process_key(b"0")
                ui._process_key(b"9")
                switch.assert_not_called()
                send.assert_not_called()
            self.assertEqual(ui.mode, "MIX_ARCHIVE")
            self.assertEqual(ui.mp_visualizer_preset_id, 9)
            self.assertIn("Resonant Fluid Dynamics", ui.notification_msg)
            saved = json.loads(self.state.read_text(encoding="utf-8"))
            self.assertEqual(saved["preset_id"], 9)
            self.assertEqual(saved["preset_key"], "resonant_fluid_dynamics")
            self.assertTrue(saved["active"])

    def test_equalizer_and_search_keep_their_number_keys(self):
        with patch.dict(os.environ, {"MP_LIQUID_GLASS": "1"}):
            ui = self._ui(liquid=True)
            ui._process_key(b"V")
            ui.mp_visualizer_preset_id = 4
            ui.equalizer_hud_active = True
            with patch.object(ui.eq_manager, "apply_preset", wraps=ui.eq_manager.apply_preset) as apply:
                ui._process_key(b"1")
            apply.assert_called_with("Flat")
            self.assertEqual(ui.mp_visualizer_preset_id, 4)
            ui.equalizer_hud_active = False
            ui.search_mode = True
            ui.search_query = ""
            ui._process_key(b"3")
            self.assertEqual(ui.search_query, "3")
            self.assertEqual(ui.mp_visualizer_preset_id, 4)

    def test_visualization_button_is_on_full_mini_and_micro(self):
        with patch.dict(os.environ, {"MP_LIQUID_GLASS": "1"}):
            for kind, title in (
                ("full", "LIQUID GLASS"),
                ("mini", "MP MINI AUDIO PLAYER"),
                ("micro", "MP MICRO AUDIO PLAYER"),
            ):
                self._clear_state()
                ui = self._ui(liquid=True)
                drawn = self._draw(ui, kind)
                self.assertIn(title, drawn)
                self.assertIn("VISUALIZATION", drawn)
                self.assertIn("FAVORITES", drawn)
                self.assertIn("38;2;255;196;0", drawn)
                self.assertNotIn("48;2;255;196;0", drawn)
                self.assertIn("48;2;16;28;52", drawn)
                self.assertFalse(ui._favorites_button_whole_row)
                fav = ui._favorites_button_span
                vis_span = ui._visualizer_button_span
                self.assertLess(fav[1], vis_span[0])
                self.assertGreater(vis_span[1], vis_span[0])
                self.assertEqual(ui._favorites_button_row, ui._visualizer_button_row)
                self._click(ui, vis_span[0], ui._visualizer_button_row)
                self.assertTrue(ui.mp_visualizer_on)
                self.assertNotEqual(ui.mode, "FAVORITES")
                drawn_on = self._draw(ui, kind)
                self.assertIn("MP LIQUID GLASS VISUALIZER", drawn_on)
                self.assertIn("48;2;0;48;72", drawn_on)
                self._click(ui, ui._favorites_button_span[0], ui._favorites_button_row)
                self.assertEqual(ui.mode, "FAVORITES")

    def test_mini_and_micro_use_the_same_theme_keys(self):
        with patch.dict(os.environ, {"MP_LIQUID_GLASS": "1"}):
            for size in ("MINI", "MICRO"):
                self._clear_state()
                ui = self._ui(liquid=True)
                ui.ui_size_mode = size
                ui._process_key(b"V")
                ui._process_key(b"5")
                self.assertTrue(ui.mp_visualizer_on)
                self.assertEqual(ui.mp_visualizer_preset_id, 5)
                self.assertIn("Stream of Frequency", ui.notification_msg)

    def test_text_guard_lifts_dim_text_and_keeps_button_chips(self):
        dim = "\033[2m\033[38;2;20;30;40mDim label\033[0m"
        button = "\033[48;2;255;196;0;38;2;32;18;52m  FAVORITES  \033[0m"
        cyan = "\033[38;2;0;229;255mTest Title\033[0m"
        self.assertEqual(player._guard_visualizer_text(button), button)
        self.assertEqual(player._guard_visualizer_text(cyan), cyan)
        guarded = player._guard_visualizer_text(dim)
        self.assertNotIn("\033[2m", guarded)
        self.assertNotIn("38;2;20;30;40", guarded)

        ui = self._ui(liquid=True)
        ui.mp_visualizer_on = True
        written = []
        with patch.dict(os.environ, {"MP_LIQUID_GLASS": "1"}), \
             patch("sys.stdout.write", side_effect=written.append), \
             patch("sys.stdout.flush"):
            ui._arm_visualizer_text()
            player._present_frame([dim, button, cyan], 80, 3)
        shown = "".join(written)
        self.assertNotIn("\033[2m", shown)
        self.assertNotIn("38;2;20;30;40", shown)
        self.assertIn("48;2;255;196;0;38;2;32;18;52", shown)
        self.assertIn("38;2;0;229;255", shown)
        self.assertFalse(player._MP_VISUALIZER_TEXT)

    def test_shader_port_uses_flat_uniforms_and_a_text_guard(self):
        source = vis.opengl_visualizer_source()
        self.assertNotIn("layout(set", source)
        self.assertNotIn("u.res", source)
        self.assertNotIn("u.preset", source)
        self.assertNotIn("u.audio0", source)
        self.assertNotIn("u.bands0", source)
        self.assertIn("uniform vec4 u_preset", source)
        self.assertIn("uniform float uTextGuard", source)
        guard_at = source.find("uTextGuard > 0.5")
        out_at = source.find("outColor = vec4(col, 1.0);")
        self.assertGreater(guard_at, 0)
        self.assertGreater(out_at, guard_at)

    def test_macos_raymarch_is_smaller_than_the_retina_framebuffer(self):
        wide_fb = (3024, 1964)
        logical = (1512, 982)
        rw, rh = vis.visualizer_internal_size(*wide_fb, *logical, macos=True, long_edge=800)
        self.assertLessEqual(max(rw, rh), 800)
        self.assertLess(rw * rh, (wide_fb[0] * wide_fb[1]) // 8)
        self.assertEqual(vis.visualizer_internal_size(128, 64, 64, 32, macos=True, long_edge=800), (64, 32))
        self.assertEqual(vis.visualizer_internal_size(1920, 1080, 1920, 1080, macos=False), (1920, 1080))

    def test_macos_visualizer_fits_in_1080p_without_shrinking_the_player(self):
        os.environ.pop("MP_VISUALIZER_GL_LONG_EDGE", None)
        self.assertEqual(vis.MACOS_FULLSCREEN_SIZE, (1920, 1080))
        # The window stays full size. The march long edge is 768, then the
        # picture is scaled onto the window.
        self.assertEqual(vis.visualizer_internal_size(2188, 1468, 1094, 734, macos=True), (768, 515))
        self.assertEqual(vis.visualizer_internal_size(1094, 734, 1094, 734, macos=True), (768, 515))
        self.assertEqual(vis.visualizer_internal_size(1920, 1080, 1920, 1080, macos=True), (768, 432))
        self.assertEqual(vis.visualizer_internal_size(800, 600, 800, 600, macos=True), (768, 576))
        self.assertEqual(vis.visualizer_internal_size(128, 64, 128, 64, macos=True), (128, 64))
        self.assertEqual(
            vis.visualizer_internal_size(3024, 1964, 1512, 982, macos=True, fullscreen=True),
            (768, 499),
        )
        self.assertEqual(
            vis.visualizer_internal_size(3840, 2160, 3840, 2160, macos=True, fullscreen=True),
            (768, 432),
        )
        self.assertEqual(vis.macos_fullscreen_size(3024, 1964), (1920, 1080))
        self.assertEqual(vis.macos_fullscreen_size(1512, 982), (1512, 982))
        cols, rows = vis.macos_player_grid(1094, 734)
        self.assertEqual((cols, rows), (120, 40))

    def test_linux_visualizer_matches_the_liquid_player_window(self):
        self.assertEqual(vis.linux_liquid_player_window_size(), (1094, 778))
        self.assertEqual(vis.linux_liquid_player_window_size(char_w=13, char_h=30), (1574, 1258))
        tree = '\n'.join([
            '     0x1000007 "MP Audio Player (Liquid Glass - OpenGL)": ("mp_liquid" "MP_Liquid")  1574x1258+510+385  +510+385',
            '     0x2000001 "MP Mix Manager (Liquid Glass - OpenGL)": ("mp_liquid" "MP_Liquid")  800x600+10+10  +10+10',
            '     0x1000008 "MP Audio Player (Liquid Glass - OpenGL)": ("mp_liquid" "MP_Liquid")  680x266+20+20  +20+20',
        ])
        self.assertEqual(vis.parse_liquid_player_window_size(tree), (1574, 1258))
        self.assertIsNone(vis.parse_liquid_player_window_size(""))
        self.assertEqual(vis.linux_visualizer_window_size(tree), (1574, 1258))
        self.assertEqual(vis.linux_visualizer_window_size(""), (1094, 778))

    def test_linux_visualizer_started_by_mp_gui_matches_the_gui_window(self):
        tree = "\n".join([
            '     0x1000007 "MP Audio Player (Liquid Glass - OpenGL)": ("mp_liquid" "MP_Liquid")  680x266+20+20  +20+20',
            '     0x2000001 "MP Mix Manager (Liquid Glass - OpenGL)": ("mp_liquid" "MP_Liquid")  1574x1258+72+64  +72+64',
        ])
        self.assertEqual(vis.parse_liquid_gui_window_size(tree), (1574, 1258))
        self.assertEqual(vis.parse_liquid_player_window_size(tree), (680, 266))
        self.assertEqual(vis.linux_gui_visualizer_window_size(tree), (1574, 1258))
        self.assertEqual(vis.linux_visualizer_window_size(tree), (680, 266))
        previous = os.environ.get("MP_VISUALIZER_MATCH_GUI")
        os.environ["MP_VISUALIZER_MATCH_GUI"] = "1"
        try:
            self.assertTrue(vis.visualizer_matches_gui())
            self.assertEqual(vis.linux_visualizer_match_window_size(tree), (1574, 1258))
        finally:
            if previous is None:
                os.environ.pop("MP_VISUALIZER_MATCH_GUI", None)
            else:
                os.environ["MP_VISUALIZER_MATCH_GUI"] = previous
        self.assertEqual(vis.linux_visualizer_match_window_size(tree), (680, 266))
        gui = (BASE / "MP_Gui.sh").read_text(encoding="utf-8")
        self.assertIn("MP_VISUALIZER_MATCH_GUI=1", gui)
        for name in ("MP_Audio_Player_Liquid_Glass_OpenGL.py", "MP_Audio_Player_Liquid_Glass.py"):
            host = (BASE / name).read_text(encoding="utf-8")
            self.assertIn("publish_liquid_gui_window_size", host)

    def test_published_player_size_is_the_visualizer_size(self):
        previous = os.environ.get("MP_LIQUID_PLAYER_WINDOW_FILE")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "liquid_player_window.json"
            os.environ["MP_LIQUID_PLAYER_WINDOW_FILE"] = str(path)
            try:
                vis.publish_liquid_player_window_size(1574, 1258, pid=os.getpid())
                self.assertEqual(vis.read_published_player_window_size(), (1574, 1258))
                self.assertEqual(vis.linux_visualizer_window_size(), (1574, 1258))
                # A caller that already captured a window tree keeps that listing.
                self.assertEqual(vis.linux_visualizer_window_size(""), (1094, 778))
                gui_path = Path(directory) / "liquid_gui_window.json"
                os.environ["MP_LIQUID_GUI_WINDOW_FILE"] = str(gui_path)
                vis.publish_liquid_gui_window_size(1600, 1200, pid=os.getpid())
                self.assertEqual(vis.read_published_gui_window_size(), (1600, 1200))
                os.environ["MP_VISUALIZER_MATCH_GUI"] = "1"
                self.assertEqual(vis.linux_visualizer_match_window_size(), (1600, 1200))
                os.environ.pop("MP_VISUALIZER_MATCH_GUI", None)
                # The player lookup does not follow the MP Gui file.
                self.assertEqual(vis.linux_visualizer_window_size(), (1574, 1258))
                path.write_text(json.dumps({"width": 1574, "height": 1258, "pid": 99999999}) + "\n", encoding="utf-8")
                self.assertIsNone(vis.read_published_player_window_size())
            finally:
                os.environ.pop("MP_VISUALIZER_MATCH_GUI", None)
                os.environ.pop("MP_LIQUID_GUI_WINDOW_FILE", None)
                if previous is None:
                    os.environ.pop("MP_LIQUID_PLAYER_WINDOW_FILE", None)
                else:
                    os.environ["MP_LIQUID_PLAYER_WINDOW_FILE"] = previous

    def test_visualizer_waits_until_the_mapped_player_matches(self):
        previous = os.environ.get("MP_LIQUID_PLAYER_WINDOW_FILE")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "liquid_player_window.json"
            os.environ["MP_LIQUID_PLAYER_WINDOW_FILE"] = str(path)
            clock = {"t": 0.0, "wall": 1_000_000.0}
            trees = {
                "text": '0x1 "MP Audio Player (Liquid Glass - OpenGL)": ()  1094x778+10+10  +10+10',
            }

            def now():
                return clock["t"]

            def wall_now():
                return clock["wall"]

            def pause(seconds):
                clock["t"] += seconds
                clock["wall"] += seconds
                if clock["t"] >= 0.4:
                    trees["text"] = '0x1 "MP Audio Player (Liquid Glass - OpenGL)": ()  1574x1258+10+10  +10+10'

            try:
                vis.publish_liquid_player_window_size(1574, 1258, pid=os.getpid())
                # The file mtime is the real clock. Pin the record age to the fake clock.
                os.utime(path, (clock["wall"], clock["wall"]))
                found = vis.wait_for_published_player_window_size(
                    timeout=2.0,
                    idle_timeout=0.2,
                    stable_for=0.3,
                    require_mapped=True,
                    now=now,
                    wall_now=wall_now,
                    sleep=pause,
                    host_running=lambda: True,
                    read_tree=lambda: trees["text"],
                )
                self.assertEqual(found, (1574, 1258))
                self.assertGreaterEqual(clock["t"], 0.4)
            finally:
                if previous is None:
                    os.environ.pop("MP_LIQUID_PLAYER_WINDOW_FILE", None)
                else:
                    os.environ["MP_LIQUID_PLAYER_WINDOW_FILE"] = previous
                os.environ.pop("MP_LIQUID_GUI_WINDOW_FILE", None)

    def test_visualizer_waits_until_the_mapped_gui_matches(self):
        previous = os.environ.get("MP_LIQUID_GUI_WINDOW_FILE")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "liquid_gui_window.json"
            os.environ["MP_LIQUID_GUI_WINDOW_FILE"] = str(path)
            clock = {"t": 0.0, "wall": 1_000_000.0}
            trees = {
                "text": '0x1 "MP Audio Player (Liquid Glass - OpenGL)": ()  680x266+10+10  +10+10',
            }

            def now():
                return clock["t"]

            def wall_now():
                return clock["wall"]

            def pause(seconds):
                clock["t"] += seconds
                clock["wall"] += seconds
                if clock["t"] >= 0.4:
                    trees["text"] = '0x2 "MP Mix Manager (Liquid Glass - OpenGL)": ()  1574x1258+72+64  +72+64'

            try:
                vis.publish_liquid_gui_window_size(1574, 1258, pid=os.getpid())
                os.utime(path, (clock["wall"], clock["wall"]))
                found = vis.wait_for_published_gui_window_size(
                    timeout=2.0,
                    idle_timeout=0.2,
                    stable_for=0.3,
                    require_mapped=True,
                    now=now,
                    wall_now=wall_now,
                    sleep=pause,
                    host_running=lambda: True,
                    read_tree=lambda: trees["text"],
                )
                self.assertEqual(found, (1574, 1258))
                self.assertGreaterEqual(clock["t"], 0.4)
            finally:
                if previous is None:
                    os.environ.pop("MP_LIQUID_GUI_WINDOW_FILE", None)
                else:
                    os.environ["MP_LIQUID_GUI_WINDOW_FILE"] = previous
        # The second wait still sees the published file until the env is restored.
        # Re-run it with no file so an absent player does not invent a size.
        previous = os.environ.get("MP_LIQUID_PLAYER_WINDOW_FILE")
        with tempfile.TemporaryDirectory() as directory:
            os.environ["MP_LIQUID_PLAYER_WINDOW_FILE"] = str(Path(directory) / "missing.json")
            clock = {"t": 0.0}
            try:
                missing = vis.wait_for_published_player_window_size(
                    timeout=2.0,
                    idle_timeout=0.2,
                    stable_for=0.3,
                    require_mapped=False,
                    now=lambda: clock["t"],
                    wall_now=lambda: clock["t"],
                    sleep=lambda seconds: clock.__setitem__("t", clock["t"] + seconds),
                    host_running=lambda: False,
                    read_tree=lambda: "",
                )
            finally:
                if previous is None:
                    os.environ.pop("MP_LIQUID_PLAYER_WINDOW_FILE", None)
                else:
                    os.environ["MP_LIQUID_PLAYER_WINDOW_FILE"] = previous
        self.assertIsNone(missing)

    def test_vulkan_preset_is_folded_and_shipped(self):
        raw = (vis.ROOT / "shaders" / "mp_liquid_visualizer.frag").read_text(encoding="utf-8")
        folded = vis.specialize_vulkan_source(raw, 4, march_steps=64)
        self.assertNotIn("u.preset.x", folded)
        self.assertIn("(4.0)", folded)
        self.assertIn("u.preset.w", folded)
        self.assertIn("for (int i = 0; i < 64; i++)", folded)
        self.assertIn("u.preset.x", raw)
        digest = vis._visualizer_source_digest(raw)
        meta = vis._read_preset_manifest()
        self.assertEqual(meta.get("source"), digest)
        self.assertEqual(int(meta.get("steps", -1)), 64)
        for preset_id in range(10):
            path = vis.vulkan_preset_spirv(preset_id, march_steps=64)
            self.assertIsNotNone(path, f"preset {preset_id}")
            self.assertTrue(path.read_bytes().startswith(vis._SPIRV_MAGIC))

    def test_preset_is_folded_without_changing_the_shared_source(self):
        generic = vis.opengl_visualizer_source()
        folded = vis.specialize_visualizer_source(generic, 9, march_steps=64)
        self.assertIn("uniform vec4 u_preset", generic)
        self.assertIn("u_preset.x", generic)
        self.assertIn(vis._MARCH_LOOP, generic)
        self.assertNotIn("u_preset.x", folded)
        self.assertIn("(9.0)", folded)
        self.assertIn("u_preset.w", folded)
        self.assertIn("for (int i = 0; i < 64; i++)", folded)
        self.assertNotIn("for (int i = 0; i < 84; i++)", folded)

    def test_opengl_source_does_not_reuse_the_noise3_builtin(self):
        source = vis.opengl_visualizer_source()
        self.assertIn("float valueNoise3(", source)
        self.assertNotIn("noise3(", source)

    def test_opengl_shader_links_on_this_machine(self):
        if sys.platform != "darwin" and not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
            self.skipTest("no display")
        env = os.environ.copy()
        env["MP_LIQUID_VISUALIZER_STATE"] = str(self.state)
        result = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--compile-shader", str(self.state)],
            cwd=str(BASE),
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 3:
            self.skipTest(result.stderr.strip() or result.stdout.strip() or "OpenGL context was not created")
        self.assertEqual(result.returncode, 0, result.stdout + "\n" + result.stderr)
        self.assertIn("VISUALIZER_SHADER_OK", result.stdout)


def compile_visualizer_shader(state_path: str) -> int:
    """Link the player visualizer in a hidden OpenGL window and draw one pixel."""
    import ctypes
    from unittest.mock import MagicMock

    os.environ["MP_LIQUID_VISUALIZER_STATE"] = state_path
    # The liquid-glass host pins PyOpenGL to GLX. This hidden window is created
    # by GLFW, which may be EGL, so let PyOpenGL detect the current context.
    os.environ.pop("PYOPENGL_PLATFORM", None)
    vis._CACHE.update(path="", mtime=None, state=None)
    if sys.platform != "darwin" and not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        print("no display", file=sys.stderr)
        return 3
    from mp_liquid_visualizer_vulkan import load_glfw_dll
    from OpenGL import GL

    glfw = load_glfw_dll()
    glfw.glfwInit.restype = ctypes.c_int
    glfw.glfwWindowHint.argtypes = [ctypes.c_int, ctypes.c_int]
    glfw.glfwCreateWindow.restype = ctypes.c_void_p
    glfw.glfwCreateWindow.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_char_p, ctypes.c_void_p, ctypes.c_void_p]
    glfw.glfwMakeContextCurrent.argtypes = [ctypes.c_void_p]
    glfw.glfwDestroyWindow.argtypes = [ctypes.c_void_p]
    glfw.glfwTerminate.argtypes = []
    glfw.glfwDefaultWindowHints.argtypes = []
    if not glfw.glfwInit():
        print("GLFW did not start", file=sys.stderr)
        return 3
    window = None
    try:
        glfw.glfwDefaultWindowHints()
        glfw.glfwWindowHint(0x00022001, 0x00030001)
        glfw.glfwWindowHint(0x00022002, 3)
        glfw.glfwWindowHint(0x00022003, 3)
        glfw.glfwWindowHint(0x00022008, 0x00032001)
        glfw.glfwWindowHint(0x00020004, 0)
        glfw.glfwWindowHint(0x00020001, 0)
        glfw.glfwWindowHint(0x00020005, 0)
        window = glfw.glfwCreateWindow(64, 64, b"MP Visualizer shader check", None, None)
        if not window:
            print("OpenGL context was not created", file=sys.stderr)
            return 3
        glfw.glfwMakeContextCurrent(window)
        layer = vis.PlayerVisualizerLayer()
        layer._compile(GL, None)
        import numpy as np
        verts = np.array([
            -1, -1, 0, 0,
            1, -1, 1, 0,
            -1, 1, 0, 1,
            -1, 1, 0, 1,
            1, -1, 1, 0,
            1, 1, 1, 1,
        ], dtype=np.float32)
        vao = GL.glGenVertexArrays(1)
        vbo = GL.glGenBuffers(1)
        GL.glBindVertexArray(vao)
        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, vbo)
        GL.glBufferData(GL.GL_ARRAY_BUFFER, verts.nbytes, verts, GL.GL_STATIC_DRAW)
        GL.glEnableVertexAttribArray(0)
        GL.glVertexAttribPointer(0, 2, GL.GL_FLOAT, GL.GL_FALSE, 16, None)
        GL.glEnableVertexAttribArray(1)
        GL.glVertexAttribPointer(1, 2, GL.GL_FLOAT, GL.GL_FALSE, 16, ctypes.c_void_p(8))
        vis.write_player_visualizer_state(True, vis.preset_by_id(0))
        renderer = MagicMock()
        renderer._vao = vao
        if not layer.draw(renderer, 64, 64):
            print(layer._error or "draw failed", file=sys.stderr)
            return 1
        GL.glFinish()
        raw = bytes(GL.glReadPixels(32, 32, 1, 1, GL.GL_RGBA, GL.GL_UNSIGNED_BYTE))
        if len(raw) != 4 or max(raw[:3]) <= 0:
            print(f"visualizer pixel was empty: {raw!r}", file=sys.stderr)
            return 1
        print(f"VISUALIZER_SHADER_OK pixel={tuple(raw)}")
        return 0
    finally:
        if window:
            glfw.glfwDestroyWindow(window)
        glfw.glfwTerminate()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--compile-shader":
        raise SystemExit(compile_visualizer_shader(sys.argv[2] if len(sys.argv) > 2 else ""))
    unittest.main()
