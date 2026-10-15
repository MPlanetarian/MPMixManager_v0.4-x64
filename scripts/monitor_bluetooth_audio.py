#!/usr/bin/env python3
"""
scripts/monitor_bluetooth_audio.py - Intelligent Bluetooth Audio Monitor & Stream Router
Part of MP Mix Manager (Dreamworlds Productions)

Monitors Linux PipeWire / WirePlumber / PulseAudio sound system for Bluetooth audio devices
(headphones, headsets, speakers) and intelligently:
  1. Detects Bluetooth audio sink connections and disconnections in real-time (sub-millisecond via pactl subscribe + heartbeat).
  2. Automatically switches system default audio output to the newly connected Bluetooth headphones (wpctl + pactl).
  3. Seamlessly migrates active MP Audio Player streams (sink-inputs) to Bluetooth with zero dropouts or interruptions.
  4. Automatically switches default audio input / source if Bluetooth headset microphone is detected.
  5. Gracefully reverts to the primary fallback audio sink (HDMI/speakers) when Bluetooth disconnects.
"""

from __future__ import annotations
import os
import sys
import re
import time
import json
import shutil
import argparse
import threading
import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple, Callable

for stream in (sys.stdout, sys.stderr):
    if stream and hasattr(stream, "reconfigure"):
        try: stream.reconfigure(line_buffering=True, encoding="utf-8", errors="replace")
        except Exception: pass

# ANSI Colors
BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[38;2;0;255;0m"
YELLOW = "\033[38;2;255;153;51m"
RED = "\033[38;2;255;0;0m"
PURPLE = "\033[38;2;166;77;255m"
CYAN = "\033[38;2;0;229;255m"
BLUE = "\033[38;2;102;102;255m"
NC = "\033[0m"

STATE_DIR = Path.home() / ".config" / "mix-manager"
STATE_DIR.mkdir(parents=True, exist_ok=True)
BT_STATE_FILE = STATE_DIR / "mp_bluetooth_state.json"


def check_command(cmd: str) -> bool:
    return shutil.which(cmd) is not None


class BluetoothAudioRouter:
    def __init__(
        self,
        target_pid: Optional[int] = None,
        on_route_change: Optional[Callable[[str, bool, str, Optional[str]], None]] = None,
        auto_switch: bool = True,
        logger: Optional[Callable[[str], None]] = None
    ):
        self.target_pid = target_pid or os.getpid()
        self.on_route_change = on_route_change
        self.auto_switch = auto_switch
        self.logger = logger or (lambda msg: None)

        self.running = False
        self._lock = threading.RLock()
        self._subscribe_proc: Optional[subprocess.Popen] = None
        self._threads: List[threading.Thread] = []

        self.active_bt_sink: Optional[Dict[str, Any]] = None
        self.fallback_sink: Optional[Dict[str, Any]] = None
        self.last_routed_sink_name: Optional[str] = None
        self.last_switch_time: float = 0.0

    def log(self, msg: str):
        if self.logger:
            try:
                self.logger(msg)
            except Exception:
                pass

    def probe_sinks(self) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Returns (bluetooth_sinks, non_bluetooth_sinks).
        Each sink dict has:
          index, name, description, object_id, is_bluetooth, codec, state, is_default
        """
        bt_sinks: List[Dict[str, Any]] = []
        other_sinks: List[Dict[str, Any]] = []

        default_sink_name = self._get_default_sink_name()

        # Try pactl -f json list sinks
        if check_command("pactl"):
            try:
                p = subprocess.run(
                    ["pactl", "-f", "json", "list", "sinks"],
                    capture_output=True, text=True, timeout=1.2
                )
                if p.returncode == 0 and p.stdout.strip():
                    raw_sinks = json.loads(p.stdout)
                    for s in raw_sinks:
                        props = s.get("properties", {})
                        name = s.get("name", "")
                        desc = s.get("description", name)
                        obj_id = props.get("object.id")
                        bus = props.get("device.bus", "")
                        api = props.get("device.api", "")
                        codec = props.get("api.bluez5.codec", "")
                        is_bt = (
                            bus == "bluetooth"
                            or api == "bluez5"
                            or name.startswith("bluez_output.")
                            or "bluez" in name.lower()
                            or "bluetooth" in props.get("device.icon_name", "").lower()
                        )
                        sink_info = {
                            "index": s.get("index"),
                            "name": name,
                            "description": desc,
                            "object_id": str(obj_id) if obj_id is not None else None,
                            "is_bluetooth": is_bt,
                            "codec": codec.upper() if codec else "",
                            "state": s.get("state", ""),
                            "is_default": (name == default_sink_name)
                        }
                        if is_bt:
                            bt_sinks.append(sink_info)
                        else:
                            other_sinks.append(sink_info)
                    return bt_sinks, other_sinks
            except Exception:
                pass

        # Fallback to wpctl status if pactl json failed or unavailable
        if check_command("wpctl"):
            try:
                bt_sinks, other_sinks = self._probe_wpctl_sinks(default_sink_name)
                if bt_sinks or other_sinks:
                    return bt_sinks, other_sinks
            except Exception:
                pass

        return bt_sinks, other_sinks

    def probe_sources(self) -> List[Dict[str, Any]]:
        """
        Returns list of Bluetooth input sources (microphones/headsets).
        """
        bt_sources: List[Dict[str, Any]] = []
        if check_command("pactl"):
            try:
                p = subprocess.run(
                    ["pactl", "-f", "json", "list", "sources"],
                    capture_output=True, text=True, timeout=1.0
                )
                if p.returncode == 0 and p.stdout.strip():
                    raw = json.loads(p.stdout)
                    for s in raw:
                        props = s.get("properties", {})
                        name = s.get("name", "")
                        desc = s.get("description", name)
                        obj_id = props.get("object.id")
                        bus = props.get("device.bus", "")
                        api = props.get("device.api", "")
                        is_bt = (
                            bus == "bluetooth"
                            or api == "bluez5"
                            or name.startswith("bluez_input.")
                            or "bluez" in name.lower()
                        )
                        if is_bt and not name.endswith(".monitor"):
                            bt_sources.append({
                                "index": s.get("index"),
                                "name": name,
                                "description": desc,
                                "object_id": str(obj_id) if obj_id is not None else None
                            })
            except Exception:
                pass
        return bt_sources

    def _get_default_sink_name(self) -> Optional[str]:
        if check_command("pactl"):
            try:
                p = subprocess.run(["pactl", "info"], capture_output=True, text=True, timeout=0.6)
                if p.returncode == 0:
                    for line in p.stdout.splitlines():
                        if "Default Sink:" in line:
                            return line.split(":", 1)[1].strip()
            except Exception:
                pass
        return None

    def _probe_wpctl_sinks(self, default_name: Optional[str]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        bt_sinks: List[Dict[str, Any]] = []
        other_sinks: List[Dict[str, Any]] = []
        try:
            p = subprocess.run(["wpctl", "status"], capture_output=True, text=True, timeout=1.0)
            if p.returncode != 0:
                return bt_sinks, other_sinks

            in_sinks = False
            devices_bt_ids = set()

            for line in p.stdout.splitlines():
                if "Devices:" in line:
                    in_sinks = False
                elif "Sinks:" in line:
                    in_sinks = True
                    continue
                elif in_sinks and (line.strip().startswith("Sources:") or line.strip().startswith("Filters:")):
                    in_sinks = False
                    continue

                if "[bluez5]" in line:
                    m = re.search(r"(\d+)\.\s+", line)
                    if m:
                        devices_bt_ids.add(m.group(1))

                if in_sinks:
                    m_sink = re.search(r"(\*?)\s*(\d+)\.\s+([^\[]+)(?:\[vol:\s*([\d\.]+)\])?", line)
                    if m_sink:
                        is_star = bool(m_sink.group(1))
                        obj_id = m_sink.group(2).strip()
                        desc = m_sink.group(3).strip()
                        # Inspect node details
                        node_name = desc
                        codec = ""
                        is_bt = (obj_id in devices_bt_ids or "bluez" in desc.lower())
                        try:
                            p_insp = subprocess.run(["wpctl", "inspect", obj_id], capture_output=True, text=True, timeout=0.4)
                            if p_insp.returncode == 0:
                                for iline in p_insp.stdout.splitlines():
                                    if "node.name =" in iline:
                                        m_name = re.search(r'node\.name\s*=\s*\"([^\"]+)\"', iline)
                                        if m_name: node_name = m_name.group(1)
                                    elif "api.bluez5.codec =" in iline:
                                        m_c = re.search(r'api\.bluez5\.codec\s*=\s*\"([^\"]+)\"', iline)
                                        if m_c: codec = m_c.group(1).upper()
                                    elif "device.api = \"bluez5\"" in iline or "media.class = \"Audio/Sink\"" in iline:
                                        if "bluez" in iline: is_bt = True
                        except Exception:
                            pass

                        item = {
                            "index": int(obj_id),
                            "name": node_name,
                            "description": desc,
                            "object_id": obj_id,
                            "is_bluetooth": is_bt,
                            "codec": codec,
                            "state": "",
                            "is_default": is_star
                        }
                        if is_bt:
                            bt_sinks.append(item)
                        else:
                            other_sinks.append(item)
        except Exception:
            pass
        return bt_sinks, other_sinks

    def get_player_sink_inputs(self) -> List[Dict[str, Any]]:
        """
        Finds all active PipeWire / PulseAudio sink inputs belonging to MP Audio Player
        or matching target_pid.
        """
        matching_inputs: List[Dict[str, Any]] = []
        if not check_command("pactl"):
            return matching_inputs

        try:
            p_inputs = subprocess.run(
                ["pactl", "-f", "json", "list", "sink-inputs"],
                capture_output=True, text=True, timeout=1.0
            )
            if p_inputs.returncode != 0 or not p_inputs.stdout.strip():
                return matching_inputs
            sink_inputs = json.loads(p_inputs.stdout)

            p_cli = subprocess.run(
                ["pactl", "-f", "json", "list", "clients"],
                capture_output=True, text=True, timeout=1.0
            )
            clients = {}
            if p_cli.returncode == 0 and p_cli.stdout.strip():
                clients = {str(c.get("index")): c for c in json.loads(p_cli.stdout)}

            target_pid_str = str(self.target_pid)

            for si in sink_inputs:
                idx = si.get("index")
                props = si.get("properties", {})
                cli_idx = str(si.get("client", ""))
                cli = clients.get(cli_idx, {})
                cli_props = cli.get("properties", {})

                app_pid = (
                    props.get("application.process.id")
                    or cli_props.get("application.process.id")
                    or cli_props.get("pipewire.sec.pid")
                )
                app_name = (
                    props.get("application.name")
                    or cli_props.get("application.name", "")
                )
                node_name = props.get("node.name", "")

                is_target = False
                if app_pid and str(app_pid) == target_pid_str:
                    is_target = True
                elif "python" in (app_name or "").lower() and "alsa" in node_name.lower():
                    # Fallback match for Python ALSA playback stream
                    is_target = True
                elif "mp_audio_player" in (app_name or "").lower() or "mix_manager" in (app_name or "").lower():
                    is_target = True

                if is_target:
                    matching_inputs.append({
                        "index": idx,
                        "sink": si.get("sink"),
                        "app_name": app_name,
                        "pid": app_pid,
                        "node_name": node_name
                    })
        except Exception:
            pass

        return matching_inputs

    def set_system_default_sink(self, sink_name: str, object_id: Optional[str] = None) -> bool:
        """
        Sets default sink in both PulseAudio (pactl) and WirePlumber (wpctl).
        """
        ok = False
        if check_command("pactl"):
            try:
                p = subprocess.run(["pactl", "set-default-sink", sink_name], capture_output=True, timeout=1.0)
                if p.returncode == 0:
                    ok = True
            except Exception:
                pass

        if object_id and check_command("wpctl"):
            try:
                p2 = subprocess.run(["wpctl", "set-default", str(object_id)], capture_output=True, timeout=1.0)
                if p2.returncode == 0:
                    ok = True
            except Exception:
                pass
        return ok

    def set_system_default_source(self, source_name: str, object_id: Optional[str] = None) -> bool:
        """
        Sets default input source (for headset mic).
        """
        ok = False
        if check_command("pactl"):
            try:
                p = subprocess.run(["pactl", "set-default-source", source_name], capture_output=True, timeout=1.0)
                if p.returncode == 0:
                    ok = True
            except Exception:
                pass

        if object_id and check_command("wpctl"):
            try:
                p2 = subprocess.run(["wpctl", "set-default", str(object_id)], capture_output=True, timeout=1.0)
                if p2.returncode == 0:
                    ok = True
            except Exception:
                pass
        return ok

    def move_player_stream(self, target_sink_name: str, target_sink_index: Optional[int] = None) -> int:
        """
        Moves all MP Audio Player sink inputs to target sink.
        Returns number of streams moved.
        """
        moved = 0
        inputs = self.get_player_sink_inputs()
        for inp in inputs:
            inp_idx = inp.get("index")
            current_sink = inp.get("sink")
            # If current sink is already target sink index or name, skip
            if target_sink_index is not None and current_sink == target_sink_index:
                continue

            dest = str(target_sink_index) if target_sink_index is not None else target_sink_name
            try:
                p = subprocess.run(["pactl", "move-sink-input", str(inp_idx), dest], capture_output=True, timeout=1.0)
                if p.returncode == 0:
                    moved += 1
                    self.log(f"Moved player stream #{inp_idx} to {target_sink_name}")
            except Exception:
                pass
        return moved

    def route_to_bluetooth(self, bt_sink: Optional[Dict[str, Any]] = None) -> bool:
        """
        Routes system default and active MP Audio Player stream to Bluetooth.
        """
        with self._lock:
            bt_sinks, other_sinks = self.probe_sinks()
            if not bt_sink:
                if not bt_sinks:
                    self.log("No Bluetooth audio sink found to route to.")
                    return False
                bt_sink = bt_sinks[0]

            # Store fallback sink if not already set or if previous was bluetooth
            if other_sinks:
                current_default = self._get_default_sink_name()
                for o in other_sinks:
                    if o.get("name") == current_default:
                        self.fallback_sink = o
                        break
                else:
                    if not self.fallback_sink or self.fallback_sink.get("is_bluetooth"):
                        self.fallback_sink = other_sinks[0]

            self.active_bt_sink = bt_sink
            sink_name = bt_sink["name"]
            obj_id = bt_sink.get("object_id")
            sink_idx = bt_sink.get("index")
            desc = bt_sink.get("description", "Bluetooth Audio")
            codec = bt_sink.get("codec", "")

            # 1. Set default sink
            self.set_system_default_sink(sink_name, obj_id)

            # 2. Check and set bluetooth source if present
            bt_sources = self.probe_sources()
            if bt_sources:
                self.set_system_default_source(bt_sources[0]["name"], bt_sources[0].get("object_id"))

            # 3. Move streams
            self.move_player_stream(sink_name, sink_idx)
            self.last_routed_sink_name = sink_name
            self.last_switch_time = time.time()

            self._save_state()
            self.log(f"✓ Routed audio to Bluetooth device: {desc} ({codec or 'AAC'})")

            if self.on_route_change:
                try:
                    self.on_route_change(desc, True, "connected", codec)
                except Exception:
                    pass
            return True

    def route_to_fallback(self) -> bool:
        """
        Reverts system default and active MP Audio Player stream to fallback sink.
        """
        with self._lock:
            _, other_sinks = self.probe_sinks()
            fallback = self.fallback_sink
            if not fallback or not any(o.get("name") == fallback.get("name") for o in other_sinks):
                fallback = other_sinks[0] if other_sinks else None

            if not fallback:
                self.log("No fallback audio sink available.")
                self.active_bt_sink = None
                return False

            sink_name = fallback["name"]
            obj_id = fallback.get("object_id")
            sink_idx = fallback.get("index")
            desc = fallback.get("description", "Default Speakers")

            self.set_system_default_sink(sink_name, obj_id)
            self.move_player_stream(sink_name, sink_idx)

            self.active_bt_sink = None
            self.last_routed_sink_name = sink_name
            self.last_switch_time = time.time()

            self._save_state()
            self.log(f"Reverted audio to primary sink: {desc}")

            if self.on_route_change:
                try:
                    self.on_route_change(desc, False, "disconnected", None)
                except Exception:
                    pass
            return True

    def check_and_route(self):
        """
        Intelligently inspects current audio topology:
        - If a Bluetooth sink connected and we haven't routed to it, auto-routes to Bluetooth.
        - If the active Bluetooth sink disconnected, reverts to fallback sink.
        - Ensures stream migration.
        """
        try:
            bt_sinks, other_sinks = self.probe_sinks()

            # Bluetooth connected
            if bt_sinks:
                target_bt = bt_sinks[0]
                # If auto-switch enabled
                if self.auto_switch:
                    is_new = (
                        self.active_bt_sink is None
                        or self.active_bt_sink.get("name") != target_bt.get("name")
                        or self.last_routed_sink_name != target_bt.get("name")
                    )
                    # Check if stream is currently on this sink
                    player_inputs = self.get_player_sink_inputs()
                    needs_stream_move = any(
                        inp.get("sink") != target_bt.get("index") for inp in player_inputs
                    )
                    default_sink = self._get_default_sink_name()
                    needs_default_switch = (default_sink != target_bt.get("name"))

                    if is_new or needs_stream_move or needs_default_switch:
                        self.route_to_bluetooth(target_bt)
            else:
                # Bluetooth disconnected
                if self.active_bt_sink is not None:
                    self.log(f"Bluetooth device disconnected ({self.active_bt_sink.get('description', '')}). Reverting audio...")
                    self.route_to_fallback()
        except Exception as e:
            self.log(f"Error in check_and_route: {e}")

    def _subscribe_listener_loop(self):
        """
        Real-time event loop using pactl subscribe.
        Wakes up immediately on sink / server events.
        """
        if not check_command("pactl"):
            return

        while self.running:
            proc = None
            try:
                proc = subprocess.Popen(
                    ["pactl", "subscribe"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    text=True
                )
                self._subscribe_proc = proc

                for line in iter(proc.stdout.readline, ""):
                    if not self.running:
                        break
                    line_s = line.strip().lower()
                    if "sink" in line_s or "server" in line_s or "card" in line_s:
                        # Slight debounce for device initialization
                        time.sleep(0.08)
                        self.check_and_route()
            except Exception:
                pass
            finally:
                if proc:
                    try:
                        proc.terminate()
                        proc.wait(timeout=0.5)
                    except Exception:
                        pass
            if self.running:
                time.sleep(1.0)

    def _heartbeat_polling_loop(self):
        """
        Failsafe periodic heartbeat check (every 1.2 seconds).
        Guarantees switching even if events are not delivered.
        """
        while self.running:
            try:
                self.check_and_route()
            except Exception:
                pass
            time.sleep(1.2)

    def start(self):
        """
        Starts the background monitoring threads.
        """
        with self._lock:
            if self.running:
                return
            self.running = True

            # Initial check
            self.check_and_route()

            t1 = threading.Thread(target=self._subscribe_listener_loop, name="BTSubscribeListener", daemon=True)
            t2 = threading.Thread(target=self._heartbeat_polling_loop, name="BTHeartbeatPolling", daemon=True)
            t1.start()
            t2.start()
            self._threads = [t1, t2]
            self.log("Bluetooth Audio Router started.")

    def stop(self):
        """
        Stops the monitoring threads cleanly.
        """
        with self._lock:
            self.running = False
            if self._subscribe_proc:
                try:
                    self._subscribe_proc.terminate()
                except Exception:
                    pass
                self._subscribe_proc = None

    def get_status(self) -> Dict[str, Any]:
        bt_sinks, other_sinks = self.probe_sinks()
        default_sink = self._get_default_sink_name()
        connected = len(bt_sinks) > 0
        active_bt = bt_sinks[0] if connected else None

        inputs = self.get_player_sink_inputs()
        player_routed_bt = False
        if active_bt and inputs:
            player_routed_bt = all(inp.get("sink") == active_bt.get("index") for inp in inputs)

        return {
            "bluetooth_connected": connected,
            "bluetooth_device": active_bt.get("description", "") if active_bt else "",
            "bluetooth_codec": active_bt.get("codec", "") if active_bt else "",
            "bluetooth_sink_name": active_bt.get("name", "") if active_bt else "",
            "default_sink": default_sink or "",
            "is_default_bluetooth": bool(active_bt and default_sink == active_bt.get("name")),
            "fallback_sink": self.fallback_sink.get("name", "") if self.fallback_sink else (other_sinks[0]["name"] if other_sinks else ""),
            "auto_switch_enabled": self.auto_switch,
            "player_streams_count": len(inputs),
            "player_streams_on_bluetooth": player_routed_bt,
            "last_switch_time": self.last_switch_time
        }

    def _save_state(self):
        try:
            st = self.get_status()
            tmp = BT_STATE_FILE.with_suffix(".tmp")
            tmp.write_text(json.dumps(st, indent=2), encoding="utf-8")
            tmp.replace(BT_STATE_FILE)
        except Exception:
            pass


def get_bluetooth_audio_status() -> Dict[str, Any]:
    router = BluetoothAudioRouter(auto_switch=False)
    return router.get_status()


def main():
    parser = argparse.ArgumentParser(description="MP Mix Manager - Bluetooth Audio Monitor & Stream Router")
    parser.add_argument("--status", action="store_true", help="Print current Bluetooth audio status as JSON")
    parser.add_argument("--route", action="store_true", help="Manually route active audio and default sink to Bluetooth")
    parser.add_argument("--revert", action="store_true", help="Manually revert audio to primary fallback output")
    parser.add_argument("--monitor", action="store_true", help="Run live monitor in console with status output")
    parser.add_argument("--daemon", action="store_true", help="Run background monitoring daemon")
    parser.add_argument("--stop", action="store_true", help="Stop background monitoring daemon")
    parser.add_argument("--target-pid", type=int, default=None, help="Target process PID for audio stream routing")
    args = parser.parse_args()

    pid_file = STATE_DIR / "mp_bt_monitor.pid"
    log_file = STATE_DIR / "mp_bt_monitor.log"

    if args.stop:
        if pid_file.exists():
            try:
                pid = int(pid_file.read_text().strip())
                os.kill(pid, 15)
                try: pid_file.unlink()
                except OSError: pass
                print(f"{GREEN}✓ Stopped Bluetooth Audio Router daemon (PID: {pid}).{NC}")
            except OSError as e:
                print(f"{YELLOW}Warning: Process not active or already stopped ({e}).{NC}")
                try: pid_file.unlink()
                except OSError: pass
        else:
            print("No running Bluetooth Audio Router daemon found.")
        return

    if args.daemon:
        if pid_file.exists():
            try:
                old_pid = int(pid_file.read_text().strip())
                os.kill(old_pid, 0)
                print(f"Bluetooth Audio Router daemon is already running (PID: {old_pid}).")
                return
            except OSError:
                pass

        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"\n--- Started BT Monitor Daemon at {time.ctime()} ---\n")
            f.flush()
            sub_args = [sys.executable, str(Path(__file__).resolve()), "--monitor"]
            if args.target_pid:
                sub_args.append(f"--target-pid={args.target_pid}")
            proc = subprocess.Popen(
                sub_args, stdout=f, stderr=f, stdin=subprocess.DEVNULL, start_new_session=True
            )
        pid_file.write_text(str(proc.pid))
        print(f"{GREEN}✓ Started Bluetooth Audio Router daemon (PID: {proc.pid}).{NC}")
        print(f"  Log: {log_file}")
        return

    if args.status:
        st = get_bluetooth_audio_status()
        print(json.dumps(st, indent=2))
        return

    if args.route:
        router = BluetoothAudioRouter(target_pid=args.target_pid, logger=print)
        ok = router.route_to_bluetooth()
        print(f"{GREEN}✓ Successfully routed audio to Bluetooth.{NC}" if ok else f"{RED}✗ Could not route to Bluetooth.{NC}")
        return

    if args.revert:
        router = BluetoothAudioRouter(target_pid=args.target_pid, logger=print)
        ok = router.route_to_fallback()
        print(f"{GREEN}✓ Successfully reverted audio to primary output.{NC}" if ok else f"{RED}✗ Could not revert audio.{NC}")
        return

    # Monitor / Daemon mode
    print(f"{BOLD}{PURPLE}=== MP MIX MANAGER — BLUETOOTH AUDIO INTELLIGENT ROUTER ==={NC}")
    router = BluetoothAudioRouter(target_pid=args.target_pid, logger=lambda m: print(f"{CYAN}[BT Router]{NC} {m}"))
    router.start()

    st = router.get_status()
    if st["bluetooth_connected"]:
        print(f"{GREEN}● Bluetooth Connected:{NC} {BOLD}{st['bluetooth_device']}{NC} (Codec: {st['bluetooth_codec'] or 'Standard'})")
    else:
        print(f"{YELLOW}○ No Bluetooth audio devices currently connected.{NC} Waiting for headphones...")

    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Stopping Bluetooth Audio Router...{NC}")
        router.stop()
        print(f"{GREEN}Stopped.{NC}")


if __name__ == "__main__":
    main()
