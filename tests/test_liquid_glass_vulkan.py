"""Liquid Glass menu wiring and the NVIDIA Vulkan renderer."""

import os
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from liquid_glass_vulkan import (  # noqa: E402
    NVIDIA_VENDOR_ID,
    select_nvidia_device,
    theme_rgb,
)
from MP_Audio_Player_Liquid_Glass import embed_check_argv, player_argv  # noqa: E402


class TestNvidiaSelection(unittest.TestCase):
    def test_prefers_the_discrete_nvidia_gpu(self):
        devices = [
            {"vendor_id": 0x1002, "device_type": 2, "name": "AMD"},
            {"vendor_id": NVIDIA_VENDOR_ID, "device_type": 1, "name": "NVIDIA integrated"},
            {"vendor_id": NVIDIA_VENDOR_ID, "device_type": 2, "name": "NVIDIA GeForce RTX 3080"},
            {"vendor_id": 0x10005, "device_type": 4, "name": "llvmpipe"},
        ]
        self.assertEqual(select_nvidia_device(devices), 2)

    def test_refuses_a_machine_without_nvidia(self):
        with self.assertRaises(RuntimeError):
            select_nvidia_device([{"vendor_id": 0x10005, "device_type": 4, "name": "llvmpipe"}])

    def test_theme_aliases_use_the_player_palette(self):
        self.assertEqual(theme_rgb("dreamworlds"), theme_rgb("dreamworlds_ultra"))
        self.assertEqual(theme_rgb("matrix"), theme_rgb("phosphor"))
        self.assertEqual(theme_rgb("dreamworlds_ultra")[0], (166, 77, 255))


class TestMenuOption(unittest.TestCase):
    def test_option_three_is_liquid_glass_and_exit_is_thirty_seven(self):
        text = (ROOT / "Mix_Archive_Manager.sh").read_text(encoding="utf-8")
        start = text.index("main_opts=(")
        end = text.index('); if [ -n "$CLI_INITIAL_ACTION" ]', start)
        keys = []
        for entry in re.findall(r'"((?:[^"\\]|\\.)*)"', text[start:end]):
            key, _, title = entry.partition("|")
            if key in {"SECTION", "SEP"}:
                continue
            keys.append((key, title.split("|", 1)[0]))
        self.assertEqual(keys[3], ("3", "MP Audio Player (Liquid Glass Mode)"))
        self.assertEqual(keys[4][0], "4")
        self.assertIn("Run Mix Conversion", keys[4][1])
        self.assertEqual(keys[-1][0], "37")
        self.assertIn("Exit Manager", keys[-1][1])
        self.assertIn('3|liquid|liquid-glass|glass|"MP Audio Player (Liquid Glass Mode)"*', text)
        self.assertIn("37|77|", text)
        self.assertNotIn("36|77|", text)
        self.assertIn("between 0 and 37", text)
        self.assertGreaterEqual(text.count("launch_mp_audio_player_liquid_glass"), 2)

    def test_shell_parses(self):
        result = subprocess.run(
            ["bash", "-n", str(ROOT / "Mix_Archive_Manager.sh")],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


class TestHostDoesNotForkThePlayer(unittest.TestCase):
    def test_embed_check_uses_a_dummy_child(self):
        argv = embed_check_argv()
        self.assertNotIn("--interactive", argv)
        self.assertFalse(any(arg.endswith("MP_Audio_Player.py") for arg in argv))

    def test_normal_launch_uses_the_unmodified_player(self):
        self.assertEqual(player_argv()[-2:], [str(ROOT / "MP_Audio_Player.py"), "--interactive"])


@unittest.skipUnless(os.environ.get("DISPLAY"), "an X11 display is required")
class TestNvidiaFrame(unittest.TestCase):
    def test_renderer_draws_on_the_nvidia_gpu(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "liquid_glass_vulkan.py")],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("LIQUID_GLASS_OK", result.stdout)
        self.assertIn("vendor 0x10de", result.stdout)
        self.assertIn("NVIDIA GeForce RTX 3080", result.stdout)

    def test_terminal_sits_in_the_glass_without_starting_playback(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "MP_Audio_Player_Liquid_Glass.py"), "--embed-check"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("LIQUID_GLASS_EMBED_OK", result.stdout)
        self.assertIn("vendor 0x10de", result.stdout)

    def test_window_movement_and_pointer_tracking(self):
        from liquid_glass_vulkan import LiquidGlassRenderer

        renderer = LiquidGlassRenderer(400, 300, "Movement Test")
        try:
            renderer.open()
            init_pos = renderer.window_pos()
            self.assertEqual(init_pos, (72, 64))
            renderer.set_window_pos(150, 200)
            self.assertEqual(renderer.window_pos(), (150, 200))
            rx, ry = renderer.root_pointer()
            self.assertIsInstance(rx, int)
            self.assertIsInstance(ry, int)
        finally:
            renderer.close()


if __name__ == "__main__":
    unittest.main()
