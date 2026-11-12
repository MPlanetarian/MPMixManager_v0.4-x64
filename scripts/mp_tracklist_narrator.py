#!/usr/bin/env python3
"""Read a tracklist out loud with the MP Harmony Agent and save the recording.

The selected tracklist is sent to the running MP Harmony Agent (port 11435). The
agent's active AI model turns the tracklist into a spoken narration script and
the agent's own OpenAI-compatible speech endpoint (/v1/audio/speech) synthesises
the audio with one of the voices already installed in MP Harmony. Stephen
Hawking (``stephen_hawking_matrix``) is the default voice.

Every recording is written to::

    <MIX_ARCHIVE>/MP_TRACKLISTS_VOICED/<title>_<voice>_<timestamp>.wav

with a companion ``.txt`` transcript and a ``.json`` metadata file so the audio
can be reused for production work.

Usage::

    python3 mp_tracklist_narrator.py --tracklist /path/to/Mix_40.txt
    python3 mp_tracklist_narrator.py --tracklist Mix.txt --voice neo
    python3 mp_tracklist_narrator.py --list-voices
"""

from __future__ import annotations

import argparse
import datetime as _dt
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import wave
from pathlib import Path

VERSION = "1.0"
DEFAULT_VOICE = "stephen_hawking_matrix"
DEFAULT_PORT = 11435
VOICED_FOLDER = "MP_TRACKLISTS_VOICED"

# Voices already installed in the MP Harmony Agent (see VOICES_MAP in
# MP_Harmony_Agent.py). Stephen Hawking is the tracklist narration default.
VOICES = (
    ("stephen_hawking_matrix", "Stephen Hawking (Enters the Matrix)", "Stephen Hawking"),
    ("morpheus", "Morpheus (The Matrix - Master)", "Morpheus"),
    ("morpheus_construct", "Morpheus (The Construct - 'What is real?')", "Morpheus Construct"),
    ("morpheus_redpill", "Morpheus (Red Pill - 'Rabbit Hole')", "Morpheus Red Pill"),
    ("morpheus_dojo", "Morpheus (Combat Dojo - 'Free your mind')", "Morpheus Dojo"),
    ("morpheus_system", "Morpheus (The System - 'Our enemy')", "Morpheus System"),
    ("agent_smith", "Agent Smith (The Matrix)", "Agent Smith"),
    ("neo", "Neo (The Matrix)", "Neo"),
    ("trinity", "Trinity (The Matrix)", "Trinity"),
    ("oracle", "The Oracle (The Matrix)", "The Oracle"),
    ("zion", "Zion (Councillor Hamann)", "Zion"),
)
VOICE_IDS = {v[0] for v in VOICES}

# Same Matrix/Hawking filter chain the MP Harmony Agent uses for its own speech.
HAWKING_FILTER = "bass=g=12:f=95:w=0.6, equalizer=f=2400:t=q:w=1.2:g=2, aecho=0.8:0.7:50|100:0.3|0.2"


# ---------------------------------------------------------------------------
# Console helpers
# ---------------------------------------------------------------------------
def _c(code: str, text: str) -> str:
    if not sys.stdout.isatty():
        return text
    return f"\033[{code}m{text}\033[0m"


def info(msg: str) -> None:
    print(f"{_c('1;36', '[MP Tracklist Narrator]')} {msg}", flush=True)


def warn(msg: str) -> None:
    print(f"{_c('1;33', '[Notice]')} {msg}", flush=True)


def fail(msg: str) -> None:
    print(f"{_c('1;31', '[Error]')} {msg}", file=sys.stderr, flush=True)


# ---------------------------------------------------------------------------
# Tracklist parsing / narration cleanup
# ---------------------------------------------------------------------------
ENTRY_RE = re.compile(r"^\s*(?:\[[^\]]*\]\s*)?\d{1,3}\s*[.)\-:]\s+(.+?)\s*$")
INLINE_ENTRY_RE = re.compile(r"^\s*\d{1,3}\s*[.)]?\s+\S")


def read_tracklist(path: Path) -> str:
    for enc in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return path.read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
    return path.read_bytes().decode("utf-8", "replace")


def release_info(text: str) -> tuple[str, str]:
    """Return (title, artist) declared in the tracklist header, if present."""
    title = ""
    artist = ""
    for line in text.splitlines()[:25]:
        m = re.match(r"^\s*(?:release\s+)?title\s*:\s*(.+?)\s*$", line, re.I)
        if m and not title:
            title = m.group(1)
        m = re.match(r"^\s*artist\s*:\s*(.+?)\s*$", line, re.I)
        if m and not artist:
            artist = m.group(1)
    return title, artist


def track_entries(text: str) -> list[str]:
    """Pull the numbered track lines out of a tracklist document."""
    entries: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        low = stripped.lower()
        if low.startswith(("release info", "title:", "artist:", "=== tracklist", "tracklist:")):
            continue
        m = ENTRY_RE.match(stripped)
        if m:
            entry = m.group(1).strip(" -–—\t")
            if entry:
                entries.append(entry)
    return entries


def clean_narration(raw: str) -> str:
    """Turn the agent reply into plain spoken words.

    The agent occasionally wraps its answer in describing what it did
    ("I reviewed the tracklist..." / "No tools were invoked..."). Those
    sentences would otherwise be read out loud, so they are dropped here.
    """
    if not raw:
        return ""
    text = raw

    marker = re.search(r"<<<\s*NARRATION\s*>>>(.*?)(?:<<<\s*END\s*>>>|$)", text, re.S | re.I)
    if marker:
        text = marker.group(1)

    # Strip markdown that the speech engine should not read.
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"^\s*#{1,6}\s*", "", text, flags=re.M)
    text = re.sub(r"(\*\*|__)(.*?)\1", r"\2", text, flags=re.S)
    text = re.sub(r"(?<![\w*])(\*|_)([^*_\n]+)\1(?![\w*])", r"\2", text)
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.M)
    text = re.sub(r"<<<\s*(?:NARRATION|END)\s*>>>", " ", text, flags=re.I)

    # Drop sentences that talk about the task instead of the mix.
    meta = re.compile(
        r"(no tools? (?:were|was) (?:used|invoked|called)"
        r"|no further (?:findings|actions)"
        r"|\bI (?:reviewed|converted|created|generated|produced|prepared|summari[sz]ed|read)\b"
        r"|\bI(?:'ve| have)\b"
        r"|as (?:requested|instructed|asked)"
        r"|the requested\b"
        r"|the (?:tracklist|narration|script|reply|response) (?:was|is|has been)\b"
        r"|this narration\b"
        r"|in this (?:reply|response)\b"
        r"|here (?:is|are) the\b"
        r"|below is\b"
        r"|(?:it|which) (?:welcomes|reads|lists|ends)\b"
        r"|welcome[sd]? listeners\b"
        r"|reads the (?:sole )?(?:listed )?track"
        r"|ends with a (?:short )?sign"
        r"|let me know\b"
        r"|feel free\b)",
        re.I,
    )
    kept: list[str] = []
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        candidate = sentence.strip()
        if not candidate:
            continue
        # "The requested narration is: Welcome to ..." -> keep only what follows
        # the colon, because the spoken words start there.
        if meta.search(candidate):
            if ":" in candidate:
                tail = candidate.split(":", 1)[1].strip()
                if tail and not meta.search(tail):
                    kept.append(tail)
            continue
        kept.append(candidate)
    text = " ".join(kept)

    # Drop stray wrapping quotes around the whole reply.
    text = text.strip().strip("\"'“”‘’").strip()
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", ". ", text)
    text = re.sub(r"\n", " ", text)
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    text = re.sub(r"\.{3,}", ".", text)
    text = re.sub(r"\.\s*\.", ".", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()


META_HINTS = re.compile(
    r"(no tools? (?:were|was)"
    r"|\bI (?:reviewed|converted|created|generated|produced|prepared|summari[sz]ed)\b"
    r"|as (?:requested|instructed)"
    r"|the requested\b"
    r"|this narration\b"
    r"|welcome[sd]? listeners\b"
    r"|ends with a (?:short )?sign)",
    re.I,
)


def _words_only(text: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", " ", text.lower())
    return " ".join(cleaned.split())


def looks_like_narration(narration: str, entries: list[str]) -> bool:
    if len(narration) < 60:
        return False
    words = narration.split()
    if len(words) < 15:
        return False
    if META_HINTS.search(narration):
        return False
    if not entries:
        return True
    haystack = _words_only(narration)
    hits = 0
    checked = 0
    for entry in entries[:40]:
        artist = re.split(r"\s+[-–—]\s+|\s+-\s+", entry, maxsplit=1)[0]
        token = " ".join(_words_only(artist).split()[:3])
        if not token:
            continue
        checked += 1
        if token in haystack:
            hits += 1
    if not checked:
        return True
    return hits >= max(1, int(checked * 0.35))


def fallback_narration(text: str, title: str) -> str:
    """Build a clean narration locally if the agent reply is unusable."""
    header_title, header_artist = release_info(text)
    mix_title = header_title or title
    entries = track_entries(text)
    parts: list[str] = []
    if header_artist:
        parts.append(f"Welcome to {mix_title} by {header_artist}.")
    else:
        parts.append(f"Welcome to {mix_title}.")
    if entries:
        parts.append(f"Here is the tracklist. {len(entries)} tracks in this mix.")
        for idx, entry in enumerate(entries, 1):
            spoken = re.sub(r"\s+[-–—]\s+", ", ", entry)
            spoken = re.sub(r"\s*\(([^)]*)\)", r", \1", spoken)
            spoken = re.sub(r"\s*\[([^\]]*)\]", r", \1", spoken)
            spoken = re.sub(r"\s{2,}", " ", spoken).strip(" ,")
            parts.append(f"Track {idx}. {spoken}.")
    else:
        parts.append(re.sub(r"\s+", " ", text).strip())
    parts.append("Thanks for listening, and enjoy the mix.")
    return " ".join(p for p in parts if p)


# ---------------------------------------------------------------------------
# MP Harmony Agent bridge
# ---------------------------------------------------------------------------
def harmony_base_url() -> str:
    port = os.getenv("HARMONY_PORT", str(DEFAULT_PORT)).strip() or str(DEFAULT_PORT)
    return f"http://127.0.0.1:{port}"


def harmony_is_up(base: str) -> bool:
    try:
        with urllib.request.urlopen(f"{base}/v1/models", timeout=2):
            return True
    except Exception:
        return False


def ensure_harmony(base: str) -> bool:
    if harmony_is_up(base):
        return True
    manage = Path(__file__).resolve().parent / "manage_harmony_agent.sh"
    if not manage.is_file():
        manage = Path(__file__).resolve().parent.parent / "scripts" / "manage_harmony_agent.sh"
    if manage.is_file():
        info("MP Harmony Agent is not running. Starting the voice bridge...")
        try:
            subprocess.run(["bash", str(manage), "start"], timeout=180, check=False)
        except Exception as exc:  # pragma: no cover - environment specific
            warn(f"Could not start MP Harmony Agent automatically: {exc}")
    for _ in range(30):
        if harmony_is_up(base):
            return True
        time.sleep(0.5)
    return harmony_is_up(base)


def _post_json(url: str, payload: dict, timeout: float, raw: bool = False):
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read()
        if raw:
            return resp.status, data
        return resp.status, json.loads(data.decode("utf-8", "replace"))


def request_narration(base: str, tracklist_path: Path, text: str, title: str) -> str:
    """Ask the agent's active model for a spoken narration of the tracklist."""
    header_title, header_artist = release_info(text)
    prompt = (
        "You are the announcer for an electronic music mix. Turn the tracklist below "
        "into a spoken narration for a text-to-speech voice.\n"
        "Strict rules:\n"
        "- Reply with ONLY the words that should be spoken out loud.\n"
        "- No headings, no bullet points, no notes, no explanation, and never mention tools.\n"
        "- Wrap the narration between <<<NARRATION>>> and <<<END>>>.\n"
        "- Welcome the listener with the mix title and artist, then read each track in order "
        "once, using its artist and title, then finish with a short sign-off.\n\n"
        f"TRACKLIST FILE: {tracklist_path.name}\n"
        f"MIX TITLE: {header_title or title}\n"
    )
    if header_artist:
        prompt += f"MIX ARTIST: {header_artist}\n"
    prompt += f"--- TRACKLIST START ---\n{text.strip()}\n--- TRACKLIST END ---\n"

    payload = {
        "model": os.getenv("HARMONY_MODEL", "mp-harmony-agent"),
        "stream": False,
        "messages": [{"role": "user", "content": prompt}],
    }
    req = urllib.request.Request(
        f"{base}/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-Session-Id": f"tracklist-narrator-{os.getpid()}-{int(time.time())}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=900) as resp:
        data = json.loads(resp.read().decode("utf-8", "replace"))
    choices = data.get("choices") or []
    if not choices:
        return ""
    return (choices[0].get("message") or {}).get("content", "") or ""


# ---------------------------------------------------------------------------
# Text to speech
# ---------------------------------------------------------------------------
def split_for_tts(text: str, limit: int = 1400) -> list[str]:
    """Split long narration on sentence/clause boundaries for large tracklists."""
    if len(text) <= limit:
        return [text]
    chunks: list[str] = []
    remaining = text
    while len(remaining) > limit:
        cut = remaining.rfind(". ", 0, limit)
        if cut < limit // 2:
            cut = remaining.rfind(", ", 0, limit)
        if cut < limit // 2:
            cut = remaining.rfind(" ", 0, limit)
        if cut <= 0:
            cut = limit
        else:
            cut += 1
        chunk = remaining[:cut].strip()
        if chunk:
            chunks.append(chunk)
        remaining = remaining[cut:].strip()
    if remaining:
        chunks.append(remaining)
    return chunks


def wav_params(blob: bytes):
    try:
        with wave.open(io.BytesIO(blob), "rb") as wf:
            return (wf.getnchannels(), wf.getsampwidth(), wf.getframerate(), wf.getcomptype())
    except Exception:
        return None


def concat_wavs(blobs: list[bytes]) -> bytes:
    if not blobs:
        return b""
    if len(blobs) == 1:
        return blobs[0]
    params = wav_params(blobs[0])
    if params is None:
        return b""
    frames: list[bytes] = []
    for blob in blobs:
        if wav_params(blob) != params:
            return b""
        with wave.open(io.BytesIO(blob), "rb") as wf:
            frames.append(wf.readframes(wf.getnframes()))
    out = io.BytesIO()
    with wave.open(out, "wb") as wf:
        wf.setnchannels(params[0])
        wf.setsampwidth(params[1])
        wf.setframerate(params[2])
        wf.setcomptype(params[3], "NONE")
        for frame in frames:
            wf.writeframes(frame)
    return out.getvalue()


def synthesize_via_agent(base: str, text: str, voice: str, speed: float) -> bytes:
    status, body = _post_json(
        f"{base}/v1/audio/speech",
        {"input": text, "voice": voice, "speed": speed},
        timeout=900,
        raw=True,
    )
    if status == 200 and body[:4] == b"RIFF" and len(body) > 128:
        return body
    return b""


def synthesize_hawking_locally(text: str, speed: float = 1.0) -> bytes:
    """Local copy of the MP Harmony Agent's Stephen Hawking synthesis chain."""
    espeak = shutil.which("espeak-ng") or shutil.which("espeak")
    if not espeak:
        return b""
    tmpdir = tempfile.mkdtemp(prefix="mp_narrator_")
    raw = os.path.join(tmpdir, "raw.wav")
    filtered = os.path.join(tmpdir, "filtered.wav")
    try:
        subprocess.run(
            [espeak, "-v", "en-us+m3", "-p", "19", "-s", str(int(110 * max(0.4, min(2.5, speed)))),
             text, "-w", raw],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300,
        )
        final = raw
        if shutil.which("ffmpeg"):
            res = subprocess.run(
                ["ffmpeg", "-y", "-v", "error", "-i", raw, "-af", HAWKING_FILTER, filtered],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300,
            )
            if res.returncode == 0 and os.path.exists(filtered) and os.path.getsize(filtered) > 44:
                final = filtered
        with open(final, "rb") as handle:
            return handle.read()
    except Exception as exc:
        warn(f"Local Stephen Hawking synthesis failed: {exc}")
        return b""
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def synthesize(text: str, base: str, voice: str, speed: float) -> bytes:
    try:
        audio = synthesize_via_agent(base, text, voice, speed)
        if audio:
            return audio
        warn("MP Harmony speech endpoint returned no audio. Retrying in smaller segments...")
    except urllib.error.HTTPError as exc:
        warn(f"MP Harmony speech endpoint returned HTTP {exc.code}.")
    except Exception as exc:
        warn(f"MP Harmony speech endpoint unavailable ({exc}).")

    chunks = split_for_tts(text)
    if len(chunks) > 1:
        blobs: list[bytes] = []
        for idx, chunk in enumerate(chunks, 1):
            info(f"Synthesising audio segment {idx}/{len(chunks)}...")
            try:
                blob = synthesize_via_agent(base, chunk, voice, speed)
            except Exception as exc:
                warn(f"Segment {idx} failed: {exc}")
                blob = b""
            if not blob:
                blobs = []
                break
            blobs.append(blob)
        joined = concat_wavs(blobs)
        if joined:
            return joined

    if voice in ("stephen_hawking_matrix", "stephen_hawking", "hawking"):
        info("Falling back to the local Stephen Hawking Matrix synthesiser...")
        return synthesize_hawking_locally(text, speed)
    return b""


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
def resolve_archive_root(tracklist_path: Path) -> Path:
    env = os.getenv("MIX_ARCHIVE_DIR", "").strip()
    if env:
        candidate = Path(os.path.expanduser(env))
        if candidate.is_dir():
            return candidate
    here = tracklist_path.resolve().parent
    for parent in (here, *here.parents):
        if parent.name in ("FLAC_CONVERTED_OUTPUTS", "CONVERTED_WAV_FILES", "MP3_CONVERTED_OUTPUTS"):
            return parent.parent
        if (parent / "FLAC_CONVERTED_OUTPUTS").is_dir():
            return parent
    return Path(__file__).resolve().parent.parent / "MIX_ARCHIVE"


def voiced_dir(archive_root: Path, create: bool = True) -> Path:
    target = archive_root / VOICED_FOLDER
    if create:
        target.mkdir(parents=True, exist_ok=True)
    return target


def slugify(value: str, limit: int = 90) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_")
    return (slug[:limit] or "Tracklist")


# ---------------------------------------------------------------------------
# Playback
# ---------------------------------------------------------------------------
def play_audio(path: Path) -> None:
    players = (
        ("pw-play", ["pw-play", str(path)]),
        ("paplay", ["paplay", str(path)]),
        ("aplay", ["aplay", "-q", str(path)]),
        ("ffplay", ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", str(path)]),
    )
    for binary, cmd in players:
        if shutil.which(binary):
            info(f"Playing the narration with {binary} (press Ctrl+C to stop early)...")
            try:
                subprocess.run(cmd, check=False)
            except KeyboardInterrupt:
                warn("Playback stopped early.")
            except Exception as exc:
                warn(f"{binary} playback failed: {exc}")
            return
    warn("No local audio player was found. The recording is saved and ready to play.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def narrate(tracklist: Path, voice: str, speed: float, out_dir: str | None,
            play: bool, quiet: bool) -> dict:
    text = read_tracklist(tracklist)
    if not text.strip():
        raise SystemExit(f"Tracklist is empty: {tracklist}")

    title = tracklist.stem
    base = harmony_base_url()
    if not ensure_harmony(base):
        raise SystemExit(
            "MP Harmony Agent is not running and could not be started.\n"
            "Start it from AI Assistant & Local LLM Servers > Manage MP Harmony AI Agent, then retry."
        )
    if not quiet:
        info(f"MP Harmony Agent online at {base}")
        info(f"Tracklist: {tracklist.name}")
        info(f"Voice: {voice}")

    info("Asking the MP Harmony Agent's active AI model to narrate the tracklist...")
    raw_reply = ""
    try:
        raw_reply = request_narration(base, tracklist, text, title)
    except Exception as exc:
        warn(f"Agent narration request failed: {exc}")

    entries = track_entries(text)
    narration = clean_narration(raw_reply)
    agent_narration = bool(narration) and looks_like_narration(narration, entries)
    if not agent_narration:
        warn("Agent reply was not usable narration. Building the script from the tracklist instead.")
        narration = fallback_narration(text, title)
    if not narration:
        raise SystemExit("Could not produce a narration script from this tracklist.")
    if not quiet:
        info(f"Narration script ready ({len(narration.split())} words).")

    info("Synthesising the voice track with the MP Harmony speech engine...")
    audio = synthesize(narration, base, voice, speed)
    if not audio or audio[:4] != b"RIFF":
        raise SystemExit("Audio synthesis failed. Check that espeak-ng and ffmpeg are installed.")

    if out_dir:
        target_dir = Path(os.path.expanduser(out_dir))
    else:
        target_dir = voiced_dir(resolve_archive_root(tracklist), create=False)
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise SystemExit(
            f"Cannot create the {VOICED_FOLDER} folder at {target_dir}: {exc}\n"
            "Check that the primary MIX_ARCHIVE drive or share is mounted and writable."
        )

    stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = f"{slugify(title)}_{slugify(voice.replace('_matrix', ''))}_{stamp}"
    audio_path = target_dir / f"{base_name}.wav"
    text_path = target_dir / f"{base_name}.txt"
    meta_path = target_dir / f"{base_name}.json"
    try:
        audio_path.write_bytes(audio)
        text_path.write_text(narration + "\n", encoding="utf-8")
    except OSError as exc:
        raise SystemExit(f"Could not write the narration files to {target_dir}: {exc}")

    with wave.open(str(audio_path), "rb") as wf:
        duration = wf.getnframes() / float(wf.getframerate() or 1)
    meta = {
        "title": title,
        "tracklist_file": str(tracklist.resolve()),
        "voice": voice,
        "voice_label": next((v[1] for v in VOICES if v[0] == voice), voice),
        "speed": speed,
        "agent_url": base,
        "created": _dt.datetime.now().isoformat(timespec="seconds"),
        "duration_seconds": round(duration, 1),
        "audio_path": str(audio_path),
        "text_path": str(text_path),
        "words": len(narration.split()),
        "tracks": len(entries),
        "narration_source": "agent" if agent_narration else "fallback",
    }
    try:
        meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    except OSError:
        meta_path = None

    if not quiet:
        info(f"Saved narration audio: {audio_path}")
        info(f"Saved transcript:      {text_path}")
        info(f"Duration: {duration:.1f}s | Tracks: {len(entries)} | Folder: {target_dir}")
    if play:
        play_audio(audio_path)

    meta["out_dir"] = str(target_dir)
    return meta


def print_voices() -> None:
    print("Voices available in the MP Harmony Agent:")
    for voice_id, label, _short in VOICES:
        marker = "  (default)" if voice_id == DEFAULT_VOICE else ""
        print(f"  {voice_id:<24} {label}{marker}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read a tracklist out loud using the MP Harmony Agent and save the recording."
    )
    parser.add_argument("tracklist", nargs="?", help="Path to the tracklist .txt file")
    parser.add_argument("--tracklist", "-t", dest="tracklist_opt", help="Path to the tracklist .txt file")
    parser.add_argument("--voice", "-V", default=DEFAULT_VOICE, help=f"MP Harmony voice id (default: {DEFAULT_VOICE})")
    parser.add_argument("--speed", type=float, default=1.0, help="Speech speed multiplier (default: 1.0)")
    parser.add_argument("--out-dir", default=None, help=f"Destination folder (default: <MIX_ARCHIVE>/{VOICED_FOLDER})")
    parser.add_argument("--no-play", action="store_true", help="Generate the recording without playing it")
    parser.add_argument("--quiet", "-q", action="store_true", help="Only print the result paths")
    parser.add_argument("--json", action="store_true", help="Print a JSON result object at the end")
    parser.add_argument("--list-voices", action="store_true", help="List the voices available in MP Harmony")
    parser.add_argument("--version", action="version", version=f"MP Tracklist Narrator {VERSION}")
    args = parser.parse_args(argv)

    if args.list_voices:
        print_voices()
        return 0

    raw_path = args.tracklist_opt or args.tracklist
    if not raw_path:
        parser.error("a tracklist file is required")
    tracklist = Path(os.path.expanduser(raw_path.strip().strip("\"'")))
    if not tracklist.is_file():
        fail(f"Tracklist file not found: {tracklist}")
        return 1

    voice = (args.voice or DEFAULT_VOICE).strip().lower()
    if voice not in VOICE_IDS:
        warn(f"Unknown voice '{voice}'. Using {DEFAULT_VOICE}.")
        voice = DEFAULT_VOICE

    print()
    print(_c("1;35", "=" * 70))
    print(_c("1;35", "   MP HARMONY TRACKLIST NARRATOR - SPOKEN TRACKLIST RECORDING"))
    print(_c("1;35", "=" * 70))
    try:
        meta = narrate(tracklist, voice, args.speed, args.out_dir, not args.no_play, args.quiet)
    except SystemExit as exc:
        fail(str(exc))
        return 1
    except KeyboardInterrupt:
        warn("Cancelled.")
        return 130

    print()
    print(f"AUDIO_PATH={meta['audio_path']}")
    print(f"TEXT_PATH={meta['text_path']}")
    print(f"OUT_DIR={meta['out_dir']}")
    if args.json:
        print("RESULT_JSON=" + json.dumps(meta))
    return 0


if __name__ == "__main__":
    sys.exit(main())
