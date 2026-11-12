"""One definition of the audio file types MP Audio Player can open.

Every scanner, picker and web route used to keep its own extension tuple, so a
format could be dropped onto the Liquid player and still be invisible in the
Mix Archive and Music Folders listings. This module is the single list those
modules import.

The player decodes with FFmpeg first for anything libsndfile cannot open, and
falls back to the other backend, so an extension belongs here when one of the
two backends can decode it. `prefers_ffmpeg()` decides which backend is tried
first.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Union

# Ordered roughly by family so dialog filters read sensibly.
AUDIO_EXTENSIONS = (
    # Lossless / uncompressed
    ".flac", ".wav", ".wave", ".w64", ".rf64",
    # MPEG audio
    ".mp3", ".mp2", ".mp1", ".mpga",
    # Ogg family
    ".ogg", ".oga", ".opus", ".spx",
    # MPEG-4 / Apple
    ".m4a", ".m4b", ".m4p", ".aac", ".alac",
    # PCM containers
    ".aiff", ".aif", ".aifc",
    # Windows Media
    ".wma",
    # Lossless compressors
    ".ape", ".wv", ".tta", ".tak",
    # Musepack
    ".mpc", ".mpp",
    # Cinema audio
    ".ac3", ".eac3", ".dts",
    # Apple / Sun / other PCM
    ".caf", ".au", ".snd",
    # Speech
    ".amr", ".3ga",
    # Direct Stream Digital
    ".dsf", ".dff",
    # Matroska audio
    ".mka",
    # Legacy Creative Voice
    ".voc",
)
AUDIO_EXTENSION_SET = frozenset(AUDIO_EXTENSIONS)

# Lossless codecs, used for the "Lossless" badge in the player HUD.
LOSSLESS_EXTENSIONS = frozenset({
    ".flac", ".wav", ".wave", ".w64", ".rf64",
    ".alac", ".aiff", ".aif", ".aifc", ".ape", ".wv", ".tta", ".tak",
    ".caf", ".au", ".snd", ".dsf", ".dff",
})

# Formats libsndfile opens natively. Everything else starts in FFmpeg.
SOUNDFILE_EXTENSIONS = frozenset({
    ".flac", ".wav", ".wave", ".w64", ".rf64",
    ".aiff", ".aif", ".aifc", ".ogg", ".oga",
    ".au", ".snd", ".caf", ".mp3",
})

# Browsers stream these with a real MIME type; anything else falls back to
# audio/mpeg, which every browser sniffs.
AUDIO_MIME_TYPES = {
    ".flac": "audio/flac",
    ".wav": "audio/wav",
    ".wave": "audio/wav",
    ".w64": "audio/wav",
    ".rf64": "audio/wav",
    ".mp3": "audio/mpeg",
    ".mp2": "audio/mpeg",
    ".mp1": "audio/mpeg",
    ".mpga": "audio/mpeg",
    ".ogg": "audio/ogg",
    ".oga": "audio/ogg",
    ".spx": "audio/ogg",
    ".opus": "audio/opus",
    ".m4a": "audio/mp4",
    ".m4b": "audio/mp4",
    ".m4p": "audio/mp4",
    ".alac": "audio/mp4",
    ".aac": "audio/aac",
    ".aiff": "audio/aiff",
    ".aif": "audio/aiff",
    ".aifc": "audio/aiff",
    ".wma": "audio/x-ms-wma",
    ".ape": "audio/x-ape",
    ".wv": "audio/x-wavpack",
    ".tta": "audio/x-tta",
    ".tak": "audio/x-tak",
    ".mpc": "audio/x-musepack",
    ".mpp": "audio/x-musepack",
    ".ac3": "audio/ac3",
    ".eac3": "audio/eac3",
    ".dts": "audio/vnd.dts",
    ".caf": "audio/x-caf",
    ".au": "audio/basic",
    ".snd": "audio/basic",
    ".amr": "audio/amr",
    ".3ga": "audio/amr",
    ".dsf": "audio/x-dsd",
    ".dff": "audio/x-dsd",
    ".mka": "audio/x-matroska",
    ".voc": "audio/x-voc",
}

# Containers that carry video too. They stay out of the audio lists so a
# dropped movie is not queued as a track.
VIDEO_EXTENSIONS = frozenset({
    ".mp4", ".m4v", ".mkv", ".mov", ".avi", ".webm", ".ts", ".m2ts", ".flv", ".wmv",
})


def extension_of(path: Union[str, os.PathLike, None]) -> str:
    """Lowercase extension including the dot, or "" when there is none."""
    try:
        return os.path.splitext(str(path))[1].lower()
    except (TypeError, ValueError):
        return ""


def is_audio_path(path: Union[str, os.PathLike, None]) -> bool:
    return extension_of(path) in AUDIO_EXTENSION_SET


def is_lossless_path(path: Union[str, os.PathLike, None]) -> bool:
    return extension_of(path) in LOSSLESS_EXTENSIONS


def prefers_ffmpeg(path: Union[str, os.PathLike, None]) -> bool:
    """Formats libsndfile often cannot open should start in FFmpeg."""
    return extension_of(path) not in SOUNDFILE_EXTENSIONS


def mime_type_for(path: Union[str, os.PathLike, None], default: str = "audio/mpeg") -> str:
    return AUDIO_MIME_TYPES.get(extension_of(path), default)


def display_extension(path: Union[str, os.PathLike, None], default: str = "AUDIO") -> str:
    return extension_of(path).lstrip(".").upper() or default


def dialog_audio_globs(separator: str = " ") -> str:
    return separator.join(f"*{ext}" for ext in AUDIO_EXTENSIONS)


AUDIO_DIALOG_LABEL = "Audio Files (All types)"


def kdialog_audio_filter() -> str:
    return f"{dialog_audio_globs(' ')} | {AUDIO_DIALOG_LABEL}"


def zenity_audio_filter() -> str:
    return f"{AUDIO_DIALOG_LABEL} | {dialog_audio_globs(' ')}"


def windows_audio_filter() -> str:
    return f"{AUDIO_DIALOG_LABEL}|{dialog_audio_globs(';')}|All Files (*.*)|*.*"


def macos_audio_file_types() -> list[str]:
    """Values for AppleScript `choose file of type`."""
    return ["public.audio"] + [ext.lstrip(".") for ext in AUDIO_EXTENSIONS]


if __name__ == "__main__":
    print(f"{len(AUDIO_EXTENSIONS)} audio extensions")
    print(dialog_audio_globs("\n"))
