#!/usr/bin/env python3
"""First install creates four named desktop shortcuts on every platform."""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from install_desktop_shortcuts import (  # noqa: E402
    MAC_APP_EXECUTABLE,
    MAC_ICON_NAME,
    SHORTCUT_NAMES,
    _is_public_windows_folder,
    desktop_dir_for,
    desktop_shortcuts_present,
    ensure_installed,
    install_desktop_shortcuts,
    mac_bundle_identifier,
    mac_finder_icon_present,
)


class TestDesktopShortcuts(unittest.TestCase):
    def test_there_are_four_named_shortcuts(self):
        self.assertEqual(
            list(SHORTCUT_NAMES),
            [
                "MP Liquid Player",
                "MP Mix Manager",
                "MP Gui",
                "MP Liquid Visualizer",
            ],
        )

    def test_linux_install_writes_four_desktop_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            desktop = Path(tmp) / "Desktop"
            apps = Path(tmp) / "applications"
            desktop.mkdir()
            (desktop / "MP_Liquid.desktop").write_text("old\n", encoding="utf-8")
            (desktop / "Mix Archive Manager.command").write_text("old\n", encoding="utf-8")
            paths = install_desktop_shortcuts(
                ROOT,
                platform_name="linux",
                desktop_dir=desktop,
                apps_dir=apps,
                launcher_dir=Path(tmp) / "launchers",
            )
            self.assertEqual([path.name for path in paths], [f"{name}.desktop" for name in SHORTCUT_NAMES])
            self.assertFalse((desktop / "MP_Liquid.desktop").exists())
            self.assertFalse((desktop / "Mix Archive Manager.command").exists())

            player = (desktop / "MP Liquid Player.desktop").read_text(encoding="utf-8")
            self.assertIn("Name=MP Liquid Player", player)
            self.assertIn("launch_liquid_glass.sh", player)
            self.assertNotIn("--play", player)
            self.assertIn("Terminal=false", player)

            manager = (desktop / "MP Mix Manager.desktop").read_text(encoding="utf-8")
            self.assertIn("Name=MP Mix Manager", manager)
            self.assertIn("Mix_Archive_Manager.sh", manager)
            self.assertNotIn("manager.sh", manager)
            self.assertIn("Terminal=true", manager)

            gui = (desktop / "MP Gui.desktop").read_text(encoding="utf-8")
            self.assertIn("Name=MP Gui", gui)
            self.assertIn("MP_Gui.sh", gui)
            self.assertIn("Terminal=false", gui)

            visualizer = (desktop / "MP Liquid Visualizer.desktop").read_text(encoding="utf-8")
            self.assertIn("Name=MP Liquid Visualizer", visualizer)
            self.assertIn("launch_liquid_visualizer.sh", visualizer)
            self.assertIn("Terminal=false", visualizer)

            for name in SHORTCUT_NAMES:
                menu = apps / f"{name}.desktop"
                self.assertTrue(menu.is_file(), name)
                self.assertIn(f"Name={name}", menu.read_text(encoding="utf-8"))

    def test_macos_gui_shortcuts_are_apps_and_manager_stays_a_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            desktop = Path(tmp) / "Desktop"
            apps = Path(tmp) / "Applications"
            desktop.mkdir()
            apps.mkdir()
            (desktop / "MP Gui.command").write_text("old\n", encoding="utf-8")
            (apps / "MP Liquid Player.command").write_text("old\n", encoding="utf-8")
            self.assertFalse(desktop_shortcuts_present(desktop, "macos"))
            written = install_desktop_shortcuts(
                ROOT,
                platform_name="macos",
                desktop_dir=desktop,
                apps_dir=apps,
                launcher_dir=Path(tmp) / "launchers",
            )
            self.assertEqual(
                [path.name for path in written],
                [
                    "MP Liquid Player.app",
                    "MP Mix Manager.command",
                    "MP Gui.app",
                    "MP Liquid Visualizer.app",
                ],
            )
            self.assertEqual([path.name for path in desktop.glob("*.command")], ["MP Mix Manager.command"])
            self.assertFalse((desktop / "MP Gui.command").exists())
            self.assertFalse((apps / "MP Liquid Player.command").exists())
            self.assertFalse((desktop / "MP Mix Manager.app").exists())

            manager = (desktop / "MP Mix Manager.command").read_text(encoding="utf-8")
            self.assertIn("Mix_Archive_Manager.sh", manager)
            self.assertIn("/opt/homebrew/bin/bash", manager)
            self.assertTrue(os.access(desktop / "MP Mix Manager.command", os.X_OK))
            self.assertTrue((apps / "MP Mix Manager.command").is_file())

            gui_apps = ("MP Liquid Player", "MP Gui", "MP Liquid Visualizer")
            expected = {
                "MP Liquid Player": "launch_liquid_glass.sh",
                "MP Gui": "MP_Gui.sh",
                "MP Liquid Visualizer": "launch_liquid_visualizer.sh",
            }
            for name in gui_apps:
                for directory in (desktop, apps):
                    app = directory / f"{name}.app"
                    exe = app / "Contents" / "MacOS" / MAC_APP_EXECUTABLE
                    plist = (app / "Contents" / "Info.plist").read_text(encoding="utf-8")
                    script = exe.read_text(encoding="utf-8")
                    self.assertTrue(os.access(exe, os.X_OK), name)
                    self.assertIn(expected[name], script)
                    self.assertNotIn("Terminal", script)
                    self.assertNotIn("--play", script)
                    self.assertIn(f"<string>{name}</string>", plist)
                    self.assertIn(mac_bundle_identifier(name), plist)
                    self.assertIn(f"<string>{MAC_APP_EXECUTABLE}</string>", plist)
                    if sys.platform == "darwin":
                        icns = app / "Contents" / "Resources" / f"{MAC_ICON_NAME}.icns"
                        self.assertTrue(icns.is_file() and icns.stat().st_size > 0, name)
                        self.assertIn("CFBundleIconFile", plist)
                        self.assertIn(MAC_ICON_NAME, plist)
                        self.assertTrue(mac_finder_icon_present(app), name)
            if sys.platform == "darwin":
                self.assertTrue(mac_finder_icon_present(desktop / "MP Mix Manager.command"))
                self.assertTrue(mac_finder_icon_present(apps / "MP Mix Manager.command"))
            self.assertTrue(desktop_shortcuts_present(desktop, "macos"))

    def test_windows_install_links_the_four_launchers(self):
        created = []

        def writer(path, target, arguments, workdir, description, icon):
            created.append((Path(path), Path(target).name, arguments, description))
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            Path(path).write_text("shortcut\n", encoding="utf-8")

        with tempfile.TemporaryDirectory() as tmp:
            desktop = Path(tmp) / "Desktop"
            apps = Path(tmp) / "Programs"
            launchers = Path(tmp) / "launchers"
            install_desktop_shortcuts(
                ROOT,
                platform_name="windows",
                desktop_dir=desktop,
                apps_dir=apps,
                launcher_dir=launchers,
                link_writer=writer,
            )
            desktop_links = [item for item in created if item[0].parent == desktop]
            self.assertEqual([item[0].name for item in desktop_links], [f"{name}.lnk" for name in SHORTCUT_NAMES])
            by_name = {item[0].name: item for item in desktop_links}
            self.assertEqual(by_name["MP Liquid Player.lnk"][1], "launch_liquid_glass.bat")
            self.assertEqual(by_name["MP Mix Manager.lnk"][1], "manager.bat")
            self.assertEqual(by_name["MP Gui.lnk"][1], "MP Gui.cmd")
            self.assertIn("MP_Gui.sh", (launchers / "MP Gui.cmd").read_text(encoding="utf-8"))
            visualizer_cmd = (launchers / "MP Liquid Visualizer.cmd").read_text(encoding="utf-8")
            self.assertIn("MP_Liquid_Visualizer.py", visualizer_cmd)
            self.assertNotIn("--play", visualizer_cmd)
            self.assertEqual(len(list(apps.glob("*.lnk"))), 4)

    def test_windows_desktop_falls_back_to_the_user_profile(self):
        with patch.dict(os.environ, {"USERPROFILE": r"C:\Users\Ada"}, clear=False), \
             patch("install_desktop_shortcuts._windows_special_folder", return_value=None):
            self.assertEqual(desktop_dir_for("windows"), Path(r"C:\Users\Ada") / "Desktop")

    def test_public_desktop_is_not_the_user_profile(self):
        self.assertTrue(_is_public_windows_folder(r"C:\Users\Public\Desktop"))
        self.assertFalse(_is_public_windows_folder(r"C:\Users\Administrator\Desktop"))

    def test_ensure_installs_only_when_a_shortcut_is_missing(self):
        with patch("install_desktop_shortcuts.desktop_shortcuts_present", return_value=True), \
             patch("install_desktop_shortcuts.install_desktop_shortcuts") as install:
            self.assertFalse(ensure_installed(ROOT))
            install.assert_not_called()
        with patch("install_desktop_shortcuts.desktop_shortcuts_present", return_value=False), \
             patch("install_desktop_shortcuts.desktop_dir_for", return_value=Path("/tmp/mp-shortcuts-unused")), \
             patch("install_desktop_shortcuts.install_desktop_shortcuts", return_value=[]) as install:
            self.assertTrue(ensure_installed(ROOT))
            install.assert_called_once()


if __name__ == "__main__":
    unittest.main()
