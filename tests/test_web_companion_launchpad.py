"""Tests for the Web Companion desktop launch pad plumbing.

The dashboard runs as a user service, so ``mp_suite_control`` is what lets a
phone start or close the desktop suite. These tests pin the pieces that are
easy to regress: which roles the four buttons map to, which launchers they
use, how a live process table is read, and the guarantee that Close All never
signals the shared tray icon.
"""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import mp_suite_control as control
import mp_system_tray as tray


def proc(pid, ppid, cmdline, environ=""):
    return tray.ProcessInfo(pid, ppid, cmdline, environ)


class TestRoles(unittest.TestCase):
    def test_four_buttons_in_launch_order(self):
        apps = control.app_definitions()
        self.assertEqual(
            [app["id"] for app in apps],
            ["gui", "manager", "liquid", "visualizer"],
        )
        self.assertEqual(
            [app["label"] for app in apps],
            [
                "MP Gui",
                "MP Mix Manager (CLI)",
                "MP Liquid Player",
                "MP Liquid Visualizer",
            ],
        )

    def test_launchers_match_the_tray_and_desktop_shortcuts(self):
        gui = control.launch_argv(control.ROLE_GUI, ROOT)
        self.assertEqual(gui[0], "bash")
        self.assertTrue(gui[1].endswith("MP_Gui.sh"))

        manager = control.launch_argv(control.ROLE_MANAGER, ROOT)
        self.assertTrue(str(manager[0]).endswith("launch-manager"))

        liquid = control.launch_argv(control.ROLE_LIQUID, ROOT)
        self.assertTrue(str(liquid[0]).endswith("launch-liquid-glass"))

        visualizer = control.launch_argv(control.ROLE_VISUALIZER, ROOT)
        self.assertTrue(visualizer[1].endswith("launch_liquid_visualizer.sh"))

    def test_unknown_role_is_rejected(self):
        with self.assertRaises(ValueError):
            control.launch_argv("not-an-app", ROOT)


class TestDetection(unittest.TestCase):
    def test_all_four_are_detected_from_a_process_list(self):
        processes = [
            proc(10, 1, "python3 /opt/MP_Audio_Player_Liquid_Glass_OpenGL.py --manager"),
            proc(11, 5, "bash /opt/Mix_Archive_Manager.sh"),
            proc(5, 1, "/usr/bin/konsole -e /opt/bin/mix-archive-manager"),
            proc(12, 1, "python3 /opt/MP_Audio_Player_Liquid_Glass_OpenGL.py"),
            proc(13, 1, "python3 /opt/MP_Liquid_Visualizer.py --preset random"),
            proc(14, 1, "python3 /opt/scripts/mp_system_tray.py"),
        ]
        self.assertEqual(
            control.running_roles(processes),
            {"gui", "manager", "liquid", "visualizer"},
        )

    def test_a_manager_hosted_in_mp_gui_is_not_the_cli(self):
        """MP_Gui.sh runs Mix_Archive_Manager.sh inside its own window."""
        processes = [
            proc(10, 1, "python3 /opt/MP_Audio_Player_Liquid_Glass_OpenGL.py --manager"),
            proc(11, 10, "bash /opt/Mix_Archive_Manager.sh", "MP_GUI_SESSION=1\nTERM=xterm"),
        ]
        self.assertEqual(control.running_roles(processes), {"gui"})

    def test_the_visualizer_is_not_confused_with_the_player(self):
        processes = [proc(13, 1, "python3 /opt/MP_Liquid_Visualizer.py")]
        self.assertEqual(control.running_roles(processes), {"visualizer"})

    def test_empty_table_reports_nothing_running(self):
        self.assertEqual(control.running_roles([]), set())

    def test_status_payload_carries_a_running_flag_per_app(self):
        processes = [proc(12, 1, "python3 /opt/MP_Audio_Player_Liquid_Glass.py")]
        with patch.object(control, "is_supported", return_value=True), \
             patch.object(control, "_process_table", return_value=processes):
            status = control.app_status()
        self.assertTrue(status["supported"])
        flags = {app["id"]: app["running"] for app in status["apps"]}
        self.assertEqual(
            flags,
            {"gui": False, "manager": False, "liquid": True, "visualizer": False},
        )


class TestLaunch(unittest.TestCase):
    def test_launching_when_closed_spawns_the_launcher(self):
        with patch.object(control, "is_supported", return_value=True), \
             patch.object(control, "running_roles", return_value=set()), \
             patch.object(control, "_spawn") as spawn:
            result = control.launch_app(control.ROLE_GUI)
        self.assertTrue(result["success"])
        self.assertEqual(result["action"], "launch")
        self.assertEqual(spawn.call_count, 1)

    def test_launching_when_open_focuses_instead(self):
        with patch.object(control, "is_supported", return_value=True), \
             patch.object(control, "running_roles", return_value={"liquid"}), \
             patch.object(control, "_focus", return_value=True) as focus, \
             patch.object(control, "_spawn") as spawn:
            result = control.launch_app(control.ROLE_LIQUID)
        self.assertTrue(result["success"])
        self.assertEqual(result["action"], "focus")
        self.assertEqual(focus.call_count, 1)
        self.assertEqual(spawn.call_count, 0)

    def test_unsupported_host_does_nothing(self):
        with patch.object(control, "is_supported", return_value=False), \
             patch.object(control, "_spawn") as spawn:
            result = control.launch_app(control.ROLE_GUI)
        self.assertFalse(result["success"])
        self.assertEqual(result["action"], "unsupported")
        self.assertEqual(spawn.call_count, 0)


class TestCloseAll(unittest.TestCase):
    def test_close_all_leaves_the_tray_icon_running(self):
        calls = {}

        def fake_shutdown(base):
            calls["shutdown"] = base
            return []

        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp)
            with patch.object(control, "is_supported", return_value=True), \
                 patch.object(control, "running_roles", side_effect=[{"gui", "manager", "liquid", "visualizer"}, set()]), \
                 patch.object(control, "tray_running", return_value=True), \
                 patch.object(control, "_tray_module") as module:
                module.return_value.shutdown_suite = fake_shutdown
                module.return_value.request_keepalive = lambda _cfg: tray.request_keepalive(config)
                module.return_value.config_dir = lambda: config
                module.return_value.TrayLock.held.return_value = True
                result = control.close_all_apps(ROOT)

            self.assertTrue(result["success"])
            self.assertEqual(result["remaining"], [])
            self.assertEqual(result["action"], "close_all")
            # The keepalive marker is what keeps a shortcut-started tray alive.
            self.assertTrue(tray.keepalive_active(config))
        # And the icon is reported as still up, never as one of the closed apps.
        self.assertTrue(result["tray_running"])
        self.assertEqual(
            result["closed"], ["gui", "liquid", "manager", "visualizer"]
        )
        self.assertNotIn("tray", result["closed"])

    def test_close_all_is_unsupported_off_linux(self):
        with patch.object(control, "is_supported", return_value=False):
            result = control.close_all_apps(ROOT)
        self.assertFalse(result["success"])
        self.assertEqual(result["action"], "unsupported")


class TestKeepalive(unittest.TestCase):
    def test_keepalive_expires(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp)
            tray.request_keepalive(config)
            self.assertTrue(tray.keepalive_active(config))
            # A stale stamp must not hold the icon up forever.
            path = tray.keepalive_path(config)
            path.write_text("0\n", encoding="utf-8")
            self.assertFalse(tray.keepalive_active(config))

    def test_missing_keepalive_is_inactive(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertFalse(tray.keepalive_active(Path(tmp)))


if __name__ == "__main__":
    unittest.main()
