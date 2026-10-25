from __future__ import annotations

import ctypes
import ctypes.util
import faulthandler
import os
import pty
import select
import shutil
import signal
import sys
import threading
import time
from pathlib import Path

# Enable C-level crash tracebacks so any segfault prints the exact Python line
faulthandler.enable()

# --- 0. Restore ctypes._CData for Python 3.14+ (removed from public API, needed by PyOpenGL) ---
if not hasattr(ctypes, "_CData"):
    for base in ctypes.c_int.__mro__:
        if base.__name__ == "_CData":
            ctypes._CData = base
            break

# --- 1. Fix Python 3.14 / 3.15 ctypes.CFUNCTYPE strictness for PyOpenGL ---
_orig_cfunctype = ctypes.CFUNCTYPE
_type_proxy_cache = {}


def _is_valid_ctype(tp):
    if tp is None:
        return True
    return isinstance(tp, type) and issubclass(
        tp,
        (
            ctypes._SimpleCData,
            ctypes.Structure,
            ctypes.Union,
            ctypes._Pointer,
            ctypes.Array,
            ctypes._CFuncPtr,
        ),
    )


def _sanitize_ctype(tp):
    """
    Wrap non-ctype PyOpenGL ArrayDatatype / Wrapper classes in a real
    ctypes.c_void_p subclass that preserves their .from_param() conversion.
    Without this, passing arrays/buffers to OpenGL segfaults in Python 3.15.
    """
    if _is_valid_ctype(tp):
        return tp
    if tp in _type_proxy_cache:
        return _type_proxy_cache[tp]

    orig_from_param = getattr(tp, "from_param", None)

    class _PyOpenGLTypeProxy(ctypes.c_void_p):
        @classmethod
        def from_param(cls, value):
            if value is None:
                return None
            if orig_from_param is not None:
                try:
                    res = orig_from_param(value)
                    if isinstance(res, ctypes._CData) or hasattr(res, "_as_parameter_"):
                        return res
                except Exception:
                    pass
            if isinstance(value, (bytes, bytearray)):
                return ctypes.c_char_p(bytes(value))
            if isinstance(value, str):
                return ctypes.c_char_p(value.encode("utf-8"))
            if isinstance(value, int):
                return ctypes.c_void_p(value)
            if isinstance(value, ctypes._CData):
                return ctypes.byref(value) if not isinstance(value, (ctypes._Pointer, ctypes.Array, ctypes.c_void_p, ctypes.c_char_p)) else value
            if hasattr(value, "ctypes"):
                # numpy array support
                return value.ctypes.data_as(ctypes.c_void_p)
            return ctypes.c_void_p.from_param(value)

    _PyOpenGLTypeProxy.__name__ = f"Proxy_{getattr(tp, '__name__', 'Param')}"
    _type_proxy_cache[tp] = _PyOpenGLTypeProxy
    return _PyOpenGLTypeProxy


def _py315_safe_cfunctype(restype, *argtypes, **kwargs):
    safe_restype = _sanitize_ctype(restype)
    safe_argtypes = tuple(_sanitize_ctype(a) for a in argtypes)
    try:
        return _orig_cfunctype(restype, *argtypes, **kwargs)
    except TypeError:
        return _orig_cfunctype(safe_restype, *safe_argtypes, **kwargs)


ctypes.CFUNCTYPE = _py315_safe_cfunctype

# --- 2. Advanced macOS Compatibility Patch for X11, GL, GLX, and GLFW calls ---
_orig_cdll = ctypes.CDLL

# Keep C callback references and scratch memory alive so C callers never dereference 0x1
_c_func_refs = {}
_scratch_buf = ctypes.create_string_buffer(4096)
_scratch_ptr = ctypes.cast(_scratch_buf, ctypes.c_void_p).value

_FALLBACK_DYLIB = "/usr/lib/libSystem.B.dylib"
_OPENGL_FRAMEWORK = (
    ctypes.util.find_library("OpenGL")
    or "/System/Library/Frameworks/OpenGL.framework/OpenGL"
)

# Load a raw handle to macOS OpenGL.framework for symbol lookups
try:
    _RAW_MACOS_GL = _orig_cdll(_OPENGL_FRAMEWORK)
except OSError:
    _RAW_MACOS_GL = _orig_cdll(_FALLBACK_DYLIB)

_DUMMY_CFUNCTYPE = _orig_cfunctype(ctypes.c_void_p)
_PROC_ADDR_CFUNCTYPE = _orig_cfunctype(ctypes.c_void_p, ctypes.c_char_p)


def _get_dummy_cfunc(name: str):
    """
    Return a real ctypes CFuncPtr.
    Returns 0 (NULL) by default so C code checking for NULL pointers doesn't
    dereference invalid address 0x1 and segfault.
    """
    sname = str(name)
    if sname not in _c_func_refs:
        if sname in ("glXGetProcAddress", "glXGetProcAddressARB", "eglGetProcAddress"):
            def _proc_addr(sym_bytes):
                if not sym_bytes:
                    return 0
                sym = sym_bytes.decode("utf-8", errors="ignore") if isinstance(sym_bytes, bytes) else str(sym_bytes)
                try:
                    fn = _orig_cdll.__getitem__(_RAW_MACOS_GL, sym)
                    return ctypes.cast(fn, ctypes.c_void_p).value or 0
                except Exception:
                    return 0
            cfunc = _PROC_ADDR_CFUNCTYPE(_proc_addr)
        elif sname in ("XOpenDisplay",):
            # Return valid zeroed scratch memory so structs reading Display* don't segfault
            def _open_disp(*args):
                return _scratch_ptr
            cfunc = _DUMMY_CFUNCTYPE(_open_disp)
        else:
            def _noop(*args):
                return 0
            cfunc = _DUMMY_CFUNCTYPE(_noop)

        cfunc.__name__ = sname
        _c_func_refs[sname] = cfunc
    return _c_func_refs[sname]


# Force PyOpenGL to use native macOS (darwin) platform BEFORE liquid_glass_opengl imports it
os.environ["PYOPENGL_PLATFORM"] = "darwin"
try:
    import OpenGL.platform.baseplatform as _bp
    import OpenGL.platform.ctypesloader as _cl

    def _safe_function_type_for(self, dll):
        def _builder(restype, *argtypes):
            safe_res = _sanitize_ctype(restype)
            safe_args = tuple(_sanitize_ctype(a) for a in argtypes)
            return _orig_cfunctype(safe_res, *safe_args)
        return _builder

    _bp.BasePlatform.functionTypeFor = _safe_function_type_for

    def _safe_build_function(functionType, name, dll):
        """Build a PyOpenGL ctypes function using _PyOpenGLTypeProxy argtypes for Python 3.15."""
        safe_res = _sanitize_ctype(getattr(functionType, "_restype_", ctypes.c_void_p))
        raw_args = getattr(functionType, "_argtypes_", ())
        safe_args = tuple(_sanitize_ctype(a) for a in raw_args)
        safe_ftype = _orig_cfunctype(safe_res, *safe_args)
        # Always look up real gl* functions in _RAW_MACOS_GL if dll is missing them
        target_dll = _RAW_MACOS_GL if str(name).startswith("gl") else dll
        try:
            func = safe_ftype((name, target_dll))
            func.argtypes = safe_args
            func.restype = safe_res
            return func
        except (AttributeError, OSError, TypeError):
            try:
                func = safe_ftype((name, dll))
                func.argtypes = safe_args
                func.restype = safe_res
                return func
            except (AttributeError, OSError, TypeError):
                return _get_dummy_cfunc(name)

    _cl.buildFunction = _safe_build_function
except ImportError:
    pass


class SafeMacOSCDLL(_orig_cdll):
    """
    Real ctypes.CDLL subclass that preserves _FuncPtr and _handle for PyOpenGL,
    while mocking any missing Linux/X11/GLX symbols safely.
    """

    def __init__(self, name, *args, **kwargs):
        super().__init__(name, *args, **kwargs)

    def _mock_symbol(self, name: str):
        fn = _get_dummy_cfunc(str(name))
        try:
            super().__setattr__(str(name), fn)
        except Exception:
            pass
        return fn

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(name)

        if name == "glfwInitHint":
            try:
                orig_hint = _orig_cdll.__getitem__(self, name)
                def _safe_init_hint(hint, value):
                    # Ignore GLFW_PLATFORM (0x00050003) X11 hint on macOS
                    if hint == 0x00050003:
                        return 0
                    return orig_hint(hint, value)
                super().__setattr__(name, _safe_init_hint)
                return _safe_init_hint
            except (AttributeError, OSError, KeyError):
                return self._mock_symbol(name)

        if name == "glXGetCurrentContext":
            try:
                cgl_fn = _orig_cdll.__getitem__(_RAW_MACOS_GL, "CGLGetCurrentContext")
                cgl_fn.restype = ctypes.c_void_p
                super().__setattr__(name, cgl_fn)
                return cgl_fn
            except (AttributeError, OSError, KeyError):
                return self._mock_symbol(name)

        try:
            func = _orig_cdll.__getitem__(self, name)
            super().__setattr__(name, func)
            return func
        except (AttributeError, OSError, KeyError):
            if name.startswith("gl") and not name.startswith("glX") and not name.startswith("glfw"):
                try:
                    func = _orig_cdll.__getitem__(_RAW_MACOS_GL, name)
                    super().__setattr__(name, func)
                    return func
                except (AttributeError, OSError, KeyError):
                    pass
            return self._mock_symbol(name)

    def __getitem__(self, name):
        if isinstance(name, str) and name.startswith("_"):
            return _orig_cdll.__getitem__(self, name)
        try:
            return _orig_cdll.__getitem__(self, name)
        except (AttributeError, OSError, KeyError):
            sname = str(name)
            if sname.startswith("gl") and not sname.startswith("glX") and not sname.startswith("glfw"):
                try:
                    return _orig_cdll.__getitem__(_RAW_MACOS_GL, sname)
                except (AttributeError, OSError, KeyError):
                    pass
            return self._mock_symbol(sname)


def _mock_cdll(name, *args, **kwargs):
    if isinstance(name, _orig_cdll):
        return name

    if name is None or str(name) in ("None", "libc.dylib", "libdl.dylib", "libSystem.B.dylib"):
        return SafeMacOSCDLL(_OPENGL_FRAMEWORK if os.path.exists(_OPENGL_FRAMEWORK) else _FALLBACK_DYLIB, *args, **kwargs)

    sname = str(name)
    slower = sname.lower()

    if "glfw" in slower:
        for candidate in (
            ctypes.util.find_library("glfw"),
            "/opt/homebrew/lib/libglfw.3.dylib",
            "/usr/local/lib/libglfw.3.dylib",
        ):
            if candidate and os.path.exists(candidate):
                return SafeMacOSCDLL(candidate, *args, **kwargs)

    if any(k in slower for k in ("libgl", "libopengl", "opengl", "libegl")):
        if os.path.exists(_OPENGL_FRAMEWORK):
            return SafeMacOSCDLL(_OPENGL_FRAMEWORK, *args, **kwargs)
        return SafeMacOSCDLL(_FALLBACK_DYLIB, *args, **kwargs)

    if any(k in slower for k in ("libx11", "libxext", "libxrender", "libxfixes", "libxcb")):
        return SafeMacOSCDLL(_FALLBACK_DYLIB, *args, **kwargs)

    try:
        return SafeMacOSCDLL(sname, *args, **kwargs)
    except OSError:
        return SafeMacOSCDLL(_FALLBACK_DYLIB, *args, **kwargs)


ctypes.CDLL = _mock_cdll
ctypes.cdll = ctypes.LibraryLoader(_mock_cdll)
# --------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from liquid_glass_opengl import (  # noqa: E402
    LiquidGlassRendererOpenGL,
    read_player_theme,
)

os.environ["PYOPENGL_PLATFORM"] = "darwin"

COLS = 120
ROWS = 40


def player_panel_rects(cols=120, rows=40, char_w=9, char_h=18, origin_x=0, origin_y=0, mode="NORMAL"):
    def box(col, row, box_cols, box_rows):
        return (
            origin_x + col * char_w,
            origin_y + row * char_h,
            box_cols * char_w,
            box_rows * char_h,
        )

    m = str(mode).upper()
    if m == "MICRO":
        return box(2, 0, max(20, cols - 4), rows), (0.0, 0.0, 0.0, 0.0)
    elif m == "MINI":
        return box(2, 0, max(20, cols - 4), 3), box(2, 3, max(20, cols - 4), max(1, rows - 3))
    elif m == "TRACKLIST":
        iw = max(20, cols - 4)
        if rows <= 7:
            return box(2, 0, iw, rows), (0.0, 0.0, 0.0, 0.0)
        return box(2, 0, iw, 7), box(2, 7, iw, max(1, rows - 7))
    else:
        iw = max(20, cols - 6)
        viz_rows = 7 if rows >= 34 else (5 if rows >= 28 else 3)
        before = 4 + 1 + 1 + 3 + (viz_rows + 3) + 1
        body_rows = max(1, rows - (before + 1) - 4)
        return box(2, 0, iw + 2, 4), box(2, before, iw + 2, body_rows + 2)


def player_argv(mode="NORMAL", extra_args=None):
    cmd = [sys.executable, str(ROOT / "MP_Audio_Player.py"), "--interactive"]
    m = str(mode).upper()
    if m == "MINI":
        cmd.append("--mini")
    elif m == "MICRO":
        cmd.append("--micro")
    if extra_args:
        cmd.extend(extra_args)
    return cmd


def _child_env():
    env = {key: value for key, value in os.environ.items()}
    env["TERM"] = "xterm-256color"
    env["COLORTERM"] = "truecolor"
    env["MP_LIQUID_GLASS"] = "1"
    env["MP_LIQUID_GLASS_BACKEND"] = "opengl"
    env["MP_LIQUID_GLASS_PLATFORM"] = "macos"
    env["PYTHONUNBUFFERED"] = "1"
    return env


class TerminalOverlay:
    """Core Profile compatible OpenGL terminal text overlay using shaders and VBOs."""

    def __init__(self, cols=120, rows=40, char_w=9, char_h=18):
        self.cols = cols
        self.rows = rows
        self.char_w = char_w
        self.char_h = char_h
        self.lines = [""] * rows
        self.cursor_row = 0
        self.cursor_col = 0
        self._buf = bytearray()
        
        self.shader_program = None
        self.vao = None
        self.vbo = None
        self._initialized_gl = False
        self.feed(b"MP Audio Player Initializing (OpenGL Core Profile macOS)...\r\n")

    def _init_gl_resources(self):
        if self._initialized_gl:
            return
        try:
            from OpenGL.GL import (
                glCreateShader, glShaderSource, glCompileShader,
                glCreateProgram, glAttachShader, glLinkProgram,
                glGetUniformLocation, glGenVertexArrays, glBindVertexArray,
                glGenBuffers, glBindBuffer, glBufferData, glVertexAttribPointer,
                glEnableVertexAttribArray, GL_VERTEX_SHADER, GL_FRAGMENT_SHADER,
                GL_ARRAY_BUFFER, GL_STATIC_DRAW, GL_DYNAMIC_DRAW, GL_FLOAT, GL_FALSE
            )

            vs = glCreateShader(GL_VERTEX_SHADER)
            glShaderSource(vs, b"""
                #version 410 core
                layout(location = 0) in vec2 a_position;
                void main() {
                    gl_Position = vec4(a_position, 0.0, 1.0);
                }
            """)
            glCompileShader(vs)

            fs = glCreateShader(GL_FRAGMENT_SHADER)
            glShaderSource(fs, b"""
                #version 410 core
                out vec4 fragColor;
                uniform vec4 u_color;
                void main() {
                    fragColor = u_color;
                }
            """)
            glCompileShader(fs)

            self.shader_program = glCreateProgram()
            glAttachShader(self.shader_program, vs)
            glAttachShader(self.shader_program, fs)
            glLinkProgram(self.shader_program)

            self.u_color_loc = glGetUniformLocation(self.shader_program, "u_color")

            self.vao = glGenVertexArrays(1)
            self.vbo = glGenBuffers(1)

            glBindVertexArray(self.vao)
            glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
            glBufferData(GL_ARRAY_BUFFER, 1024 * 6 * 2 * 4, None, GL_DYNAMIC_DRAW)

            glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 2 * 4, ctypes.c_void_p(0))
            glEnableVertexAttribArray(0)

            glBindVertexArray(0)
            self._initialized_gl = True
        except Exception as e:
            print(f"DEBUG Overlay GL init error: {e}", flush=True)

    def feed(self, data: bytes):
        if not data:
            return
        self._buf.extend(data)
        try:
            text = self._buf.decode("utf-8", errors="replace")
            self._buf.clear()
        except Exception:
            return

        import re
        text = re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", text)
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        for ch in text:
            if ch == "\n":
                self.cursor_row = min(self.rows - 1, self.cursor_row + 1)
                self.cursor_col = 0
                if self.cursor_row == self.rows - 1:
                    self.lines = self.lines[1:] + [""]
            elif ch == "\b":
                self.cursor_col = max(0, self.cursor_col - 1)
            elif ord(ch) >= 32:
                line = self.lines[self.cursor_row]
                if self.cursor_col >= len(line):
                    line += " " * (self.cursor_col - len(line) + 1)
                line = line[:self.cursor_col] + ch + line[self.cursor_col + 1:]
                self.lines[self.cursor_row] = line[:self.cols]
                self.cursor_col = min(self.cols - 1, self.cursor_col + 1)

    def draw(self, margin_x=0, margin_y=0):
        if not self._initialized_gl:
            self._init_gl_resources()
        if not self._initialized_gl or not self.shader_program:
            return

        try:
            from OpenGL.GL import (
                glUseProgram, glBindVertexArray, glUniform4f,
                glDrawArrays, glBindBuffer, glBufferData,
                glDisable, GL_DEPTH_TEST, GL_TRIANGLES,
                GL_ARRAY_BUFFER, GL_DYNAMIC_DRAW, glGetIntegerv, GL_VIEWPORT
            )
            import numpy as np

            viewport = glGetIntegerv(GL_VIEWPORT)
            vw = viewport[2] if len(viewport) >= 4 else 1200
            vh = viewport[3] if len(viewport) >= 3 else 800

            glDisable(GL_DEPTH_TEST)
            glUseProgram(self.shader_program)
            glUniform4f(self.u_color_loc, 0.90, 0.94, 1.0, 0.95)

            vertices = []
            for r, line in enumerate(self.lines):
                y = margin_y + r * self.char_h
                for c, ch in enumerate(line[:self.cols]):
                    if ch == " " or ch == "":
                        continue
                    x = margin_x + c * self.char_w
                    
                    x1 = (x / vw) * 2.0 - 1.0
                    y1 = 1.0 - ((y + 2) / vh) * 2.0
                    x2 = ((x + self.char_w - 1) / vw) * 2.0 - 1.0
                    y2 = 1.0 - ((y + self.char_h - 2) / vh) * 2.0

                    vertices.extend([
                        x1, y1,  x2, y1,  x1, y2,
                        x2, y1,  x2, y2,  x1, y2
                    ])

            if vertices:
                verts_arr = np.array(vertices, dtype=np.float32)
                glBindVertexArray(self.vao)
                glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
                glBufferData(GL_ARRAY_BUFFER, verts_arr.nbytes, verts_arr, GL_DYNAMIC_DRAW)
                glDrawArrays(GL_TRIANGLES, 0, len(vertices) // 2)
                glBindVertexArray(0)

            glUseProgram(0)
        except Exception as e:
            print(f"DEBUG Overlay draw error: {e}", flush=True)


class OpenGLGlassHost:
    """macOS OpenGL liquid-glass host for MP Audio Player."""

    def __init__(self, argv, mode="NORMAL", cli_theme=None):
        self.argv = list(argv)
        self.mode = mode.upper()
        self.cli_theme = cli_theme
        self.renderer = None
        self.child_pid = 0
        self._target_cols = COLS
        self._target_rows = ROWS
        self.overlay = TerminalOverlay(COLS, ROWS)

    def _sync_panels(self):
        if self.renderer is None:
            return
        char_w, char_h = 9, 18
        margin = self.renderer.bezel_px
        self.renderer.set_panels(
            player_panel_rects(self._target_cols, self._target_rows, char_w, char_h, margin, margin, mode=self.mode)
        )

    def run(self):
        char_w, char_h = 9, 18
        margin = LiquidGlassRendererOpenGL.bezel_px
        init_w = self._target_cols * char_w + 2 * margin
        init_h = self._target_rows * char_h + 2 * margin

        title = "MP Audio Player (Liquid Glass - OpenGL / macOS)"
        self.renderer = LiquidGlassRendererOpenGL(width=init_w, height=init_h, title=title)
        self.renderer.open()
        self._sync_panels()

        master_fd, slave_fd = pty.openpty()
        pid = os.fork()
        if pid == 0:
            os.close(master_fd)
            os.setsid()
            os.dup2(slave_fd, 0)
            os.dup2(slave_fd, 1)
            os.dup2(slave_fd, 2)
            if slave_fd > 2:
                os.close(slave_fd)
            env = _child_env()
            os.execvpe(self.argv[0], self.argv, env)
            sys.exit(1)

        os.close(slave_fd)
        self.child_pid = pid

        theme = read_player_theme()
        theme_at = 0.0

        print("DEBUG: Entering OpenGL event loop...", flush=True)

        try:
            while not self.renderer.should_close:
                now = time.monotonic()
                if now - theme_at > 0.4:
                    theme = read_player_theme()
                    theme_at = now

                self.renderer.poll()
                self._sync_panels()
                self.renderer.draw(theme)

                # Draw terminal content on top of the glass panels
                self.overlay.draw(margin, margin)

                pid_res, _ = os.waitpid(self.child_pid, os.WNOHANG)
                if pid_res == self.child_pid:
                    break

                r, _, _ = select.select([master_fd], [], [], 0.016)
                if master_fd in r:
                    try:
                        data = os.read(master_fd, 4096)
                        if not data:
                            break
                        self.overlay.feed(data)
                    except OSError:
                        break

                time.sleep(0.015)
        finally:
            self.close(master_fd)

        return True

    def close(self, master_fd=None):
        if master_fd is not None:
            try:
                os.close(master_fd)
            except OSError:
                pass
        pid = self.child_pid
        self.child_pid = 0
        if pid:
            try:
                os.kill(pid, signal.SIGTERM)
                time.sleep(0.05)
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
        if self.renderer:
            self.renderer.close()
            self.renderer = None


def main():
    theme_arg = None
    cleaned_argv = []
    i = 1
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg in ("--theme", "-t") and i + 1 < len(sys.argv):
            theme_arg = sys.argv[i + 1]
            i += 2
            continue
        cleaned_argv.append(arg)
        i += 1

    extra = []
    if theme_arg:
        extra.extend(["--theme", theme_arg])

    command = player_argv(mode="NORMAL", extra_args=extra)
    host = OpenGLGlassHost(command, mode="NORMAL", cli_theme=theme_arg)
    host.run()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as exc:
        import traceback
        traceback.print_exc()
        print(f"OpenGL Glass Error: {exc}", file=sys.stderr)
        sys.exit(1)
