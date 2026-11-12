"""Linux process-creation events, shaped for the Stream of Frequency effect.

The MP Visualizer's *Stream of Frequency — Dynamic Waves* presets draw a river
of frequency bands. Inside the MP Audio Player that river is driven by FFT
telemetry. In the **screen saver** there is no player running, so the same
river is driven by something else that is always happening on a live machine:
**every new PID the Linux kernel creates**.

A new process fires one *stream event*. The event travels across the screen as
a bright front, throwing pixel fireworks (coloured squares and glyph icons) out
behind it as it goes. On a quiet desktop that is a handful of events a minute;
during a build, a browser tab storm or a package upgrade it becomes a
machine-gun of streams, which is exactly the Matrix-on-fire look the presets
are after.

The module is deliberately dependency-free and safe to poll from a render
loop:

* :class:`PidStreamSource` reads ``/proc`` directly on Linux.
* On macOS / Windows / BSD it reports no events, so the saver falls back to
  its normal slow river rather than stalling.
* Reading ``/proc`` is a directory listing plus integer parsing — about
  0.1 ms on a busy desktop — and is rate limited to one scan per
  ``scan_interval`` seconds.

Usage::

    source = PidStreamSource()
    state = source.update(dt)      # once per frame
    state.phase, state.heat, state.serial
"""
from __future__ import annotations

import math
import os
import platform
import time
from dataclasses import dataclass
from typing import Optional, Set

# A stream event lives for this long. The shader maps it to one sweep of the
# screen, so this is also the "time to cross the display" of a PID.
EVENT_SECONDS = 1.85

# Heat decays over the event lifetime. The front stays legible for most of the
# sweep and then fades quickly at the very end.
HEAT_FLOOR = 0.0

# Linux reuses PIDs. A brand-new PID that is below the previous maximum is
# either a wrap-around or reuse, and is treated as a normal event anyway.
_MAX_TRACKED = 20000


@dataclass
class PidStreamState:
    """One frame of PID-stream telemetry, ready to upload to the shader."""

    phase: float = 0.0     # 0..1 position of the travelling front
    heat: float = 0.0      # 0..1 brightness of the burst
    serial: float = 0.0    # monotonic event counter (seeds the randomness)
    events: int = 0        # events fired by the most recent scan
    last_pid: int = 0      # the PID that fired the newest event

    def as_uniform(self) -> tuple:
        """The ``u.stream`` vector: id is filled in by the renderer."""
        return (self.phase, self.heat, self.serial)


def _pid_scan_available() -> bool:
    system = platform.system().lower()
    if system == "linux":
        return os.path.isdir("/proc")
    return False


def read_pids() -> Optional[Set[int]]:
    """Every numeric entry in ``/proc``, or ``None`` when unavailable."""
    if not _pid_scan_available():
        return None
    try:
        names = os.listdir("/proc")
    except OSError:
        return None
    pids: Set[int] = set()
    for name in names:
        if not name.isdigit():
            continue
        try:
            pids.add(int(name))
        except ValueError:
            continue
        if len(pids) >= _MAX_TRACKED:
            break
    return pids


class PidStreamSource:
    """Turn new PIDs into stream events for the visualizer.

    ``scan_interval`` keeps the ``/proc`` walk off the hot path. The event
    clock advances every frame regardless, so the front moves smoothly even
    though new PIDs are only noticed a few times a second.
    """

    def __init__(self, scan_interval: float = 0.12, event_seconds: float = EVENT_SECONDS,
                 enabled: Optional[bool] = None, source=None):
        if enabled is None:
            enabled = str(os.environ.get("MP_PID_STREAM", "1")).strip().lower() not in (
                "0", "false", "no", "off",
            )
        self.enabled = bool(enabled)
        self.scan_interval = max(0.02, float(scan_interval))
        self.event_seconds = max(0.2, float(event_seconds))
        self._read = source if source is not None else read_pids
        self._known: Optional[Set[int]] = None
        self._last_scan = 0.0
        self._started = 0.0
        self._started_once = False
        self._serial = 0.0
        self._event_at = -1e9
        self._event_pid = 0
        self._event_heat = 0.0
        self._pending = 0

    # -- lifecycle -----------------------------------------------------
    def reset(self, now: Optional[float] = None) -> None:
        """Forget the known PID set, so the next scan does not fire a storm."""
        self._known = None
        self._last_scan = 0.0
        self._started = time.monotonic() if now is None else float(now)
        self._started_once = False
        self._pending = 0

    # -- frame update ---------------------------------------------------
    def update(self, dt: float = 0.0, now: Optional[float] = None) -> PidStreamState:
        now = time.monotonic() if now is None else float(now)
        if not self._started_once:
            self._started = now
            self._started_once = True

        if self.enabled and (now - self._last_scan) >= self.scan_interval:
            self._last_scan = now
            self._scan(now)

        elapsed = now - self._event_at
        if elapsed < 0.0 or elapsed > self.event_seconds:
            return PidStreamState(serial=self._serial, last_pid=self._event_pid)

        phase = elapsed / self.event_seconds
        # Ease-out so the front decelerates slightly as it reaches the far edge,
        # which reads better than a perfectly linear sweep.
        phase = 1.0 - (1.0 - phase) ** 1.35
        heat = self._event_heat * (1.0 - phase ** 2.4)
        return PidStreamState(
            phase=float(min(1.0, max(0.0, phase))),
            heat=float(max(HEAT_FLOOR, min(1.0, heat))),
            serial=self._serial,
            events=self._pending,
            last_pid=self._event_pid,
        )

    # -- internals ------------------------------------------------------
    def _scan(self, now: float) -> None:
        current = self._read()
        if current is None:
            return
        previous = self._known
        self._known = current
        if previous is None:
            # First scan only learns the baseline. Otherwise starting the
            # saver would fire one event per process already on the machine.
            return

        new_pids = current - previous
        if not new_pids:
            self._pending = 0
            return

        self._pending = len(new_pids)
        # The newest event wins the front; the rest are folded into its heat so
        # a storm of new processes produces a hotter, longer burst rather than
        # an unreadable stack of fronts.
        self._serial += 1.0
        self._event_at = now
        self._event_pid = max(new_pids)
        burst = math.log2(1.0 + len(new_pids)) / math.log2(1.0 + 8.0)
        self._event_heat = float(min(1.0, 0.55 + 0.55 * burst))
        # A storm keeps re-arming the event so the screen stays busy.
        if len(new_pids) > 6:
            self._event_at = now - self.event_seconds * 0.06


def demoSweep(now: float, period: float = 4.0) -> PidStreamState:
    """A synthetic PID event clock, used by tests and previews."""
    cycle = (now % max(0.1, period)) / max(0.1, period)
    phase = 1.0 - (1.0 - cycle) ** 1.35
    return PidStreamState(
        phase=float(phase),
        heat=float(max(0.0, 1.0 - phase ** 2.4)),
        serial=float(int(now / max(0.1, period))),
        events=1,
        last_pid=0,
    )


class StreamDriver:
    """The one place that decides *what* fires a Stream of Frequency event.

    ``mode="pid"``   — the screen saver: new Linux PIDs fire the streams.
    ``mode="audio"`` — the player: beats and transients fire the streams, so
                       the effect stays locked to the music instead of to
                       whatever the desktop happens to be doing.

    Both modes produce the same ``(stream_id, phase, heat, serial)`` vector the
    shader reads from ``u.stream``, so a preset looks the same in either place
    and only the trigger differs.
    """

    def __init__(self, mode: str = "pid", event_seconds: float = EVENT_SECONDS,
                 pid_source: Optional[PidStreamSource] = None,
                 min_audio_gap: float = 0.55):
        self.mode = "audio" if str(mode).lower() == "audio" else "pid"
        self.event_seconds = max(0.2, float(event_seconds))
        self._pid = pid_source if pid_source is not None else PidStreamSource(
            event_seconds=self.event_seconds
        )
        self._serial = 0.0
        self._event_at = -1e9
        self._event_heat = 0.0
        self._last_audio_fire = 0.0
        self._min_audio_gap = max(0.0, float(min_audio_gap))
        self._last_beat = 0.0
        self._last_rms = 0.0

    def reset(self) -> None:
        self._serial = 0.0
        self._event_at = -1e9
        self._event_heat = 0.0
        self._last_audio_fire = 0.0
        self._last_beat = 0.0
        self._last_rms = 0.0
        self._pid.reset()

    def update(self, dt: float, now: float, bridge=None) -> tuple:
        """Return the ``(stream_id, phase, heat, serial)`` stream vector.

        ``stream_id`` is filled by the renderer, which knows which of the two
        presets is on screen; here it is always 0.
        """
        if self.mode == "audio" and bridge is not None:
            self._poll_audio(now, bridge)
        else:
            state = self._pid.update(dt, now=now)
            return (0.0, state.phase, state.heat, state.serial)
        elapsed = now - self._event_at
        if elapsed < 0.0 or elapsed > self.event_seconds:
            return (0.0, 0.0, 0.0, self._serial)
        phase = 1.0 - (1.0 - min(1.0, elapsed / self.event_seconds)) ** 1.35
        heat = self._event_heat * (1.0 - phase ** 2.4)
        return (0.0, float(min(1.0, max(0.0, phase))), float(min(1.0, max(0.0, heat))), self._serial)

    def _poll_audio(self, now: float, bridge) -> None:
        """Fire a stream when the music hits, with a floor between events."""
        beat = float(getattr(bridge, "beat_pulse", 0.0) or 0.0)
        rms = float(getattr(bridge, "rms_energy", 0.0) or 0.0)
        rising_beat = beat > 0.35 and beat > self._last_beat + 0.08
        rising_rms = rms > 0.30 and rms > self._last_rms + 0.10
        self._last_beat, self._last_rms = beat, rms
        if now - self._last_audio_fire < self._min_audio_gap:
            return
        if not (rising_beat or rising_rms):
            return
        self._last_audio_fire = now
        self._serial += 1.0
        self._event_at = now
        self._event_heat = float(min(1.0, 0.45 + 0.55 * max(beat, rms)))

