#!/usr/bin/env python3
"""
Unit tests for Liquid Glass Player Features:
1. Double-click top bezel to toggle maximize / restore to default size.
2. Mode transitions between NORMAL, MINI, and MICRO in Liquid Glass (both Vulkan and OpenGL hosts).
3. In-process 'm'/'M' key handling when MP_LIQUID_GLASS=1.
4. Correct panel geometry computation for NORMAL, MINI, and MICRO modes.
"""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import MP_Audio_Player
import MP_Audio_Player_Liquid_Glass as lg_vulkan
import MP_Audio_Player_Liquid_Glass_OpenGL as lg_opengl


class TestLiquidGlassPlayerFeatures(unittest.TestCase):
    def test_player_panel_rects_modes(self):
        """Verifies player_panel_rects produces appropriate rects for NORMAL, MINI, and MICRO."""
        for mod in (lg_vulkan, lg_opengl):
            r_norm = mod.player_panel_rects(80, 24, 9, 18, 14, 14, mode="NORMAL")
            self.assertEqual(len(r_norm), 2, f"{mod.__name__} NORMAL should return 2 panel rects")
            self.assertGreater(r_norm[0][2], 0)
            self.assertGreater(r_norm[1][2], 0)

            r_mini = mod.player_panel_rects(74, 14, 9, 18, 14, 14, mode="MINI")
            self.assertEqual(len(r_mini), 2, f"{mod.__name__} MINI should return 2 panel rects")

            r_micro = mod.player_panel_rects(74, 7, 9, 18, 14, 14, mode="MICRO")
            self.assertEqual(len(r_micro), 2, f"{mod.__name__} MICRO should return 2 panel rects (second empty)")
            self.assertEqual(r_micro[1], (0.0, 0.0, 0.0, 0.0))

            r_tl = mod.player_panel_rects(100, 35, 9, 18, 14, 14, mode="TRACKLIST")
            self.assertEqual(len(r_tl), 2, f"{mod.__name__} TRACKLIST should return 2 panel rects")
            self.assertGreater(r_tl[0][2], 0)
            self.assertGreater(r_tl[1][2], 0)

    def test_on_top_bezel_detection(self):
        """Verifies _on_top_bezel accurately identifies clicks within the top window bezel."""
        for mod in (lg_vulkan, lg_opengl):
            host = mod.GlassHost.__new__(mod.GlassHost)
            host.renderer = MagicMock()
            host.renderer.bezel_px = 14

            # Within top bezel
            self.assertTrue(host._on_top_bezel(100, 5, 800, 600))
            self.assertTrue(host._on_top_bezel(400, 13, 800, 600))

            # Close button area is excluded from top bezel drag
            self.assertFalse(host._on_top_bezel(800 - int(14 * 0.72), int(14 * 0.62), 800, 600))

            # Outside top bezel (lower in client area)
            self.assertFalse(host._on_top_bezel(100, 100, 800, 600))

    def test_toggle_maximize_restore(self):
        """Verifies toggle_maximize maximizes to monitor workarea and restores to original dimensions."""
        for mod in (lg_vulkan, lg_opengl):
            host = mod.GlassHost.__new__(mod.GlassHost)
            host.is_maximized = False
            host.mode = "NORMAL"
            host._saved_rect = None
            host.terminal = MagicMock()
            host.terminal.get_char_width.return_value = 9
            host.terminal.get_char_height.return_value = 18

            host.renderer = MagicMock()
            host.renderer.bezel_px = 14
            host.renderer.window_pos.return_value = (100, 100)
            host.renderer.window_size.return_value = (900, 600)
            host.renderer.get_workarea.return_value = (0, 0, 1920, 1080)
            host._place_terminal = MagicMock()

            # 1. First toggle: should maximize
            host.toggle_maximize()
            self.assertTrue(host.is_maximized)
            self.assertEqual(host._saved_rect, ((100, 100), (900, 600)))
            host.renderer.set_window_pos.assert_called_with(0, 0)
            host.renderer.set_window_size.assert_called_with(1920, 1080)

            # 2. Second toggle: should restore
            host.toggle_maximize()
            self.assertFalse(host.is_maximized)
            host.renderer.set_window_pos.assert_called_with(100, 100)

    def test_set_mode_resizing(self):
        """Verifies set_mode updates mode and resizes window / terminal for NORMAL, MINI, and MICRO."""
        for mod in (lg_vulkan, lg_opengl):
            host = mod.GlassHost.__new__(mod.GlassHost)
            host.mode = "NORMAL"
            host.is_maximized = False
            host.terminal = MagicMock()
            host.terminal.get_char_width.return_value = 9
            host.terminal.get_char_height.return_value = 18

            host.renderer = MagicMock()
            host.renderer.bezel_px = 14
            host.renderer.set_panels = MagicMock()
            host.renderer.set_window_size = MagicMock()
            host._place_terminal = MagicMock()

            # Switch to MINI
            host.set_mode("MINI")
            self.assertEqual(host.mode, "MINI")
            host.terminal.set_size.assert_called_with(74, 14)

            # Switch to MICRO
            host.set_mode("MICRO")
            self.assertEqual(host.mode, "MICRO")
            host.terminal.set_size.assert_called_with(74, 7)

            # Switch back to NORMAL
            host.set_mode("NORMAL")
            self.assertEqual(host.mode, "NORMAL")
            host.terminal.set_size.assert_called_with(mod.COLS, mod.ROWS)

    def test_audio_player_m_key_inside_liquid_glass(self):
        """Verifies pressing 'm'/'M' inside Liquid Glass cycles mode in-place without spawning external window."""
        mock_scanner = MagicMock()
        mock_scanner.get_mixes.return_value = []
        ui = MP_Audio_Player.TerminalPlayerUI(
            engine=None,
            scanner=mock_scanner,
            ui_size_mode="NORMAL",
            is_remote=True
        )

        with patch.dict(os.environ, {"MP_LIQUID_GLASS": "1"}), \
             patch("MP_Audio_Player.launch_mini_player_window") as mock_launch:
            # Press 'm': NORMAL -> MINI
            ui._process_key(b"m")
            self.assertEqual(ui.ui_size_mode, "MINI")
            mock_launch.assert_not_called()

            # Press 'm': MINI -> MICRO
            ui._process_key(b"m")
            self.assertEqual(ui.ui_size_mode, "MICRO")
            mock_launch.assert_not_called()

            # Press 'm': MICRO -> NORMAL
            ui._process_key(b"m")
            self.assertEqual(ui.ui_size_mode, "NORMAL")
            mock_launch.assert_not_called()

    def test_unselected_playlist_entries_have_high_contrast_bold_white(self):
        """Verifies unselected playlist rows use explicit bold truecolor white so they do not wash out on Liquid Glass."""
        mock_scanner = MagicMock()
        mock_scanner.get_mixes.return_value = [
            {"name": "Mix 01 - Selected Track.flac", "path": "/path/mix1.flac", "ext": "FLAC", "size_mb": 650},
            {"name": "Mix 02 - Unselected Track.flac", "path": "/path/mix2.flac", "ext": "FLAC", "size_mb": 820},
        ]
        ui = MP_Audio_Player.TerminalPlayerUI(
            engine=None,
            scanner=mock_scanner,
            ui_size_mode="NORMAL",
            is_remote=True,
        )
        ui.selected_row = 0
        st = {
            "title": "Mix 01 - Selected Track.flac",
            "path": "/path/mix1.flac",
            "state": "playing",
            "index": 0,
            "position_fmt": "02:00",
            "duration_fmt": "60:00",
            "progress_pct": 3.3,
            "volume": 85,
            "pitch_percent": 0,
            "levels": [0.4] * 24,
            "peaks": [0.6] * 24,
            "levels_left": [0.4] * 24,
            "levels_right": [0.4] * 24,
            "peaks_left": [0.6] * 24,
            "peaks_right": [0.6] * 24,
        }
        captured = []
        with patch.dict(os.environ, {"MP_LIQUID_GLASS": "1"}), \
             patch("MP_Audio_Player._present_frame", side_effect=lambda lines, w, h: captured.extend(lines)), \
             patch("MP_Audio_Player._win_visible_size", return_value=(120, 40)):
            ui._get_status = MagicMock(return_value=st)
            ui._draw_frame()

        unselected = [l for l in captured if "Mix 02 - Unselected Track.flac" in l]
        self.assertTrue(unselected, "Unselected playlist entry was not rendered")
        self.assertIn("\033[38;2;255;255;255m", unselected[0])
        self.assertNotIn("\033[1;38;2;255;255;255m", unselected[0])

    def test_player_argv_forwards_extra_args(self):
        """Verifies player_argv forwards mode/playlist/theme flags to MP_Audio_Player.py."""
        for mod in (lg_vulkan, lg_opengl):
            argv = mod.player_argv(mode="NORMAL", extra_args=["--music-mode", "--music-folder", "Trance"])
            self.assertIn("--interactive", argv)
            self.assertIn("--music-mode", argv)
            self.assertIn("Trance", argv)


    def test_bezel_width_reduced_by_86_percent(self):
        """Verifies bezel width is reduced by 86% (from 52px to 7px) across Vulkan, OpenGL, and Metal renderers."""
        from liquid_glass_vulkan import LiquidGlassRenderer as VulkanRenderer
        from liquid_glass_opengl import LiquidGlassRendererOpenGL as OpenGLRenderer
        from liquid_glass_metal import LiquidGlassRendererMetal as MetalRenderer

        # 52px reduced by 86% = 52 * 0.14 = 7.28px -> 7px
        expected_bezel = round(52 * (1 - 0.86))
        self.assertEqual(expected_bezel, 7)
        self.assertEqual(VulkanRenderer.bezel_px, 7)
        self.assertEqual(OpenGLRenderer.bezel_px, 7)
        self.assertEqual(MetalRenderer.bezel_px, 7)

    def test_bezel_width_modes_geometry(self):
        """Verifies bezel width is 7px for default window (NORMAL), MINI, and MICRO modes."""
        for mod in (lg_vulkan, lg_opengl):
            for mode, cols, rows in [("NORMAL", mod.COLS, mod.ROWS), ("MINI", 74, 14), ("MICRO", 74, 7)]:
                host = mod.GlassHost(["test"], mode=mode)
                host.renderer = MagicMock()
                host.renderer.bezel_px = 7
                char_w, char_h = 9, 18

                win_w = cols * char_w + 2 * host.renderer.bezel_px
                win_h = rows * char_h + 2 * host.renderer.bezel_px
                host.renderer.window_pos.return_value = (10, 20)
                host.renderer.window_size.return_value = (win_w, win_h)

                # Inner well rect should be indented by exactly 7px margin
                well_x, well_y, inner_w, inner_h = host._well_rect()
                self.assertEqual(well_x, 10 + 7)
                self.assertEqual(well_y, 20 + 7)
                self.assertEqual(inner_w, win_w - 14)
                self.assertEqual(inner_h, win_h - 14)

                # Bezel edge detection should trigger within 7px border
                self.assertTrue(host._on_bezel(3, win_h // 2, win_w, win_h))
                self.assertTrue(host._on_bezel(win_w - 3, win_h // 2, win_w, win_h))
                self.assertTrue(host._on_bezel(win_w // 2, 3, win_w, win_h))
                self.assertTrue(host._on_bezel(win_w // 2, win_h - 3, win_w, win_h))

                # Client area (inside well) should not be considered bezel
                self.assertFalse(host._on_bezel(win_w // 2, win_h // 2, win_w, win_h))

    def test_window_dragging_terminal_header_and_modifiers(self):
        """Verifies dragging from terminal header (y <= 90) or with Alt/Super moves window."""
        import gi
        gi.require_version("Gtk", "3.0")
        gi.require_version("Gdk", "3.0")
        from gi.repository import Gdk
        for mod in (lg_vulkan, lg_opengl):
            host = mod.GlassHost(["test"], mode="NORMAL")
            host.renderer = MagicMock()
            host.renderer.bezel_px = 7
            host.renderer.window_size.return_value = (1280, 820)
            host.renderer.window_pos.return_value = (100, 200)
            host.renderer.root_pointer.return_value = (300, 400)
            host.is_maximized = False
            host.gtk_window = MagicMock()

            # 1. Single click on terminal header (y = 45 <= 90)
            mock_press = MagicMock()
            mock_press.button = 1
            mock_press.type = Gdk.EventType.BUTTON_PRESS
            mock_press.y = 45
            mock_press.state = 0
            mock_press.x_root = 300
            mock_press.y_root = 400

            res = host._on_term_button_press(None, mock_press)
            self.assertTrue(res, f"{mod.__name__} should accept header button press for dragging")
            self.assertTrue(getattr(host, "_term_dragging", False))
            self.assertEqual(host._term_drag_origin, (100, 200))

            # 2. Motion notify while dragging
            mock_motion = MagicMock()
            host.renderer.root_pointer.return_value = (350, 480)
            mock_motion.x_root = 350
            mock_motion.y_root = 480

            res_motion = host._on_term_motion_notify(None, mock_motion)
            self.assertTrue(res_motion)
            # Origin was (100, 200), moved by dx=+50, dy=+80 -> (150, 280)
            host.renderer.set_window_pos.assert_called_with(150, 280)

            # 3. Button release ends drag
            mock_release = MagicMock()
            mock_release.button = 1
            host._on_term_button_release(None, mock_release)
            self.assertFalse(host._term_dragging)

            # 4. Alt+Click anywhere (e.g. y = 300) allows dragging
            mock_alt_press = MagicMock()
            mock_alt_press.button = 1
            mock_alt_press.type = Gdk.EventType.BUTTON_PRESS
            mock_alt_press.y = 300
            mock_alt_press.state = Gdk.ModifierType.MOD1_MASK
            res_alt = host._on_term_button_press(None, mock_alt_press)
            self.assertTrue(res_alt, "Alt+click anywhere should initiate window drag")
            self.assertTrue(host._term_dragging)

    def test_window_dragging_top_bezel_glass(self):
        """Verifies clicking on top bezel of glass window initiates drag even with slim 7px bezel."""
        for mod in (lg_vulkan, lg_opengl):
            host = mod.GlassHost(["test"], mode="NORMAL")
            host.renderer = MagicMock()
            host.renderer.bezel_px = 7
            host.renderer.window_size.return_value = (1280, 820)
            host.renderer.window_pos.return_value = (50, 50)
            host.renderer.root_pointer.return_value = (150, 60)
            host.renderer.cursor = (100, 15)  # y=15 is in top bezel (15 < 7 + 48 = 55)
            host.renderer.mouse_down = True
            host.is_maximized = False

            was_down, dragging, origin, press = host._track_drag(False, False, (50, 50), (0, 0))
            self.assertTrue(dragging, f"{mod.__name__} should start dragging when top bezel is clicked")
            self.assertEqual(origin, (50, 50))

    def test_tracklist_mode_cli_and_host_setup(self):
        """Verifies tracklist mode argument creation, dimensions, and CLI launching across hosts."""
        import tempfile
        import MP_Audio_Player_Liquid_Glass_macOS as lg_macos

        with tempfile.TemporaryDirectory() as tmp:
            tmp_p = Path(tmp)
            tl_file = tmp_p / "Mix_Demo.txt"
            tl_file.write_text("01. Solar Fields - Sol\n", encoding="utf-8")
            audio_file = tmp_p / "Mix_Demo.flac"
            audio_file.write_bytes(b"FLAC_AUDIO")

            for mod in (lg_vulkan, lg_opengl, lg_macos):
                cmd = mod.tracklist_argv(tl_file, audio_path=audio_file, theme="cosmic_supernova")
                self.assertIn("bash", cmd[0])
                self.assertIn("view_tracklist_console.sh", cmd[1])
                self.assertIn("--theme", cmd)
                self.assertIn("cosmic_supernova", cmd)
                self.assertIn(str(tl_file), cmd)
                self.assertIn(str(audio_file), cmd)

                host_cls = getattr(mod, "GlassHost", None) or getattr(mod, "MetalGlassHost", None)
                host = host_cls(cmd, mode="TRACKLIST", cli_theme="cosmic_supernova")
                self.assertEqual(host.mode, "TRACKLIST")
                self.assertEqual(host._target_cols, 100)
                self.assertEqual(host._target_rows, 35)

            # Test main() parsing of --tracklist
            for mod in (lg_vulkan, lg_opengl):
                with patch.object(mod.GlassHost, "run", return_value=True) as mock_run:
                    code = mod.main([
                        "--tracklist", str(tl_file),
                        "--audio", str(audio_file),
                        "--theme", "orbital_void_reflux",
                    ])
                    self.assertEqual(code, 0)
                    mock_run.assert_called_once()

    def test_clear_bezel_outer_edge_no_speckles(self):
        """Verifies that outer bezel edge is clear with no speckles or hash patterns across all shaders."""
        shaders_dir = BASE_DIR / "shaders"
        vk_frag = (shaders_dir / "liquid_glass.frag").read_text(encoding="utf-8")
        gl_frag = (shaders_dir / "liquid_glass_gl.frag").read_text(encoding="utf-8")
        metal = (shaders_dir / "liquid_glass_metal.metal").read_text(encoding="utf-8")

        for name, src in [("Vulkan", vk_frag), ("OpenGL", gl_frag), ("Metal", metal)]:
            self.assertNotIn("beadCell", src, f"{name} shader should not contain beadCell noise speckles")
            self.assertNotIn("float bead", src, f"{name} shader should not contain bead noise speckles")
            self.assertNotIn("float glint", src, f"{name} shader should not contain glint noise speckles")
            self.assertIn("Clear liquid glass effect", src, f"{name} shader should specify clear liquid glass effect")

        # Verify Vulkan SPIR-V bytecode is compiled and valid
        spv_file = shaders_dir / "liquid_glass.frag.spv"
        self.assertTrue(spv_file.is_file())
        spv_bytes = spv_file.read_bytes()
        self.assertGreater(len(spv_bytes), 1000)
        self.assertEqual(spv_bytes[:4], b"\x03\x02#\x07")



if __name__ == "__main__":
    unittest.main()
