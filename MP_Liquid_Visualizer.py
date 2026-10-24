#!/usr/bin/env python3
"""MP_Liquid_Visualizer — Native Vulkan 3D Audio-Reactive Visualizer for MP Liquid Audio Player.

Built from the ground up in Vulkan (1400x1400 fixed borderless window, zero text overlay).
First Preset: "Cosmic Dreamworlds (Liquid)"
Exclusively inspired by MPlanetarian - Cosmic Dreamworlds [Deluxe Edition] cover art
(https://mplanetarian.bandcamp.com/album/mplanetarian-cosmic-dreamworlds-deluxe-edition)
with strictly ONE Bandcamp cover per preset.

Core Behavior:
- Continually generates 3D geometry that connects and moves to the music currently playing.
- When music is paused or stopped, 3D generation freezes in-place and waits for the user
  to press Play on the audio player.
- The user cannot change how the visualizer looks; they can only select different presets.
- Fixed 1400x1400 borderless window, no scrollbar, zero text overlay ever displayed.
- Closes immediately when the user presses Escape or 'q'.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from scripts.mp_liquid_visualizer_vulkan import (  # noqa: E402
    VISUALIZER_PRESETS,
    WINDOW_HEIGHT,
    WINDOW_WIDTH,
    AudioTelemetryBridge,
    LiquidVisualizerVulkanRenderer,
    VisualizerUBO,
    get_active_preset,
    main,
    run_self_test,
    run_visualizer,
    save_active_preset,
    save_png,
)

__all__ = [
    "VISUALIZER_PRESETS",
    "WINDOW_WIDTH",
    "WINDOW_HEIGHT",
    "AudioTelemetryBridge",
    "LiquidVisualizerVulkanRenderer",
    "VisualizerUBO",
    "get_active_preset",
    "save_active_preset",
    "save_png",
    "run_self_test",
    "run_visualizer",
    "main",
]

if __name__ == "__main__":
    raise SystemExit(main())
