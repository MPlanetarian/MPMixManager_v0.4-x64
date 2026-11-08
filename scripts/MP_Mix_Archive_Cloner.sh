#!/usr/bin/env bash
# ==============================================================================
# MP_Mix_Archive_Cloner.sh - Full Mix Archive Folder Cloner, Backup & Exporter
# Part of MP_Mix_Manager_v0.3 (Dreamworlds Productions)
#
# Clones entire Mix Archive folders (preserving subfolders, FLAC/WAV/MP3/MP4
# outputs, tracklists, cover art, Spek spectrograms, and playlists) to a new
# destination full path provided by the user.
# ==============================================================================

set -u

BOLD='\033[1m'
DIM='\033[2m'
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
NC='\033[0m'

SCRIPT_SOURCE="${BASH_SOURCE[0]}"
while [ -h "$SCRIPT_SOURCE" ]; do
    SCRIPT_DIR="$(cd -P "$(dirname "$SCRIPT_SOURCE")" && pwd)"
    SCRIPT_SOURCE="$(readlink "$SCRIPT_SOURCE")"
    [[ $SCRIPT_SOURCE != /* ]] && SCRIPT_SOURCE="$SCRIPT_DIR/$SCRIPT_SOURCE"
done
SCRIPT_DIR="$(cd -P "$(dirname "$SCRIPT_SOURCE")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
[ -f "$SCRIPT_DIR/Mix_Archive_Manager.sh" ] && REPO_DIR="$SCRIPT_DIR"

load_config() {
    local pre_mix_dir="${MIX_ARCHIVE_DIR:-}"
    local pre_extra_dirs="${EXTRA_MIX_ARCHIVE_DIRS-__UNSET__}"
    local cfg
    for cfg in "${MP_CLONER_CONFIG_FILE:-}" "$REPO_DIR/config.env" "$HOME/.config/mix-manager/config.env"; do
        if [ -n "$cfg" ] && [ -f "$cfg" ]; then
            # shellcheck disable=SC1090
            source "$cfg" 2>/dev/null || true
            break
        fi
    done
    [ -n "$pre_mix_dir" ] && MIX_ARCHIVE_DIR="$pre_mix_dir"
    [ "$pre_extra_dirs" != "__UNSET__" ] && EXTRA_MIX_ARCHIVE_DIRS="$pre_extra_dirs"
}

discover_archive_folders() {
    load_config
    local -a dirs=()
    local -A seen=()

    add_dir() {
        local d="${1:-}"
        [ -z "$d" ] && return 0
        d="${d/#\~/$HOME}"
        d="${d//\\//}"
        [[ ! "$d" =~ ^[a-zA-Z]:/$ && "$d" != "/" ]] && d="${d%/}"
        if [ -d "$d" ]; then
            local resolved
            resolved="$(cd "$d" 2>/dev/null && pwd -P || printf '%s' "$d")"
            if [ -z "${seen[$resolved]:-}" ]; then
                seen["$resolved"]=1
                dirs+=("$resolved")
            fi
        fi
    }

    if [ -n "${MIX_ARCHIVE_DIR:-}" ]; then
        add_dir "$MIX_ARCHIVE_DIR"
    fi
    if [ "${MP_CLONER_SKIP_REPO_DEFAULT:-0}" != "1" ]; then
        add_dir "$REPO_DIR/MIX_ARCHIVE"
    fi

    local raw_extras="${EXTRA_MIX_ARCHIVE_DIRS-${MIX_ARCHIVE_DIRS:-}}"
    if [ -n "$raw_extras" ]; then
        local IFS_BACK="$IFS"
        IFS=';,'$'\n'
        for item in $raw_extras; do
            IFS="$IFS_BACK"
            item="$(printf '%s' "$item" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' -e 's/^["'"'"']//' -e 's/["'"'"']$//')"
            [ -n "$item" ] && add_dir "$item"
        done
        IFS="$IFS_BACK"
    fi

    if [ ${#dirs[@]} -gt 0 ]; then
        printf '%s\n' "${dirs[@]}"
    fi
}

validate_full_destination_path() {
    local raw_dest="${1:-}"
    raw_dest="$(printf '%s' "$raw_dest" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' -e 's/^["'"'"']//' -e 's/["'"'"']$//')"
    if [ -z "$raw_dest" ]; then
        echo -e "${RED}Error: Destination path is required.${NC}" >&2
        return 1
    fi

    raw_dest="${raw_dest/#\~/$HOME}"
    raw_dest="${raw_dest//\\//}"

    # Require a full (absolute) path: starts with / on Unix or Drive:/ on Windows
    if [[ ! "$raw_dest" =~ ^(/|[a-zA-Z]:/) ]]; then
        echo -e "${RED}Error: You must provide a full (absolute) destination path (e.g. /mnt/backup/Mix_Archive_Clone).${NC}" >&2
        return 1
    fi

    [[ ! "$raw_dest" =~ ^[a-zA-Z]:/$ && "$raw_dest" != "/" ]] && raw_dest="${raw_dest%/}"
    printf '%s\n' "$raw_dest"
    return 0
}

get_folder_stats() {
    local dir="$1"
    if [ ! -d "$dir" ]; then
        echo "0 files"
        return 0
    fi
    local file_count
    file_count=$(timeout 2s find "$dir" -maxdepth 3 -type f 2>/dev/null | wc -l | tr -d ' ')
    echo "${file_count:-0} files"
}

clone_single_archive_folder() {
    local src_dir="$1"
    local dest_root="$2"
    local preserve_folder_name="${3:-true}"
    local dry_run="${4:-false}"

    if [ ! -d "$src_dir" ]; then
        echo -e "${RED}✗ Source archive folder does not exist: ${src_dir}${NC}" >&2
        return 1
    fi

    local src_real
    src_real="$(cd "$src_dir" 2>/dev/null && pwd -P || printf '%s' "$src_dir")"

    local target_dir="$dest_root"
    if [ "$preserve_folder_name" = "true" ]; then
        target_dir="${dest_root%/}/$(basename "$src_real")"
    fi

    if [ "$dry_run" != "true" ]; then
        mkdir -p "$target_dir" 2>/dev/null || {
            echo -e "${RED}✗ Failed to create destination folder: ${target_dir}${NC}" >&2
            return 1
        }
    fi

    local target_real="$target_dir"
    if [ -d "$target_dir" ]; then
        target_real="$(cd "$target_dir" 2>/dev/null && pwd -P || printf '%s' "$target_dir")"
    fi

    if [ "$src_real" = "$target_real" ]; then
        echo -e "${RED}✗ Source and destination cannot be the same directory: ${src_real}${NC}" >&2
        return 1
    fi

    if [[ "$target_real" == "$src_real/"* ]]; then
        echo -e "${RED}✗ Destination path (${target_real}) cannot be inside the source archive folder (${src_real}).${NC}" >&2
        return 1
    fi

    echo -e "\n${BOLD}${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "  ${BOLD}Source Archive:${NC}      ${GREEN}${src_real}${NC} ${DIM}($(get_folder_stats "$src_real"))${NC}"
    echo -e "  ${BOLD}Clone Destination:${NC}   ${YELLOW}${target_dir}${NC}"
    echo -e "${BOLD}${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

    if [ "$dry_run" = "true" ]; then
        echo -e "  ${BOLD}${YELLOW}[DRY RUN] Would clone '${src_real}/' ➔ '${target_dir}/'${NC}"
        if command -v rsync >/dev/null 2>&1; then
            rsync -avhn "${src_real}/" "${target_dir}/"
        fi
        return 0
    fi

    if command -v rsync >/dev/null 2>&1; then
        echo -e "  ${BOLD}${YELLOW}⚡ Cloning archive folder via rsync...${NC}\n"
        if rsync -avh "${src_real}/" "${target_dir}/"; then
            echo -e "\n  ${BOLD}${GREEN}✓ Successfully cloned archive folder to: ${target_dir}${NC}"
            echo -e "  ${DIM}Cloned Inventory: $(get_folder_stats "$target_dir")${NC}"
            return 0
        else
            echo -e "\n  ${BOLD}${RED}✗ rsync encountered an error while cloning ${src_real}.${NC}" >&2
            return 1
        fi
    else
        echo -e "  ${BOLD}${YELLOW}⚡ Cloning archive folder via cp -a...${NC}\n"
        if cp -a "${src_real}/." "${target_dir}/"; then
            echo -e "\n  ${BOLD}${GREEN}✓ Successfully cloned archive folder to: ${target_dir}${NC}"
            echo -e "  ${DIM}Cloned Inventory: $(get_folder_stats "$target_dir")${NC}"
            return 0
        else
            echo -e "\n  ${BOLD}${RED}✗ cp encountered an error while cloning ${src_real}.${NC}" >&2
            return 1
        fi
    fi
}

show_usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS] [DESTINATION_FULL_PATH]

MP_Mix_Archive_Cloner - Clones entire Mix Archive folders to a new destination
full path for complete mix backup and export.

Options:
  -s, --source <PATH>       Source Mix Archive folder to clone (can be specified multiple times).
                            Defaults to all configured Mix Archive folders if --all is used,
                            or primary MIX_ARCHIVE_DIR.
  -d, --dest <FULL_PATH>    Full (absolute) destination path to clone into (Required in CLI mode).
  -a, --all                 Clone all configured Mix Archive folders into subdirectories of <FULL_PATH>.
      --flat                Clone source contents directly into <FULL_PATH> without creating a
                            parent folder named after the source archive (when cloning a single source).
  -n, --dry-run             Preview what would be cloned without copying files.
  -l, --list                List all discovered Mix Archive folders and exit.
  -y, --yes                 Skip interactive confirmation prompts.
  -h, --help                Show this help message.
EOF
}

run_interactive_cloner() {
    clear 2>/dev/null || true
    echo -e "${BOLD}${MAGENTA}====================================================================================${NC}"
    echo -e "${BOLD}${CYAN}            📦 MP MIX ARCHIVE CLONER • FULL ARCHIVE BACKUP & EXPORT 📦              ${NC}"
    echo -e "${BOLD}${MAGENTA}====================================================================================${NC}"
    echo -e "  Clone entire Mix Archive folders (FLAC/WAV/MP3/MP4 mixes, Tracklists, Cover Art,"
    echo -e "  Spek Spectrograms & Playlists) to a new destination full path.\n"

    local -a archives=()
    while IFS= read -r line; do
        [ -n "$line" ] && archives+=("$line")
    done < <(discover_archive_folders)

    echo -e "${BOLD}${BLUE}Discovered Mix Archive Folders:${NC}"
    if [ ${#archives[@]} -eq 0 ]; then
        echo -e "  ${YELLOW}No pre-configured Mix Archive folders found.${NC}"
    else
        local i
        for i in "${!archives[@]}"; do
            printf "  ${BOLD}${CYAN}%d)${NC} ${GREEN}%s${NC} ${DIM}(%s)${NC}\n" "$((i + 1))" "${archives[$i]}" "$(get_folder_stats "${archives[$i]}")"
        done
    fi
    echo ""
    echo -e "${BOLD}Select Source Archive(s) to Clone:${NC}"
    if [ ${#archives[@]} -gt 0 ]; then
        echo -e "  ${BOLD}${CYAN}A)${NC} Clone ${BOLD}ALL${NC} Discovered Mix Archive Folders (${#archives[@]} folder(s))"
        echo -e "  ${BOLD}${CYAN}1-${#archives[@]})${NC} Clone Specific Discovered Mix Archive Folder"
    fi
    echo -e "  ${BOLD}${CYAN}C)${NC} Enter Custom Source Mix Archive Folder Full Path"
    echo -e "  ${BOLD}${CYAN}Q)${NC} Cancel & Exit\n"

    local src_choice=""
    read -r -p "Enter selection [A/1-${#archives[@]}/C/Q]: " src_choice

    local -a selected_sources=()
    local preserve_subfolders="true"

    case "$src_choice" in
        [qQ]|"")
            echo -e "\n${YELLOW}Cancelled.${NC}"
            return 0
            ;;
        [aA])
            if [ ${#archives[@]} -eq 0 ]; then
                echo -e "\n${RED}No discovered archives available.${NC}"
                return 1
            fi
            selected_sources=("${archives[@]}")
            preserve_subfolders="true"
            ;;
        [cC])
            local custom_src=""
            echo ""
            read -e -r -p "Enter full path of source Mix Archive folder to clone: " custom_src
            custom_src="$(validate_full_destination_path "$custom_src")" || return 1
            if [ ! -d "$custom_src" ]; then
                echo -e "${RED}Error: Source folder does not exist: ${custom_src}${NC}" >&2
                return 1
            fi
            selected_sources=("$custom_src")
            preserve_subfolders="true"
            ;;
        *)
            if [[ "$src_choice" =~ ^[0-9]+$ ]] && (( src_choice >= 1 && src_choice <= ${#archives[@]} )); then
                selected_sources=("${archives[$((src_choice - 1))]}")
                preserve_subfolders="true"
            else
                echo -e "\n${RED}Invalid selection!${NC}" >&2
                return 1
            fi
            ;;
    esac

    echo ""
    echo -e "${BOLD}${YELLOW}Destination Full Path Requirement:${NC}"
    echo -e "  Please provide the ${BOLD}full (absolute) path${NC} where the Mix Archive folder(s) will be cloned"
    echo -e "  ${DIM}(e.g. /run/media/$USER/BackupDrive/MP_Mix_Backups or /mnt/storage/MIX_ARCHIVE_CLONE)${NC}"
    echo ""
    local raw_dest=""
    if [ -t 0 ]; then
        read -e -r -p "Enter full destination path: " raw_dest
    else
        read -r -p "Enter full destination path: " raw_dest
    fi

    local valid_dest=""
    valid_dest="$(validate_full_destination_path "$raw_dest")" || return 1

    local overall_rc=0
    local s
    for s in "${selected_sources[@]}"; do
        clone_single_archive_folder "$s" "$valid_dest" "$preserve_subfolders" "false" || overall_rc=1
    done

    echo ""
    if [ "$overall_rc" -eq 0 ]; then
        echo -e "${BOLD}${GREEN}====================================================================================${NC}"
        echo -e "${BOLD}${GREEN}  ✓ MIX ARCHIVE CLONE & BACKUP COMPLETED SUCCESSFULLY!                              ${NC}"
        echo -e "${BOLD}${GREEN}  Destination: ${valid_dest}${NC}"
        echo -e "${BOLD}${GREEN}====================================================================================${NC}"
    else
        echo -e "${BOLD}${RED}⚠️ Clone completed with one or more errors.${NC}" >&2
    fi
    return "$overall_rc"
}

main() {
    local -a cli_sources=()
    local dest_path=""
    local clone_all="false"
    local flat_mode="false"
    local dry_run="false"
    local list_only="false"

    while [ $# -gt 0 ]; do
        case "$1" in
            -s|--source)
                shift
                [ $# -gt 0 ] && cli_sources+=("$1")
                ;;
            -d|--dest|--destination)
                shift
                [ $# -gt 0 ] && dest_path="$1"
                ;;
            -a|--all)
                clone_all="true"
                ;;
            --flat)
                flat_mode="true"
                ;;
            -n|--dry-run)
                dry_run="true"
                ;;
            -l|--list)
                list_only="true"
                ;;
            -y|--yes)
                ;;
            -h|--help)
                show_usage
                exit 0
                ;;
            -*)
                echo -e "${RED}Unknown option: $1${NC}" >&2
                show_usage
                exit 1
                ;;
            *)
                if [ -z "$dest_path" ]; then
                    dest_path="$1"
                else
                    cli_sources+=("$1")
                fi
                ;;
        esac
        shift
    done

    if [ "$list_only" = "true" ]; then
        discover_archive_folders
        exit 0
    fi

    # If no destination was passed on CLI, launch interactive mode
    if [ -z "$dest_path" ] && [ ${#cli_sources[@]} -eq 0 ] && [ "$clone_all" = "false" ]; then
        run_interactive_cloner
        exit $?
    fi

    if [ -z "$dest_path" ]; then
        echo -e "${RED}Error: You must provide the full destination path (--dest /full/path).${NC}" >&2
        exit 1
    fi

    local valid_dest=""
    valid_dest="$(validate_full_destination_path "$dest_path")" || exit 1

    if [ ${#cli_sources[@]} -eq 0 ]; then
        if [ "$clone_all" = "true" ]; then
            while IFS= read -r line; do
                [ -n "$line" ] && cli_sources+=("$line")
            done < <(discover_archive_folders)
        else
            local first_arch=""
            first_arch="$(discover_archive_folders | head -n 1)"
            [ -n "$first_arch" ] && cli_sources+=("$first_arch")
        fi
    fi

    if [ ${#cli_sources[@]} -eq 0 ]; then
        echo -e "${RED}Error: No Mix Archive folders found to clone.${NC}" >&2
        exit 1
    fi

    local preserve_sub="true"
    if [ "$flat_mode" = "true" ] && [ ${#cli_sources[@]} -eq 1 ]; then
        preserve_sub="false"
    fi

    local rc=0
    local src
    for src in "${cli_sources[@]}"; do
        clone_single_archive_folder "$src" "$valid_dest" "$preserve_sub" "$dry_run" || rc=1
    done

    exit "$rc"
}

main "$@"
