#!/usr/bin/env bash
# ==============================================================================
# MP Mix Manager 0.4.3 Stable (Liquid) - Help Usage & Available Options
# Purpose: Display help usage and all available options for mix-archive-manager
# Usage:
#   mix-archive-manager --help
#   mix-archive-manager -h
# ==============================================================================

set -euo pipefail

# Resolve codebase directory
_RESOLVED_SRC="${BASH_SOURCE[0]}"
while [ -h "$_RESOLVED_SRC" ]; do
    _RESOLVED_DIR="$(cd -P "$(dirname "$_RESOLVED_SRC")" >/dev/null 2>&1 && pwd)"
    _RESOLVED_SRC="$(readlink "$_RESOLVED_SRC")"
    [[ $_RESOLVED_SRC != /* ]] && _RESOLVED_SRC="$_RESOLVED_DIR/$_RESOLVED_SRC"
done
_SCRIPT_DIR="$(cd -P "$(dirname "$_RESOLVED_SRC")" >/dev/null 2>&1 && pwd)"
if [ "$(basename "$_SCRIPT_DIR")" = "scripts" ]; then
    CODEBASE_DIR="$(cd -P "$_SCRIPT_DIR/.." >/dev/null 2>&1 && pwd)"
else
    CODEBASE_DIR="$_SCRIPT_DIR"
fi
unset _RESOLVED_SRC _RESOLVED_DIR _SCRIPT_DIR

# Determine version
VERSION="${VERSION:-}"
if [ -z "$VERSION" ]; then
    if [ -f "$CODEBASE_DIR/VERSION" ]; then
        VERSION="$(head -n 1 "$CODEBASE_DIR/VERSION" | tr -d '\r\n')"
    else
        VERSION="0.4.3 Stable (Liquid)"
    fi
fi
export VERSION

# Terminal colors (respect NO_COLOR and non-interactive output)
if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
    BOLD=$'\033[1m'
    DIM=$'\033[2m'
    NC=$'\033[0m'
    CYAN=$'\033[38;5;51m'
    GREEN=$'\033[38;5;48m'
    YELLOW=$'\033[38;5;226m'
    BLUE=$'\033[38;5;45m'
    MAGENTA=$'\033[38;5;198m'
    RED=$'\033[38;5;196m'
else
    BOLD=''
    DIM=''
    NC=''
    CYAN=''
    GREEN=''
    YELLOW=''
    BLUE=''
    MAGENTA=''
    RED=''
fi

cat << EOF
${BOLD}${MAGENTA}===================================================================================${NC}
${BOLD}${MAGENTA}                     MP Mix Archive Manager (MP_Mix_Manager_v${VERSION})                     ${NC}
${BOLD}${MAGENTA}===================================================================================${NC}
${DIM}Comprehensive DJ Mix Ingestion, Transcoding, Playback, Video & Archive Suite${NC}

${BOLD}USAGE:${NC}
  ${CYAN}mix-archive-manager${NC} [${GREEN}OPTIONS${NC}] [${YELLOW}COMMAND${NC} | ${YELLOW}OPTION_NUMBER${NC}]
  ${CYAN}./Mix_Archive_Manager.sh${NC} [${GREEN}OPTIONS${NC}] [${YELLOW}COMMAND${NC} | ${YELLOW}OPTION_NUMBER${NC}]

${BOLD}DESCRIPTION:${NC}
  When executed without arguments, launches the interactive full-screen terminal
  menu. You can also supply launch flags, shortcut commands, or specific menu option
  numbers to execute operations directly.

${BOLD}LAUNCH FLAGS & OPTIONS:${NC}
  ${BOLD}${GREEN}-h, --help, help${NC}
      Display this help usage screen and list all available options.

  ${BOLD}${GREEN}-v, --version, version${NC}
      Display current installed version, Git commit hash, and commit timestamp.

  ${BOLD}${GREEN}update, --update${NC}
      Check for and automatically install the latest updates from remote Git.
      ${DIM}Sub-options:${NC}
        ${GREEN}--check, -c${NC}    Check for updates without installing
        ${GREEN}--force, -f${NC}    Force re-pull and reinstall from remote repository

  ${BOLD}${GREEN}reinstall, --reinstall${NC}
      Reset this user's configuration and reinstall from a first-install state.
      You are asked whether to preserve playlists, music folder config, and mix
      archive folder config. Always keeps converted audio: delete those yourself.
      ${DIM}Sub-options:${NC}
        ${GREEN}--yes, -y${NC}       Preserve all three, no questions
        ${GREEN}--fresh${NC}         Keep nothing at all
        ${GREEN}--dry-run${NC}       Show what would change, then stop

  ${BOLD}${GREEN}-p, --track, --current-track${NC}
      Print the absolute filesystem path of the currently playing mix track.

  ${BOLD}${GREEN}--strawberry-info${NC}
      Display playback state, track metadata, and file path from Strawberry player.

  ${BOLD}${GREEN}--cliamp-info${NC}
      Display playback state, track metadata, and file path from cliamp player.

${BOLD}AVAILABLE MENU OPTIONS (INTERACTIVE & DIRECT SHORTCUTS):${NC}
  Press B on any menu to turn this window into a Bash prompt. Press B again on an empty line to return to the manager.

  Press Shift+A on any menu to open MP Harmony. Press Shift+A again on an empty assistant line to return.

  ${BOLD}${BLUE}─── [ SECTION 1: Listen to Mixes & Tracks / Convert Audio / Import Mixes / Plus More ] ────${NC}
  ${BOLD}${CYAN}AI${NC}  ${BOLD}Load MP Mix Manager AI Assistant (MP Harmony) (New)${NC}
       First row. If Ollama is not running the manager asks before starting it: a container name can be given for distrobox/podman, otherwise it uses the systemd user service or a plain ollama serve. Answering no returns to the menu. Loads gpt-oss-pinned:latest, or asks before installing that model. Shift+A opens it. Shift+A on an empty assistant line returns here.
  ${BOLD}${CYAN}MP${NC}  ${BOLD}MP GUI Mix Manager (New)${NC}
       Open the manager in the Liquid Glass window (MP_Gui.sh). Press G on the main menu. Also: gui, mp-gui, 36.
   ${BOLD}${CYAN}0${NC}   ${BOLD}Run Any Desktop Shortcuts — Linux${NC}
       Launch or bind KDE Plasma desktop applications, games, audio tools, and servers.
   ${BOLD}${CYAN}1${NC}   ${BOLD}Play DJ Mixes (MP Audio Player — Mix Archive Mode)${NC}
       Built-in player. In the player: [1] Mix Archive, [2] Music, [3] Favorites, [H] mark, [D][D] clear playlist.
   ${BOLD}${CYAN}2${NC}   ${BOLD}Play Tracks from MUSIC Folders${NC}
       SMB and local music libraries. Option 3 refreshes playlists. Option 8 sets the SMB login.
   ${BOLD}${CYAN}3${NC}   ${BOLD}MP Audio Player (Liquid Glass Mode)${NC}
       Translucent desktop player (OpenGL, Vulkan, or Apple Silicon Metal). Also: L, --liquid.
   ${BOLD}${CYAN}4${NC}   ${BOLD}Run Mix Conversion${NC}
       Batch convert with Make_SOF_FLAC_CONVERSION.sh. At the split prompt, A / All / 2 skips every remaining mix.
   ${BOLD}${CYAN}5${NC}   ${BOLD}Audio Conversion, EBU R128 Mastering & CUE Sheets${NC}
       Convert formats, master loudness, generate Red Book .cue sheets, or split tracks.
   ${BOLD}${CYAN}6${NC}   ${BOLD}Retrieve Unconverted WAVs from Archive${NC}
       Move pending uncompressed WAV files from archive storage back to the working area.
   ${BOLD}${CYAN}7${NC}   ${BOLD}Search & Import Mixes from Local Drives & SMB${NC}
       Scan local drives and SMB shares and import new mixes.
   ${BOLD}${CYAN}8${NC}   ${BOLD}Rename a Mix and Associated Assets${NC}
       Rename the FLAC, tracklist text, and Spek spectrogram together.
   ${BOLD}${CYAN}9${NC}   ${BOLD}Find & Remove Duplicate Audio Files / Mixes${NC}
       Find duplicate mixes by partial hash and full content.
  ${BOLD}${CYAN}10${NC}   ${BOLD}Export / Copy Mixes to Specified Path${NC}
       Copy mixes with artwork, tracklists, and spectrograms.
  ${BOLD}${CYAN}11${NC}   ${BOLD}Audio Integrity, Bit-Rot Scrub & FLAC Verification${NC}
       SHA-256 manifests, FLAC decode checks, fake-FLAC spectral checks, and background scrub.
  ${BOLD}${CYAN}12${NC}   ${BOLD}Cloud & Remote Backup Suite${NC}
       Back up mixes to Google Drive, iCloud, Dropbox, or another rclone destination.
  ${BOLD}${CYAN}13${NC}   ${BOLD}Storage Management & Multiple Mix Archives Setup${NC}
       Show drive space and configure more than one mix archive.

  ${BOLD}${BLUE}─── [ SECTION 2: STUDIO AUDIO, PLAYBACK, METADATA & VIDEO ] ──────────────────${NC}
  ${BOLD}${CYAN}14${NC}   ${BOLD}Tracklist Management, Scanning & Metadata Suite${NC}
       Browse tracklists, tag with Picard, and generate HTML and PDF indexes.
  ${BOLD}${CYAN}15${NC}   ${BOLD}Audio Players & Retro Playback Suite${NC}
       Launch cliamp, Audacious, Strawberry, VLC, Haruna, Kodi, Audacity, and platform players.
  ${BOLD}${CYAN}16${NC}   ${BOLD}Configure Mix Archive Storage Locations${NC}
       Set the primary mix folder and extra archive drives.
  ${BOLD}${CYAN}17${NC}   ${BOLD}Custom Mix Playlists & Traktor History Suite${NC}
       Build playlists, read Traktor history, export Favorites for a DJ set, and export Rekordbox XML.
  ${BOLD}${CYAN}18${NC}   ${BOLD}Digital Audio Workstations (DAWs) & Mix Dispatch${NC}
       Launch REAPER, Logic, FL Studio, Ardour, and other installed DAWs.
  ${BOLD}${CYAN}19${NC}   ${BOLD}Studio Hardware, Audio Interfaces & Master Volume Control${NC}
       PipeWire, ALSA, MIDI, and the Traktor Kontrol S4 menu (also: s4).
  ${BOLD}${CYAN}20${NC}   ${BOLD}Spectrogram Generation & Audio Frequency Analysis${NC}
       Spek, SoX, and Praat analysis for one file or a folder.
  ${BOLD}${CYAN}21${NC}   ${BOLD}Morning Alarm Clock & DJ Mix Playback Suite${NC}
       Wake-up mixes, the scheduler, and the MPlanetarians alarm clock.
  ${BOLD}${CYAN}22${NC}   ${BOLD}YouTube Video Suite${NC}
       4K, 1080p, and 720p videos, Shorts, and the channel downloader.
  ${BOLD}${CYAN}23${NC}   ${BOLD}Visual Media, Cover Art & MP Liquid Visualizer${NC}
       Vulkan visualizer (also: Z, visualizer), video cut and split, and cover art.
  ${BOLD}${CYAN}24${NC}   ${BOLD}Record Video of DJ Mix using GPU Screen Recorder (Linux)${NC}
       Open GPU Screen Recorder, then return to the menu.
  ${BOLD}${CYAN}25${NC}   ${BOLD}Listen to Your Top 5 Tracks Right Now${NC}
       Open the curated Top 5 listening session.

  ${BOLD}${BLUE}─── [ SECTION 3: SYSTEM, NETWORK, AI & SETTINGS ] ────────────────────────────${NC}
  ${BOLD}${CYAN}26${NC}   ${BOLD}Live Session, Stream & Transfer Monitors Suite${NC}
       Tracklist, Traktor, conversion output, transfers, and upload monitors.
  ${BOLD}${CYAN}27${NC}   ${BOLD}System & Hardware Process Monitors Suite${NC}
       btop, nvtop, and top.
  ${BOLD}${CYAN}28${NC}   ${BOLD}MP Reporter Suite & Automated Reports${NC}
       Daily, weekly, monthly, and yearly reports, plus email delivery.
  ${BOLD}${CYAN}29${NC}   ${BOLD}Promotional Outreach, Syndication & Music Shopping${NC}
       Promo email, the publishing calendar, and music-store tabs.
  ${BOLD}${CYAN}30${NC}   ${BOLD}Network Services, Congen & Internet Control${NC}
       SSH, Samba, FTP, Congen, the web companion, and the internet block.
  ${BOLD}${CYAN}31${NC}   ${BOLD}Desktop Display Settings, Audio Routing & App Control${NC}
       Wayland or X11, window alignment, and closing other desktop apps.
  ${BOLD}${CYAN}32${NC}   ${BOLD}Universal System Maintenance & Cleanup${NC}
       Drive space, package cleanup, and OS updates for the current platform.
  ${BOLD}${CYAN}33${NC}   ${BOLD}Monitor System Processes and Bash Commands${NC}
       MP_Monitor_Bash.sh in a new terminal tab. Also: monitor, mp-monitor.
  ${BOLD}${CYAN}34${NC}   ${BOLD}Dynamic MOTD Banner Manager & Drive Burner${NC}
       Login banner from the latest mixes, and ISO to USB with a safety check.
  ${BOLD}${CYAN}35${NC}   ${BOLD}Manager Settings, Themes, Shell CLI & Reboot${NC}
       Themes (including Retro Linux Memories), config backup, Bash CLI, updater, reboot.
       Press C on the main menu to cycle themes.
  ${BOLD}${CYAN}36${NC}   ${BOLD}MP Mix Manager GUI${NC}
       Same Liquid Glass manager as the MP row. Press G on the main menu. Also: gui, mp-gui, MP_Gui, ./MP_Gui.sh.
  ${BOLD}${CYAN}VR${NC}   ${BOLD}Enter VR Mode with MP Liquid Player (BigScreen)${NC}
       Row directly under MP. Bigscreen starts first, the visualizer becomes the
       centred backdrop, then MP Liquid Player opens centred and paused. Music
       starts only once the player reports it is centred. Also: vr, vr-mode,
       bigscreen, bigscreen-vr. Refused on Linux.
  ${BOLD}${CYAN}37${NC}   ${BOLD}Linux TTY Desktop Switcher (MP Mix Manager TTY Audio Mode)${NC}
       Linux only. This row is hidden on macOS, Windows, and FreeBSD.
       Runs scripts/MP_Desktop_CLI_Switch.sh. From Plasma it leaves the desktop for tty1
       and enables MP Mix Manager TTY Audio Mode. The console service
       mp-mix-manager-tty.service starts the manager there and restarts it if it exits.
       Ctrl+Alt+F2 stays a login shell. From that console, option 37 turns the mode off
       and returns to the Plasma login. Playback stays in the terminal player. The console
       is restored on exit, including a crash: echo, the cursor, and stty sane. The player
       repaints changed cells and does not clear the screen on every tick. Liquid Glass,
       MP Gui, the visualizer, and other desktop windows stay closed. Also: tty, tty-mode, desktop-cli.
  ${BOLD}${CYAN}38${NC}   ${BOLD}Exit Manager${NC} (or q / exit)
       Exit the application cleanly.

${BOLD}VISUALIZER KEYS:${NC}
  ${CYAN}1${NC}-${CYAN}9${NC}        Numbered preset slots.
  ${CYAN}+${NC} / ${CYAN}-${NC}        Cycle the entire preset library in either direction.
  ${CYAN}F10${NC}        Span a visualizer across every other monitor, then fullscreen them.
  ${CYAN}F11${NC}        Same as F10, with a different random preset per spawned window.
               Press F10 or F11 again to close the extra windows.
  ${CYAN}Z${NC}          Cycle fullscreen -> half the default size -> default size.
  ${CYAN}R${NC}          Turn random mode on: a new random preset every minute. Press R again to stop.

${BOLD}HEADER SESSION:${NC}
  A desktop Bash terminal shows ${CYAN}CLI Mode${NC} on the right of the main header title.
  The Linux text console shows ${GREEN}TTY CLI Mode${NC}. MP Gui does not show either label.

${BOLD}SYSTEM TRAY:${NC}
  MP Mix Manager, MP Gui, and MP Liquid Player share one tray icon while any of them is open.
  Right-click it for ${CYAN}Launch MP Gui${NC}, ${CYAN}Launch MP Liquid Player${NC}, and ${CYAN}Launch MP Mix Manager${NC}.
  ${CYAN}Start / Stop MP Web Audio${NC} starts or stops the Mobile Web Companion service (Linux). The row reads
  ${CYAN}Stop MP Web Audio${NC} while the companion is serving and ${CYAN}Start MP Web Audio${NC} while it is not. Stopping it
  notifies every connected phone that the companion is restarting, and they refresh themselves as soon as it is back.
  ${CYAN}Close MP Mix Manager (Closes everything)${NC} stops the console manager, MP Gui, MP Liquid Player, playback, and the visualizer.

${BOLD}INSTANCE CAP:${NC}
  MP Gui and MP Liquid Player open at most ${BOLD}4${NC} windows each, from the desktop shortcuts, the global
  hotkeys, and the tray icon. The shortcuts open a new window until four are up; a fifth launch brings an
  open window forward and says so. The console manager, the tracklist viewer, and the visualizer are not capped.

${BOLD}DIRECT COMMAND SHORTCUTS:${NC}
  You can execute these shortcuts directly from the command line:
    ${CYAN}split-flac${NC}        Split continuous FLAC audio via CUE sheet or track boundaries
    ${CYAN}split-video${NC}       Split video clips into segments
    ${CYAN}cut-video${NC}         Trim / cut video clips by timestamps
    ${CYAN}btop${NC}              Launch btop interactive hardware monitor
    ${CYAN}nvtop${NC}             Launch nvtop GPU performance monitor
    ${CYAN}top${NC}               Launch standard top process monitor
    ${CYAN}beszel${NC}            Manage Beszel Hub & Agent monitoring services
    ${CYAN}ollama${NC}            Manage Ollama LLM server & chat sessions
    ${CYAN}dsh${NC}               Manage DeepSeek Mobile Harness server
    ${CYAN}inspect${NC} | ${CYAN}specs${NC}   Inspect audio specifications of currently playing mix
    ${CYAN}audacity${NC}          Launch Audacity digital audio editor
    ${CYAN}strawberry${NC}        Launch Strawberry music player
    ${CYAN}vlc${NC}               Launch VLC media player
    ${CYAN}haruna${NC}            Launch Haruna video player
    ${CYAN}gimp${NC}              Launch GIMP image editor
    ${CYAN}electricsheep${NC}     Launch Electric Sheep screensaver
    ${CYAN}geexlab${NC}           Launch GeeXLab 3D demos
    ${CYAN}gpu-screen-recorder${NC}  Record a DJ mix with GPU Screen Recorder (Linux)
    ${CYAN}gui${NC} | ${CYAN}mp-gui${NC} | ${CYAN}36${NC}   Open the MP Mix Manager GUI (Liquid Glass)
    ${CYAN}vr${NC} | ${CYAN}vr-mode${NC} | ${CYAN}bigscreen${NC}   Enter VR Mode with MP Liquid Player (BigScreen)
    ${CYAN}tty${NC} | ${CYAN}37${NC}          Linux TTY Desktop Switcher (MP Mix Manager TTY Audio Mode)
    ${CYAN}visualizer${NC} | ${CYAN}Z${NC}   Launch the MP Liquid Visualizer
    ${CYAN}alarm${NC} | ${CYAN}alarm-clock${NC}   Launch MPlanetarians Alarm Clock (Wake Up Edition)
    ${CYAN}congen${NC} | ${CYAN}kdeconnect${NC}    Launch Congen KDE Connect Commands Generator & Remote Control
    ${CYAN}m${NC} | ${CYAN}monitor${NC}     Monitor processes, shell commands, and system info in a new tab
    ${CYAN}reinstall${NC}         Reset this user's config and reinstall (asks what to keep)

${BOLD}EXAMPLES:${NC}
  ${DIM}# Launch interactive terminal UI:${NC}
  ${GREEN}mix-archive-manager${NC}

  ${DIM}# Launch morning alarm clock control:${NC}
  ${GREEN}mix-archive-manager alarm${NC}

  ${DIM}# Launch Congen KDE Connect commands suite:${NC}
  ${GREEN}mix-archive-manager congen${NC}

  ${DIM}# Display help usage and all available options:${NC}
  ${GREEN}mix-archive-manager --help${NC}
  ${GREEN}mix-archive-manager -h${NC}

  ${DIM}# Display version information:${NC}
  ${GREEN}mix-archive-manager --version${NC}

  ${DIM}# Check for and install software updates:${NC}
  ${GREEN}mix-archive-manager update${NC}

  ${DIM}# Open the MP Mix Manager GUI:${NC}
  ${GREEN}mix-archive-manager gui${NC}

  ${DIM}# Directly jump into Option 16 (Configure Mix Archive Storage):${NC}
  ${GREEN}mix-archive-manager 16${NC}

  ${DIM}# Directly launch btop resource monitor:${NC}
  ${GREEN}mix-archive-manager btop${NC}

  ${DIM}# Query path of currently playing mix track:${NC}
  ${GREEN}mix-archive-manager --track${NC}

EOF
