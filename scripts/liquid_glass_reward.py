#!/usr/bin/env python3
"""
Special First-Run Reward & Welcome System for MP Liquid Transparent Glass Audio Player.

When a user runs MP Mix Manager or MP Audio Player for the very first time:
1. Installs the high-resolution MP Liquid Transparent Glass desktop icon and shortcut
   on the user's Desktop (~/Desktop/MP_Liquid_Glass_Audio_Player.desktop).
2. Sets the Liquid Glass Audio Player as the Default Audio Player in config.
3. Displays a heartfelt welcome message from MPlanetarian thanking them and wishing
   them a great journey.
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

    # 4. Create Desktop shortcut content
    content = f"""[Desktop Entry]
Type=Application
Name=MP Liquid
GenericName=Liquid Transparent Audio Player
Comment=Launch MP Audio Player in Liquid Transparent Glass Mode
Path={ROOT}
Exec={target_launcher}
Icon={ICON_PNG}
Terminal=false
Categories=AudioVideo;Audio;Player;
StartupNotify=true
StartupWMClass=MP_Liquid
X-KDE-GlobalAccel-CommandShortcut=true
"""
    DESKTOP_SHORTCUT.write_text(content, encoding="utf-8")
    DESKTOP_SHORTCUT.chmod(0o755)

    APPS_SHORTCUT.write_text(content, encoding="utf-8")
    APPS_SHORTCUT.chmod(0o755)

    # 5. Mark as trusted in KDE/GNOME if gio is available
    if shutil.which("gio"):
        try:
            subprocess.run(
                ["gio", "set", str(DESKTOP_SHORTCUT), "metadata::trusted", "true"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=2,
            )
        except Exception:
            pass

    # 6. Set Default Player to mp_liquid_glass in config
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


def setup_first_run_sample_track(force: bool = False) -> bool:
    """
    Celebrate the v0.4 release by pre-loading the free exclusive sample track
    into MP Audio Player ready for the user to press play when they are ready.
    This only happens the very first time the program is run and never again.
    """
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
    title = "✦ WELCOME TO MP MIX ARCHIVE MANAGER & LIQUID GLASS ✦"
    sub = "Special v0.4 Release Celebration & Gift from MPlanetarian"

    banner = [
        "",
        f"  {BOLD}{CYAN}╭{'─' * w}╮{NC}",
        f"  {BOLD}{CYAN}│{BOLD}{WHITE}{title.center(w)}{BOLD}{CYAN}│{NC}",
        f"  {BOLD}{CYAN}│{BOLD}{PURPLE}{sub.center(w)}{BOLD}{CYAN}│{NC}",
        f"  {BOLD}{CYAN}╰{'─' * w}╯{NC}",
        "",
        f"  {WHITE}\"Thank you for downloading and running the MP Mix Archive Manager & MP Audio Player!{NC}",
        f"  {WHITE} As a special welcome reward, I have designed and installed the new{NC}",
        f"  {BOLD}{CYAN} MP Liquid Transparent Glass Icon{NC}{WHITE} right onto your Desktop.{NC}",
        "",
        f"  {WHITE} To celebrate the release of v0.4, I have also included a free exclusive track{NC}",
        f"  {WHITE} and original art piece in the MP_SAMPLES folder:{NC}",
        f"  {BOLD}{GOLD} MPlanetarian - Ecology of the Earth (Cosmic Dreamworlds Remake){NC}",
        f"  {WHITE} It is ready loaded in the Liquid Transparent Audio Player for you to enjoy!\"{NC}",
        f"                                                       {BOLD}{PURPLE}— MPlanetarian ♫{NC}",
        "",
        f"  {BOLD}{MINT}✓ Special Desktop Reward Unlocked:{NC} {WHITE}~/Desktop/MP_Liquid.desktop{NC}",
        f"  {BOLD}{MINT}✓ High-Resolution Glass Icon:{NC}      {WHITE}{ICON_PNG}{NC}",
        f"  {BOLD}{MINT}✓ Default Audio Player Configured:{NC}  {BOLD}{CYAN}MP Liquid Glass Audio Player{NC}",
        f"  {BOLD}{MINT}✓ Free v0.4 Release Track Preloaded:{NC}{WHITE} MP_SAMPLES/MPlanetarian - Ecology of the Earth.flac{NC}",
        f"  {BOLD}{MINT}✓ Free Art Piece Included:{NC}          {WHITE} MP_SAMPLES/Cosmic_Dreamworlds_Cover.png{NC}",
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


def ensure_first_run_reward(interactive=True):
    setup_first_run_sample_track()
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
