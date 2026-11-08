"""Shared system tray for MP Mix Manager, MP Gui, and MP Liquid Player."""

import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import mp_system_tray as tray


def proc(pid, ppid, cmdline, environ=""):
    return tray.ProcessInfo(pid, ppid, cmdline, environ)


class TestClassify(unittest.TestCase):
    def test_the_three_apps_and_the_console_host_are_distinct(self):
        gui = proc(10, 1, "python3 /opt/MP_Audio_Player_Liquid_Glass_OpenGL.py --manager")
        gui_shell = proc(11, 10, "bash /opt/Mix_Archive_Manager.sh")
        console = proc(12, 5, "bash /opt/Mix_Archive_Manager.sh")
        konsole = proc(
            5,
            1,
            "/usr/bin/konsole --fullscreen --separate -p tabtitle=MP Mix Archive Manager "
            "-e /opt/bin/mix-archive-manager",
        )
        liquid = proc(13, 1, "python3 /opt/MP_Audio_Player_Liquid_Glass_OpenGL.py")
        launcher = proc(14, 1, "setsid bash /opt/MP_Gui.sh")
        player_launcher = proc(15, 1, "/opt/scripts/launch-liquid-glass")
        detached = proc(
            16,
            1,
            "setsid env -u MP_GUI_SESSION -u LINES -u COLUMNS "
            "python3 /opt/MP_Audio_Player_Liquid_Glass.py --play /tmp/a.flac",
        )
        processes = [gui, gui_shell, console, konsole, liquid, launcher, player_launcher, detached]
        by_pid = tray.index_processes(processes)

        self.assertEqual(tray.classify_process(gui, by_pid), tray.ROLE_GUI)
        self.assertIsNone(tray.classify_process(gui_shell, by_pid))
        self.assertEqual(tray.classify_process(console, by_pid), tray.ROLE_MANAGER)
        self.assertEqual(tray.classify_process(konsole, by_pid), tray.ROLE_MANAGER)
        self.assertEqual(tray.classify_process(liquid, by_pid), tray.ROLE_LIQUID)
        self.assertEqual(tray.classify_process(launcher, by_pid), tray.ROLE_GUI)
        self.assertEqual(tray.classify_process(player_launcher, by_pid), tray.ROLE_LIQUID)
        self.assertEqual(tray.classify_process(detached, by_pid), tray.ROLE_LIQUID)
        self.assertEqual(
            tray.roles_present(processes),
            {tray.ROLE_GUI, tray.ROLE_LIQUID, tray.ROLE_MANAGER},
        )

    def test_gui_session_environment_is_not_the_console_manager(self):
        shell = proc(20, 1, "bash /opt/Mix_Archive_Manager.sh", "MP_GUI_SESSION=1\nTERM=xterm")
        self.assertIsNone(tray.classify_process(shell, {20: shell}))

    def test_the_tray_an_editor_and_a_sourced_script_are_ignored(self):
        ignored = [
            proc(1, 0, "python3 /opt/scripts/mp_system_tray.py"),
            proc(2, 0, "nvim /opt/Mix_Archive_Manager.sh"),
            proc(3, 0, "bash -c source ./Mix_Archive_Manager.sh"),
            proc(4, 0, "grep Mix_Archive_Manager.sh"),
        ]
        for item in ignored:
            self.assertIsNone(tray.classify_process(item, tray.index_processes(ignored)), item.cmdline)

    def test_close_targets_the_console_manager_and_its_konsole(self):
        gui = proc(10, 1, "python3 /opt/MP_Audio_Player_Liquid_Glass_OpenGL.py --manager")
        gui_shell = proc(11, 10, "bash /opt/Mix_Archive_Manager.sh")
        console = proc(12, 5, "bash /opt/Mix_Archive_Manager.sh")
        konsole = proc(5, 1, "/usr/bin/konsole -e /opt/bin/mix-archive-manager")
        tray_proc = proc(99, 1, "python3 /opt/scripts/mp_system_tray.py")
        processes = [gui, gui_shell, console, konsole, tray_proc]
        self.assertEqual(tray.manager_pids(processes, {99}), [12, 5])


class TestMenu(unittest.TestCase):
    def test_menu_labels_and_close_is_last(self):
        labels = [label for _ident, label in tray.MENU_ENTRIES]
        self.assertEqual(
            labels,
            [
                "Launch MP Gui",
                "Launch MP Liquid Player",
                "Launch MP Mix Manager",
                "Close MP Mix Manager (Closes everything)",
            ],
        )
        self.assertEqual(tray.MENU_ENTRIES[-1][0], "close-all")

    def test_launch_focuses_an_open_app_and_spawns_a_closed_one(self):
        base = ROOT
        focused = tray.launch_plan(tray.ROLE_GUI, base, {tray.ROLE_GUI})
        self.assertEqual(focused["action"], "focus")
        self.assertEqual(focused["title"], "MP Mix Manager (Liquid Glass")

        spawned = tray.launch_plan(tray.ROLE_LIQUID, base, set())
        self.assertEqual(spawned["action"], "spawn")
        self.assertTrue(str(spawned["argv"][0]).endswith("launch-liquid-glass"))

        manager = tray.launch_plan(tray.ROLE_MANAGER, base, {tray.ROLE_LIQUID, tray.ROLE_GUI})
        self.assertEqual(manager["action"], "spawn")
        self.assertTrue(str(manager["argv"][0]).endswith("launch-manager"))
        self.assertEqual(manager["title"], "MP Mix Archive Manager")

    def test_kill_script_is_the_player_shutdown_script(self):
        script = tray.kill_all_script(ROOT)
        self.assertIsNotNone(script)
        self.assertEqual(script.name, "kill_all_mp_audio_players.sh")


class TestSingleton(unittest.TestCase):
    def test_a_second_process_does_not_take_the_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            lock_path = Path(tmp) / "mp_system_tray.lock"
            err_path = Path(tmp) / "holder.err"
            err_file = open(err_path, "w", encoding="utf-8")
            holder = subprocess.Popen(
                [
                    sys.executable,
                    "-c",
                    "import os, time\n"
                    "from pathlib import Path\n"
                    "import mp_system_tray as tray\n"
                    "lock = tray.TrayLock(Path(os.environ['LOCK']))\n"
                    "assert lock.acquire()\n"
                    "time.sleep(30)\n",
                ],
                cwd=str(ROOT / "scripts"),
                env={**os.environ, "LOCK": str(lock_path)},
                stdout=subprocess.DEVNULL,
                stderr=err_file,
            )
            try:
                deadline = time.time() + 5
                while time.time() < deadline and not tray.TrayLock.held(lock_path):
                    if holder.poll() is not None:
                        err_file.close()
                        self.fail(f"lock holder exited {holder.returncode}: {err_path.read_text()}")
                    time.sleep(0.05)
                self.assertTrue(tray.TrayLock.held(lock_path))
                self.assertFalse(tray.TrayLock(lock_path).acquire())
            finally:
                err_file.close()
                if holder.poll() is None:
                    holder.terminate()
                    try:
                        holder.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        holder.kill()
                        holder.wait(timeout=2)


class TestHooks(unittest.TestCase):
    def test_each_app_starts_the_same_tray(self):
        manager = (ROOT / "Mix_Archive_Manager.sh").read_text(encoding="utf-8")
        guard = manager.index('if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then')
        self.assertLess(manager.index("_ensure_mp_system_tray() {"), guard)
        self.assertIn("_ensure_mp_system_tray", manager[guard:])
        for name in ("MP_Gui.sh", "scripts/launch-liquid-glass", "scripts/launch_liquid_glass.sh"):
            text = (ROOT / name).read_text(encoding="utf-8")
            self.assertIn("mp_system_tray.sh", text, name)
            self.assertIn("--ensure", text, name)

    def test_shell_scripts_parse(self):
        for name in (
            "scripts/mp_system_tray.sh",
            "MP_Gui.sh",
            "scripts/launch-liquid-glass",
            "scripts/launch_liquid_glass.sh",
            "Mix_Archive_Manager.sh",
        ):
            result = subprocess.run(
                ["bash", "-n", str(ROOT / name)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_help_mentions_the_shared_icon(self):
        text = (ROOT / "scripts" / "show_help.sh").read_text(encoding="utf-8")
        self.assertIn("Close MP Mix Manager (Closes everything)", text)
        self.assertIn("Launch MP Gui", text)
        self.assertIn("Launch MP Liquid Player", text)
        self.assertIn("Launch MP Mix Manager", text)


if __name__ == "__main__":
    unittest.main()
