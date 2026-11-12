#!/usr/bin/env bash
# ==============================================================================
# MP_Mix_Manager - Reinstall / Factory Reset
#
# Wipes the user's MP Mix Manager configuration and leaves the program in the
# same state as a first install. Works on every supported host: Linux,
# Bazzite / SteamOS, macOS, Windows (Git Bash / MSYS2), WSL, and FreeBSD.
#
# The user is asked separately whether to preserve:
#   * playlists            (custom playlists, generated playlists, favorites)
#   * music folder config  (music_folders.json, mounts, MUSIC_SMB_* settings)
#   * mix archive config   (MIX_ARCHIVE_DIR and the archive/output paths)
#
# Converted audio is never deleted. FLAC_CONVERTED_OUTPUTS,
# MP3_CONVERTED_OUTPUTS, WAV_CONVERTED_OUTPUTS, MP4_CONVERTED_OUTPUTS,
# CONVERTED_WAV_FILES, MIX_ARCHIVE, COVERS, and SPEK_OUTPUTS are left exactly
# as they are. The user deletes their own audio files.
#
# Usage:
#   ./install.sh --reinstall                     Ask what to preserve
#   ./install.sh --reinstall --yes               Preserve everything, no prompt
#   ./install.sh --reinstall --fresh --yes       Wipe everything (no preserve)
#   ./install.sh --reinstall --preserve-playlists \
#                            --preserve-music-folders \
#                            --preserve-archive-config --yes
#
# This file can also be run on its own:
#   bash scripts/reinstall_mp_manager.sh [options]
# ==============================================================================
set -euo pipefail

BOLD='\033[1m'
DIM='\033[2m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m'

# ------------------------------------------------------------------------------
# Locate the install tree
# ------------------------------------------------------------------------------
_resolve_script() {
    local src="$1" dir
    while [ -h "$src" ]; do
        dir="$(cd -P "$(dirname "$src")" >/dev/null 2>&1 && pwd)"
        src="$(readlink "$src")"
        case "$src" in
            /*) ;;
            *) src="$dir/$src" ;;
        esac
    done
    cd -P "$(dirname "$src")" >/dev/null 2>&1 && pwd
}

_HELPER_DIR="$(_resolve_script "${BASH_SOURCE[0]}")"
if [ -f "$_HELPER_DIR/Mix_Archive_Manager.sh" ]; then
    DEFAULT_ROOT="$_HELPER_DIR"
elif [ -f "$_HELPER_DIR/../Mix_Archive_Manager.sh" ]; then
    DEFAULT_ROOT="$(cd -P "$_HELPER_DIR/.." >/dev/null 2>&1 && pwd)"
else
    DEFAULT_ROOT="$_HELPER_DIR"
fi
unset _HELPER_DIR

ROOT="${MP_REINSTALL_ROOT:-$DEFAULT_ROOT}"
ROOT="${ROOT%/}"

# Windows Git Bash / MSYS2 can leave HOME unset; fall back to USERPROFILE.
if [ -z "${HOME:-}" ] && [ -n "${USERPROFILE:-}" ]; then
    HOME="$USERPROFILE"
fi
CONFIG_DIR="${MP_REINSTALL_CONFIG_DIR:-${HOME}/.config/mix-manager}"
DATA_DIR="${MP_REINSTALL_DATA_DIR:-${HOME}/.local/share/mp-mix-manager}"

# ------------------------------------------------------------------------------
# Host detection
# ------------------------------------------------------------------------------
OS_TYPE="linux"
case "$(uname -s 2>/dev/null || echo Linux)" in
    Darwin*) OS_TYPE="macos" ;;
    CYGWIN*|MINGW*|MSYS*) OS_TYPE="windows" ;;
    FreeBSD*) OS_TYPE="freebsd" ;;
    Linux*)
        if grep -qi microsoft /proc/version 2>/dev/null; then
            OS_TYPE="wsl"
        else
            OS_TYPE="linux"
        fi
        ;;
esac

say()  { echo -e "$*"; }
step() { echo -e "      ${CYAN}$*${NC}"; }
ok()   { echo -e "      ${GREEN}✓ $*${NC}"; }
warn() { echo -e "      ${YELLOW}⚠ $*${NC}"; }
die()  { echo -e "\n${RED}$*${NC}" >&2; exit 1; }

usage() {
    echo -e "${BOLD}MP Mix Manager - Reinstall (Factory Reset)${NC}"
    echo ""
    echo "Usage: bash scripts/reinstall_mp_manager.sh [options]"
    echo ""
    echo "Options:"
    echo "  --root PATH                  Install directory (default: this install)"
    echo "  --preserve-playlists         Keep custom playlists, generated playlists, favorites"
    echo "  --preserve-music-folders     Keep music_folders.json, mounts, MUSIC_SMB_* settings"
    echo "  --preserve-archive-config    Keep MIX_ARCHIVE_DIR and the archive/output paths"
    echo "  --no-preserve-playlists      Do not keep playlists"
    echo "  --no-preserve-music-folders  Do not keep music folder config"
    echo "  --no-preserve-archive-config Do not keep mix archive folder config"
    echo "  --fresh                      Preserve nothing (same as all --no-preserve-*)"
    echo "  --yes, -y                    Do not ask for confirmation; default to preserving"
    echo "  --dry-run                    Show what would be removed and kept"
    echo "  -h, --help                   Show this help"
    echo ""
    echo "The installer calls this script for you:"
    echo "  ./install.sh --reinstall"
    echo "  ./install.sh --reinstall --yes"
    echo "  ./install.sh --reinstall --fresh --yes"
    echo ""
    echo -e "${BOLD}Converted audio is never deleted.${NC}"
    echo "Remove your own converted files from the archive folders when you are ready."
}

# ------------------------------------------------------------------------------
# Options
# ------------------------------------------------------------------------------
ASSUME_YES=0
DRY_RUN=0
PRESERVE_PLAYLISTS=""
PRESERVE_MUSIC=""
PRESERVE_ARCHIVE=""
NO_PRESERVE=0

while [ $# -gt 0 ]; do
    case "$1" in
        --root)
            [ $# -ge 2 ] || die "--root needs a directory"
            ROOT="${2%/}"
            shift 2
            ;;
        --preserve-playlists|--keep-playlists)
            PRESERVE_PLAYLISTS=1; shift ;;
        --preserve-music-folders|--keep-music-folders)
            PRESERVE_MUSIC=1; shift ;;
        --preserve-archive-config|--keep-archive-config|--preserve-archive)
            PRESERVE_ARCHIVE=1; shift ;;
        --no-preserve-playlists)
            PRESERVE_PLAYLISTS=0; shift ;;
        --no-preserve-music-folders)
            PRESERVE_MUSIC=0; shift ;;
        --no-preserve-archive-config|--no-preserve-archive)
            PRESERVE_ARCHIVE=0; shift ;;
        --fresh|--no-preserve)
            NO_PRESERVE=1; shift ;;
        --yes|-y)
            ASSUME_YES=1; shift ;;
        --dry-run)
            DRY_RUN=1; shift ;;
        -h|--help)
            usage; exit 0 ;;
        *)
            die "Unknown option: $1 (use --help)" ;;
    esac
done

[ -d "$ROOT" ] || die "Install directory was not found: $ROOT"
[ -f "$ROOT/Mix_Archive_Manager.sh" ] || die "This does not look like an MP Mix Manager install: $ROOT"

if [ "$NO_PRESERVE" -eq 1 ]; then
    PRESERVE_PLAYLISTS=0
    PRESERVE_MUSIC=0
    PRESERVE_ARCHIVE=0
fi

# ------------------------------------------------------------------------------
# Interactive questions
# ------------------------------------------------------------------------------
ask_preserve() {
    # $1 label, $2 variable name
    local label="$1" var="$2" ans=""
    if [ -n "${!var:-}" ]; then
        return 0
    fi
    if [ "$ASSUME_YES" -eq 1 ]; then
        printf -v "$var" '%s' 1
        return 0
    fi
    while :; do
        printf "      Preserve %s? [Y/n]: " "$label"
        if [ -r /dev/tty ]; then
            IFS= read -r ans < /dev/tty || ans=""
        else
            IFS= read -r ans || ans=""
        fi
        case "$ans" in
            ""|y|Y|yes|YES|Yes) printf -v "$var" '%s' 1; return 0 ;;
            n|N|no|NO|No)       printf -v "$var" '%s' 0; return 0 ;;
            *) echo "      Please answer y or n." ;;
        esac
    done
}

confirm_reinstall() {
    local ans=""
    if [ "$ASSUME_YES" -eq 1 ]; then
        return 0
    fi
    echo ""
    echo -e "      Type ${BOLD}REINSTALL${NC} to confirm, or press Enter to cancel:"
    printf "      > "
    if [ -r /dev/tty ]; then
        IFS= read -r ans < /dev/tty || ans=""
    else
        IFS= read -r ans || ans=""
    fi
    [ "$ans" = "REINSTALL" ] || return 1
    return 0
}

# ------------------------------------------------------------------------------
# Header
# ------------------------------------------------------------------------------
echo ""
echo -e "${BOLD}${MAGENTA}======================================================================${NC}"
echo -e "${BOLD}${MAGENTA}          MP Mix Manager - Reinstall / Factory Reset                  ${NC}"
echo -e "${BOLD}${MAGENTA}======================================================================${NC}"
echo -e "  Install directory:   ${BOLD}${CYAN}${ROOT}${NC}"
echo -e "  Config directory:    ${BOLD}${CYAN}${CONFIG_DIR}${NC}"
echo -e "  Detected host OS:    ${BOLD}${CYAN}${OS_TYPE}${NC}"
echo ""
echo -e "This resets MP Mix Manager to a first-install state. Your saved settings,"
echo -e "themes, equalizer, window layout, caches, and activity history are cleared."
echo -e "${BOLD}${GREEN}Converted audio files are never deleted.${NC} You remove those yourself."
echo ""

ask_preserve "playlists (custom, generated, and favorites)" PRESERVE_PLAYLISTS
ask_preserve "music folder config (folders and SMB login)" PRESERVE_MUSIC
ask_preserve "mix archive folder config (archive paths)" PRESERVE_ARCHIVE

echo ""
echo -e "  ${BOLD}Will preserve:${NC}"
[ "$PRESERVE_PLAYLISTS" -eq 1 ] && echo -e "    ${GREEN}•${NC} playlists"
[ "$PRESERVE_MUSIC" -eq 1 ]     && echo -e "    ${GREEN}•${NC} music folder config"
[ "$PRESERVE_ARCHIVE" -eq 1 ]   && echo -e "    ${GREEN}•${NC} mix archive folder config"
if [ "$PRESERVE_PLAYLISTS" -eq 0 ] && [ "$PRESERVE_MUSIC" -eq 0 ] && [ "$PRESERVE_ARCHIVE" -eq 0 ]; then
    echo -e "    ${DIM}(nothing - full factory reset)${NC}"
fi

if ! confirm_reinstall; then
    echo -e "\n${YELLOW}Reinstall cancelled. Nothing was changed.${NC}"
    exit 10
fi

# ------------------------------------------------------------------------------
# Stop programs that hold config files open
# ------------------------------------------------------------------------------
stop_helpers() {
    [ "${MP_REINSTALL_SKIP_STOP:-0}" = "1" ] && return 0
    local killer="$ROOT/scripts/kill_all_mp_audio_players.sh"
    [ -f "$killer" ] || killer="$ROOT/kill_all_mp_audio_players.sh"
    if [ -f "$killer" ]; then
        bash "$killer" -q >/dev/null 2>&1 || true
    fi
    # Tray and visualizer are not covered by the player killer. The manager
    # itself is left running: the reinstall can be started from its own menu.
    if command -v pkill >/dev/null 2>&1; then
        pkill -f "mp_system_tray\.py" >/dev/null 2>&1 || true
        pkill -f "windows_tray\.ps1" >/dev/null 2>&1 || true
        pkill -f "MP_Liquid_Visualizer" >/dev/null 2>&1 || true
        pkill -f "liquid_visualizer" >/dev/null 2>&1 || true
    fi
    if [ "$OS_TYPE" = "windows" ] || [ "$OS_TYPE" = "wsl" ]; then
        if command -v taskkill.exe >/dev/null 2>&1; then
            taskkill.exe //F //IM "MP Mix Manager.exe" >/dev/null 2>&1 || true
        fi
    fi
    if [ "$OS_TYPE" = "macos" ] && command -v launchctl >/dev/null 2>&1; then
        launchctl bootout "gui/$(id -u)/com.mplanetarian.mp-mix-manager-tray" >/dev/null 2>&1 || true
    fi
}

# ------------------------------------------------------------------------------
# Staging: copies are made first, then the config is wiped, then restored.
# ------------------------------------------------------------------------------
STAGE=""
cleanup_stage() {
    [ -n "${STAGE:-}" ] && [ -d "$STAGE" ] && rm -rf "$STAGE" 2>/dev/null || true
}
trap cleanup_stage EXIT

MANIFEST=""
STAGE_INDEX=0

stage_path() {
    # $1 absolute source path
    local src="$1" idx dest
    { [ -e "$src" ] || [ -L "$src" ]; } || return 0
    if [ "$DRY_RUN" -eq 1 ]; then
        step "would preserve: $src"
        return 0
    fi
    STAGE_INDEX=$((STAGE_INDEX + 1))
    idx="$STAGE_INDEX"
    dest="$STAGE/files/$idx"
    mkdir -p "$STAGE/files"
    if cp -a "$src" "$dest" 2>/dev/null; then
        printf '%s\t%s\n' "$src" "$idx" >> "$MANIFEST"
        step "preserved: $src"
    else
        warn "could not preserve: $src"
    fi
}

restore_staged() {
    [ -n "$MANIFEST" ] && [ -f "$MANIFEST" ] || return 0
    local src idx
    while IFS="$(printf '\t')" read -r src idx; do
        [ -n "$src" ] && [ -n "$idx" ] || continue
        [ -e "$STAGE/files/$idx" ] || continue
        if is_protected_path "$src"; then
            warn "refusing to replace protected path: $src"
            continue
        fi
        mkdir -p "$(dirname "$src")" 2>/dev/null || true
        rm -rf "$src" 2>/dev/null || true
        if cp -a "$STAGE/files/$idx" "$src" 2>/dev/null; then
            ok "restored: $src"
        else
            warn "could not restore: $src"
        fi
    done < "$MANIFEST"
}

is_mountpoint() {
    local path="$1"
    [ -d "$path" ] || return 1
    if command -v mountpoint >/dev/null 2>&1; then
        mountpoint -q "$path" 2>/dev/null
        return $?
    fi
    local dev parent
    dev="$(df -P "$path" 2>/dev/null | awk 'NR==2 {print $1}')"
    parent="$(df -P "$(dirname "$path")" 2>/dev/null | awk 'NR==2 {print $1}')"
    [ -n "$dev" ] && [ -n "$parent" ] && [ "$dev" != "$parent" ]
}

# ------------------------------------------------------------------------------
# Config.env key preservation
# ------------------------------------------------------------------------------
OLD_CONFIG="$ROOT/config.env"
KEY_FILE=""

read_config_line() {
    # $1 key; prints the raw assignment line (quotes kept)
    [ -f "$OLD_CONFIG" ] || return 0
    MP_CFG_KEY="$1" awk '
        BEGIN { k = ENVIRON["MP_CFG_KEY"] }
        $0 ~ "^[[:space:]]*" k "=" { print; exit }
    ' "$OLD_CONFIG"
}

config_value() {
    # $1 key; prints the unquoted value of the first matching assignment
    local line
    line="$(read_config_line "$1")"
    [ -n "$line" ] || return 0
    line="${line#*=}"
    line="${line#"${line%%[![:space:]]*}"}"
    line="${line%"${line##*[![:space:]]}"}"
    line="${line%\"}"; line="${line#\"}"
    line="${line%\'}"; line="${line#\'}"
    printf '%s' "$line"
}

capture_config_keys() {
    [ -f "$OLD_CONFIG" ] || return 0
    local key line count
    if [ -z "${KEY_FILE_INITIALIZED:-}" ]; then
        : > "$KEY_FILE"
        KEY_FILE_INITIALIZED=1
    fi
    for key in "$@"; do
        line="$(read_config_line "$key")"
        [ -n "$line" ] && printf '%s\n' "$line" >> "$KEY_FILE"
    done
    count="$(grep -c '' "$KEY_FILE" 2>/dev/null || echo 0)"
    [ "$count" -gt 0 ] && step "captured ${count} config.env setting(s) to carry over"
    return 0
}

apply_config_keys() {
    [ -n "$KEY_FILE" ] && [ -s "$KEY_FILE" ] || return 0
    local new_config="$ROOT/config.env" line key
    [ -f "$new_config" ] || : > "$new_config"
    while IFS= read -r line; do
        [ -n "$line" ] || continue
        key="${line%%=*}"
        key="${key#"${key%%[![:space:]]*}"}"
        key="${key%"${key##*[![:space:]]}"}"
        [ -n "$key" ] || continue
        MP_CFG_KEY="$key" MP_CFG_LINE="$line" awk '
            BEGIN { k = ENVIRON["MP_CFG_KEY"]; repl = ENVIRON["MP_CFG_LINE"]; done = 0 }
            $0 ~ "^[[:space:]]*" k "=" { if (!done) { print repl; done = 1 } ; next }
            { print }
            END { if (!done) print repl }
        ' "$new_config" > "$new_config.reinstall.tmp"
        mv "$new_config.reinstall.tmp" "$new_config"
    done < "$KEY_FILE"
    ok "restored archive and music folder settings into the new config.env"
}

# ------------------------------------------------------------------------------
# Wipe helpers
# ------------------------------------------------------------------------------
PROTECTED_BASENAMES=(
    FLAC_CONVERTED_OUTPUTS MP3_CONVERTED_OUTPUTS WAV_CONVERTED_OUTPUTS
    MP4_CONVERTED_OUTPUTS CONVERTED_WAV_FILES MIX_ARCHIVE COVERS
    SPEK_OUTPUTS MP_AUDIOWAV_REC_OUTPUT TOP_5_TRACKS
)
PROTECTED_ROOTS=()

add_protected_root() {
    # Skip "roots" that are the install tree itself or one of its parents: a
    # broad MIX_ARCHIVE_DIR must not turn the whole install into a protected
    # area, or the reset would silently stop working.
    local candidate="${1%/}" root="${ROOT%/}" skip
    [ -n "$candidate" ] || return 0
    skip=0
    case "$root" in
        "$candidate") skip=1 ;;
        "$candidate"/*) skip=1 ;;
    esac
    [ "$skip" -eq 1 ] && return 0
    PROTECTED_ROOTS+=("$candidate")
}

collect_protected_roots() {
    # Exact folders that hold converted audio, source WAVs, recordings, and
    # artwork. These and anything below them are never removed. Absolute paths
    # come from the install tree, the active config.env, and the extra list.
    PROTECTED_ROOTS=()
    local name path key extras entry
    for name in "${PROTECTED_BASENAMES[@]}"; do
        PROTECTED_ROOTS+=("$ROOT/$name")
        PROTECTED_ROOTS+=("$CONFIG_DIR/$name")
    done
    [ -f "$OLD_CONFIG" ] || return 0
    for key in MIX_ARCHIVE_DIR OUTPUT_DIR ARCHIVE_DIR MP3_OUTPUT_DIR \
               WAV_OUTPUT_DIR MP4_OUTPUT_DIR SPEK_DIR; do
        path="$(config_value "$key")"
        [ -n "$path" ] || continue
        case "$path" in
            /*|?:/*|?:\\*) add_protected_root "$path" ;;
            *) add_protected_root "$ROOT/$path" ;;
        esac
    done
    extras="$(config_value EXTRA_MIX_ARCHIVE_DIRS)"
    if [ -n "$extras" ]; then
        local IFS=';'
        for entry in $extras; do
            entry="${entry#"${entry%%[![:space:]]*}"}"
            entry="${entry%"${entry##*[![:space:]]}"}"
            entry="${entry%\"}"; entry="${entry#\"}"
            entry="${entry%\'}"; entry="${entry#\'}"
            case "$entry" in
                /*|?:/*|?:\\*) add_protected_root "$entry" ;;
            esac
        done
    fi
}

is_protected_path() {
    local target="${1%/}" root
    [ -n "$target" ] || return 1
    for root in "${PROTECTED_ROOTS[@]}"; do
        root="${root%/}"
        [ -n "$root" ] || continue
        if [ "$target" = "$root" ]; then
            return 0
        fi
        case "$target" in
            "$root"/*) return 0 ;;
        esac
    done
    return 1
}

wipe_path() {
    local target="$1"
    { [ -e "$target" ] || [ -L "$target" ]; } || return 0
    if is_protected_path "$target"; then
        warn "refusing to remove protected audio/artwork path: $target"
        return 1
    fi
    if [ "$DRY_RUN" -eq 1 ]; then
        step "would remove: $target"
        return 0
    fi
    if rm -rf -- "$target" 2>/dev/null; then
        step "removed: $target"
    else
        warn "could not remove: $target"
        return 1
    fi
}

wipe_dir_contents() {
    # Remove the contents of a directory but keep the directory itself.
    local dir="$1" entry
    [ -d "$dir" ] || return 0
    for entry in "$dir"/* "$dir"/.[!.]* "$dir"/..?*; do
        { [ -e "$entry" ] || [ -L "$entry" ]; } || continue
        wipe_path "$entry" || true
    done
}

# ------------------------------------------------------------------------------
# Build the staging area
# ------------------------------------------------------------------------------
if [ "$DRY_RUN" -eq 0 ]; then
    STAGE="$(mktemp -d "${TMPDIR:-/tmp}/mp_reinstall.XXXXXX")" || die "Could not create a staging directory"
    MANIFEST="$STAGE/manifest.tsv"
    KEY_FILE="$STAGE/config_keys.env"
else
    KEY_FILE=""
fi

echo ""
say "${BOLD}${BLUE}Stopping player, tray, and visualizer processes...${NC}"
stop_helpers

echo ""
say "${BOLD}${BLUE}Preserving selected settings...${NC}"

if [ "$PRESERVE_PLAYLISTS" -eq 1 ]; then
    for path in \
        "$ROOT/playlists" \
        "$ROOT/PLAYLISTS_GENERATED" \
        "$ROOT/scripts/playlists" \
        "$ROOT/scripts/PLAYLISTS_GENERATED" \
        "$CONFIG_DIR/playlists" \
        "$CONFIG_DIR/PLAYLISTS_GENERATED" \
        "$CONFIG_DIR/favorites.json" \
        "$CONFIG_DIR/favorites.m3u8" \
        "$CONFIG_DIR/top_5_tracks.json"; do
        stage_path "$path"
    done
fi

if [ "$PRESERVE_MUSIC" -eq 1 ]; then
    for path in \
        "$CONFIG_DIR/music_folders.json" \
        "$CONFIG_DIR/mounts"; do
        stage_path "$path"
    done
    if [ "$DRY_RUN" -eq 0 ]; then
        capture_config_keys \
            MUSIC_SMB_USER MUSIC_SMB_PASSWORD MUSIC_SMB_MOUNT_ROOT \
            MUSIC_SMB_HOST MUSIC_SMB_SHARES AV_EXPORT_LOCAL_DIR \
            FAV_EXPORT_LOCAL_DIR FAV_EXPORT_SMB_HOST FAV_EXPORT_SMB_SHARE \
            FAV_EXPORT_SMB_USER FAV_EXPORT_SMB_PASSWORD FAV_EXPORT_SMB_MOUNT
    fi
fi

if [ "$PRESERVE_ARCHIVE" -eq 1 ] && [ "$DRY_RUN" -eq 0 ]; then
    capture_config_keys \
        MIX_ARCHIVE_CONFIGURED MIX_ARCHIVE_DIR EXTRA_MIX_ARCHIVE_DIRS \
        OUTPUT_DIR ARCHIVE_DIR SPEK_DIR MP3_OUTPUT_DIR WAV_OUTPUT_DIR \
        MP4_OUTPUT_DIR
fi

# ------------------------------------------------------------------------------
# Wipe user configuration and runtime state
# ------------------------------------------------------------------------------
echo ""
say "${BOLD}${BLUE}Resetting configuration and runtime state...${NC}"

# Build the protected-root list before config.env is replaced.
collect_protected_roots

# config.env is recreated from the shipped template below.
wipe_path "$ROOT/config.env" || true

# The whole per-user config directory: theme, EQ, favorites, window layout,
# scheduled mixes, caches, logs, tray/macOS launch agent, and activity history.
if [ -d "$CONFIG_DIR" ]; then
    for entry in "$CONFIG_DIR"/* "$CONFIG_DIR"/.[!.]* "$CONFIG_DIR"/..?*; do
        { [ -e "$entry" ] || [ -L "$entry" ]; } || continue
        if is_mountpoint "$entry"; then
            warn "leaving a mounted music folder in place: $entry"
            continue
        fi
        wipe_path "$entry" || true
    done
    if [ "$DRY_RUN" -eq 0 ]; then
        rmdir "$CONFIG_DIR" 2>/dev/null || true
    fi
else
    step "no config directory to clear"
fi

# macOS keeps its generated Python environment and menu-bar bundle here.
wipe_path "$DATA_DIR" || true

# The macOS menu-bar agent is a launchd job outside the config directory.
if [ "$OS_TYPE" = "macos" ]; then
    wipe_path "${HOME}/Library/LaunchAgents/com.mplanetarian.mp-mix-manager-tray.plist" || true
fi

# Generated runtime files inside the install tree.
wipe_path "$ROOT/MP_Mix_Manager_Conversion_Log.jsonl" || true
wipe_path "$ROOT/MP_Mix_Manager_Conversion_Log.txt" || true
wipe_path "$ROOT/MP_Error.log" || true
wipe_path "$ROOT/running_history.log" || true
wipe_path "$ROOT/assets/weather_cache.txt" || true
wipe_path "$ROOT/LOGS" || true
wipe_path "$ROOT/.reinstall_stage" || true

if [ -d "$ROOT/logs" ]; then
    for entry in "$ROOT/logs"/* "$ROOT/logs"/.[!.]*; do
        { [ -e "$entry" ] || [ -L "$entry" ]; } || continue
        case "$(basename "$entry")" in
            .gitkeep) continue ;;
        esac
        wipe_path "$entry" || true
    done
fi

# Snapshot and exported bundle folders inside the install tree. The .gitkeep
# markers are kept so the first-install layout comes back unchanged.
for dir in "$ROOT/config_backups" "$ROOT/exported_configs"; do
    [ -d "$dir" ] || continue
    for entry in "$dir"/* "$dir"/.[!.]*; do
        { [ -e "$entry" ] || [ -L "$entry" ]; } || continue
        case "$(basename "$entry")" in
            .gitkeep) continue ;;
        esac
        wipe_path "$entry" || true
    done
done

# Playlists that live inside the install tree. Generated playlist folders in
# the user's archive storage are left alone: they sit on removable drives and
# are regenerated on demand from the Mix Archive menu.
if [ "$PRESERVE_PLAYLISTS" -eq 0 ]; then
    for dir in "$ROOT/PLAYLISTS_GENERATED" "$ROOT/playlists" \
               "$ROOT/scripts/PLAYLISTS_GENERATED" "$ROOT/scripts/playlists"; do
        [ -d "$dir" ] || continue
        for entry in "$dir"/* "$dir"/.[!.]*; do
            { [ -e "$entry" ] || [ -L "$entry" ]; } || continue
            case "$(basename "$entry")" in
                .gitkeep) continue ;;
            esac
            wipe_path "$entry" || true
        done
    done
fi

if [ -d "$ROOT/REPORTS" ]; then
    for entry in "$ROOT/REPORTS"/*; do
        { [ -e "$entry" ] || [ -L "$entry" ]; } || continue
        case "$(basename "$entry")" in
            DAILY_REPORTS|WEEKLY_REPORTS|MONTHLY_REPORTS|YEARLY_REPORTS)
                wipe_dir_contents "$entry" || true
                ;;
            DAILY|WEEKLY|MONTHLY|YEARLY)
                # These are symlinks to the report folders above. Keep them.
                continue
                ;;
            *)
                wipe_path "$entry" || true
                ;;
        esac
    done
fi

# ------------------------------------------------------------------------------
# Recreate the first-install configuration
# ------------------------------------------------------------------------------
echo ""
say "${BOLD}${BLUE}Recreating the default configuration...${NC}"

if [ "$DRY_RUN" -eq 0 ]; then
    if [ -f "$ROOT/config.env.example" ]; then
        cp "$ROOT/config.env.example" "$ROOT/config.env"
    else
        : > "$ROOT/config.env"
    fi
    chmod 600 "$ROOT/config.env" 2>/dev/null || true
    ok "created a fresh config.env from the shipped template"
    apply_config_keys
    restore_staged
else
    step "would recreate config.env from config.env.example"
fi

# ------------------------------------------------------------------------------
# Report what was deliberately left alone
# ------------------------------------------------------------------------------
echo ""
say "${BOLD}${GREEN}Converted audio and artwork left untouched:${NC}"
for dir in \
    "$ROOT/FLAC_CONVERTED_OUTPUTS" \
    "$ROOT/MP3_CONVERTED_OUTPUTS" \
    "$ROOT/WAV_CONVERTED_OUTPUTS" \
    "$ROOT/MP4_CONVERTED_OUTPUTS" \
    "$ROOT/CONVERTED_WAV_FILES" \
    "$ROOT/MIX_ARCHIVE" \
    "$ROOT/COVERS" \
    "$ROOT/SPEK_OUTPUTS"; do
    [ -d "$dir" ] && echo -e "    ${CYAN}${dir}${NC}"
done
if [ -f "$OLD_CONFIG" ] || [ -n "${MIX_ARCHIVE_DIR:-}" ]; then
    :
fi
# Show the configured archive root if it belongs to another drive.
if [ -n "$KEY_FILE" ] && [ -s "$KEY_FILE" ]; then
    archive_root="$(MP_CFG_KEY=MIX_ARCHIVE_DIR awk '
        BEGIN { k = ENVIRON["MP_CFG_KEY"] }
        $0 ~ "^[[:space:]]*" k "=" {
            v = $0
            sub(/^[^=]*=/, "", v)
            gsub(/^[[:space:]"'\'']+|[[:space:]"'\'']+$/, "", v)
            print v
            exit
        }
    ' "$KEY_FILE")"
    if [ -n "${archive_root:-}" ] && [ -d "$archive_root" ]; then
        echo -e "    ${CYAN}${archive_root}${NC}"
    fi
fi
unset archive_root 2>/dev/null || true

echo ""
echo -e "${BOLD}${GREEN}======================================================================${NC}"
if [ "$DRY_RUN" -eq 1 ]; then
    echo -e "${BOLD}${GREEN}              DRY RUN COMPLETE - nothing was changed                  ${NC}"
else
    echo -e "${BOLD}${GREEN}              REINSTALL RESET COMPLETE                                ${NC}"
fi
echo -e "${BOLD}${GREEN}======================================================================${NC}"
if [ "${MP_REINSTALL_FROM_INSTALLER:-0}" = "1" ]; then
    echo -e "  The installer continues next: permissions, folder scaffolds,"
    echo -e "  symlinks, and desktop shortcuts are installed again."
else
    echo -e "  Run ${BOLD}./install.sh${NC} to finish the install, or start the manager"
    echo -e "  with ${BOLD}manager${NC}."
fi
echo ""