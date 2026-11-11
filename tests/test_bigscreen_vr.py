#!/usr/bin/env python3
"""Bigscreen VR mode is Windows-only and uses its own window layout."""

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from bigscreen_vr import (  # noqa: E402
    REFUSAL_MESSAGE,
    VR_THEME,
    enter_vr_mode,
    find_bigscreen_exe,
    is_microsoft_windows,
    steam_library_roots,
    vr_layout,
)


def _touch_exe(folder: Path, name: str = "Bigscreen.exe") -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    exe = folder / name
    exe.write_text("", encoding="utf-8")
    return exe


class TestBigscreenLookup(unittest.TestCase):
    def test_linux_is_not_microsoft_windows(self):
        self.assertFalse(is_microsoft_windows("linux"))
        self.assertTrue(is_microsoft_windows("win32"))
        self.assertTrue(is_microsoft_windows("windows"))

    def test_steam_libraryfolders_path(self):
        roots = steam_library_roots('"path"\t\t"D:\\\\SteamLibrary"\n')
        self.assertEqual(str(roots[0]).replace("\\", "/"), "D:/SteamLibrary")

    def test_finds_default_steam_install(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            exe = _touch_exe(root / "Program Files (x86)" / "Steam" / "steamapps" / "common" / "Bigscreen")
            found = find_bigscreen_exe([root])
            self.assertEqual(found, exe)

    def test_finds_steam_library_on_another_drive(self):
        with tempfile.TemporaryDirectory() as tmp:
            library = Path(tmp) / "SteamLibrary"
            exe = _touch_exe(library / "steamapps" / "common" / "BigScreen", "BigScreen.exe")
            vdf = f'"path"\t\t"{library.as_posix()}"\n'
            found = find_bigscreen_exe([], [vdf])
            self.assertEqual(found, exe)

    def test_finds_oculus_install(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / "Program Files (x86)" / "Oculus" / "Software" / "Software" / "bigscreen-bigscreen" / "Bigscreen"
            exe = _touch_exe(folder)
            found = find_bigscreen_exe([root])
            self.assertEqual(found, exe)

    def test_registry_install_location(self):
        with tempfile.TemporaryDirectory() as tmp:
            exe = _touch_exe(Path(tmp))
            found = find_bigscreen_exe([], [], [tmp])
            self.assertEqual(found, exe)


class TestVrLayout(unittest.TestCase):
    def test_player_is_centered_and_visualizer_is_the_backdrop(self):
        layout = vr_layout(0, 0, 1920, 1080, "opengl")
        px, py, pw, ph = layout["player"]
        vx, vy, side, side_h = layout["visualizer"]
        self.assertEqual(layout["theme"], VR_THEME)
        self.assertEqual(side, side_h)
        self.assertGreater(side, pw)
        self.assertGreater(side, ph)
        self.assertEqual(px + pw // 2, vx + side // 2)
        self.assertEqual(py + ph // 2, vy + side // 2)
        self.assertEqual((px, py, pw, ph), (575, 277, 770, 526))
        self.assertEqual((vx, vy, side), (444, 24, 1032))

    def test_visualizer_stays_behind_the_player_on_a_small_screen(self):
        layout = vr_layout(100, 40, 800, 600, "opengl")
        _px, _py, pw, ph = layout["player"]
        _vx, _vy, side, _side_h = layout["visualizer"]
        self.assertGreater(side, pw)
        self.assertGreater(side, ph)
        self.assertEqual(layout["player"][0] + pw // 2, layout["visualizer"][0] + side // 2)
        self.assertEqual(layout["player"][1] + ph // 2, layout["visualizer"][1] + side // 2)


class TestEnterVrMode(unittest.TestCase):
    def test_refuses_unless_windows_and_bigscreen_are_both_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            exe = _touch_exe(Path(tmp) / "Bigscreen")
            self.assertEqual(enter_vr_mode(ROOT, platform_name="linux", bigscreen_exe=exe), 1)
            self.assertEqual(enter_vr_mode(ROOT, platform_name="windows", bigscreen_exe=None), 1)
            missing = Path(tmp) / "missing" / "Bigscreen.exe"
            self.assertEqual(enter_vr_mode(ROOT, platform_name="windows", bigscreen_exe=missing), 1)

    def test_refusal_message_is_the_same_every_time(self):
        from io import StringIO
        from contextlib import redirect_stdout
        buf = StringIO()
        with redirect_stdout(buf):
            enter_vr_mode(ROOT, platform_name="linux", bigscreen_exe=None)
            enter_vr_mode(ROOT, platform_name="windows", bigscreen_exe=None)
        self.assertIn(REFUSAL_MESSAGE, buf.getvalue())
        self.assertEqual(buf.getvalue().count(REFUSAL_MESSAGE), 2)
        self.assertIn("Microsoft Windows", REFUSAL_MESSAGE)
        self.assertIn("Bigscreen VR installed already", REFUSAL_MESSAGE)

    def test_windows_launch_sets_theme_and_vr_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            exe = _touch_exe(Path(tmp) / "Bigscreen")
            config = Path(tmp) / "config"
            calls = []

            def spawn(command, env, cwd, log_path):
                calls.append((list(command), dict(env), Path(cwd)))

            code = enter_vr_mode(
                ROOT,
                platform_name="windows",
                bigscreen_exe=exe,
                screen=(0, 0, 1920, 1080),
                config_dir=config,
                spawn=spawn,
                sleeper=lambda _seconds: None,
            )
            self.assertEqual(code, 0)
            self.assertEqual((config / "theme").read_text(encoding="utf-8").strip(), VR_THEME)
            self.assertEqual(len(calls), 3)
            visualizer, player, bigscreen = calls
            self.assertTrue(any("MP_Liquid_Visualizer" in part or "mp_liquid_visualizer" in part for part in visualizer[0]))
            self.assertEqual(visualizer[1]["MP_VR_LAYOUT"], "1")
            self.assertEqual(visualizer[1]["MP_VR_VISUALIZER_SIZE"], "1032")
            self.assertEqual(visualizer[1]["MP_VR_VISUALIZER_X"], "444")
            self.assertIn("--theme", player[0])
            self.assertIn(VR_THEME, player[0])
            self.assertIn("--no-visualizer", player[0])
            self.assertEqual(player[1]["MP_VR_PLAYER_X"], "575")
            self.assertEqual(player[1]["MP_VR_PLAYER_Y"], "277")
            self.assertEqual(player[1]["MP_VR_PLAYER_COLS"], "84")
            self.assertEqual(bigscreen[0], [str(exe)])
            self.assertEqual(bigscreen[2], exe.parent)


class TestMenuAndInstaller(unittest.TestCase):
    def test_vr_row_is_directly_under_mp(self):
        text = (ROOT / "Mix_Archive_Manager.sh").read_text(encoding="utf-8")
        mp = text.index('"MP|MP GUI Mix Manager (New)|')
        vr = text.index('"VR|Enter VR Mode with MP Liquid Player (BigScreen)|')
        desktop = text.index('"0|Run Any Desktop Shortcuts|')
        self.assertLess(mp, vr)
        self.assertLess(vr, desktop)
        self.assertIn("enter_bigscreen_vr_mode", text)
        install = (ROOT / "install.sh").read_text(encoding="utf-8")
        self.assertIn("MP Liquid Player VR Mode", install)


if __name__ == "__main__":
    unittest.main()
