#!/usr/bin/env python3
"""
==============================================================================
wan2gp_tts_batch.py - WAN2GP Text-to-Speech (TTS) Batch Converter & Audio Player
==============================================================================
Converts text (.txt) files to uncompressed .wav speech audio files with full support
for British (English) and international female and male voices.

Workflows:
  - Input directory: /run/media/mplanetarian/GAMES1/DATA_DRIVE_MOVED/WAN2GP_TTSBATCH/
  - Outputs saved first to the same directory as .wav
  - After conversion, both the .wav and matching .txt are moved to TTS_CONVERTED/
    named with date and unique ID (e.g. YYYY-MM-DD_ID001_<filename>.[wav|txt])
  - Interactive playback menu to listen to converted speech files
  - Supports both Neural voices (Edge-TTS) and High-Speed Offline (eSpeak-NG)
==============================================================================
"""

import os
import sys
import re
import json
import time
import wave
import shutil
import datetime
import argparse
import subprocess
from pathlib import Path
from typing import List, Dict, Optional, Tuple

# Terminal color styling
GREEN = "\033[0;32m"
YELLOW = "\033[0;33m"
CYAN = "\033[0;36m"
RED = "\033[0;31m"
BOLD = "\033[1m"
MAGENTA = "\033[1;35m"
BLUE = "\033[1;34m"
DIM = "\033[2m"
RESET = "\033[0m"

# Default directories
PRIMARY_DATA_DIR = Path("/run/media/mplanetarian/GAMES1/DATA_DRIVE_MOVED")
FALLBACK_DATA_DIR = Path("/run/media/mplanetarian/DATA")
BASE_DATA_DIR = PRIMARY_DATA_DIR if PRIMARY_DATA_DIR.exists() else FALLBACK_DATA_DIR

DEFAULT_TTS_DIR = Path(os.environ.get("WAN2GP_TTSBATCH_DIR", BASE_DATA_DIR / "WAN2GP_TTSBATCH"))
CONFIG_FILE = Path.home() / ".config" / "wan2gp_tts_config.json"

# Voice catalog
VOICES: List[Dict[str, str]] = [
    # British (English) Voices (1-8)
    {
        "id": "en-GB-SoniaNeural",
        "name": "Sonia",
        "gender": "Female",
        "accent": "British (English)",
        "engine": "edge",
        "desc": "Natural, clear, warm British English (Neural)"
    },
    {
        "id": "en-GB-LibbyNeural",
        "name": "Libby",
        "gender": "Female",
        "accent": "British (English)",
        "engine": "edge",
        "desc": "Friendly, positive, polite British English (Neural)"
    },
    {
        "id": "en-GB-MaisieNeural",
        "name": "Maisie",
        "gender": "Female",
        "accent": "British (English)",
        "engine": "edge",
        "desc": "Cheerful, lively, conversational British English (Neural)"
    },
    {
        "id": "en-GB-RyanNeural",
        "name": "Ryan",
        "gender": "Male",
        "accent": "British (English)",
        "engine": "edge",
        "desc": "Professional, natural, articulate British English (Neural)"
    },
    {
        "id": "en-GB-ThomasNeural",
        "name": "Thomas",
        "gender": "Male",
        "accent": "British (English)",
        "engine": "edge",
        "desc": "Authoritative, calm, deep British English (Neural)"
    },
    {
        "id": "espeak:en-gb+f3",
        "name": "Emily (eSpeak)",
        "gender": "Female",
        "accent": "British (English)",
        "engine": "espeak",
        "desc": "Instant offline British female voice (High-Speed)"
    },
    {
        "id": "espeak:en-gb",
        "name": "George (eSpeak)",
        "gender": "Male",
        "accent": "British (English)",
        "engine": "espeak",
        "desc": "Instant offline British male voice (High-Speed)"
    },
    {
        "id": "espeak:en-gb-x-rp",
        "name": "Oliver RP (eSpeak)",
        "gender": "Male",
        "accent": "British (Received Pronunciation)",
        "engine": "espeak",
        "desc": "Received Pronunciation British male voice (Offline)"
    },
    # American (English) Voices (9-16)
    {
        "id": "en-US-JennyNeural",
        "name": "Jenny",
        "gender": "Female",
        "accent": "American (US)",
        "engine": "edge",
        "desc": "Clear, professional, versatile US English (Neural)"
    },
    {
        "id": "en-US-AriaNeural",
        "name": "Aria",
        "gender": "Female",
        "accent": "American (US)",
        "engine": "edge",
        "desc": "Confident, expressive, broadcast quality (Neural)"
    },
    {
        "id": "en-US-AvaNeural",
        "name": "Ava",
        "gender": "Female",
        "accent": "American (US)",
        "engine": "edge",
        "desc": "Pleasant, caring, conversational (Neural)"
    },
    {
        "id": "en-US-GuyNeural",
        "name": "Guy",
        "gender": "Male",
        "accent": "American (US)",
        "engine": "edge",
        "desc": "Warm, casual, conversational US English (Neural)"
    },
    {
        "id": "en-US-ChristopherNeural",
        "name": "Christopher",
        "gender": "Male",
        "accent": "American (US)",
        "engine": "edge",
        "desc": "Reliable, authoritative, documentary narration (Neural)"
    },
    {
        "id": "en-US-AndrewNeural",
        "name": "Andrew",
        "gender": "Male",
        "accent": "American (US)",
        "engine": "edge",
        "desc": "Warm, confident, natural (Neural)"
    },
    {
        "id": "espeak:en-us+f3",
        "name": "Sarah (eSpeak)",
        "gender": "Female",
        "accent": "American (US)",
        "engine": "espeak",
        "desc": "Instant offline US female voice (High-Speed)"
    },
    {
        "id": "espeak:en-us",
        "name": "Michael (eSpeak)",
        "gender": "Male",
        "accent": "American (US)",
        "engine": "espeak",
        "desc": "Instant offline US male voice (High-Speed)"
    },
    # Other Accents (17-20)
    {
        "id": "en-AU-NatashaNeural",
        "name": "Natasha",
        "gender": "Female",
        "accent": "Australian (en-AU)",
        "engine": "edge",
        "desc": "Friendly Australian female voice (Neural)"
    },
    {
        "id": "en-AU-WilliamNeural",
        "name": "William",
        "gender": "Male",
        "accent": "Australian (en-AU)",
        "engine": "edge",
        "desc": "Warm Australian male voice (Neural)"
    },
    {
        "id": "en-IE-OrlaNeural",
        "name": "Orla",
        "gender": "Female",
        "accent": "Irish (en-IE)",
        "engine": "edge",
        "desc": "Melodic Irish female voice (Neural)"
    },
    {
        "id": "en-IE-ColmNeural",
        "name": "Colm",
        "gender": "Male",
        "accent": "Irish (en-IE)",
        "engine": "edge",
        "desc": "Natural Irish male voice (Neural)"
    },
    # The Matrix Cast & Cinematic Voices (21 to 26)
    {
        "id": "agent_smith",
        "name": "Agent Smith",
        "gender": "Male",
        "accent": "The Matrix (Hugo Weaving)",
        "engine": "xtts",
        "xtts_voice": "agent_smith",
        "voice_name": "en-GB-ThomasNeural",
        "pitch": "-10Hz",
        "rate": "-4%",
        "desc": "Cold, menacing, hyper-precise Matrix agent voice (Hugo Weaving zero-shot XTTS-v2)"
    },
    {
        "id": "morpheus",
        "name": "Morpheus",
        "gender": "Male",
        "accent": "The Matrix (Laurence Fishburne)",
        "engine": "xtts",
        "xtts_voice": "morpheus",
        "voice_name": "en-US-ChristopherNeural",
        "pitch": "-4Hz",
        "rate": "-3%",
        "desc": "Deep, philosophical, commanding resonance of Laurence Fishburne (XTTS-v2 Master)"
    },
    {
        "id": "morpheus_construct",
        "name": "Morpheus (The Construct)",
        "gender": "Male",
        "accent": "The Matrix ('What is real?')",
        "engine": "xtts",
        "xtts_voice": "morpheus_construct",
        "voice_name": "en-US-ChristopherNeural",
        "pitch": "-4Hz",
        "rate": "-3%",
        "desc": "Expansive, contemplative philosophical delivery from the white Construct"
    },
    {
        "id": "morpheus_redpill",
        "name": "Morpheus (Red Pill)",
        "gender": "Male",
        "accent": "The Matrix ('Rabbit Hole')",
        "engine": "xtts",
        "xtts_voice": "morpheus_redpill",
        "voice_name": "en-US-ChristopherNeural",
        "pitch": "-4Hz",
        "rate": "-3%",
        "desc": "Intense, hypnotic cadence offering the red and blue pills"
    },
    {
        "id": "morpheus_dojo",
        "name": "Morpheus (Combat Dojo)",
        "gender": "Male",
        "accent": "The Matrix ('Free Your Mind')",
        "engine": "xtts",
        "xtts_voice": "morpheus_dojo",
        "voice_name": "en-US-ChristopherNeural",
        "pitch": "-4Hz",
        "rate": "-3%",
        "desc": "Commanding martial arts mentor pushing past perceived human limits"
    },
    {
        "id": "morpheus_system",
        "name": "Morpheus (The System)",
        "gender": "Male",
        "accent": "The Matrix ('Our Enemy')",
        "engine": "xtts",
        "xtts_voice": "morpheus_system",
        "voice_name": "en-US-ChristopherNeural",
        "pitch": "-4Hz",
        "rate": "-3%",
        "desc": "Tactical, solemn briefing on the nature of agents and the Matrix"
    },
    {
        "id": "neo",
        "name": "Neo",
        "gender": "Male",
        "accent": "The Matrix (Keanu Reeves)",
        "engine": "xtts",
        "xtts_voice": "neo",
        "voice_name": "en-US-BrianNeural",
        "pitch": "-4Hz",
        "rate": "-2%",
        "desc": "Calm, contemplative, determined voice of Keanu Reeves (The One)"
    },
    {
        "id": "trinity",
        "name": "Trinity",
        "gender": "Female",
        "accent": "The Matrix (Carrie-Anne Moss)",
        "engine": "xtts",
        "xtts_voice": "trinity",
        "voice_name": "en-US-AvaNeural",
        "pitch": "+0Hz",
        "rate": "+0%",
        "desc": "Focused, sharp, fearless cadence of Carrie-Anne Moss"
    },
    {
        "id": "oracle",
        "name": "The Oracle",
        "gender": "Female",
        "accent": "The Matrix (Gloria Foster)",
        "engine": "xtts",
        "xtts_voice": "oracle",
        "voice_name": "en-US-JennyNeural",
        "pitch": "-6Hz",
        "rate": "-6%",
        "desc": "Warm, motherly, enigmatic wisdom of Gloria Foster"
    },
    {
        "id": "zion",
        "name": "Councillor Hamann",
        "gender": "Male",
        "accent": "The Matrix (Anthony Zerbe)",
        "engine": "xtts",
        "xtts_voice": "zion",
        "voice_name": "en-US-RogerNeural",
        "pitch": "-8Hz",
        "rate": "-5%",
        "desc": "Wise, solemn elder statesman of Zion (Anthony Zerbe)"
    },
    {
        "id": "stephen_hawking_matrix",
        "name": "Stephen Hawking (Enters the Matrix)",
        "gender": "Male",
        "accent": "The Matrix (Robotic / Synth)",
        "engine": "espeak",
        "voice_code": "en-us+m3",
        "pitch_val": 19,
        "speed_wpm": 110,
        "af_filter": "bass=g=12:f=95:w=0.6, equalizer=f=2400:t=q:w=1.2:g=2, aecho=0.8:0.7:50|100:0.3|0.2",
        "desc": "Robotic synth entering the Matrix (Deep pitch -p 19, -s 110, bass boost & reverb)"
    }
]

DEFAULT_VOICE_ID = "en-GB-SoniaNeural"


def load_config() -> Dict[str, str]:
    """Load persistent user configuration."""
    cfg = {
        "voice_id": DEFAULT_VOICE_ID,
        "speed_rate": "+0%",
        "tts_dir": str(DEFAULT_TTS_DIR),
        "engine": "auto"
    }
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                if isinstance(saved, dict):
                    cfg.update(saved)
        except Exception:
            pass
    return cfg


def save_config(cfg: Dict[str, str]) -> None:
    """Save user configuration to disk."""
    try:
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception:
        pass


def pause_if_tty(prompt: str = "\nPress [Enter] to continue...") -> None:
    """Prompt user to press Enter only if connected to an interactive terminal."""
    if sys.stdin.isatty():
        try:
            input(f"{DIM}{prompt}{RESET}")
        except (EOFError, KeyboardInterrupt):
            pass


def get_voice_info(voice_id: str) -> Dict[str, str]:
    """Retrieve voice info dictionary by ID or name with alias mapping."""
    clean_id = voice_id.lower().strip()
    alias_map = {
        "morpheus": "morpheus",
        "morpheus_master": "morpheus",
        "morpheus master": "morpheus",
        "laurence_fishburne": "morpheus",
        "laurence fishburne": "morpheus",
        "construct": "morpheus_construct",
        "morpheus construct": "morpheus_construct",
        "redpill": "morpheus_redpill",
        "red pill": "morpheus_redpill",
        "morpheus redpill": "morpheus_redpill",
        "dojo": "morpheus_dojo",
        "combat dojo": "morpheus_dojo",
        "morpheus dojo": "morpheus_dojo",
        "system": "morpheus_system",
        "the system": "morpheus_system",
        "morpheus system": "morpheus_system",
        "smith": "agent_smith",
        "agent smith": "agent_smith",
        "elrond": "agent_smith",
        "the one": "neo",
        "the_one": "neo",
    }
    if clean_id in alias_map:
        clean_id = alias_map[clean_id]

    for v in VOICES:
        if v["id"].lower() == clean_id or v["name"].lower() == clean_id:
            return v
    for v in VOICES:
        if clean_id in v["id"].lower() or clean_id in v["name"].lower():
            return v
    return VOICES[0]


def sanitize_text_for_speech(raw_text: str) -> str:
    """Cleans raw text so that it sounds natural when spoken."""
    text = re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", " ", raw_text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[─═━│┃┄┅┌┐└┘├┤┬┴┼▄▀█▓▒░●○•◆◇▶▼▲◀★☆]+", " ", text)
    text = re.sub(r"[-_=~*]{3,}", " ", text)
    text = "".join(c for c in text if c.isprintable() or c in "\n\t")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
    return text.strip()


def get_audio_duration_seconds(path: Path) -> float:
    """Calculate the duration of a .wav file in seconds using standard library wave."""
    try:
        with wave.open(str(path), "rb") as w:
            frames = w.getnframes()
            rate = w.getframerate()
            if rate > 0:
                return frames / float(rate)
    except Exception:
        try:
            cmd = [
                "ffprobe", "-v", "error", "-show_entries",
                "format=duration", "-of", "default=noprint_wrappers=1:nokey=1",
                str(path)
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return float(res.stdout.strip())
        except Exception:
            pass
    return 0.0


def format_duration(seconds: float) -> str:
    """Format seconds into HH:MM:SS or MM:SS string."""
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def format_size(bytes_num: int) -> str:
    """Format bytes into human-readable size."""
    for unit in ["B", "KB", "MB", "GB"]:
        if bytes_num < 1024.0:
            return f"{bytes_num:.1f} {unit}"
        bytes_num /= 1024.0
    return f"{bytes_num:.1f} TB"


def get_next_id(converted_dir: Path, date_str: str) -> str:
    """Finds the next sequential ID for converted files."""
    max_id = 0
    if converted_dir.exists():
        pattern = re.compile(rf"{date_str}_ID(\d{{3,}})")
        for item in converted_dir.iterdir():
            match = pattern.search(item.name)
            if match:
                try:
                    num = int(match.group(1))
                    if num > max_id:
                        max_id = num
                except ValueError:
                    pass
        pattern_general = re.compile(r"ID(\d{3,})")
        for item in converted_dir.iterdir():
            match = pattern_general.search(item.name)
            if match:
                try:
                    num = int(match.group(1))
                    if num > max_id:
                        max_id = num
                except ValueError:
                    pass
    next_num = max_id + 1
    return f"ID{next_num:03d}"


def synthesize_speech_espeak(text: str, voice_code_or_id: str, output_wav: Path, speed_wpm: int = 130) -> bool:
    """Synthesize speech using local eSpeak-NG engine with optional pitch, speed, and audio filtering."""
    v_info = get_voice_info(voice_code_or_id)
    if v_info and (v_info["id"].lower() == voice_code_or_id.lower() or v_info.get("voice_code", "").lower() == voice_code_or_id.lower()):
        clean_voice = v_info.get("voice_code", v_info["id"]).replace("espeak:", "")
        pitch_val = str(v_info.get("pitch_val", 50))
        wpm = str(v_info.get("speed_wpm", speed_wpm))
        af_filter = v_info.get("af_filter", None)
    else:
        clean_voice = voice_code_or_id.replace("espeak:", "")
        pitch_val = "50"
        wpm = str(speed_wpm)
        af_filter = None

    temp_txt = output_wav.with_suffix(".tmp.txt")
    raw_wav = output_wav.with_suffix(".raw.wav") if af_filter else output_wav
    espeak_bin = "espeak-ng" if shutil.which("espeak-ng") else ("espeak" if shutil.which("espeak") else "espeak-ng")

    try:
        temp_txt.write_text(text, encoding="utf-8")
        cmd = [
            espeak_bin,
            "-v", clean_voice,
            "-s", wpm,
            "-p", pitch_val,
            "-f", str(temp_txt),
            "-w", str(raw_wav)
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0 or not raw_wav.exists() or raw_wav.stat().st_size <= 44:
            print(f"{RED}[-] eSpeak-NG failed: {res.stderr.strip()}{RESET}")
            return False

        if af_filter:
            cmd_filter = [
                "ffmpeg", "-y", "-v", "error",
                "-i", str(raw_wav),
                "-af", af_filter,
                str(output_wav)
            ]
            res_filter = subprocess.run(cmd_filter, capture_output=True, text=True)
            if res_filter.returncode != 0 or not output_wav.exists() or output_wav.stat().st_size <= 44:
                print(f"{RED}[-] FFmpeg filter failed: {res_filter.stderr.strip()}{RESET}")
                return False

        return True
    except Exception as e:
        print(f"{RED}[-] Error during eSpeak-NG synthesis: {e}{RESET}")
        return False
    finally:
        if temp_txt.exists():
            temp_txt.unlink()
        if af_filter and raw_wav.exists() and raw_wav != output_wav:
            raw_wav.unlink(missing_ok=True)


def split_text_into_chunks(text: str, max_chars: int = 4000) -> List[str]:
    """Split long text into coherent paragraphs/chunks for stable Edge-TTS processing."""
    paragraphs = text.split("\n\n")
    chunks = []
    current_chunk = []
    current_len = 0

    for p in paragraphs:
        p_clean = p.strip()
        if not p_clean:
            continue
        if current_len + len(p_clean) > max_chars and current_chunk:
            chunks.append("\n\n".join(current_chunk))
            current_chunk = [p_clean]
            current_len = len(p_clean)
        else:
            current_chunk.append(p_clean)
            current_len += len(p_clean) + 2

    if current_chunk:
        chunks.append("\n\n".join(current_chunk))
    return chunks if chunks else [text]


def concatenate_wav_files(wav_paths: List[Path], final_wav: Path) -> bool:
    """Concatenate multiple PCM WAV files into a single WAV file."""
    if not wav_paths:
        return False
    if len(wav_paths) == 1:
        shutil.copy2(wav_paths[0], final_wav)
        return True

    try:
        with wave.open(str(wav_paths[0]), "rb") as first:
            params = first.getparams()
            frames = [first.readframes(first.getnframes())]

        for p in wav_paths[1:]:
            with wave.open(str(p), "rb") as w:
                frames.append(w.readframes(w.getnframes()))

        with wave.open(str(final_wav), "wb") as out:
            out.setparams(params)
            for f in frames:
                out.writeframes(f)
        return True
    except Exception:
        concat_list = final_wav.with_suffix(".concat.txt")
        try:
            with open(concat_list, "w") as f:
                for wp in wav_paths:
                    f.write(f"file '{wp.resolve()}'\n")
            cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list), "-c", "copy", str(final_wav)]
            res = subprocess.run(cmd, capture_output=True, text=True)
            return res.returncode == 0
        except Exception:
            return False
        finally:
            if concat_list.exists():
                concat_list.unlink()


def synthesize_speech_edge(text: str, voice_id: str, output_wav: Path, rate: str = "+0%") -> bool:
    """Synthesize speech using Microsoft Edge Neural TTS with extreme audio distortions and ffmpeg filters."""
    edge_bin = Path.home() / ".local" / "bin" / "edge-tts"
    if not edge_bin.exists():
        edge_bin = Path("edge-tts")

    v_info = get_voice_info(voice_id)
    actual_voice_id = v_info.get("voice_name", v_info["id"])
    actual_rate = v_info.get("rate", rate)
    custom_pitch = v_info.get("pitch", None)

    chunks = split_text_into_chunks(text, max_chars=4000)
    temp_wavs = []
    temp_dir = output_wav.parent / ".tts_tmp"
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        for idx, chunk in enumerate(chunks, 1):
            if len(chunks) > 1:
                print(f"  {CYAN}Generating audio chunk {idx}/{len(chunks)} ({len(chunk)} characters)...{RESET}")
            chunk_txt = temp_dir / f"chunk_{idx}.txt"
            chunk_mp3 = temp_dir / f"chunk_{idx}.mp3"
            chunk_wav = temp_dir / f"chunk_{idx}.wav"
            chunk_txt.write_text(chunk, encoding="utf-8")

            cmd_tts = [
                str(edge_bin),
                "-f", str(chunk_txt),
                "-v", actual_voice_id,
                "--rate", actual_rate,
                "--write-media", str(chunk_mp3)
            ]
            if custom_pitch:
                cmd_tts.extend(["--pitch", custom_pitch])

            res_tts = subprocess.run(cmd_tts, capture_output=True, text=True, timeout=120)
            if res_tts.returncode != 0 or not chunk_mp3.exists() or chunk_mp3.stat().st_size == 0:
                print(f"{YELLOW}[!] Edge-TTS chunk {idx} failed: {res_tts.stderr.strip()}{RESET}")
                return False

            # Base conversion command
            cmd_conv = [
                "ffmpeg", "-y", "-v", "error",
                "-i", str(chunk_mp3)
            ]

            # If Agent Smith Edge fallback, ensure clean 24kHz clarity
            if v_info["id"] == "agent_smith":
                cmd_conv.extend([
                    "-af", "aformat=sample_fmts=s16:sample_rates=24000"
                ])

            cmd_conv.extend([
                "-ar", "24000", "-ac", "1", "-c:a", "pcm_s16le",
                str(chunk_wav)
            ])

            res_conv = subprocess.run(cmd_conv, capture_output=True, text=True)
            if res_conv.returncode != 0 or not chunk_wav.exists():
                return False

            temp_wavs.append(chunk_wav)

        success = concatenate_wav_files(temp_wavs, output_wav)
        return success and output_wav.exists() and output_wav.stat().st_size > 44
    except Exception as e:
        print(f"{RED}[-] Error during Edge-TTS generation: {e}{RESET}")
        return False
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def synthesize_speech_xtts(text: str, voice_id: str, output_wav: Path, speed: float = 1.0) -> bool:
    """Synthesize speech using local XTTS-v2 microservice on port 8020."""
    v_info = get_voice_info(voice_id)
    xtts_voice = v_info.get("xtts_voice", v_info["id"])
    xtts_url = os.environ.get("XTTS_URL", "http://127.0.0.1:8020")
    
    # Check if XTTS service is responding
    try:
        import urllib.request
        req_health = urllib.request.Request(f"{xtts_url}/health")
        with urllib.request.urlopen(req_health, timeout=1.5) as h_resp:
            if h_resp.status != 200:
                return False
    except Exception:
        return False

    # Split text into sentences for maximum XTTS quality
    import re
    text_clean = re.sub(r'\b(Mr|Mrs|Ms|Dr|Prof|Sr|Jr|vs|e\.g|i\.e)\.', r'\1<DOT>', text)
    raw_sentences = [s.strip().replace('<DOT>', '.') for s in re.split(r'(?<=[.!?])\s+', text_clean) if s.strip()]
    sentences = []
    for s in raw_sentences:
        if sentences and len(sentences[-1].split()) < 4:
            sentences[-1] = sentences[-1] + " " + s
        else:
            sentences.append(s)
    if not sentences:
        sentences = [text.strip()]

    temp_wavs = []
    temp_dir = output_wav.parent / ".tts_tmp_xtts"
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        for idx, sentence in enumerate(sentences, 1):
            if len(sentences) > 1:
                print(f"  {CYAN}Generating neural chunk {idx}/{len(sentences)} ({len(sentence)} chars)...{RESET}")
            chunk_wav = temp_dir / f"xtts_chunk_{idx}.wav"
            payload = json.dumps({
                "text": sentence,
                "voice": xtts_voice,
                "speed": speed
            }).encode("utf-8")

            req = urllib.request.Request(
                f"{xtts_url}/synthesize",
                data=payload,
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=45) as resp:
                if resp.status != 200:
                    return False
                audio_bytes = resp.read()
                if len(audio_bytes) < 100:
                    return False
                with open(chunk_wav, "wb") as f_out:
                    f_out.write(audio_bytes)

            temp_wavs.append(chunk_wav)

        success = concatenate_wav_files(temp_wavs, output_wav)
        return success and output_wav.exists() and output_wav.stat().st_size > 44
    except Exception as e:
        print(f"{YELLOW}[!] Error during XTTS synthesis: {e}{RESET}")
        return False
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def convert_text_to_speech(text_file: Path, voice_id: str, tts_dir: Path) -> Optional[Tuple[Path, Path]]:
    """Core conversion pipeline."""
    if not text_file.exists():
        print(f"{RED}[-] Error: File not found: {text_file}{RESET}")
        return None

    converted_dir = tts_dir / "TTS_CONVERTED"
    converted_dir.mkdir(parents=True, exist_ok=True)

    v_info = get_voice_info(voice_id)
    raw_content = text_file.read_text(encoding="utf-8", errors="ignore")
    cleaned_content = sanitize_text_for_speech(raw_content)

    if not cleaned_content:
        print(f"{RED}[-] Error: File {text_file.name} is empty or contains no speakable text.{RESET}")
        return None

    char_count = len(cleaned_content)
    word_count = len(cleaned_content.split())
    original_stem = text_file.stem
    initial_wav = tts_dir / f"{original_stem}.wav"

    print(f"\n{BOLD}{CYAN}══════════════════════════════════════════════════════════════{RESET}")
    print(f"{BOLD}Converting File:{RESET}   {GREEN}{text_file.name}{RESET}")
    print(f"{BOLD}Voice Selected:{RESET}    {YELLOW}{v_info['name']} ({v_info['gender']}, {v_info['accent']}){RESET}")
    print(f"{BOLD}Engine Mode:{RESET}       {MAGENTA}{v_info['engine'].upper()}{RESET} ({v_info['id']})")
    print(f"{BOLD}Text Volume:{RESET}       {CYAN}{char_count:,} characters / {word_count:,} words{RESET}")
    print(f"{BOLD}Step 1 Target:{RESET}     {DIM}{initial_wav}{RESET}")
    print(f"{BOLD}{CYAN}══════════════════════════════════════════════════════════════{RESET}")

    t_start = time.time()
    success = False

    if v_info["engine"] == "espeak":
        print(f"[*] Synthesizing via eSpeak-NG local engine...")
        success = synthesize_speech_espeak(cleaned_content, v_info["id"], initial_wav)
    elif v_info.get("engine") == "xtts" or v_info.get("xtts_voice"):
        print(f"[*] Synthesizing via XTTS-v2 Matrix Neural Engine ({v_info['name']})...")
        success = synthesize_speech_xtts(cleaned_content, v_info["id"], initial_wav)
        if not success:
            print(f"{YELLOW}[!] XTTS local engine unavailable. Falling back to Edge-TTS Neural...{RESET}")
            success = synthesize_speech_edge(cleaned_content, v_info["id"], initial_wav)
            if not success:
                print(f"{YELLOW}[!] Neural generation encountered an issue. Falling back to eSpeak-NG...{RESET}")
                fallback_voice = "en-gb+f3" if v_info["gender"] == "Female" else "en-gb"
                success = synthesize_speech_espeak(cleaned_content, fallback_voice, initial_wav)
    else:
        print(f"[*] Synthesizing via Microsoft Edge Neural TTS...")
        success = synthesize_speech_edge(cleaned_content, v_info["id"], initial_wav)
        if not success:
            print(f"{YELLOW}[!] Neural generation encountered an issue. Falling back to eSpeak-NG British Female voice...{RESET}")
            fallback_voice = "en-gb+f3" if v_info["gender"] == "Female" else "en-gb"
            success = synthesize_speech_espeak(cleaned_content, fallback_voice, initial_wav)

    if not success or not initial_wav.exists():
        print(f"{RED}[-] Synthesis failed for {text_file.name}!{RESET}")
        return None

    dur_sec = get_audio_duration_seconds(initial_wav)
    wav_size = initial_wav.stat().st_size
    elapsed = time.time() - t_start

    print(f"{GREEN}[✓] Audio generated successfully in {elapsed:.1f}s!{RESET}")
    print(f"    Duration: {BOLD}{format_duration(dur_sec)}{RESET} | Size: {BOLD}{format_size(wav_size)}{RESET}")
    print(f"    Saved initially at: {GREEN}{initial_wav}{RESET}")

    today_str = datetime.date.today().strftime("%Y-%m-%d")
    unique_id = get_next_id(converted_dir, today_str)

    target_stem = f"{today_str}_{unique_id}_{original_stem}"
    final_wav = converted_dir / f"{target_stem}.wav"
    final_txt = converted_dir / f"{target_stem}.txt"

    print(f"\n[*] Moving converted pair to {BOLD}TTS_CONVERTED{RESET} with Date and ID: {CYAN}{unique_id}{RESET}...")

    shutil.move(str(initial_wav), str(final_wav))
    shutil.move(str(text_file), str(final_txt))

    print(f"{GREEN}[✓] Successfully archived in TTS_CONVERTED:{RESET}")
    print(f"    Audio: {CYAN}{final_wav.name}{RESET}")
    print(f"    Text:  {CYAN}{final_txt.name}{RESET}")

    log_file = converted_dir / "tts_conversion_history.log"
    try:
        timestamp_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(log_file, "a", encoding="utf-8") as lf:
            lf.write(
                f"[{timestamp_str}] ID={unique_id} VOICE={v_info['name']} ({v_info['id']}) "
                f"WORDS={word_count} DUR={format_duration(dur_sec)} AUDIO={final_wav.name} TXT={final_txt.name}\n"
            )
    except Exception:
        pass

    return final_wav, final_txt


def list_pending_text_files(tts_dir: Path) -> List[Path]:
    """Return all .txt files directly inside tts_dir."""
    if not tts_dir.exists():
        return []
    txt_files = [p for p in tts_dir.iterdir() if p.is_file() and p.suffix.lower() == ".txt"]
    txt_files.sort(key=lambda p: p.name.lower())
    return txt_files


def list_converted_audio_files(tts_dir: Path) -> List[Path]:
    """Return all .wav files in TTS_CONVERTED."""
    converted_dir = tts_dir / "TTS_CONVERTED"
    if not converted_dir.exists():
        return []
    wav_files = [p for p in converted_dir.iterdir() if p.is_file() and p.suffix.lower() == ".wav"]
    wav_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return wav_files


def play_audio_file(wav_path: Path) -> None:
    """Plays an audio file using available system player."""
    if not wav_path.exists():
        print(f"{RED}[-] File does not exist: {wav_path}{RESET}")
        return

    dur = get_audio_duration_seconds(wav_path)
    print(f"\n{BOLD}{GREEN}▶ Playing:{RESET} {CYAN}{wav_path.name}{RESET} ({format_duration(dur)})")
    print(f"{DIM}Press [Enter] or [s] at any time to stop playback...{RESET}\n")

    player_cmd = None
    if shutil.which("pw-play"):
        player_cmd = ["pw-play", str(wav_path)]
    elif shutil.which("aplay"):
        player_cmd = ["aplay", "-q", str(wav_path)]
    elif shutil.which("ffplay"):
        player_cmd = ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", str(wav_path)]
    elif shutil.which("mpv"):
        player_cmd = ["mpv", "--no-video", str(wav_path)]
    elif shutil.which("vlc"):
        player_cmd = ["cvlc", "--play-and-exit", str(wav_path)]

    if not player_cmd:
        print(f"{RED}[-] Error: No supported audio player found!{RESET}")
        return

    proc = subprocess.Popen(player_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        while proc.poll() is None:
            import select
            r, _, _ = select.select([sys.stdin], [], [], 0.3)
            if r:
                sys.stdin.readline().strip().lower()
                print(f"{YELLOW}[■] Stopping playback...{RESET}")
                proc.terminate()
                try:
                    proc.wait(timeout=1.0)
                except subprocess.TimeoutExpired:
                    proc.kill()
                break
    except KeyboardInterrupt:
        print(f"\n{YELLOW}[■] Playback stopped by user.{RESET}")
        proc.terminate()
    print(f"{DIM}Playback finished.{RESET}")


def preview_voice(voice_id: str) -> None:
    """Generates and plays a short audio preview for the chosen voice."""
    v_info = get_voice_info(voice_id)
    matrix_previews = {
        "agent_smith": "Mr. Anderson. Welcome back. We missed you.",
        "morpheus": "Welcome to the real world. You take the blue pill, the story ends. You take the red pill, you stay in Wonderland.",
        "morpheus_construct": "What is real? How do you define real? Real is simply electrical signals interpreted by your brain.",
        "morpheus_redpill": "Remember, all I am offering is the truth. Nothing more. How deep does the rabbit hole go?",
        "morpheus_dojo": "Do you believe that my being stronger or faster has anything to do with my muscles in this place? Free your mind.",
        "morpheus_system": "The Matrix is a system, Neo. That system is our enemy. Inside the Matrix, they are everyone and no one.",
        "neo": "I know why you are here. I know what you have been doing. I know kung fu.",
        "trinity": "The answer is out there, Neo. It is looking for you, and it will find you if you want it to.",
        "oracle": "Everything that has a beginning has an end. Do not worry about the vase.",
        "zion": "I like to be reminded this city survives because of these machines.",
        "stephen_hawking_matrix": "Entering the Matrix. Remember to look up at the stars and not down at your feet."
    }
    preview_text = matrix_previews.get(v_info["id"], f"Hello! This is {v_info['name']}. Your WAN2GP text to speech conversion system is ready.")
    
    preview_wav = Path("/tmp") / f"tts_preview_{v_info['name'].lower().replace(' ', '_').replace('(', '').replace(')', '')}.wav"

    print(f"\n[*] Generating voice preview for {BOLD}{v_info['name']}{RESET} ({v_info['gender']}, {v_info['accent']})...")
    success = False
    if v_info.get("engine") == "xtts" or v_info.get("xtts_voice"):
        success = synthesize_speech_xtts(preview_text, v_info["id"], preview_wav)
        if not success:
            success = synthesize_speech_edge(preview_text, v_info["id"], preview_wav)
    elif v_info["engine"] == "espeak":
        success = synthesize_speech_espeak(preview_text, v_info["id"], preview_wav)
    else:
        success = synthesize_speech_edge(preview_text, v_info["id"], preview_wav)

    if success and preview_wav.exists():
        play_audio_file(preview_wav)
        preview_wav.unlink(missing_ok=True)
    else:
        print(f"{RED}[-] Failed to generate voice preview.{RESET}")


def select_voice_menu(current_voice_id: str) -> str:
    """Displays the voice selection menu with all categories including cinematic voices."""
    while True:
        os.system("clear" if os.name == "posix" else "cls")
        curr_info = get_voice_info(current_voice_id)
        print(f"{BOLD}{MAGENTA}=================================================={RESET}")
        print(f"{BOLD}{MAGENTA}           SELECT TEXT-TO-SPEECH VOICE            {RESET}")
        print(f"{BOLD}{MAGENTA}=================================================={RESET}")
        print(f"  Active Voice: {BOLD}{GREEN}{curr_info['name']}{RESET} ({curr_info['gender']}, {curr_info['accent']} - {curr_info['engine'].upper()})\n")

        # 1) British Voices (Indices 0 to 7 -> Items 1 to 8)
        print(f"{BOLD}{CYAN}--- BRITISH (ENGLISH) VOICES ---{RESET}")
        for i in range(1, 9):
            v = VOICES[i - 1]
            marker = f"{GREEN}●{RESET}" if v["id"] == current_voice_id else " "
            print(f" {marker} {BOLD}{CYAN}{i:2d}){RESET} [{v['gender']:6s}] {BOLD}{v['name']:18s}{RESET} | {DIM}{v['desc']}{RESET}")

        # 2) American Voices (Indices 8 to 15 -> Items 9 to 16)
        print(f"\n{BOLD}{CYAN}--- AMERICAN (ENGLISH) VOICES ---{RESET}")
        for i in range(9, 17):
            v = VOICES[i - 1]
            marker = f"{GREEN}●{RESET}" if v["id"] == current_voice_id else " "
            print(f" {marker} {BOLD}{CYAN}{i:2d}){RESET} [{v['gender']:6s}] {BOLD}{v['name']:18s}{RESET} | {DIM}{v['desc']}{RESET}")

        # 3) Other Accents (Indices 16 to 19 -> Items 17 to 20)
        print(f"\n{BOLD}{CYAN}--- OTHER ACCENTS (ENGLISH) ---{RESET}")
        for i in range(17, 21):
            v = VOICES[i - 1]
            marker = f"{GREEN}●{RESET}" if v["id"] == current_voice_id else " "
            print(f" {marker} {BOLD}{CYAN}{i:2d}){RESET} [{v['gender']:6s}] {BOLD}{v['name']:18s}{RESET} | {DIM}{v['desc']}{RESET}")

        # 4) The Matrix Cast & Cinematic Voices (Indices 20+ -> Items 21+)
        print(f"\n{BOLD}{CYAN}--- THE MATRIX CAST & CINEMATIC VOICES ---{RESET}")
        for i in range(21, len(VOICES) + 1):
            v = VOICES[i - 1]
            marker = f"{GREEN}●{RESET}" if v["id"] == current_voice_id else " "
            print(f" {marker} {BOLD}{CYAN}{i:2d}){RESET} [{v['gender']:6s}] {BOLD}{v['name']:36s}{RESET} | {DIM}{v['desc']}{RESET}")

        print("")
        print(f"  {BOLD}P){RESET} Preview Current Voice Sample")
        print(f"  {BOLD}B){RESET} Back / Confirm Selection")
        print("")

        choice = input(f"{BOLD}Enter choice [1-{len(VOICES)} / P / B]: {RESET}").strip()
        if choice.lower() == "b" or choice == "":
            return current_voice_id
        elif choice.lower() == "p":
            preview_voice(current_voice_id)
            pause_if_tty()
        else:
            try:
                idx = int(choice)
                if 1 <= idx <= len(VOICES):
                    selected = VOICES[idx - 1]
                    current_voice_id = selected["id"]
                    print(f"\n{GREEN}✓ Voice set to: {selected['name']} ({selected['gender']}, {selected['accent']}){RESET}")
                    preview_voice(current_voice_id)
                    time.sleep(0.5)
                else:
                    print(f"{RED}Invalid number choice!{RESET}")
                    time.sleep(1)
            except ValueError:
                print(f"{RED}Invalid input!{RESET}")
                time.sleep(1)


def playback_menu(tts_dir: Path) -> None:
    """Interactive audio player menu for listening to converted speech files."""
    while True:
        os.system("clear" if os.name == "posix" else "cls")
        converted_dir = tts_dir / "TTS_CONVERTED"
        audio_files = list_converted_audio_files(tts_dir)

        print(f"{BOLD}{MAGENTA}=================================================={RESET}")
        print(f"{BOLD}{MAGENTA}       CONVERTED SPEECH AUDIO PLAYBACK MENU       {RESET}")
        print(f"{BOLD}{MAGENTA}=================================================={RESET}")
        print(f"  Location: {CYAN}{converted_dir}{RESET}")
        print(f"  Converted Audio Files: {BOLD}{len(audio_files)}{RESET}\n")

        if not audio_files:
            print(f"  {YELLOW}No converted .wav audio files found in TTS_CONVERTED.{RESET}")
            pause_if_tty("Press [Enter] to return to the TTS menu...")
            return

        print(f"  {BOLD}{'#':<3} {'Filename':<48} {'Duration':<10} {'Size':<10}{RESET}")
        print(f"  {DIM}{'─'*3} {'─'*48} {'─'*10} {'─'*10}{RESET}")

        display_limit = min(20, len(audio_files))
        for idx in range(display_limit):
            f = audio_files[idx]
            dur = format_duration(get_audio_duration_seconds(f))
            size = format_size(f.stat().st_size)
            name_disp = f.name if len(f.name) <= 46 else f.name[:43] + "..."
            print(f"  {BOLD}{CYAN}{idx + 1:2d}){RESET} {name_disp:<48} {dur:<10} {size:<10}")

        print("")
        print(f"  {BOLD}A){RESET} Play All Files Sequentially")
        print(f"  {BOLD}D){RESET} Open Folder in File Manager (Dolphin)")
        print(f"  {BOLD}B){RESET} Back to TTS Menu")
        print("")

        choice = input(f"{BOLD}Select track to play [1-{display_limit} / A / D / B]: {RESET}").strip()
        if choice.lower() == "b" or choice == "":
            return
        elif choice.lower() == "a":
            for f in audio_files:
                play_audio_file(f)
        elif choice.lower() == "d":
            if shutil.which("dolphin"):
                subprocess.Popen(["dolphin", str(converted_dir)])
            elif shutil.which("xdg-open"):
                subprocess.Popen(["xdg-open", str(converted_dir)])
        else:
            try:
                num = int(choice)
                if 1 <= num <= len(audio_files):
                    play_audio_file(audio_files[num - 1])
                    pause_if_tty()
                else:
                    print(f"{RED}Invalid selection!{RESET}")
                    time.sleep(1)
            except ValueError:
                print(f"{RED}Invalid input!{RESET}")
                time.sleep(1)


def convert_single_interactive(tts_dir: Path, voice_id: str) -> None:
    """Interactive prompt to select and convert a single text file."""
    pending = list_pending_text_files(tts_dir)
    if not pending:
        print(f"\n{YELLOW}[!] No pending .txt files found in {tts_dir}!{RESET}")
        pause_if_tty()
        return

    print(f"\n{BOLD}{CYAN}--- AVAILABLE TEXT FILES FOR CONVERSION ---{RESET}")
    for idx, p in enumerate(pending, 1):
        size = format_size(p.stat().st_size)
        print(f"  {BOLD}{CYAN}{idx:2d}){RESET} {p.name} ({DIM}{size}{RESET})")
    print("")

    choice = input(f"{BOLD}Select file number to convert [1-{len(pending)}] (or [B] Back): {RESET}").strip()
    if choice.lower() == "b" or choice == "":
        return
    try:
        idx = int(choice)
        if 1 <= idx <= len(pending):
            selected_file = pending[idx - 1]
            convert_text_to_speech(selected_file, voice_id, tts_dir)
            pause_if_tty()
        else:
            print(f"{RED}Invalid selection!{RESET}")
            time.sleep(1)
    except ValueError:
        print(f"{RED}Invalid input!{RESET}")
        time.sleep(1)


def convert_all_batch(tts_dir: Path, voice_id: str) -> None:
    """Batch converts all pending .txt files in the TTS directory."""
    pending = list_pending_text_files(tts_dir)
    if not pending:
        print(f"\n{YELLOW}[!] No pending .txt files found in {tts_dir}!{RESET}")
        pause_if_tty()
        return

    print(f"\n{BOLD}{MAGENTA}Starting Batch Conversion of {len(pending)} file(s)...{RESET}")
    success_count = 0
    t_start = time.time()

    for idx, p in enumerate(pending, 1):
        print(f"\n{BOLD}[Batch {idx}/{len(pending)}]{RESET} Processing: {CYAN}{p.name}{RESET}")
        result = convert_text_to_speech(p, voice_id, tts_dir)
        if result:
            success_count += 1

    total_time = time.time() - t_start
    print(f"\n{BOLD}{GREEN}══════════════════════════════════════════════════════════════{RESET}")
    print(f"{BOLD}BATCH CONVERSION COMPLETE:{RESET} {GREEN}{success_count}/{len(pending)}{RESET} files converted successfully in {total_time:.1f}s.")
    print(f"{BOLD}Archived location:{RESET} {CYAN}{tts_dir / 'TTS_CONVERTED'}{RESET}")
    print(f"{BOLD}{GREEN}══════════════════════════════════════════════════════════════{RESET}")
    pause_if_tty()


def interactive_main(tts_dir: Path) -> None:
    """Main interactive terminal UI for the TTS converter and audio player."""
    cfg = load_config()
    active_voice = cfg.get("voice_id", DEFAULT_VOICE_ID)

    while True:
        os.system("clear" if os.name == "posix" else "cls")
        pending = list_pending_text_files(tts_dir)
        converted = list_converted_audio_files(tts_dir)
        v_info = get_voice_info(active_voice)

        print(f"{BOLD}{MAGENTA}=================================================={RESET}")
        print(f"{BOLD}{MAGENTA}        WAN2GP TEXT-TO-SPEECH (TTS) MANAGER       {RESET}")
        print(f"{BOLD}{MAGENTA}=================================================={RESET}")
        print(f"  Batch Directory:  {GREEN}{tts_dir}{RESET}")
        print(f"  Archive Folder:   {CYAN}{tts_dir / 'TTS_CONVERTED'}{RESET}")
        print(f"  Pending .txt:     {BOLD}{YELLOW if pending else GREEN}{len(pending)} file(s){RESET}")
        print(f"  Converted .wav:   {BOLD}{GREEN}{len(converted)} file(s){RESET}")
        print(f"  Active Voice:     {BOLD}{CYAN}{v_info['name']}{RESET} [{v_info['gender']}, {v_info['accent']}] ({v_info['engine'].upper()})")
        print("")
        print(f"  {BOLD}${CYAN}1)${RESET} Convert a Single Text File ({BOLD}{len(pending)}{RESET} pending)")
        print(f"  {BOLD}${CYAN}2)${RESET} Batch Convert All Text Files in Directory ({BOLD}{len(pending)}{RESET} files)")
        print(f"  {BOLD}${CYAN}3)${RESET} Select Voice (British / US / Male / Female / Accents)")
        print(f"  {BOLD}${CYAN}4)${RESET} Preview / Test Current Voice")
        print(f"  {BOLD}${CYAN}5)${RESET} Audio Player & Playback Menu (Play Converted Audio)")
        print(f"  {BOLD}${CYAN}6)${RESET} Open TTS Directory in File Manager (Dolphin)")
        print(f"  {BOLD}${CYAN}7)${RESET} Return to WAN2GP / Main Menu")
        print("")

        choice = input(f"{BOLD}Enter choice [1-7]: {RESET}").strip()
        if choice == "1":
            convert_single_interactive(tts_dir, active_voice)
        elif choice == "2":
            convert_all_batch(tts_dir, active_voice)
        elif choice == "3":
            active_voice = select_voice_menu(active_voice)
            cfg["voice_id"] = active_voice
            save_config(cfg)
        elif choice == "4":
            preview_voice(active_voice)
            pause_if_tty()
        elif choice == "5":
            playback_menu(tts_dir)
        elif choice == "6":
            if shutil.which("dolphin"):
                subprocess.Popen(["dolphin", str(tts_dir)])
            elif shutil.which("xdg-open"):
                subprocess.Popen(["xdg-open", str(tts_dir)])
        elif choice in ["7", "q", "exit"]:
            print(f"\n{GREEN}Returning to WAN2GP Server Manager...{RESET}\n")
            break
        else:
            print(f"{RED}Invalid option!{RESET}")
            time.sleep(1)


def main():
    parser = argparse.ArgumentParser(description="WAN2GP Text-to-Speech (TTS) Batch Converter & Audio Player")
    parser.add_argument("--file", "-f", type=str, help="Convert a single text file (filename or full path)")
    parser.add_argument("--all", "-a", action="store_true", help="Batch convert all .txt files in the TTS batch directory")
    parser.add_argument("--voice", "-v", type=str, default=None, help="Voice ID or name")
    parser.add_argument("--dir", "-d", type=str, default=None, help="Custom TTS batch directory")
    parser.add_argument("--play", "-p", action="store_true", help="Launch interactive audio player playback menu")
    parser.add_argument("--list-voices", "-l", action="store_true", help="List all available voices and exit")
    args = parser.parse_args()

    tts_dir = Path(args.dir) if args.dir else DEFAULT_TTS_DIR
    tts_dir.mkdir(parents=True, exist_ok=True)
    (tts_dir / "TTS_CONVERTED").mkdir(parents=True, exist_ok=True)

    if args.list_voices:
        print(f"\n{BOLD}{CYAN}Available Text-to-Speech Voices:{RESET}\n")
        for idx, v in enumerate(VOICES, 1):
            print(f"  {idx:2d}) {BOLD}{v['name']:36s}{RESET} [{v['gender']:6s}] {v['accent']:30s} ({v['id']})")
        return

    cfg = load_config()
    voice_id = args.voice if args.voice else cfg.get("voice_id", DEFAULT_VOICE_ID)

    if args.play:
        playback_menu(tts_dir)
        return

    if args.file:
        target = Path(args.file)
        if not target.is_absolute():
            target = tts_dir / target
        convert_text_to_speech(target, voice_id, tts_dir)
        return

    if args.all:
        convert_all_batch(tts_dir, voice_id)
        return

    interactive_main(tts_dir)


if __name__ == "__main__":
    main()