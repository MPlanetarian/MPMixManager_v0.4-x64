#!/usr/bin/env python3
"""Windows installs shortcuts and the tray into the signed-in user's profile."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))


class TestWindowsUserIntegration(unittest.TestCase):
    def test_installer_does_not_need_python_on_windows(self):
        install = (ROOT / "install.sh").read_text(encoding="utf-8")
        windows = install.index('"$HOST_OS" = "windows"')
        helper = install.index("install_windows_user.sh", windows)
        python_required = install.index("python3 is required", helper)
        self.assertLess(helper, python_required)
        self.assertIn("mp_system_tray.py", install)
        self.assertIn("--install", install)

    def test_shortcuts_target_the_user_profile_desktop(self):
        script = (ROOT / "scripts" / "windows_user_integration.ps1").read_text(encoding="utf-8")
        self.assertIn("DesktopDirectory", script)
        self.assertIn("User Shell Folders", script)
        self.assertIn("explorer.exe", script)
        for name in (
            "MP Liquid Player",
            "MP Mix Manager",
            "MP Gui",
            "MP Liquid Visualizer",
        ):
            self.assertIn(name, script)
        self.assertIn("launch_liquid_glass.bat", script)
        self.assertIn("launch_liquid_visualizer.bat", script)
        self.assertIn("manager.bat", script)
        self.assertIn("MP_Gui.sh", script)
        self.assertIn("windows_tray.ps1", script)
        self.assertIn("Startup", script)
        self.assertIn("LogonType Interactive", script)
        self.assertIn("HideIcons", script)
        self.assertIn("Show-MpDesktopIcons", script)
        self.assertNotIn("CommonDesktopDirectory", script)
        self.assertNotIn("Public\\Desktop", script)

    def test_tray_icon_uses_the_windows_notification_area(self):
        tray = (ROOT / "scripts" / "windows_tray.ps1").read_text(encoding="utf-8")
        self.assertIn("NotifyIcon", tray)
        self.assertIn("Local\\MPMixManagerTray", tray)
        self.assertIn("Launch MP Gui", tray)
        self.assertIn("Launch MP Liquid Player", tray)
        self.assertIn("Launch MP Mix Manager", tray)
        self.assertIn("Close MP Mix Manager (Closes everything)", tray)
        self.assertIn("MP_Mix_Manager_Windows_Icon.ico", tray)

    def test_manager_and_tray_helper_repair_a_windows_profile(self):
        manager = (ROOT / "manager.ps1").read_text(encoding="utf-8")
        self.assertIn("windows_user_integration.ps1", manager)
        self.assertIn("-Action Install", manager)
        shell = (ROOT / "scripts" / "mp_system_tray.sh").read_text(encoding="utf-8")
        self.assertLess(shell.index("_is_windows_host"), shell.index("import PySide6.QtWidgets"))
        self.assertIn("install_windows_user.sh", shell)
        helper = (ROOT / "scripts" / "install_windows_user.sh").read_text(encoding="utf-8")
        self.assertIn("MSYS_NO_PATHCONV", helper)
        self.assertIn("cygpath", helper)
        self.assertIn("wslpath", helper)

    def test_launchers_skip_the_store_python_alias(self):
        finder = (ROOT / "scripts" / "windows_find_python.cmd").read_text(encoding="utf-8")
        self.assertIn("WindowsApps", finder)
        self.assertIn("anaconda3", finder)
        self.assertLess(finder.index(r"venv\Scripts\python.exe"), finder.index("anaconda3"))
        for name in ("scripts/launch_liquid_glass.bat", "scripts/launch_liquid_visualizer.bat"):
            text = (ROOT / name).read_text(encoding="utf-8")
            self.assertIn("windows_find_python.cmd", text)
            self.assertNotIn('set "PYTHON_BIN=python.exe"', text)


if __name__ == "__main__":
    unittest.main()
