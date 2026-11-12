#!/usr/bin/env python3
"""
MP Mix Manager - Studio & DJ Booth Mobile Web Companion
Lightweight, standalone HTTP & REST server providing a modern, theme-adaptive
web dashboard accessible from phones, tablets, and remote browsers on the local LAN.
Displays live mix playback, tracklists, EQ visualizers, and remote playback controls.
Automatically synchronizes with the active theme currently running in Manager.
"""

import argparse
import html
import http.server
import json
import os
import random
import re
import socket
import subprocess
import sys
import threading
import time
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

PORT = 8888

def _get_app_version() -> str:
    ver = os.environ.get("VERSION")
    if ver:
        return ver.strip()
    s_dir = Path(__file__).resolve().parent
    for cand in [s_dir / "VERSION", s_dir.parent / "VERSION"]:
        if cand.is_file():
            try:
                return cand.read_text(encoding="utf-8").strip()
            except Exception:
                pass
    return "0.4.2 Stable (Liquid)"

VERSION = _get_app_version()

# ------------------------------------------------------------------------------
# THEME ENGINE — Palettes matching Mix_Archive_Manager.sh
# ------------------------------------------------------------------------------
THEMES: Dict[str, Dict[str, Any]] = {
    "dynamic_rainbow_liquid_glass": {
        "id": "dynamic_rainbow_liquid_glass",
        "name": "Dynamic Liquid Glass [Rainbow Colours] (New)",
        "bg": "#070614",
        "card_bg": "rgba(22, 16, 42, 0.70)",
        "card_border": "rgba(176, 88, 255, 0.45)",
        "card_shadow": "0 14px 40px rgba(0, 0, 0, 0.85)",
        "text_main": "#f3f0ff",
        "text_dim": "#a29bfe",
        "accent_primary": "#b058ff",     # Liquid Violet
        "accent_secondary": "#00f2fe",   # Aqua Cyan
        "accent_tertiary": "#ff2d8e",    # Liquid Rose
        "accent_crimson": "#ff0844",     # Rainbow Red
        "header_gradient": "linear-gradient(135deg, #b058ff 0%, #ff2d8e 35%, #fee140 70%, #00f2fe 100%)",
        "btn_gradient": "linear-gradient(135deg, #b058ff, #ff2d8e)",
        "btn_shadow": "0 4px 20px rgba(176, 88, 255, 0.55)",
        "progress_fill": "linear-gradient(90deg, #b058ff, #ff2d8e, #fee140, #00f2fe)",
        "badge_bg": "rgba(176, 88, 255, 0.20)",
        "badge_color": "#00f2fe",
        "eq_bar": "#00f2fe",
        "eq_peak": "#ff2d8e",
        "is_dynamic_rainbow": True,
    },
    "dreamworlds_liquid": {
        "id": "dreamworlds_liquid",
        "name": "MP Dreamworlds Liquid Transparency [Special Edition]",
        "bg": "#060b17",
        "card_bg": "rgba(11, 23, 44, 0.70)",
        "card_border": "rgba(0, 245, 255, 0.35)",
        "card_shadow": "0 12px 35px rgba(0, 0, 0, 0.85)",
        "text_main": "#e2f8ff",
        "text_dim": "#70a6c2",
        "accent_primary": "#00f5ff",     # Crystalline Aqua Cyan
        "accent_secondary": "#c77dff",   # Liquid Amethyst
        "accent_tertiary": "#00f5d4",    # Seafoam Mint
        "accent_crimson": "#ff4b82",     # Liquid Coral
        "header_gradient": "linear-gradient(135deg, #00f5ff 0%, #c77dff 50%, #4899ef 100%)",
        "btn_gradient": "linear-gradient(135deg, #00f5ff, #c77dff)",
        "btn_shadow": "0 4px 18px rgba(0, 245, 255, 0.45)",
        "progress_fill": "linear-gradient(90deg, #4899ef, #00f5ff, #00f5d4, #c77dff)",
        "badge_bg": "rgba(0, 245, 255, 0.15)",
        "badge_color": "#00f5ff",
        "eq_bar": "#00f5ff",
        "eq_peak": "#c77dff",
    },
    "cosmic_supernova": {
        "id": "cosmic_supernova",
        "name": "Cosmic Supernova [Special Edition]",
        "bg": "#0a0814",
        "card_bg": "#14112c",
        "card_border": "rgba(224, 86, 253, 0.32)",
        "card_shadow": "0 12px 35px rgba(10, 8, 20, 0.85)",
        "text_main": "#e2e8f0",
        "text_dim": "#7c8ba1",
        "accent_primary": "#00f5d4",     # Aurora Aquamarine
        "accent_secondary": "#e056fd",   # Nebula Orchid
        "accent_tertiary": "#fee440",    # Solar Flare Gold
        "accent_crimson": "#ff3366",     # Supernova Crimson
        "header_gradient": "linear-gradient(135deg, #ff3366 0%, #e056fd 50%, #00f5d4 100%)",
        "btn_gradient": "linear-gradient(135deg, #e056fd, #ff3366)",
        "btn_shadow": "0 4px 18px rgba(224, 86, 253, 0.45)",
        "progress_fill": "linear-gradient(90deg, #5e60ce, #e056fd, #00f5d4)",
        "badge_bg": "rgba(0, 245, 212, 0.15)",
        "badge_color": "#00f5d4",
        "eq_bar": "#00f5d4",
        "eq_peak": "#ff3366",
    },
    "dreamworlds": {
        "id": "dreamworlds",
        "name": "MPlanetarian Dreamworlds",
        "bg": "#0d0f18",
        "card_bg": "#151928",
        "card_border": "rgba(247, 37, 133, 0.28)",
        "card_shadow": "0 12px 35px rgba(0, 0, 0, 0.65)",
        "text_main": "#f0f3f6",
        "text_dim": "#7f8ba4",
        "accent_primary": "#f72585",     # Neon Pink
        "accent_secondary": "#00e5ff",   # Electric Cyan
        "accent_tertiary": "#ffaa00",    # Amber Gold
        "accent_crimson": "#ed254e",     # Coral Red
        "header_gradient": "linear-gradient(135deg, #f72585 0%, #00e5ff 100%)",
        "btn_gradient": "linear-gradient(135deg, #f72585, #ed254e)",
        "btn_shadow": "0 4px 18px rgba(247, 37, 133, 0.4)",
        "progress_fill": "linear-gradient(90deg, #f72585, #00e5ff)",
        "badge_bg": "rgba(0, 229, 255, 0.15)",
        "badge_color": "#00e5ff",
        "eq_bar": "#00e5ff",
        "eq_peak": "#f72585",
    },
    "dreamworlds_ultra": {
        "id": "dreamworlds_ultra",
        "name": "MP Mix Archive Manager (Dreamworlds Ultra)",
        "bg": "#000000",
        "card_bg": "#110e20",
        "card_border": "rgba(166, 77, 255, 0.38)",
        "card_shadow": "0 12px 35px rgba(0, 0, 0, 0.9)",
        "text_main": "#d1d1e0",
        "text_dim": "#9999ff",
        "accent_primary": "#a64dff",     # Hot Purple
        "accent_secondary": "#00ff00",   # Traffic Green
        "accent_tertiary": "#ff9933",    # Amber
        "accent_crimson": "#ff0000",     # Alert Red
        "header_gradient": "linear-gradient(135deg, #a64dff 0%, #00ff00 100%)",
        "btn_gradient": "linear-gradient(135deg, #a64dff, #ff0000)",
        "btn_shadow": "0 4px 18px rgba(166, 77, 255, 0.45)",
        "progress_fill": "linear-gradient(90deg, #00ff00, #ff9933, #ff0000)",
        "badge_bg": "rgba(0, 255, 0, 0.15)",
        "badge_color": "#00ff00",
        "eq_bar": "#00ff00",
        "eq_peak": "#ff0000",
    },
    "cyberpunk": {
        "id": "cyberpunk",
        "name": "Cyberpunk 2077",
        "bg": "#080812",
        "card_bg": "#121026",
        "card_border": "rgba(255, 0, 85, 0.35)",
        "card_shadow": "0 12px 35px rgba(0, 0, 0, 0.8)",
        "text_main": "#e0ffff",
        "text_dim": "#708090",
        "accent_primary": "#ff0055",     # Neon Pink
        "accent_secondary": "#00ffff",   # Cyan
        "accent_tertiary": "#ffff00",    # Neon Yellow
        "accent_crimson": "#ff0055",
        "header_gradient": "linear-gradient(135deg, #ff0055 0%, #ffff00 50%, #00ffff 100%)",
        "btn_gradient": "linear-gradient(135deg, #ff0055, #ff00aa)",
        "btn_shadow": "0 4px 18px rgba(255, 0, 85, 0.5)",
        "progress_fill": "linear-gradient(90deg, #ff0055, #ffff00, #00ffff)",
        "badge_bg": "rgba(0, 255, 255, 0.15)",
        "badge_color": "#00ffff",
        "eq_bar": "#00ffff",
        "eq_peak": "#ff0055",
    },
    "dracula": {
        "id": "dracula",
        "name": "Dracula",
        "bg": "#282a36",
        "card_bg": "#343746",
        "card_border": "rgba(189, 147, 249, 0.3)",
        "card_shadow": "0 12px 35px rgba(0, 0, 0, 0.6)",
        "text_main": "#f8f8f2",
        "text_dim": "#6272a4",
        "accent_primary": "#bd93f9",     # Purple
        "accent_secondary": "#ff79c6",   # Pink
        "accent_tertiary": "#8be9fd",    # Cyan
        "accent_crimson": "#ff5555",
        "header_gradient": "linear-gradient(135deg, #bd93f9 0%, #ff79c6 100%)",
        "btn_gradient": "linear-gradient(135deg, #bd93f9, #ff79c6)",
        "btn_shadow": "0 4px 18px rgba(189, 147, 249, 0.4)",
        "progress_fill": "linear-gradient(90deg, #bd93f9, #ff79c6, #8be9fd)",
        "badge_bg": "rgba(139, 233, 253, 0.15)",
        "badge_color": "#8be9fd",
        "eq_bar": "#50fa7b",
        "eq_peak": "#ff79c6",
    },
    "nord": {
        "id": "nord",
        "name": "Nord Frost",
        "bg": "#242933",
        "card_bg": "#2e3440",
        "card_border": "rgba(136, 192, 208, 0.3)",
        "card_shadow": "0 12px 35px rgba(0, 0, 0, 0.5)",
        "text_main": "#eceff4",
        "text_dim": "#929cb0",
        "accent_primary": "#88c0d0",     # Frost Cyan
        "accent_secondary": "#81a1c1",   # Frost Blue
        "accent_tertiary": "#a3be8c",    # Aurora Green
        "accent_crimson": "#bf616a",
        "header_gradient": "linear-gradient(135deg, #88c0d0 0%, #81a1c1 100%)",
        "btn_gradient": "linear-gradient(135deg, #5e81ac, #88c0d0)",
        "btn_shadow": "0 4px 18px rgba(136, 192, 208, 0.35)",
        "progress_fill": "linear-gradient(90deg, #5e81ac, #88c0d0, #a3be8c)",
        "badge_bg": "rgba(136, 192, 208, 0.15)",
        "badge_color": "#88c0d0",
        "eq_bar": "#88c0d0",
        "eq_peak": "#bf616a",
    },
    "matrix": {
        "id": "matrix",
        "name": "The Matrix",
        "bg": "#070b07",
        "card_bg": "#0e180e",
        "card_border": "rgba(0, 255, 102, 0.3)",
        "card_shadow": "0 12px 35px rgba(0, 20, 0, 0.8)",
        "text_main": "#d4ffd4",
        "text_dim": "#448844",
        "accent_primary": "#00ff66",     # Neon Green
        "accent_secondary": "#a6ff00",   # Lime
        "accent_tertiary": "#00cc44",
        "accent_crimson": "#ff3333",
        "header_gradient": "linear-gradient(135deg, #00ff66 0%, #a6ff00 100%)",
        "btn_gradient": "linear-gradient(135deg, #008f39, #00ff66)",
        "btn_shadow": "0 4px 18px rgba(0, 255, 102, 0.4)",
        "progress_fill": "linear-gradient(90deg, #008f39, #00ff66)",
        "badge_bg": "rgba(0, 255, 102, 0.15)",
        "badge_color": "#00ff66",
        "eq_bar": "#00ff66",
        "eq_peak": "#a6ff00",
    },
    "solarized": {
        "id": "solarized",
        "name": "Solarized Dark",
        "bg": "#00212b",
        "card_bg": "#073642",
        "card_border": "rgba(42, 161, 152, 0.3)",
        "card_shadow": "0 12px 35px rgba(0, 15, 20, 0.7)",
        "text_main": "#93a1a1",
        "text_dim": "#657b83",
        "accent_primary": "#2aa198",     # Cyan
        "accent_secondary": "#268bd2",   # Blue
        "accent_tertiary": "#b58900",    # Yellow
        "accent_crimson": "#dc322f",
        "header_gradient": "linear-gradient(135deg, #2aa198 0%, #268bd2 100%)",
        "btn_gradient": "linear-gradient(135deg, #268bd2, #2aa198)",
        "btn_shadow": "0 4px 18px rgba(42, 161, 152, 0.35)",
        "progress_fill": "linear-gradient(90deg, #268bd2, #2aa198)",
        "badge_bg": "rgba(42, 161, 152, 0.15)",
        "badge_color": "#2aa198",
        "eq_bar": "#2aa198",
        "eq_peak": "#cb4b16",
    },
    "tokyo": {
        "id": "tokyo",
        "name": "Tokyo Night",
        "bg": "#1a1b26",
        "card_bg": "#24283b",
        "card_border": "rgba(122, 162, 247, 0.3)",
        "card_shadow": "0 12px 35px rgba(0, 0, 0, 0.6)",
        "text_main": "#c0caf5",
        "text_dim": "#565f89",
        "accent_primary": "#7aa2f7",     # Blue
        "accent_secondary": "#bb9af7",   # Magenta
        "accent_tertiary": "#7dcfff",    # Cyan
        "accent_crimson": "#f7768e",
        "header_gradient": "linear-gradient(135deg, #7aa2f7 0%, #bb9af7 100%)",
        "btn_gradient": "linear-gradient(135deg, #7aa2f7, #bb9af7)",
        "btn_shadow": "0 4px 18px rgba(122, 162, 247, 0.4)",
        "progress_fill": "linear-gradient(90deg, #7aa2f7, #bb9af7, #7dcfff)",
        "badge_bg": "rgba(125, 207, 255, 0.15)",
        "badge_color": "#7dcfff",
        "eq_bar": "#7aa2f7",
        "eq_peak": "#f7768e",
    },
    "monokai": {
        "id": "monokai",
        "name": "Monokai Pro",
        "bg": "#1e1f1c",
        "card_bg": "#272822",
        "card_border": "rgba(249, 38, 114, 0.3)",
        "card_shadow": "0 12px 35px rgba(0, 0, 0, 0.6)",
        "text_main": "#f8f8f2",
        "text_dim": "#75715e",
        "accent_primary": "#f92672",     # Pink
        "accent_secondary": "#66d9ef",   # Cyan
        "accent_tertiary": "#a6e22e",    # Green
        "accent_crimson": "#f92672",
        "header_gradient": "linear-gradient(135deg, #f92672 0%, #66d9ef 100%)",
        "btn_gradient": "linear-gradient(135deg, #f92672, #ae81ff)",
        "btn_shadow": "0 4px 18px rgba(249, 38, 114, 0.4)",
        "progress_fill": "linear-gradient(90deg, #f92672, #ae81ff, #66d9ef)",
        "badge_bg": "rgba(102, 217, 239, 0.15)",
        "badge_color": "#66d9ef",
        "eq_bar": "#a6e22e",
        "eq_peak": "#f92672",
    },
    "gruvbox": {
        "id": "gruvbox",
        "name": "Gruvbox Dark",
        "bg": "#1d2021",
        "card_bg": "#282828",
        "card_border": "rgba(250, 189, 47, 0.3)",
        "card_shadow": "0 12px 35px rgba(0, 0, 0, 0.6)",
        "text_main": "#ebdbb2",
        "text_dim": "#a89984",
        "accent_primary": "#fabd2f",     # Yellow
        "accent_secondary": "#fe8019",   # Orange
        "accent_tertiary": "#8ec07c",    # Aqua
        "accent_crimson": "#fb4934",
        "header_gradient": "linear-gradient(135deg, #fabd2f 0%, #fe8019 100%)",
        "btn_gradient": "linear-gradient(135deg, #d65d0e, #fabd2f)",
        "btn_shadow": "0 4px 18px rgba(250, 189, 47, 0.35)",
        "progress_fill": "linear-gradient(90deg, #d65d0e, #fabd2f, #8ec07c)",
        "badge_bg": "rgba(250, 189, 47, 0.15)",
        "badge_color": "#fabd2f",
        "eq_bar": "#fabd2f",
        "eq_peak": "#fb4934",
    },
    "emerald": {
        "id": "emerald",
        "name": "Emerald Isle",
        "bg": "#081410",
        "card_bg": "#10261e",
        "card_border": "rgba(46, 204, 113, 0.3)",
        "card_shadow": "0 12px 35px rgba(0, 20, 15, 0.7)",
        "text_main": "#e0f2ec",
        "text_dim": "#528c77",
        "accent_primary": "#2ecc71",     # Emerald
        "accent_secondary": "#4ee0b5",   # Mint
        "accent_tertiary": "#f1c40f",    # Gold
        "accent_crimson": "#e74c3c",
        "header_gradient": "linear-gradient(135deg, #2ecc71 0%, #4ee0b5 100%)",
        "btn_gradient": "linear-gradient(135deg, #27ae60, #2ecc71)",
        "btn_shadow": "0 4px 18px rgba(46, 204, 113, 0.4)",
        "progress_fill": "linear-gradient(90deg, #1abc9c, #2ecc71, #4ee0b5)",
        "badge_bg": "rgba(78, 224, 181, 0.15)",
        "badge_color": "#4ee0b5",
        "eq_bar": "#2ecc71",
        "eq_peak": "#f1c40f",
    },
    "classic": {
        "id": "classic",
        "name": "Classic ANSI",
        "bg": "#101010",
        "card_bg": "#1a1a1a",
        "card_border": "rgba(0, 205, 205, 0.3)",
        "card_shadow": "0 12px 35px rgba(0, 0, 0, 0.8)",
        "text_main": "#e0e0e0",
        "text_dim": "#888888",
        "accent_primary": "#00cdcd",     # Cyan
        "accent_secondary": "#cd00cd",   # Magenta
        "accent_tertiary": "#00cd00",    # Green
        "accent_crimson": "#cd0000",
        "header_gradient": "linear-gradient(135deg, #00cdcd 0%, #cd00cd 100%)",
        "btn_gradient": "linear-gradient(135deg, #0077aa, #00cdcd)",
        "btn_shadow": "0 4px 18px rgba(0, 205, 205, 0.35)",
        "progress_fill": "linear-gradient(90deg, #0077aa, #00cdcd)",
        "badge_bg": "rgba(0, 205, 205, 0.15)",
        "badge_color": "#00cdcd",
        "eq_bar": "#00cdcd",
        "eq_peak": "#cd00cd",
    },
    "retro_terminal": {
        "id": "retro_terminal",
        "name": "Old Style Unix Terminal Retro Mode (White on Black)",
        "bg": "#000000",
        "card_bg": "#0a0a0a",
        "card_border": "rgba(255, 255, 255, 0.4)",
        "card_shadow": "0 12px 35px rgba(0, 0, 0, 0.95)",
        "text_main": "#ffffff",
        "text_dim": "#aaaaaa",
        "accent_primary": "#ffffff",
        "accent_secondary": "#cccccc",
        "accent_tertiary": "#ffffff",
        "accent_crimson": "#ffffff",
        "header_gradient": "linear-gradient(135deg, #ffffff 0%, #aaaaaa 100%)",
        "btn_gradient": "linear-gradient(135deg, #333333, #111111)",
        "btn_shadow": "0 4px 18px rgba(255, 255, 255, 0.2)",
        "progress_fill": "linear-gradient(90deg, #666666, #ffffff)",
        "badge_bg": "rgba(255, 255, 255, 0.15)",
        "badge_color": "#ffffff",
        "eq_bar": "#ffffff",
        "eq_peak": "#ffffff",
    },
    "retro_linux_memories": {
        "id": "retro_linux_memories",
        "name": "Retro Linux Memories",
        "bg": "#1e2226",
        "card_bg": "rgba(45, 45, 45, 0.90)",
        "card_border": "#3a3f44",
        "card_shadow": "0 8px 24px rgba(0, 0, 0, 0.70)",
        "text_main": "#ffffff",
        "text_dim": "#919190",
        "accent_primary": "#15539e",     # VeraCrypt Selection Blue
        "accent_secondary": "#5b86bb",   # GTK Slate Highlight Blue
        "accent_tertiary": "#f0ad4e",    # Amber Title Accent
        "accent_crimson": "#d9534f",     # GTK Classic Crimson
        "header_gradient": "linear-gradient(135deg, #15539e 0%, #2d3058 50%, #5b86bb 100%)",
        "btn_gradient": "linear-gradient(180deg, #3c3c3c 0%, #2a2a2a 100%)",
        "btn_shadow": "0 2px 8px rgba(0, 0, 0, 0.60)",
        "progress_fill": "linear-gradient(90deg, #15539e, #1b6acb, #5b86bb)",
        "badge_bg": "rgba(21, 83, 158, 0.25)",
        "badge_color": "#5b86bb",
        "eq_bar": "#15539e",
        "eq_peak": "#5b86bb",
    },
    "into_darkness_void_out": {
        "id": "into_darkness_void_out",
        "name": "Into Darkness (Void Out)",
        "bg": "#000000",
        "card_bg": "#000000",
        "card_border": "#303030",
        "card_shadow": "0 8px 24px rgba(0, 0, 0, 0.95)",
        "text_main": "#ffffff",
        "text_dim": "#a0a0a0",
        "accent_primary": "#ffffff",
        "accent_secondary": "#c8c8c8",
        "accent_tertiary": "#ffffff",
        "accent_crimson": "#ffffff",
        "header_gradient": "linear-gradient(135deg, #000000 0%, #080808 100%)",
        "btn_gradient": "linear-gradient(135deg, #181818, #000000)",
        "btn_shadow": "0 2px 8px rgba(0, 0, 0, 0.85)",
        "progress_fill": "linear-gradient(90deg, #555555, #ffffff)",
        "badge_bg": "rgba(255, 255, 255, 0.12)",
        "badge_color": "#ffffff",
        "eq_bar": "#c8c8c8",
        "eq_peak": "#ffffff",
    },
    "cosmic_dreamworlds_radioactive": {
        "id": "cosmic_dreamworlds_radioactive",
        "name": "Cosmic Dreamworlds Radioactive (Liquid Glass Skin)",
        "bg": "#050e08",
        "card_bg": "rgba(8, 20, 14, 0.78)",
        "card_border": "rgba(57, 255, 20, 0.45)",
        "card_shadow": "0 14px 45px rgba(0, 0, 0, 0.85), 0 0 25px rgba(57, 255, 20, 0.22)",
        "text_main": "#ffffff",
        "text_dim": "#a2e6b5",
        "accent_primary": "#39ff14",
        "accent_secondary": "#00f5d4",
        "accent_tertiary": "#a64dff",
        "accent_crimson": "#00ff66",
        "header_gradient": "linear-gradient(135deg, #39ff14 0%, #00f5d4 50%, #a64dff 100%)",
        "btn_gradient": "linear-gradient(135deg, #39ff14, #00f5d4)",
        "btn_shadow": "0 4px 18px rgba(57, 255, 20, 0.45)",
        "progress_fill": "linear-gradient(90deg, #39ff14, #00f5d4, #a64dff)",
        "badge_bg": "rgba(57, 255, 20, 0.20)",
        "badge_color": "#39ff14",
        "eq_bar": "#39ff14",
        "eq_peak": "#00f5d4",
    },
    "cosmic_dreamworlds": {
        "id": "cosmic_dreamworlds",
        "name": "Cosmic Dreamworlds (Liquid Glass Skin)",
        "bg": "#0c040d",
        "card_bg": "rgba(22, 9, 25, 0.78)",
        "card_border": "rgba(232, 13, 104, 0.45)",
        "card_shadow": "0 14px 45px rgba(0, 0, 0, 0.85), 0 0 25px rgba(232, 13, 104, 0.22)",
        "text_main": "#ffffff",
        "text_dim": "#fbcfe8",
        "accent_primary": "#e80d68",
        "accent_secondary": "#00f5d4",
        "accent_tertiary": "#b058ff",
        "accent_crimson": "#ff007f",
        "header_gradient": "linear-gradient(135deg, #e80d68 0%, #b058ff 50%, #00f5d4 100%)",
        "btn_gradient": "linear-gradient(135deg, #e80d68, #b058ff)",
        "btn_shadow": "0 4px 18px rgba(232, 13, 104, 0.45)",
        "progress_fill": "linear-gradient(90deg, #e80d68, #b058ff, #00f5d4)",
        "badge_bg": "rgba(232, 13, 104, 0.20)",
        "badge_color": "#e80d68",
        "eq_bar": "#e80d68",
        "eq_peak": "#00f5d4",
    },
    "orbital_void_reflux": {
        "id": "orbital_void_reflux",
        "name": "Orbital Void Reflux (Liquid Glass Skin)",
        "bg": "#080714",
        "card_bg": "rgba(15, 13, 36, 0.78)",
        "card_border": "rgba(0, 240, 255, 0.45)",
        "card_shadow": "0 14px 45px rgba(0, 0, 0, 0.85), 0 0 25px rgba(157, 78, 221, 0.25)",
        "text_main": "#ffffff",
        "text_dim": "#c8b6ff",
        "accent_primary": "#00f0ff",
        "accent_secondary": "#ff007f",
        "accent_tertiary": "#9d4edd",
        "accent_crimson": "#ff0055",
        "header_gradient": "linear-gradient(135deg, #00f0ff 0%, #9d4edd 50%, #ff007f 100%)",
        "btn_gradient": "linear-gradient(135deg, #00f0ff, #9d4edd)",
        "btn_shadow": "0 4px 18px rgba(0, 240, 255, 0.45)",
        "progress_fill": "linear-gradient(90deg, #00f0ff, #9d4edd, #ff007f)",
        "badge_bg": "rgba(0, 240, 255, 0.20)",
        "badge_color": "#00f0ff",
        "eq_bar": "#00f0ff",
        "eq_peak": "#ff007f",
    }
}

THEME_ALIASES: Dict[str, str] = {
    "cosmic_dreamworlds": "cosmic_dreamworlds",
    "cosmic_dreamworlds_(liquid_glass_skin)": "cosmic_dreamworlds",
    "cosmic dreamworlds (liquid glass skin)": "cosmic_dreamworlds",
    "cosmic dreamworlds": "cosmic_dreamworlds",
    "cosmic_dream": "cosmic_dreamworlds",
    "cosmic dream": "cosmic_dreamworlds",
    "cosmic_dreamworld": "cosmic_dreamworlds",
    "cosmic dreamworld": "cosmic_dreamworlds",
    "cosmic_dreamworlds_radioactive": "cosmic_dreamworlds_radioactive",
    "cosmic_dreamworlds_radioactive_(liquid_glass_skin)": "cosmic_dreamworlds_radioactive",
    "cosmic dreamworlds radioactive (liquid glass skin)": "cosmic_dreamworlds_radioactive",
    "cosmic dreamworlds radioactive": "cosmic_dreamworlds_radioactive",
    "cosmic_radioactive": "cosmic_dreamworlds_radioactive",
    "radioactive": "cosmic_dreamworlds_radioactive",
    "orbital_void_reflux": "orbital_void_reflux",
    "orbital_void_reflux_(liquid_glass_skin)": "orbital_void_reflux",
    "orbital void reflux (liquid glass skin)": "orbital_void_reflux",
    "orbital void reflux": "orbital_void_reflux",
    "orbital_void": "orbital_void_reflux",
    "void_reflux": "orbital_void_reflux",
    "orbital": "orbital_void_reflux",
    "dynamic_rainbow_liquid_glass": "dynamic_rainbow_liquid_glass",
    "dynamic_liquid_glass_rainbow": "dynamic_rainbow_liquid_glass",
    "dynamic_rainbow": "dynamic_rainbow_liquid_glass",
    "rainbow_liquid_glass": "dynamic_rainbow_liquid_glass",
    "rainbow": "dynamic_rainbow_liquid_glass",
    "dynamic_liquid_glass": "dynamic_rainbow_liquid_glass",
    "dynamic_liquid_glass_[rainbow_colours]_(new)": "dynamic_rainbow_liquid_glass",
    "dynamic_liquid_glass_[rainbow_colours]": "dynamic_rainbow_liquid_glass",
    "dynamic liquid glass [rainbow colours] (new)": "dynamic_rainbow_liquid_glass",
    "dynamic liquid glass [rainbow colours]": "dynamic_rainbow_liquid_glass",
    "mp_dreamworlds_liquid_transparency": "dreamworlds_liquid",
    "dreamworlds_liquid_transparency": "dreamworlds_liquid",
    "liquid_transparency": "dreamworlds_liquid",
    "liquid": "dreamworlds_liquid",
    "glass": "dreamworlds_liquid",
    "liquid_glass": "dreamworlds_liquid",
    "mplanetarian_dreamworlds": "dreamworlds",
    "mplanetarian": "dreamworlds",
    "default": "dreamworlds",
    "ultra": "dreamworlds_ultra",
    "dreamworlds ultra": "dreamworlds_ultra",
    "dreamworlds_ultra_mp_mix_manager": "dreamworlds_ultra",
    "mp mix archive manager (dreamworlds ultra)": "dreamworlds_ultra",
    "cosmic": "cosmic_supernova",
    "supernova": "cosmic_supernova",
    "cosmic supernova": "cosmic_supernova",
    "cosmic supernova [special]": "cosmic_supernova",
    "cosmic supernova [special edition]": "cosmic_supernova",
    "cosmic_supernova_mp_mix_manager": "cosmic_supernova",
    "the matrix": "matrix",
    "tokyo night": "tokyo",
    "solarized dark": "solarized",
    "monokai pro": "monokai",
    "gruvbox dark": "gruvbox",
    "emerald isle": "emerald",
    "classic ansi": "classic",
    "retro_terminal": "retro_terminal",
    "unix_terminal": "retro_terminal",
    "retro_unix": "retro_terminal",
    "old_style_unix": "retro_terminal",
    "white_on_black": "retro_terminal",
    "retro": "retro_terminal",
    "terminal": "retro_terminal",
    "vt100": "retro_terminal",
    "old style unix terminal retro mode (white on black)": "retro_terminal",
    "old style unix terminal": "retro_terminal",
    "retro_linux_memories": "retro_linux_memories",
    "into_darkness_void_out": "into_darkness_void_out",
    "into darkness (void out)": "into_darkness_void_out",
    "into darkness": "into_darkness_void_out",
    "void out": "into_darkness_void_out",
    "retro_linux": "retro_linux_memories",
    "linux_memories": "retro_linux_memories",
    "retro-linux-memories": "retro_linux_memories",
    "retro-linux": "retro_linux_memories",
    "retro linux memories": "retro_linux_memories",
    "retro linux": "retro_linux_memories",
    "veracrypt": "retro_linux_memories",
    "retrolinux": "retro_linux_memories",
    "linux": "retro_linux_memories",
}

CLI_THEME: Optional[str] = None
WEB_THEME_FILE = Path.home() / ".config" / "mix-manager" / "web_companion_theme"
_tracklist_cache: Dict[str, str] = {}


def get_base_dir() -> Path:
    p = Path(__file__).resolve()
    return p.parent.parent if p.parent.name == "scripts" else p.parent


def normalize_theme_id(value: Any) -> Optional[str]:
    """Map a theme name, alias, or id to a real palette id."""
    if not value:
        return None
    key = str(value).strip().lower()
    if not key:
        return None
    if key in THEME_ALIASES:
        return THEME_ALIASES[key]
    if key in THEMES:
        return key
    # Accept a human-readable palette name too, e.g. "Retro Linux Memories".
    for tid, palette in THEMES.items():
        if str(palette.get("name", "")).strip().lower() == key:
            return tid
    return None


def get_web_theme_override() -> Optional[str]:
    """Theme chosen from the web companion UI. It wins over the manager theme."""
    if WEB_THEME_FILE.is_file():
        try:
            return normalize_theme_id(WEB_THEME_FILE.read_text(encoding="utf-8").strip())
        except Exception:
            pass
    return None


def set_web_theme(theme_id: str) -> Optional[str]:
    tid = normalize_theme_id(theme_id)
    if not tid:
        return None
    try:
        WEB_THEME_FILE.parent.mkdir(parents=True, exist_ok=True)
        WEB_THEME_FILE.write_text(tid + "\n", encoding="utf-8")
    except Exception:
        return None
    return tid


def available_themes() -> List[Dict[str, str]]:
    return [
        {"id": tid, "name": str(palette.get("name", tid))}
        for tid, palette in THEMES.items()
    ]


def get_current_theme_id(cli_theme: Optional[str] = None) -> str:
    if cli_theme:
        k = cli_theme.strip().lower()
        if k in THEME_ALIASES: return THEME_ALIASES[k]
        if k in THEMES: return k

    override = get_web_theme_override()
    if override:
        return override

    env_theme = os.environ.get("CURRENT_THEME", "").strip().lower()
    if env_theme:
        if env_theme in THEME_ALIASES: return THEME_ALIASES[env_theme]
        if env_theme in THEMES: return env_theme

    theme_file = Path.home() / ".config" / "mix-manager" / "theme"
    if theme_file.is_file():
        try:
            saved = theme_file.read_text(encoding="utf-8").strip().lower()
            if saved in THEME_ALIASES: return THEME_ALIASES[saved]
            if saved in THEMES: return saved
        except Exception:
            pass

    return "cosmic_supernova" if "cosmic_supernova" in THEMES else "dreamworlds"


def get_theme_palette(cli_theme: Optional[str] = None) -> Dict[str, Any]:
    tid = get_current_theme_id(cli_theme)
    return THEMES.get(tid, THEMES["dreamworlds"])


def get_local_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip


# ------------------------------------------------------------------------------
# STREAMING SERVICE STATE
#
# This process is an HTTP streamer only. It deliberately contains no IPC to a
# local audio player, because it must never cause sound on the host machine.
# ------------------------------------------------------------------------------
CONFIG_DIR = Path.home() / ".config" / "mix-manager"

AUDIO_EXTENSIONS = (".flac", ".wav", ".mp3", ".ogg", ".m4a", ".aac", ".aiff", ".wma")
AUDIO_CONTENT_TYPES = {
    ".flac": "audio/flac",
    ".wav": "audio/wav",
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
    ".aac": "audio/aac",
    ".ogg": "audio/ogg",
    ".aiff": "audio/aiff",
    ".wma": "audio/x-ms-wma",
}
RESUME_FILE = CONFIG_DIR / "playback_resume.json"
PLAYLIST_DIR = CONFIG_DIR / "playlists"
MUSIC_FOLDERS_FILE = CONFIG_DIR / "music_folders.json"
WEB_MODE_FILE = CONFIG_DIR / "web_companion_mode"

# Same libraries the MP Audio Player switches between with [1], [2] and [3].
LIBRARY_MODE_MIX = "MIX_ARCHIVE"
LIBRARY_MODE_MUSIC = "MUSIC"
LIBRARY_MODE_FAVORITES = "FAVORITES"
MODE_LABELS = {
    LIBRARY_MODE_MIX: "Mix Archive",
    LIBRARY_MODE_MUSIC: "Music",
    LIBRARY_MODE_FAVORITES: "Favorites",
}
# The Favorites playlist is shared with the MP Audio Player, which writes it on
# every [H] mark, so the companion only ever reads it.
FAVORITES_FILE = CONFIG_DIR / "favorites.json"

_autoplay_done = threading.Event()
_autoplay_result: Dict[str, Any] = {"status": "pending", "detail": ""}

# The resolved stream queue is expensive to build for a large music library, so
# it is cached per mode for a few seconds while the dashboard polls.
QUEUE_CACHE_TTL = 10.0
_queue_cache: Optional[Tuple[str, float, Tuple[str, ...]]] = None
_queue_source_state: Dict[str, Any] = {"fallback": False, "detail": ""}
# Resolving the queue can take seconds (a 51k-entry music playlist), and the
# dashboard polls hard. Only one thread may scan; the rest wait and then read
# the fresh cache instead of starting their own scan.
_queue_build_lock = threading.Lock()


# ------------------------------------------------------------------------------
# STREAM CATALOG & QUEUE
#
# This service is a pure HTTP audio streamer. It never opens a sound device and
# never spawns a local player: phones and tablets pull the mix themselves from
# /api/stream. Everything below is bookkeeping for which file to serve next.
# ------------------------------------------------------------------------------
def _env_flag(name: str, default: bool = True) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return str(raw).strip().lower() not in ("0", "false", "no", "off", "")


def read_config_env() -> Dict[str, str]:
    """Read config.env so the service sees manager settings without systemd env."""
    cfg: Dict[str, str] = {}
    for cand in (get_base_dir() / "config.env", CONFIG_DIR / "config.env"):
        if not cand.is_file():
            continue
        try:
            for line in cand.read_text(encoding="utf-8", errors="ignore").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    cfg.setdefault(key.strip(), val.strip().strip("\"'"))
        except Exception:
            pass
    return cfg


def _config_value(key: str, default: str = "") -> str:
    if key in os.environ:
        return os.environ[key]
    return read_config_env().get(key, default)


def is_audio_file(path: Any) -> bool:
    try:
        return bool(path) and Path(str(path)).suffix.lower() in AUDIO_EXTENSIONS
    except Exception:
        return False


def get_library_mode() -> str:
    """Which library the companion streams from: MIX_ARCHIVE, MUSIC or FAVORITES.

    The web toggle persists here so a phone can switch libraries and the choice
    survives a service restart. Falls back to WEB_COMPANION_MODE in config.env,
    then to the mix archive.
    """
    if WEB_MODE_FILE.is_file():
        try:
            saved = WEB_MODE_FILE.read_text(encoding="utf-8").strip().upper()
            if saved in MODE_LABELS:
                return saved
        except Exception:
            pass
    configured = (_config_value("WEB_COMPANION_MODE", "") or "").strip().upper()
    if configured in MODE_LABELS:
        return configured
    return LIBRARY_MODE_MIX


def set_library_mode(mode: str) -> Optional[str]:
    """Persist the library choice and restart the queue at its first entry."""
    target = str(mode or "").strip().upper()
    if target in ("MIX", "MIXES", "ARCHIVE", "MIXARCHIVE"):
        target = LIBRARY_MODE_MIX
    elif target in ("MUSIC", "TRACKS", "SONGS", "LIBRARY"):
        target = LIBRARY_MODE_MUSIC
    elif target in ("FAV", "FAVS", "FAVES", "FAVOURITE", "FAVOURITES", "FAVORITE", "FAVORITES"):
        target = LIBRARY_MODE_FAVORITES
    if target not in MODE_LABELS:
        return None
    unchanged = get_library_mode() == target
    try:
        WEB_MODE_FILE.parent.mkdir(parents=True, exist_ok=True)
        WEB_MODE_FILE.write_text(target + "\n", encoding="utf-8")
    except Exception:
        return None
    # Tapping the library that is already active must not rewind the stream to
    # track one or pay for another library scan.
    if unchanged:
        return target
    invalidate_queue_cache()
    reset_stream_for_new_library()
    return target


def reset_stream_for_new_library() -> None:
    """Point the stream at the first entry of the newly selected library.

    Playback state carries over, so switching libraries while listening keeps
    the phone playing - it just starts the new library from track one. The
    dashboard sees the file change and re-points its <audio> element.
    """
    was_playing = bool(load_stream_session().get("playing"))
    queue = build_stream_queue()
    with _stream_lock:
        state = load_stream_session()
        state.update({
            "index": 0,
            "path": queue[0] if queue else "",
            "position_sec": 0.0,
            "started_at": 0.0,
            "duration_sec": probe_duration(queue[0]) if queue else 0.0,
            "playing": was_playing and bool(queue),
        })
        if state["playing"]:
            state["started_at"] = time.time()
        save_stream_session(state)


def scan_playlist_files() -> List[str]:
    """Return the playlist the companion should play from.

    Order of preference:
      1. WEB_COMPANION_PLAYLIST (explicit .m3u/.m3u8/.json file)
      2. Saved player playlist for the selected library mode
      3. Every audio file in the configured folders for that mode, newest first

    An empty list means "there is nothing to play" and autoplay is skipped.
    """
    explicit = _config_value("WEB_COMPANION_PLAYLIST", "").strip()
    if explicit:
        return _read_playlist_file(Path(os.path.expanduser(explicit)))

    if get_library_mode() == LIBRARY_MODE_MUSIC:
        files = scan_music_files()
        if files:
            return files
        # An unconfigured or unreachable music library must not leave the
        # companion with nothing to stream, so fall through to the archive.
        return scan_archive_files()

    return scan_archive_files()


def music_playlist_candidates() -> List[Path]:
    """The combined per-machine music playlist, mirroring the MP Audio Player.

    music_folders_manager.py writes the "ALL_MUSIC_FOLDERS" playlist beside the
    per-machine list, under either the config playlists dir or the legacy
    PLAYLISTS_GENERATED folder inside the app.
    """
    base = get_base_dir()
    names = (
        "DJ_Tracks_ALL_MUSIC_FOLDERS.json",
        "DJ_Tracks_ALL_MUSIC_FOLDERS.m3u8",
        "DJ_Tracks_ALL_MUSIC_FOLDERS.m3u",
    )
    dirs = [PLAYLIST_DIR,
            CONFIG_DIR / "PLAYLISTS_GENERATED",
            base / "PLAYLISTS_GENERATED",
            base / "playlists"]
    return [d / name for d in dirs for name in names]


def music_folder_roots() -> List[Path]:
    """Local paths of the configured music folders, skipping SMB/UNC entries.

    A share such as \\\\192.168.1.138\\MUSIC001 only becomes a filesystem path
    once the desktop has mounted it, so those entries are ignored here rather
    than reported as unreadable folders.
    """
    roots: List[Path] = []
    seen = set()
    try:
        if not MUSIC_FOLDERS_FILE.is_file():
            return roots
        data = json.loads(MUSIC_FOLDERS_FILE.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return roots

    for folder in (data.get("folders") if isinstance(data, dict) else data) or []:
        if not isinstance(folder, dict):
            continue
        if str(folder.get("type", "")).lower() in ("smb", "nfs", "remote", "unc"):
            continue
        raw = str(folder.get("local_path") or folder.get("path") or "").strip()
        if not raw or raw.startswith("\\\\") or raw.startswith("//"):
            continue
        try:
            p = Path(os.path.expanduser(raw)).resolve()
        except Exception:
            continue
        if p.is_dir() and str(p) not in seen:
            seen.add(str(p))
            roots.append(p)
    return roots


_music_scan_cache: Optional[Tuple[Tuple[Tuple[str, float, int], ...], Tuple[str, ...]]] = None


def _music_scan_signature() -> Tuple[Tuple[str, float, int], ...]:
    """Identity of the music playlist files, so a big JSON is parsed only once."""
    sig: List[Tuple[str, float, int]] = []
    for cand in music_playlist_candidates():
        try:
            st = cand.stat()
            sig.append((str(cand), st.st_mtime, st.st_size))
        except OSError:
            continue
    return tuple(sig)


def scan_music_files() -> List[str]:
    """The MUSIC library: generated playlist first, then the folder roots.

    The combined playlist holds tens of thousands of paths in a ~30 MB JSON
    file, so a re-parse on every library switch made the Mix/Music buttons feel
    dead. The parsed result is reused until the playlist file changes.
    """
    global _music_scan_cache

    signature = _music_scan_signature()
    if _music_scan_cache and _music_scan_cache[0] == signature:
        return list(_music_scan_cache[1])

    files: List[str] = []
    for cand in music_playlist_candidates():
        if not cand.is_file():
            continue
        files = _read_playlist_file(cand)
        if files:
            break
    if not files:
        files = _scan_dirs(music_folder_roots())

    _music_scan_cache = (signature, tuple(files))
    return list(files)


def _favorite_key(path: Any) -> str:
    """Identity used to de-duplicate Favorites, matching the MP Audio Player."""
    raw = str(path or "").strip()
    if not raw:
        return ""
    if raw.startswith(("\\\\", "//", "smb://")):
        return raw.replace("\\", "/").rstrip("/").lower()
    try:
        return os.path.normcase(os.path.abspath(os.path.expanduser(raw)))
    except Exception:
        return os.path.normcase(raw)


def scan_favorite_files() -> List[str]:
    """The FAVORITES library: the playlist the MP Audio Player marks with [H].

    favorites.json is the authoritative list (favorites.m3u8 is a mirror of it),
    so it is read in saved order - the player's Favorites order is meaningful,
    unlike the newest-first archive and music scans. The file is re-read on each
    call because it is tiny and the player may mark a track at any moment.
    """
    paths: List[str] = []
    seen = set()
    for cand in (FAVORITES_FILE, FAVORITES_FILE.with_suffix(".m3u8")):
        if not cand.is_file():
            continue
        for path in _read_playlist_file(cand):
            key = _favorite_key(path)
            if not key or key in seen:
                continue
            seen.add(key)
            paths.append(path)
        if paths:
            break
    return paths


def _scan_dirs(roots: List[Path]) -> List[str]:
    """Newest-first audio files underneath the given directories."""
    skip = {"__pycache__", "node_modules", ".git", "venv", ".venv"}
    found: List[Tuple[float, str]] = []
    seen = set()
    for root_dir in roots:
        for root, subdirs, files in os.walk(root_dir):
            subdirs[:] = [d for d in subdirs if not d.startswith(".") and d not in skip]
            for name in files:
                if not is_audio_file(name):
                    continue
                full = os.path.join(root, name)
                if full in seen:
                    continue
                seen.add(full)
                try:
                    st = os.stat(full)
                except OSError:
                    continue
                # A zero-byte file (usually an interrupted conversion) would
                # stall the phone on an empty body, so it is not streamable.
                if st.st_size <= 0:
                    continue
                found.append((st.st_mtime, full))
    found.sort(key=lambda item: item[0], reverse=True)
    return [path for _, path in found]


def _read_playlist_file(path: Path) -> List[str]:
    if not path.is_file():
        return []
    try:
        if path.suffix.lower() == ".json":
            data = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
            raw = data.get("tracks") if isinstance(data, dict) else data
            paths: List[str] = []
            for item in raw or []:
                if isinstance(item, dict):
                    item = item.get("path") or item.get("file") or ""
                if isinstance(item, str) and is_audio_file(item):
                    paths.append(item)
            return [p for p in paths if os.path.isfile(p)]
        paths = []
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if is_audio_file(line):
                paths.append(line)
        return [p for p in paths if os.path.isfile(p)]
    except Exception:
        return []


def _archive_dirs() -> List[Path]:
    dirs: List[Path] = []
    seen = set()

    def add(value: Any) -> None:
        if not value:
            return
        try:
            p = Path(os.path.expanduser(str(value).strip().strip("\"'"))).resolve()
            if p.is_dir() and str(p) not in seen:
                seen.add(str(p))
                dirs.append(p)
        except Exception:
            pass

    add(_config_value("MIX_ARCHIVE_DIR", ""))
    for part in re.split(r"[;\n,]", _config_value("EXTRA_MIX_ARCHIVE_DIRS", "") or ""):
        add(part)
    base = get_base_dir()
    for name in ("MIX_ARCHIVE", "FLAC_CONVERTED_OUTPUTS"):
        add(base / name)
    return dirs


def scan_archive_files() -> List[str]:
    """Newest-first audio files across the configured archive folders."""
    return _scan_dirs(_archive_dirs())


# ------------------------------------------------------------------------------
# STREAM CATALOG
#
# Pure HTTP streaming state. No sound device is ever opened and no local player
# process is ever spawned - the phone or tablet is the only audio output.
# ------------------------------------------------------------------------------
def player_position(status: Optional[Dict[str, Any]]) -> float:
    try:
        return float((status or {}).get("position_sec", 0.0) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def load_resume_state() -> Optional[Dict[str, Any]]:
    if not RESUME_FILE.is_file():
        return None
    try:
        data = json.loads(RESUME_FILE.read_text(encoding="utf-8", errors="ignore"))
        if isinstance(data, dict) and data.get("path") and os.path.isfile(str(data["path"])):
            return data
    except Exception:
        pass
    return None


def _pick_start_track(playlist: List[str]) -> Tuple[Optional[str], float]:
    """Choose the resume track when it is still in the playlist, else the first."""
    resume = load_resume_state()
    if resume:
        saved_path = str(resume.get("path"))
        try:
            saved_pos = max(0.0, float(resume.get("position_sec", 0.0) or 0.0))
        except (TypeError, ValueError):
            saved_pos = 0.0
        if saved_path in playlist:
            return saved_path, saved_pos
    return (playlist[0], 0.0) if playlist else (None, 0.0)


def build_stream_queue() -> List[str]:
    """Resolve the play queue the phones will stream through.

    Scanning the music playlist stats tens of thousands of paths, so the result
    is cached briefly. Without this every 2-second status poll would re-walk the
    library.
    """
    global _queue_cache

    mode = get_library_mode()
    now = time.time()
    cached = _queue_cache
    if cached and cached[0] == mode and (now - cached[1]) < QUEUE_CACHE_TTL:
        return list(cached[2])

    with _queue_build_lock:
        # Another request may have finished the scan while this one waited.
        now = time.time()
        cached = _queue_cache
        if cached and cached[0] == mode and (now - cached[1]) < QUEUE_CACHE_TTL:
            return list(cached[2])

        if mode == LIBRARY_MODE_MUSIC:
            files = scan_music_files()
            # An unmounted SMB share leaves the generated playlist full of paths
            # that no longer resolve. Falling back keeps audio flowing, but the
            # status call reports it so the phone is not silently mislabelled.
            _queue_source_state.update({
                "fallback": not files,
                "detail": "" if files else "Music library offline - streaming Mix Archive",
            })
            if not files:
                files = scan_archive_files()
        elif mode == LIBRARY_MODE_FAVORITES:
            files = scan_favorite_files()
            # An empty Favorites playlist is a normal state, not a broken
            # library, so it is reported as empty instead of borrowed from
            # another mode. Marking tracks with [H] in the player fills it.
            _queue_source_state.update({
                "fallback": False,
                "detail": "" if files else "No favorites yet - press H in the player to add one",
            })
        else:
            _queue_source_state.update({"fallback": False, "detail": ""})
            files = scan_archive_files()

        if files and _env_flag("WEB_COMPANION_SHUFFLE", False):
            files = list(files)
            random.shuffle(files)

        _queue_cache = (mode, now, tuple(files))
        return list(files)


def invalidate_queue_cache() -> None:
    global _queue_cache, _music_scan_cache
    _queue_cache = None
    _music_scan_cache = None


def autoplay_once() -> Dict[str, Any]:
    """Arm the stream at startup so a phone starts playing with no extra taps.

    Nothing is played on the host: the session is only marked as playing, which
    makes /api/status report a running stream so the browser dashboard points
    its <audio> element at /api/stream and autoplays. The phone is the only
    audio output.
    """
    if _autoplay_done.is_set():
        return dict(_autoplay_result)

    if not _env_flag("WEB_COMPANION_AUTOPLAY", True):
        _autoplay_result.update(status="disabled", detail="Autoplay disabled by WEB_COMPANION_AUTOPLAY")
        _autoplay_done.set()
        return dict(_autoplay_result)

    playlist = build_stream_queue()
    track, position = _pick_start_track(playlist)
    if not track:
        _autoplay_result.update(status="empty_playlist", detail="Playlist is empty")
        _autoplay_done.set()
        return dict(_autoplay_result)

    # Resume where the last session stopped, otherwise start at the top.
    with _stream_lock:
        state = load_stream_session()
        state["path"] = track
        try:
            state["index"] = playlist.index(track)
        except ValueError:
            state["index"] = 0
        state["duration_sec"] = probe_duration(track)
        state["position_sec"] = clamp_position(state, position)
        state["playing"] = True
        state["started_at"] = time.time()
        save_stream_session(state)

    _autoplay_result.update(
        status="ready",
        detail=f"Auto-streaming {MODE_LABELS.get(get_library_mode(), 'library')} ({len(playlist)} items)",
        match=track,
        track=os.path.basename(track),
        position=round(float(state.get("position_sec", 0.0) or 0.0), 2),
        queue_len=len(playlist),
        mode=get_library_mode(),
        verified=True,
        verified_position=round(float(state.get("position_sec", 0.0) or 0.0), 2),
    )
    _autoplay_done.set()
    return dict(_autoplay_result)


def start_autoplay_worker() -> threading.Thread:
    thread = threading.Thread(target=autoplay_once, name="mp-companion-stream-queue", daemon=True)
    thread.start()
    return thread


def autoplay_state() -> Dict[str, Any]:
    return dict(_autoplay_result)



# ------------------------------------------------------------------------------
# TRACKLIST RESOLUTION & METADATA PARSING
# ------------------------------------------------------------------------------
def find_tracklist_for_mix(mix_file: str) -> str:
    if not mix_file:
        return ""
    if mix_file in _tracklist_cache:
        return _tracklist_cache[mix_file]

    p = Path(mix_file).expanduser().resolve()
    base = get_base_dir()
    stem = p.stem

    exact = p.parent / f"{stem}.txt"
    if exact.is_file():
        _tracklist_cache[mix_file] = str(exact)
        return str(exact)

    candidate_dirs = [
        p.parent,
        p.parent / "FLAC_CONVERTED_OUTPUTS",
        p.parent.parent / "FLAC_CONVERTED_OUTPUTS",
        base / "FLAC_CONVERTED_OUTPUTS",
        base / "MIX_ARCHIVE" / "FLAC_CONVERTED_OUTPUTS",
        Path.home() / "GoogleDrive" / "MIX_ARCHIVE" / "FLAC_CONVERTED_OUTPUTS"
    ]

    for d in candidate_dirs:
        if d.is_dir():
            c = d / f"{stem}.txt"
            if c.is_file():
                _tracklist_cache[mix_file] = str(c)
                return str(c)

    m = re.search(r'[_\ -](\d{2,3})([_\ -]|$)', stem)
    mix_num = m.group(1) if m else None

    if mix_num:
        for d in candidate_dirs:
            if d.is_dir():
                try:
                    for f in d.iterdir():
                        if f.is_file() and f.suffix.lower() == ".txt":
                            if mix_num in f.name:
                                _tracklist_cache[mix_file] = str(f)
                                return str(f)
                except Exception:
                    pass

    _tracklist_cache[mix_file] = ""
    return ""


_parsed_tracklist_cache: Dict[str, Dict[str, Any]] = {}


def parse_tracklist_file(tracklist_path: str) -> Dict[str, Any]:
    if not tracklist_path or not os.path.isfile(tracklist_path):
        return {"metadata": {}, "tracks": []}
    if tracklist_path in _parsed_tracklist_cache:
        return _parsed_tracklist_cache[tracklist_path]
    try:
        with open(tracklist_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        metadata: Dict[str, str] = {}
        tracks: List[str] = []
        in_tracklist = False
        for line in content.splitlines():
            s = line.strip()
            if not s:
                continue
            if "TRACKLIST" in s.upper():
                in_tracklist = True
                continue
            if s.startswith("Artist:") and "artist" not in metadata:
                metadata["artist"] = s.split(":", 1)[1].strip()
            elif s.startswith("Album:") and "album" not in metadata:
                metadata["album"] = s.split(":", 1)[1].strip()
            elif s.startswith("Title:") and "title" not in metadata:
                metadata["title"] = s.split(":", 1)[1].strip()

            if in_tracklist:
                if s.startswith("=") or s.startswith("-"):
                    continue
                if re.match(r'^\d{1,3}[\.\:\-\s]', s):
                    tracks.append(s)
            else:
                if re.match(r'^\d{1,3}[\.\:\-]\s+', s):
                    tracks.append(s)
        parsed = {"metadata": metadata, "tracks": tracks}
        _parsed_tracklist_cache[tracklist_path] = parsed
        return parsed
    except Exception:
        return {"metadata": {}, "tracks": []}


def clean_track_title(raw_title: str, raw_path: str, tl_meta: Dict[str, str]) -> Tuple[str, str, str]:
    if tl_meta.get("title"):
        return tl_meta["title"], tl_meta.get("artist", "MPlanetarian"), tl_meta.get("album", "Stream of Frequency")

    if not raw_title and raw_path:
        raw_title = Path(raw_path).name

    stem = Path(raw_title).stem
    clean = re.sub(r'[\uf000-\uf8ff]', ':', stem).strip().replace('_', ' ')
    clean = re.sub(r'\s+', ' ', clean).strip()

    artist, album, title = "MPlanetarian", "Stream of Frequency", clean
    if " - " in clean:
        parts = clean.split(" - ", 1)
        artist, title = parts[0].strip(), parts[1].strip()

    return title, artist, album


# ------------------------------------------------------------------------------
# STREAMING SESSION
#
# The companion tracks "which file is being served" and a coarse elapsed clock,
# so the phone dashboard has a position and a progress bar. It is deliberately
# NOT an authority on playback: the browser owns that. Nothing here opens an
# audio device.
# ------------------------------------------------------------------------------
VOLUME_FILE = CONFIG_DIR / "web_companion_stream.json"
_stream_lock = threading.Lock()


def _stream_state_path() -> Path:
    return VOLUME_FILE


def load_stream_session() -> Dict[str, Any]:
    state: Dict[str, Any] = {
        "index": 0,
        "path": "",
        "playing": False,
        "position_sec": 0.0,
        "started_at": 0.0,
        "duration_sec": 0.0,
        "volume": 100,
        "shuffle": False,
        "repeat": "all",
    }
    if _stream_state_path().is_file():
        try:
            saved = json.loads(_stream_state_path().read_text(encoding="utf-8", errors="ignore"))
            if isinstance(saved, dict):
                state.update({k: saved[k] for k in state if k in saved})
        except Exception:
            pass
    return state


def save_stream_session(state: Dict[str, Any]) -> None:
    try:
        _stream_state_path().parent.mkdir(parents=True, exist_ok=True)
        tmp = _stream_state_path().with_suffix(".tmp")
        tmp.write_text(json.dumps(state), encoding="utf-8")
        tmp.replace(_stream_state_path())
    except Exception:
        pass


def stream_position(state: Dict[str, Any]) -> float:
    """Elapsed seconds within the current file, accounting for active playback."""
    base = float(state.get("position_sec", 0.0) or 0.0)
    if state.get("playing") and state.get("started_at"):
        base += max(0.0, time.time() - float(state["started_at"]))
    return max(0.0, base)


def clamp_position(state: Dict[str, Any], pos: float) -> float:
    duration = float(state.get("duration_sec", 0.0) or 0.0)
    pos = max(0.0, float(pos))
    return min(pos, duration) if duration > 0 else pos


def current_stream_file() -> Tuple[str, Dict[str, Any]]:
    """Return the file the phone should currently be streaming."""
    queue = build_stream_queue()
    state = load_stream_session()
    if not queue:
        return "", state
    idx = int(state.get("index", 0) or 0)
    if idx < 0 or idx >= len(queue):
        idx = 0
        state["index"] = 0
    # Keep the saved path authoritative if it is still present in the queue.
    saved = str(state.get("path", "") or "")
    if saved and saved in queue:
        idx = queue.index(saved)
    else:
        state["path"] = queue[idx]
    return queue[idx], state


def get_eq_status() -> Dict[str, Any]:
    active_file, state = current_stream_file()
    playing = bool(state.get("playing"))
    pos = stream_position(state)
    dur = float(state.get("duration_sec", 0.0) or 0.0)
    pct = round(pos / dur * 100.0, 1) if dur > 0 else 0.0
    return {
        "state": "playing" if playing else ("paused" if active_file else "stopped"),
        "position": format_seconds(pos),
        "duration": format_seconds(dur) if dur > 0 else "--:--",
        "position_sec": round(pos, 2),
        "duration_sec": round(dur, 2),
        "progress_pct": pct,
        "volume": int(state.get("volume", 100)),
        "pitch_percent": 0,
        "shuffle": bool(state.get("shuffle", False)),
        "repeat": str(state.get("repeat", "all")),
        "levels": [0.0] * 24,
        "peaks": [0.0] * 24,
    }


def format_seconds(value: Any) -> str:
    try:
        total = int(max(0.0, float(value)))
    except (TypeError, ValueError):
        total = 0
    return f"{total // 3600:02d}:{(total % 3600) // 60:02d}:{total % 60:02d}"


_duration_cache: Dict[str, Tuple[float, float, float]] = {}


def probe_duration(path: str) -> float:
    """Read only the container header for length. Never decodes audio."""
    try:
        st = os.stat(path)
    except OSError:
        return 0.0
    cached = _duration_cache.get(path)
    if cached and cached[0] == st.st_mtime and cached[1] == st.st_size:
        return cached[2]
    duration = 0.0
    try:
        import soundfile  # header-only probe; no device, no decoding
        duration = float(soundfile.info(path).duration or 0.0)
    except Exception:
        duration = 0.0
    if duration <= 0.0:
        duration = _wav_duration(path)
    if duration <= 0.0:
        # soundfile lives in the user site-packages, which a systemd start may
        # not resolve. ffprobe reads the same header and is package-managed.
        duration = _ffprobe_duration(path)
    _duration_cache[path] = (st.st_mtime, st.st_size, duration)
    return duration


def _ffprobe_duration(path: str) -> float:
    """Container length from ffprobe, used when soundfile is unavailable."""
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", str(path)],
            capture_output=True, text=True, timeout=6,
        )
        if out.returncode == 0:
            return max(0.0, float((out.stdout or "").strip() or 0.0))
    except Exception:
        pass
    return 0.0


def _wav_duration(path: str) -> float:
    """Fallback for plain PCM WAV: data chunk size / byte rate."""
    try:
        with open(path, "rb") as f:
            header = f.read(64)
        if header[:4] != b"RIFF" or header[8:12] != b"WAVE":
            return 0.0
        byte_rate = int.from_bytes(header[28:32], "little")
        data_size = int.from_bytes(header[40:44], "little")
        if byte_rate > 0 and data_size > 0:
            return data_size / float(byte_rate)
    except Exception:
        pass
    return 0.0


def get_playback_status(cli_theme: Optional[str] = None) -> Dict[str, Any]:
    active_theme = get_theme_palette(cli_theme)
    active_file, state = current_stream_file()
    queue = build_stream_queue()

    duration = probe_duration(active_file) if active_file else 0.0
    if duration > 0 and abs(float(state.get("duration_sec", 0.0) or 0.0) - duration) > 0.5:
        state["duration_sec"] = duration

    pos = clamp_position(state, stream_position(state))
    pct = round(pos / duration * 100.0, 1) if duration > 0 else 0.0
    playing = bool(state.get("playing")) and bool(active_file)

    title, artist, album = clean_track_title("", active_file, {})
    tracklist: List[str] = []
    if active_file:
        tl_path = find_tracklist_for_mix(active_file)
        tl_info = parse_tracklist_file(tl_path) if tl_path else {"metadata": {}, "tracks": []}
        title, artist, album = clean_track_title(
            os.path.basename(active_file), active_file, tl_info.get("metadata", {})
        )
        tracklist = tl_info.get("tracks", [])

    return {
        "player": "Web Stream",
        "state": "playing" if playing else ("paused" if active_file else "stopped"),
        "title": title or "No Mix Playing",
        "raw_title": os.path.basename(active_file),
        "artist": artist,
        "album": album,
        "position": format_seconds(pos),
        "duration": format_seconds(duration) if duration else "00:00:00",
        "position_sec": round(pos, 2),
        "duration_sec": round(duration, 2),
        "progress_pct": pct,
        "active_file": active_file,
        "format": Path(active_file).suffix.lstrip(".").upper() if active_file else "",
        "sample_rate": "",
        "channels": "Stereo",
        "volume": int(state.get("volume", 100)),
        "pitch_percent": 0,
        "pitch_factor": 1.0,
        "shuffle": bool(state.get("shuffle", False)),
        "repeat": str(state.get("repeat", "all")),
        "levels": [0.0] * 24,
        "peaks": [0.0] * 24,
        "mini_eq": "",
        "tracklist": tracklist,
        "tracklist_total": len(tracklist),
        "queue_len": len(queue),
        "queue_position": int(state.get("index", 0) or 0) + 1,
        "mode": get_library_mode(),
        "mode_label": MODE_LABELS.get(get_library_mode(), "Library"),
        "library_fallback": bool(_queue_source_state.get("fallback")),
        "library_detail": _queue_source_state.get("detail", ""),
        "theme": active_theme,
    }


MINI_PLAYLIST_SIZE = 5
# Five rows are visible on a phone; the extra entries are what the list scrolls
# through, so a long mix queue is browsable without loading the whole library.
MINI_PLAYLIST_WINDOW = 20


def get_mini_playlist(limit: Optional[int] = None) -> Dict[str, Any]:
    """A short window of the stream queue: the current track plus the next ones.

    The dashboard renders `show` rows inside a scrollable box and the server
    sends up to `limit` (default MINI_PLAYLIST_WINDOW) entries, so five tracks
    are visible at once and the rest can be scrolled. `total` is the full queue
    length and is what the dashboard shows as the track count.
    """
    queue = build_stream_queue()
    mode = get_library_mode()
    show = MINI_PLAYLIST_SIZE
    if not queue:
        return {
            "items": [],
            "total": 0,
            "show": show,
            "current_index": -1,
            "mode": mode,
            "mode_label": MODE_LABELS.get(mode, "Library"),
            "library_fallback": bool(_queue_source_state.get("fallback")),
            "library_detail": _queue_source_state.get("detail", ""),
            "modes": [{"id": mid, "label": label} for mid, label in MODE_LABELS.items()],
        }

    try:
        window = int(limit) if limit is not None else MINI_PLAYLIST_WINDOW
    except (TypeError, ValueError):
        window = MINI_PLAYLIST_WINDOW
    window = max(1, window)

    state = load_stream_session()
    idx = int(state.get("index", 0) or 0)
    saved = str(state.get("path", "") or "")
    if saved and saved in queue:
        idx = queue.index(saved)
    idx = max(0, min(idx, len(queue) - 1))

    items: List[Dict[str, Any]] = []
    # Stop at the end of the queue instead of wrapping: a repeating window
    # looks broken once it is scrollable.
    for offset in range(min(window, len(queue))):
        i = (idx + offset)
        if i >= len(queue):
            break
        path = queue[i]
        title, artist, album = clean_track_title("", path, {})
        duration = probe_duration(path)
        items.append({
            "index": i,
            "title": title,
            "artist": artist,
            "file": path,
            "current": i == idx,
            "duration": format_seconds(duration),
            "duration_sec": round(duration, 2),
        })
    return {
        "items": items,
        "total": len(queue),
        "show": show,
        "current_index": idx,
        "mode": mode,
        "mode_label": MODE_LABELS.get(mode, "Library"),
        "library_fallback": bool(_queue_source_state.get("fallback")),
        "library_detail": _queue_source_state.get("detail", ""),
        "modes": [{"id": mid, "label": label} for mid, label in MODE_LABELS.items()],
    }


def control_player(action: str, params: Optional[Dict[str, List[str]]] = None) -> bool:
    """Drive the stream session. The browser performs the actual playback."""
    params = params or {}
    queue = build_stream_queue()
    if not queue:
        return False

    with _stream_lock:
        state = load_stream_session()
        path, _ = current_stream_file()
        if path and state.get("path") != path:
            state["path"] = path
        if state.get("path"):
            try:
                state["index"] = queue.index(state["path"])
            except ValueError:
                state["index"] = 0
                state["path"] = queue[0]

        pos = clamp_position(state, stream_position(state))
        duration = float(state.get("duration_sec", 0.0) or 0.0) or probe_duration(state["path"])

        def seek_to(target: float) -> None:
            state["position_sec"] = clamp_position(state, target)
            state["started_at"] = time.time() if state.get("playing") else 0.0

        def switch(step: int) -> None:
            state["index"] = (int(state.get("index", 0)) + step) % len(queue)
            state["path"] = queue[state["index"]]
            state["position_sec"] = 0.0
            state["started_at"] = time.time() if state.get("playing") else 0.0
            state["duration_sec"] = probe_duration(state["path"])

        if action in ("play", "resume"):
            state["playing"] = True
            state["started_at"] = time.time()
        elif action in ("pause", "play-pause", "toggle"):
            if state.get("playing"):
                state["playing"] = False
                state["position_sec"] = pos
                state["started_at"] = 0.0
            else:
                state["playing"] = True
                state["position_sec"] = pos
                state["started_at"] = time.time()
        elif action == "next":
            switch(1)
        elif action in ("previous", "prev"):
            switch(-1)
        elif action == "select_index":
            try:
                target = int(params.get("index", [0])[0])
            except (TypeError, ValueError):
                target = 0
            target = max(0, min(target, len(queue) - 1))
            state["index"] = target
            state["path"] = queue[target]
            state["position_sec"] = 0.0
            state["started_at"] = time.time() if state.get("playing") else 0.0
            state["duration_sec"] = probe_duration(state["path"])
        elif action == "seek_forward":
            seek_to(pos + 30.0)
        elif action == "seek_backward":
            seek_to(pos - 30.0)
        elif action == "seek":
            seek_to(pos + float(params.get("seconds", [10.0])[0]))
        elif action == "seek_to":
            seek_to(float(params.get("position", [0.0])[0]))
        elif action in ("shuffle", "toggle_shuffle"):
            state["shuffle"] = not bool(state.get("shuffle"))
        elif action in ("repeat", "cycle_repeat"):
            order = ["off", "all", "one"]
            cur = str(state.get("repeat", "all"))
            state["repeat"] = order[(order.index(cur) + 1) % len(order)] if cur in order else "all"
        elif action == "vol_up":
            state["volume"] = min(100, int(state.get("volume", 100)) + 5)
        elif action == "vol_down":
            state["volume"] = max(0, int(state.get("volume", 100)) - 5)
        elif action == "set_volume":
            state["volume"] = max(0, min(100, int(params.get("volume", [100])[0])))
        elif action == "mute":
            state["volume"] = 0
        elif action == "track_ended":
            # The phone finished the file: advance and keep the elapsed clock honest.
            switch(1)
            state["duration_sec"] = probe_duration(state["path"])
            state["playing"] = True
            state["started_at"] = time.time()
        else:
            return False

        if duration > 0:
            state["duration_sec"] = duration
        save_stream_session(state)
    return True


# ------------------------------------------------------------------------------
# DYNAMIC HTML TEMPLATE (SEAMLESS AUDIO STREAMING & SYNCED SEEKING)
# ------------------------------------------------------------------------------
def render_html_page(theme: Dict[str, Any]) -> str:
    t = theme
    is_rainbow = t.get("is_dynamic_rainbow", False) or t['id'] == "dynamic_rainbow_liquid_glass"

    # Dynamic Liquid Glass [Rainbow Colours]: the body carries a slowly rotating
    # hue while the glass cards breathe, so the whole dashboard cycles through
    # the spectrum instead of sitting on one static accent colour.
    rainbow_anim_css = """
        @keyframes rainbowShift {
            0% { background-position: 0% 50%; }
            100% { background-position: 300% 50%; }
        }
        @keyframes dynamicRainbowHue {
            0% { filter: hue-rotate(0deg) saturate(1.15); }
            100% { filter: hue-rotate(360deg) saturate(1.15); }
        }
        @keyframes dynamicRainbowBreath {
            0%, 100% {
                box-shadow: 0 14px 40px rgba(176, 88, 255, 0.45),
                            inset 0 0 24px rgba(0, 242, 254, 0.16);
                border-color: rgba(176, 88, 255, 0.45);
            }
            50% {
                box-shadow: 0 18px 52px rgba(255, 45, 142, 0.55),
                            inset 0 0 34px rgba(254, 225, 64, 0.22);
                border-color: rgba(0, 242, 254, 0.60);
            }
        }
        body.dynamic-rainbow-glass-active {
            animation: dynamicRainbowHue 18s linear infinite;
        }
        body.dynamic-rainbow-glass-active .card {
            animation: dynamicRainbowBreath 6s ease-in-out infinite;
            backdrop-filter: blur(18px) saturate(1.35);
            -webkit-backdrop-filter: blur(18px) saturate(1.35);
        }
        body.dynamic-rainbow-glass-active .header h1 {
            background: linear-gradient(90deg,
                #b058ff, #ff2d8e, #fee140, #00f2fe, #b058ff);
            background-size: 300% 100%;
            -webkit-background-clip: text;
            background-clip: text;
            -webkit-text-fill-color: transparent;
            animation: rainbowShift 12s linear infinite;
        }
        @media (prefers-reduced-motion: reduce) {
            body.dynamic-rainbow-glass-active,
            body.dynamic-rainbow-glass-active .card,
            body.dynamic-rainbow-glass-active .header h1 {
                animation: none;
            }
        }
    """ if is_rainbow else ""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>MP Liquid Player (Web) — DJ Booth Remote</title>
    <style>
        :root {{
            --bg: {t['bg']};
            --card-bg: {t['card_bg']};
            --card-border: {t['card_border']};
            --card-shadow: {t['card_shadow']};
            --text-main: {t['text_main']};
            --text-dim: {t['text_dim']};
            --accent-primary: {t['accent_primary']};
            --accent-secondary: {t['accent_secondary']};
            --accent-tertiary: {t['accent_tertiary']};
            --accent-crimson: {t['accent_crimson']};
            --header-gradient: {t['header_gradient']};
            --btn-gradient: {t['btn_gradient']};
            --btn-shadow: {t['btn_shadow']};
            --progress-fill: {t['progress_fill']};
            --badge-bg: {t['badge_bg']};
            --badge-color: {t['badge_color']};
            --eq-bar: {t['eq_bar']};
            --eq-peak: {t['eq_peak']};
        }}
        {rainbow_anim_css}
        * {{
            box-sizing: border-box;
            -webkit-tap-highlight-color: transparent;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: var(--bg);
            color: var(--text-main);
            margin: 0;
            padding: 16px 12px;
            display: flex;
            flex-direction: column;
            align-items: center;
            min-height: 100vh;
        }}
        .header {{
            text-align: center;
            margin-bottom: 16px;
        }}
        .header h1 {{
            margin: 0;
            font-size: 1.75rem;
            background: var(--header-gradient);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-weight: 900;
            letter-spacing: 1.5px;
            text-transform: uppercase;
        }}
        .app-version {{
            font-size: 0.75rem;
            color: var(--accent-secondary);
            font-weight: 700;
            vertical-align: middle;
            background: rgba(255, 255, 255, 0.08);
            padding: 2px 8px;
            border-radius: 8px;
            border: 1px solid var(--card-border);
            margin-left: 6px;
            display: inline-block;
        }}
        .header p {{
            margin: 6px 0 8px 0;
            font-size: 0.85rem;
            color: var(--text-dim);
            font-weight: 500;
        }}
        .theme-pill {{
            display: inline-block;
            font-size: 0.72rem;
            padding: 3px 12px;
            border-radius: 12px;
            background: rgba(255, 255, 255, 0.05);
            color: var(--text-dim);
            border: 1px solid var(--card-border);
            letter-spacing: 0.5px;
            font-weight: 600;
        }}
        .theme-bar {{
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            flex-wrap: wrap;
            margin-top: 10px;
        }}
        .theme-btn {{
            appearance: none;
            -webkit-appearance: none;
            display: inline-flex;
            align-items: center;
            gap: 7px;
            padding: 9px 18px;
            border-radius: 12px;
            font-size: 0.82rem;
            font-weight: 800;
            letter-spacing: 0.4px;
            color: var(--text-main);
            background: var(--btn-gradient);
            border: 1px solid var(--card-border);
            box-shadow: var(--btn-shadow);
            cursor: pointer;
            transition: transform 0.12s ease, filter 0.15s ease;
        }}
        .theme-btn:active {{
            transform: scale(0.96);
        }}
        .theme-btn:hover {{
            filter: brightness(1.12);
        }}
        .theme-btn.open {{
            border-color: var(--accent-secondary);
        }}
        .theme-menu {{
            display: none;
            margin-top: 10px;
            width: 100%;
            max-width: 420px;
            max-height: 270px;
            overflow-y: auto;
            padding: 6px;
            border-radius: 14px;
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            box-shadow: var(--card-shadow);
            -webkit-overflow-scrolling: touch;
        }}
        .theme-menu.show {{
            display: block;
        }}
        .theme-option {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 10px;
            width: 100%;
            text-align: left;
            padding: 9px 12px;
            margin: 2px 0;
            border: 1px solid transparent;
            border-radius: 10px;
            background: transparent;
            color: var(--text-main);
            font-size: 0.8rem;
            font-weight: 600;
            font-family: inherit;
            cursor: pointer;
        }}
        .theme-option:hover {{
            background: rgba(255, 255, 255, 0.07);
        }}
        .theme-option.active {{
            background: var(--badge-bg);
            color: var(--badge-color);
            border-color: var(--badge-color);
            font-weight: 800;
        }}
        .theme-option .theme-check {{
            font-size: 0.72rem;
            opacity: 0.9;
        }}
        .mini-playlist {{
            margin-top: 14px;
            display: flex;
            flex-direction: column;
            gap: 6px;
        }}
        /* Five rows are visible at once; the rest of the window scrolls. */
        #miniPlItems {{
            display: flex;
            flex-direction: column;
            gap: 6px;
            /* 5 rows x 48px + 4 gaps x 6px = 264px */
            max-height: 264px;
            overflow-y: auto;
            overscroll-behavior: contain;
            -webkit-overflow-scrolling: touch;
            touch-action: pan-y;
            padding-right: 4px;
        }}
        #miniPlItems::-webkit-scrollbar {{
            width: 5px;
        }}
        #miniPlItems::-webkit-scrollbar-thumb {{
            background: var(--accent-secondary);
            border-radius: 3px;
        }}
        #miniPlItems::-webkit-scrollbar-track {{
            background: transparent;
        }}
        .mini-pl-head {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 8px;
            font-size: 0.7rem;
            font-weight: 800;
            letter-spacing: 0.7px;
            color: var(--text-dim);
            text-transform: uppercase;
        }}
        .mini-pl-count {{
            font-size: 0.68rem;
            font-weight: 800;
            letter-spacing: 0.5px;
            padding: 3px 9px;
            border-radius: 10px;
            background: var(--badge-bg);
            color: var(--badge-color);
            border: 1px solid var(--badge-color);
            white-space: nowrap;
            text-transform: none;
        }}
        .mode-switch {{
            display: flex;
            gap: 4px;
            padding: 3px;
            border-radius: 11px;
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid var(--card-border);
        }}
        .mode-switch button {{
            appearance: none;
            border: none;
            background: transparent;
            color: var(--text-dim);
            font-family: inherit;
            font-size: 0.72rem;
            font-weight: 800;
            letter-spacing: 0.2px;
            padding: 7px 6px;
            border-radius: 8px;
            cursor: pointer;
            flex: 1 1 0;
            min-width: 0;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            transition: background 0.15s ease, color 0.15s ease;
        }}
        .mode-switch button.active {{
            background: var(--badge-bg);
            color: var(--badge-color);
            box-shadow: 0 0 0 1px var(--badge-color) inset;
        }}
        .mode-switch button:disabled {{
            cursor: progress;
            opacity: 0.55;
        }}
        .mode-switch button.pending:disabled {{
            opacity: 1;
            animation: modePulse 1s ease-in-out infinite;
        }}
        @keyframes modePulse {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0.45; }}
        }}
        @media (prefers-reduced-motion: reduce) {{
            .mode-switch button.pending:disabled {{ animation: none; }}
        }}
        .mini-pl-empty {{
            font-size: 0.75rem;
            color: var(--text-dim);
            padding: 10px 12px;
            border-radius: 10px;
            border: 1px dashed var(--card-border);
            text-align: center;
        }}
        .mini-pl-item {{
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 8px 12px;
            border-radius: 12px;
            background: rgba(255, 255, 255, 0.04);
            border: 1px solid var(--card-border);
            cursor: pointer;
            transition: background 0.15s ease, border-color 0.15s ease;
            /* Uniform 48px rows put exactly five in the 264px window. */
            flex: 0 0 48px;
            height: 48px;
            box-sizing: border-box;
        }}
        .mini-pl-item:hover {{
            background: rgba(255, 255, 255, 0.08);
            border-color: var(--accent-secondary);
        }}
        .mini-pl-item.current {{
            background: var(--badge-bg);
            border-color: var(--badge-color);
            box-shadow: 0 0 0 1px var(--badge-color) inset;
        }}
        .mini-pl-num {{
            font-size: 0.68rem;
            font-weight: 800;
            color: var(--text-dim);
            min-width: 16px;
        }}
        .mini-pl-item.current .mini-pl-num {{
            color: var(--badge-color);
        }}
        .mini-pl-body {{
            flex: 1;
            min-width: 0;
        }}
        .mini-pl-title {{
            font-size: 0.78rem;
            font-weight: 700;
            color: var(--text-main);
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}
        .mini-pl-dur {{
            font-size: 0.68rem;
            color: var(--text-dim);
            margin-top: 2px;
        }}
        .autoplay-notice {{
            margin-top: 8px;
            padding: 6px 12px;
            border-radius: 10px;
            font-size: 0.72rem;
            font-weight: 700;
            letter-spacing: 0.3px;
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid var(--card-border);
            color: var(--text-dim);
        }}
        .autoplay-notice.ok {{
            background: var(--badge-bg);
            color: var(--badge-color);
            border-color: var(--badge-color);
        }}
        .autoplay-notice.warn {{
            background: rgba(255, 170, 0, 0.12);
            color: #ffaa00;
            border-color: #ffaa00;
        }}
        .card {{
            background-color: var(--card-bg);
            border-radius: 18px;
            padding: 22px;
            width: 100%;
            max-width: 520px;
            box-shadow: var(--card-shadow);
            border: 1px solid var(--card-border);
            margin-bottom: 16px;
        }}
        .badges-row {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            width: 100%;
            margin-bottom: 12px;
        }}
        .badge {{
            background: var(--badge-bg);
            color: var(--badge-color);
            padding: 4px 10px;
            border-radius: 14px;
            font-size: 0.72rem;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 1px;
            border: 1px solid var(--badge-color);
        }}
        .badge-source {{
            background: rgba(255, 255, 255, 0.06);
            color: var(--text-dim);
            border-color: rgba(255, 255, 255, 0.12);
        }}
        .track-info {{
            text-align: center;
            width: 100%;
            margin-bottom: 14px;
        }}
        .track-title {{
            font-size: 1.25rem;
            font-weight: 800;
            margin: 0 0 6px 0;
            line-height: 1.35;
            color: var(--text-main);
            word-break: break-word;
        }}
        .track-artist {{
            font-size: 0.95rem;
            color: var(--accent-primary);
            font-weight: 600;
            margin: 0 0 6px 0;
        }}
        .track-specs {{
            font-size: 0.75rem;
            color: var(--text-dim);
            letter-spacing: 0.5px;
            display: flex;
            justify-content: center;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 4px;
        }}
        .spec-chip {{
            background: rgba(255, 255, 255, 0.04);
            padding: 2px 8px;
            border-radius: 8px;
            border: 1px solid rgba(255, 255, 255, 0.05);
        }}
        .mobile-audio-banner {{
            display: none;
            background: linear-gradient(135deg, rgba(0, 245, 255, 0.12), rgba(176, 88, 255, 0.12));
            border: 1px solid var(--accent-primary);
            border-radius: 12px;
            padding: 10px 14px;
            margin-bottom: 16px;
            text-align: center;
        }}
        .mobile-audio-banner h4 {{
            margin: 0;
            font-size: 0.82rem;
            color: var(--accent-secondary);
            text-transform: uppercase;
            letter-spacing: 0.8px;
        }}
        .mobile-audio-banner p {{
            margin: 3px 0 0 0;
            font-size: 0.72rem;
            color: var(--text-dim);
        }}
        /* Stream Activation Modal */
        #streamOverlay {{
            display: flex;
            position: fixed;
            top: 0; left: 0; width: 100%; height: 100%;
            background: rgba(5, 4, 15, 0.92);
            z-index: 9999;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 24px;
            text-align: center;
        }}
        .overlay-card {{
            background: var(--card-bg);
            border: 2px solid var(--accent-primary);
            border-radius: 20px;
            padding: 28px 20px;
            max-width: 400px;
            width: 100%;
            box-shadow: 0 16px 50px rgba(0, 0, 0, 0.9), 0 0 30px rgba(176, 88, 255, 0.3);
        }}
        .overlay-card h2 {{
            margin: 0 0 10px 0;
            font-size: 1.4rem;
            background: var(--header-gradient);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-weight: 900;
        }}
        .overlay-card p {{
            font-size: 0.88rem;
            color: var(--text-dim);
            margin: 0 0 20px 0;
            line-height: 1.4;
        }}
        .btn-activate-stream {{
            background: var(--btn-gradient);
            color: #fff;
            border: none;
            padding: 16px 28px;
            border-radius: 14px;
            font-size: 1.05rem;
            font-weight: 800;
            cursor: pointer;
            width: 100%;
            box-shadow: var(--btn-shadow);
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        .visualizer-container {{
            width: 100%;
            height: 56px;
            display: flex;
            align-items: flex-end;
            justify-content: center;
            gap: 3px;
            margin: 12px 0 16px 0;
            padding: 4px 6px;
            background: rgba(0, 0, 0, 0.35);
            border-radius: 10px;
            border: 1px solid rgba(255, 255, 255, 0.06);
            position: relative;
        }}
        .v-col {{
            flex: 1;
            max-width: 14px;
            height: 100%;
            display: flex;
            align-items: flex-end;
            position: relative;
        }}
        .v-bar {{
            width: 100%;
            height: 4%;
            background: linear-gradient(180deg, var(--eq-peak) 0%, var(--eq-bar) 28%, var(--accent-primary) 100%);
            border-radius: 2px 2px 0 0;
            position: relative;
        }}
        .v-peak {{
            position: absolute;
            left: 0;
            right: 0;
            height: 2px;
            background: var(--eq-peak);
            border-radius: 1px;
            bottom: 4%;
            pointer-events: none;
        }}
        .progress-box {{
            width: 100%;
            margin-bottom: 16px;
        }}
        .progress-bar-bg {{
            width: 100%;
            height: 9px;
            background: rgba(255, 255, 255, 0.08);
            border-radius: 5px;
            cursor: pointer;
            overflow: hidden;
            position: relative;
            touch-action: none;
        }}
        .progress-bar-fill {{
            height: 100%;
            width: 0%;
            background: var(--progress-fill);
            border-radius: 5px;
            transition: width 0.15s ease-out;
        }}
        .time-row {{
            display: flex;
            justify-content: space-between;
            font-size: 0.8rem;
            color: var(--text-dim);
            font-weight: 600;
            margin-top: 6px;
        }}
        .controls-row {{
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 10px;
            width: 100%;
            margin-top: 8px;
        }}
        .mode-controls-row {{
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 10px;
            width: 100%;
            margin-top: 10px;
        }}
        .btn-mode {{
            flex: 1;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 6px;
            padding: 8px 12px;
            font-size: 0.84rem;
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid var(--card-border);
            color: var(--text-dim);
            border-radius: 10px;
        }}
        .btn-mode.active {{
            background: var(--badge-bg);
            color: var(--text-main);
            border-color: var(--accent-primary);
            font-weight: 800;
        }}
        .badge-shuffle {{
            background: rgba(255, 255, 255, 0.05);
            color: var(--text-dim);
            border-color: rgba(255, 255, 255, 0.12);
            cursor: pointer;
        }}
        .badge-shuffle.active {{
            background: var(--badge-bg);
            color: var(--badge-color);
            border-color: var(--badge-color);
            font-weight: 800;
        }}
        button {{
            background: rgba(255, 255, 255, 0.07);
            color: var(--text-main);
            border: 1px solid var(--card-border);
            padding: 12px 16px;
            border-radius: 12px;
            font-size: 1rem;
            font-weight: 700;
            cursor: pointer;
        }}
        .btn-main {{
            background: var(--btn-gradient);
            color: #fff;
            padding: 14px 24px;
            font-size: 1.15rem;
            box-shadow: var(--btn-shadow);
            border: none;
            flex-grow: 1;
            max-width: 180px;
        }}
        .sec-controls {{
            display: flex;
            /* Two control clusters cannot sit side by side on a 390px phone;
               without stacking, the pitch cluster is clipped off the card. */
            flex-direction: column;
            gap: 8px;
            width: 100%;
            margin-top: 14px;
            padding-top: 12px;
            border-top: 1px solid rgba(255, 255, 255, 0.06);
        }}
        .control-group {{
            display: flex;
            align-items: center;
            gap: 6px;
            flex: 1 1 auto;
            min-width: 0;
            justify-content: center;
            flex-wrap: nowrap;
        }}
        .control-pill {{
            font-size: 0.78rem;
            color: var(--text-dim);
            font-weight: 700;
            min-width: 52px;
            text-align: center;
        }}
        .btn-mini {{
            padding: 6px 10px;
            font-size: 0.78rem;
            border-radius: 8px;
        }}
        .tracklist-card {{
            max-height: 280px;
            display: flex;
            flex-direction: column;
        }}
        .tl-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
            padding-bottom: 8px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.07);
        }}
        .tl-header h3 {{
            margin: 0;
            font-size: 0.92rem;
            color: var(--accent-secondary);
            font-weight: 800;
        }}
        .tl-items {{
            overflow-y: auto;
            flex: 1;
            padding-right: 4px;
            list-style: none;
            margin: 0;
            padding-left: 0;
        }}
        .tl-item {{
            padding: 6px 10px;
            margin-bottom: 4px;
            border-radius: 6px;
            font-size: 0.82rem;
            color: var(--text-main);
            background: rgba(255, 255, 255, 0.02);
            border-left: 3px solid var(--accent-primary);
        }}
        .footer {{
            margin-top: auto;
            text-align: center;
            font-size: 0.72rem;
            color: var(--text-dim);
            opacity: 0.75;
            padding: 10px 0;
        }}
    </style>
</head>
<body>
    <!-- Stream Activation Modal to Satisfy Mobile Autoplay Policies -->
    <div id="streamOverlay">
        <div class="overlay-card">
            <h2>🎧 MP Mix Stream</h2>
            <p>Tap below to engage mobile studio audio streaming and dashboard synchronization.</p>
            <button class="btn-activate-stream" onclick="activateMobileStream()">Engage Audio Stream</button>
        </div>
    </div>

    <div class="header">
        <h1>MP LIQUID PLAYER (WEB) <span class="app-version">v{html.escape(VERSION)}</span></h1>
        <p>Studio & DJ Booth Mobile Web Companion</p>
        <div id="themeBadge" class="theme-pill">🎨 <span id="themeNameText">{html.escape(t['name'])}</span></div>
        <div class="theme-bar">
            <button class="theme-btn" id="themeBtn" onclick="toggleThemeMenu()"
                    aria-haspopup="true" aria-expanded="false"
                    title="Change the companion theme">
                🎨 Theme
            </button>
        </div>
        <div class="theme-menu" id="themeMenu" role="menu"></div>
        <div id="autoplayNotice" class="autoplay-notice" style="display: none;"></div>
    </div>

    <div class="card now-playing">
        <div id="mobileAudioBanner" class="mobile-audio-banner">
            <h4>📱 Mobile Audio Stream Active</h4>
            <p>High-resolution FLAC/WAV streaming active</p>
        </div>

        <!-- HTML5 Audio Streaming Element -->
        <audio id="mobileAudioStream" preload="auto" style="display: none;"></audio>

        <div class="badges-row">
            <div id="playBadge" class="badge">STANDBY</div>
            <div id="shuffleBadge" class="badge badge-shuffle" onclick="sendAction('shuffle')">🔀 SHUFFLE OFF</div>
            <div id="sourceBadge" class="badge badge-source">CHECKING...</div>
        </div>

        <div class="track-info">
            <div id="trackTitle" class="track-title">Connecting to MP Mix Session...</div>
            <div id="trackArtist" class="track-artist">—</div>
            <div id="trackSpecs" class="track-specs">
                <span id="specFormat" class="spec-chip">FLAC / WAV</span>
                <span id="specRate" class="spec-chip">48 kHz</span>
                <span id="specChannels" class="spec-chip">Stereo</span>
            </div>
        </div>

        <!-- 24-Bar Audio Visualizer -->
        <div class="visualizer-container" id="visContainer">
            {"".join(f'<div class="v-col"><div class="v-bar" id="vb{i}"></div><div class="v-peak" id="vp{i}"></div></div>' for i in range(24))}
        </div>

        <!-- Progress & Time -->
        <div class="progress-box">
            <div class="progress-bar-bg" id="progressBg" onclick="seekClick(event)">
                <div class="progress-bar-fill" id="progressBar"></div>
            </div>
            <div class="time-row">
                <span id="posTime">00:00</span>
                <span id="durTime">--:--</span>
            </div>
        </div>

        <!-- Primary Controls -->
        <div class="controls-row">
            <button class="btn-sub" onclick="sendAction('seek_backward')">⏪ 30s</button>
            <button onclick="sendAction('previous')">⏮</button>
            <button class="btn-main" id="btnPlayPause" onclick="handlePlayPauseClick()">⏯ Play</button>
            <button onclick="sendAction('next')">⏭</button>
            <button class="btn-sub" onclick="sendAction('seek_forward')">30s ⏩</button>
        </div>

        <!-- Mode Controls -->
        <div class="mode-controls-row">
            <button class="btn-sub btn-mode" id="btnShuffle" onclick="sendAction('shuffle')">
                <span>🔀</span> Shuffle: <span id="shufText">OFF</span>
            </button>
            <button class="btn-sub btn-mode" id="btnRepeat" onclick="sendAction('repeat')">
                <span>🔁</span> Repeat: <span id="repText">ALL</span>
            </button>
        </div>

        <!-- Secondary Controls -->
        <div class="sec-controls">
            <div class="control-group">
                <button class="btn-mini" onclick="sendAction('vol_down')">🔉 -</button>
                <span class="control-pill" id="volPill">Vol: 85%</span>
                <button class="btn-mini" onclick="sendAction('vol_up')">+ 🔊</button>
                <button class="btn-mini" onclick="sendAction('mute')">🔇</button>
            </div>
            <div class="control-group">
                <button class="btn-mini" onclick="sendAction('pitch_down')">[-]</button>
                <span class="control-pill" id="pitchPill">Pitch: 0%</span>
                <button class="btn-mini" onclick="sendAction('pitch_up')">[+]</button>
                <button class="btn-mini" onclick="sendAction('reset_pitch')">0</button>
            </div>
        </div>
        <!-- Mini Playlist: the current track plus the next four, scrollable -->
        <div class="mini-playlist" id="miniPlaylist">
            <div class="mini-pl-head">
                <span id="miniPlTitle">🎵 Up Next</span>
                <span class="mini-pl-count" id="miniPlCount">0 tracks</span>
            </div>
            <div class="mode-switch" id="modeSwitch" role="group" aria-label="Choose library mode">
                <button type="button" data-mode="MIX_ARCHIVE" onclick="switchLibraryMode('MIX_ARCHIVE')">Mix</button>
                <button type="button" data-mode="MUSIC" onclick="switchLibraryMode('MUSIC')">Music</button>
                <button type="button" data-mode="FAVORITES" onclick="switchLibraryMode('FAVORITES')">Favourites</button>
            </div>
            <div id="miniPlNote"></div>
            <div id="miniPlItems"></div>
        </div>
    </div>

    <!-- Tracklist Card -->
    <div class="card tracklist-card" id="tlCard" style="display: none;">
        <div class="tl-header">
            <h3>📜 Mix Tracklist</h3>
            <span class="tl-count" id="tlCount">0 Tracks</span>
        </div>
        <ul class="tl-items" id="tlItems"></ul>
    </div>

    <div class="footer">
        MP Mix Archive Manager v{html.escape(VERSION)} • MPlanetarian (Dreamworlds Productions)
    </div>

    <script>
        let currentThemeId = "{t['id']}";
        let currentDurationSec = 0;
        let lastLoadedMix = "";
        let isPlayerActive = false;
        let audioStreamConfigured = false;
        let activeAudioFile = "";
        let audioSeekInFlight = false;
        let lastAudioSyncAt = 0;
        let lastServerPos = -1.0;
        let audioStreamEngaged = false;

        function audioElIsPlaying() {{
            const audioEl = document.getElementById('mobileAudioStream');
            return Boolean(audioEl && !audioEl.paused && !audioEl.ended);
        }}

        // Seek the phone's element only once per request and clear the guard
        // when the element reports it actually moved. Without this the 100 ms
        // poll can re-issue the same seek while the previous one is settling.
        function seekAudioTo(pos) {{
            const audioEl = document.getElementById('mobileAudioStream');
            if (!audioEl || !isFinite(pos) || pos < 0) return;
            if (audioSeekInFlight && Math.abs(audioEl.currentTime - pos) < 0.5) return;
            try {{
                audioSeekInFlight = true;
                audioEl.currentTime = pos;
                lastAudioSyncAt = performance.now();
                setTimeout(() => {{ audioSeekInFlight = false; }}, 1500);
            }} catch (e) {{
                audioSeekInFlight = false;
            }}
        }}

        window.addEventListener('DOMContentLoaded', () => {{
            if (currentThemeId === 'dynamic_rainbow_liquid_glass') {{
                document.body.classList.add('dynamic-rainbow-glass-active');
            }}
            const audioEl = document.getElementById('mobileAudioStream');
            if (audioEl) {{
                audioEl.addEventListener('seeked', () => {{ audioSeekInFlight = false; }});
                // The phone decides when a mix ends, so tell the server which
                // file to serve next instead of waiting for a local player.
                audioEl.addEventListener('ended', () => {{
                    sendAction('track_ended');
                }});
            }}
            loadThemeList();
            fetchMiniPlaylist();
        }});

        function applyPalette(th) {{
            if (!th || !th.id) return;
            currentThemeId = th.id;
            const nameEl = document.getElementById('themeNameText');
            if (nameEl) nameEl.innerText = th.name;
            const r = document.querySelector(':root');
            r.style.setProperty('--bg', th.bg);
            r.style.setProperty('--card-bg', th.card_bg);
            r.style.setProperty('--card-border', th.card_border);
            r.style.setProperty('--card-shadow', th.card_shadow);
            r.style.setProperty('--text-main', th.text_main);
            r.style.setProperty('--text-dim', th.text_dim);
            r.style.setProperty('--accent-primary', th.accent_primary);
            r.style.setProperty('--accent-secondary', th.accent_secondary);
            r.style.setProperty('--accent-tertiary', th.accent_tertiary);
            r.style.setProperty('--accent-crimson', th.accent_crimson);
            r.style.setProperty('--header-gradient', th.header_gradient);
            r.style.setProperty('--btn-gradient', th.btn_gradient);
            r.style.setProperty('--btn-shadow', th.btn_shadow);
            r.style.setProperty('--progress-fill', th.progress_fill);
            r.style.setProperty('--badge-bg', th.badge_bg);
            r.style.setProperty('--badge-color', th.badge_color);
            r.style.setProperty('--eq-bar', th.eq_bar);
            r.style.setProperty('--eq-peak', th.eq_peak);
            document.body.classList.toggle('dynamic-rainbow-glass-active', th.id === 'dynamic_rainbow_liquid_glass');
        }}

        async function loadThemeList() {{
            try {{
                const res = await fetch('/api/themes');
                const data = await res.json();
                const menu = document.getElementById('themeMenu');
                if (!menu || !data.themes) return;
                const active = data.current || currentThemeId;
                menu.innerHTML = '';
                data.themes.forEach(th => {{
                    const opt = document.createElement('button');
                    opt.type = 'button';
                    opt.className = 'theme-option' + (th.id === active ? ' active' : '');
                    opt.setAttribute('role', 'menuitem');
                    opt.dataset.themeId = th.id;

                    const label = document.createElement('span');
                    label.innerText = th.name;
                    const check = document.createElement('span');
                    check.className = 'theme-check';
                    check.innerText = th.id === active ? '✓ Active' : '';

                    opt.appendChild(label);
                    opt.appendChild(check);
                    opt.onclick = () => changeTheme(th.id);
                    menu.appendChild(opt);
                }});
            }} catch (e) {{}}
        }}

        function toggleThemeMenu() {{
            const menu = document.getElementById('themeMenu');
            const btn = document.getElementById('themeBtn');
            if (!menu) return;
            const show = !menu.classList.contains('show');
            menu.classList.toggle('show', show);
            if (btn) {{
                btn.classList.toggle('open', show);
                btn.setAttribute('aria-expanded', show ? 'true' : 'false');
            }}
        }}

        function closeThemeMenu() {{
            const menu = document.getElementById('themeMenu');
            const btn = document.getElementById('themeBtn');
            if (menu) menu.classList.remove('show');
            if (btn) {{
                btn.classList.remove('open');
                btn.setAttribute('aria-expanded', 'false');
            }}
        }}

        document.addEventListener('click', (e) => {{
            const menu = document.getElementById('themeMenu');
            const btn = document.getElementById('themeBtn');
            if (!menu || !menu.classList.contains('show')) return;
            if (menu.contains(e.target) || (btn && btn.contains(e.target))) return;
            closeThemeMenu();
        }});

        async function changeTheme(themeId) {{
            if (!themeId) return;
            closeThemeMenu();
            try {{
                const res = await fetch('/api/set_theme?theme=' + encodeURIComponent(themeId));
                const data = await res.json();
                if (data && data.success && data.palette) {{
                    applyPalette(data.palette);
                    loadThemeList();
                }} else {{
                    loadThemeList();
                }}
            }} catch (e) {{
                loadThemeList();
            }}
        }}

        function renderMiniPlaylist(data) {{
            const wrap = document.getElementById('miniPlItems');
            if (!wrap) return;
            const items = (data && data.items) || [];
            const total = Number(data && data.total) || 0;
            const show = Math.max(1, Number(data && data.show) || 5);

            const countEl = document.getElementById('miniPlCount');
            if (countEl) {{
                // Track count for the whole selected library, not just the
                // rows that fit on a phone screen.
                countEl.innerText = total + (total === 1 ? ' track' : ' tracks');
                countEl.title = Math.min(items.length, show) + ' shown of ' + total +
                                ' in this library · scroll for more';
            }}

            const titleEl = document.getElementById('miniPlTitle');
            if (titleEl) {{
                const label = (data && data.mode_label) || 'Library';
                titleEl.innerText = '🎵 Up Next · ' + label;
            }}

            // The offline notice sits above the list, so five rows always fit.
            const noteEl = document.getElementById('miniPlNote');
            if (noteEl) {{
                noteEl.innerHTML = '';
                if (data && data.library_detail) {{
                    // A warning when the mode fell back, a plain hint otherwise
                    // (an empty Favorites playlist is normal, not an error).
                    const note = document.createElement('div');
                    note.className = 'mini-pl-empty';
                    if (data.library_fallback) {{
                        note.style.borderColor = '#ffaa00';
                        note.style.color = '#ffaa00';
                    }}
                    note.innerText = (data.library_fallback ? '⚠ ' : '') + data.library_detail;
                    noteEl.appendChild(note);
                }}
            }}

            // Keep the scroll position across the 15-second refresh instead of
            // snapping back to the top while the user is browsing.
            const scrollTop = wrap.scrollTop;
            wrap.innerHTML = '';

            if (!items.length) {{
                const empty = document.createElement('div');
                empty.className = 'mini-pl-empty';
                empty.innerText = (data && data.mode === 'FAVORITES')
                    ? 'No favourites yet — press H in the player to add one'
                    : 'No audio found in this library';
                wrap.appendChild(empty);
                return;
            }}

            items.forEach((item, i) => {{
                const row = document.createElement('div');
                row.className = 'mini-pl-item' + (item.current ? ' current' : '');
                row.onclick = () => sendAction('select_index', {{ index: item.index }});

                const num = document.createElement('div');
                num.className = 'mini-pl-num';
                num.innerText = item.current ? '▶' : String(i + 1);

                const body = document.createElement('div');
                body.className = 'mini-pl-body';
                const title = document.createElement('div');
                title.className = 'mini-pl-title';
                title.innerText = item.title || 'Untitled Track';
                const dur = document.createElement('div');
                dur.className = 'mini-pl-dur';
                dur.innerText = (item.artist || '') + (item.duration ? ' • ' + item.duration : '');
                body.appendChild(title);
                body.appendChild(dur);

                row.appendChild(num);
                row.appendChild(body);
                wrap.appendChild(row);
            }});
            wrap.scrollTop = scrollTop;
        }}

        function updateModeSwitch(mode) {{
            document.querySelectorAll('#modeSwitch button').forEach(btn => {{
                btn.classList.toggle('active', btn.dataset.mode === mode);
            }});
        }}

        // The mode request scans a multi-thousand-entry library, so it can take
        // a few seconds. A single token makes sure only the newest tap decides
        // the highlighted mode and the playlist that is finally shown.
        let modeRequestToken = 0;
        let modeSwitchBusy = false;

        function setModeBusy(busy, pendingMode) {{
            modeSwitchBusy = busy;
            const group = document.getElementById('modeSwitch');
            if (group) group.classList.toggle('busy', busy);
            document.querySelectorAll('#modeSwitch button').forEach(btn => {{
                btn.disabled = busy;
                btn.classList.toggle('pending', busy && btn.dataset.mode === pendingMode);
            }});
            const titleEl = document.getElementById('miniPlTitle');
            if (!titleEl || !busy) return;
            const labels = {{ MIX_ARCHIVE: 'Mix Archive', MUSIC: 'Music', FAVORITES: 'Favourites' }};
            titleEl.innerText = '⏳ Switching to ' + (labels[pendingMode] || 'library') + '…';
        }}

        async function switchLibraryMode(mode) {{
            if (!mode) return;
            const token = ++modeRequestToken;
            updateModeSwitch(mode);
            setModeBusy(true, mode);
            try {{
                const res = await fetch('/api/mode?mode=' + encodeURIComponent(mode));
                const data = await res.json();
                if (token !== modeRequestToken) return;
                if (data && data.success) {{
                    updateModeSwitch(data.mode);
                    // fetchMiniPlaylist reports the offline notice itself, so no
                    // placeholder render here (it would flash "No audio").
                    await fetchMiniPlaylist();
                    await fetchStatus();
                }} else {{
                    fetchMiniPlaylist();
                }}
            }} catch (e) {{
                if (token === modeRequestToken) fetchMiniPlaylist();
            }} finally {{
                if (token === modeRequestToken) setModeBusy(false, null);
            }}
        }}

        async function fetchMiniPlaylist() {{
            try {{
                const res = await fetch('/api/playlist');
                const data = await res.json();
                renderMiniPlaylist(data);
                // A tap already picked the new mode; the poll must not paint the
                // old one back while that switch is still in flight.
                if (!modeSwitchBusy && data && data.mode) updateModeSwitch(data.mode);
            }} catch (e) {{}}
        }}

        // Start streaming with no extra taps. The server arms the session when
        // the service boots, so the phone picks up the running stream. Browsers
        // only allow audible playback after a gesture, so a refused play() keeps
        // the overlay up and the first touch starts the same stream.
        function engageStreamFromServer(resumePos) {{
            const audioEl = document.getElementById('mobileAudioStream');
            if (!audioEl) return;
            if (activeAudioFile && !audioStreamConfigured) {{
                audioEl.src = '/api/stream?file=' + encodeURIComponent(activeAudioFile);
                audioStreamConfigured = true;
            }}
            // One-time alignment with the saved stream position; the browser
            // then owns playback. Never re-sync from here.
            const startAt = Number(resumePos);
            if (isFinite(startAt) && startAt > 0) {{
                audioEl.addEventListener('loadedmetadata', function once() {{
                    audioEl.removeEventListener('loadedmetadata', once);
                    seekAudioTo(startAt);
                }});
            }}
            audioEl.play().then(() => {{
                audioStreamEngaged = true;
                hideStreamOverlay();
            }}).catch(() => {{
                showStreamOverlay();
            }});
        }}

        function showStreamOverlay() {{
            const overlay = document.getElementById('streamOverlay');
            if (overlay) overlay.style.display = 'flex';
        }}

        function hideStreamOverlay() {{
            const overlay = document.getElementById('streamOverlay');
            if (overlay) overlay.style.display = 'none';
            const banner = document.getElementById('mobileAudioBanner');
            if (banner) banner.style.display = 'block';
        }}

        let streamAutoStarted = false;

        // Called once the dashboard knows which file the server is streaming.
        function maybeAutoStartStream() {{
            if (streamAutoStarted) return;
            if (!activeAudioFile) return;
            streamAutoStarted = true;
            engageStreamFromServer(lastServerPos > 0 ? lastServerPos : 0);
        }}

        function activateMobileStream() {{
            engageStreamFromServer(lastServerPos > 0 ? lastServerPos : 0);
        }}

        function handlePlayPauseClick() {{
            const audioEl = document.getElementById('mobileAudioStream');
            if (audioEl) {{
                if (!audioEl.paused) {{
                    audioEl.pause();
                }} else {{
                    audioEl.play().catch(e => {{
                        const overlay = document.getElementById('streamOverlay');
                        if (overlay) overlay.style.display = 'flex';
                    }});
                }}
            }}
            sendAction('play-pause');
        }}

        // Visualizer 60 FPS Physics
        const BANDS = 24;
        const currentLevels = new Float32Array(BANDS).fill(0.04);
        const targetLevels = new Float32Array(BANDS).fill(0.04);
        const currentPeaks = new Float32Array(BANDS).fill(0.04);
        const peakVels = new Float32Array(BANDS).fill(0.0);

        function animLoop() {{
            const attack = 0.52;
            const decay = 0.88;
            const gravity = 0.0022;

            for (let i = 0; i < BANDS; i++) {{
                const bar = document.getElementById('vb' + i);
                const peakEl = document.getElementById('vp' + i);
                if (!bar) continue;

                if (isPlayerActive) {{
                    if (targetLevels[i] > currentLevels[i]) {{
                        currentLevels[i] += (targetLevels[i] - currentLevels[i]) * attack;
                    }} else {{
                        currentLevels[i] = Math.max(0.04, currentLevels[i] * decay);
                    }}

                    if (currentLevels[i] >= currentPeaks[i]) {{
                        currentPeaks[i] = currentLevels[i];
                        peakVels[i] = 0.0;
                    }} else {{
                        peakVels[i] += gravity;
                        currentPeaks[i] = Math.max(currentLevels[i], currentPeaks[i] - peakVels[i]);
                    }}
                }} else {{
                    currentLevels[i] = Math.max(0.04, currentLevels[i] * 0.82);
                    currentPeaks[i] = Math.max(0.04, currentPeaks[i] * 0.82);
                }}

                const barPct = Math.min(100, Math.max(4, Math.round(currentLevels[i] * 100)));
                const peakPct = Math.min(98, Math.max(barPct, Math.round(currentPeaks[i] * 100)));

                bar.style.height = barPct + '%';
                if (peakEl) peakEl.style.bottom = peakPct + '%';
            }}
            requestAnimationFrame(animLoop);
        }}
        requestAnimationFrame(animLoop);

        async function seekClick(e) {{
            if (!currentDurationSec || currentDurationSec <= 0) return;
            const rect = e.currentTarget.getBoundingClientRect();
            const clickX = e.clientX - rect.left;
            const pct = Math.max(0, Math.min(1, clickX / rect.width));
            const seekPos = pct * currentDurationSec;
            
            const audioEl = document.getElementById('mobileAudioStream');
            if (audioEl && audioEl.duration) {{
                seekAudioTo(seekPos);
            }}

            sendAction('seek_to', {{ position: seekPos.toFixed(1) }});
        }}

        function updateShuffleUI(isShuf) {{
            const btn = document.getElementById('btnShuffle');
            const txt = document.getElementById('shufText');
            const badge = document.getElementById('shuffleBadge');
            if (btn && txt) {{
                btn.classList.toggle('active', isShuf);
                txt.innerText = isShuf ? 'ON' : 'OFF';
            }}
            if (badge) {{
                badge.innerText = isShuf ? '🔀 SHUFFLE ON' : '🔀 SHUFFLE OFF';
                badge.classList.toggle('active', isShuf);
            }}
        }}

        function updateRepeatUI(repMode) {{
            const btn = document.getElementById('btnRepeat');
            const txt = document.getElementById('repText');
            if (txt) txt.innerText = String(repMode || 'ALL').toUpperCase();
            if (btn) btn.classList.toggle('active', Boolean(repMode && repMode !== 'off'));
        }}

        function formatClock(seconds) {{
            const total = Math.max(0, Math.floor(Number(seconds) || 0));
            const h = Math.floor(total / 3600);
            const m = Math.floor((total % 3600) / 60);
            const s = total % 60;
            return String(h).padStart(2, '0') + ':' + String(m).padStart(2, '0') + ':' + String(s).padStart(2, '0');
        }}

        async function fetchTheme() {{
            try {{
                const res = await fetch('/api/theme');
                const th = await res.json();
                if (th && th.id && th.id !== currentThemeId) {{
                    applyPalette(th);
                    loadThemeList();
                }}
            }} catch (e) {{}}
        }}

        async function fetchEq() {{
            try {{
                const res = await fetch('/api/eq');
                const data = await res.json();
                // The phone is the only audio output, so the visualizer follows
                // its element. The server cannot observe audio itself.
                isPlayerActive = audioElIsPlaying();

                if (data.levels && data.levels.length) {{
                    for (let i = 0; i < BANDS && i < data.levels.length; i++) {{
                        targetLevels[i] = isPlayerActive ? Math.max(0.04, Math.min(1.0, data.levels[i])) : 0.04;
                    }}
                }}
                // No local audio analysis exists (the phone owns playback), so
                // synthesise a gentle spectrum while the stream is running.
                if (isPlayerActive) {{
                    const t = performance.now() / 1000;
                    for (let i = 0; i < BANDS; i++) {{
                        const base = 0.30 + 0.22 * Math.sin(t * 1.7 + i * 0.55);
                        const wobble = 0.14 * Math.sin(t * 3.1 + i * 1.15);
                        const tilt = 1.0 - (i / BANDS) * 0.55;
                        targetLevels[i] = Math.max(0.05, Math.min(0.95, (base + wobble) * tilt));
                    }}
                }}
                const audioEl = document.getElementById('mobileAudioStream');
                const hasLocalClock = audioEl && isFinite(audioEl.duration) && audioEl.duration > 0 && audioStreamConfigured;
                const shownPos = hasLocalClock ? audioEl.currentTime : Number(data.position_sec || 0);
                const shownDur = hasLocalClock ? audioEl.duration : Number(data.duration_sec || 0);

                if (hasLocalClock) {{
                    document.getElementById('posTime').innerText = formatClock(shownPos);
                    document.getElementById('durTime').innerText = formatClock(shownDur);
                    const pct = shownDur > 0 ? (shownPos / shownDur) * 100 : 0;
                    document.getElementById('progressBar').style.width = Math.max(0, Math.min(100, pct)) + '%';
                    currentDurationSec = shownDur;
                }} else {{
                    if (data.position) document.getElementById('posTime').innerText = data.position;
                    if (data.duration) document.getElementById('durTime').innerText = data.duration;
                    if (data.progress_pct !== undefined) {{
                        document.getElementById('progressBar').style.width = Math.max(0, Math.min(100, data.progress_pct)) + '%';
                    }}
                }}
                if (data.position_sec !== undefined) {{
                    // The server only records where streaming last left off.
                    // The browser clock is authoritative while audio plays, so
                    // never seek from this poll - that is what used to trap
                    // playback in a repeating fragment.
                    lastServerPos = Number(data.position_sec);
                }}
                if (data.volume !== undefined) {{
                    document.getElementById('volPill').innerText = 'Vol: ' + data.volume + '%';
                    const audioEl = document.getElementById('mobileAudioStream');
                    if (audioEl) audioEl.volume = Math.max(0, Math.min(1, data.volume / 100.0));
                }}
                if (data.pitch_percent !== undefined) {{
                    const p = data.pitch_percent;
                    document.getElementById('pitchPill').innerText = 'Pitch: ' + (p > 0 ? '+' : '') + p + '%';
                }}
                updateShuffleUI(Boolean(data.shuffle));
                if (data.repeat) updateRepeatUI(data.repeat);
            }} catch (e) {{}}
        }}

        function updateAutoplayNotice(state) {{
            const el = document.getElementById('autoplayNotice');
            if (!el) return;
            if (!state || !state.status || state.status === 'pending') {{
                el.style.display = 'none';
                return;
            }}
            const labels = {{
                ready: '🎧 Stream ready — tap to listen',
                playing: '🎧 Stream ready — tap to listen',
                empty_playlist: '⏹ No mixes found in the archive',
                disabled: '⏹ Streaming disabled',
                player_unavailable: '⚠ Stream source unavailable',
                player_unreachable: '⚠ Stream source unreachable',
                playback_unverified: '⚠ Stream not confirmed',
            }};
            el.innerText = labels[state.status] || state.status;
            el.className = 'autoplay-notice ' + (
                (state.status === 'ready' || state.status === 'playing') ? 'ok' :
                (state.status === 'empty_playlist' || state.status === 'disabled') ? '' : 'warn'
            );
            el.style.display = 'block';
            if (state.detail) el.title = state.detail;
        }}

        async function fetchStatus() {{
            try {{
                const res = await fetch('/api/status');
                const data = await res.json();

                document.getElementById('trackTitle').innerText = data.title || "No Mix Playing";
                document.getElementById('trackArtist').innerText = data.album ? (data.artist + " • " + data.album) : (data.artist || "MPlanetarian");

                const badge = document.getElementById('playBadge');
                const state = (data.state || "stopped").toLowerCase();
                badge.innerText = state.toUpperCase();
                
                if (state === 'playing') {{
                    badge.style.background = 'var(--badge-bg)';
                    badge.style.color = 'var(--badge-color)';
                    badge.style.borderColor = 'var(--badge-color)';
                    document.getElementById('btnPlayPause').innerText = '⏸ Pause';
                }} else {{
                    badge.style.background = 'rgba(255, 170, 0, 0.15)';
                    badge.style.color = '#ffaa00';
                    badge.style.borderColor = '#ffaa00';
                    document.getElementById('btnPlayPause').innerText = '⏯ Play';
                }}

                document.getElementById('sourceBadge').innerText = (data.player || "None").toUpperCase();
                currentDurationSec = data.duration_sec || 0;
                updateAutoplayNotice(data.autoplay);

                if (data.active_file && activeAudioFile !== data.active_file) {{
                    const wasPlaying = audioStreamEngaged && audioElIsPlaying();
                    activeAudioFile = data.active_file;
                    audioStreamConfigured = false;
                    lastServerPos = -1.0;
                    const audioEl = document.getElementById('mobileAudioStream');
                    if (audioEl) {{
                        audioEl.src = '/api/stream?file=' + encodeURIComponent(data.active_file);
                        audioStreamConfigured = true;
                        const resumeAt = Number(data.position_sec) || 0;
                        if (resumeAt > 0) {{
                            // Wait for metadata before seeking, otherwise the
                            // assignment is discarded by the new source load.
                            audioEl.addEventListener('loadedmetadata', function once() {{
                                audioEl.removeEventListener('loadedmetadata', once);
                                seekAudioTo(resumeAt);
                            }});
                        }}
                        audioEl.load();
                        // Keep playing across a server-side track change.
                        if (wasPlaying) {{
                            audioEl.play().catch(() => {{}});
                        }}
                    }}
                }}
                // First status poll: the service already armed the stream at
                // startup, so pull it without waiting for a tap.
                maybeAutoStartStream();

                document.getElementById('specFormat').innerText = data.format || "AUDIO";
                document.getElementById('specRate').innerText = data.sample_rate || "48.0 kHz";
                document.getElementById('specChannels').innerText = data.channels || "Stereo";

                updateShuffleUI(Boolean(data.shuffle));
                if (data.repeat) updateRepeatUI(data.repeat);

                if (data.tracklist && data.tracklist.length > 0) {{
                    document.getElementById('tlCard').style.display = 'flex';
                    document.getElementById('tlCount').innerText = data.tracklist.length + ' Tracks';
                    const key = (data.active_file || data.title);
                    if (key !== lastLoadedMix) {{
                        lastLoadedMix = key;
                        const listEl = document.getElementById('tlItems');
                        listEl.innerHTML = '';
                        data.tracklist.forEach(t => {{
                            const li = document.createElement('li');
                            li.className = 'tl-item';
                            li.innerText = t;
                            listEl.appendChild(li);
                        }});
                    }}
                }} else {{
                    document.getElementById('tlCard').style.display = 'none';
                }}
            }} catch (e) {{}}
        }}

        async function sendAction(act, params = {{}}) {{
            let url = '/api/control?action=' + encodeURIComponent(act);
            for (const [k, v] of Object.entries(params)) {{
                url += '&' + encodeURIComponent(k) + '=' + encodeURIComponent(v);
            }}
            try {{
                await fetch(url, {{ method: 'POST' }});
                setTimeout(fetchEq, 50);
                setTimeout(fetchStatus, 150);
                setTimeout(fetchMiniPlaylist, 250);
            }} catch (e) {{}}
        }}

        setInterval(fetchEq, 100);
        setInterval(fetchStatus, 2000);
        setInterval(fetchTheme, 3000);
        setInterval(fetchMiniPlaylist, 15000);
        fetchEq();
        fetchStatus();
        fetchTheme();
        fetchMiniPlaylist();
    </script>
</body>
</html>
"""


# ------------------------------------------------------------------------------
# HTTP SERVER & API HANDLER (WITH RANGE HEADER SUPPORT FOR HTML5 STREAMING)
# ------------------------------------------------------------------------------
class CompanionHandler(http.server.BaseHTTPRequestHandler):
    def do_HEAD(self):
        url = urllib.parse.urlparse(self.path)
        if url.path in ("/", "/index.html"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.end_headers()
        elif url.path in ("/api/status", "/api/theme", "/api/eq", "/api/autoplay",
                          "/api/themes", "/api/set_theme", "/api/playlist", "/api/mode"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        parsed_query = urllib.parse.parse_qs(url.query)

        if url.path in ("/", "/index.html"):
            current_theme = get_theme_palette(CLI_THEME)
            html_content = render_html_page(current_theme)
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.end_headers()
            self.wfile.write(html_content.encode("utf-8"))
        elif url.path == "/api/eq":
            eq_data = get_eq_status()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(eq_data).encode("utf-8"))
        elif url.path == "/api/status":
            status = get_playback_status(CLI_THEME)
            status["autoplay"] = autoplay_state()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(status).encode("utf-8"))
        elif url.path == "/api/autoplay":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(autoplay_state()).encode("utf-8"))
        elif url.path == "/api/theme":
            theme = get_theme_palette(CLI_THEME)
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(theme).encode("utf-8"))
        elif url.path == "/api/themes":
            payload = {
                "current": get_current_theme_id(CLI_THEME),
                "themes": available_themes(),
            }
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode("utf-8"))
        elif url.path == "/api/set_theme":
            requested = parsed_query.get("theme", [""])[0]
            chosen = set_web_theme(requested) if requested else None
            success = chosen is not None
            payload = {
                "success": success,
                "theme": chosen or get_current_theme_id(CLI_THEME),
                "palette": get_theme_palette(CLI_THEME) if success else {},
            }
            self.send_response(200 if success else 400)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode("utf-8"))
        elif url.path == "/api/mode":
            requested = parsed_query.get("mode", [""])[0]
            chosen = set_library_mode(requested) if requested else None
            payload = {
                "success": chosen is not None,
                "mode": chosen or get_library_mode(),
                "mode_label": MODE_LABELS.get(chosen or get_library_mode(), "Library"),
                "total": len(build_stream_queue()),
                "library_fallback": bool(_queue_source_state.get("fallback")),
                "library_detail": _queue_source_state.get("detail", ""),
            }
            self.send_response(200 if chosen else 400)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode("utf-8"))
        elif url.path == "/api/playlist":
            payload = get_mini_playlist()
            payload["shuffle"] = bool(load_stream_session().get("shuffle", False))
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode("utf-8"))
        elif url.path == "/api/stream":
            file_path = parsed_query.get("file", [""])[0]
            if file_path and os.path.isfile(file_path):
                self._serve_audio_stream(file_path)
                return
            self.send_response(404)
            self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    # --------------------------------------------------------------------------
    # AUDIO STREAMING
    #
    # Phones and tablets pull the whole mix over HTTP and seek within it. Two
    # things matter for correctness:
    #   * `bytes=start-` must be honoured for the whole tail, otherwise the
    #     element receives a truncated body and restarts from the same offset.
    #   * A client that disconnects mid-transfer raises BrokenPipeError, which
    #     is normal and must never be reported as a server fault.
    # --------------------------------------------------------------------------
    STREAM_CHUNK = 65536

    def _serve_audio_stream(self, file_path: str) -> None:
        try:
            file_size = os.path.getsize(file_path)
            content_type = AUDIO_CONTENT_TYPES.get(Path(file_path).suffix.lower(), "audio/mpeg")
            start, end = self._parse_range_header(file_size)

            if start is None:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{file_size}")
                self.send_header("Content-Length", "0")
                self.send_header("Accept-Ranges", "bytes")
                self.end_headers()
                return

            length = end - start + 1
            if start == 0 and end == file_size - 1:
                self.send_response(200)
                self.send_header("Content-Length", str(file_size))
            else:
                self.send_response(206)
                self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
                self.send_header("Content-Length", str(length))
            self.send_header("Content-Type", content_type)
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

            with open(file_path, "rb") as f:
                f.seek(start)
                remaining = length
                while remaining > 0:
                    data = f.read(min(self.STREAM_CHUNK, remaining))
                    if not data:
                        break
                    self.wfile.write(data)
                    remaining -= len(data)
        except (BrokenPipeError, ConnectionResetError):
            # The phone scrubbed away or closed the tab: not an error.
            self.close_connection = True
        except OSError:
            try:
                self.send_error(404)
            except Exception:
                pass

    def _parse_range_header(self, file_size: int) -> Tuple[Optional[int], int]:
        """Return (start, end) for the requested bytes, or (None, 0) if invalid.

        A missing or unparsable header means "send the whole file".
        """
        raw = (self.headers.get("Range") or "").strip()
        if not raw:
            return 0, file_size - 1

        m = re.match(r'bytes=(\d*)-(\d*)$', raw)
        if not m or (not m.group(1) and not m.group(2)):
            return 0, file_size - 1

        try:
            if not m.group(1):
                # Suffix form, e.g. "bytes=-65536" = last 64 KiB.
                suffix = int(m.group(2))
                if suffix <= 0:
                    return None, 0
                return max(0, file_size - suffix), file_size - 1

            start = int(m.group(1))
            end = int(m.group(2)) if m.group(2) else file_size - 1
        except ValueError:
            return 0, file_size - 1

        if start >= file_size:
            return None, 0
        return start, min(end, file_size - 1)

    def do_POST(self):
        url = urllib.parse.urlparse(self.path)
        if url.path == "/api/control":
            params = urllib.parse.parse_qs(url.query)
            action = params.get("action", [""])[0]
            success = control_player(action, params)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"success": success, "action": action}).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass


def main():
    global CLI_THEME
    default_host = os.environ.get("WEB_COMPANION_HOST", "0.0.0.0")
    default_port = int(os.environ.get("WEB_COMPANION_PORT", str(PORT)))

    parser = argparse.ArgumentParser(description="MP Mix Manager Mobile Web Companion")
    parser.add_argument("--host", "-H", type=str, default=default_host)
    parser.add_argument("--port", "-p", type=int, default=default_port)
    parser.add_argument("--theme", "-t", type=str, default=None)
    parser.add_argument("--stream-status", action="store_true",
                        help="Print the resolved stream queue as JSON and exit")
    args = parser.parse_args()

    if args.stream_status:
        playlist = scan_playlist_files()
        track, position = _pick_start_track(playlist)
        print(json.dumps({
            "playlist_size": len(playlist),
            "track": track or "",
            "position": round(position, 2),
            "listening": "HTTP stream only (no local audio output)",
        }, indent=2))
        return 0

    CLI_THEME = args.theme
    active_theme = get_theme_palette(CLI_THEME)
    lan_ip = get_local_ip()
    host_display = lan_ip if args.host in ("0.0.0.0", "", "::") else args.host

    server_address = (args.host, args.port)
    try:
        httpd = http.server.ThreadingHTTPServer(server_address, CompanionHandler)
    except OSError as err:
        if err.errno in (98, 48, 10048):
            print(f"\n======================================================================")
            print(f"  🌌 MP MIX ARCHIVE MANAGER — MOBILE WEB COMPANION (ACTIVE)")
            print(f"======================================================================")
            print(f"  • Local Machine:  http://localhost:{args.port}")
            print(f"  • Phone / Tablet: http://{host_display}:{args.port}")
            print(f"======================================================================\n")
            return 0
        raise

    # Arm the stream at startup so the phone begins playing on its own. This
    # only catalogs files and marks the session active; no local device opens.
    stream_thread = start_autoplay_worker()

    print(f"\n======================================================================")
    print(f"  🌌 MP MIX ARCHIVE MANAGER — MOBILE WEB COMPANION")
    print(f"======================================================================")
    print(f"  • Active Theme:   {active_theme['name']} ({active_theme['id']})")
    print(f"  • Library Mode:   {MODE_LABELS.get(get_library_mode(), 'Library')}")
    print(f"  • Local Machine:  http://localhost:{args.port}")
    print(f"  • Phone / Tablet: http://{host_display}:{args.port}")
    print(f"  • Audio Output:   STREAM ONLY (no local device)")
    print(f"  • Autoplay:       {'ON' if _env_flag('WEB_COMPANION_AUTOPLAY', True) else 'OFF'}")
    print(f"======================================================================\n")

    def _report_stream_queue() -> None:
        stream_thread.join()
        state = autoplay_state()
        if state.get("status") == "ready":
            print(f"  ▶ AUTO-STREAM ARMED: {state.get('detail', '')}", flush=True)
            print(f"  • First track:    {state.get('track', '')}", flush=True)
        else:
            print(f"  ⏹ NO STREAM QUEUE: {state.get('detail', '')}", flush=True)
        print(f"======================================================================\n", flush=True)

    threading.Thread(target=_report_stream_queue, name="mp-companion-queue-report", daemon=True).start()

    print("Press Ctrl+C to stop the companion server.\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Web Companion...")
        httpd.server_close()


if __name__ == "__main__":
    main()
