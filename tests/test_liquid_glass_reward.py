import io
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.liquid_glass_reward import (
    is_welcomed,
    install_reward_desktop_shortcut,
    ensure_first_run_reward,
    show_welcome_message,
)

ROOT = Path(__file__).resolve().parent.parent

class TestLiquidGlassReward(unittest.TestCase):
    def test_welcome_message_output(self):
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            show_welcome_message(wait_for_input=False)
        out = buf.getvalue()
        self.assertIn("MPlanetarian", out)
        self.assertIn("Liquid Transparent Audio Player", out)
        self.assertIn("Special Desktop Reward Unlocked", out)

    def test_icon_assets_exist(self):
        png_icon = ROOT / "assets" / "mp_liquid_glass_icon.png"
        svg_icon = ROOT / "assets" / "mp_liquid_glass_icon.svg"
        desktop_file = ROOT / "desktop" / "MP_Liquid_Glass_Audio_Player.desktop"
        root_desktop_file = ROOT / "MP_Liquid_Glass_Audio_Player.desktop"
        launcher_script = ROOT / "scripts" / "launch_liquid_glass.sh"

        self.assertTrue(png_icon.exists(), "PNG icon should exist")
        self.assertGreater(png_icon.stat().st_size, 1000, "PNG icon should have non-trivial size")
        self.assertTrue(svg_icon.exists(), "SVG icon should exist")
        self.assertTrue(desktop_file.exists(), "desktop entry template should exist")
        self.assertTrue(root_desktop_file.exists(), "root desktop file should exist")
        self.assertTrue(launcher_script.exists(), "launch_liquid_glass.sh should exist")
        self.assertTrue(os.access(launcher_script, os.X_OK), "launch_liquid_glass.sh should be executable")

        # Check desktop file content
        desktop_content = desktop_file.read_text(encoding="utf-8")
        self.assertIn("[Desktop Entry]", desktop_content)
        self.assertIn("MP Liquid Glass Audio Player", desktop_content)
        self.assertIn("mp_liquid_glass_icon", desktop_content)

    def test_default_audio_player_in_configs(self):
        cfg_env = ROOT / "config.env"
        cfg_example = ROOT / "config.env.example"
        self.assertIn('DEFAULT_AUDIO_PLAYER="mp_liquid_glass"', cfg_env.read_text(encoding="utf-8"))
        self.assertIn('DEFAULT_AUDIO_PLAYER="mp_liquid_glass"', cfg_example.read_text(encoding="utf-8"))

    def test_reward_workflow_mock(self):
        with patch("scripts.liquid_glass_reward.FLAG_FILE") as mock_flag, \
             patch("scripts.liquid_glass_reward.install_reward_desktop_shortcut") as mock_install, \
             patch("scripts.liquid_glass_reward.show_welcome_message") as mock_show:
            mock_flag.exists.return_value = False
            self.assertFalse(is_welcomed())
            unlocked = ensure_first_run_reward(interactive=False)
            self.assertTrue(unlocked)
            mock_install.assert_called_once()
            mock_flag.touch.assert_called_once()

    def test_copied_launcher_resolves_base_dir(self):
        import shutil
        import subprocess
        import tempfile

        launcher_script = ROOT / "scripts" / "launch_liquid_glass.sh"
        with tempfile.TemporaryDirectory() as tmpdir:
            copied_launcher = Path(tmpdir) / "launch-liquid-glass"
            shutil.copy2(launcher_script, copied_launcher)
            copied_launcher.chmod(0o755)
            proc = subprocess.run(
                [str(copied_launcher), "--self-test"],
                cwd=tmpdir,
                capture_output=True,
                text=True,
                timeout=15,
            )
            self.assertNotIn("No such file or directory", proc.stderr)
            self.assertEqual(proc.returncode, 0, f"Copied launcher failed: {proc.stderr}")

if __name__ == "__main__":
    unittest.main()
