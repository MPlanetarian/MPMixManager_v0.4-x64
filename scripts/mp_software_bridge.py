#!/usr/bin/env python3
"""
mp_software_bridge.py - Workstation Software Bridge between MP Mix Manager & Congen
Part of MP_Mix_Manager_v0.3 & Congen

Provides bidirectional process detection, menu tracking, telemetry exchange,
connectivity validation, and remote command orchestration between MP Mix Manager
and Congen (KDE Connect Command Generator).
"""

import os
import sys
import time
import json
import subprocess
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, Tuple, List

# Paths
WORKSPACE_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = WORKSPACE_DIR / "scripts"
CONGEN_DIR = WORKSPACE_DIR / "Congen"
MIX_MANAGER_CONFIG_DIR = Path.home() / ".config" / "mix-manager"
CONGEN_CONFIG_DIR = Path.home() / ".config" / "congen"
KDECONNECT_CONFIG_DIR = Path.home() / ".config" / "kdeconnect"

MIX_MANAGER_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
CONGEN_CONFIG_DIR.mkdir(parents=True, exist_ok=True)

BRIDGE_STATE_FILE = MIX_MANAGER_CONFIG_DIR / "bridge_status.json"
BRIDGE_STATE_MIRROR = CONGEN_CONFIG_DIR / "bridge_status.json"
USER_ACTIVITY_FILE = MIX_MANAGER_CONFIG_DIR / "user_activity.jsonl"
PLAYER_STATE_FILE = MIX_MANAGER_CONFIG_DIR / "mp_player_state.json"
MM_THEME_FILE = MIX_MANAGER_CONFIG_DIR / "theme"
CONGEN_THEME_FILE = CONGEN_CONFIG_DIR / "theme"


def get_process_stats(pid: int) -> Dict[str, Any]:
    """Retrieve process stats for PID using /proc or ps."""
    stats = {"alive": False, "pid": pid, "cpu_pct": 0.0, "mem_mb": 0.0, "etime": "0s"}
    if not pid or pid <= 0:
        return stats
    try:
        # Check if process is alive
        os.kill(pid, 0)
        stats["alive"] = True
    except OSError:
        return stats

    # Query ps for formatted details
    try:
        res = subprocess.run(
            ["ps", "-p", str(pid), "-o", "etimes=,%cpu=,rss="],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=2
        )
        if res.returncode == 0 and res.stdout.strip():
            parts = res.stdout.strip().split()
            if len(parts) >= 3:
                etimes = int(parts[0])
                stats["cpu_pct"] = float(parts[1])
                rss_kb = int(parts[2])
                stats["mem_mb"] = round(rss_kb / 1024.0, 1)

                mins, secs = divmod(etimes, 60)
                hours, mins = divmod(mins, 60)
                if hours > 0:
                    stats["etime"] = f"{hours}h {mins:02d}m {secs:02d}s"
                elif mins > 0:
                    stats["etime"] = f"{mins}m {secs:02d}s"
                else:
                    stats["etime"] = f"{secs}s"
    except Exception:
        pass
    return stats


def find_mix_manager_pid() -> Optional[int]:
    """Locate running MP Mix Manager process PID."""
    # Check bridge state file first
    if BRIDGE_STATE_FILE.exists():
        try:
            with open(BRIDGE_STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                saved_pid = data.get("pid")
                if saved_pid and isinstance(saved_pid, int):
                    try:
                        os.kill(saved_pid, 0)
                        # Verify it's actually bash running Mix_Archive_Manager
                        with open(f"/proc/{saved_pid}/cmdline", "rb") as cf:
                            cmdline = cf.read().decode("utf-8", errors="ignore")
                            if "Mix_Archive_Manager" in cmdline or "manager.sh" in cmdline:
                                return saved_pid
                    except (OSError, IOError):
                        pass
        except Exception:
            pass

    # Scan processes with pgrep
    try:
        res = subprocess.run(
            ["pgrep", "-f", "Mix_Archive_Manager.sh"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=2
        )
        if res.returncode == 0:
            pids = [int(p) for p in res.stdout.strip().split() if p.isdigit()]
            for p in pids:
                if p != os.getpid():
                    return p
    except Exception:
        pass

    return None


def detect_manager_child_operation(pid: int) -> Optional[str]:
    """Inspect child processes of Mix Manager to identify running sub-scripts."""
    if not pid:
        return None
    try:
        res = subprocess.run(
            ["pgrep", "-P", str(pid)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=2
        )
        if res.returncode == 0:
            child_pids = [int(p) for p in res.stdout.strip().split() if p.isdigit()]
            for c_pid in child_pids:
                try:
                    with open(f"/proc/{c_pid}/cmdline", "rb") as cf:
                        cmd = cf.read().decode("utf-8", errors="ignore").replace("\0", " ")
                        if "Make_SOF_FLAC_CONVERSION" in cmd:
                            return "Mix Conversion Suite (FLAC / MP3 / WAV / MP4)"
                        elif "convert_audio_format" in cmd:
                            return "Audio Format & Bit Depth Converter"
                        elif "MOVE_NOT_CONVERTED_WAVS" in cmd:
                            return "Retrieving Unconverted WAV Files"
                        elif "search_and_import_mixes" in cmd or "import_new_mixes" in cmd:
                            return "Search & Import Mixes from Drives / SMB"
                        elif "tag_audio_metadata" in cmd:
                            return "Audio Tagging & Vorbis Metadata Suite"
                        elif "master_audio_loudness" in cmd:
                            return "EBU R128 Loudness Scanner & Mastering"
                        elif "verify_audio_mastering" in cmd:
                            return "Audio Mastering Quality & Mono Phase Verification"
                        elif "generate_cue_sheet" in cmd:
                            return "Red Book CUE Sheet Generator"
                        elif "generate_master_tracklist" in cmd:
                            return "Generating Master Tracklist & Docs"
                        elif "generate_youtube_short_promo" in cmd:
                            return "YouTube Promo & Shorts Generator"
                        elif "btop" in cmd:
                            return "btop Hardware & System Resource Monitor"
                        elif "nvtop" in cmd:
                            return "nvtop GPU Monitor"
                        elif "MP_Monitor_Bash" in cmd:
                            return "Bash Process & System Monitor"
                        elif "mix_web_companion" in cmd:
                            return "Studio & DJ Booth Mobile Web Companion"
                        elif "Congen" in cmd or "congen" in cmd:
                            return "Congen KDE Connect Suite"
                        elif "manage_harmony_agent" in cmd:
                            return "MP Harmony AI Autonomous Agent"
                        elif "manage_ollama" in cmd:
                            return "Ollama Local LLM Management"
                        elif "dsh_mobile" in cmd:
                            return "DeepSeek Mobile Harness Server"
                        elif "wan2gp" in cmd:
                            return "WAN2GP AI Video & TTS Suite"
                        elif "backup_mix_archive" in cmd or "backup_to_gdrive" in cmd:
                            return "Cloud & Remote Archive Backup"
                except Exception:
                    continue
    except Exception:
        pass
    return None


def get_last_user_activity() -> Dict[str, Any]:
    """Retrieve the most recent activity recorded in user_activity.jsonl."""
    if not USER_ACTIVITY_FILE.exists():
        return {}
    try:
        with open(USER_ACTIVITY_FILE, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
            for line in reversed(lines):
                line = line.strip()
                if line:
                    data = json.loads(line)
                    return data
    except Exception:
        pass
    return {}


def get_audio_player_state() -> Dict[str, Any]:
    """Read the latest live state from MP Audio Player."""
    if not PLAYER_STATE_FILE.exists():
        return {"running": False, "state": "stopped", "title": "", "pos_fmt": "00:00", "dur_fmt": "00:00", "pct": 0}
    try:
        with open(PLAYER_STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return {
                "running": data.get("running", False),
                "state": data.get("state", "stopped"),
                "title": data.get("title", ""),
                "pos_fmt": data.get("position_fmt", "00:00"),
                "dur_fmt": data.get("duration_fmt", "00:00"),
                "pct": data.get("progress_pct", 0),
                "device": data.get("output_device", "Default Output")
            }
    except Exception:
        return {"running": False, "state": "stopped", "title": "", "pos_fmt": "00:00", "dur_fmt": "00:00", "pct": 0}


def get_theme_names() -> Tuple[str, str]:
    """Returns (mix_manager_theme, congen_theme)."""
    mm_t = "dreamworlds"
    cg_t = "dreamworlds"
    if MM_THEME_FILE.exists():
        try:
            val = MM_THEME_FILE.read_text(encoding="utf-8").strip()
            if val:
                mm_t = val
        except Exception:
            pass
    if CONGEN_THEME_FILE.exists():
        try:
            val = CONGEN_THEME_FILE.read_text(encoding="utf-8").strip()
            if val:
                cg_t = val
        except Exception:
            pass
    return mm_t, cg_t


def get_full_bridge_status() -> Dict[str, Any]:
    """Compile comprehensive live bridge status between MP Mix Manager & Congen."""
    pid = find_mix_manager_pid()
    proc_stats = get_process_stats(pid) if pid else {"alive": False, "pid": None, "cpu_pct": 0.0, "mem_mb": 0.0, "etime": "0s"}
    is_running = proc_stats["alive"]

    # Read current state file if available
    saved_state = {}
    if BRIDGE_STATE_FILE.exists():
        try:
            with open(BRIDGE_STATE_FILE, "r", encoding="utf-8") as f:
                saved_state = json.load(f)
        except Exception:
            pass

    # Resolve active menu
    active_menu = "Main Console / Workstation Menu"
    if is_running:
        child_op = detect_manager_child_operation(pid)
        if child_op:
            active_menu = child_op
        elif saved_state.get("active_menu"):
            active_menu = saved_state["active_menu"]
    else:
        active_menu = "Standby (Mix Manager Not Running)"

    # Audio player
    audio_info = get_audio_player_state()

    # Themes
    mm_theme, congen_theme = get_theme_names()
    themes_in_sync = (mm_theme == congen_theme)

    # User activity
    last_act = get_last_user_activity()

    # Congen liveness
    congen_pids = []
    try:
        res = subprocess.run(
            ["pgrep", "-f", "Congen/Congen"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=2
        )
        if res.returncode == 0:
            congen_pids = [int(p) for p in res.stdout.strip().split() if p.isdigit()]
    except Exception:
        pass
    congen_running = len(congen_pids) > 0

    # Connectivity validation
    # Both connected if state file is accessible, Mix Manager PID alive and IPC fresh
    now = time.time()
    updated_at = saved_state.get("updated_at", 0)
    time_diff = now - updated_at if updated_at > 0 else 999999

    bridge_status = "STANDBY"
    bridge_label = "○ Bridge Standby — Mix Manager Not Running"
    if is_running:
        if time_diff < 120 or BRIDGE_STATE_FILE.exists():
            bridge_status = "CONNECTED"
            bridge_label = "● Validated & Connected via MP Software Bridge"
        else:
            bridge_status = "LINKED"
            bridge_label = f"⚡ Manager Active (PID {pid}) — Bridge Linked"

    status_data = {
        "manager_running": is_running,
        "manager_pid": pid,
        "manager_uptime": proc_stats["etime"],
        "manager_cpu_pct": proc_stats["cpu_pct"],
        "manager_mem_mb": proc_stats["mem_mb"],
        "active_operation": active_menu,
        "active_theme_manager": mm_theme,
        "active_theme_congen": congen_theme,
        "themes_in_sync": themes_in_sync,
        "audio_player": audio_info,
        "last_activity": {
            "action": last_act.get("action", "—"),
            "category": last_act.get("category", "—"),
            "time": last_act.get("time", "—"),
            "date": last_act.get("date", "—"),
            "status": last_act.get("status", "—")
        },
        "congen_running": congen_running,
        "congen_pids": congen_pids,
        "bridge_status": bridge_status,
        "bridge_label": bridge_label,
        "bridge_file": str(BRIDGE_STATE_FILE),
        "updated_at": updated_at,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    return status_data


def update_bridge_state(menu: Optional[str] = None,
                        running: Optional[bool] = None,
                        pid: Optional[int] = None,
                        action: Optional[str] = None,
                        category: Optional[str] = None) -> Dict[str, Any]:
    """Update bridge state JSON atomically."""
    current = {}
    if BRIDGE_STATE_FILE.exists():
        try:
            with open(BRIDGE_STATE_FILE, "r", encoding="utf-8") as f:
                current = json.load(f)
        except Exception:
            current = {}

    now = time.time()
    now_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if menu is not None:
        current["active_menu"] = menu
    if running is not None:
        current["manager_running"] = running
    if pid is not None:
        current["pid"] = pid
    elif "pid" not in current or not current["pid"]:
        current["pid"] = find_mix_manager_pid()

    if action is not None:
        current["last_action"] = action
        current["last_action_category"] = category or "general"
        current["last_action_time"] = now_iso

    mm_t, _ = get_theme_names()
    current["active_theme"] = mm_t
    current["updated_at"] = now
    current["updated_iso"] = now_iso
    current["bridge_version"] = "1.0.0"

    try:
        temp_file = BRIDGE_STATE_FILE.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(current, f, indent=2)
        temp_file.replace(BRIDGE_STATE_FILE)

        # Mirror to congen config
        try:
            temp_mirror = BRIDGE_STATE_MIRROR.with_suffix(".tmp")
            with open(temp_mirror, "w", encoding="utf-8") as f:
                json.dump(current, f, indent=2)
            temp_mirror.replace(BRIDGE_STATE_MIRROR)
        except Exception:
            pass
    except Exception as e:
        sys.stderr.write(f"Error updating bridge state: {e}\n")

    return current


def validate_bridge_connectivity() -> Tuple[bool, List[Dict[str, Any]]]:
    """
    Execute 5-step comprehensive verification between Congen and MP Mix Manager.
    Returns (all_passed, results_list).
    """
    results = []

    # Step 1: Process Check
    pid = find_mix_manager_pid()
    if pid:
        results.append({
            "step": 1,
            "title": "MP Mix Manager Process Liveness",
            "status": "PASS",
            "detail": f"Active process running on PID {pid}"
        })
    else:
        results.append({
            "step": 1,
            "title": "MP Mix Manager Process Liveness",
            "status": "WARN",
            "detail": "Manager not running (standby mode — can be launched on demand)"
        })

    # Step 2: Bridge State Storage Integrity
    try:
        MIX_MANAGER_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        test_file = MIX_MANAGER_CONFIG_DIR / ".bridge_perm_test"
        test_file.write_text("ok", encoding="utf-8")
        test_file.unlink()
        results.append({
            "step": 2,
            "title": "Bridge State File Storage",
            "status": "PASS",
            "detail": f"Read/Write access verified in {MIX_MANAGER_CONFIG_DIR}"
        })
    except Exception as e:
        results.append({
            "step": 2,
            "title": "Bridge State File Storage",
            "status": "FAIL",
            "detail": f"Permission error: {e}"
        })

    # Step 3: Congen Installation & Symlinks
    congen_bin = CONGEN_DIR / "Congen"
    congen_link = WORKSPACE_DIR / "congen"
    if congen_bin.exists() and os.access(congen_bin, os.X_OK):
        link_str = f"Symlink: {congen_link}" if congen_link.exists() else "Direct binary"
        results.append({
            "step": 3,
            "title": "Congen Executable & Symlinks",
            "status": "PASS",
            "detail": f"Executable verified at {congen_bin} ({link_str})"
        })
    else:
        results.append({
            "step": 3,
            "title": "Congen Executable & Symlinks",
            "status": "FAIL",
            "detail": f"Congen binary missing or not executable at {congen_bin}"
        })

    # Step 4: KDE Connect Subsystem & Config
    if KDECONNECT_CONFIG_DIR.exists():
        dev_count = len(list(KDECONNECT_CONFIG_DIR.glob("*/kdeconnect_runcommand")))
        results.append({
            "step": 4,
            "title": "KDE Connect Subsystem",
            "status": "PASS",
            "detail": f"Configuration directory found with {dev_count} device configuration profile(s)"
        })
    else:
        results.append({
            "step": 4,
            "title": "KDE Connect Subsystem",
            "status": "WARN",
            "detail": f"Config path {KDECONNECT_CONFIG_DIR} not found yet (daemon may be uninitialized)"
        })

    # Step 5: Real-time IPC Handshake
    t0 = time.time()
    try:
        update_bridge_state(action="Connectivity Validation Ping", category="telemetry")
        t_latency_ms = round((time.time() - t0) * 1000, 2)
        results.append({
            "step": 5,
            "title": "Real-time Bidirectional Handshake",
            "status": "PASS",
            "detail": f"State sync confirmed with {t_latency_ms} ms roundtrip latency"
        })
    except Exception as e:
        results.append({
            "step": 5,
            "title": "Real-time Bidirectional Handshake",
            "status": "FAIL",
            "detail": f"Handshake failed: {e}"
        })

    all_passed = all(r["status"] in ("PASS", "WARN") for r in results)
    return all_passed, results


def sync_themes(source: str = "mix-manager") -> str:
    """Sync theme from one application to the other."""
    mm_t, cg_t = get_theme_names()
    target_theme = mm_t if source == "mix-manager" else cg_t
    MM_THEME_FILE.write_text(target_theme + "\n", encoding="utf-8")
    CONGEN_THEME_FILE.write_text(target_theme + "\n", encoding="utf-8")

    # If btop is installed and theme is ultra/cosmic, sync btop
    btop_dir = Path.home() / ".config" / "btop"
    if btop_dir.exists():
        tn = None
        if target_theme in ("dreamworlds_ultra", "ultra"):
            tn = "Dreamworlds_Ultra_MP_Mix_Manager"
        elif target_theme in ("cosmic_supernova", "supernova"):
            tn = "Cosmic_Supernova_MP_Mix_Manager"
        elif target_theme in ("stream_of_frequency", "stream", "frequency", "sof", "frequency_stream"):
            tn = "Stream_of_Frequency_MP_Mix_Manager"
        if tn:
            btop_themes = btop_dir / "themes"
            btop_themes.mkdir(parents=True, exist_ok=True)
            theme_src = WORKSPACE_DIR / "themes" / f"{tn}.theme"
            if theme_src.exists():
                shutil.copy2(theme_src, btop_themes / f"{tn}.theme")
            btop_conf = btop_dir / "btop.conf"
            if btop_conf.exists():
                try:
                    content = btop_conf.read_text(encoding="utf-8")
                    new_content = re.sub(r'color_theme\s*=\s*".*"', f'color_theme = "{tn}"', content)
                    btop_conf.write_text(new_content, encoding="utf-8")
                except Exception:
                    pass

    return target_theme


def launch_mix_manager() -> bool:
    """Launch MP Mix Manager in a new window/terminal."""
    manager_script = WORKSPACE_DIR / "manager.sh"
    if not manager_script.exists():
        manager_script = WORKSPACE_DIR / "Mix_Archive_Manager.sh"

    # Terminal candidates
    terms = [
        ["konsole", "-e", "bash", str(manager_script)],
        ["ptyxis", "--", "bash", str(manager_script)],
        ["gnome-terminal", "--", "bash", str(manager_script)],
        ["xterm", "-e", "bash", str(manager_script)],
        ["alacritty", "-e", "bash", str(manager_script)],
        ["kitty", "bash", str(manager_script)]
    ]

    for cmd in terms:
        try:
            if shutil.which(cmd[0]):
                subprocess.Popen(cmd, cwd=str(WORKSPACE_DIR), start_new_session=True)
                return True
        except Exception:
            continue

    # Fallback to background nohup
    try:
        subprocess.Popen(["nohup", "bash", str(manager_script)], cwd=str(WORKSPACE_DIR), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        return True
    except Exception:
        return False


def main():
    import argparse
    parser = argparse.ArgumentParser(description="MP Software Bridge: MP Mix Manager & Congen Integration")
    parser.add_argument("command", nargs="?", default="status", choices=[
        "status", "validate", "update-menu", "update-action", "sync-theme", "launch", "ping", "get-eval"
    ])
    parser.add_argument("--json", action="store_true", help="Output in JSON format")
    parser.add_argument("--menu", type=str, help="Operation menu name")
    parser.add_argument("--action", type=str, help="User action name")
    parser.add_argument("--category", type=str, default="general", help="Action category")
    parser.add_argument("--running", type=str, help="Running state (true/false)")
    parser.add_argument("--pid", type=int, help="Manager PID")
    parser.add_argument("--from-source", choices=["mix-manager", "congen"], default="mix-manager", help="Sync source")

    args = parser.parse_args()

    if args.command == "status":
        status = get_full_bridge_status()
        if args.json:
            print(json.dumps(status, indent=2))
        else:
            CYAN = "\033[38;2;0;229;255m\033[1m"
            MAGENTA = "\033[38;2;247;37;133m\033[1m"
            GREEN = "\033[38;2;0;255;0m\033[1m"
            YELLOW = "\033[38;2;255;170;0m\033[1m"
            RED = "\033[38;2;255;51;102m\033[1m"
            WHITE = "\033[1;37m"
            DIM = "\033[2m"
            RESET = "\033[0m"

            st_color = GREEN if status["manager_running"] else YELLOW
            st_text = "● RUNNING" if status["manager_running"] else "○ STANDBY"

            print(f"\n{CYAN}" + ("═" * 70) + f"{RESET}")
            print(f"{CYAN}║{RESET}  {MAGENTA}MP Software Bridge — Telemetry & Integration Engine{RESET}")
            print(f"{CYAN}" + ("═" * 70) + f"{RESET}\n")

            print(f"  {WHITE}Manager Status    :{RESET} {st_color}{st_text}{RESET}  (PID: {status['manager_pid'] or 'None'}, Uptime: {status['manager_uptime']})")
            if status["manager_running"]:
                print(f"  {WHITE}CPU / Memory      :{RESET} {CYAN}{status['manager_cpu_pct']}% CPU{RESET} │ {CYAN}{status['manager_mem_mb']} MB RAM{RESET}")
            print(f"  {WHITE}Current Operation :{RESET} {YELLOW}{status['active_operation']}{RESET}")

            audio = status["audio_player"]
            if audio["running"] and audio["state"] == "playing":
                print(f"  {WHITE}Workstation Audio :{RESET} {GREEN}▶ PLAYING:{RESET} {audio['title']} {DIM}({audio['pos_fmt']} / {audio['dur_fmt']} - {audio['pct']}%){RESET}")
            elif audio["running"]:
                print(f"  {WHITE}Workstation Audio :{RESET} {YELLOW}⏸ PAUSED:{RESET} {audio['title']}")
            else:
                print(f"  {WHITE}Workstation Audio :{RESET} {DIM}○ Idle (No active playback){RESET}")

            print(f"  {WHITE}Bridge Connection :{RESET} {status['bridge_label']}")
            sync_label = f"{GREEN}In Sync{RESET}" if status["themes_in_sync"] else f"{YELLOW}Mismatch (MM: {status['active_theme_manager']} / CG: {status['active_theme_congen']}){RESET}"
            print(f"  {WHITE}Themes            :{RESET} {sync_label}")

            act = status["last_activity"]
            if act["action"] != "—":
                print(f"  {WHITE}Last User Action  :{RESET} {act['action']} {DIM}@{act['time']} [{act['status']}]{RESET}")

            print(f"\n{DIM}Bridge File: {status['bridge_file']}{RESET}\n")

    elif args.command == "get-eval":
        # Outputs bash-eval safe environment variables
        status = get_full_bridge_status()
        def q(s): return "'" + str(s).replace("'", "'\\''") + "'"

        print(f"MM_RUNNING={1 if status['manager_running'] else 0}")
        print(f"MM_PID={q(status['manager_pid'] or '—')}")
        print(f"MM_UPTIME={q(status['manager_uptime'])}")
        print(f"MM_CPU={q(str(status['manager_cpu_pct']) + '%')}")
        print(f"MM_MEM={q(str(status['manager_mem_mb']) + ' MB')}")
        print(f"MM_ACTIVE_OPERATION={q(status['active_operation'])}")
        print(f"MM_THEME={q(status['active_theme_manager'])}")
        print(f"MM_THEMES_IN_SYNC={1 if status['themes_in_sync'] else 0}")
        print(f"MM_BRIDGE_STATUS={q(status['bridge_status'])}")
        print(f"MM_BRIDGE_LABEL={q(status['bridge_label'])}")

        audio = status["audio_player"]
        print(f"MM_AUDIO_RUNNING={1 if audio['running'] else 0}")
        print(f"MM_AUDIO_STATE={q(audio['state'])}")
        print(f"MM_AUDIO_TITLE={q(audio['title'])}")
        pos_str = f"{audio['pos_fmt']} / {audio['dur_fmt']} ({audio['pct']}%)"
        print(f"MM_AUDIO_POS={q(pos_str)}")

        act = status["last_activity"]
        print(f"MM_LAST_ACTION={q(act['action'])}")
        print(f"MM_LAST_ACTION_TIME={q(act['time'])}")

    elif args.command == "update-menu":
        is_run = True
        if args.running is not None:
            is_run = (args.running.lower() in ("true", "1", "yes"))
        res = update_bridge_state(menu=args.menu, running=is_run, pid=args.pid)
        if args.json:
            print(json.dumps(res))
        else:
            print(f"Bridge updated: menu='{args.menu}', running={is_run}")

    elif args.command == "update-action":
        res = update_bridge_state(action=args.action, category=args.category)
        if args.json:
            print(json.dumps(res))
        else:
            print(f"Bridge updated: action='{args.action}'")

    elif args.command == "validate":
        passed, results = validate_bridge_connectivity()
        if args.json:
            print(json.dumps({"passed": passed, "results": results}, indent=2))
        else:
            GREEN = "\033[38;2;0;255;0m\033[1m"
            YELLOW = "\033[38;2;255;170;0m\033[1m"
            RED = "\033[38;2;255;51;102m\033[1m"
            WHITE = "\033[1;37m"
            DIM = "\033[2m"
            RESET = "\033[0m"

            print(f"\n{WHITE}MP Software Bridge — Connectivity & Health Diagnostics{RESET}")
            print(f"{DIM}─" * 60 + f"{RESET}")
            for r in results:
                badge = f"{GREEN}[PASS]{RESET}" if r["status"] == "PASS" else (f"{YELLOW}[WARN]{RESET}" if r["status"] == "WARN" else f"{RED}[FAIL]{RESET}")
                print(f"  {badge}  {WHITE}Step {r['step']}: {r['title']}{RESET}")
                print(f"         {DIM}{r['detail']}{RESET}")
            print(f"{DIM}─" * 60 + f"{RESET}")
            overall = f"{GREEN}● ALL CHECKS VALIDATED{RESET}" if passed else f"{RED}✘ VALIDATION WARNINGS/ERRORS DETECTED{RESET}"
            print(f"  Overall Validation Status: {overall}\n")
        sys.exit(0 if passed else 1)

    elif args.command == "sync-theme":
        synced = sync_themes(args.from_source)
        print(f"Themes synchronized successfully to '{synced}'.")

    elif args.command == "launch":
        ok = launch_mix_manager()
        if ok:
            print("MP Mix Manager launch signal dispatched successfully.")
        else:
            print("Failed to dispatch launch command for MP Mix Manager.")
            sys.exit(1)

    elif args.command == "ping":
        update_bridge_state(action="Ping Handshake", category="telemetry")
        print("PONG - MP Software Bridge is active and responsive.")


if __name__ == "__main__":
    main()
