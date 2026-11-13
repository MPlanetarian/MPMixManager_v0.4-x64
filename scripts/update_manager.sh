#!/usr/bin/env bash
# ==============================================================================
# MP_Mix_Archive_Manager - System Updater
# Purpose: Check for and install latest version of MP Mix Archive Manager
# Usage:
#   mix-archive-manager update          (Checks and installs latest version)
#   mix-archive-manager update --check  (Checks for updates without installing)
#   mix-archive-manager --version       (Displays current version)
#
# End of life hand-off:
#   0.4 is the final 0.4 release. On a 0.4 install, `update` upgrades the user
#   to MP Mix Manager 0.5 by cloning
#       https://github.com/MPlanetarian/MPMixManager_v0.5-x64
#   into a sibling directory, copying the user's config and data across, and
#   running the 0.5 installer. The 0.4 tree is left untouched as a fallback.
#
#   Until that repository actually has a published branch, `update` falls back
#   to the normal 0.4 git pull, so existing users keep getting 0.4 fixes.
#   A tree that already runs 0.5 keeps the original git-pull behaviour.
# ==============================================================================

set -euo pipefail

# ANSI Styling
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
# End-of-life hand-off configuration
# ------------------------------------------------------------------------------
MP_UPGRADE_REPO_SLUG="MPMixManager_v0.5-x64"
MP_UPGRADE_REPO_URL="${MP_UPGRADE_REPO_URL:-https://github.com/MPlanetarian/${MP_UPGRADE_REPO_SLUG}.git}"
MP_UPGRADE_PREFERRED_BRANCH="${MP_UPGRADE_PREFERRED_BRANCH:-main}"
MP_UPGRADE_TARGET_MM="${MP_UPGRADE_TARGET_MM:-0.5}"
MP_UPGRADE_TARGET_DIR="${MP_UPGRADE_TARGET_DIR:-}"
MP_UPGRADE_SKIP_INSTALL="${MP_UPGRADE_SKIP_INSTALL:-0}"

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

get_current_version() {
    if [ -n "${VERSION:-}" ]; then
        echo "${VERSION#v}"
    elif [ -f "$CODEBASE_DIR/VERSION" ]; then
        head -n 1 "$CODEBASE_DIR/VERSION" | tr -d '\r\n'
    elif [ -f "$CODEBASE_DIR/CHANGELOG.md" ]; then
        grep -E '^## \[[0-9]+\.[0-9]+' "$CODEBASE_DIR/CHANGELOG.md" | head -1 | sed -E 's/.*\[([0-9]+\.[0-9]+\.[0-9]+.*)\].*/\1/'
    else
        echo "0.4.3 Stable (Liquid)"
    fi
}

CURRENT_VER="$(get_current_version)"
export VERSION="${VERSION:-$CURRENT_VER}"

# Print the "major.minor" part of a version label ("0.4.2 Stable" -> "0.4").
version_major_minor() {
    printf '%s' "${1:-}" | sed -n 's/^[[:space:]]*[vV]*\([0-9][0-9]*\.[0-9][0-9]*\).*$/\1/p' | head -n 1
}

# Exit 0 when version $1 is greater than or equal to version $2.
version_at_least() {
    awk -v a="${1:-0}" -v b="${2:-0}" '
        BEGIN {
            na = split(a, x, ".")
            nb = split(b, y, ".")
            for (i = 1; i <= 3; i++) {
                xa = (i <= na && x[i] != "") ? x[i] + 0 : 0
                yb = (i <= nb && y[i] != "") ? y[i] + 0 : 0
                if (xa > yb) exit 0
                if (xa < yb) exit 1
            }
            exit 0
        }'
}

CURRENT_MM="$(version_major_minor "$CURRENT_VER")"

# ------------------------------------------------------------------------------
# 1. Version Flag Check (--version, -v, version)
# ------------------------------------------------------------------------------
if [ "${1:-}" = "--version" ] || [ "${1:-}" = "-v" ] || [ "${1:-}" = "version" ]; then
    COMMIT_HASH="unknown"
    COMMIT_DATE=""
    if [ -d "$CODEBASE_DIR/.git" ] && command -v git >/dev/null 2>&1; then
        COMMIT_HASH=$(git -C "$CODEBASE_DIR" rev-parse --short HEAD 2>/dev/null || echo "unknown")
        COMMIT_DATE=$(git -C "$CODEBASE_DIR" log -1 --format=%cd --date=short 2>/dev/null || echo "")
    fi
    if [ -n "$COMMIT_DATE" ]; then
        echo -e "MP Mix Archive Manager ${BOLD}v${CURRENT_VER}${NC} (${CYAN}${COMMIT_HASH}${NC}, ${COMMIT_DATE})"
    else
        echo -e "MP Mix Archive Manager ${BOLD}v${CURRENT_VER}${NC} (${CYAN}${COMMIT_HASH}${NC})"
    fi
    exit 0
fi

# ------------------------------------------------------------------------------
# 2. Help Flag
# ------------------------------------------------------------------------------
if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ] || [ "${1:-}" = "help" ]; then
    echo -e "${BOLD}MP Mix Archive Manager - System Updater${NC}"
    echo -e "Usage:"
    echo -e "  mix-archive-manager update           Check for and install the latest version"
    echo -e "  mix-archive-manager update --check   Check for available updates without installing"
    echo -e "  mix-archive-manager update --force   Force re-pull/update from remote"
    echo -e "  mix-archive-manager --version        Display current installed version"
    echo -e "  mix-archive-manager --help           Display help usage and list all options"
    echo ""
    echo -e "${BOLD}${YELLOW}0.4 is end of life${NC}"
    echo -e "  Running 'update' on a 0.4 install upgrades it to MP Mix Manager 0.5"
    echo -e "  (${CYAN}${MP_UPGRADE_REPO_SLUG}${NC}). A fresh 0.5 tree is cloned next to this"
    echo -e "  one and your configuration, playlists, covers, reports and archive data"
    echo -e "  are copied into it. The 0.4 tree is never modified or deleted."
    echo -e "  ${DIM}Override the clone URL with MP_UPGRADE_REPO_URL and the destination"
    echo -e "  with MP_UPGRADE_TARGET_DIR. Use --check to preview the upgrade.${NC}"
    exit 0
fi

CHECK_ONLY=0
FORCE_UPDATE=0

for arg in "$@"; do
    case "$arg" in
        --check|-c) CHECK_ONLY=1 ;;
        --force|-f) FORCE_UPDATE=1 ;;
    esac
done

# ------------------------------------------------------------------------------
# 3. Banner
# ------------------------------------------------------------------------------
echo -e "${BOLD}${MAGENTA}======================================================================${NC}"
echo -e "${BOLD}${MAGENTA}                 MP Mix Archive Manager - System Updater                 ${NC}"
echo -e "${BOLD}${MAGENTA}======================================================================${NC}"
echo -e "  Current Installed Version: ${BOLD}${GREEN}v${CURRENT_VER}${NC}"
echo -e "  Codebase Directory:        ${CYAN}${CODEBASE_DIR}${NC}"

# Check git availability
if ! command -v git >/dev/null 2>&1; then
    echo -e "${YELLOW}Warning: 'git' command not found. Cannot verify remote repository updates.${NC}"
    echo -e "MP Mix Archive Manager is running version: ${BOLD}${GREEN}v${CURRENT_VER}${NC}"
    exit 0
fi

# ------------------------------------------------------------------------------
# End-of-life helpers
# ------------------------------------------------------------------------------
# The directory the 0.5 tree is cloned into.
successor_target_dir() {
    if [ -n "$MP_UPGRADE_TARGET_DIR" ]; then
        printf '%s\n' "$MP_UPGRADE_TARGET_DIR"
    else
        printf '%s\n' "$(dirname "$CODEBASE_DIR")/$MP_UPGRADE_REPO_SLUG"
    fi
}

# 0 when this tree is already MP Mix Manager 0.5 (by version or by remote).
tree_is_successor() {
    local url=""
    if [ -n "$CURRENT_MM" ] && version_at_least "$CURRENT_MM" "$MP_UPGRADE_TARGET_MM"; then
        return 0
    fi
    if [ -d "$CODEBASE_DIR/.git" ]; then
        url="$(git -C "$CODEBASE_DIR" remote get-url origin 2>/dev/null || true)"
        case "$url" in
            *"$MP_UPGRADE_REPO_SLUG"*) return 0 ;;
        esac
    fi
    return 1
}

# 0 when a published branch exists on the successor repository.
SUCCESSOR_BRANCH=""
SUCCESSOR_REMOTE_STATE="unknown"

probe_successor_remote() {
    local refs=""
    SUCCESSOR_BRANCH=""
    # The 0.5 repository is public and reached over HTTPS. Never block the
    # updater on a credential prompt if it has been renamed or made private.
    refs="$(GIT_TERMINAL_PROMPT=0 GIT_ASKPASS=/bin/echo \
        git ls-remote --heads "$MP_UPGRADE_REPO_URL" 2>/dev/null || true)"
    if [ -n "$refs" ]; then
        if printf '%s\n' "$refs" | grep -q "refs/heads/${MP_UPGRADE_PREFERRED_BRANCH}$"; then
            SUCCESSOR_BRANCH="$MP_UPGRADE_PREFERRED_BRANCH"
        elif printf '%s\n' "$refs" | grep -q 'refs/heads/master$'; then
            SUCCESSOR_BRANCH="master"
        else
            SUCCESSOR_BRANCH="$(printf '%s\n' "$refs" | head -n 1 | sed -E 's#.*refs/heads/##')"
        fi
        SUCCESSOR_REMOTE_STATE="available"
    elif GIT_TERMINAL_PROMPT=0 GIT_ASKPASS=/bin/echo \
            git ls-remote "$MP_UPGRADE_REPO_URL" >/dev/null 2>&1; then
        # Reachable but with no commits: the release is not published yet.
        SUCCESSOR_REMOTE_STATE="empty"
    else
        SUCCESSOR_REMOTE_STATE="unreachable"
    fi
}

# 0 when the successor tree exists and really is a 0.5 install.
successor_tree_valid() {
    local dir="$1" mm="" url=""
    [ -d "$dir" ] || return 1
    [ -f "$dir/Mix_Archive_Manager.sh" ] || return 1
    if [ -f "$dir/VERSION" ]; then
        mm="$(version_major_minor "$(head -n 1 "$dir/VERSION" 2>/dev/null | tr -d '\r\n')")"
    fi
    if [ -n "$mm" ] && version_at_least "$mm" "$MP_UPGRADE_TARGET_MM"; then
        return 0
    fi
    if [ -d "$dir/.git" ]; then
        url="$(git -C "$dir" remote get-url origin 2>/dev/null || true)"
        case "$url" in
            *"$MP_UPGRADE_REPO_SLUG"*) return 0 ;;
        esac
    fi
    return 1
}

# Copy one directory tree, never overwriting a file that already exists.
copy_missing_tree() {
    local src="$1" dst="$2"
    [ -d "$src" ] || return 0
    mkdir -p "$dst" 2>/dev/null || true
    if command -v rsync >/dev/null 2>&1; then
        rsync -a --ignore-existing "$src"/ "$dst"/ >/dev/null 2>&1 || true
        return 0
    fi
    (
        cd "$src" || exit 0
        find . -type f -print0 2>/dev/null | while IFS= read -r -d '' f; do
            rel="${f#./}"
            [ -e "$dst/$rel" ] && continue
            mkdir -p "$dst/$(dirname "$rel")" 2>/dev/null || continue
            cp "$rel" "$dst/$rel" 2>/dev/null || true
        done
    ) || true
}

# Carry the user's configuration and in-tree data into the 0.5 tree.
migrate_user_data() {
    local src="$1" dst="$2" item count=0
    echo -e "\n${BOLD}${BLUE}Carrying your configuration and data across...${NC}"

    if [ -f "$src/config.env" ] && [ ! -f "$dst/config.env" ]; then
        if cp "$src/config.env" "$dst/config.env" 2>/dev/null; then
            echo -e "  ${GREEN}✓${NC} config.env"
            count=$((count + 1))
        else
            echo -e "  ${YELLOW}⚠${NC} config.env could not be copied"
        fi
    elif [ -f "$dst/config.env" ]; then
        echo -e "  ${DIM}•${NC} config.env ${DIM}(already present in 0.5)${NC}"
    fi

    for item in \
        PLAYLISTS_GENERATED \
        COVERS \
        MIX_ARCHIVE \
        REPORTS \
        logs \
        LOGS \
        BACKUP_LOGS \
        VERIFY_LOGS \
        IMPORT_LOGS \
        SPEK_OUTPUTS \
        config_backups \
        exported_configs \
        themes \
        scripts/playlists \
        FLAC_CONVERTED_OUTPUTS \
        MP3_CONVERTED_OUTPUTS \
        WAV_CONVERTED_OUTPUTS \
        MP4_CONVERTED_OUTPUTS \
        CONVERTED_WAV_FILES; do
        [ -e "$src/$item" ] || continue
        if [ -d "$src/$item" ]; then
            copy_missing_tree "$src/$item" "$dst/$item"
        elif [ ! -e "$dst/$item" ]; then
            mkdir -p "$(dirname "$dst/$item")" 2>/dev/null || true
            cp "$src/$item" "$dst/$item" 2>/dev/null || true
        fi
        echo -e "  ${GREEN}✓${NC} $item"
        count=$((count + 1))
    done

    echo -e "  ${DIM}Existing 0.5 files were never overwritten; only missing files were added (${count} item(s) checked).${NC}"
}

# Point the user's commands at the 0.5 tree.
ensure_successor_launchers() {
    local dst="$1"
    mkdir -p "$HOME/.local/bin" 2>/dev/null || true
    if [ -f "$dst/bin/mix-archive-manager" ]; then
        ln -sfn "$dst/bin/mix-archive-manager" "$HOME/.local/bin/mix-archive-manager" 2>/dev/null || true
    fi
    ln -sfn "$dst/Mix_Archive_Manager.sh" "$HOME/.local/bin/manager" 2>/dev/null || true
    ln -sfn "$dst/Mix_Archive_Manager.sh" "$HOME/manager.sh" 2>/dev/null || true

    mkdir -p "$HOME/.config/mix-manager" 2>/dev/null || true
    printf '%s\n' "$dst" > "$HOME/.config/mix-manager/install_dir" 2>/dev/null || true
    if [ -f "$dst/scripts/lib/mp_install_dir.sh" ]; then
        mkdir -p "$HOME/.config/mix-manager/lib" 2>/dev/null || true
        cp -f "$dst/scripts/lib/mp_install_dir.sh" "$HOME/.config/mix-manager/lib/mp_install_dir.sh" 2>/dev/null || true
    fi
}

refresh_motd() {
    local dir="$1"
    if [ -x "$dir/scripts/update_system_motd.sh" ]; then
        "$dir/scripts/update_system_motd.sh" --apply >/dev/null 2>&1 || true
    elif [ -f "$dir/scripts/manage_motd.py" ]; then
        python3 "$dir/scripts/manage_motd.py" --apply >/dev/null 2>&1 || true
    elif [ -f "$dir/manage_motd.py" ]; then
        python3 "$dir/manage_motd.py" --apply >/dev/null 2>&1 || true
    fi
}

print_successor_summary() {
    local dst="$1" new_ver="$2"
    echo ""
    echo -e "${GREEN}======================================================================${NC}"
    echo -e "${BOLD}${GREEN}✓ MP Mix Manager 0.5 is installed: v${new_ver}${NC}"
    echo -e "${GREEN}======================================================================${NC}"
    echo -e "  New installation:  ${CYAN}${dst}${NC}"
    echo -e "  Your 0.4 tree:     ${DIM}${CODEBASE_DIR} (kept, unchanged)${NC}"
    echo -e "  Shared settings:   ${DIM}${HOME}/.config/mix-manager${NC}"
    echo ""
    echo -e "  Launch it with:    ${BOLD}${GREEN}manager${NC}"
    echo -e "  Or directly:       ${BOLD}${GREEN}${dst}/Mix_Archive_Manager.sh${NC}"
    echo -e "  Update it with:    ${BOLD}${GREEN}manager update${NC}"
    echo ""
    echo -e "  ${DIM}Converted audio and the archive folders were not moved or deleted."
    echo -e "  Keep the 0.4 folder until you are happy with 0.5; delete it whenever"
    echo -e "  you like. Its repository stays online for other 0.4 users.${NC}"
    echo -e "${BOLD}${MAGENTA}======================================================================${NC}"
}

# Run the 0.5 installer so symlinks, desktop entries and the tray are rebuilt.
run_successor_installer() {
    local dst="$1"
    if [ "$MP_UPGRADE_SKIP_INSTALL" = "1" ]; then
        echo -e "\n${DIM}Skipping the 0.5 installer (MP_UPGRADE_SKIP_INSTALL=1).${NC}"
        return 0
    fi
    if [ ! -f "$dst/install.sh" ]; then
        echo -e "\n${YELLOW}Notice: ${dst}/install.sh was not found; launchers were repointed manually.${NC}"
        ensure_successor_launchers "$dst"
        return 0
    fi
    echo -e "\n${BOLD}${BLUE}Running the 0.5 installer (launchers, desktop shortcuts, tray)...${NC}"
    if ( cd "$dst" && bash install.sh ); then
        echo -e "\n${GREEN}✓ The 0.5 installer completed.${NC}"
    else
        echo -e "\n${YELLOW}⚠ The 0.5 installer reported an error. The upgrade is still usable;${NC}"
        echo -e "${YELLOW}  launchers were repointed manually. You can re-run:${NC}"
        echo -e "  ${CYAN}cd ${dst} && ./install.sh${NC}"
    fi
    # install.sh writes these, but make sure they are correct even on failure.
    ensure_successor_launchers "$dst"
}

# Clone the published successor repository and hand the user over to it.
perform_successor_upgrade() {
    local target="" parent="" tmp="" branch="" new_ver="" existing_ok=0

    target="$(successor_target_dir)"
    parent="$(dirname "$target")"

    echo -e "\n${BOLD}${YELLOW}0.4 is end of life - upgrading to MP Mix Manager 0.5${NC}"
    echo -e "  Successor repository: ${CYAN}${MP_UPGRADE_REPO_URL}${NC}"
    echo -e "  New installation:     ${CYAN}${target}${NC}"

    if [ -e "$target" ]; then
        if successor_tree_valid "$target"; then
            existing_ok=1
        elif [ -d "$target" ] && [ -z "$(ls -A "$target" 2>/dev/null)" ]; then
            : # Empty directory; git clone can use it.
        else
            echo -e "\n${RED}Error: ${target} already exists and is not an MP Mix Manager 0.5 install.${NC}"
            echo -e "${YELLOW}Nothing was changed. Move or rename that directory, then run the update again.${NC}"
            return 1
        fi
    fi

    if [ "$existing_ok" -eq 1 ]; then
        echo -e "\n${BOLD}${GREEN}MP Mix Manager 0.5 is already installed at:${NC} ${CYAN}${target}${NC}"
        if [ "$FORCE_UPDATE" -eq 1 ]; then
            echo -e "${DIM}--force: refreshing that installation instead of cloning again.${NC}"
            migrate_user_data "$CODEBASE_DIR" "$target"
            run_successor_installer "$target"
            refresh_motd "$target"
            new_ver="$(head -n 1 "$target/VERSION" 2>/dev/null | tr -d '\r\n')"
            print_successor_summary "$target" "${new_ver:-0.5}"
            return 0
        fi
        echo -e "${DIM}Your commands already point at it. Run 'manager' to launch 0.5.${NC}"
        echo -e "${DIM}Use 'update --force' from this 0.4 tree to refresh its launchers and copy over any missing data.${NC}"
        return 0
    fi

    mkdir -p "$parent" 2>/dev/null || true

    # Clone into a temporary sibling so a failed download can never leave a
    # half-written install behind.
    tmp="${parent}/.${MP_UPGRADE_REPO_SLUG}.clone.$$"
    rm -rf "$tmp" 2>/dev/null || true

    echo -e "\n${BOLD}${BLUE}Downloading MP Mix Manager 0.5...${NC}"
    if [ -n "$SUCCESSOR_BRANCH" ]; then
        if ! GIT_TERMINAL_PROMPT=0 GIT_ASKPASS=/bin/echo \
                git clone --quiet --branch "$SUCCESSOR_BRANCH" "$MP_UPGRADE_REPO_URL" "$tmp"; then
            rm -rf "$tmp" 2>/dev/null || true
            echo -e "\n${RED}Error: could not clone ${MP_UPGRADE_REPO_URL}.${NC}"
            echo -e "${YELLOW}Your 0.4 installation was not changed.${NC}"
            return 1
        fi
    else
        if ! GIT_TERMINAL_PROMPT=0 GIT_ASKPASS=/bin/echo \
                git clone --quiet "$MP_UPGRADE_REPO_URL" "$tmp"; then
            rm -rf "$tmp" 2>/dev/null || true
            echo -e "\n${RED}Error: could not clone ${MP_UPGRADE_REPO_URL}.${NC}"
            echo -e "${YELLOW}Your 0.4 installation was not changed.${NC}"
            return 1
        fi
    fi

    if [ ! -f "$tmp/Mix_Archive_Manager.sh" ] || [ ! -f "$tmp/VERSION" ]; then
        rm -rf "$tmp" 2>/dev/null || true
        echo -e "\n${RED}Error: the downloaded tree does not look like MP Mix Manager 0.5.${NC}"
        echo -e "${YELLOW}Your 0.4 installation was not changed.${NC}"
        return 1
    fi
    new_ver="$(head -n 1 "$tmp/VERSION" 2>/dev/null | tr -d '\r\n')"
    if ! version_at_least "$(version_major_minor "$new_ver")" "$MP_UPGRADE_TARGET_MM"; then
        rm -rf "$tmp" 2>/dev/null || true
        echo -e "\n${RED}Error: the downloaded version is '${new_ver}', not 0.5 or newer.${NC}"
        echo -e "${YELLOW}Your 0.4 installation was not changed.${NC}"
        return 1
    fi

    if [ -d "$target" ]; then
        rmdir "$target" 2>/dev/null || true
    fi
    if ! mv "$tmp" "$target"; then
        rm -rf "$tmp" 2>/dev/null || true
        echo -e "\n${RED}Error: could not move the new installation into ${target}.${NC}"
        echo -e "${YELLOW}Your 0.4 installation was not changed.${NC}"
        return 1
    fi
    echo -e "  ${GREEN}✓${NC} Downloaded v${new_ver}"

    migrate_user_data "$CODEBASE_DIR" "$target"
    run_successor_installer "$target"
    refresh_motd "$target"
    print_successor_summary "$target" "$new_ver"
    return 0
}

# ------------------------------------------------------------------------------
# 4. End-of-life check (0.4 only; 0.5 and newer fall through to git pull)
# ------------------------------------------------------------------------------
if ! tree_is_successor && [ -n "$CURRENT_MM" ] && ! version_at_least "$CURRENT_MM" "$MP_UPGRADE_TARGET_MM"; then
    echo -e "${BOLD}${YELLOW}──────────────────────────────────────────────────────────────────────${NC}"
    echo -e "${BOLD}${YELLOW}0.4 is the final 0.4 release. MP Mix Manager 0.5 is the successor.${NC}"
    echo -e "${BOLD}${YELLOW}──────────────────────────────────────────────────────────────────────${NC}"

    probe_successor_remote

    if [ "$SUCCESSOR_REMOTE_STATE" != "available" ]; then
        if [ "$CHECK_ONLY" -eq 1 ]; then
            echo -e "\n${YELLOW}The 0.5 release is not published yet${NC} (${DIM}${MP_UPGRADE_REPO_URL}${NC})."
            echo -e "No successor upgrade is available right now."
            echo -e "${BOLD}${MAGENTA}======================================================================${NC}"
            exit 0
        fi
        if [ "$SUCCESSOR_REMOTE_STATE" = "unreachable" ]; then
            echo -e "\n${YELLOW}Notice: the 0.5 repository could not be reached.${NC}"
        else
            echo -e "\n${YELLOW}Notice: the 0.5 repository has no published branch yet.${NC}"
        fi
        echo -e "${DIM}Continuing with the normal 0.4 update so you still receive 0.4 fixes.${NC}"
    else
        echo -e "\n${BOLD}${GREEN}★ MP Mix Manager 0.5 is available${NC} ${DIM}(you are on v${CURRENT_VER})${NC}"
        echo -e "  Upgrade target: ${CYAN}$(successor_target_dir)${NC}"
        echo -e "  Your config, playlists, covers, reports and archive data are copied"
        echo -e "  into the new tree. The 0.4 folder is kept and never modified."

        if [ "$CHECK_ONLY" -eq 1 ]; then
            echo -e "\nRun '${BOLD}${GREEN}manager update${NC}' or '${BOLD}${GREEN}./Mix_Archive_Manager.sh update${NC}' to upgrade to 0.5."
            echo -e "${BOLD}${MAGENTA}======================================================================${NC}"
            exit 0
        fi

        perform_successor_upgrade
        exit $?
    fi
fi

if [ ! -d "$CODEBASE_DIR/.git" ] && ! git -C "$CODEBASE_DIR" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo -e "${YELLOW}Notice: ${CODEBASE_DIR} is not a git repository.${NC}"
    echo -e "MP Mix Archive Manager is running version: ${BOLD}${GREEN}v${CURRENT_VER}${NC}"
    exit 0
fi

cd "$CODEBASE_DIR"

CURRENT_COMMIT="$(git rev-parse --short HEAD 2>/dev/null || echo 'unknown')"
CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo 'main')"
echo -e "  Active Branch:             ${CYAN}${CURRENT_BRANCH}${NC} (${DIM}commit: ${CURRENT_COMMIT}${NC})"
echo -e "${BOLD}${BLUE}──────────────────────────────────────────────────────────────────────${NC}"

# ------------------------------------------------------------------------------
# 5. Fetch Updates from Remote
# ------------------------------------------------------------------------------
echo -e "Checking for updates from remote repository (${DIM}origin/${CURRENT_BRANCH}${NC})..."

FETCH_OK=1
if ! git fetch origin "$CURRENT_BRANCH" --quiet 2>/dev/null; then
    if ! git fetch origin "$CURRENT_BRANCH" 2>&1; then
        FETCH_OK=0
    fi
fi

if [ "$FETCH_OK" -eq 0 ]; then
    echo -e "\n${YELLOW}Notice: Unable to connect to remote repository (offline or remote unreachable).${NC}"
    echo -e "MP Mix Archive Manager is running version: ${BOLD}${GREEN}v${CURRENT_VER}${NC}"
    exit 0
fi

# Determine upstream commit
UPSTREAM="origin/$CURRENT_BRANCH"
if ! git rev-parse "$UPSTREAM" >/dev/null 2>&1; then
    UPSTREAM="origin/main"
fi

if ! git rev-parse "$UPSTREAM" >/dev/null 2>&1; then
    echo -e "\n${YELLOW}Notice: No remote tracking branch found for origin.${NC}"
    echo -e "MP Mix Archive Manager is running version: ${BOLD}${GREEN}v${CURRENT_VER}${NC}"
    exit 0
fi

BEHIND_COUNT=$(git rev-list --count HEAD.."$UPSTREAM" 2>/dev/null || echo 0)
AHEAD_COUNT=$(git rev-list --count "$UPSTREAM"..HEAD 2>/dev/null || echo 0)

# Check remote version string if available
REMOTE_VER=""
if git cat-file -e "${UPSTREAM}:VERSION" 2>/dev/null; then
    REMOTE_VER="$(git show "${UPSTREAM}:VERSION" 2>/dev/null | head -n 1 | tr -d '\r\n')"
fi
if [ -z "$REMOTE_VER" ] && git cat-file -e "${UPSTREAM}:CHANGELOG.md" 2>/dev/null; then
    REMOTE_VER="$(git show "${UPSTREAM}:CHANGELOG.md" 2>/dev/null | grep -E '^## \[[0-9]+\.[0-9]+' | head -1 | sed -E 's/.*\[([0-9]+\.[0-9]+\.[0-9]+)\].*/\1/' || true)"
fi

# ------------------------------------------------------------------------------
# 6. Up To Date Condition
# ------------------------------------------------------------------------------
if [ "$BEHIND_COUNT" -eq 0 ] && [ "$FORCE_UPDATE" -eq 0 ]; then
    echo -e "\n${BOLD}${GREEN}✓ MP Mix Archive Manager is running the latest version: v${CURRENT_VER}${NC}"
    if [ "$AHEAD_COUNT" -gt 0 ]; then
        echo -e "  ${DIM}(Local development branch is ahead of remote by ${AHEAD_COUNT} commit(s))${NC}"
    fi
    echo -e "${BOLD}${MAGENTA}======================================================================${NC}"
    exit 0
fi

# ------------------------------------------------------------------------------
# 7. Update Available
# ------------------------------------------------------------------------------
TARGET_VER="${REMOTE_VER:-latest}"
echo -e "\n${BOLD}${CYAN}★ A new version of MP Mix Archive Manager is available: v${TARGET_VER}${NC}"
echo -e "  Remote commits available: ${BOLD}${YELLOW}${BEHIND_COUNT}${NC}"
echo -e "\n${DIM}Incoming commits:${NC}"
git log --oneline -n "$BEHIND_COUNT" "$UPSTREAM"

if [ "$CHECK_ONLY" -eq 1 ]; then
    echo -e "\nRun '${BOLD}${GREEN}mix-archive-manager update${NC}' or '${BOLD}${GREEN}manager update${NC}' to install."
    echo -e "${BOLD}${MAGENTA}======================================================================${NC}"
    exit 0
fi

# ------------------------------------------------------------------------------
# 8. Install Update
# ------------------------------------------------------------------------------
echo -e "\n${BOLD}${BLUE}Installing the latest version...${NC}"

# Handle uncommitted local modifications safely
STASH_NEEDED=0
if [ -n "$(git status --porcelain 2>/dev/null)" ]; then
    echo -e "  ${DIM}Temporarily stashing local modifications...${NC}"
    git stash push -m "Auto-stashed before update on $(date '+%Y-%m-%d %H:%M:%S')" >/dev/null 2>&1 || true
    STASH_NEEDED=1
fi

UPDATE_SUCCESS=1
if git pull origin "$CURRENT_BRANCH" 2>&1; then
    echo -e "  ${GREEN}✓ Pulled latest changes from origin/${CURRENT_BRANCH}.${NC}"
else
    echo -e "  ${YELLOW}Fast-forward pull not possible; attempting rebase integration...${NC}"
    if git pull --rebase origin "$CURRENT_BRANCH" 2>&1; then
        echo -e "  ${GREEN}✓ Rebased cleanly onto origin/${CURRENT_BRANCH}.${NC}"
    else
        echo -e "\n${RED}Error: Git pull/rebase encountered merge conflicts.${NC}"
        echo -e "${YELLOW}Please inspect 'git status' in ${CODEBASE_DIR} and resolve conflicts.${NC}"
        UPDATE_SUCCESS=0
    fi
fi

if [ "$STASH_NEEDED" -eq 1 ]; then
    echo -e "  ${DIM}Restoring stashed local modifications...${NC}"
    git stash pop >/dev/null 2>&1 || true
fi

if [ "$UPDATE_SUCCESS" -eq 0 ]; then
    exit 1
fi

# Ensure executable permissions across all executables and scripts
chmod +x "$CODEBASE_DIR/Mix_Archive_Manager.sh" 2>/dev/null || true
chmod +x "$CODEBASE_DIR/bin/"* 2>/dev/null || true
chmod +x "$CODEBASE_DIR/scripts/"*.sh "$CODEBASE_DIR/scripts/"*.py 2>/dev/null || true

# Refresh user symlinks in ~/.local/bin and ~/manager.sh
mkdir -p "$HOME/.local/bin" 2>/dev/null || true
ln -sf "$CODEBASE_DIR/bin/mix-archive-manager" "$HOME/.local/bin/mix-archive-manager" 2>/dev/null || true
ln -sf "$CODEBASE_DIR/Mix_Archive_Manager.sh" "$HOME/.local/bin/manager" 2>/dev/null || true
ln -sf "$CODEBASE_DIR/bin/launch-manager-fullscreen" "$HOME/.local/bin/launch-manager-fullscreen" 2>/dev/null || true
ln -sf "$CODEBASE_DIR/Mix_Archive_Manager.sh" "$HOME/manager.sh" 2>/dev/null || true

# Refresh dynamic MOTD banner
refresh_motd "$CODEBASE_DIR"

NEW_VER="$(get_current_version)"
NEW_COMMIT="$(git rev-parse --short HEAD 2>/dev/null || echo 'unknown')"

echo -e "\n${GREEN}======================================================================${NC}"
echo -e "${BOLD}${GREEN}✓ MP Mix Archive Manager successfully updated to v${NEW_VER}!${NC}"
echo -e "  Installed Commit: ${CYAN}${NEW_COMMIT}${NC} (${DIM}$(git log -1 --format=%cd --date=short 2>/dev/null || echo '')${NC})"
echo -e "${GREEN}======================================================================${NC}"
