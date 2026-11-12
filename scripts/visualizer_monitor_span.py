#!/usr/bin/env python3
"""F10 / F11 monitor-span support shared by the MP Visualizer backends.

Pressing **F10** inside the MP Visualizer asks GLFW for the monitor layout and
launches one more visualizer on every monitor except the one the user is on.
Two seconds later those extra windows go fullscreen. Pressing **F10** or
**F11** again closes them again and leaves only the original window running.

Pressing **F11** does exactly the same, but every spawned window gets a
different preset chosen at random.

Design notes
------------
* The window that received the key ("owner") spawns children with
  ``--span-role spawned`` and writes a small JSON session file. Each child
  polls that file, so closing the session (or the owner exiting) closes every
  child even though there is no IPC server.
* A child that receives F10/F11 writes a stop marker instead of killing the
  session directly. The owner sees it on its next poll and tears the span
  down. Anything that kills only the owner is also covered: when the owner
  disappears, ``read_span_session`` reports no session and the children exit.
* The owner window itself is never closed. That keeps a visualizer bonded
  behind the MP Liquid Player alive while the other screens are spanned, and
  it is also what "revert" means: only the spawned copies disappear.
"""
from __future__ import annotations

import json
import os
import random
import subprocess
import sys
import time
from ctypes import byref, c_int
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

SPAN_SESSION_FILE = Path.home() / ".config" / "mix-manager" / "visualizer_span.json"
SPAN_STOP_FILE = Path.home() / ".config" / "mix-manager" / "visualizer_span.stop"
SPAN_LOG_FILE = Path.home() / ".config" / "mix-manager" / "liquid_visualizer_span.log"
CONFIG_DIR = SPAN_SESSION_FILE.parent
SPAN_FULLSCREEN_DELAY = 2.0
MIN_WINDOW_SIDE = 64

ROLE_NONE, ROLE_OWNER, ROLE_SPAWNED = "", "owner", "spawned"


def project_root() -> Path:
    """Locate the program folder that holds ``MP_Liquid_Visualizer.py``."""
    here = Path(__file__).resolve().parent
    if (here.parent / "MP_Liquid_Visualizer.py").is_file():
        return here.parent
    return here


def visualizer_entry_path() -> Optional[Path]:
    """The launcher used when a spanned window is spawned."""
    root = project_root()
    for cand in (root / "MP_Liquid_Visualizer.py", root / "scripts" / "mp_liquid_visualizer_vulkan.py"):
        if cand.is_file():
            return cand
    return None


def _is_windows() -> bool:
    return sys.platform == "win32"


def pid_alive(pid: Any) -> bool:
    """Return True when ``pid`` belongs to a running process."""
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    if _is_windows():
        try:
            import ctypes

            handle = ctypes.windll.kernel32.OpenProcess(0x1000, 0, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
            if not handle:
                return False
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        except Exception:
            return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def span_log(message: str) -> None:
    """Append a line to the span log and mirror it to stderr."""
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}"
    print(line, file=sys.stderr, flush=True)
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(SPAN_LOG_FILE, "a", encoding="utf-8") as fp:
            fp.write(line + "\n")
    except OSError:
        pass


def _write_json_atomic(path: Path, data: Dict[str, Any]) -> None:
    """Write a small JSON file so readers never see a half-written document."""
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + f".{os.getpid()}.tmp")
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        pass


def read_span_session() -> Optional[Dict[str, Any]]:
    """Return the live monitor-span session, or None when there is none."""
    try:
        data = json.loads(SPAN_SESSION_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    if not pid_alive(data.get("owner_pid", 0)):
        return None
    return data


def write_span_session(data: Dict[str, Any]) -> None:
    _write_json_atomic(SPAN_SESSION_FILE, data)


def clear_span_session() -> None:
    for path in (SPAN_SESSION_FILE, SPAN_STOP_FILE):
        try:
            path.unlink()
        except OSError:
            pass


def request_span_stop(owner_pid: int) -> None:
    """Ask the owning window to close the span (written by a spawned window)."""
    _write_json_atomic(SPAN_STOP_FILE, {"stop": True, "owner_pid": int(owner_pid), "at": time.time()})


def stop_requested(owner_pid: int) -> bool:
    """True when a spawned window asked this owner to close the span."""
    try:
        data = json.loads(SPAN_STOP_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    try:
        return bool(data.get("stop")) and int(data.get("owner_pid", 0)) == int(owner_pid)
    except (TypeError, ValueError):
        return False


def parse_span_bounds(text: Optional[str]) -> Optional[Tuple[int, int, int, int]]:
    """Parse the ``x,y,width,height`` monitor bounds handed to a spawned window."""
    if not text:
        return None
    try:
        parts = [int(float(piece.strip())) for piece in str(text).split(",")]
    except (TypeError, ValueError):
        return None
    if len(parts) != 4:
        return None
    x, y, width, height = parts
    if width < MIN_WINDOW_SIDE or height < MIN_WINDOW_SIDE:
        return None
    return x, y, width, height


def span_preset_plan(current: Dict[str, Any], count: int, random_mode: bool) -> List[str]:
    """Preset keys for the windows spawned by F10 (plain) or F11 (random).

    F10 mirrors the preset already on screen. F11 shuffles the library and
    gives each spawned window a different preset, starting away from the
    preset on the current monitor. With more monitors than presets the list
    wraps, but adjacent repeats are avoided when possible.
    """
    try:
        from mp_liquid_visualizer_vulkan import VISUALIZER_PRESETS
    except ImportError:
        from scripts.mp_liquid_visualizer_vulkan import VISUALIZER_PRESETS
    keys = [p["key"] for p in VISUALIZER_PRESETS]
    if count <= 0 or not keys:
        return []
    current_key = current.get("key", keys[0])
    if not random_mode:
        return [current_key] * count
    pool = [k for k in keys if k != current_key] or list(keys)
    random.shuffle(pool)
    plan = [pool[i % len(pool)] for i in range(count)]
    if len(pool) > 1:
        for i in range(1, len(plan)):
            if plan[i] == plan[i - 1]:
                j = (i + 1) % len(plan)
                plan[i], plan[j] = plan[j], plan[i]
    return plan


def monitor_rects(glfw) -> List[Tuple[str, Tuple[int, int, int, int]]]:
    """Return ``(name, (x, y, width, height))`` for every connected monitor."""
    if not glfw:
        return []
    rects: List[Tuple[str, Tuple[int, int, int, int]]] = []
    try:
        count = c_int()
        monitors = glfw.glfwGetMonitors(byref(count))
        if not monitors or count.value <= 0:
            return []
        for index in range(count.value):
            mon = monitors[index]
            mx, my = c_int(), c_int()
            glfw.glfwGetMonitorPos(mon, byref(mx), byref(my))
            mode = glfw.glfwGetVideoMode(mon)
            if not mode:
                continue
            md = mode.contents
            name = ""
            if hasattr(glfw, "glfwGetMonitorName"):
                try:
                    raw = glfw.glfwGetMonitorName(mon)
                    if raw:
                        name = raw.decode("utf-8", errors="ignore")
                except Exception:
                    name = ""
            rects.append((name or f"Monitor {index + 1}",
                          (int(mx.value), int(my.value), int(md.width), int(md.height))))
    except Exception:
        return rects
    return rects


class MonitorSpanMixin:
    """F10/F11 window spanning, mixed into both visualizer renderers.

    The renderer must provide ``_glfw``, ``_window``, ``preset``,
    ``is_fullscreen``, ``toggle_fullscreen()``, ``request_close()`` and
    ``window_pos()``. Everything else lives here so Vulkan and OpenGL behave
    identically.
    """

    # -- state ------------------------------------------------------------
    def _init_span_state(self, span_bounds: Optional[Tuple[int, int, int, int]] = None,
                         span_role: str = "", span_delay: float = SPAN_FULLSCREEN_DELAY) -> None:
        self._span_role = span_role or ROLE_NONE
        self._span_bounds = span_bounds
        self._span_children: List[subprocess.Popen] = []
        self._span_pending: List[Tuple[subprocess.Popen, float]] = []
        self._span_session_open = False
        self._span_poll_at = 0.0
        self._span_owner_mode = ""
        # A spawned window fills its monitor once the delay has elapsed.
        self._span_fullscreen_at = (time.monotonic() + max(0.0, float(span_delay))
                                    if self._span_role == ROLE_SPAWNED else 0.0)

    def _span_is_active(self) -> bool:
        """True when this window currently participates in a span."""
        if self._span_role == ROLE_OWNER:
            return bool(self._span_session_open or self._span_children or self._span_pending)
        if self._span_role == ROLE_SPAWNED:
            return read_span_session() is not None
        return False

    # -- geometry ---------------------------------------------------------
    def monitor_rects(self) -> List[Tuple[str, Tuple[int, int, int, int]]]:
        return monitor_rects(getattr(self, "_glfw", None))

    def _window_monitor(self):
        """Return ``(GLFWmonitor, rect)`` for the monitor holding the window."""
        glfw = getattr(self, "_glfw", None)
        if not glfw:
            return None, None
        try:
            wx, wy = self.window_pos()
        except Exception:
            wx, wy = (0, 0)
        try:
            ww, wh = self.window_size()
        except Exception:
            ww, wh = getattr(self, "width", 1) or 1, getattr(self, "height", 1) or 1
        ww, wh = max(1, int(ww)), max(1, int(wh))
        best, best_area, best_rect = None, -1, None
        try:
            count = c_int()
            monitors = glfw.glfwGetMonitors(byref(count))
            if not monitors or count.value <= 0:
                return None, None
            for index in range(count.value):
                mon = monitors[index]
                mx, my = c_int(), c_int()
                glfw.glfwGetMonitorPos(mon, byref(mx), byref(my))
                mode = glfw.glfwGetVideoMode(mon)
                if not mode:
                    continue
                md = mode.contents
                rect = (int(mx.value), int(my.value), int(md.width), int(md.height))
                area = (max(0, min(int(wx) + ww, rect[0] + rect[2]) - max(int(wx), rect[0]))
                        * max(0, min(int(wy) + wh, rect[1] + rect[3]) - max(int(wy), rect[1])))
                if area > best_area:
                    best, best_area, best_rect = mon, area, rect
        except Exception:
            return None, None
        return best, best_rect

    def monitor_bounds(self) -> Tuple[int, int, int, int]:
        """Bounds of the monitor this window is on, or its assigned bounds."""
        if getattr(self, "_span_bounds", None):
            return self._span_bounds
        _mon, rect = self._window_monitor()
        return rect or (0, 0, 0, 0)

    def span_monitor(self):
        """The GLFW monitor this window must fill, when it has an assignment."""
        bounds = getattr(self, "_span_bounds", None)
        if not bounds:
            return None
        for _name, rect in self.monitor_rects():
            if tuple(rect) == tuple(bounds):
                return self._monitor_handle_for(rect)
        return None

    def _monitor_handle_for(self, rect):
        """Return the GLFW monitor handle whose desktop rect matches ``rect``."""
        glfw = getattr(self, "_glfw", None)
        if not glfw:
            return None
        try:
            count = c_int()
            monitors = glfw.glfwGetMonitors(byref(count))
            if not monitors or count.value <= 0:
                return None
            for index in range(count.value):
                mon = monitors[index]
                mx, my = c_int(), c_int()
                glfw.glfwGetMonitorPos(mon, byref(mx), byref(my))
                mode = glfw.glfwGetVideoMode(mon)
                if not mode:
                    continue
                md = mode.contents
                if (int(mx.value), int(my.value), int(md.width), int(md.height)) == tuple(rect):
                    return mon
        except Exception:
            return None
        return None

    # -- lifecycle --------------------------------------------------------
    def start_monitor_span(self, random_mode: bool = False) -> List[subprocess.Popen]:
        """Spawn a visualizer on every monitor except the one in use."""
        if self._span_role == ROLE_SPAWNED:
            # A spawned window never owns the span; hand the toggle to its owner.
            self._request_owner_span_stop()
            return []
        if self._span_role == ROLE_OWNER and self._span_is_active():
            self.stop_monitor_span()
            return []

        here = self.monitor_bounds()
        others = [rect for _name, rect in self.monitor_rects() if tuple(rect) != tuple(here)]
        if not others:
            span_log("F10/F11 ignored: no other monitor is connected")
            return []

        entry = visualizer_entry_path()
        if entry is None:
            span_log("F10/F11 ignored: MP_Liquid_Visualizer.py was not found")
            return []

        plan = span_preset_plan(getattr(self, "preset", {}) or {}, len(others), random_mode)
        session: Dict[str, Any] = {
            "owner_pid": os.getpid(),
            "mode": "random" if random_mode else "mirror",
            "owner_monitor": list(here),
            "monitors": [list(rect) for rect in others],
            "presets": list(plan),
            "fullscreen_delay": SPAN_FULLSCREEN_DELAY,
            "started_at": time.time(),
            "children": [],
        }
        self._span_role = ROLE_OWNER
        self._span_owner_mode = session["mode"]
        self._span_children = []
        self._span_pending = []
        try:
            SPAN_STOP_FILE.unlink()
        except OSError:
            pass
        write_span_session(session)
        self._span_session_open = True

        log = None
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            log = open(SPAN_LOG_FILE, "a", encoding="utf-8")
        except OSError:
            log = None
        try:
            for rect, preset_key in zip(others, plan):
                cmd = [
                    sys.executable, str(entry),
                    "--preset", str(preset_key),
                    "--span-bounds", ",".join(str(int(v)) for v in rect),
                    "--span-role", ROLE_SPAWNED,
                ]
                backend = getattr(self, "_span_backend", "")
                if backend:
                    # Use the same drawing backend as the window that spawned us.
                    cmd += ["--backend", backend]
                try:
                    proc = subprocess.Popen(
                        cmd, cwd=str(project_root()), stdin=subprocess.DEVNULL,
                        stdout=log or subprocess.DEVNULL, stderr=log or subprocess.DEVNULL,
                        start_new_session=True,
                    )
                except Exception as exc:  # pragma: no cover - depends on the host
                    span_log(f"Could not spawn a visualizer on {rect}: {exc}")
                    continue
                self._span_children.append(proc)
                self._span_pending.append((proc, time.monotonic() + SPAN_FULLSCREEN_DELAY))
                session["children"].append(proc.pid)
                span_log(f"Spawned {preset_key} on monitor {rect} (PID {proc.pid}, {session['mode']} mode)")
        finally:
            if log is not None:
                try:
                    log.close()
                except OSError:
                    pass
            write_span_session(session)

        if not self._span_children:
            clear_span_session()
            self._span_session_open = False
        return list(self._span_children)

    def stop_monitor_span(self) -> None:
        """Close every spawned window, leaving only the window in use."""
        if self._span_role == ROLE_SPAWNED:
            self._request_owner_span_stop()
            return
        self._terminate_span_children()
        self._span_session_open = False
        self._span_owner_mode = ""
        clear_span_session()
        span_log("Monitor span closed; spawned windows stopped")

    def _request_owner_span_stop(self) -> None:
        session = read_span_session() or {}
        owner = int(session.get("owner_pid", 0) or 0)
        if owner:
            request_span_stop(owner)
            span_log(f"Asked owner PID {owner} to close the monitor span")
        else:
            clear_span_session()

    def _terminate_span_children(self) -> None:
        # A child that has not reached its fullscreen deadline appears in both
        # lists; terminate each process exactly once.
        seen = set()
        for proc, _due in self._span_pending:
            if id(proc) not in seen:
                seen.add(id(proc))
                self._stop_span_child(proc)
        self._span_pending = []
        for proc in self._span_children:
            if id(proc) not in seen:
                seen.add(id(proc))
                self._stop_span_child(proc)
        self._span_children = []

    @staticmethod
    def _stop_span_child(proc: subprocess.Popen) -> None:
        """Terminate one spawned visualizer, force-killing it if it lingers."""
        try:
            if proc.poll() is not None:
                return
        except Exception:
            return
        try:
            proc.terminate()
            proc.wait(timeout=2.5)
        except Exception:
            try:
                proc.kill()
                proc.wait(timeout=2.5)
            except Exception:
                pass

    def poll_monitor_span(self) -> None:
        """Delayed fullscreen for spawned windows, teardown when the span ends."""
        now = time.monotonic()
        if self._span_role == ROLE_OWNER:
            if not self._span_session_open:
                return
            if stop_requested(os.getpid()):
                self.stop_monitor_span()
                return
            alive: List[Tuple[subprocess.Popen, float]] = []
            for proc, due in self._span_pending:
                if proc.poll() is None:
                    alive.append((proc, due))
                else:
                    try:
                        self._span_children.remove(proc)
                    except ValueError:
                        pass
            self._span_pending = alive
            if now >= self._span_poll_at:
                self._span_poll_at = now + 0.5
                if not self._span_children and not self._span_pending:
                    self._span_session_open = False
                    self._span_owner_mode = ""
                    clear_span_session()
                    span_log("All spanned windows exited; span session ended")
            return

        if self._span_role != ROLE_SPAWNED:
            return
        if now >= self._span_fullscreen_at > 0.0:
            self._span_fullscreen_at = 0.0
            if not self.is_fullscreen and not getattr(self, "_player_bonded", False):
                try:
                    self.toggle_fullscreen()
                except Exception as exc:  # pragma: no cover - backend specific
                    span_log(f"Spanned window could not go fullscreen: {exc}")
        if now >= self._span_poll_at:
            self._span_poll_at = now + 0.4
            if read_span_session() is None:
                # The owner closed the span (or exited): this copy must go too.
                self.request_close()

    # -- key handling -----------------------------------------------------
    def handle_span_key(self, key: int) -> bool:
        """Handle F10/F11. Returns True when the key belonged to the span."""
        try:
            from mp_liquid_visualizer_vulkan import GLFW_KEY_F10, GLFW_KEY_F11
        except ImportError:
            from scripts.mp_liquid_visualizer_vulkan import GLFW_KEY_F10, GLFW_KEY_F11
        if key not in (GLFW_KEY_F10, GLFW_KEY_F11):
            return False
        if self._span_is_active():
            self.stop_monitor_span()
        else:
            self.start_monitor_span(random_mode=(key == GLFW_KEY_F11))
        return True

    # -- cleanup ----------------------------------------------------------
    def shutdown_monitor_span(self) -> None:
        """Called from close(): never leave spawned windows orphaned."""
        if self._span_role == ROLE_OWNER:
            self._terminate_span_children()
            self._span_session_open = False
            clear_span_session()
        # A closing child must not tear down its siblings or the owner: the
        # owner removes dead children on its own next poll.
