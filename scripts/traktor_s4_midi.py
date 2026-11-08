#!/usr/bin/env python3
"""
Traktor Kontrol S4 Hardware MIDI Controller Service for MP Mix Archive Manager & MP Audio Player
Version 0.4.0 Stable

Communicates with Native Instruments Traktor Kontrol S4 over Hardware ALSA MIDI Port (amidi / hw:0,0).
Translates MIDI Mode signals (Pitch Faders, Buttons, Encoders, Volume Sliders) to MP Audio Player IPC commands.
"""

from __future__ import annotations
import os, sys, time, json, socket, subprocess, threading, signal, select, argparse
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, List

CONFIG_DIR = Path.home() / ".config" / "mix-manager"
CONFIG_DIR.mkdir(parents=True, exist_ok=True)

PID_FILE = CONFIG_DIR / "traktor_s4_midi.pid"
LOG_FILE = CONFIG_DIR / "traktor_s4_midi.log"
STATE_FILE = CONFIG_DIR / "traktor_s4_midi_state.json"
FIRST_SEEN_FLAG = CONFIG_DIR / "traktor_s4_first_seen.flag"

PLAYER_SOCKET = CONFIG_DIR / "mp_audio_player.sock"
PLAYER_PORT_FILE = CONFIG_DIR / "mp_audio_player.port"
PLAYER_STATE_FILE = CONFIG_DIR / "mp_player_state.json"

DEFAULT_PORT = "hw:0,0"
DEFAULT_DEVICE_NAME = "Traktor Kontrol S4"

# ANSI Colors
BOLD = "\033[1m"
DIM = "\033[2m"
ITALIC = "\033[3m"
NC = "\033[0m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
MAGENTA = "\033[35m"
BLUE = "\033[34m"
WHITE = "\033[37m"

def log(msg: str):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{timestamp}] [Traktor S4 MIDI] {msg}"
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(formatted + "\n")
    except Exception:
        pass


def send_player_ipc(cmd: str, **kwargs) -> Optional[Dict[str, Any]]:
    """Send IPC command directly to running MP Audio Player."""
    use_unix = hasattr(socket, "AF_UNIX") and PLAYER_SOCKET.exists()
    if not use_unix and not PLAYER_PORT_FILE.exists():
        return None
    try:
        s = socket.socket(socket.AF_UNIX if use_unix else socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1.2)
        target = str(PLAYER_SOCKET) if use_unix else ("127.0.0.1", int(PLAYER_PORT_FILE.read_text().strip()))
        s.connect(target)
        s.sendall(json.dumps({"cmd": cmd, **kwargs}).encode("utf-8"))
        raw = s.recv(16384).decode("utf-8")
        s.close()
        if raw:
            return json.loads(raw)
    except Exception as e:
        log(f"IPC command failed ({cmd}): {e}")
    return None


def get_player_status() -> Optional[Dict[str, Any]]:
    """Fetch live status of MP Audio Player."""
    res = send_player_ipc("status")
    if res and res.get("status") == "ok":
        return res.get("data")
    if PLAYER_STATE_FILE.is_file():
        try:
            return json.loads(PLAYER_STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return None


def is_player_running() -> bool:
    st = get_player_status()
    if st:
        return st.get("running", False) or st.get("state") in ("playing", "paused")
    return False


def detect_traktor_s4_port() -> Tuple[bool, str, str]:
    """
    Detect Traktor Kontrol S4 hardware port.
    Returns: (is_detected, port_str, details)
    """
    import glob
    port = DEFAULT_PORT
    detected = False
    details = ""

    # 1. Primary ALSA check: /proc/asound/card*/midi*
    for f in glob.glob("/proc/asound/card*/midi*"):
        try:
            content = Path(f).read_text(encoding="utf-8", errors="ignore")
            if "Traktor Kontrol S4" in content or "Traktor" in content:
                parts = f.split("/")
                card_num = parts[3].replace("card", "")
                dev_num = parts[-1].replace("midi", "")
                port = f"hw:{card_num},{dev_num}"
                detected = True
                details = content.splitlines()[0].strip()
                return detected, port, details
        except Exception:
            pass

    # 2. Check /proc/asound/cards
    try:
        cards = Path("/proc/asound/cards").read_text(encoding="utf-8", errors="ignore")
        if "Traktor Kontrol S4" in cards or "TraktorKontrolS" in cards:
            detected = True
            details = "Traktor Kontrol S4 (snd-usb-caiaq)"
            port = "hw:0,0"
            return detected, port, details
    except Exception:
        pass

    # 3. Check amidi -l
    try:
        res = subprocess.run(["amidi", "-l"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=2)
        for line in res.stdout.splitlines():
            if "Traktor Kontrol S4" in line or "Traktor" in line:
                parts = line.split()
                if len(parts) >= 2 and parts[1].startswith("hw:"):
                    port = parts[1]
                detected = True
                details = line.strip()
                return detected, port, details
    except Exception:
        pass

    # 4. Check rawmidi character device
    if os.path.exists("/dev/snd/midiC0D0"):
        try:
            inp = Path("/proc/bus/input/devices").read_text(encoding="utf-8", errors="ignore")
            if "Traktor Kontrol S4" in inp:
                detected = True
                details = "Traktor Kontrol S4 (/dev/snd/midiC0D0)"
                port = "hw:0,0"
        except Exception:
            pass

    return detected, port, details


class TraktorS4MidiController:
    """
    Traktor Kontrol S4 MIDI Event Processor.
    Translates raw MIDI messages to MP Mix Archive Manager and MP Audio Player commands.
    """

    def __init__(self, port: str = DEFAULT_PORT):
        self.port = port
        self.rawmidi_dev = self._get_rawmidi_device_path(port)
        self.running = False
        self.last_pitch_sent = 0
        self.last_pitch_time = 0.0
        self.last_vol_sent = -1
        self.last_vol_time = 0.0
        self.last_turn_time = 0.0
        self.shift_active = False

    def _get_rawmidi_device_path(self, port: str) -> Optional[str]:
        if port.startswith("hw:"):
            parts = port[3:].split(",")
            if len(parts) == 2:
                card, dev = parts[0], parts[1]
                path = f"/dev/snd/midiC{card}D{dev}"
                if os.path.exists(path):
                    return path
        if os.path.exists("/dev/snd/midiC0D0"):
            return "/dev/snd/midiC0D0"
        return None

    def update_state(self, status: str, last_action: str = ""):
        state_data = {
            "device": DEFAULT_DEVICE_NAME,
            "port": self.port,
            "rawmidi_dev": self.rawmidi_dev,
            "status": status,
            "pid": os.getpid(),
            "updated_at": time.time(),
            "last_action": last_action,
            "shift": self.shift_active,
        }
        try:
            STATE_FILE.write_text(json.dumps(state_data, indent=2), encoding="utf-8")
        except Exception:
            pass

    def scale_pitch_cc_to_percent(self, value: int, inverted: bool = False) -> int:
        """
        Convert standard 7-bit CC (0..127) to DJ Pitch percentage (-20% to +20%).
        Center detent is 64. A deadzone of 62..66 snaps to 0.
        """
        if 62 <= value <= 66:
            return 0
        if inverted:
            val = 127 - value
        else:
            val = value
        
        # Center is 64
        diff = val - 64
        pct = int(round((diff / 63.0) * 20.0))
        return max(-20, min(20, pct))

    def scale_pitch_bend_to_percent(self, lsb: int, msb: int, inverted: bool = False) -> int:
        """
        Convert 14-bit Pitch Bend (0..16383, center 8192) to DJ Pitch percentage (-20% to +20%).
        """
        val_14 = (msb << 7) | lsb
        diff = val_14 - 8192
        if abs(diff) < 250:
            return 0
        if inverted:
            diff = -diff
        pct = int(round((diff / 8191.0) * 20.0))
        return max(-20, min(20, pct))

    def handle_pitch_change(self, percent: int, source: str) -> str:
        now = time.time()
        # Limit rate to avoid spamming the audio resampler (max 25 updates/sec unless 0 snap)
        if percent == self.last_pitch_sent and (now - self.last_pitch_time) < 0.2:
            return f"Pitch unchanged ({percent}%)"
        if percent != 0 and abs(percent - self.last_pitch_sent) < 1 and (now - self.last_pitch_time) < 0.04:
            return f"Pitch rate-limited ({percent}%)"

        self.last_pitch_sent = percent
        self.last_pitch_time = now
        log(f"Setting pitch to {percent}% (Source: {source})")
        send_player_ipc("set_pitch", percent=percent)
        return f"DJ Pitch: {percent:+d}%"

    def handle_volume_change(self, val_127: int, channel_name: str) -> str:
        now = time.time()
        vol = max(0, min(100, int(round((val_127 / 127.0) * 100.0))))
        if vol == self.last_vol_sent and (now - self.last_vol_time) < 0.2:
            return f"Volume unchanged ({vol}%)"
        if abs(vol - self.last_vol_sent) < 2 and (now - self.last_vol_time) < 0.05:
            return f"Volume rate-limited ({vol}%)"

        self.last_vol_sent = vol
        self.last_vol_time = now
        log(f"Setting volume to {vol}% (Fader: {channel_name})")
        send_player_ipc("set_volume", volume=vol)
        return f"Volume: {vol}%"

    def process_midi_event(self, status: int, data1: int, data2: int) -> Tuple[str, str]:
        """
        Parse raw MIDI packet and execute matching MP Mix Archive Manager / Player function.
        Returns: (event_desc, action_desc)
        """
        msg_type = status & 0xF0
        channel = (status & 0x0F) + 1  # 1-indexed channel (1 to 16)
        action = ""
        desc = ""

        # =========================================================================
        # 1. PITCH BEND (0xE0) - Traktor S4 High-Resolution Deck Pitch Controls
        # =========================================================================
        if msg_type == 0xE0:
            # Channel 1: Left Deck Pitch Bend
            # Channel 2: Right Deck Pitch Bend
            deck_name = "Left Deck (Deck A)" if channel == 1 else ("Right Deck (Deck B)" if channel == 2 else f"Deck Ch {channel}")
            pct = self.scale_pitch_bend_to_percent(data1, data2)
            desc = f"Pitch Bend Ch {channel} ({deck_name}): LSB={data1} MSB={data2}"
            action = self.handle_pitch_change(pct, f"{deck_name} Pitch Bend")
            return desc, action

        # =========================================================================
        # 2. CONTROL CHANGE (0xB0) - Faders, Knobs, Encoders, CC-mapped Buttons
        # =========================================================================
        if msg_type == 0xB0:
            cc = data1
            val = data2
            desc = f"CC {cc} Ch {channel}: Val={val}"

            # Left Deck Pitch Fader CCs (CC 14, CC 0, CC 1, CC 2, CC 16, CC 20)
            if (channel == 1 and cc in (14, 0, 1, 2, 16, 20)) or (channel != 2 and cc in (14, 20)):
                pct = self.scale_pitch_cc_to_percent(val)
                action = self.handle_pitch_change(pct, "Left Deck Pitch Fader")
                return desc, action

            # Right Deck Pitch Fader CCs (CC 15, CC 3, CC 4, CC 17, CC 21)
            if (channel == 2 and cc in (15, 3, 4, 17, 21)) or (channel != 1 and cc in (15, 21)):
                pct = self.scale_pitch_cc_to_percent(val)
                action = self.handle_pitch_change(pct, "Right Deck Pitch Fader")
                return desc, action

            # Mixer Volume Faders (Channels A, B, C, D)
            # Default CCs: 8, 9, 10, 11 or 7 (Standard MIDI Volume)
            if cc in (8, 9, 10, 11, 7, 19, 22):
                ch_map = {8: "Ch A", 9: "Ch B", 10: "Ch C", 11: "Ch D", 7: "Master", 19: "Ch A", 22: "Ch B"}
                action = self.handle_volume_change(val, ch_map.get(cc, f"CC {cc}"))
                return desc, action

            # Master / Gain Knobs (CC 23, 24, 25, 26)
            if cc in (23, 24, 25, 26):
                action = self.handle_volume_change(val, f"Gain CC {cc}")
                return desc, action

            # Browse Encoder Turn (CC 42, CC 43, CC 64, CC 80, CC 81, or Relative 65/63 / 1/127)
            if cc in (42, 43, 80, 81, 100):
                now = time.time()
                if (now - self.last_turn_time) > 0.08:
                    self.last_turn_time = now
                    if val > 64 or val == 1:
                        send_player_ipc("next")
                        action = "Next Track / Mix ⏩"
                    else:
                        send_player_ipc("prev")
                        action = "Previous Track / Mix ⏪"
                return desc, action

            # Loop Move / Size Encoder Turn (CC 44, CC 45)
            if cc in (44, 45):
                now = time.time()
                if (now - self.last_turn_time) > 0.08:
                    self.last_turn_time = now
                    if val > 64 or val == 1:
                        send_player_ipc("seek", seconds=30.0)
                        action = "Seek Forward +30s ⏩"
                    else:
                        send_player_ipc("seek", seconds=-30.0)
                        action = "Seek Backward -30s ⏪"
                return desc, action

            # CC-triggered Buttons (val > 0)
            if val > 0:
                # Play button (CC 32, CC 33, CC 40)
                if cc in (32, 33, 40):
                    send_player_ipc("toggle")
                    action = "Play / Pause (Toggle)"
                    return desc, action
                # Cue button (CC 34, CC 35, CC 41)
                elif cc in (34, 35, 41):
                    send_player_ipc("seek_to", position=0.0)
                    action = "Cue (Return to Start)"
                    return desc, action
                # Sync / Pitch Reset (CC 36, CC 37)
                elif cc in (36, 37):
                    send_player_ipc("reset_pitch")
                    action = "Sync (Reset Pitch to 0%)"
                    return desc, action
                # Pitch Up / Down Nudge Buttons (CC 38, CC 39)
                elif cc == 38:
                    send_player_ipc("pitch_up", step=1)
                    action = "Pitch Nudge Up (+1%)"
                    return desc, action
                elif cc == 39:
                    send_player_ipc("pitch_down", step=1)
                    action = "Pitch Nudge Down (-1%)"
                    return desc, action

            return desc, f"Ignored CC {cc}"

        # =========================================================================
        # 3. NOTE ON (0x90) / NOTE OFF (0x80) - Hardware Push Buttons & Pads
        # =========================================================================
        if msg_type in (0x90, 0x80):
            note = data1
            vel = data2
            is_on = (msg_type == 0x90) and (vel > 0)
            desc = f"Note {'ON' if is_on else 'OFF'} {note} Ch {channel} Vel={vel}"

            if not is_on:
                # Shift release
                if note in (48, 49, 12):
                    self.shift_active = False
                return desc, "Note Release"

            # Shift Button Press (Note 48, 49, 12)
            if note in (48, 49, 12):
                self.shift_active = True
                return desc, "SHIFT Button Active"

            # Play / Pause Buttons (Left: Note 0, 11, 36 | Right: Note 1, 12, 37)
            if note in (0, 1, 11, 36, 37, 50, 51):
                send_player_ipc("toggle")
                action = "Play / Pause (Toggle) ▶⏸"
                return desc, action

            # Cue Buttons (Left: Note 2, 13, 38 | Right: Note 3, 14, 39)
            if note in (2, 3, 13, 38, 39, 52, 53):
                send_player_ipc("seek_to", position=0.0)
                action = "CUE (Seek to 0:00) ⏹"
                return desc, action

            # Cup Buttons (Cue-Play)
            if note in (4, 5, 40, 41):
                send_player_ipc("seek_to", position=0.0)
                send_player_ipc("play")
                action = "CUP (Play from Start) ⏯"
                return desc, action

            # Sync Buttons (Left: Note 6, 42 | Right: Note 7, 43)
            if note in (6, 7, 42, 43):
                if self.shift_active or note in (7, 43):
                    send_player_ipc("shuffle")
                    action = "Shuffle Mode Toggled 🔀"
                else:
                    send_player_ipc("reset_pitch")
                    action = "Sync (Pitch Reset to 0%) 🎚"
                return desc, action

            # Pitch Bend / Tempo Buttons (+ / -)
            # Left Deck Pitch + / - : Note 8, 9
            # Right Deck Pitch + / - : Note 10, 11
            if note in (8, 10, 44, 46):
                send_player_ipc("pitch_up", step=1)
                action = "Pitch Nudge Up (+1%) 🔼"
                return desc, action
            if note in (9, 11, 45, 47):
                send_player_ipc("pitch_down", step=1)
                action = "Pitch Nudge Down (-1%) 🔽"
                return desc, action

            # Browse Push Encoder (Note 14, 15, 60)
            if note in (14, 15, 60, 61):
                send_player_ipc("toggle")
                action = "Browse Encoder Push (Play/Pause)"
                return desc, action

            # Loop In / Loop Out Buttons (Note 16, 17, 62, 63)
            if note in (16, 62):
                send_player_ipc("seek", seconds=-10.0)
                action = "Loop In / Quick Seek -10s ⏪"
                return desc, action
            if note in (17, 63):
                send_player_ipc("seek", seconds=10.0)
                action = "Loop Out / Quick Seek +10s ⏩"
                return desc, action

            # Hotcue Buttons 1, 2, 3, 4 (Left Deck: Note 20..23 | Right Deck: Note 24..27)
            if note in (20, 24, 64, 68):
                send_player_ipc("seek_to", position=0.0)
                action = "Hotcue 1 (Jump to 0% Start)"
                return desc, action
            elif note in (21, 25, 65, 69):
                st = get_player_status()
                dur = float(st.get("duration_sec", 0)) if st else 0.0
                send_player_ipc("seek_to", position=dur * 0.25)
                action = "Hotcue 2 (Jump to 25% Mix Position)"
                return desc, action
            elif note in (22, 26, 66, 70):
                st = get_player_status()
                dur = float(st.get("duration_sec", 0)) if st else 0.0
                send_player_ipc("seek_to", position=dur * 0.50)
                action = "Hotcue 3 (Jump to 50% Mid-Point)"
                return desc, action
            elif note in (23, 27, 67, 71):
                st = get_player_status()
                dur = float(st.get("duration_sec", 0)) if st else 0.0
                send_player_ipc("seek_to", position=dur * 0.75)
                action = "Hotcue 4 (Jump to 75% Mix Position)"
                return desc, action

            # Headphone Cue Buttons (Channel Mute) (Note 28..31, 72..75)
            if note in (28, 29, 30, 31, 72, 73, 74, 75):
                send_player_ipc("mute")
                action = "Headphone Cue (Mute / Unmute) 🔇"
                return desc, action

            # Loop Recorder REC Button (Note 32, 76)
            if note in (32, 76):
                send_player_ipc("toggle_record")
                action = "Loop Recorder REC (Toggle Recording) 🔴"
                return desc, action

            # Loop Recorder PLAY Button (Note 33, 77)
            if note in (33, 77):
                send_player_ipc("toggle")
                action = "Loop Recorder PLAY (Play/Pause)"
                return desc, action

            return desc, f"Unhandled Note {note}"

        return f"Raw MIDI: {status:02X} {data1:02X} {data2:02X}", "Ignored"

    def run_rawmidi_stream(self, monitor_mode: bool = False):
        """
        Read directly from ALSA rawmidi device (/dev/snd/midiC0D0).
        """
        if not self.rawmidi_dev or not os.path.exists(self.rawmidi_dev):
            log(f"Rawmidi device {self.rawmidi_dev} not found. Attempting amidi fallback...")
            return self.run_amidi_stream(monitor_mode=monitor_mode)

        try:
            fd = os.open(self.rawmidi_dev, os.O_RDONLY | os.O_NONBLOCK)
        except Exception as e:
            log(f"Failed to open {self.rawmidi_dev}: {e}. Falling back to amidi...")
            return self.run_amidi_stream(monitor_mode=monitor_mode)

        log(f"Connected to Traktor S4 on {self.rawmidi_dev} (hw:{self.port})")
        self.update_state("running", "Connected via ALSA Rawmidi")
        buffer = bytearray()

        try:
            while self.running:
                r, _, _ = select.select([fd], [], [], 0.1)
                if not r:
                    continue
                try:
                    chunk = os.read(fd, 256)
                except BlockingIOError:
                    continue
                except OSError as e:
                    log(f"Read error: {e}")
                    break

                if not chunk:
                    time.sleep(0.01)
                    continue

                buffer.extend(chunk)

                # Process 3-byte standard MIDI messages
                while len(buffer) >= 3:
                    # Sync to status byte (>= 0x80)
                    while buffer and buffer[0] < 0x80:
                        buffer.pop(0)

                    if len(buffer) < 3:
                        break

                    status = buffer[0]
                    # Filter realtime messages
                    if status >= 0xF8:
                        buffer.pop(0)
                        continue

                    data1 = buffer[1]
                    data2 = buffer[2]
                    buffer = buffer[3:]

                    desc, action = self.process_midi_event(status, data1, data2)
                    self.update_state("running", f"{desc} -> {action}")
                    if monitor_mode:
                        print(f"  {CYAN}[MIDI]{NC} {WHITE}{desc:<40}{NC} ➔ {BOLD}{GREEN}{action}{NC}")
        finally:
            try:
                os.close(fd)
            except Exception:
                pass

    def run_amidi_stream(self, monitor_mode: bool = False):
        """
        Fallback MIDI stream reader using 'amidi -p <port> --dump'.
        """
        cmd = ["amidi", "-p", self.port, "--dump"]
        log(f"Starting amidi process: {' '.join(cmd)}")
        self.update_state("running", f"Listening via amidi on {self.port}")

        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)

        try:
            for line in iter(proc.stdout.readline, ""):
                if not self.running:
                    break
                line = line.strip()
                if not line:
                    continue

                # Hex tokens (e.g. "90 3C 7F" or "B0 0E 40")
                tokens = line.split()
                i = 0
                while i + 2 < len(tokens):
                    try:
                        s_byte = int(tokens[i], 16)
                        d1_byte = int(tokens[i + 1], 16)
                        d2_byte = int(tokens[i + 2], 16)
                        desc, action = self.process_midi_event(s_byte, d1_byte, d2_byte)
                        self.update_state("running", f"{desc} -> {action}")
                        if monitor_mode:
                            print(f"  {CYAN}[MIDI]{NC} {WHITE}{desc:<40}{NC} ➔ {BOLD}{GREEN}{action}{NC}")
                        i += 3
                    except ValueError:
                        i += 1
        except Exception as e:
            log(f"amidi process error: {e}")
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=1.0)
            except Exception:
                proc.kill()

    def start_loop(self, monitor_mode: bool = False):
        self.running = True
        log("Traktor S4 MIDI listener daemon started.")
        if monitor_mode:
            print(f"\n{BOLD}{MAGENTA}========================================================================{NC}")
            print(f"{BOLD}{WHITE}   🎛️  TRAKTOR KONTROL S4 HARDWARE MIDI LIVE MONITOR / TEST CONSOLE{NC}")
            print(f"{BOLD}{MAGENTA}========================================================================{NC}")
            print(f"  Hardware Port   : {BOLD}{CYAN}{self.port}{NC}")
            print(f"  ALSA Device     : {BOLD}{CYAN}{self.rawmidi_dev or 'amidi stream'}{NC}")
            print(f"  Audio Player IPC: {BOLD}{GREEN if is_player_running() else YELLOW}{'Connected' if is_player_running() else 'Waiting for player'}{NC}")
            print(f"  MIDI Mode Hint  : Press {BOLD}{YELLOW}SHIFT + BROWSE{NC} (MK1) or {BOLD}{YELLOW}SHIFT + PREVIEW{NC} (MK2) on S4")
            print(f"  Exit Monitor    : Press {BOLD}Ctrl+C{NC}\n")
            print(f"  {DIM}Listening for incoming pitch faders, buttons, knobs, encoders...{NC}\n")

        # Prioritize ALSA rawmidi character device for ultra-low latency, fallback to amidi
        if self.rawmidi_dev and os.path.exists(self.rawmidi_dev):
            self.run_rawmidi_stream(monitor_mode=monitor_mode)
        else:
            self.run_amidi_stream(monitor_mode=monitor_mode)


# =============================================================================
# DAEMON LIFECYCLE MANAGEMENT
# =============================================================================

def is_daemon_running() -> Tuple[bool, Optional[int]]:
    if PID_FILE.is_file():
        try:
            pid = int(PID_FILE.read_text().strip())
            os.kill(pid, 0)
            return True, pid
        except (OSError, ValueError):
            PID_FILE.unlink(missing_ok=True)
    return False, None


def start_daemon(port: str = DEFAULT_PORT):
    running, pid = is_daemon_running()
    if running:
        print(f"{YELLOW}Traktor S4 MIDI service is already running (PID: {pid}).{NC}")
        return

    # Check device presence
    detected, detected_port, _ = detect_traktor_s4_port()
    if not detected and not os.path.exists("/dev/snd/midiC0D0"):
        print(f"{YELLOW}Warning: Traktor Kontrol S4 hardware not currently detected on {port}. Starting daemon anyway in standby mode.{NC}")

    cmd = [sys.executable, str(Path(__file__).resolve()), "--daemon", "--port", port]
    with open(LOG_FILE, "a", encoding="utf-8") as out:
        p = subprocess.Popen(cmd, stdout=out, stderr=out, start_new_session=True)
    
    PID_FILE.write_text(str(p.pid), encoding="utf-8")
    FIRST_SEEN_FLAG.touch(exist_ok=True)
    print(f"{GREEN}✓ Traktor Kontrol S4 MIDI Control Service successfully started (PID: {p.pid}, Port: {port}).{NC}")


def stop_daemon():
    running, pid = is_daemon_running()
    if not running:
        print(f"{DIM}Traktor S4 MIDI service is not currently running.{NC}")
        PID_FILE.unlink(missing_ok=True)
        return

    try:
        os.kill(pid, signal.SIGTERM)
        for _ in range(20):
            time.sleep(0.1)
            try:
                os.kill(pid, 0)
            except OSError:
                break
        else:
            os.kill(pid, signal.SIGKILL)
        print(f"{GREEN}✓ Traktor Kontrol S4 MIDI Control Service stopped (PID: {pid}).{NC}")
    except OSError as e:
        print(f"{RED}Error stopping MIDI service: {e}{NC}")
    finally:
        PID_FILE.unlink(missing_ok=True)
        try:
            STATE_FILE.write_text(json.dumps({"status": "stopped", "pid": 0}), encoding="utf-8")
        except Exception:
            pass


def print_status():
    detected, port, details = detect_traktor_s4_port()
    daemon_run, pid = is_daemon_running()
    player_run = is_player_running()

    print(f"\n{BOLD}{MAGENTA}=== TRAKTOR KONTROL S4 MIDI HARDWARE STATUS ==={NC}\n")
    print(f"  Device Name          : {BOLD}{WHITE}{DEFAULT_DEVICE_NAME}{NC}")
    print(f"  Hardware Port        : {BOLD}{CYAN}{port}{NC} {DIM}(ALSA Rawmidi: /dev/snd/midiC0D0){NC}")
    if detected:
        print(f"  Hardware Connection  : {BOLD}{GREEN}✓ Detected & Connected{NC} {DIM}({details}){NC}")
    else:
        print(f"  Hardware Connection  : {BOLD}{YELLOW}⚠ Not Detected / Unplugged{NC}")

    if daemon_run:
        print(f"  MIDI Service Daemon  : {BOLD}{GREEN}✓ Active & Running{NC} {DIM}(PID: {pid}){NC}")
    else:
        print(f"  MIDI Service Daemon  : {BOLD}{RED}✗ Disabled / Stopped{NC}")

    if player_run:
        st = get_player_status()
        p_pct = st.get("pitch_percent", 0) if st else 0
        state = st.get("state", "unknown") if st else "unknown"
        print(f"  MP Audio Player      : {BOLD}{GREEN}✓ Connected{NC} {DIM}(State: {state}, Pitch: {p_pct:+d}%){NC}")
    else:
        print(f"  MP Audio Player      : {DIM}Offline / Waiting for launch{NC}")

    print(f"  Supported in v0.4.0  : {BOLD}{GREEN}Traktor Kontrol S4 Exclusively{NC}\n")


def print_user_guide():
    guide_path = Path(__file__).resolve().parent.parent / "docs" / "TRAKTOR_KONTROL_S4_USER_GUIDE.md"
    if guide_path.is_file():
        try:
            content = guide_path.read_text(encoding="utf-8")
            print(content)
            return
        except Exception:
            pass

    # Fallback built-in guide
    print(f"""
{BOLD}{MAGENTA}========================================================================{NC}
{BOLD}{WHITE}   🎛️  TRAKTOR KONTROL S4 GETTING STARTED GUIDE (v0.4.0){NC}
{BOLD}{MAGENTA}========================================================================{NC}

1. SWITCHING TO MIDI MODE ON THE S4:
   • Traktor Kontrol S4 MK1: Hold {BOLD}{YELLOW}SHIFT{NC} and press {BOLD}{YELLOW}BROWSE{NC} button.
   • Traktor Kontrol S4 MK2: Hold {BOLD}{YELLOW}SHIFT{NC} and press {BOLD}{YELLOW}PREVIEW{NC} button.
   • Confirmation: The two Loop Size Displays on the S4 will read {BOLD}{GREEN}ON{NC}.

2. HARDWARE ALSA PORT:
   • The Traktor Kontrol S4 connects via ALSA hardware port {BOLD}{CYAN}hw:0,0{NC} (or /dev/snd/midiC0D0).
   • To verify in terminal: run '{BOLD}amidi -l{NC}'.

3. PITCH CONTROLS (LEFT & RIGHT DECKS):
   • Moving either Tempo/Pitch Fader adjusts the MP Audio Player DJ Pitch in real-time.
   • Range: {BOLD}-20% to +20%{NC} with rock-solid deadzone center snap at 0%.
   • Pitch Bend [+] / [-] buttons: Micro-nudge pitch up or down by 1%.
   • SYNC button: Instant Pitch Reset to 0%.

4. ESSENTIAL BUTTON MAPPINGS:
   • {BOLD}PLAY ▶{NC}               : Toggle Play / Pause in MP Audio Player
   • {BOLD}CUE ⏹{NC}                : Stop / Jump to start (0:00)
   • {BOLD}BROWSE Encoder{NC}        : Turn to jump tracks (Next/Prev); Push to Play
   • {BOLD}LOOP IN / OUT{NC}         : Quick Seek -10s / +10s
   • {BOLD}HOTCUES 1..4{NC}          : Instant Jump to 0%, 25%, 50%, 75% of mix
   • {BOLD}VOLUME FADERS{NC}         : Adjust Master / Track Volume (0% - 100%)
   • {BOLD}HEADPHONE CUE{NC}         : Instant Mute / Unmute
   • {BOLD}REC (Loop Recorder){NC}   : Toggle Live DJ Mix Recording

5. CONTROLLING FROM MP MIX ARCHIVE MANAGER:
   • Use Option 18 in the Main Menu to Enable or Disable MIDI Support.
   • Monitor live MIDI messages in real-time with '{BOLD}python3 scripts/traktor_s4_midi.py --monitor{NC}'.
""")


def main():
    parser = argparse.ArgumentParser(description="Traktor Kontrol S4 MIDI Controller Daemon for MP Mix Manager")
    parser.add_argument("--daemon", action="store_true", help="Run MIDI event listener loop")
    parser.add_argument("--start", action="store_true", help="Start background daemon")
    parser.add_argument("--stop", action="store_true", help="Stop background daemon")
    parser.add_argument("--restart", action="store_true", help="Restart background daemon")
    parser.add_argument("--status", action="store_true", help="Show hardware and service status")
    parser.add_argument("--monitor", action="store_true", help="Interactive live test and packet monitor")
    parser.add_argument("--guide", action="store_true", help="Print Traktor Kontrol S4 User Guide")
    parser.add_argument("--port", type=str, default=DEFAULT_PORT, help="ALSA MIDI Port (default: hw:0,0)")

    args = parser.parse_args()

    if args.start:
        start_daemon(port=args.port)
        return
    if args.stop:
        stop_daemon()
        return
    if args.restart:
        stop_daemon()
        time.sleep(0.5)
        start_daemon(port=args.port)
        return
    if args.status:
        print_status()
        return
    if args.guide:
        print_user_guide()
        return
    if args.monitor:
        ctrl = TraktorS4MidiController(port=args.port)
        try:
            ctrl.start_loop(monitor_mode=True)
        except KeyboardInterrupt:
            print(f"\n{GREEN}Exited monitor mode.{NC}")
        return

    if args.daemon:
        PID_FILE.write_text(str(os.getpid()), encoding="utf-8")
        ctrl = TraktorS4MidiController(port=args.port)

        def _sig_handler(sig, frame):
            ctrl.running = False
            PID_FILE.unlink(missing_ok=True)
            sys.exit(0)

        signal.signal(signal.SIGTERM, _sig_handler)
        signal.signal(signal.SIGINT, _sig_handler)

        try:
            ctrl.start_loop(monitor_mode=False)
        finally:
            PID_FILE.unlink(missing_ok=True)
        return

    # Default action if no args
    print_status()

if __name__ == "__main__":
    main()
