#!/usr/bin/env python3
"""
Special First-Run Reward & Welcome System for MP Liquid Transparent Glass Audio Player.

When a user runs MP Mix Manager or MP Audio Player for the very first time:
1. Installs four desktop shortcuts: MP Liquid Player, MP Mix Manager, MP Gui,
   and MP Liquid Visualizer.
2. Sets the Liquid Glass Audio Player as the Default Audio Player in config.
3. Displays the welcome installer message for 0.4.3 (Liquid) - [Stable Release]
   from MPlanetarian: features added since 0.4.1, five tips, a Mix Archive and
   Music Folder quick start, and a thank-you.
4. Marks the first-run reward as completed in ~/.config/mix-manager/.liquid_glass_welcomed.
"""

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = Path.home() / ".config" / "mix-manager"
FLAG_FILE = CONFIG_DIR / ".liquid_glass_welcomed"

SAMPLE_DIR = ROOT / "MP_SAMPLES"
SAMPLE_TRACK_NAME = "MPlanetarian - Ecology of the Earth (Cosmic Dreamworlds Remake)"
SAMPLE_TRACK_FILE = SAMPLE_DIR / f"{SAMPLE_TRACK_NAME}.flac"
SAMPLE_COVER_FILE = SAMPLE_DIR / "Cosmic_Dreamworlds_Cover.png"
SAMPLE_FLAG_FILE = CONFIG_DIR / ".first_run_sample_loaded"
PREVENT_AUTOPLAY_FILE = CONFIG_DIR / ".first_run_sample_prevent_autoplay"
EQ_FLAG_FILE = CONFIG_DIR / ".first_run_eq_initialized"

ASSETS_DIR = ROOT / "assets"
ICON_PNG = ASSETS_DIR / "mp_liquid_glass_icon.png"
ICON_SVG = ASSETS_DIR / "mp_liquid_glass_icon.svg"
LAUNCHER_SCRIPT = ROOT / "scripts" / "launch_liquid_glass.sh"

USER_DESKTOP = Path.home() / "Desktop"
DESKTOP_SHORTCUT = USER_DESKTOP / "MP_Liquid.desktop"
APPS_SHORTCUT = Path.home() / ".local" / "share" / "applications" / "MP_Liquid.desktop"


def is_welcomed() -> bool:
    return FLAG_FILE.exists()


def install_reward_desktop_shortcut():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    USER_DESKTOP.mkdir(parents=True, exist_ok=True)
    APPS_SHORTCUT.parent.mkdir(parents=True, exist_ok=True)

    # 1. Ensure icons exist
    if not ICON_PNG.exists() or not ICON_SVG.exists():
        try:
            from scripts.generate_liquid_glass_icon import generate_png_icon, generate_svg_icon
            if not ICON_PNG.exists():
                png_img = generate_png_icon(512)
                png_img.save(ICON_PNG, format="PNG")
            if not ICON_SVG.exists():
                generate_svg_icon()
        except Exception:
            pass

    # 2. Install icons to user system directories
    user_icons = Path.home() / ".local" / "share" / "icons"
    user_icons.mkdir(parents=True, exist_ok=True)
    hicolor_512 = user_icons / "hicolor" / "512x512" / "apps"
    hicolor_512.mkdir(parents=True, exist_ok=True)

    if ICON_PNG.exists():
        shutil.copy2(ICON_PNG, user_icons / "mp_liquid_glass_icon.png")
        shutil.copy2(ICON_PNG, hicolor_512 / "mp_liquid_glass_icon.png")
    if ICON_SVG.exists():
        shutil.copy2(ICON_SVG, user_icons / "mp_liquid_glass_icon.svg")

    # 3. Ensure ~/.local/bin/launch-liquid-glass launcher exists
    local_bin = Path.home() / ".local" / "bin"
    local_bin.mkdir(parents=True, exist_ok=True)
    target_launcher = local_bin / "launch-liquid-glass"

    if LAUNCHER_SCRIPT.exists():
        shutil.copy2(LAUNCHER_SCRIPT, target_launcher)
        target_launcher.chmod(0o755)

    # 4. Desktop and application-menu shortcuts for this install.
    ensure_desktop_shortcuts(ROOT)

    # 5. Set Default Player to mp_liquid_glass in config
    set_default_player_in_config("mp_liquid_glass")


def set_default_player_in_config(player_name="mp_liquid_glass"):
    for cfg in (CONFIG_DIR / "config.env", ROOT / "config.env"):
        if cfg.exists():
            try:
                lines = cfg.read_text(encoding="utf-8", errors="ignore").splitlines()
                found = False
                new_lines = []
                for line in lines:
                    if line.startswith("DEFAULT_AUDIO_PLAYER="):
                        new_lines.append(f'DEFAULT_AUDIO_PLAYER="{player_name}"')
                        found = True
                    else:
                        new_lines.append(line)
                if not found:
                    new_lines.append(f'DEFAULT_AUDIO_PLAYER="{player_name}"')
                cfg.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
            except Exception:
                pass


def setup_first_run_equalizer(force: bool = False) -> bool:
    """
    Ensure MP Audio Player's equaliser is set to Flat (0 dB across all bands)
    when MP Mix Manager loads for the first time.
    Executes: python MP_Audio_Player.py --reset-eq
    """
    flag = CONFIG_DIR / ".first_run_eq_initialized"
    if not force and flag.exists():
        return False
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    mp_py = ROOT / "MP_Audio_Player.py"
    if not mp_py.is_file():
        mp_py = ROOT / "scripts" / "MP_Audio_Player.py"
    if mp_py.is_file():
        try:
            subprocess.run(
                [sys.executable, str(mp_py), "--reset-eq"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
            )
        except Exception:
            try:
                import json
                (CONFIG_DIR / "eq_preset").write_text("Flat", encoding="utf-8")
                (CONFIG_DIR / "eq_active_bands.json").write_text(json.dumps([0.0] * 10), encoding="utf-8")
            except Exception:
                pass
    try:
        flag.touch(exist_ok=True)
    except Exception:
        pass
    return True


def setup_first_run_sample_track(force: bool = False) -> bool:
    """
    Celebrate the v0.4 release by pre-loading the free exclusive sample track
    into MP Audio Player ready for the user to press play when they are ready.
    This only happens the very first time the program is run and never again.
    """
    setup_first_run_equalizer(force=force)
    if not force and SAMPLE_FLAG_FILE.exists():
        return False
    if not SAMPLE_TRACK_FILE.exists():
        return False

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    res_path = str(SAMPLE_TRACK_FILE.resolve())
    resume_file = CONFIG_DIR / "playback_resume.json"
    state_file = CONFIG_DIR / "mp_player_state.json"

    # Only set up initial playback resume if user doesn't already have one, or if forcing
    if force or not resume_file.exists():
        resume_data = {
            "path": res_path,
            "position_sec": 0.0,
            "duration_sec": 1014.42,
            "title": SAMPLE_TRACK_NAME,
            "mode": "MIX_ARCHIVE",
            "player": "mp_audio_player",
            "timestamp": time.time(),
        }
        try:
            import json
            tmp_res = resume_file.with_suffix(".tmp")
            tmp_res.write_text(json.dumps(resume_data, indent=2), encoding="utf-8")
            tmp_res.replace(resume_file)
        except Exception:
            pass

    # Ensure mp_player_state is in ready/stopped state
    if force or not state_file.exists():
        state_data = {
            "running": False,
            "state": "stopped",
            "path": res_path,
            "title": SAMPLE_TRACK_NAME,
            "position_sec": 0.0,
            "position_fmt": "00:00",
            "duration_sec": 1014.42,
            "duration_fmt": "16:54",
            "progress_pct": 0.0,
            "mode": "MIX_ARCHIVE",
            "volume": 85,
        }
        try:
            import json
            tmp_state = state_file.with_suffix(".tmp")
            tmp_state.write_text(json.dumps(state_data, indent=2), encoding="utf-8")
            tmp_state.replace(state_file)
        except Exception:
            pass

    # Marker to prevent autoplay on the very first startup so it remains ready for user to press play
    try:
        PREVENT_AUTOPLAY_FILE.touch(exist_ok=True)
    except Exception:
        pass

    try:
        SAMPLE_FLAG_FILE.touch(exist_ok=True)
    except Exception:
        pass
    return True


def _wrap_welcome(text, width):
    words = text.split()
    lines, cur = [], ""
    for word in words:
        trial = word if not cur else f"{cur} {word}"
        if len(trial) <= width:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines or [""]


def _welcome_items(items, color, nc, label_for, width=72):
    """Paint a readable list. label_for(index, item) supplies the item prefix."""
    lines = []
    for index, item in enumerate(items, 1):
        label = label_for(index, item)
        wrapped = _wrap_welcome(item, width - len(label))
        lines.append(f"  {color}{label}{wrapped[0]}{nc}")
        pad = " " * len(label)
        for extra in wrapped[1:]:
            lines.append(f"  {color}{pad}{extra}{nc}")
    return lines


def show_welcome_message(wait_for_input=True):
    NC = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    CYAN = "\033[38;2;0;245;255m"
    MINT = "\033[38;2;0;245;212m"
    PURPLE = "\033[38;2;199;125;255m"
    BLUE = "\033[38;2;72;149;239m"
    WHITE = "\033[38;2;255;255;255m"
    GOLD = "\033[38;2;255;215;0m"

    w = 78
    title = "✦ WELCOME TO MP MIX MANAGER ✦"
    version = "0.4.3 (Liquid) - [Stable Release]"
    sub = "Welcome Installer Message from MPlanetarian"

    features_since_041 = [
        "Shared system tray. One icon for MP Mix Manager, MP Gui, and MP Liquid Player. Right-click it to launch any of them, or choose Close MP Mix Manager to close all of them.",
        "Favorites. Press H to mark or unmark the selected mix or track. Press 3, or the Favorites button, to open the Favorites playlist. The audio files are not rewritten.",
        "Drag and drop. Drop audio files, or an M3U playlist, onto the Liquid Player and they join the list that is open.",
        "In-window visualizer. The MP Visualizer can draw behind the player text. The separate visualizer window uses the Liquid Player size. When MP Gui starts it, that window uses MP Gui's fitted size.",
        "Visualizer close. Leaving the Liquid Player closes the companion visualizer. Closing MP Gui stops playback and closes it too.",
        "Pointer follow. When MP Gui opens the Liquid Player, the pointer moves into that player window. G brings MP Gui in front of a fullscreen terminal, and the player opened from MP Gui is raised the same way.",
        "Bash on B. Press B on a manager menu for a Bash prompt in the same window. Press B again on an empty line to return.",
        "Theme menu numbers. Each theme paints its menu numbers in its own colour, including the selection bar.",
        "Status line. Latency and the audio engine move onto the next line so they stay inside the window.",
        "Black startup loader. The console behind the loader video stays black. Esc, Space, Enter, and q still skip the intro.",
        "Escape closes MP Gui. On the MP Gui main menu, Escape closes the window. In a submenu, Escape still goes back one menu.",
        "Linux TTY Desktop Switcher. On Linux, main menu option 37 turns on MP Mix Manager TTY Audio Mode and uses tty1. A console service restarts the manager if it exits. The terminal is restored on the way out. Playback stays in the terminal player. Desktop windows stay closed. Exit is option 38.",
        "Primary display. MP Mix Manager and the MP Liquid shortcut open on the main desktop.",
        "Windows player. After the Liquid Player loads you can drag it. The tray icon sits on the taskbar, the shortcuts use the Liquid Glass icon, and the console scrollbar stays hidden.",
        "macOS player. MP Gui and the Liquid Player open the OpenGL host. Press G in that player to open MP Gui. The visualizer shader stays compiled. The player, MP Gui, and visualizer shortcuts open as apps.",
        "Your volume stays put. Opening MP Gui or the Liquid Player keeps the volume you already set.",
        "Music Folders skip a Logic Pro Library bundle, so those WAV files are not added as tracks.",
        "Mix conversion. A zero-byte WAV no longer stops the rest of the batch.",
        "Startup. The manager no longer opens the Liquid Player by itself. Main menu option 3 and the L key still open it.",
        "Console colour. Each theme paints its own dark console background. The Dreamworlds console background is black.",
    ]
    tips = [
        "In the player, press 1 for the Mix Archive playlist, 2 for Music Folders, and 3 for Favorites. Press H to mark the row you are on.",
        "Press L for MP Liquid Player, G for MP Gui, and Z for the MP Liquid Visualizer. Press C to cycle themes. The choice is saved.",
        "Press B on a menu for Bash in that same window, then B on an empty line to come back. Press D twice to clear the open playlist. Esc cancels, and the files stay on disk.",
        "For music on an SMB share, open main menu 2, then option 8, and save the login before option 3 builds the playlists. Enter keeps the login you already saved.",
        "Add the four MP desktop shortcuts yourself, then run them. Their names are MP Liquid Player, MP Mix Manager, MP Gui, and MP Liquid Visualizer.",
    ]
    steps = [
        "Start MP Mix Manager. In a terminal run manager or ./manager.sh. On macOS, open manager_macos.command. On Windows, open MP Mix Manager.exe or manager.bat.",
        "Set up your Mix Archive Folders. On the main menu choose 16, Configure Mix Archive Storage Locations. Choice 1 sets the primary folder, the one that holds your FLAC mixes. Choice 4 adds another Mix Archive folder. Choice 2 picks a folder found on a connected drive. Main menu option 13 shows the space those folders use. Then choose main menu 1, Play DJ Mixes. In the player, press 1 any time to reload the Mix Archive playlist.",
        "Set up your Music Folders. On the main menu choose 2, Play Tracks from MUSIC Folders. Choice 4 adds a local folder or an SMB share. Choice 8 saves the SMB username and password. Choice 3 generates the playlists. Choice 1 plays every Music Folder. In the player, press 2 any time to reload the Music playlist.",
        "Add the MP desktop shortcuts yourself, then run them to play what you just set up. Put these four on your Desktop: MP Liquid Player, MP Mix Manager, MP Gui, and MP Liquid Visualizer. MP Liquid Player plays the Mix Archive and Music playlists. MP Mix Manager opens this manager. MP Gui opens the manager in the Liquid Glass window. MP Liquid Visualizer draws the picture that follows the audio.",
    ]

    banner = [
        "",
        f"  {BOLD}{CYAN}╭{'─' * w}╮{NC}",
        f"  {BOLD}{CYAN}│{BOLD}{WHITE}{title.center(w)}{BOLD}{CYAN}│{NC}",
        f"  {BOLD}{CYAN}│{BOLD}{GOLD}{version.center(w)}{BOLD}{CYAN}│{NC}",
        f"  {BOLD}{CYAN}│{BOLD}{PURPLE}{sub.center(w)}{BOLD}{CYAN}│{NC}",
        f"  {BOLD}{CYAN}╰{'─' * w}╯{NC}",
        "",
        f"  {WHITE}Thank you for supporting MP Mix Manager.{NC}",
        f"  {WHITE}Version {BOLD}{GOLD}{version}{NC}",
        "",
        f"  {WHITE}A gift is ready in the Liquid Transparent Audio Player:{NC}",
        f"  {BOLD}{GOLD}MPlanetarian - Ecology of the Earth (Cosmic Dreamworlds Remake){NC}",
        f"  {WHITE}The track and its art are in MP_SAMPLES. Press play when you are ready.{NC}",
        "",
        f"  {BOLD}{MINT}What's new since 0.4.1{NC}",
        f"  {DIM}{WHITE}Read each item below. These are the features added after 0.4.1.{NC}",
        *_welcome_items(features_since_041, WHITE, NC, lambda _i, _item: "• "),
        "",
        f"  {BOLD}{MINT}Five tips{NC}",
        *_welcome_items(tips, WHITE, NC, lambda i, _item: f"Tip {i}. "),
        "",
        f"  {BOLD}{MINT}Quick start{NC}",
        f"  {DIM}{WHITE}Mix Archive Folders, then Music Folders, then the shortcuts you add.{NC}",
        *_welcome_items(steps, WHITE, NC, lambda i, _item: f"Step {i}. "),
        "",
        f"  {BOLD}{PURPLE}Wishing you a Magical Journey with MP Mix Manager.{NC}",
        f"  {WHITE}Thank you again for supporting it.{NC}",
        f"  {BOLD}{PURPLE}— MPlanetarian ♫{NC}",
        "",
        f"  {DIM}{GOLD}Last updated by MPlanetarian on November 10, 2026.{NC}",
        "",
        f"  {BOLD}{BLUE}{'─' * (w + 2)}{NC}",
    ]

    try:
        sys.stdout.write("\n".join(banner) + "\n")
        sys.stdout.flush()
        if wait_for_input and sys.stdin.isatty():
            sys.stdout.write(f"  {DIM}{GOLD}Press [Enter] to continue to the Manager...{NC} ")
            sys.stdout.flush()
            sys.stdin.readline()
        else:
            time.sleep(2.0)
    except Exception:
        pass


def ensure_desktop_shortcuts(root=None) -> bool:
    """Put the four shortcuts on the Desktop when any of them is missing."""
    scripts_dir = Path(__file__).resolve().parent
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    from install_desktop_shortcuts import ensure_installed

    return ensure_installed(Path(root) if root else ROOT)


def ensure_first_run_reward(interactive=True):
    setup_first_run_equalizer()
    setup_first_run_sample_track()
    try:
        ensure_desktop_shortcuts(ROOT)
    except Exception:
        pass
    if is_welcomed():
        return False

    install_reward_desktop_shortcut()
    show_welcome_message(wait_for_input=interactive)

    try:
        FLAG_FILE.touch(exist_ok=True)
    except Exception:
        pass
    return True


if __name__ == "__main__":
    force = "--force" in sys.argv
    if force and FLAG_FILE.exists():
        FLAG_FILE.unlink()
    ensure_first_run_reward(interactive=True)
