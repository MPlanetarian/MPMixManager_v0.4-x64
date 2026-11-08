"""Pick the desktop monitor for MP Liquid windows.

The Hisense 4K TV is HDMI-A-1. Several saved layouts put that TV at (0, 0).
A fixed window position of (72, 64) then opens on the TV. The main screen is
the highest-priority output that is not the Hisense.
"""

from __future__ import annotations

import re
import subprocess
import time

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
_OUTPUT_RE = re.compile(r"^Output:\s+\d+\s+(\S+)")
_GEOMETRY_RE = re.compile(r"Geometry:\s*(-?\d+),(-?\d+)\s+(\d+)x(\d+)")
_PRIORITY_RE = re.compile(r"^priority\s+(\d+)\s*$")
_XRANDR_RE = re.compile(
    r"^\s*\d+:\s+\+([*]?)(\S+)\s+\d+/\d+x\d+/\d+\+(-?\d+)\+(-?\d+)"
)
_WORKAREA_RE = re.compile(r"=\s*(-?\d+),\s*(-?\d+),\s*(-?\d+),\s*(-?\d+)")


def is_hisense_name(name: str) -> bool:
    label = (name or "").upper()
    return label == "HDMI-A-1" or "HISENSE" in label


def parse_kscreen(text: str) -> list[dict]:
    outputs = []
    current = None
    for raw in _ANSI_RE.sub("", text or "").splitlines():
        header = _OUTPUT_RE.match(raw.strip())
        if header:
            current = {
                "name": header.group(1),
                "enabled": False,
                "connected": False,
                "priority": 0,
                "geo": None,
            }
            outputs.append(current)
            continue
        if current is None:
            continue
        line = raw.strip()
        if line == "enabled":
            current["enabled"] = True
        elif line == "connected":
            current["connected"] = True
        else:
            priority = _PRIORITY_RE.match(line)
            if priority:
                current["priority"] = int(priority.group(1))
                continue
            geometry = _GEOMETRY_RE.search(line)
            if geometry:
                current["geo"] = tuple(int(part) for part in geometry.groups())
    return outputs


def parse_xrandr_monitors(text: str) -> list[dict]:
    monitors = []
    for raw in (text or "").splitlines():
        match = _XRANDR_RE.match(raw)
        if not match:
            continue
        star, name, x, y = match.groups()
        monitors.append({
            "name": name,
            "primary": star == "*",
            "geo": (int(x), int(y), 0, 0),
        })
    return monitors


def select_main(outputs: list[dict]) -> dict | None:
    """Lowest positive KDE priority among connected outputs that are not the TV.

    Priority 1 is the main desktop. Priority 0 is unset and must not win,
    because the Hisense is sometimes stored with priority 0 at the origin.
    """
    candidates = []
    for output in outputs:
        if not output.get("enabled") or not output.get("connected"):
            continue
        if not output.get("geo"):
            continue
        if is_hisense_name(output.get("name", "")):
            continue
        candidates.append(output)
    if not candidates:
        return None
    candidates.sort(key=lambda output: (output["priority"] <= 0, output["priority"], output["geo"][0]))
    return candidates[0]


def _read_command(args: list[str]) -> str:
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=3)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout or ""


def kscreen_outputs(text: str | None = None) -> list[dict]:
    if text is None:
        text = _read_command(["kscreen-doctor", "-o"])
    return parse_kscreen(text or "")


def _xrandr_origin() -> tuple[int, int] | None:
    monitors = parse_xrandr_monitors(_read_command(["xrandr", "--listmonitors"]))
    if not monitors:
        return None
    desktop = [monitor for monitor in monitors if not is_hisense_name(monitor["name"])]
    if not desktop:
        return None
    primary = next((monitor for monitor in desktop if monitor["primary"]), desktop[0])
    return primary["geo"][0], primary["geo"][1]


def main_desktop_origin(offset_x: int = 72, offset_y: int = 64, outputs: list[dict] | None = None) -> tuple[int, int]:
    """Window top-left on the main desktop, offset from that monitor's origin."""
    chosen = select_main(kscreen_outputs() if outputs is None else outputs)
    if chosen is not None:
        origin_x, origin_y = chosen["geo"][0], chosen["geo"][1]
    else:
        fallback = _xrandr_origin()
        origin_x, origin_y = fallback if fallback is not None else (0, 0)
    return origin_x + int(offset_x), origin_y + int(offset_y)


def net_workarea(text: str | None = None) -> tuple[int, int, int, int] | None:
    """First EWMH work area, which already excludes the panel struts."""
    if text is None:
        text = _read_command(["xprop", "-root", "_NET_WORKAREA"])
    match = _WORKAREA_RE.search(text or "")
    if not match:
        return None
    x, y, width, height = (int(part) for part in match.groups())
    if width <= 0 or height <= 0:
        return None
    return x, y, width, height


def _usable_box(geo: tuple[int, int, int, int], workarea: tuple[int, int, int, int] | None) -> tuple[int, int, int, int]:
    """Usable x, y, width, height relative to the monitor origin."""
    origin_x, origin_y, width, height = geo
    if not workarea or width <= 0 or height <= 0:
        return 0, 0, width, height
    work_x, work_y, work_w, work_h = workarea
    left = max(origin_x, work_x)
    top = max(origin_y, work_y)
    right = min(origin_x + width, work_x + work_w)
    bottom = min(origin_y + height, work_y + work_h)
    if right - left < 64 or bottom - top < 64:
        return 0, 0, width, height
    return left - origin_x, top - origin_y, right - left, bottom - top


def fit_square_on_main(
    preferred: int = 1400,
    offset_x: int = 160,
    offset_y: int = 80,
    margin: int = 12,
    outputs: list[dict] | None = None,
    workarea: tuple[int, int, int, int] | None = None,
) -> tuple[int, int, int, int]:
    """Width, height, and offsets from the main monitor origin.

    The preferred square and offset are kept when they sit inside the usable
    area. Otherwise the square shrinks and is centered so the whole window
    stays on that monitor, inside the panel work area.
    """
    preferred = max(1, int(preferred))
    chosen = select_main(kscreen_outputs() if outputs is None else outputs)
    if chosen is None or not chosen.get("geo"):
        return preferred, preferred, int(offset_x), int(offset_y)
    if outputs is None and workarea is None:
        workarea = net_workarea()
    box_x, box_y, box_w, box_h = _usable_box(chosen["geo"], workarea)
    if (
        offset_x >= box_x
        and offset_y >= box_y
        and offset_x + preferred <= box_x + box_w
        and offset_y + preferred <= box_y + box_h
    ):
        return preferred, preferred, int(offset_x), int(offset_y)
    inset = max(0, int(margin))
    if box_w - 2 * inset < 64 or box_h - 2 * inset < 64:
        inset = 0
    side = min(preferred, max(1, box_w - 2 * inset), max(1, box_h - 2 * inset))
    off_x = box_x + max(0, (box_w - side) // 2)
    off_y = box_y + max(0, (box_h - side) // 2)
    return int(side), int(side), int(off_x), int(off_y)


def _contains(output: dict, x: int, y: int) -> bool:
    left, top, width, height = output["geo"]
    return left <= x < left + width and top <= y < top + height


def _wmctrl_windows() -> list[dict]:
    text = _read_command(["wmctrl", "-lG"])
    windows = []
    for line in text.splitlines():
        parts = line.split(None, 7)
        if len(parts) < 8:
            continue
        try:
            windows.append({
                "id": parts[0],
                "x": int(parts[2]),
                "y": int(parts[3]),
                "w": int(parts[4]),
                "h": int(parts[5]),
                "title": parts[7],
            })
        except ValueError:
            continue
    return windows


def visible_origin(x11_window_id: int = 0, title_contains: str = "") -> tuple[int, int] | None:
    """Global top-left reported by the window manager, not the GLFW position."""
    text = _read_command(["wmctrl", "-lG"])
    wanted = int(x11_window_id or 0)
    title_hit = None
    for line in text.splitlines():
        parts = line.split(None, 7)
        if len(parts) < 4:
            continue
        try:
            ident = int(parts[0], 16)
            origin = (int(parts[2]), int(parts[3]))
        except ValueError:
            continue
        if wanted and ident == wanted:
            return origin
        if title_contains and len(parts) >= 8 and title_contains in parts[7]:
            title_hit = origin
    return title_hit


def place_on_main_screen(set_pos, x11_window_id: int, offset_x: int = 72, offset_y: int = 64, flush=None, title_contains: str = "") -> tuple[int, int]:
    """Move a GLFW window onto the main desktop.

    On this KWin session, the position passed to GLFW is applied at twice the
    global layout coordinate. Asking for the main screen at x=1992 therefore
    appears at x=3984, which is a different monitor. Measure the real position
    and correct once.
    """
    global_x, global_y = main_desktop_origin(offset_x, offset_y)
    set_pos(global_x, global_y)
    if flush:
        flush()
    visible = None
    for _ in range(8):
        time.sleep(0.05)
        visible = visible_origin(int(x11_window_id or 0), title_contains)
        if visible:
            break
    if visible and global_x:
        scale = visible[0] / float(global_x)
        if scale >= 1.25:
            set_pos(int(round(global_x / scale)), int(round(global_y / scale)))
            if flush:
                flush()
    return global_x, global_y


def reposition_off_hisense() -> None:
    """Move an existing Liquid window off the Hisense, then focus the player."""
    outputs = kscreen_outputs()
    televisions = [
        output for output in outputs
        if is_hisense_name(output.get("name", "")) and output.get("enabled") and output.get("geo")
    ]
    targets = (
        ("MP Audio Player (Liquid Glass", 72, 64),
        ("MP Liquid Visualizer", 160, 80),
    )
    for title, offset_x, offset_y in targets:
        for window in _wmctrl_windows():
            if title not in window["title"]:
                continue
            center_x = window["x"] + window["w"] // 2
            center_y = window["y"] + window["h"] // 2
            on_tv = any(
                _contains(tv, window["x"], window["y"]) or _contains(tv, center_x, center_y)
                for tv in televisions
            )
            if not on_tv:
                continue
            x, y = main_desktop_origin(offset_x, offset_y, outputs)
            subprocess.run(
                ["wmctrl", "-i", "-r", window["id"], "-e", f"0,{x},{y},-1,-1"],
                capture_output=True,
                timeout=3,
            )
    subprocess.run(
        ["wmctrl", "-a", "MP Audio Player (Liquid Glass"],
        capture_output=True,
        timeout=3,
    )
