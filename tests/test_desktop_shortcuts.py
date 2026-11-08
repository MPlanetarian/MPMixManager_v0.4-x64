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
    SHORTCUT_NAMES,
    ensure_installed,
    install_desktop_shortcuts,
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

    def test_macos_install_writes_four_commands(self):
        with tempfile.TemporaryDirectory() as tmp:
            desktop = Path(tmp) / "Desktop"
            apps = Path(tmp) / "Applications"
            install_desktop_shortcuts(
                ROOT,
                platform_name="macos",
                desktop_dir=desktop,
                apps_dir=apps,
                launcher_dir=Path(tmp) / "launchers",
            )
            commands = sorted(path.name for path in desktop.glob("*.command"))
            self.assertEqual(commands, sorted(f"{name}.command" for name in SHORTCUT_NAMES))
            manager = (desktop / "MP Mix Manager.command").read_text(encoding="utf-8")
            self.assertIn("Mix_Archive_Manager.sh", manager)
            self.assertIn("/opt/homebrew/bin/bash", manager)
            player = (desktop / "MP Liquid Player.command").read_text(encoding="utf-8")
            self.assertIn("launch_liquid_glass.sh", player)
            self.assertNotIn("--play", player)
            for name in SHORTCUT_NAMES:
                path = desktop / f"{name}.command"
                self.assertTrue(os.access(path, os.X_OK), name)
                self.assertTrue((apps / f"{name}.command").is_file(), name)

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
