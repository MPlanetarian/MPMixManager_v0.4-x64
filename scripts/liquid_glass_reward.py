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
    sub = "Special First-Run Reward from MPlanetarian"

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
        f"  {WHITE} I wish you a wonderful and inspiring journey exploring your music archive with{NC}",
        f"  {WHITE} the new Liquid Transparent Audio Player. Enjoy the sound, the visuals, and the vibes!\"{NC}",
        f"                                                       {BOLD}{PURPLE}— MPlanetarian ♫{NC}",
        "",
        f"  {BOLD}{MINT}✓ Special Desktop Reward Unlocked:{NC} {WHITE}~/Desktop/MP_Liquid_Glass_Audio_Player.desktop{NC}",
        f"  {BOLD}{MINT}✓ High-Resolution Glass Icon:{NC}      {WHITE}{ICON_PNG}{NC}",
        f"  {BOLD}{MINT}✓ Default Audio Player Configured:{NC}  {BOLD}{CYAN}MP Liquid Glass Audio Player{NC}",
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
