"""Terminal lifecycle for MP Mix Manager TTY Audio Mode.

A Linux console keeps the last termios state. If the player exits without
restoring it, the next shell has a hidden cursor and no echo. This module
saves the attributes, switches to single-key input, and puts them back on
every exit path it can still run.

Single-key input uses cbreak rather than raw. cbreak returns each key
without waiting for Enter, and it leaves ISIG on so Ctrl+C still delivers
SIGINT and the restore trap can run. Pass raw=True for a fully raw line
discipline. Both modes restore the saved attributes.

Frames are drawn by parking the cursor at home and overwriting cells.
A full clear is reserved for a real size change. Output is write-through
so a status line is not held in the block buffer.

Bash and Python exchange records as newline-delimited JSON. Each record
is flushed. Keeping a record under PIPE_BUF (4096 bytes on Linux) lets a
reader take it in one read and avoids a pipe deadlock where each side is
waiting for the other to drain.
"""

from __future__ import annotations

import json
import os
import select
import signal
import sys
from typing import Any, Iterator, Optional, TextIO

try:
    import termios
    import tty
except ImportError:  # pragma: no cover - non-Unix
    termios = None  # type: ignore
    tty = None  # type: ignore

_fd: Optional[int] = None
_saved: Optional[list] = None
_resized = False
_signals_installed = False
_previous_handlers: dict = {}

PIPE_BUF = 4096
_CURSOR_ON = b"\033[?25h\033[?7h\033[?1049l"


def tty_mode_enabled() -> bool:
    return os.environ.get("MP_MIX_MANAGER_TTY_MODE") == "1"


def configure_stdio() -> None:
    """Make stdout and stderr visible as soon as a TTY frame is written."""
    for stream in (sys.stdout, sys.stderr):
        if stream is None:
            continue
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(write_through=True)
        except Exception:
            pass
        try:
            stream.flush()
        except Exception:
            pass


def saved_attributes():
    return _saved


def terminal_fd() -> Optional[int]:
    return _fd


def arm_terminal(fd: Optional[int] = None, *, raw: bool = False, install_signals: bool = True) -> bool:
    """Save the current termios and switch this fd to single-key input."""
    global _fd, _saved
    if termios is None or tty is None:
        return False
    if fd is None:
        if not sys.stdin or not sys.stdin.isatty():
            return False
        fd = sys.stdin.fileno()
    try:
        current = termios.tcgetattr(fd)
    except Exception:
        return False
    _fd = fd
    if _saved is None:
        _saved = current
    try:
        if raw:
            tty.setraw(fd)
        else:
            tty.setcbreak(fd)
            updated = termios.tcgetattr(fd)
            updated[1] |= termios.OPOST
            termios.tcsetattr(fd, termios.TCSADRAIN, updated)
    except Exception:
        restore_terminal()
        return False
    if install_signals:
        _install_signals()
    return True


def restore_terminal() -> None:
    """Put the saved termios back and show the cursor. Safe to call twice."""
    global _fd, _saved
    fd, saved = _fd, _saved
    _fd = None
    _saved = None
    if fd is not None and saved is not None and termios is not None:
        try:
            termios.tcsetattr(fd, termios.TCSANOW, saved)
        except Exception:
            pass
    try:
        os.write(fd if fd is not None else 1, _CURSOR_ON)
    except Exception:
        pass


def consume_resize() -> bool:
    """Return True once after SIGWINCH. The next frame may clear the screen."""
    global _resized
    flag = _resized
    _resized = False
    return flag


def note_resize(signum: int = 0, frame: Any = None) -> None:
    global _resized
    _resized = True


def present_lines(lines: list[str], *, full_clear: bool = False, stream: Optional[TextIO] = None) -> None:
    """Overwrite the visible cells. full_clear is for a resize, not every tick."""
    out = stream or sys.stdout
    parts = ["\033[?7l"]
    if full_clear:
        parts.append("\033[2J")
    parts.append("\033[H")
    parts.append("\n".join(lines))
    out.write("".join(parts))
    try:
        out.flush()
    except Exception:
        pass


def wait_for_input(fd: int, timeout: float) -> bytes:
    """Read one burst of keys. An empty result means the timeout elapsed."""
    try:
        ready = select.select([fd], [], [], timeout)[0]
    except (OSError, ValueError):
        return b""
    if not ready:
        return b""
    try:
        return os.read(fd, 64)
    except OSError:
        return b""


def write_ndjson(obj: Any, stream: Optional[TextIO] = None) -> None:
    """Write one JSON object and flush it. The line stays under PIPE_BUF."""
    out = stream or sys.stdout
    payload = json.dumps(obj, separators=(",", ":"), ensure_ascii=False)
    if len(payload.encode("utf-8")) > PIPE_BUF:
        raise ValueError(f"NDJSON record is larger than PIPE_BUF ({PIPE_BUF})")
    out.write(payload + "\n")
    out.flush()


def iter_ndjson(stream: TextIO) -> Iterator[Any]:
    """Yield JSON objects from a newline-delimited stream."""
    for line in stream:
        text = line.strip()
        if not text:
            continue
        yield json.loads(text)


def _crash_restore(signum: int, frame: Any = None) -> None:
    """Restore the console, then return the signal to its default action."""
    restore_terminal()
    try:
        os.write(1, b"\n[!] Application terminated.\n")
    except Exception:
        pass
    try:
        signal.signal(signum, signal.SIG_DFL)
    except Exception:
        os._exit(128 + int(signum))
    os.kill(os.getpid(), signum)


def _install_signals() -> None:
    global _signals_installed
    if _signals_installed:
        return
    _signals_installed = True
    for sig in (signal.SIGINT, signal.SIGTERM, getattr(signal, "SIGHUP", None), getattr(signal, "SIGSEGV", None)):
        if sig is None:
            continue
        try:
            _previous_handlers[sig] = signal.getsignal(sig)
            if sig == signal.SIGSEGV:
                signal.signal(sig, _crash_restore)
            else:
                signal.signal(sig, _forward_signal)
        except Exception:
            pass
    if hasattr(signal, "SIGWINCH"):
        try:
            signal.signal(signal.SIGWINCH, note_resize)
        except Exception:
            pass
    import atexit
    atexit.register(restore_terminal)


def _forward_signal(signum: int, frame: Any) -> None:
    restore_terminal()
    previous = _previous_handlers.get(signum)
    if callable(previous):
        previous(signum, frame)
        return
    os._exit(128 + int(signum))


__all__ = [
    "PIPE_BUF",
    "arm_terminal",
    "configure_stdio",
    "consume_resize",
    "iter_ndjson",
    "note_resize",
    "present_lines",
    "restore_terminal",
    "tty_mode_enabled",
    "wait_for_input",
    "write_ndjson",
]
