#!/usr/bin/env bash
"true" '''\'
# ==============================================================================
# MP_Infinite_Talker.py - Self-Executing Python Wrapper (WAN2GP Environment)
# ==============================================================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
for _cfg in "$SCRIPT_DIR/config.env" "$SCRIPT_DIR/../config.env" "$PWD/config.env" "/x/MP_Mix_Manager_v0.3/config.env" "X:/MP_Mix_Manager_v0.3/config.env" "$HOME/MP_Mix_Manager_v0.3/config.env"; do
    if [ -f "$_cfg" ]; then
        source "$_cfg" 2>/dev/null || true
        break
    fi
done

# Resolve WAN2GP Application Directory
APP_DIR="${WAN2GP_DIR:-}"
[ -z "$APP_DIR" ] && [ -d "X:/WAN2GP/Wan2GP" ] && APP_DIR="X:/WAN2GP/Wan2GP"
[ -z "$APP_DIR" ] && [ -d "D:/WAN2GP/Wan2GP" ] && APP_DIR="D:/WAN2GP/Wan2GP"
[ -z "$APP_DIR" ] && [ -d "/var/home/mplanetarian/pinokio/api/wan.git/app" ] && APP_DIR="/var/home/mplanetarian/pinokio/api/wan.git/app"
[ -z "$APP_DIR" ] && [ -d "$HOME/pinokio/api/wan.git/app" ] && APP_DIR="$HOME/pinokio/api/wan.git/app"

# Resolve Python Environment
VENV_PYTHON="${WAN2GP_PYTHON:-}"
[ -z "$VENV_PYTHON" ] && [ -x "X:/WAN2GP/conda_envs/wan2gp/python.exe" ] && VENV_PYTHON="X:/WAN2GP/conda_envs/wan2gp/python.exe"
[ -z "$VENV_PYTHON" ] && [ -x "$APP_DIR/venv/Scripts/python.exe" ] && VENV_PYTHON="$APP_DIR/venv/Scripts/python.exe"
[ -z "$VENV_PYTHON" ] && [ -x "$APP_DIR/venv/bin/python" ] && VENV_PYTHON="$APP_DIR/venv/bin/python"
if [ -z "$VENV_PYTHON" ] || [ ! -x "$VENV_PYTHON" ]; then
    if command -v python3 >/dev/null 2>&1; then
        VENV_PYTHON="$(command -v python3)"
    elif command -v python >/dev/null 2>&1; then
        VENV_PYTHON="$(command -v python)"
    fi
fi

if [ -z "$VENV_PYTHON" ] || [ ! -x "$VENV_PYTHON" ]; then
    echo -e "\033[0;31m[-] Error: Python environment not found!\033[0m" >&2
    exit 1
fi

export WAN2GP_DIR="$APP_DIR"
export WAN2GP_PYTHON="$VENV_PYTHON"
export PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True"
export CUDA_VISIBLE_DEVICES="0"

if [ "$(uname -s)" = "Linux" ]; then
    SITE_PKGS=$("$VENV_PYTHON" -c "import site; print(site.getsitepackages()[0])" 2>/dev/null || true)
    if [ -n "$SITE_PKGS" ]; then
        export LD_LIBRARY_PATH="$SITE_PKGS/nvidia/cudnn/lib:$SITE_PKGS/nvidia/cublas/lib:$SITE_PKGS/nvidia/cuda_runtime/lib:${LD_LIBRARY_PATH:-}"
    fi
fi

exec "$VENV_PYTHON" "$0" "$@"
'''

"""
==============================================================================
MP_Infinite_Talker.py - Infinite Talk Video Generation & Batch Suite
==============================================================================
Generates Infinite Talk AI video portraits driven by speech audio using
WAN2GP's Infinitetalk 14B model.

Key Capabilities:
  - Batch Generation: Processes text (.txt) and audio (.wav/.mp3) from:
    /run/media/mplanetarian/GAMES1/DATA_DRIVE_MOVED/WAN2GP_INFTLKBATCH/
  - Default Avatar: Uses /run/media/mplanetarian/GAMES1/DATA_DRIVE_MOVED/
    WAN2GP_INFTLKBATCH/CTRL_IMAGE/Stephen_Hawking.png
  - Default Voice: Stephen Hawking Matrix Synthesizer (espeak-ng + DSP filter chain)
  - Extensible Voices: Select existing voices or dynamically add new voices from
    Edge-TTS or custom reference audio samples
  - Watch Mode: Automatically converts incoming texts & audios in background
  - MP Reporter Integration: Generates Stephen Hawking video reports reading
    transcripts from MP Reporter
==============================================================================
"""

import os
import sys
import re
import json
import time
import shutil
import signal
import datetime
import argparse
import tempfile
import subprocess
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any

# Styling Colors
RED = "\033[0;31m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
BLUE = "\033[0;34m"
MAGENTA = "\033[1;35m"
CYAN = "\033[0;36m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"

# Load config.env
def load_config_env():
    """Load config.env variables into os.environ if not already present."""
    possible_cfgs = [
        Path(__file__).resolve().parent / "config.env",
        Path(__file__).resolve().parent.parent / "config.env",
        Path.cwd() / "config.env",
        Path("/x/MP_Mix_Manager_v0.3/config.env"),
        Path("/var/home/mplanetarian/MP_Mix_Manager_v0.3/config.env"),
        Path("D:/DATA_DRIVE_MOVED/config.env"),
    ]
    for cfg in possible_cfgs:
        if cfg.exists():
            try:
                with open(cfg, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            k = k.strip()
                            v = v.strip().strip('"').strip("'")
                            if k not in os.environ and v:
                                os.environ[k] = v
                break
            except Exception:
                pass

load_config_env()

# Directory Resolution
PRIMARY_DATA_DIR = Path("/run/media/mplanetarian/GAMES1/DATA_DRIVE_MOVED")
WIN_DATA_DIR = Path("D:/DATA_DRIVE_MOVED")
FALLBACK_DATA_DIR = Path("/run/media/mplanetarian/DATA")

if PRIMARY_DATA_DIR.exists():
    BASE_DATA_DIR = PRIMARY_DATA_DIR
elif WIN_DATA_DIR.exists():
    BASE_DATA_DIR = WIN_DATA_DIR
elif FALLBACK_DATA_DIR.exists():
    BASE_DATA_DIR = FALLBACK_DATA_DIR
else:
    BASE_DATA_DIR = PRIMARY_DATA_DIR

DEFAULT_BATCH_DIR = Path(os.environ.get("WAN2GP_INFTLKBATCH_DIR", BASE_DATA_DIR / "WAN2GP_INFTLKBATCH"))
DEFAULT_OUTPUTS_DIR = Path(os.environ.get("WAN2GP_OUTPUTS", BASE_DATA_DIR / "WAN2GP_OUTPUTS"))
CONFIG_FILE = Path.home() / ".config" / "mp_infinite_talker_config.json"

# WAN2GP paths
wan_candidate = os.environ.get("WAN2GP_DIR")
if wan_candidate and Path(wan_candidate).exists():
    WAN_APP_ROOT = Path(wan_candidate)
elif Path("/var/home/mplanetarian/pinokio/api/wan.git/app").exists():
    WAN_APP_ROOT = Path("/var/home/mplanetarian/pinokio/api/wan.git/app")
elif (Path.home() / "pinokio/api/wan.git/app").exists():
    WAN_APP_ROOT = Path.home() / "pinokio/api/wan.git/app"
elif Path("X:/WAN2GP/Wan2GP").exists():
    WAN_APP_ROOT = Path("X:/WAN2GP/Wan2GP")
elif Path("D:/WAN2GP/Wan2GP").exists():
    WAN_APP_ROOT = Path("D:/WAN2GP/Wan2GP")
else:
    WAN_APP_ROOT = Path("/var/home/mplanetarian/pinokio/api/wan.git/app")

# Supported file extensions
SUPPORTED_TEXT_EXTS = {".txt", ".text", ".md", ".log"}
SUPPORTED_AUDIO_EXTS = {".wav", ".mp3", ".flac", ".m4a", ".ogg", ".aac"}
SUPPORTED_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}

# Built-in Voice Catalog
DEFAULT_VOICES = [
    {
        "id": "stephen_hawking",
        "name": "Stephen Hawking (Matrix Synthesizer)",
        "gender": "Male",
        "engine": "hawking_espeak",
        "desc": "Famous robotic Stephen Hawking synthesizer with resonant bass, EQ & echo (Default)",
    },
    {
        "id": "en-GB-RyanNeural",
        "name": "Ryan (Edge Neural)",
        "gender": "Male",
        "engine": "edge",
        "desc": "Professional, articulate British English",
    },
    {
        "id": "en-GB-SoniaNeural",
        "name": "Sonia (Edge Neural)",
        "gender": "Female",
        "engine": "edge",
        "desc": "Natural, clear, warm British English",
    },
    {
        "id": "en-GB-ThomasNeural",
        "name": "Thomas (Edge Neural)",
        "gender": "Male",
        "engine": "edge",
        "desc": "Authoritative, calm, deep British English",
    },
    {
        "id": "en-GB-LibbyNeural",
        "name": "Libby (Edge Neural)",
        "gender": "Female",
        "engine": "edge",
        "desc": "Friendly, polite British English",
    },
    {
        "id": "en-US-GuyNeural",
        "name": "Guy (Edge Neural)",
        "gender": "Male",
        "engine": "edge",
        "desc": "Natural, confident American English",
    },
    {
        "id": "en-US-JennyNeural",
        "name": "Jenny (Edge Neural)",
        "gender": "Female",
        "engine": "edge",
        "desc": "Clear, professional US female voice",
    },
    {
        "id": "en-US-ChristopherNeural",
        "name": "Christopher (Edge Neural)",
        "gender": "Male",
        "engine": "edge",
        "desc": "Authoritative, broadcast quality US male voice",
    },
    {
        "id": "espeak:en-gb",
        "name": "George (eSpeak)",
        "gender": "Male",
        "engine": "espeak",
        "desc": "Instant offline British male voice",
    },
    {
        "id": "espeak:en-gb+f3",
        "name": "Emily (eSpeak)",
        "gender": "Female",
        "engine": "espeak",
        "desc": "Instant offline British female voice",
    },
]

def load_user_config() -> dict:
    """Load configuration JSON from ~/.config/mp_infinite_talker_config.json."""
    data = {
        "batch_dir": str(DEFAULT_BATCH_DIR),
        "outputs_dir": str(DEFAULT_OUTPUTS_DIR),
        "active_voice": "stephen_hawking",
        "active_ctrl_image": "Stephen_Hawking.png",
        "resolution": "832x480",
        "profile": "4.5",
        "steps": 4,
        "custom_voices": [],
    }
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                data.update(saved)
        except Exception:
            pass
    return data

def save_user_config(data: dict):
    """Save configuration JSON."""
    try:
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"{YELLOW}[!] Failed to save config: {e}{RESET}")

def get_voice_catalog(config: dict) -> list[dict]:
    """Return all voices including built-ins, custom registered, and audio files in VOICES/."""
    voices = list(DEFAULT_VOICES)
    # Add saved custom voices
    for cv in config.get("custom_voices", []):
        if not any(v["id"] == cv["id"] for v in voices):
            voices.append(cv)

    # Scan VOICES/ directory for custom reference audio files
    batch_dir = Path(config.get("batch_dir", str(DEFAULT_BATCH_DIR)))
    voices_dir = batch_dir / "VOICES"
    if voices_dir.exists():
        for f in voices_dir.iterdir():
            if f.is_file() and f.suffix.lower() in SUPPORTED_AUDIO_EXTS:
                vid = f"sample:{f.name}"
                if not any(v["id"] == vid for v in voices):
                    voices.append({
                        "id": vid,
                        "name": f"{f.stem} (Custom Audio Sample)",
                        "gender": "Custom",
                        "engine": "audio_sample",
                        "sample_path": str(f.resolve()),
                        "desc": f"Custom driving audio from {f.name}",
                    })
    return voices

def get_control_images(batch_dir: Path) -> list[Path]:
    """Find all valid control avatar images in CTRL_IMAGE."""
    ctrl_dir = batch_dir / "CTRL_IMAGE"
    if not ctrl_dir.exists():
        return []
    imgs = [
        f for f in ctrl_dir.iterdir()
        if f.is_file() and f.suffix.lower() in SUPPORTED_IMAGE_EXTS
    ]
    # Stephen Hawking first if present
    imgs.sort(key=lambda x: (0 if "stephen" in x.name.lower() or "hawking" in x.name.lower() else 1, x.name.lower()))
    return imgs

def ensure_batch_directory_structure(batch_dir: Path, outputs_dir: Path):
    """Ensure all required folders exist."""
    batch_dir.mkdir(parents=True, exist_ok=True)
    (batch_dir / "CTRL_IMAGE").mkdir(parents=True, exist_ok=True)
    (batch_dir / "PROCESSED").mkdir(parents=True, exist_ok=True)
    (batch_dir / "OUTPUTS").mkdir(parents=True, exist_ok=True)
    (batch_dir / "VOICES").mkdir(parents=True, exist_ok=True)
    (batch_dir / "TTS_CONVERTED").mkdir(parents=True, exist_ok=True)
    outputs_dir.mkdir(parents=True, exist_ok=True)

    # Check if Stephen_Hawking.png exists in CTRL_IMAGE
    default_img = batch_dir / "CTRL_IMAGE" / "Stephen_Hawking.png"
    if not default_img.exists():
        # Look for alternative location
        alt = Path("/run/media/mplanetarian/GAMES1/DATA_DRIVE_MOVED/WAN2GP_INFTLKBATCH/CTRL_IMAGE/Stephen_Hawking.png")
        if alt.exists():
            try:
                shutil.copy2(str(alt), str(default_img))
            except Exception:
                pass

def synthesize_hawking_speech(text: str, out_wav: Path) -> bool:
    """Synthesize speech using Stephen Hawking's authentic synthesizer filter chain."""
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as tf:
        tf.write(text)
        t_name = tf.name

    raw_wav = Path(tempfile.mktemp(suffix=".wav"))
    try:
        espeak_bin = shutil.which("espeak-ng") or shutil.which("espeak")
        if not espeak_bin:
            print(f"{RED}[-] Error: espeak-ng is required for Stephen Hawking voice.{RESET}")
            return False

        # espeak-ng -v en-us+m3 -s 110 -p 19
        cmd_espeak = [espeak_bin, "-v", "en-us+m3", "-s", "110", "-p", "19", "-f", t_name, "-w", str(raw_wav)]
        res = subprocess.run(cmd_espeak, capture_output=True, text=True)
        if res.returncode != 0:
            print(f"{RED}[-] espeak-ng error: {res.stderr}{RESET}")
            return False

        # Tuned DSP Filter: resonant bass, EQ & echo
        dsp_filter = "bass=g=12:f=95:w=0.6, equalizer=f=2400:t=q:w=1.2:g=2, aecho=0.8:0.7:50|100:0.3|0.2"
        out_wav.parent.mkdir(parents=True, exist_ok=True)
        cmd_ffmpeg = [
            "ffmpeg", "-y", "-v", "error",
            "-i", str(raw_wav),
            "-af", dsp_filter,
            "-ar", "16000",
            "-ac", "1",
            str(out_wav)
        ]
        res_ff = subprocess.run(cmd_ffmpeg, capture_output=True, text=True)
        return res_ff.returncode == 0 and out_wav.exists() and out_wav.stat().st_size > 0
    finally:
        if os.path.exists(t_name):
            os.remove(t_name)
        if raw_wav.exists():
            raw_wav.unlink(missing_ok=True)

def synthesize_edge_speech(text: str, voice_id: str, out_wav: Path) -> bool:
    """Synthesize speech using Edge-TTS neural voice."""
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as tf:
        tf.write(text)
        t_name = tf.name

    tmp_mp3 = Path(tempfile.mktemp(suffix=".mp3"))
    try:
        # Run edge-tts command
        cmd = ["edge-tts", "--voice", voice_id, "-f", t_name, "--write-media", str(tmp_mp3)]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0 or not tmp_mp3.exists() or tmp_mp3.stat().st_size == 0:
            # Try python -m edge_tts
            cmd_py = [sys.executable, "-m", "edge_tts", "--voice", voice_id, "-f", t_name, "--write-media", str(tmp_mp3)]
            subprocess.run(cmd_py, capture_output=True, text=True)

        if not tmp_mp3.exists() or tmp_mp3.stat().st_size == 0:
            print(f"{RED}[-] Edge-TTS synthesis failed. Falling back to Stephen Hawking voice.{RESET}")
            return synthesize_hawking_speech(text, out_wav)

        # Convert mp3 to 16kHz mono WAV for WAN2GP Infinite Talk
        cmd_ff = [
            "ffmpeg", "-y", "-v", "error",
            "-i", str(tmp_mp3),
            "-ar", "16000",
            "-ac", "1",
            str(out_wav)
        ]
        res_ff = subprocess.run(cmd_ff, capture_output=True, text=True)
        return res_ff.returncode == 0 and out_wav.exists() and out_wav.stat().st_size > 0
    finally:
        if os.path.exists(t_name):
            os.remove(t_name)
        if tmp_mp3.exists():
            tmp_mp3.unlink(missing_ok=True)

def synthesize_espeak_speech(text: str, voice_id: str, out_wav: Path) -> bool:
    """Synthesize speech using eSpeak-NG."""
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as tf:
        tf.write(text)
        t_name = tf.name

    espeak_bin = shutil.which("espeak-ng") or shutil.which("espeak") or "espeak-ng"
    v_param = voice_id.replace("espeak:", "")
    raw_wav = Path(tempfile.mktemp(suffix=".wav"))
    try:
        cmd = [espeak_bin, "-v", v_param, "-f", t_name, "-w", str(raw_wav)]
        subprocess.run(cmd, capture_output=True, text=True)
        if not raw_wav.exists() or raw_wav.stat().st_size == 0:
            return False

        cmd_ff = ["ffmpeg", "-y", "-v", "error", "-i", str(raw_wav), "-ar", "16000", "-ac", "1", str(out_wav)]
        subprocess.run(cmd_ff, capture_output=True, text=True)
        return out_wav.exists() and out_wav.stat().st_size > 0
    finally:
        if os.path.exists(t_name):
            os.remove(t_name)
        if raw_wav.exists():
            raw_wav.unlink(missing_ok=True)

def generate_speech_for_text(text: str, voice_info: dict, out_wav: Path) -> bool:
    """Generate audio for text based on voice engine."""
    engine = voice_info.get("engine", "hawking_espeak")
    vid = voice_info.get("id", "stephen_hawking")
    if engine == "hawking_espeak" or "hawking" in vid.lower():
        return synthesize_hawking_speech(text, out_wav)
    elif engine == "edge":
        return synthesize_edge_speech(text, vid, out_wav)
    elif engine == "espeak":
        return synthesize_espeak_speech(text, vid, out_wav)
    else:
        return synthesize_hawking_speech(text, out_wav)

def get_audio_duration_seconds(audio_path: Path) -> float:
    """Get duration of audio file in seconds."""
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(audio_path)
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0 and res.stdout.strip():
            return float(res.stdout.strip())
    except Exception:
        pass
    return 10.0

def check_and_resolve_running_server():
    """Check if another WAN2GP instance is active and offer to stop it."""
    try:
        pids = []
        res = subprocess.run(["pgrep", "-f", "python.*wgp\\.py"], capture_output=True, text=True)
        if res.returncode == 0:
            pids = [p.strip() for p in res.stdout.strip().split("\n") if p.strip()]
        current_pid = str(os.getpid())
        pids = [p for p in pids if p != current_pid]
        if pids:
            print(f"\n{YELLOW}[!] Notice: WAN2GP server is already active (PID: {', '.join(pids)}).{RESET}")
            print(f"    Running batch generation concurrently might exhaust GPU VRAM.")
            ans = input(f"{BOLD}    Stop running WAN2GP server before proceeding? [Y/n]: {RESET}").strip().lower()
            if ans in ("", "y", "yes"):
                print(f"{CYAN}[*] Stopping WAN2GP server...{RESET}")
                stop_script = Path(__file__).resolve().parent / "wan2gp.sh"
                if not stop_script.exists():
                    stop_script = Path(__file__).resolve().parent.parent / "scripts" / "wan2gp.sh"
                if stop_script.exists():
                    subprocess.run(["bash", str(stop_script), "stop"], capture_output=True)
                else:
                    for p in pids:
                        try:
                            os.kill(int(p), signal.SIGTERM)
                        except Exception:
                            pass
                time.sleep(1.5)
                print(f"{GREEN}[✓] WAN2GP server stopped.{RESET}")
    except Exception:
        pass

def generate_infinite_talk_video(
    ctrl_image: Path,
    audio_path: Path,
    output_video_path: Path,
    prompt: Optional[str] = None,
    resolution: str = "832x480",
    profile: str = "4.5",
    steps: int = 4,
    guidance: float = 1.0,
    audio_guidance: float = 1.0,
    duration: float = 0.0,
) -> bool:
    """Generate an Infinite Talk video using WAN2GP Infinite Talk 14B model."""
    if not ctrl_image.exists():
        print(f"{RED}[-] Error: Control image not found: {ctrl_image}{RESET}")
        return False
    if not audio_path.exists():
        print(f"{RED}[-] Error: Audio file not found: {audio_path}{RESET}")
        return False

    duration_sec = get_audio_duration_seconds(audio_path)
    trimmed_audio = None
    if duration > 0 and duration < duration_sec:
        trimmed_audio = Path(tempfile.mktemp(suffix="_trimmed.wav"))
        subprocess.run(["ffmpeg", "-y", "-i", str(audio_path), "-t", str(duration), "-c", "copy", str(trimmed_audio)], capture_output=True)
        if trimmed_audio.exists() and trimmed_audio.stat().st_size > 0:
            audio_path = trimmed_audio
            duration_sec = duration

    # 25 fps WAN default
    estimated_frames = max(81, int(duration_sec * 25))

    default_prompt = (
        "A distinguished person sitting in a study speaking calmly and intelligently to the camera, "
        "photorealistic, cinematic lighting, sharp focus, 8k resolution, realistic facial expressions, natural lip sync"
    )
    if "hawking" in ctrl_image.name.lower():
        default_prompt = (
            "Stephen Hawking sitting in his iconic high-tech wheelchair in a modern scientific study, "
            "speaking to the camera, photorealistic 8k, ultra-detailed expressions, cinematic lighting, natural lip sync"
        )
    active_prompt = prompt or default_prompt

    print(f"\n{BOLD}{CYAN}=================================================={RESET}")
    print(f"{BOLD}{CYAN}       WAN2GP INFINITE TALK VIDEO GENERATION      {RESET}")
    print(f"{BOLD}{CYAN}=================================================={RESET}")
    print(f"  Avatar Image:     {GREEN}{ctrl_image.name}{RESET}")
    print(f"  Driving Audio:    {GREEN}{audio_path.name}{RESET} (~{duration_sec:.1f}s)")
    print(f"  Resolution:       {CYAN}{resolution}{RESET}")
    print(f"  Target Video:     {GREEN}{output_video_path.name}{RESET}")
    print(f"  Model:            {MAGENTA}Wan2.1 InfiniteTalk 14B (Quantized INT8){RESET}")
    print(f"  Safety Profile:   {YELLOW}Profile {profile} (Low VRAM Offload){RESET}")
    print(f"  Inference Steps:  {CYAN}{steps}{RESET}")
    print(f"  Sliding Window:   {CYAN}81 frames (9 overlap){RESET}")
    print(f"  Prompt:           {DIM}\"{active_prompt[:80]}...\"{RESET}")
    print(f"{CYAN}--------------------------------------------------{RESET}")

    # Create temporary task manifest
    task_json = Path(tempfile.mktemp(suffix="_inftalk_task.json"))
    task_payload = {
        "model_type": "infinitetalk",
        "model_filename": "wan2.1_infinitetalk_single_14B_quanto_mfp16_int8.safetensors",
        "prompt": active_prompt,
        "alt_prompt": "",
        "negative_prompt": "",
        "resolution": resolution,
        "video_length": estimated_frames,
        "sliding_window_size": 81,
        "sliding_window_overlap": 9,
        "sliding_window_color_correction_strength": 0,
        "sliding_window_overlap_noise": 0,
        "sliding_window_discard_last_frames": 0,
        "num_inference_steps": steps,
        "guidance_scale": guidance,
        "audio_guidance_scale": audio_guidance,
        "flow_shift": 7,
        "sample_solver": "euler",
        "repeat_generation": 1,
        "video_prompt_type": "0KI",
        "audio_prompt_type": "A",
        "audio_guide": str(audio_path.resolve()),
        "image_refs": [str(ctrl_image.resolve())],
        "image_start": [str(ctrl_image.resolve())],
        "output_filename": output_video_path.stem,
        "mode": "",
    }

    try:
        with open(task_json, "w", encoding="utf-8") as f:
            json.dump(task_payload, f, indent=2)

        # Execute WAN2GP via Python environment
        venv_python = os.environ.get("WAN2GP_PYTHON", str(WAN_APP_ROOT / "venv" / "bin" / "python"))
        wgp_py = WAN_APP_ROOT / "wgp.py"

        if not wgp_py.exists():
            print(f"{RED}[-] Error: wgp.py not found in {WAN_APP_ROOT}{RESET}")
            return False

        out_dir = output_video_path.parent
        out_dir.mkdir(parents=True, exist_ok=True)

        cmd = [
            venv_python,
            str(wgp_py),
            "--profile", profile,
            "--attention", "sage",
            "--process", str(task_json),
            "--output-dir", str(out_dir),
        ]

        env = os.environ.copy()
        env["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
        env["CUDA_VISIBLE_DEVICES"] = "0"

        # Ensure LD_LIBRARY_PATH has nvidia packages
        site_pkgs_res = subprocess.run([venv_python, "-c", "import site; print(site.getsitepackages()[0])"], capture_output=True, text=True)
        if site_pkgs_res.returncode == 0:
            sp = site_pkgs_res.stdout.strip()
            nv_libs = f"{sp}/nvidia/cudnn/lib:{sp}/nvidia/cublas/lib:{sp}/nvidia/cuda_runtime/lib"
            env["LD_LIBRARY_PATH"] = f"{nv_libs}:{env.get('LD_LIBRARY_PATH', '')}"

        print(f"{CYAN}[*] Starting Infinite Talk model generation...{RESET}\n")
        start_t = time.time()
        proc = subprocess.Popen(cmd, env=env, cwd=str(WAN_APP_ROOT))
        ret = proc.wait()
        elapsed = time.time() - start_t

        if ret != 0:
            print(f"\n{RED}[-] WAN2GP generation failed with exit code {ret}{RESET}")
            return False

        # Find generated output video in out_dir
        # Check if output_video_path exists or find the newest video file
        if not output_video_path.exists():
            candidates = [
                p for p in out_dir.iterdir()
                if p.is_file() and p.suffix.lower() == ".mp4" and p.stat().st_mtime >= start_t - 5
            ]
            if candidates:
                candidates.sort(key=lambda x: x.stat().st_mtime, reverse=True)
                shutil.copy2(str(candidates[0]), str(output_video_path))

        if output_video_path.exists() and output_video_path.stat().st_size > 0:
            print(f"\n{GREEN}[✓] Infinite Talk video generated successfully in {elapsed:.1f}s!{RESET}")
            print(f"    Saved: {BOLD}{output_video_path}{RESET}")
            return True
        else:
            print(f"\n{YELLOW}[!] Generation finished but output file was not found at expected path.{RESET}")
            return False

    finally:
        if task_json.exists():
            task_json.unlink(missing_ok=True)
        if trimmed_audio and trimmed_audio.exists():
            trimmed_audio.unlink(missing_ok=True)

def process_batch(config: dict, watch_mode: bool = False, interval: int = 5):
    """Run batch processing on WAN2GP_INFTLKBATCH directory."""
    batch_dir = Path(config.get("batch_dir", str(DEFAULT_BATCH_DIR)))
    outputs_dir = Path(config.get("outputs_dir", str(DEFAULT_OUTPUTS_DIR)))
    ensure_batch_directory_structure(batch_dir, outputs_dir)

    ctrl_images = get_control_images(batch_dir)
    if not ctrl_images:
        print(f"{RED}[-] Error: No control images found in {batch_dir / 'CTRL_IMAGE'}{RESET}")
        print(f"    Please place an avatar image (e.g. Stephen_Hawking.png) into {batch_dir / 'CTRL_IMAGE'}")
        return

    # Select active control image from config or first available
    active_ctrl_img_name = config.get("active_ctrl_image", "Stephen_Hawking.png")
    matched = [img for img in ctrl_images if img.name.lower() == active_ctrl_img_name.lower()]
    ctrl_img = matched[0] if matched else ctrl_images[0]

    voice_catalog = get_voice_catalog(config)
    active_vid = config.get("active_voice", "stephen_hawking")
    v_match = [v for v in voice_catalog if v["id"] == active_vid]
    voice_info = v_match[0] if v_match else voice_catalog[0]

    processed_dir = batch_dir / "PROCESSED"
    tts_converted_dir = batch_dir / "TTS_CONVERTED"
    batch_outputs_dir = batch_dir / "OUTPUTS"

    print(f"\n{BOLD}{MAGENTA}======================================================{RESET}")
    print(f"{BOLD}{MAGENTA}      MP INFINITE TALKER BATCH VIDEO GENERATOR        {RESET}")
    print(f"{BOLD}{MAGENTA}======================================================{RESET}")
    print(f"  Batch Directory:  {YELLOW}{batch_dir}{RESET}")
    print(f"  Control Avatar:   {GREEN}{ctrl_img.name}{RESET}")
    print(f"  Active Voice:     {CYAN}{voice_info['name']}{RESET}")
    print(f"  Outputs (Batch):  {GREEN}{batch_outputs_dir}{RESET}")
    print(f"  Outputs (Global): {GREEN}{outputs_dir}{RESET}")
    print(f"  Mode:             {BOLD}{'CONTINUOUS WATCH MODE' if watch_mode else 'SINGLE PASS BATCH'}{RESET}")
    print(f"{MAGENTA}------------------------------------------------------{RESET}")

    check_and_resolve_running_server()

    def process_item(item: Path) -> bool:
        stem = item.stem
        date_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        out_name = f"{stem}_InfiniteTalk_{date_str}.mp4"
        batch_out_video = batch_outputs_dir / out_name
        global_out_video = outputs_dir / out_name

        print(f"\n{BOLD}[*] Processing file: {YELLOW}{item.name}{RESET}")

        driving_wav = None
        if item.suffix.lower() in SUPPORTED_TEXT_EXTS:
            try:
                with open(item, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read().strip()
                if not content:
                    print(f"{YELLOW}[!] Empty text file: {item.name}, skipping.{RESET}")
                    return False
                driving_wav = tts_converted_dir / f"{stem}_{date_str}.wav"
                print(f"{CYAN}[*] Synthesizing speech with voice: {voice_info['name']}...{RESET}")
                ok_synth = generate_speech_for_text(content, voice_info, driving_wav)
                if not ok_synth:
                    print(f"{RED}[-] Failed to synthesize speech for {item.name}{RESET}")
                    return False
            except Exception as e:
                print(f"{RED}[-] Read/synthesis error: {e}{RESET}")
                return False
        elif item.suffix.lower() in SUPPORTED_AUDIO_EXTS:
            driving_wav = item

        if not driving_wav or not driving_wav.exists():
            print(f"{RED}[-] Driving audio not found for {item.name}{RESET}")
            return False

        # Run Infinite Talk generation
        ok_gen = generate_infinite_talk_video(
            ctrl_image=ctrl_img,
            audio_path=driving_wav,
            output_video_path=batch_out_video,
            resolution=config.get("resolution", "832x480"),
            profile=config.get("profile", "4.5"),
            steps=int(config.get("steps", 4)),
        )

        if ok_gen and batch_out_video.exists():
            # Mirror to global outputs directory
            try:
                shutil.copy2(str(batch_out_video), str(global_out_video))
            except Exception:
                pass

            # Move original input to PROCESSED/
            try:
                dest = processed_dir / f"{date_str}_{item.name}"
                shutil.move(str(item), str(dest))
                print(f"{GREEN}[✓] Moved input to: {dest.name}{RESET}")
            except Exception as e:
                print(f"{YELLOW}[!] Could not move input file: {e}{RESET}")

            return True
        return False

    if watch_mode:
        print(f"\n{GREEN}[✓] Watch Mode active. Drop .txt or .wav files into {batch_dir} to process automatically.{RESET}")
        print(f"{DIM}Press Ctrl+C to stop watch mode.{RESET}\n")
        try:
            while True:
                files = [
                    f for f in batch_dir.iterdir()
                    if f.is_file() and (f.suffix.lower() in SUPPORTED_TEXT_EXTS or f.suffix.lower() in SUPPORTED_AUDIO_EXTS)
                ]
                if files:
                    print(f"\n{BOLD}{GREEN}[+] Detected {len(files)} new file(s) to process!{RESET}")
                    for f in files:
                        process_item(f)
                time.sleep(interval)
        except KeyboardInterrupt:
            print(f"\n{YELLOW}[*] Watch mode terminated by user.{RESET}")
    else:
        files = [
            f for f in batch_dir.iterdir()
            if f.is_file() and (f.suffix.lower() in SUPPORTED_TEXT_EXTS or f.suffix.lower() in SUPPORTED_AUDIO_EXTS)
        ]
        if not files:
            print(f"\n{YELLOW}[i] No pending text (.txt) or audio (.wav) files found in {batch_dir}.{RESET}")
            print(f"    Drop text or audio files there, or use Watch Mode / Single Video Generation.")
            return
        print(f"\n{CYAN}[+] Found {len(files)} pending file(s) in batch directory.{RESET}")
        success_count = 0
        for f in files:
            if process_item(f):
                success_count += 1
        print(f"\n{GREEN}=================================================={RESET}")
        print(f"{BOLD}{GREEN}✓ Batch completed: {success_count}/{len(files)} video(s) generated successfully!{RESET}")
        print(f"{GREEN}=================================================={RESET}")

def run_single_video_flow(config: dict):
    """Interactive flow to generate a single Infinite Talk video."""
    batch_dir = Path(config.get("batch_dir", str(DEFAULT_BATCH_DIR)))
    outputs_dir = Path(config.get("outputs_dir", str(DEFAULT_OUTPUTS_DIR)))
    ensure_batch_directory_structure(batch_dir, outputs_dir)

    ctrl_images = get_control_images(batch_dir)
    if not ctrl_images:
        print(f"{RED}[-] Error: No avatar images found in {batch_dir / 'CTRL_IMAGE'}{RESET}")
        return

    active_ctrl_img_name = config.get("active_ctrl_image", "Stephen_Hawking.png")
    matched = [img for img in ctrl_images if img.name.lower() == active_ctrl_img_name.lower()]
    ctrl_img = matched[0] if matched else ctrl_images[0]

    voice_catalog = get_voice_catalog(config)
    active_vid = config.get("active_voice", "stephen_hawking")
    v_match = [v for v in voice_catalog if v["id"] == active_vid]
    voice_info = v_match[0] if v_match else voice_catalog[0]

    print(f"\n{BOLD}{CYAN}=== GENERATE SINGLE INFINITE TALK VIDEO ==={RESET}")
    print(f"  Avatar: {GREEN}{ctrl_img.name}{RESET}")
    print(f"  Voice:  {CYAN}{voice_info['name']}{RESET}")
    print("\nHow would you like to provide the speech content?")
    print("  1) Type or paste text directly (Stephen Hawking will read it)")
    print("  2) Select a text file (.txt, .md, .log)")
    print("  3) Select an audio file (.wav, .mp3)")
    print("  4) Select latest MP Reporter Report transcript")
    print("  0) Cancel")

    ch = input("\nEnter choice [1-4, 0]: ").strip()
    if ch == "0" or ch.lower() in ("q", "cancel"):
        return

    input_text = ""
    audio_path = None

    if ch == "1":
        print(f"\nEnter text for Stephen Hawking to speak (Press Enter when done):")
        input_text = input("> ").strip()
        if not input_text:
            print(f"{YELLOW}No text entered. Generation cancelled.{RESET}")
            return
    elif ch == "2":
        path_str = input("Enter path to text file: ").strip().strip('"').strip("'")
        p = Path(path_str)
        if not p.exists():
            print(f"{RED}File not found: {path_str}{RESET}")
            return
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            input_text = f.read().strip()
    elif ch == "3":
        path_str = input("Enter path to audio file: ").strip().strip('"').strip("'")
        p = Path(path_str)
        if not p.exists():
            print(f"{RED}Audio file not found: {path_str}{RESET}")
            return
        audio_path = p
    elif ch == "4":
        # Search MP Reporter TTS Audio directory
        rep_tts = Path("/var/home/mplanetarian/MP_REPORTER/TTS_AUDIO")
        candidates = []
        if rep_tts.exists():
            for f in rep_tts.rglob("*.wav"):
                if f.is_file() and f.stat().st_size > 0:
                    candidates.append(f)
        if candidates:
            candidates.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            print(f"\n{CYAN}Found recent MP Reporter audio reports:{RESET}")
            for idx, c in enumerate(candidates[:5], 1):
                mtime_str = datetime.datetime.fromtimestamp(c.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
                print(f"  {idx}) {c.name} ({mtime_str})")
            sel = input(f"Select report [1-{min(5, len(candidates))} (Default: 1)]: ").strip()
            sel_idx = int(sel) - 1 if sel.isdigit() and 1 <= int(sel) <= len(candidates[:5]) else 0
            audio_path = candidates[sel_idx]
            print(f"{GREEN}Selected report audio: {audio_path.name}{RESET}")
        else:
            print(f"{YELLOW}No pre-recorded MP Reporter audio files found.{RESET}")
            return
    else:
        print(f"{RED}Invalid option.{RESET}")
        return

    # Synthesize audio if text was provided
    if input_text:
        date_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        audio_path = batch_dir / "TTS_CONVERTED" / f"Single_Speech_{date_str}.wav"
        print(f"{CYAN}[*] Synthesizing speech with voice: {voice_info['name']}...{RESET}")
        ok = generate_speech_for_text(input_text, voice_info, audio_path)
        if not ok or not audio_path.exists():
            print(f"{RED}[-] Failed to synthesize speech.{RESET}")
            return

    date_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_video = batch_dir / "OUTPUTS" / f"InfiniteTalk_{ctrl_img.stem}_{date_str}.mp4"
    global_video = outputs_dir / f"InfiniteTalk_{ctrl_img.stem}_{date_str}.mp4"

    ok_gen = generate_infinite_talk_video(
        ctrl_image=ctrl_img,
        audio_path=audio_path,
        output_video_path=out_video,
        resolution=config.get("resolution", "832x480"),
        profile=config.get("profile", "4.5"),
        steps=int(config.get("steps", 4)),
    )

    if ok_gen and out_video.exists():
        try:
            shutil.copy2(str(out_video), str(global_video))
        except Exception:
            pass
        print(f"\n{BOLD}{GREEN}✓ Single video generation complete!{RESET}")
        print(f"  Video path: {BOLD}{out_video}{RESET}")
        ans = input("\nWould you like to play / preview the video now? [Y/n]: ").strip().lower()
        if ans in ("", "y", "yes"):
            play_video_file(out_video)

def play_video_file(video_path: Path):
    """Play video using available system media player."""
    for player in ["mpv", "vlc", "xdg-open", "kde-open"]:
        if shutil.which(player):
            try:
                subprocess.Popen([player, str(video_path)])
                return
            except Exception:
                pass
    print(f"{YELLOW}No media player (mpv/vlc) found to preview video.{RESET}")

def manage_voices_flow(config: dict):
    """Manage voices, select active, or add new voices."""
    while True:
        voices = get_voice_catalog(config)
        active_vid = config.get("active_voice", "stephen_hawking")

        print(f"\n{BOLD}{MAGENTA}=================================================={RESET}")
        print(f"{BOLD}{MAGENTA}           INFINITE TALK VOICE MANAGER            {RESET}")
        print(f"{BOLD}{MAGENTA}=================================================={RESET}")
        print(f"  Active Voice: {BOLD}{GREEN}{active_vid}{RESET}\n")

        for idx, v in enumerate(voices, 1):
            is_act = f"{BOLD}{GREEN}● [ACTIVE]{RESET}" if v["id"] == active_vid else " "
            print(f"  {BOLD}{CYAN}{idx:2d}){RESET} {is_act} {BOLD}{v['name']}{RESET} ({v.get('gender', 'N/A')})")
            print(f"       {DIM}Engine: {v.get('engine', 'N/A')} | {v.get('desc', '')}{RESET}")

        print(f"\n  {BOLD}{CYAN}S)${RESET} Select Active Voice by Number")
        print(f"  {BOLD}{CYAN}A)${RESET} Add New Voice from Edge-TTS Catalog (Browse Languages/Accents)")
        print(f"  {BOLD}{CYAN}C)${RESET} Add New Voice from Custom Reference Audio Sample (.wav/.mp3)")
        print(f"  {BOLD}{CYAN}T)${RESET} Test / Audio Preview Active Voice")
        print(f"  {BOLD}{CYAN}0)${RESET} Return to Previous Menu (or 'q')")

        choice = input("\nEnter choice: ").strip().lower()
        if choice in ("0", "q", "exit"):
            break
        elif choice == "s":
            num = input(f"Enter voice number [1-{len(voices)}]: ").strip()
            if num.isdigit() and 1 <= int(num) <= len(voices):
                sel = voices[int(num) - 1]
                config["active_voice"] = sel["id"]
                save_user_config(config)
                print(f"{GREEN}✓ Active voice set to: {sel['name']}{RESET}")
                time.sleep(1)
        elif choice == "a":
            # Add new voice from edge-tts
            print(f"\n{CYAN}[*] Fetching Edge-TTS voice list...{RESET}")
            try:
                cmd = ["edge-tts", "--list-voices"]
                res = subprocess.run(cmd, capture_output=True, text=True)
                lines = [l.strip() for l in res.stdout.splitlines() if l.startswith("Name:")]
                print(f"Found {len(lines)} available voices in Edge-TTS catalog.")
                query = input("Filter by keyword/language (e.g. 'en-GB', 'en-US', 'Irish', 'French'): ").strip().lower()
                matches = []
                for l in res.stdout.split("Name: ")[1:]:
                    parts = l.splitlines()
                    name = parts[0].strip()
                    gender = ""
                    for p in parts[1:4]:
                        if "Gender:" in p:
                            gender = p.replace("Gender:", "").strip()
                    if not query or query in name.lower() or query in l.lower():
                        matches.append((name, gender))

                if matches:
                    print(f"\nMatching voices (showing up to 15):")
                    for idx, (m_name, m_gen) in enumerate(matches[:15], 1):
                        print(f"  {idx}) {m_name} ({m_gen})")
                    v_choice = input(f"Select voice number [1-{min(15, len(matches))}]: ").strip()
                    if v_choice.isdigit() and 1 <= int(v_choice) <= min(15, len(matches)):
                        chosen_name, chosen_gen = matches[int(v_choice) - 1]
                        friendly_name = input(f"Enter a friendly label for this voice [{chosen_name}]: ").strip() or chosen_name
                        new_voice = {
                            "id": chosen_name,
                            "name": f"{friendly_name} (Edge Neural)",
                            "gender": chosen_gen,
                            "engine": "edge",
                            "desc": f"Added Edge-TTS Neural Voice: {chosen_name}",
                        }
                        if "custom_voices" not in config:
                            config["custom_voices"] = []
                        config["custom_voices"].append(new_voice)
                        config["active_voice"] = chosen_name
                        save_user_config(config)
                        print(f"{GREEN}✓ Added and activated new voice: {new_voice['name']}{RESET}")
                        time.sleep(1.5)
                else:
                    print(f"{YELLOW}No voices matched '{query}'.{RESET}")
            except Exception as e:
                print(f"{RED}Error fetching voices: {e}{RESET}")
        elif choice == "c":
            # Add custom reference audio
            sample_path = input("Enter path to custom voice audio (.wav/.mp3): ").strip().strip('"').strip("'")
            sp = Path(sample_path)
            if sp.exists() and sp.is_file():
                voices_dir = Path(config.get("batch_dir", str(DEFAULT_BATCH_DIR))) / "VOICES"
                voices_dir.mkdir(parents=True, exist_ok=True)
                dest = voices_dir / sp.name
                shutil.copy2(str(sp), str(dest))
                friendly = input(f"Enter name for this voice [{sp.stem}]: ").strip() or sp.stem
                new_voice = {
                    "id": f"sample:{dest.name}",
                    "name": f"{friendly} (Custom Voice)",
                    "gender": "Custom",
                    "engine": "audio_sample",
                    "sample_path": str(dest.resolve()),
                    "desc": f"Custom driving audio sample from {dest.name}",
                }
                if "custom_voices" not in config:
                    config["custom_voices"] = []
                config["custom_voices"].append(new_voice)
                config["active_voice"] = new_voice["id"]
                save_user_config(config)
                print(f"{GREEN}✓ Added and activated custom voice: {new_voice['name']}{RESET}")
                time.sleep(1.5)
            else:
                print(f"{RED}File not found: {sample_path}{RESET}")
        elif choice == "t":
            # Test active voice
            v_match = [v for v in voices if v["id"] == active_vid]
            v_info = v_match[0] if v_match else voices[0]
            test_wav = Path(tempfile.mktemp(suffix=".wav"))
            print(f"\n{CYAN}[*] Generating 3-second audio preview with {v_info['name']}...{RESET}")
            test_phrase = "Hello, this is a test of the speech synthesizer for Infinite Talk."
            ok = generate_speech_for_text(test_phrase, v_info, test_wav)
            if ok and test_wav.exists():
                print(f"{GREEN}[✓] Audio preview ready. Playing...{RESET}")
                for ply in ["pw-play", "paplay", "mpv", "ffplay"]:
                    if shutil.which(ply):
                        subprocess.run([ply, str(test_wav)], capture_output=True)
                        break
                test_wav.unlink(missing_ok=True)
            else:
                print(f"{RED}[-] Failed to generate audio preview.{RESET}")

def manage_control_images_flow(config: dict):
    """Select active control avatar image."""
    batch_dir = Path(config.get("batch_dir", str(DEFAULT_BATCH_DIR)))
    ctrl_dir = batch_dir / "CTRL_IMAGE"
    ctrl_dir.mkdir(parents=True, exist_ok=True)

    imgs = get_control_images(batch_dir)
    active_name = config.get("active_ctrl_image", "Stephen_Hawking.png")

    print(f"\n{BOLD}{CYAN}=== SELECT ACTIVE AVATAR / CONTROL IMAGE ==={RESET}")
    print(f"Directory: {ctrl_dir}\n")
    if not imgs:
        print(f"{YELLOW}No images found in {ctrl_dir}.{RESET}")
        return

    for idx, img in enumerate(imgs, 1):
        is_act = f"{BOLD}{GREEN}● [ACTIVE]{RESET}" if img.name.lower() == active_name.lower() else " "
        print(f"  {idx}) {is_act} {img.name}")

    sel = input(f"\nEnter choice [1-{len(imgs)}, 0 to cancel]: ").strip()
    if sel.isdigit() and 1 <= int(sel) <= len(imgs):
        chosen = imgs[int(sel) - 1]
        config["active_ctrl_image"] = chosen.name
        save_user_config(config)
        print(f"{GREEN}✓ Active avatar image set to: {chosen.name}{RESET}")
        time.sleep(1)

def configure_directories_flow(config: dict):
    """Configure batch and output directory locations."""
    print(f"\n{BOLD}{CYAN}=== CONFIGURE INFINITE TALK DIRECTORIES ==={RESET}")
    print(f"Current Batch Directory:   {GREEN}{config.get('batch_dir')}{RESET}")
    print(f"Current Outputs Directory: {GREEN}{config.get('outputs_dir')}{RESET}\n")

    nb = input(f"Enter new Batch Directory [Press Enter to keep current]: ").strip()
    if nb:
        p = Path(nb)
        p.mkdir(parents=True, exist_ok=True)
        config["batch_dir"] = str(p.resolve())
        os.environ["WAN2GP_INFTLKBATCH_DIR"] = str(p.resolve())

    no = input(f"Enter new Outputs Directory [Press Enter to keep current]: ").strip()
    if no:
        p = Path(no)
        p.mkdir(parents=True, exist_ok=True)
        config["outputs_dir"] = str(p.resolve())
        os.environ["WAN2GP_OUTPUTS"] = str(p.resolve())

    save_user_config(config)
    ensure_batch_directory_structure(Path(config["batch_dir"]), Path(config["outputs_dir"]))
    print(f"{GREEN}✓ Directories updated and verified.{RESET}")
    time.sleep(1)

def view_generated_videos_flow(config: dict):
    """Browse and play generated videos."""
    batch_dir = Path(config.get("batch_dir", str(DEFAULT_BATCH_DIR)))
    batch_out = batch_dir / "OUTPUTS"
    global_out = Path(config.get("outputs_dir", str(DEFAULT_OUTPUTS_DIR)))

    videos = []
    for d in [batch_out, global_out]:
        if d.exists():
            for f in d.iterdir():
                if f.is_file() and f.suffix.lower() == ".mp4" and f not in videos:
                    videos.append(f)

    if not videos:
        print(f"\n{YELLOW}No generated videos found yet in outputs folders.{RESET}")
        input("Press Enter to continue...")
        return

    videos.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    print(f"\n{BOLD}{CYAN}=== RECENTLY GENERATED INFINITE TALK VIDEOS ==={RESET}\n")
    for idx, v in enumerate(videos[:10], 1):
        mtime = datetime.datetime.fromtimestamp(v.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        size_mb = v.stat().st_size / (1024 * 1024)
        print(f"  {idx:2d}) {v.name} ({size_mb:.1f} MB, {mtime})")

    sel = input(f"\nSelect video to play [1-{min(10, len(videos))}, 0 to cancel]: ").strip()
    if sel.isdigit() and 1 <= int(sel) <= min(10, len(videos)):
        play_video_file(videos[int(sel) - 1])

def process_mp_reporter_report(report_path: Path, config: dict) -> bool:
    """Read a report from MP Reporter and generate a Stephen Hawking Infinite Talk video."""
    batch_dir = Path(config.get("batch_dir", str(DEFAULT_BATCH_DIR)))
    outputs_dir = Path(config.get("outputs_dir", str(DEFAULT_OUTPUTS_DIR)))
    ensure_batch_directory_structure(batch_dir, outputs_dir)

    ctrl_images = get_control_images(batch_dir)
    ctrl_img = ctrl_images[0] if ctrl_images else None
    if not ctrl_img:
        print(f"{RED}[-] Error: Stephen Hawking avatar not found in {batch_dir / 'CTRL_IMAGE'}{RESET}")
        return False

    date_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    stem = report_path.stem

    audio_path = None
    if report_path.suffix.lower() == ".wav":
        audio_path = report_path
    elif report_path.suffix.lower() == ".pdf":
        # Extract text from PDF
        txt_out = Path(tempfile.mktemp(suffix=".txt"))
        subprocess.run(["pdftotext", str(report_path), str(txt_out)], capture_output=True)
        if txt_out.exists() and txt_out.stat().st_size > 0:
            with open(txt_out, "r", encoding="utf-8", errors="replace") as f:
                content = f.read().strip()
            txt_out.unlink(missing_ok=True)
            # Synthesize Stephen Hawking speech
            audio_path = batch_dir / "TTS_CONVERTED" / f"Report_{stem}_{date_str}.wav"
            print(f"{CYAN}[*] Synthesizing Stephen Hawking voice for report: {stem}...{RESET}")
            synthesize_hawking_speech(content, audio_path)
    elif report_path.suffix.lower() in SUPPORTED_TEXT_EXTS:
        with open(report_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read().strip()
        audio_path = batch_dir / "TTS_CONVERTED" / f"Report_{stem}_{date_str}.wav"
        print(f"{CYAN}[*] Synthesizing Stephen Hawking voice for report: {stem}...{RESET}")
        synthesize_hawking_speech(content, audio_path)

    if not audio_path or not audio_path.exists():
        print(f"{RED}[-] Failed to prepare audio for report: {report_path.name}{RESET}")
        return False

    out_video = outputs_dir / f"Stephen_Hawking_Report_{stem}_{date_str}.mp4"
    batch_video = batch_dir / "OUTPUTS" / f"Stephen_Hawking_Report_{stem}_{date_str}.mp4"

    ok = generate_infinite_talk_video(
        ctrl_image=ctrl_img,
        audio_path=audio_path,
        output_video_path=out_video,
        prompt="Stephen Hawking sitting in his high-tech wheelchair in a modern scientific library reading an analytical report to the camera, photorealistic 8k, ultra-detailed expressions, cinematic lighting",
        resolution=config.get("resolution", "832x480"),
        profile=config.get("profile", "4.5"),
        steps=int(config.get("steps", 4)),
        duration=float(config.get("duration", 0.0)),
    )
    if ok and out_video.exists():
        try:
            shutil.copy2(str(out_video), str(batch_video))
        except Exception:
            pass
        return True
    return False

def interactive_main_menu():
    """Main interactive terminal UI for MP Infinite Talker."""
    config = load_user_config()
    batch_dir = Path(config.get("batch_dir", str(DEFAULT_BATCH_DIR)))
    outputs_dir = Path(config.get("outputs_dir", str(DEFAULT_OUTPUTS_DIR)))
    ensure_batch_directory_structure(batch_dir, outputs_dir)

    while True:
        ctrl_images = get_control_images(batch_dir)
        active_ctrl_img_name = config.get("active_ctrl_image", "Stephen_Hawking.png")
        matched = [img for img in ctrl_images if img.name.lower() == active_ctrl_img_name.lower()]
        ctrl_img_name = matched[0].name if matched else (ctrl_images[0].name if ctrl_images else "None")

        voice_catalog = get_voice_catalog(config)
        active_vid = config.get("active_voice", "stephen_hawking")
        v_match = [v for v in voice_catalog if v["id"] == active_vid]
        voice_name = v_match[0]["name"] if v_match else active_vid

        pending_files = [
            f for f in batch_dir.iterdir()
            if f.is_file() and (f.suffix.lower() in SUPPORTED_TEXT_EXTS or f.suffix.lower() in SUPPORTED_AUDIO_EXTS)
        ]

        # Check server status
        server_status = f"{RED}○ STOPPED{RESET}"
        wgp_pids = subprocess.run(["pgrep", "-f", "python.*wgp\\.py"], capture_output=True, text=True)
        if wgp_pids.returncode == 0 and wgp_pids.stdout.strip():
            server_status = f"{GREEN}● RUNNING (PID: {wgp_pids.stdout.strip()}){RESET}"

        os.system("clear" if os.name != "nt" else "cls")
        print(f"{BOLD}{MAGENTA}======================================================================{RESET}")
        print(f"{BOLD}{MAGENTA}       MP INFINITE TALKER - WAN2GP AI VIDEO & SPEECH SUITE            {RESET}")
        print(f"{BOLD}{MAGENTA}======================================================================{RESET}")
        print(f"  Batch Directory:  {BOLD}{CYAN}{batch_dir}{RESET}")
        print(f"  Outputs Directoy: {BOLD}{CYAN}{outputs_dir}{RESET}")
        print(f"  Active Avatar:    {BOLD}{GREEN}{ctrl_img_name}{RESET} (in CTRL_IMAGE/)")
        print(f"  Active Voice:     {BOLD}{GREEN}{voice_name}{RESET}")
        print(f"  Pending Batch:    {BOLD}{YELLOW}{len(pending_files)} file(s) awaiting conversion{RESET}")
        print(f"  WAN2GP Status:    {server_status}")
        print(f"  Model Engine:     {CYAN}Wan2.1 InfiniteTalk 14B (Single Speaker / 81-frame window){RESET}")
        print(f"{MAGENTA}----------------------------------------------------------------------{RESET}")
        print(f"{BOLD}Select an operation:{RESET}")
        print(f"  {BOLD}{CYAN}1)${RESET} Run Batch Video Processor {GREEN}(Convert all pending .txt / .wav files){RESET}")
        print(f"  {BOLD}{CYAN}2)${RESET} Run Batch in {BOLD}{GREEN}Watch Mode{RESET} (Continuous real-time directory processing)")
        print(f"  {BOLD}{CYAN}3)${RESET} Generate Single Video (Interactive Text / Speech Input / Report)")
        print(f"  {BOLD}{CYAN}4)${RESET} Generate Video from MP Reporter Report (Stephen Hawking Reading Report)")
        print(f"  {BOLD}{CYAN}5)${RESET} Voice Manager & Add New Voices (Stephen Hawking, Edge Neural, Custom)")
        print(f"  {BOLD}{CYAN}6)${RESET} Select Active Control Avatar Image (Stephen Hawking default or custom)")
        print(f"  {BOLD}{CYAN}7)${RESET} Browse & Play Generated Infinite Talk Videos")
        print(f"  {BOLD}{CYAN}8)${RESET} Configure Batch & Output Directory Paths")
        print(f"  {BOLD}{CYAN}0)${RESET} Return to Previous Menu (or 'q')")
        print(f"{MAGENTA}----------------------------------------------------------------------{RESET}")

        ch = input("Enter choice [1-8, 0]: ").strip().lower()
        if ch in ("0", "q", "exit"):
            break
        elif ch == "1":
            process_batch(config, watch_mode=False)
            input("\nPress Enter to return to menu...")
        elif ch == "2":
            process_batch(config, watch_mode=True)
            input("\nPress Enter to return to menu...")
        elif ch == "3":
            run_single_video_flow(config)
            input("\nPress Enter to return to menu...")
        elif ch == "4":
            # MP Reporter Report Selector
            rep_pdf = Path("/var/home/mplanetarian/MP_REPORTER/PDF_REPORTS")
            pdfs = list(rep_pdf.rglob("*.pdf")) if rep_pdf.exists() else []
            if pdfs:
                pdfs.sort(key=lambda x: x.stat().st_mtime, reverse=True)
                print(f"\n{CYAN}Recent MP Reporter PDF reports:{RESET}")
                for idx, p in enumerate(pdfs[:8], 1):
                    mtime = datetime.datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
                    print(f"  {idx}) {p.name} ({mtime})")
                sel = input(f"\nSelect report [1-{min(8, len(pdfs))}, 0 to cancel]: ").strip()
                if sel.isdigit() and 1 <= int(sel) <= min(8, len(pdfs)):
                    chosen_report = pdfs[int(sel) - 1]
                    print(f"\n{GREEN}[*] Generating Stephen Hawking video report for: {chosen_report.name}...{RESET}")
                    process_mp_reporter_report(chosen_report, config)
            else:
                print(f"{YELLOW}No MP Reporter PDF files found in {rep_pdf}.{RESET}")
            input("\nPress Enter to return to menu...")
        elif ch == "5":
            manage_voices_flow(config)
        elif ch == "6":
            manage_control_images_flow(config)
        elif ch == "7":
            view_generated_videos_flow(config)
        elif ch == "8":
            configure_directories_flow(config)
        else:
            print(f"{RED}Invalid selection!{RESET}")
            time.sleep(1)

def main():
    parser = argparse.ArgumentParser(description="MP Infinite Talker - WAN2GP Video Generation & Batch Suite")
    parser.add_argument("--batch", action="store_true", help="Run batch processing on pending files")
    parser.add_argument("--watch", action="store_true", help="Run batch processor in watch mode")
    parser.add_argument("--interval", type=int, default=5, help="Poll interval in seconds for watch mode")
    parser.add_argument("--batch-dir", type=str, default="", help="Batch workspace directory")
    parser.add_argument("--output-dir", type=str, default="", help="Outputs directory for videos")
    parser.add_argument("--ctrl-image", type=str, default="", help="Control avatar image path")
    parser.add_argument("--voice", type=str, default="", help="Voice ID (e.g. stephen_hawking, en-GB-RyanNeural)")
    parser.add_argument("--single", type=str, default="", help="Generate single video from text string")
    parser.add_argument("--text-file", type=str, default="", help="Generate video from text file")
    parser.add_argument("--audio", type=str, default="", help="Generate video directly from audio file")
    parser.add_argument("--report", type=str, default="", help="Generate Stephen Hawking video from MP Reporter report (.pdf/.txt/.wav)")
    parser.add_argument("--list-voices", action="store_true", help="List all available voices and exit")
    parser.add_argument("--profile", type=str, default="4.5", help="WAN2GP memory profile (default: 4.5)")
    parser.add_argument("--steps", type=int, default=4, help="Inference steps (default: 4)")
    parser.add_argument("--resolution", type=str, default="832x480", help="Output resolution (default: 832x480)")
    parser.add_argument("--duration", type=float, default=0.0, help="Duration limit in seconds (0 for full)")
    args = parser.parse_args()

    config = load_user_config()
    if args.batch_dir:
        config["batch_dir"] = args.batch_dir
    if args.output_dir:
        config["outputs_dir"] = args.output_dir
    if args.voice:
        config["active_voice"] = args.voice
    if args.ctrl_image:
        config["active_ctrl_image"] = args.ctrl_image
    if args.profile:
        config["profile"] = args.profile
    if args.steps:
        config["steps"] = args.steps
    if args.resolution:
        config["resolution"] = args.resolution
    if args.duration > 0:
        config["duration"] = args.duration

    batch_dir = Path(config.get("batch_dir", str(DEFAULT_BATCH_DIR)))
    outputs_dir = Path(config.get("outputs_dir", str(DEFAULT_OUTPUTS_DIR)))
    ensure_batch_directory_structure(batch_dir, outputs_dir)

    if args.list_voices:
        voices = get_voice_catalog(config)
        print(f"\n{BOLD}{CYAN}=== AVAILABLE VOICES FOR INFINITE TALK ==={RESET}\n")
        for v in voices:
            print(f"  • {BOLD}{v['id']}{RESET} : {v['name']} ({v.get('gender', 'N/A')}) - {v.get('desc', '')}")
        print("")
        sys.exit(0)

    if args.report:
        rp = Path(args.report)
        if not rp.exists():
            print(f"{RED}[-] Error: Report file not found: {args.report}{RESET}")
            sys.exit(1)
        ok = process_mp_reporter_report(rp, config)
        sys.exit(0 if ok else 1)

    if args.single or args.text_file or args.audio:
        ctrl_images = get_control_images(batch_dir)
        ctrl_img = ctrl_images[0] if ctrl_images else None
        if not ctrl_img:
            print(f"{RED}[-] Error: No avatar image found in {batch_dir / 'CTRL_IMAGE'}{RESET}")
            sys.exit(1)

        date_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        audio_path = None

        if args.single:
            audio_path = batch_dir / "TTS_CONVERTED" / f"CLI_Single_{date_str}.wav"
            voice_cat = get_voice_catalog(config)
            v_match = [v for v in voice_cat if v["id"] == config.get("active_voice", "stephen_hawking")]
            v_info = v_match[0] if v_match else voice_cat[0]
            print(f"{CYAN}[*] Synthesizing speech with voice: {v_info['name']}...{RESET}")
            generate_speech_for_text(args.single, v_info, audio_path)
        elif args.text_file:
            tf = Path(args.text_file)
            if not tf.exists():
                print(f"{RED}Text file not found: {args.text_file}{RESET}")
                sys.exit(1)
            with open(tf, "r", encoding="utf-8", errors="replace") as f:
                content = f.read().strip()
            audio_path = batch_dir / "TTS_CONVERTED" / f"{tf.stem}_{date_str}.wav"
            voice_cat = get_voice_catalog(config)
            v_match = [v for v in voice_cat if v["id"] == config.get("active_voice", "stephen_hawking")]
            v_info = v_match[0] if v_match else voice_cat[0]
            generate_speech_for_text(content, v_info, audio_path)
        elif args.audio:
            af = Path(args.audio)
            if not af.exists():
                print(f"{RED}Audio file not found: {args.audio}{RESET}")
                sys.exit(1)
            audio_path = af

        out_video = outputs_dir / f"InfiniteTalk_{ctrl_img.stem}_{date_str}.mp4"
        ok = generate_infinite_talk_video(
            ctrl_image=ctrl_img,
            audio_path=audio_path,
            output_video_path=out_video,
            resolution=config.get("resolution", "832x480"),
            profile=config.get("profile", "4.5"),
            steps=int(config.get("steps", 4)),
        )
        sys.exit(0 if ok else 1)

    if args.watch:
        process_batch(config, watch_mode=True, interval=args.interval)
        sys.exit(0)

    if args.batch:
        process_batch(config, watch_mode=False)
        sys.exit(0)

    # Interactive menu by default
    interactive_main_menu()

if __name__ == "__main__":
    main()
