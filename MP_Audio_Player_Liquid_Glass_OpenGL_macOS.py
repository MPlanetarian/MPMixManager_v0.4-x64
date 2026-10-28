#!/usr/bin/env python3
"""
MP Audio Player - Liquid Glass OpenGL Host (macOS Unified Window Edition)
Renders a fluid glass UI and embeds the audio player's PTY text stream 
directly into a single OpenGL window.
"""

import os
import sys
import pty
import select
import struct
import fcntl
import termios
import OpenGL
# Prevent automatic error-checking overhead on macOS OpenGL calls
OpenGL.ERROR_CHECKING = False

from OpenGL.GL import *
import glfw
import numpy as np

# --- macOS Compatibility Patch for Missing Linux GLX Symbols ---
import ctypes
import ctypes.util
try:
    _opengl_lib = ctypes.CDLL(ctypes.util.find_library("OpenGL"))
    if not hasattr(_opengl_lib, "glXGetCurrentContext"):
        # Mock missing Linux GLX symbols to prevent AttributeError on cross-platform wrappers
        _opengl_lib.glXGetCurrentContext = lambda: None
        _opengl_lib.glXGetCurrentDisplay = lambda: None
except Exception:
    pass

# --- Configuration & Layout ---
WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 720
FONT_SCALE = 1.0

class ANSIParser:
    """Parses standard and truecolor ANSI escape sequences from the audio player PTY stream."""
    def __init__(self, cols=120, rows=35):
        self.cols = cols
        self.rows = rows
        self.buffer = [[" " for _ in range(cols)] for _ in range(rows)]
        self.fg_color = (200, 200, 200, 255)
        self.bg_color = (20, 20, 30, 200)
        self.cursor_x = 0
        self.cursor_y = 0

    def write(self, data):
        i = 0
        n = len(data)
        while i < n:
            char = data[i]
            if char == '\033' and i + 1 < n and data[i+1] == '[':
                # Parse CSI escape sequence
                i += 2
                param_str = ""
                while i < n and (data[i].isdigit() or data[i] == ';'):
                    param_str += data[i]
                    i += 1
                if i < n:
                    cmd = data[i]
                    self._handle_csi(param_str, cmd)
                    i += 1
            elif char == '\n':
                self.cursor_x = 0
                self.cursor_y = min(self.rows - 1, self.cursor_y + 1)
                i += 1
            elif char == '\r':
                self.cursor_x = 0
                i += 1
            elif ord(char) >= 32:
                if self.cursor_y < self.rows and self.cursor_x < self.cols:
                    self.buffer[self.cursor_y][self.cursor_x] = char
                    self.cursor_x += 1
                    if self.cursor_x >= self.cols:
                        self.cursor_x = 0
                        self.cursor_y = min(self.rows - 1, self.cursor_y + 1)
                i += 1
            else:
                i += 1

    def _handle_csi(self, param_str, cmd):
        params = [int(p) for p in param_str.split(';')] if param_str else [0]
        if cmd == 'H' or cmd == 'f':
            self.cursor_y = max(0, min(self.rows - 1, (params[0] - 1 if len(params) > 0 and params[0] > 0 else 0)))
            self.cursor_x = max(0, min(self.cols - 1, (params[1] - 1 if len(params) > 1 and params[1] > 0 else 0)))
        elif cmd == 'J':
            if params[0] == 2:
                self.buffer = [[" " for _ in range(self.cols)] for _ in range(self.rows)]
                self.cursor_x = 0
                self.cursor_y = 0
        elif cmd == 'm':
            # Basic SGR color parsing fallback
            if 30 <= params[0] <= 37:
                self.fg_color = (150, 220, 255, 255)
            elif params[0] == 0:
                self.fg_color = (200, 200, 200, 255)


class TerminalOverlay:
    """Renders the parsed ANSI buffer inside the OpenGL glass window."""
    def __init__(self, cols=120, rows=35):
        self.parser = ANSIParser(cols, rows)
        self.master_fd, self.slave_fd = pty.openpty()
        
        # Set window size for the pseudo-terminal
        s = struct.pack('HHHH', rows, cols, 0, 0)
        fcntl.ioctl(self.master_fd, termios.TIOCSWINSZ, s)

        # Spawn audio player headless backend process via PTY
        self.pid = os.fork()
        if self.pid == 0:
            # Child process: redirect I/O to slave PTY and execute audio engine
            os.setsid()
            os.dup2(self.slave_fd, 0)
            os.dup2(self.slave_fd, 1)
            os.dup2(self.slave_fd, 2)
            os.close(self.master_fd)
            
            env = os.environ.copy()
            env["TERM"] = "xterm-256color"
            env["PYTHONUNBUFFERED"] = "1"
            
            # Replace with your actual player backend script or command
            os.execve("/usr/bin/env", ["python3", "player_backend.py"], env)
            os._exit(1)
        else:
            os.close(self.slave_fd)
            # Set master PTY to non-blocking
            fl = fcntl.fcntl(self.master_fd, fcntl.F_GETFL)
            fcntl.fcntl(self.master_fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)

    def update(self):
        r, _, _ = select.select([self.master_fd], [], [], 0.0)
        if r:
            try:
                data = os.read(self.master_fd, 1024).decode('utf-8', errors='ignore')
                if data:
                    self.parser.write(data)
            except OSError:
                pass

    def render_glass_ui(self):
        """Draws the unified liquid glass UI layout and text buffer."""
        self.update()
        
        # Setup orthographic projection for UI overlay
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        glOrtho(0, WINDOW_WIDTH, WINDOW_HEIGHT, 0, -1, 1)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()

        # Draw Glass Panel Background
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        
        glColor4f(0.08, 0.09, 0.12, 0.85) # Dark translucent glass tint
        glBegin(GL_QUADS)
        glVertex2f(40, 40)
        glVertex2f(WINDOW_WIDTH - 40, 40)
        glVertex2f(WINDOW_WIDTH - 40, WINDOW_HEIGHT - 40)
        glVertex2f(40, WINDOW_HEIGHT - 40)
        glEnd()

        # Draw subtle glass border frame
        glColor4f(0.3, 0.4, 0.6, 0.4)
        glLineWidth(1.5)
        glBegin(GL_LINE_LOOP)
        glVertex2f(40, 40)
        glVertex2f(WINDOW_WIDTH - 40, 40)
        glVertex2f(WINDOW_WIDTH - 40, WINDOW_HEIGHT - 40)
        glVertex2f(40, WINDOW_HEIGHT - 40)
        glEnd()


def main():
    if not glfw.init():
        sys.exit(1)

    # Configure modern OpenGL context for macOS
    glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
    glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
    glfw.window_hint(glfw.OPENGL_FORWARD_COMPAT, GL_TRUE)
    glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)

    window = glfw.create_window(WINDOW_WIDTH, WINDOW_HEIGHT, "MP Audio Player - Liquid Glass", None, None)
    if not window:
        glfw.terminate()
        sys.exit(1)

    glfw.make_context_current(window)
    glfw.swap_interval(1)

    overlay = TerminalOverlay()

    while not glfw.window_should_close(window):
        glfw.poll_events()

        # Clear viewport frame
        glClearColor(0.03, 0.03, 0.05, 1.0)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        # Render unified glass interface and update background PTY stream
        overlay.render_glass_ui()

        glfw.swap_buffers(window)

    glfw.terminate()

if __name__ == "__main__":
    main()