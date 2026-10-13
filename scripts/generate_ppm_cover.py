#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import os
import random
import re
import sys
import subprocess
import shutil
import struct
from pathlib import Path
from colorsys import hls_to_rgb

def generate_random_palette():
    palette = []
    for _ in range(4):
        h = random.random()
        l = random.uniform(0.3, 0.8)
        s = random.uniform(0.5, 0.9)
        r, g, b = hls_to_rgb(h, l, s)
        palette.append((int(r*255), int(g*255), int(b*255)))
    return palette

def render_ppm_gradient(width, height, style, palette):
    if style == "plasma":
        return render_plasma_gradient(width, height, palette)
    elif style == "linear":
        return render_linear_gradient(width, height, palette)
    # Add other gradient styles here...
    return render_plasma_gradient(width, height, palette)

def render_plasma_gradient(width, height, palette):
    ppm_data = b'P6\n{} {}\n255\n'.format(width, height).encode('ascii')
    for y in range(height):
        for x in range(width):
            hue = (x + y) / (width + height) * 4
            color = palette[int(hue) % 4]
            ppm_data += struct.pack('BBB', *color)
    return ppm_data

def render_linear_gradient(width, height, palette):
    ppm_data = b'P6\n{} {}\n255\n'.format(width, height).encode('ascii')
    for y in range(height):
        for x in range(width):
            hue = x / width
            color = palette[int(hue * 4) % 4]
            ppm_data += struct.pack('BBB', *color)
    return ppm_data

def apply_text_overlays_ffmpeg(ppm_path, png_path, artist, title, episode, tags):
    command = [
        "ffmpeg",
        "-y",
        "-i", str(ppm_path),
        "-vf",
        f"drawtext=text='{artist}':x=10:y=10:fontsize=36:fontcolor=white,"
        f"drawtext=text='{title}':x=10:y=50:fontsize=48:fontcolor=white,"
        f"drawtext=text='{episode}':x=10:y=90:fontsize=36:fontcolor=white,"
        f"drawtext=text='{tags}':x=10:y=130:fontsize=36:fontcolor=white,"
        f"drawbox=x=0:y=0:w=iw:h=ih:color=black@0.5:t=fill",
        str(png_path)
    ]
    result = subprocess.run(command, capture_output=True)
    return result.returncode == 0

def main():
    parser = argparse.ArgumentParser(description="Procedural PPM Cover Art Generator")
    parser.add_argument("--auto", action="store_true", help="Generate cover with default settings")
    parser.add_argument("--artist", default="MPlanetarian", help="Artist name")
    parser.add_argument("--title", default="Stream of Frequency", help="Mix title")
    parser.add_argument("--episode", default="Episode 041", help="Episode number")
    parser.add_argument("--tags", default="Deep Trance • Ambient Lounge", help="Subtitle tags")
    parser.add_argument("--size", type=int, default=1400, help="Width/Height in pixels")
    parser.add_argument("--style", default="plasma", choices=["linear", "plasma"])
    parser.add_argument("--output", help="Output PNG path")

    args = parser.parse_args()
    if args.auto:
        palette = generate_random_palette()
        ppm_data = render_ppm_gradient(args.size, args.size, args.style, palette)
        out_base = Path(__file__).resolve().parent / "COVERS" / f"Cover_{args.episode.replace(' ', '_')}"
        ppm_path = out_base.with_suffix(".ppm")
        png_path = Path(args.output) if args.output else out_base.with_suffix(".png")
        ppm_path.parent.mkdir(parents=True, exist_ok=True)
        with open(ppm_path, "wb") as f:
            f.write(ppm_data)
        if shutil.which("ffmpeg"):
            if apply_text_overlays_ffmpeg(ppm_path, png_path, args.artist, args.title, args.episode, args.tags):
                print(f"Generated {png_path}")
            else:
                print(f"FFmpeg failed. Generated {ppm_path}")
    else:
        print("Interactive mode not implemented.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("")
        sys.exit(0)