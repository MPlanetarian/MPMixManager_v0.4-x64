import math
import unittest
from pathlib import Path

from MP_Audio_Player import EqualizerVisualizer, _THEME_ALIASES, _THEME_PALETTES
from scripts.liquid_glass_opengl import (
    LiquidGlassRendererOpenGL,
    THEME_ALIASES as GL_ALIASES,
    THEME_COLORS as GL_COLORS,
    get_dynamic_theme_state as gl_dynamic_theme,
)
from scripts.liquid_glass_vulkan import (
    LiquidGlassRenderer as LiquidGlassRendererVulkan,
    THEME_ALIASES as VK_ALIASES,
    THEME_COLORS as VK_COLORS,
    get_dynamic_theme_state as vk_dynamic_theme,
)
from scripts.mix_web_companion import (
    THEMES as WEB_THEMES,
    THEME_ALIASES as WEB_ALIASES,
    render_html_page,
)

ROOT = Path(__file__).resolve().parent.parent


class TestDynamicRainbowLiquidGlass(unittest.TestCase):
    def test_default_transparency_reduced_by_10_percent(self):
        """Verify default core transparency is reduced by 10% (clear_opacity increased from 0.60 to 0.70)."""
        self.assertEqual(LiquidGlassRendererOpenGL.clear_opacity, 0.70)
        self.assertEqual(LiquidGlassRendererVulkan.clear_opacity, 0.70)

        # Shader sources check for 0.50 alpha (reduced by 10% from 0.40)
        gl_frag = (ROOT / "shaders" / "liquid_glass_gl.frag").read_text(encoding="utf-8")
        vk_frag = (ROOT / "shaders" / "liquid_glass.frag").read_text(encoding="utf-8")
        self.assertIn("float alpha = 0.50 *", gl_frag)
        self.assertIn("float alpha = 0.50 *", vk_frag)
        self.assertIn("alpha *= u.themeC.w;", gl_frag)
        self.assertIn("alpha *= u.themeC.w;", vk_frag)

    def test_dynamic_rainbow_theme_registration(self):
        """Verify theme registration across MP_Audio_Player, OpenGL, and Vulkan."""
        self.assertIn("dynamic_rainbow_liquid_glass", EqualizerVisualizer.THEMES)
        self.assertIn("dynamic_rainbow_liquid_glass", _THEME_PALETTES)
        self.assertEqual(_THEME_ALIASES.get("dynamic_liquid_glass_rainbow"), "dynamic_rainbow_liquid_glass")
        self.assertEqual(_THEME_ALIASES.get("rainbow"), "dynamic_rainbow_liquid_glass")

        self.assertIn("dynamic_rainbow_liquid_glass", GL_COLORS)
        self.assertIn("dynamic_rainbow_liquid_glass", VK_COLORS)
        self.assertEqual(GL_ALIASES.get("dynamic_liquid_glass_rainbow"), "dynamic_rainbow_liquid_glass")
        self.assertEqual(VK_ALIASES.get("dynamic_liquid_glass_rainbow"), "dynamic_rainbow_liquid_glass")

    def test_dynamic_transparency_oscillation_6_second_cycle(self):
        """Verify transparency changes between -9% and +9% over a 6-second period."""
        for dyn_fn in (gl_dynamic_theme, vk_dynamic_theme):
            # t = 0s: factor should be 1.0 (baseline)
            _, op0, f0 = dyn_fn("dynamic_rainbow_liquid_glass", base_opacity=1.0, current_time=0.0)
            self.assertAlmostEqual(f0, 1.0, places=4)
            self.assertAlmostEqual(op0, 1.0, places=4)

            # t = 1.5s (quarter cycle, peak): +9% increase -> factor 1.09
            _, op1_5, f1_5 = dyn_fn("dynamic_rainbow_liquid_glass", base_opacity=1.0, current_time=1.5)
            self.assertAlmostEqual(f1_5, 1.09, places=4)
            self.assertAlmostEqual(op1_5, 1.09, places=4)

            # t = 3.0s (half cycle): back to 1.0
            _, op3, f3 = dyn_fn("dynamic_rainbow_liquid_glass", base_opacity=1.0, current_time=3.0)
            self.assertAlmostEqual(f3, 1.0, places=4)
            self.assertAlmostEqual(op3, 1.0, places=4)

            # t = 4.5s (three-quarter cycle, trough): -9% reduction -> factor 0.91
            _, op4_5, f4_5 = dyn_fn("dynamic_rainbow_liquid_glass", base_opacity=1.0, current_time=4.5)
            self.assertAlmostEqual(f4_5, 0.91, places=4)
            self.assertAlmostEqual(op4_5, 0.91, places=4)

            # t = 6.0s (full cycle complete): back to 1.0
            _, op6, f6 = dyn_fn("dynamic_rainbow_liquid_glass", base_opacity=1.0, current_time=6.0)
            self.assertAlmostEqual(f6, 1.0, places=4)
            self.assertAlmostEqual(op6, 1.0, places=4)

    def test_dynamic_rainbow_colors_shift_over_time(self):
        """Verify liquid glass colors dynamically cycle through different rainbow colors over time."""
        c0, _, _ = gl_dynamic_theme("dynamic_rainbow_liquid_glass", current_time=0.0)
        c4, _, _ = gl_dynamic_theme("dynamic_rainbow_liquid_glass", current_time=4.5)
        c9, _, _ = gl_dynamic_theme("dynamic_rainbow_liquid_glass", current_time=9.0)

        # Colors should not be static; they must evolve over time
        self.assertNotEqual(c0, c4)
        self.assertNotEqual(c4, c9)
        self.assertNotEqual(c0, c9)

    def test_web_companion_dynamic_rainbow_theme(self):
        """Verify Web Companion supports dynamic liquid glass rainbow theme with animations."""
        self.assertIn("dynamic_rainbow_liquid_glass", WEB_THEMES)
        self.assertEqual(WEB_ALIASES.get("dynamic_liquid_glass_rainbow"), "dynamic_rainbow_liquid_glass")

        theme = WEB_THEMES["dynamic_rainbow_liquid_glass"]
        self.assertTrue(theme.get("is_dynamic_rainbow"))
        self.assertIn("Dynamic Liquid Glass [Rainbow Colours] (New)", theme["name"])

        html_out = render_html_page(theme)
        self.assertIn("dynamic-rainbow-glass-active", html_out)
        self.assertIn("dynamicRainbowHue", html_out)
        self.assertIn("dynamicRainbowBreath", html_out)
        self.assertIn("18s linear infinite", html_out)
        self.assertIn("6s ease-in-out infinite", html_out)

    def test_manager_themes_menu_includes_option_16(self):
        """Verify Mix_Archive_Manager.sh includes option 16 for Dynamic Liquid Glass."""
        mgr_sh = (ROOT / "Mix_Archive_Manager.sh").read_text(encoding="utf-8")
        self.assertIn("16|Dynamic Liquid Glass [Rainbow Colours] (New)", mgr_sh)
        self.assertIn("dynamic_rainbow_liquid_glass", mgr_sh)


if __name__ == "__main__":
    unittest.main()
