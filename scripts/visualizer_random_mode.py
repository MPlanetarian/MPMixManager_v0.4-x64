"""Random preset rotation shared by the MP Visualizer backends.

Pressing **R** inside the MP Visualizer window turns random mode on: the window
switches to a new randomly chosen preset every minute. Pressing **R** again
turns random mode off and leaves the window on the preset it is showing.

The mixin owns only the on/off state and the dwell clock. The host renderer
provides ``preset`` and ``switch_preset()``, so the Vulkan renderer and the
OpenGL renderer behave identically.
"""
from __future__ import annotations

import random
import time
from typing import Any, Dict, Optional

# Seconds a preset is held before random mode picks another one.
RANDOM_PRESET_INTERVAL = 60.0


def pick_random_preset(current: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """Return a random preset that is not the one currently on screen.

    Repeating the preset that is already showing would look like random mode
    had stalled, so the current key is filtered out of the draw pool.
    """
    try:
        from mp_liquid_visualizer_vulkan import VISUALIZER_PRESETS
    except ImportError:
        from scripts.mp_liquid_visualizer_vulkan import VISUALIZER_PRESETS
    if not VISUALIZER_PRESETS:
        return None
    current_key = (current or {}).get("key")
    pool = [p for p in VISUALIZER_PRESETS if p.get("key") != current_key]
    return random.choice(pool or VISUALIZER_PRESETS)


class RandomPresetMixin:
    """Minute-by-minute random preset rotation toggled by the R key."""

    random_mode = False

    def init_random_mode(self) -> None:
        self.random_mode = False
        self._random_switch_at = 0.0

    def toggle_random_mode(self) -> bool:
        """Flip random mode and return the new state.

        Turning it on starts the minute clock; the current preset keeps playing
        until that first minute is up. Turning it off cancels the clock and
        leaves the preset in place.
        """
        self.random_mode = not bool(getattr(self, "random_mode", False))
        self._random_switch_at = (
            time.monotonic() + RANDOM_PRESET_INTERVAL if self.random_mode else 0.0
        )
        return self.random_mode

    def poll_random_mode(self, now: Optional[float] = None) -> bool:
        """Advance to a new random preset when the minute is up.

        Returns True when this call switched the preset. Screensaver windows and
        F10/F11 copies are viewers, so they never rotate on their own.
        """
        if not getattr(self, "random_mode", False):
            return False
        if getattr(self, "screensaver", False):
            return False
        try:
            from visualizer_monitor_span import ROLE_SPAWNED
        except ImportError:
            from scripts.visualizer_monitor_span import ROLE_SPAWNED
        if getattr(self, "_span_role", "") == ROLE_SPAWNED:
            return False
        now = time.monotonic() if now is None else float(now)
        if now < getattr(self, "_random_switch_at", 0.0):
            return False
        self._random_switch_at = now + RANDOM_PRESET_INTERVAL
        nxt = pick_random_preset(getattr(self, "preset", None))
        if nxt is None:
            return False
        self.switch_preset(nxt)
        return True
