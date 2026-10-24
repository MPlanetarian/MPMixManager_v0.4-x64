#!/usr/bin/env python3
"""
Generate the MP Liquid Transparent Glass Icon for Desktop and Application Launchers.
Outputs:
- assets/mp_liquid_glass_icon.png (512x512 RGBA high-resolution glass icon)
- assets/mp_liquid_glass_icon.svg (Scalable vector graphic)
"""

import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
ASSETS_DIR = ROOT / "assets"
ASSETS_DIR.mkdir(parents=True, exist_ok=True)

PNG_PATH = ASSETS_DIR / "mp_liquid_glass_icon.png"
SVG_PATH = ASSETS_DIR / "mp_liquid_glass_icon.svg"


def generate_png_icon(size=512):
    # Canvas
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))

    # Dimensions
    pad = 40
    rect = [pad, pad, size - pad, size - pad]
    radius = 96

    # 1. Outer Ambient Glow & Soft Drop Shadow
    glow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    # Cyan-to-purple shadow blooms
    glow_draw.rounded_rectangle(
        [pad - 8, pad + 12, size - pad + 8, size - pad + 24],
        radius=radius + 4,
        fill=(0, 220, 255, 80)
    )
    glow_draw.rounded_rectangle(
        [pad - 12, pad + 16, size - pad + 12, size - pad + 32],
        radius=radius + 6,
        fill=(190, 80, 255, 60)
    )
    glow = glow.filter(ImageFilter.GaussianBlur(24))
    img.alpha_composite(glow)

    # 2. Main Glass Slab Base (Dark Translucent Liquid Ocean)
    slab = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    slab_draw = ImageDraw.Draw(slab)
    slab_draw.rounded_rectangle(rect, radius=radius, fill=(10, 22, 42, 225))

    # Add inner radial liquid gradient onto slab
    grad = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    cx, cy = size * 0.35, size * 0.35
    max_r = size * 0.75
    # Render procedural liquid caustics
    for y in range(pad, size - pad):
        for x in range(pad, size - pad):
            # Check if inside rounded rectangle approximately
            dx = max(pad + radius - x, 0, x - (size - pad - radius))
            dy = max(pad + radius - y, 0, y - (size - pad - radius))
            if dx * dx + dy * dy > radius * radius:
                continue
            dist = math.hypot(x - cx, y - cy) / max_r
            t = min(1.0, max(0.0, dist))
            # Fluid color blend: top-left cyan (#00f5ff) -> center ocean (#0d3b66) -> bottom-right amethyst (#c77dff)
            diag = (x + y) / (2.0 * size)
            r = int(12 + 180 * math.pow(diag, 2.2))
            g = int(180 * (1.0 - t * 0.7) + 30 * diag)
            b = int(240 * (1.0 - t * 0.3) + 210 * diag)
            a = int(170 + 60 * (1.0 - t))
            grad.putpixel((x, y), (r, min(255, g), min(255, b), a))

    slab = Image.alpha_composite(slab, grad)

    # 3. Inner Frosted Wells (Mimicking the Liquid Glass Player Panels)
    wells = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    wells_draw = ImageDraw.Draw(wells)
    # Upper Header Well
    wells_draw.rounded_rectangle([72, 72, size - 72, 134], radius=24, fill=(5, 12, 24, 160))
    # Main Lower Well
    wells_draw.rounded_rectangle([72, 150, size - 72, size - 72], radius=32, fill=(4, 10, 20, 190))
    wells = wells.filter(ImageFilter.GaussianBlur(1.5))
    slab = Image.alpha_composite(slab, wells)

    # 4. Central Graphic: Liquid Equalizer Waveform & Glass Play Badge
    eq = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    eq_draw = ImageDraw.Draw(eq)

    # Floating 11-band Equalizer Bars in Lower Well
    bars = [0.35, 0.55, 0.85, 0.70, 0.95, 1.0, 0.88, 0.75, 0.90, 0.60, 0.40]
    bar_w = 16
    spacing = 13
    total_w = len(bars) * bar_w + (len(bars) - 1) * spacing
    start_x = int((size - total_w) / 2)
    base_y = 360
    max_h = 130

    for i, bh in enumerate(bars):
        bx = start_x + i * (bar_w + spacing)
        h_px = int(bh * max_h)
        by = base_y - h_px
        frac = i / float(len(bars) - 1)

        # Gradient color per bar: cyan (#00f5ff) -> mint (#00f5d4) -> purple (#c77dff) -> pink (#ff007f)
        if frac < 0.4:
            s = frac / 0.4
            r = int(0 + 0 * s)
            g = int(245)
            b = int(255 - 43 * s)
        elif frac < 0.75:
            s = (frac - 0.4) / 0.35
            r = int(0 + 199 * s)
            g = int(245 - 120 * s)
            b = int(212 + 43 * s)
        else:
            s = (frac - 0.75) / 0.25
            r = int(199 + 56 * s)
            g = int(125 - 125 * s)
            b = int(255 - 128 * s)

        # Glowing halo
        eq_draw.rounded_rectangle(
            [bx - 3, by - 3, bx + bar_w + 3, base_y + 3],
            radius=9,
            fill=(r, g, b, 70)
        )
        # Core bar
        eq_draw.rounded_rectangle(
            [bx, by, bx + bar_w, base_y],
            radius=7,
            fill=(r, g, b, 230)
        )
        # Peak bead
        eq_draw.ellipse(
            [bx + 2, by - 12, bx + bar_w - 2, by - 4],
            fill=(255, 255, 255, 240)
        )

    # 5. Play Badge Icon (Prismatic Glass Triangle Overlay)
    play_cx, play_cy = size // 2, 235
    play_size = 38
    p1 = (play_cx - play_size * 0.7, play_cy - play_size)
    p2 = (play_cx + play_size * 1.05, play_cy)
    p3 = (play_cx - play_size * 0.7, play_cy + play_size)

    # Glow under play button
    eq_draw.polygon([p1, p2, p3], fill=(0, 245, 255, 110))
    # Play button core
    eq_draw.polygon(
        [
            (p1[0] + 3, p1[1] + 4),
            (p2[0] - 2, p2[1]),
            (p3[0] + 3, p3[1] - 4)
        ],
        fill=(255, 255, 255, 240)
    )

    # Frosted Monogram "MP" in Upper Header Well
    # Using clean vector polygons for M and P
    def draw_m(ox, oy, h=34):
        w = 34
        sw = 6
        # Left leg
        eq_draw.rectangle([ox, oy, ox + sw, oy + h], fill=(240, 250, 255, 235))
        # Right leg
        eq_draw.rectangle([ox + w - sw, oy, ox + w, oy + h], fill=(240, 250, 255, 235))
        # Diagonals
        eq_draw.polygon([
            (ox + sw - 1, oy),
            (ox + w // 2, oy + h * 0.65),
            (ox + w // 2 + 1, oy + h * 0.65),
            (ox + sw - 1, oy + sw * 1.5)
        ], fill=(0, 245, 255, 240))
        eq_draw.polygon([
            (ox + w - sw + 1, oy),
            (ox + w // 2, oy + h * 0.65),
            (ox + w // 2 - 1, oy + h * 0.65),
            (ox + w - sw + 1, oy + sw * 1.5)
        ], fill=(0, 245, 255, 240))

    def draw_p(ox, oy, h=34):
        w = 28
        sw = 6
        # Stem
        eq_draw.rectangle([ox, oy, ox + sw, oy + h], fill=(240, 250, 255, 235))
        # Loop outer
        eq_draw.rounded_rectangle([ox, oy, ox + w, oy + int(h * 0.62)], radius=10, fill=(199, 125, 255, 235))
        # Loop inner cutout
        eq_draw.rounded_rectangle([ox + sw, oy + sw, ox + w - sw, oy + int(h * 0.62) - sw], radius=5, fill=(5, 12, 24, 255))

    draw_m(size // 2 - 44, 86, h=34)
    draw_p(size // 2 + 8, 86, h=34)

    # Subtitle dots in upper well
    for dot_x in (size // 2 - 62, size // 2 + 52):
        eq_draw.ellipse([dot_x - 3, 100, dot_x + 3, 106], fill=(0, 245, 255, 200))

    slab = Image.alpha_composite(slab, eq)

    # 6. Curved Specular Gloss Highlight (Physical Glass Refraction Arch)
    gloss = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    gloss_draw = ImageDraw.Draw(gloss)
    gloss_draw.ellipse(
        [pad - 60, pad - 140, size - pad + 60, int(size * 0.58)],
        fill=(255, 255, 255, 38)
    )
    # Mask gloss to slab bounding box
    mask = Image.new("L", (size, size), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle(rect, radius=radius, fill=255)
    gloss_masked = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    gloss_masked.paste(gloss, (0, 0), mask)
    slab = Image.alpha_composite(slab, gloss_masked)

    # 7. Sloped Glass Rim (Luminous Gradient Border)
    rim = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    rim_draw = ImageDraw.Draw(rim)
    # Multi-pass antialiased bevel borders
    rim_draw.rounded_rectangle(
        rect,
        radius=radius,
        outline=(255, 255, 255, 180),
        width=3
    )
    # Top-left specular highlight rim
    rim_draw.rounded_rectangle(
        [pad + 2, pad + 2, size - pad - 2, size - pad - 2],
        radius=radius - 2,
        outline=(0, 245, 255, 140),
        width=2
    )
    # Bottom-right amethyst rim accent
    rim_draw.rounded_rectangle(
        [pad + 4, pad + 4, size - pad - 4, size - pad - 4],
        radius=radius - 4,
        outline=(199, 125, 255, 70),
        width=1
    )
    slab = Image.alpha_composite(slab, rim)

    # Final composite
    img.alpha_composite(slab)
    return img


def generate_svg_icon():
    svg_content = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512">
  <defs>
    <!-- Background Shadow Filter -->
    <filter id="glassGlow" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur stdDeviation="16" result="blur" />
      <feComposite in="SourceGraphic" in2="blur" operator="over" />
    </filter>

    <!-- Outer Rim Gradient -->
    <linearGradient id="rimGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#ffffff" stop-opacity="0.95" />
      <stop offset="35%" stop-color="#00f5ff" stop-opacity="0.85" />
      <stop offset="70%" stop-color="#4899ef" stop-opacity="0.75" />
      <stop offset="100%" stop-color="#c77dff" stop-opacity="0.90" />
    </linearGradient>

    <!-- Liquid Glass Body Gradient -->
    <radialGradient id="liquidGrad" cx="35%" cy="30%" r="75%">
      <stop offset="0%" stop-color="#00f5ff" stop-opacity="0.80" />
      <stop offset="25%" stop-color="#0c2340" stop-opacity="0.92" />
      <stop offset="65%" stop-color="#061224" stop-opacity="0.96" />
      <stop offset="100%" stop-color="#240046" stop-opacity="0.94" />
    </radialGradient>

    <!-- Equalizer Spectrum Gradient -->
    <linearGradient id="eqGrad" x1="0%" y1="100%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#00f5ff" />
      <stop offset="30%" stop-color="#00f5d4" />
      <stop offset="70%" stop-color="#c77dff" />
      <stop offset="100%" stop-color="#ff007f" />
    </linearGradient>

    <!-- Glass Specular Reflection Gradient -->
    <linearGradient id="specularGrad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#ffffff" stop-opacity="0.45" />
      <stop offset="60%" stop-color="#ffffff" stop-opacity="0.10" />
      <stop offset="100%" stop-color="#ffffff" stop-opacity="0.0" />
    </linearGradient>
  </defs>

  <!-- Ambient Glow -->
  <rect x="42" y="54" width="428" height="428" rx="100" fill="#00f5ff" opacity="0.30" filter="url(#glassGlow)" />
  <rect x="52" y="64" width="408" height="408" rx="96" fill="#c77dff" opacity="0.25" filter="url(#glassGlow)" />

  <!-- Main Glass Body Slab -->
  <rect x="40" y="40" width="432" height="432" rx="96" fill="url(#liquidGrad)" stroke="url(#rimGrad)" stroke-width="4" />

  <!-- Inner Wells -->
  <!-- Top Header Well -->
  <rect x="72" y="72" width="368" height="64" rx="22" fill="#030914" fill-opacity="0.65" stroke="#00f5ff" stroke-opacity="0.25" stroke-width="1.5" />
  <!-- Bottom Playlist/Visualizer Well -->
  <rect x="72" y="152" width="368" height="288" rx="28" fill="#02060f" fill-opacity="0.75" stroke="#c77dff" stroke-opacity="0.20" stroke-width="1.5" />

  <!-- MP Monogram in Header Well -->
  <g fill="#ffffff" fill-opacity="0.95">
    <!-- M -->
    <path d="M 210,88 L 217,88 L 227,112 L 237,88 L 244,88 L 244,120 L 238,120 L 238,97 L 229,118 L 225,118 L 216,97 L 216,120 L 210,120 Z" />
    <!-- P -->
    <path d="M 264,88 L 282,88 C 291,88 296,93 296,101 C 296,109 291,114 282,114 L 271,114 L 271,120 L 264,120 Z M 271,94 L 271,108 L 281,108 C 286,108 289,105 289,101 C 289,97 286,94 281,94 Z" />
  </g>
  <circle cx="188" cy="104" r="3" fill="#00f5ff" />
  <circle cx="318" cy="104" r="3" fill="#c77dff" />

  <!-- Central Play Badge (Glass Prism Triangle) -->
  <g filter="url(#glassGlow)">
    <polygon points="230,195 295,235 230,275" fill="#00f5ff" fill-opacity="0.35" />
  </g>
  <polygon points="232,198 290,235 232,272" fill="#ffffff" fill-opacity="0.95" />

  <!-- Floating Liquid Equalizer Spectrum Bars -->
  <g fill="url(#eqGrad)" opacity="0.90">
    <rect x="110" y="315" width="16" height="45" rx="8" />
    <rect x="138" y="285" width="16" height="75" rx="8" />
    <rect x="166" y="250" width="16" height="110" rx="8" />
    <rect x="194" y="270" width="16" height="90" rx="8" />
    <rect x="222" y="235" width="16" height="125" rx="8" />
    <rect x="250" y="225" width="16" height="135" rx="8" />
    <rect x="278" y="245" width="16" height="115" rx="8" />
    <rect x="306" y="260" width="16" height="100" rx="8" />
    <rect x="334" y="240" width="16" height="120" rx="8" />
    <rect x="362" y="280" width="16" height="80" rx="8" />
    <rect x="390" y="310" width="16" height="50" rx="8" />
  </g>

  <!-- Equalizer Peak Glyphs -->
  <g fill="#ffffff" opacity="0.95">
    <circle cx="118" cy="305" r="3" />
    <circle cx="146" cy="275" r="3" />
    <circle cx="174" cy="240" r="3" />
    <circle cx="202" cy="260" r="3" />
    <circle cx="230" cy="225" r="3" />
    <circle cx="258" cy="215" r="3" />
    <circle cx="286" cy="235" r="3" />
    <circle cx="314" cy="250" r="3" />
    <circle cx="342" cy="230" r="3" />
    <circle cx="370" cy="270" r="3" />
    <circle cx="398" cy="300" r="3" />
  </g>

  <!-- Specular Upper Glass Reflection Highlight -->
  <path d="M 44,140 C 44,80 80,44 140,44 L 372,44 C 432,44 468,80 468,140 C 468,180 380,260 256,260 C 132,260 44,180 44,140 Z" fill="url(#specularGrad)" />
</svg>
"""
    SVG_PATH.write_text(svg_content, encoding="utf-8")


def main():
    print("Generating MP Liquid Transparent Glass PNG icon...")
    png_img = generate_png_icon(512)
    png_img.save(PNG_PATH, format="PNG")
    print(f"✓ Saved PNG icon: {PNG_PATH}")

    print("Generating MP Liquid Transparent Glass SVG icon...")
    generate_svg_icon()
    print(f"✓ Saved SVG icon: {SVG_PATH}")

    # Also install to user local icons directory for desktop integration
    icons_dir = Path.home() / ".local" / "share" / "icons" / "hicolor" / "512x512" / "apps"
    icons_dir.mkdir(parents=True, exist_ok=True)
    local_png = icons_dir / "mp_liquid_glass_icon.png"
    png_img.save(local_png, format="PNG")

    user_icons = Path.home() / ".local" / "share" / "icons"
    user_icons.mkdir(parents=True, exist_ok=True)
    png_img.save(user_icons / "mp_liquid_glass_icon.png", format="PNG")
    (user_icons / "mp_liquid_glass_icon.svg").write_text(SVG_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"✓ Installed icons to {user_icons}")


if __name__ == "__main__":
    main()
