"""MP Mix Manager GUI: Retro Linux Memories theme, menu option 36, and shutdown."""

import os
import signal
import stat
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import liquid_visualizer_session as vis_session
from liquid_glass_metal import theme_rgb as metal_theme_rgb
from liquid_glass_opengl import theme_rgb as opengl_theme_rgb
from liquid_glass_vulkan import theme_rgb as vulkan_theme_rgb

CHARCOAL = ((45, 45, 45), (21, 83, 158), (26, 30, 33))
MANAGER_THEMES = (
    "stream_of_frequency",
    "dreamworlds",
    "cosmic_dreamworlds",
    "cosmic_dreamworlds_radioactive",
    "orbital_void_reflux",
    "dynamic_rainbow_liquid_glass",
    "dreamworlds_liquid",
    "dreamworlds_ultra",
    "cosmic_supernova",
    "retro_linux_memories",
    "retro_terminal",
    "dracula",
    "nord",
    "matrix",
    "solarized",
    "tokyo",
    "monokai",
    "gruvbox",
    "emerald",
    "classic",
    "cyberpunk",
)


class TestCharcoalVaultTheme(unittest.TestCase):
    def test_glass_palettes_match_the_veracrypt_screenshot(self):
        for theme_rgb in (opengl_theme_rgb, vulkan_theme_rgb, metal_theme_rgb):
            self.assertEqual(theme_rgb("retro_linux_memories"), CHARCOAL)
            self.assertEqual(theme_rgb("Retro Linux Memories"), CHARCOAL)
            self.assertEqual(theme_rgb("veracrypt"), CHARCOAL)
            self.assertEqual(theme_rgb("charcoal_vault"), CHARCOAL)

    def test_builtin_manager_themes_resolve_to_their_own_glass(self):
        ultra = opengl_theme_rgb("dreamworlds_ultra")
        for name in MANAGER_THEMES:
            colors = opengl_theme_rgb(name)
            self.assertEqual(len(colors), 3)
            self.assertTrue(all(len(rgb) == 3 for rgb in colors))
            if name not in ("dreamworlds", "dreamworlds_ultra", "default"):
                self.assertNotEqual(colors, ultra, name)


class TestManagerMenu(unittest.TestCase):
    def test_option_36_launches_the_gui_without_moving_exit(self):
        text = (ROOT / "Mix_Archive_Manager.sh").read_text(encoding="utf-8")
        self.assertIn(
            "36|MP Mix Manager GUI|(Liquid Glass window • MP Liquid Player interface • Retro Linux Memories and built-in themes)",
            text,
        )
        self.assertLess(
            text.index('"MP|MP GUI Mix Manager (New)|(Press G • Liquid Glass window • runs MP Gui)"'),
            text.index('"0|Run Any Desktop Shortcuts|'),
        )
        self.assertIn(
            'MP|"MP GUI Mix Manager (New)"*) launch_mp_gui_from_menu',
            text,
        )
        self.assertIn('36|mp-gui|gui|MP_Gui|g|G|"MP Mix Manager GUI"*) launch_mp_gui_from_menu', text)
        self.assertIn("launch_mp_gui_from_menu", text)
        self.assertIn('CURRENT_THEME="retro_linux_memories"', text)
        self.assertNotIn('CURRENT_THEME="charcoal_vault"', text)
        self.assertNotIn("23|Charcoal Vault", text)
        self.assertIn("MP_GUI_SESSION", text)
        self.assertIn("37|77|", text)
        self.assertNotIn("36|77|", text)
        self.assertIn("between 0 and 37", text)

    def test_shell_parses(self):
        result = subprocess.run(
            ["bash", "-n", str(ROOT / "Mix_Archive_Manager.sh")],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


class TestGuiThemeKey(unittest.TestCase):
    def test_c_cycles_the_same_theme_list_as_the_player(self):
        text = (ROOT / "Mix_Archive_Manager.sh").read_text(encoding="utf-8")
        start = text.index("cycle_menu_theme() {")
        end = text.index("_sync_btop_theme()", start)
        fn = text[start:end]
        self.assertIn("save_theme", fn)
        self.assertIn('cycle_menu_theme; last_term_lines=0', text)
        self.assertIn("[C] Theme", text)
        script = fn + """
save_theme() { printf '%s\\n' "$1"; }
CURRENT_THEME=retro_linux_memories
cycle_menu_theme
CURRENT_THEME=dracula
cycle_menu_theme
CURRENT_THEME=dreamworlds
cycle_menu_theme
CURRENT_THEME=retro_terminal
cycle_menu_theme
"""
        result = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout.splitlines(),
            [
                "stream_of_frequency",
                "retro_studio",
                "dynamic_rainbow_liquid_glass",
                "cosmic_dreamworlds_radioactive",
            ],
        )


class TestGuiLauncher(unittest.TestCase):
    def test_manager_sh_opens_the_gui(self):
        text = (ROOT / "manager.sh").read_text(encoding="utf-8")
        self.assertIn('exec bash "MP_Gui.sh" "$@"', text)
        self.assertLess(
            text.index('exec bash "MP_Gui.sh" "$@"'),
            text.index('exec bash "Mix_Archive_Manager.sh" "$@"'),
        )
        result = subprocess.run(
            ["bash", "-n", str(ROOT / "manager.sh")],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_mp_gui_starts_the_manager_host(self):
        path = ROOT / "MP_Gui.sh"
        self.assertTrue(path.is_file())
        mode = path.stat().st_mode
        self.assertTrue(mode & stat.S_IXUSR)
        text = path.read_text(encoding="utf-8")
        self.assertIn("--manager", text)
        self.assertIn("retro_linux_memories", text)
        self.assertNotIn("charcoal_vault", text)
        self.assertIn("--keep-theme", text)
        self.assertIn('MP Mix Manager (Liquid Glass', text)
        result = subprocess.run(["bash", "-n", str(path)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_hosts_stop_playback_and_the_visualizer_for_the_manager(self):
        for name in (
            "MP_Audio_Player_Liquid_Glass_OpenGL.py",
            "MP_Audio_Player_Liquid_Glass.py",
            "MP_Audio_Player_Liquid_Glass_macOS.py",
            "MP_Audio_Player_Liquid_Glass_OpenGL_macOS.py",
        ):
            text = (ROOT / name).read_text(encoding="utf-8")
            self.assertIn('os.environ["MP_GUI_SESSION"] = "1"', text)
            self.assertIn("stop_companion_playback()", text)
            self.assertIn("stop_companion_visualizer(force=True)", text)
            self.assertIn("stop_companion_visualizer()", text)


class TestGuiDoesNotBlockLiquidPlayer(unittest.TestCase):
    def test_manager_host_is_not_counted_as_the_player(self):
        script = r"""
        set -e
        export HOME="$(mktemp -d)"
        eval "$(sed -n '/^_liquid_glass_claim_launch() {/,/^}/p' Mix_Archive_Manager.sh)"
        eval "$(sed -n '/^_liquid_glass_release_launch() {/,/^}/p' Mix_Archive_Manager.sh)"
        pgrep() { printf '%s\n' "4242 python3 MP_Audio_Player_Liquid_Glass_OpenGL.py --manager"; }
        if _liquid_glass_claim_launch; then echo GUI:YES; else echo GUI:NO; fi
        _liquid_glass_release_launch
        pgrep() { printf '%s\n' "5252 python3 MP_Audio_Player_Liquid_Glass_OpenGL.py"; }
        if _liquid_glass_claim_launch; then echo PLAYER:YES; else echo PLAYER:NO; fi
        rm -rf "$HOME"
        """
        res = subprocess.run(
            ["bash", "-c", script],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=20,
        )
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("GUI:YES", res.stdout)
        self.assertIn("PLAYER:NO", res.stdout)

    def test_gui_startup_does_not_open_the_player(self):
        script = r"""
        set -e
        export HOME="$(mktemp -d)"
        export MP_GUI_SESSION=1
        eval "$(sed -n '/^_open_startup_audio_windows() {/,/^}/p' Mix_Archive_Manager.sh)"
        launch_mp_audio_player_liquid_glass() { echo LAUNCH; }
        execute_startup_autoplay() { echo AUTOPLAY; }
        _open_startup_audio_windows
        rm -rf "$HOME"
        """
        res = subprocess.run(
            ["bash", "-c", script],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=20,
        )
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertNotIn("LAUNCH", res.stdout)
        self.assertNotIn("AUTOPLAY", res.stdout)

    def test_launchers_ignore_the_manager_host(self):
        for name in ("scripts/launch-liquid-glass", "scripts/launch_liquid_glass.sh"):
            text = (ROOT / name).read_text(encoding="utf-8")
            self.assertIn("*--manager*) continue", text)
            self.assertNotIn('pgrep -f "MP_Audio_Player_Liquid_Glass"', text)

    def test_g_on_the_menu_launches_mp_gui(self):
        text = (ROOT / "Mix_Archive_Manager.sh").read_text(encoding="utf-8")
        start = text.index("CHAR:g|CHAR:G)")
        arm = text[start:text.index(";;", start)]
        self.assertIn("launch_mp_gui_from_menu", arm)
        self.assertIn("search_mode", arm)
        script = """
        launch_mp_gui_from_menu() { echo LAUNCH; }
        _find_menu_search_match() { echo "SEARCH:$1"; }
        _last_menu_frame=keep
        _MENU_FRAME_FRESH=1
        search_mode=0
        search_query=""
        key_action="CHAR:g"
        attempts=0
        while [ "$attempts" -lt 1 ]; do
            attempts=$((attempts + 1))
            case "$key_action" in
            __ARM__ ;;
            *) echo NOMATCH ;;
            esac
            echo FELL_LAUNCH
            break
        done
        echo "FRAME:$_last_menu_frame"
        search_mode=1
        key_action="CHAR:G"
        attempts=0
        while [ "$attempts" -lt 1 ]; do
            attempts=$((attempts + 1))
            case "$key_action" in
            __ARM__ ;;
            *) echo NOMATCH ;;
            esac
            echo FELL_SEARCH
            break
        done
        """.replace("__ARM__", arm)
        result = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("LAUNCH", result.stdout)
        self.assertNotIn("FELL_LAUNCH", result.stdout)
        self.assertIn("FRAME:", result.stdout)
        self.assertNotIn("keep", result.stdout.split("FRAME:", 1)[-1].splitlines()[0])
        self.assertIn("SEARCH:G", result.stdout)
        self.assertNotIn("FELL_SEARCH", result.stdout)
        self.assertEqual(result.stdout.count("LAUNCH"), 1)

    def test_l_from_the_gui_opens_a_separate_player(self):
        text = (ROOT / "Mix_Archive_Manager.sh").read_text(encoding="utf-8")
        self.assertIn('CHAR:l|CHAR:L)', text)
        self.assertIn("[lL]) launch_mp_audio_player_liquid_glass", text)
        self.assertIn('"${MP_GUI_SESSION:-0}" = "1"', text)
        self.assertIn("env -u MP_GUI_SESSION", text)


class TestGuiEscapeAndPlayerFocus(unittest.TestCase):
    def test_escape_on_the_main_menu_closes_only_the_gui(self):
        text = (ROOT / "Mix_Archive_Manager.sh").read_text(encoding="utf-8")
        self.assertIn(
            'ESC) [ "${MP_GUI_SESSION:-0}" = "1" ] && exit_mix_manager ;;',
            text,
        )
        self.assertIn('0|[qQ]|[eE][xX][iI][tT]|ESC) return 0 ;;', text)
        self.assertIn('_menu_exit_hint="q or Esc to close"', text)
        script = r"""
        exit_mix_manager() { echo EXIT; }
        choice=ESC
        MP_GUI_SESSION=1
        case $choice in
        ESC) [ "${MP_GUI_SESSION:-0}" = "1" ] && exit_mix_manager ;;
        esac
        echo DONE
        MP_GUI_SESSION=0
        case $choice in
        ESC) [ "${MP_GUI_SESSION:-0}" = "1" ] && exit_mix_manager ;;
        esac
        echo STAY
        """
        result = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), ["EXIT", "DONE", "STAY"])

    def test_gui_launch_gives_the_player_mouse_focus(self):
        text = (ROOT / "Mix_Archive_Manager.sh").read_text(encoding="utf-8")
        self.assertIn("MP_TAKE_MOUSE_FOCUS=1", text)
        self.assertIn("scripts/window_mouse_focus.py", text)
        start = text.index("# Inside MP Gui the manager is the VTE child.")
        block = text[start:text.index("launch_liquid_glass_from_menu()", start)]
        self.assertIn("MP_TAKE_MOUSE_FOCUS=1", block)
        self.assertIn("_focus_mp_liquid_player", block)
        for name in (
            "MP_Audio_Player_Liquid_Glass_OpenGL.py",
            "MP_Audio_Player_Liquid_Glass.py",
        ):
            host = (ROOT / name).read_text(encoding="utf-8")
            self.assertIn("MP_TAKE_MOUSE_FOCUS", host)
            self.assertIn("take_mouse_focus", host)
            self.assertIn("arm_escape_close", host)

    def test_mouse_focus_targets_the_player_and_warps_into_the_terminal(self):
        from unittest.mock import Mock

        import window_mouse_focus as focus

        rows = focus.parse_wmctrl_lp(
            "0x01000001  0 10 host MP Mix Manager (Liquid Glass - OpenGL)\n"
            "0x01000002  0 20 host MP Audio Player (Liquid Glass - OpenGL)\n"
            "0x01000003  0 20 host \n"
        )
        self.assertEqual(focus.choose_focus_target(rows), (0x01000002, 0x01000003))
        self.assertEqual(focus.choose_focus_target(rows[:1]), (0, 0))

        x11 = Mock()

        def fill(_display, _window, _root, _x, _y, width, height, _border, _depth):
            width._obj.value = 180
            height._obj.value = 90
            return 1

        x11.XGetGeometry.side_effect = fill
        self.assertTrue(focus.stack_and_point(x11, object(), 0x01000002, 0x01000003, warp=True))
        raised = [int(call.args[1].value) for call in x11.XRaiseWindow.call_args_list]
        self.assertEqual(raised, [0x01000002, 0x01000003])
        focused = int(x11.XSetInputFocus.call_args.args[1].value)
        self.assertEqual(focused, 0x01000003)
        warp = x11.XWarpPointer.call_args.args
        self.assertEqual(int(warp[2].value), 0x01000003)
        self.assertEqual((warp[7], warp[8]), (90, 45))


class TestGuiShutdown(unittest.TestCase):
    @patch("liquid_visualizer_session._signal_visualizer")
    @patch("liquid_visualizer_session._alive", return_value=False)
    @patch("liquid_visualizer_session.visualizer_pids", return_value=[4242])
    @patch("liquid_visualizer_session.other_liquid_player_running", return_value=True)
    def test_forced_close_stops_the_visualizer_while_another_host_is_open(self, _other, _pids, _alive, signal_vis):
        vis_session.stop_companion_visualizer(force=True)
        signal_vis.assert_called_once_with(4242, signal.SIGTERM)

    @patch("liquid_visualizer_session._signal_visualizer")
    @patch("liquid_visualizer_session._playback_engine_pids", return_value=[5150])
    @patch("liquid_visualizer_session._send_player_stop")
    @patch("liquid_visualizer_session._alive", return_value=False)
    def test_gui_close_stops_playback_engines(self, _alive, send_stop, _pids, signal_vis):
        vis_session.stop_companion_playback()
        send_stop.assert_called_once_with()
        signal_vis.assert_called_once_with(5150, signal.SIGTERM)


if __name__ == "__main__":
    unittest.main()
