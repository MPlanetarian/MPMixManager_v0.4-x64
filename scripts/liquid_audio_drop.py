"""Drag-and-drop audio files onto the MP Liquid Player.

The glass window is a GTK host. The playlist the user sees belongs to the
player process inside the terminal. A drop is scanned here, written as a
small manifest, and handed to that process as a private terminal sequence
so the open list and the playback engine both receive it.
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
import uuid
from pathlib import Path
from urllib.parse import unquote, urlparse

# Every audio type the player can hand to FFmpeg or libsndfile.
# Video containers are left out so a dropped movie is not treated as a track.
AUDIO_DROP_EXTENSIONS = (
    ".flac", ".wav", ".wave", ".w64", ".rf64",
    ".mp3", ".mp2", ".mp1", ".mpga",
    ".ogg", ".oga", ".opus", ".spx",
    ".m4a", ".m4b", ".m4p", ".aac", ".alac",
    ".aiff", ".aif", ".aifc",
    ".wma",
    ".ape", ".wv", ".tta", ".tak",
    ".mpc", ".mpp",
    ".ac3", ".eac3", ".dts",
    ".caf", ".au", ".snd",
    ".amr", ".3ga",
    ".dsf", ".dff",
    ".mka",
    ".voc", ".ofr", ".ofs",
)
AUDIO_DROP_EXTENSION_SET = frozenset(AUDIO_DROP_EXTENSIONS)
PLAYLIST_EXTENSIONS = frozenset({".m3u", ".m3u8", ".pls"})
DROP_FILE_LIMIT = 2000
DROP_OSC_PREFIX = b"\x1b]5221;"
AUDIO_DIALOG_LABEL = "Audio Files (All types)"

_SOUNDFILE_EXTENSIONS = frozenset({
    ".flac", ".wav", ".wave", ".w64", ".rf64",
    ".aiff", ".aif", ".aifc", ".ogg", ".oga",
    ".au", ".snd", ".caf", ".mp3",
})


def prefers_ffmpeg(path: str) -> bool:
    """Formats libsndfile often cannot open should start in FFmpeg."""
    return os.path.splitext(str(path))[1].lower() not in _SOUNDFILE_EXTENSIONS


def drop_dir() -> Path:
    override = (os.environ.get("MP_LIQUID_DROP_DIR") or "").strip()
    if override:
        return Path(override).expanduser()
    return Path.home() / ".config" / "mix-manager" / "liquid_audio_drops"


def dialog_audio_globs(separator: str = " ") -> str:
    pattern = "*{ext}"
    return separator.join(pattern.format(ext=ext) for ext in AUDIO_DROP_EXTENSIONS)


def kdialog_audio_filter() -> str:
    return f"{dialog_audio_globs(' ')} | {AUDIO_DIALOG_LABEL}"


def zenity_audio_filter() -> str:
    return f"{AUDIO_DIALOG_LABEL} | {dialog_audio_globs(' ')}"


def windows_audio_filter() -> str:
    return f"{AUDIO_DIALOG_LABEL}|{dialog_audio_globs(';')}|All Files (*.*)|*.*"


def host_accepts_audio_drops(argv) -> bool:
    """Only the embedded MP Audio Player accepts drops, not the manager or a tracklist."""
    for arg in argv or []:
        name = str(arg).replace("\\", "/").rsplit("/", 1)[-1].strip('"').strip("'")
        if name == "MP_Audio_Player.py":
            return True
    return False


def path_from_drop_entry(entry: str) -> str:
    text = str(entry or "").strip().strip("\x00")
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "'\"":
        text = text[1:-1].strip()
    if not text or text.startswith("#"):
        return ""
    if text.lower().startswith("file:"):
        parsed = urlparse(text)
        path = unquote(parsed.path or "")
        if re.match(r"^/[A-Za-z]:", path):
            path = path[1:]
        return path
    return text


def _is_audio_file(path: str) -> bool:
    ext = os.path.splitext(path)[1].lower()
    return ext in AUDIO_DROP_EXTENSION_SET and os.path.isfile(path)


def _playlist_targets(path: str) -> list[str]:
    targets = []
    base = os.path.dirname(path)
    try:
        lines = Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return targets
    ext = os.path.splitext(path)[1].lower()
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if ext == ".pls":
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            if not key.strip().lower().startswith("file"):
                continue
            line = value.strip()
        if line.lower().startswith("file:"):
            line = path_from_drop_entry(line)
        elif line.lower().startswith(("http://", "https://")):
            continue
        elif not os.path.isabs(line):
            line = os.path.join(base, line)
        if line:
            targets.append(line)
    return targets


def collect_dropped_audio(entries, limit: int = DROP_FILE_LIMIT) -> tuple[list[str], bool]:
    """Return playable audio paths, in drop order, and whether the cap was hit."""
    found: list[str] = []
    seen: set[str] = set()
    truncated = False

    def add_file(path: str) -> None:
        nonlocal truncated
        if len(found) >= limit:
            truncated = True
            return
        if not path or not _is_audio_file(path):
            return
        try:
            key = os.path.abspath(os.path.expanduser(path))
        except (OSError, ValueError):
            return
        if key in seen:
            return
        seen.add(key)
        found.append(key)

    def add_dir(path: str) -> None:
        for root, dirs, files in os.walk(path):
            dirs[:] = sorted(name for name in dirs if not name.startswith("."))
            for name in sorted(files):
                if name.startswith("."):
                    continue
                add_file(os.path.join(root, name))
                if truncated:
                    return

    for entry in entries or []:
        raw = path_from_drop_entry(str(entry))
        if not raw:
            continue
        try:
            raw = os.path.abspath(os.path.expanduser(raw))
        except (OSError, ValueError):
            continue
        ext = os.path.splitext(raw)[1].lower()
        if os.path.isdir(raw):
            add_dir(raw)
        elif ext in PLAYLIST_EXTENSIONS and os.path.isfile(raw):
            for target in _playlist_targets(raw):
                add_file(target)
                if truncated:
                    break
        else:
            add_file(raw)
        if truncated:
            break
    return found, truncated


def audio_track_items(paths) -> list[dict]:
    items = []
    seen = set()
    for raw in paths or []:
        try:
            path = os.path.abspath(os.path.expanduser(str(raw)))
        except (OSError, ValueError):
            continue
        if path in seen or not _is_audio_file(path):
            continue
        seen.add(path)
        try:
            stat = os.stat(path)
            size_mb = stat.st_size / 1048576.0
            mtime = stat.st_mtime
        except OSError:
            continue
        ext = os.path.splitext(path)[1].lower()
        items.append({
            "name": os.path.basename(path),
            "path": path,
            "size_mb": size_mb,
            "mtime": mtime,
            "ext": ext[1:].upper(),
        })
    return items


def is_drop_manifest(path) -> bool:
    try:
        resolved = Path(path).expanduser().resolve()
        root = drop_dir().resolve()
    except (OSError, RuntimeError, ValueError):
        return False
    return resolved.is_file() and resolved.parent == root and resolved.suffix == ".json"


def write_drop_manifest(paths, truncated: bool = False, rejected: bool = False) -> Path:
    folder = drop_dir()
    folder.mkdir(parents=True, exist_ok=True)
    payload = {
        "paths": [str(path) for path in paths],
        "truncated": bool(truncated),
        "rejected": bool(rejected),
    }
    dest = folder / f"{time.time_ns()}-{os.getpid()}-{uuid.uuid4().hex[:8]}.json"
    tmp = dest.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload), encoding="utf-8")
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    os.replace(tmp, dest)
    return dest


def read_drop_manifest(path) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return {"paths": [], "truncated": False, "rejected": True}
    listed = data.get("paths") if isinstance(data.get("paths"), list) else []
    return {
        "paths": [str(item) for item in listed],
        "truncated": bool(data.get("truncated")),
        "rejected": bool(data.get("rejected")),
    }


def drop_osc(manifest: Path) -> bytes:
    text = str(manifest)
    if "\x07" in text or "\x1b" in text or "\n" in text or "\r" in text:
        raise ValueError("drop manifest path cannot be sent to the terminal")
    return DROP_OSC_PREFIX + text.encode("utf-8") + b"\x07"


def _schedule(fn) -> None:
    """Run fn on the GTK thread when the host is pumping GLib."""
    try:
        from gi.repository import GLib
        GLib.idle_add(fn)
    except Exception:
        fn()


def feed_terminal_bytes(terminal, payload: bytes) -> None:
    try:
        terminal.feed_child(payload)
    except TypeError:
        terminal.feed_child(payload, len(payload))


def deliver_drop_to_terminal(terminal, paths, truncated: bool = False, rejected: bool = False) -> Path:
    manifest = write_drop_manifest(paths, truncated=truncated, rejected=rejected)
    feed_terminal_bytes(terminal, drop_osc(manifest))
    return manifest


def enable_audio_file_drop(widget, on_uris) -> None:
    """Accept file drops on a GTK widget. on_uris receives the raw URI list."""
    from gi.repository import Gdk, Gtk

    widget.drag_dest_set(
        Gtk.DestDefaults.MOTION | Gtk.DestDefaults.DROP,
        [],
        Gdk.DragAction.COPY,
    )
    widget.drag_dest_add_uri_targets()

    def _motion(wid, context, _x, _y, when):
        Gdk.drag_status(context, Gdk.DragAction.COPY, when)
        try:
            wid.stop_emission_by_name("drag-motion")
        except Exception:
            pass
        return True

    def _received(wid, context, _x, _y, selection, _info, when):
        uris = []
        try:
            uris = [str(uri) for uri in (selection.get_uris() or []) if uri]
        except Exception:
            uris = []
        if not uris:
            try:
                text = selection.get_text() or ""
            except Exception:
                text = ""
            uris = [line.strip() for line in str(text).splitlines() if line.strip() and not line.startswith("#")]
        try:
            Gtk.drag_finish(context, bool(uris), False, when)
        except Exception:
            pass
        try:
            wid.stop_emission_by_name("drag-data-received")
        except Exception:
            pass
        if uris:
            try:
                on_uris(uris)
            except Exception:
                pass
        return True

    widget.connect("drag-motion", _motion)
    widget.connect("drag-data-received", _received)


class AudioDropBridge:
    """Scan dropped URIs off the GTK thread, then feed the player terminal."""

    def __init__(self):
        self.terminal = None
        self.ready = False
        self._pending = []
        self._lock = threading.Lock()

    def attach(self, terminal) -> None:
        self.terminal = terminal
        enable_audio_file_drop(terminal, self.submit_uris)

    def mark_ready(self) -> None:
        self.ready = True
        self._flush()

    def submit_uris(self, uris) -> None:
        threading.Thread(target=self._scan, args=(list(uris),), daemon=True).start()

    def _scan(self, uris) -> None:
        paths, truncated = collect_dropped_audio(uris)
        self._enqueue(paths, truncated, rejected=not paths)

    def _enqueue(self, paths, truncated: bool, rejected: bool) -> None:
        with self._lock:
            self._pending.append((list(paths), bool(truncated), bool(rejected)))
        self._flush()

    def _flush(self) -> None:
        if not self.ready or self.terminal is None:
            return

        def _send():
            with self._lock:
                batch = self._pending
                self._pending = []
            for paths, truncated, rejected in batch:
                try:
                    deliver_drop_to_terminal(
                        self.terminal, paths, truncated=truncated, rejected=rejected,
                    )
                except Exception:
                    pass
            return False

        _schedule(_send)
