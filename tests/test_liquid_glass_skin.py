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
        skins = [
            "cosmic_dreamworlds_radioactive.png",
            "cosmic_dreamworlds.png",
            "orbital_void_reflux.png",
        ]
        for skin_file in skins:
            skin_path = ROOT / "assets" / "skins" / skin_file
            self.assertTrue(skin_path.is_file(), f"Skin file should exist: {skin_path}")
            with Image.open(skin_path) as img:
                self.assertEqual(img.size, (1280, 820), f"Skin {skin_file} should be cropped to 1280x820")
                self.assertEqual(img.mode, "RGBA")

    def test_theme_in_audio_player_order(self):
        import MP_Audio_Player as player
        eq = player.EqualizerVisualizer()
        self.assertIn("cosmic_dreamworlds_radioactive", eq.THEMES)
        self.assertIn("cosmic_dreamworlds", eq.THEMES)
        self.assertIn("orbital_void_reflux", eq.THEMES)
        retro_idx = eq.THEMES.index("retro_terminal")
        skin1_idx = eq.THEMES.index("cosmic_dreamworlds_radioactive")
        skin2_idx = eq.THEMES.index("cosmic_dreamworlds")
        skin3_idx = eq.THEMES.index("orbital_void_reflux")
        self.assertEqual(skin1_idx, retro_idx + 1, "Skin 1 should be positioned right after retro_terminal")
        self.assertEqual(skin2_idx, skin1_idx + 1, "Skin 2 should be right after skin 1")
        self.assertEqual(skin3_idx, skin2_idx + 1, "Skin 3 (orbital_void_reflux) should be right after skin 2")

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
        eq.cycle_theme()
        self.assertEqual(eq.theme, "cosmic_dreamworlds")
        self.assertEqual(
            eq.get_theme_display_name(),
            "Cosmic Dreamworlds (Liquid Glass Skin)",
        )
        eq.cycle_theme()
        self.assertEqual(eq.theme, "orbital_void_reflux")
        self.assertEqual(
            eq.get_theme_display_name(),
            "Orbital Void Reflux (Liquid Glass Skin)",
        )

    def test_liquid_glass_opengl_skin_registration(self):
        import liquid_glass_opengl as lgo
        for skin in ("cosmic_dreamworlds_radioactive", "cosmic_dreamworlds", "orbital_void_reflux"):
            self.assertIn(skin, lgo.THEME_COLORS)
            self.assertEqual(lgo.THEME_ALIASES.get(skin), skin)
            self.assertIn(skin, lgo.SKIN_FILES)
            self.assertTrue(lgo.SKIN_FILES[skin].is_file())
        self.assertEqual(
            lgo.THEME_ALIASES.get("radioactive"),
            "cosmic_dreamworlds_radioactive",
        )
        self.assertEqual(
            lgo.THEME_ALIASES.get("orbital"),
            "orbital_void_reflux",
        )
        self.assertEqual(
            lgo.THEME_ALIASES.get("void_reflux"),
            "orbital_void_reflux",
        )

    def test_liquid_glass_vulkan_registration(self):
        import liquid_glass_vulkan as lgv
        for skin in ("cosmic_dreamworlds_radioactive", "cosmic_dreamworlds", "orbital_void_reflux"):
            self.assertIn(skin, lgv.THEME_COLORS)
            self.assertEqual(lgv.THEME_ALIASES.get(skin), skin)
        self.assertEqual(
            lgv.THEME_ALIASES.get("orbital"),
            "orbital_void_reflux",
        )


if __name__ == "__main__":
    unittest.main()
