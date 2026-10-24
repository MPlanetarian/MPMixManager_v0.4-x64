import os
import sys
import unittest
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))


class TestLiquidGlassSkin(unittest.TestCase):
    def test_skin_image_file_dimensions(self):
        skin_path = ROOT / "assets" / "skins" / "cosmic_dreamworlds_radioactive.png"
        self.assertTrue(skin_path.is_file(), f"Skin file should exist: {skin_path}")
        with Image.open(skin_path) as img:
            self.assertEqual(img.size, (1280, 820), "Skin should be cropped to default window size 1280x820")
            self.assertEqual(img.mode, "RGBA")

    def test_theme_in_audio_player_order(self):
        import MP_Audio_Player as player
        eq = player.EqualizerVisualizer()
        self.assertIn("cosmic_dreamworlds_radioactive", eq.THEMES)
        retro_idx = eq.THEMES.index("retro_terminal")
        skin_idx = eq.THEMES.index("cosmic_dreamworlds_radioactive")
        self.assertEqual(skin_idx, retro_idx + 1, "Skin should be positioned right after configured themes")

    def test_cycle_theme_to_skin(self):
        import MP_Audio_Player as player
        eq = player.EqualizerVisualizer()
        eq.set_theme("retro_terminal")
        self.assertEqual(eq.theme, "retro_terminal")
        eq.cycle_theme()
        self.assertEqual(eq.theme, "cosmic_dreamworlds_radioactive")
        self.assertEqual(
            eq.get_theme_display_name(),
            "Cosmic Dreamworlds Radioactive (Liquid Glass Skin)",
        )

    def test_liquid_glass_opengl_skin_registration(self):
        import liquid_glass_opengl as lgo
        self.assertIn("cosmic_dreamworlds_radioactive", lgo.THEME_COLORS)
        self.assertEqual(
            lgo.THEME_ALIASES.get("cosmic_dreamworlds_radioactive"),
            "cosmic_dreamworlds_radioactive",
        )
        self.assertEqual(
            lgo.THEME_ALIASES.get("radioactive"),
            "cosmic_dreamworlds_radioactive",
        )
        self.assertIn("cosmic_dreamworlds_radioactive", lgo.SKIN_FILES)
        self.assertTrue(lgo.SKIN_FILES["cosmic_dreamworlds_radioactive"].is_file())

    def test_liquid_glass_vulkan_registration(self):
        import liquid_glass_vulkan as lgv
        self.assertIn("cosmic_dreamworlds_radioactive", lgv.THEME_COLORS)
        self.assertEqual(
            lgv.THEME_ALIASES.get("cosmic_dreamworlds_radioactive"),
            "cosmic_dreamworlds_radioactive",
        )


if __name__ == "__main__":
    unittest.main()
