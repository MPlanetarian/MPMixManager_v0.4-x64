    #!/bin/bash

    # ANSI Color Palette
    BOLD='\033[1m'
    DIM='\033[2m'
    ITALIC='\033[3m'
    UNDERLINE='\033[4m'
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[0;33m'
    BLUE='\033[0;34m'
    MAGENTA='\033[0;35m'
    CYAN='\033[0;36m'
    WHITE='\033[1;37m'
    NC='\033[0m'

TARGET_FILE="$1"
AUDIO_FILE="${2:-${MP_TRACKLIST_AUDIO_FILE:-}}"

SCRIPT_SOURCE="${BASH_SOURCE[0]}"
while [ -h "$SCRIPT_SOURCE" ]; do
    SCRIPT_DIR="$(cd -P "$(dirname "$SCRIPT_SOURCE")" && pwd)"
    SCRIPT_SOURCE="$(readlink "$SCRIPT_SOURCE")"
    [[ $SCRIPT_SOURCE != /* ]] && SCRIPT_SOURCE="$SCRIPT_DIR/$SCRIPT_SOURCE"
done
SCRIPT_DIR="$(cd -P "$(dirname "$SCRIPT_SOURCE")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
[ -f "$SCRIPT_DIR/MP_Audio_Player.py" ] && REPO_DIR="$SCRIPT_DIR"

if [ -z "$TARGET_FILE" ] || [ ! -f "$TARGET_FILE" ]; then
    clear
    echo -e "${RED}Error: Tracklist file not provided or does not exist!${NC}"
    echo -e "${DIM}Usage: $0 <path-to-tracklist.txt> [path-to-audio-file]${NC}"
    echo ""
    read -r -p "Press [Enter] to exit..."
    exit 1
fi

HOST_DESC="Linux"
if [ -f /etc/os-release ]; then
    HOST_DESC=$(grep -E '^PRETTY_NAME=' /etc/os-release | cut -d= -f2 | tr -d '"')
elif [ "$(uname -s)" = "Darwin" ]; then
    HOST_DESC="macOS $(sw_vers -productVersion 2>/dev/null)"
elif [ "$(uname -s)" = "FreeBSD" ]; then
    HOST_DESC="FreeBSD $(uname -r)"
fi

copy_tracklist_clipboard() {
    local text
    text=$(<"$TARGET_FILE")
    for cmd in wl-copy xclip pbcopy clip.exe; do
        if command -v "$cmd" >/dev/null 2>&1; then
            printf "%s" "$text" | "$cmd" 2>/dev/null
            return 0
        fi
    done
    return 1
}

edit_tracklist_vi() {
    if command -v vi >/dev/null 2>&1; then
        vi "$TARGET_FILE"
        return $?
    elif command -v vim >/dev/null 2>&1; then
        vim "$TARGET_FILE"
        return $?
    elif command -v nvim >/dev/null 2>&1; then
        nvim "$TARGET_FILE"
        return $?
    elif [ -n "${EDITOR:-}" ] && command -v "$EDITOR" >/dev/null 2>&1; then
        "$EDITOR" "$TARGET_FILE"
        return $?
    elif command -v nano >/dev/null 2>&1; then
        nano "$TARGET_FILE"
        return $?
    fi
    return 1
}

open_spek_image() {
    local img="$1"
    [ -z "$img" ] || [ ! -f "$img" ] && return 1
    local os_name
    os_name="$(uname -s)"
    if [ "$os_name" = "Darwin" ]; then
        open -a Preview "$img" >/dev/null 2>&1 &
        return 0
    fi
    for viewer in gwenview loupe eog feh xdg-open; do
        if command -v "$viewer" >/dev/null 2>&1; then
            "$viewer" "$img" >/dev/null 2>&1 &
            return 0
        fi
    done
    return 1
}

_load_archive_config() {
    if [ -z "${MIX_ARCHIVE_DIR:-}" ]; then
        local cfg
        for cfg in "$REPO_DIR/config.env" "$HOME/.config/mix-manager/config.env"; do
            if [ -f "$cfg" ]; then
                local val
                val=$(grep -E '^[[:space:]]*MIX_ARCHIVE_DIR=' "$cfg" 2>/dev/null | tail -n 1 | cut -d= -f2- | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' -e 's/^["'"'"']//' -e 's/["'"'"']$//')
                if [ -n "$val" ] && [ -d "$val" ]; then
                    MIX_ARCHIVE_DIR="$val"
                    break
                fi
            fi
        done
    fi
}

resolve_mix_audio_file() {
    if [ -n "$AUDIO_FILE" ] && [ -f "$AUDIO_FILE" ]; then
        echo "$AUDIO_FILE"
        return 0
    fi

    _load_archive_config

    local hdr_mix hdr_dir
    hdr_mix=$(grep -E '^Mix File:[[:space:]]+' "$TARGET_FILE" 2>/dev/null | head -n 1 | sed -E 's/^Mix File:[[:space:]]+//')
    hdr_dir=$(grep -E '^Directory:[[:space:]]+' "$TARGET_FILE" 2>/dev/null | head -n 1 | sed -E 's/^Directory:[[:space:]]+//')
    if [ -n "$hdr_mix" ] && [ -n "$hdr_dir" ] && [ -f "$hdr_dir/$hdr_mix" ]; then
        echo "$hdr_dir/$hdr_mix"
        return 0
    fi

    local tl_dir tl_base tl_stem
    tl_dir="$(cd "$(dirname "$TARGET_FILE")" 2>/dev/null && pwd || dirname "$TARGET_FILE")"
    tl_base="$(basename "$TARGET_FILE")"
    tl_stem="${tl_base%.*}"
    tl_stem="${tl_stem#Tracklist_}"

    local -a search_dirs=(
        "$tl_dir"
        "$(dirname "$tl_dir")"
        "$tl_dir/FLAC_CONVERTED_OUTPUTS"
        "$(dirname "$tl_dir")/FLAC_CONVERTED_OUTPUTS"
        "$(dirname "$tl_dir")/CONVERTED_WAV_FILES"
    )
    if [ -n "${MIX_ARCHIVE_DIR:-}" ]; then
        search_dirs+=(
            "${MIX_ARCHIVE_DIR%/}/FLAC_CONVERTED_OUTPUTS"
            "${MIX_ARCHIVE_DIR%/}/CONVERTED_WAV_FILES"
            "${MIX_ARCHIVE_DIR%/}"
        )
    fi
    search_dirs+=(
        "$REPO_DIR/MIX_ARCHIVE/FLAC_CONVERTED_OUTPUTS"
        "$REPO_DIR/FLAC_CONVERTED_OUTPUTS"
        "$REPO_DIR"
    )

    local d ext
    for d in "${search_dirs[@]}"; do
        [ -d "$d" ] || continue
        for ext in flac wav mp3 ogg m4a aiff FLAC WAV MP3; do
            if [ -f "$d/${tl_stem}.${ext}" ]; then
                echo "$d/${tl_stem}.${ext}"
                return 0
            fi
        done
    done

    local state_file="$HOME/.config/mix-manager/mp_player_state.json"
    if [ -f "$state_file" ]; then
        local st_path
        st_path=$(grep -o '"path":[[:space:]]*"[^"]*"' "$state_file" 2>/dev/null | head -n 1 | cut -d'"' -f4)
        if [ -n "$st_path" ] && [ -f "$st_path" ]; then
            echo "$st_path"
            return 0
        fi
    fi

    return 1
}

find_existing_spek_file() {
    local audio_ref="${1:-}"
    _load_archive_config

    local tl_base tl_stem clean_tl_stem
    tl_base="$(basename "$TARGET_FILE")"
    tl_stem="${tl_base%.*}"
    tl_stem="${tl_stem#Tracklist_}"
    clean_tl_stem=$(printf '%s' "$tl_stem" | sed 's/[\/\\:*?"<>|]/_/g')

    local -a stems=()
    local s
    if [ -n "$audio_ref" ]; then
        local aud_base aud_stem clean_aud_stem
        aud_base="$(basename "$audio_ref")"
        aud_stem="${aud_base%.*}"
        clean_aud_stem=$(printf '%s' "$aud_stem" | sed 's/[\/\\:*?"<>|]/_/g')
        stems+=("$clean_aud_stem" "$aud_stem")
    fi
    stems+=("$clean_tl_stem" "$tl_stem")

    local tl_dir
    tl_dir="$(cd "$(dirname "$TARGET_FILE")" 2>/dev/null && pwd || dirname "$TARGET_FILE")"
    local -a spek_dirs=()
    if [ -n "$audio_ref" ]; then
        local aud_dir
        aud_dir="$(cd "$(dirname "$audio_ref")" 2>/dev/null && pwd || dirname "$audio_ref")"
        spek_dirs+=("$aud_dir/SPEK_OUTPUTS" "$aud_dir" "$(dirname "$aud_dir")/SPEK_OUTPUTS")
    fi
    spek_dirs+=("$tl_dir/SPEK_OUTPUTS" "$tl_dir" "$(dirname "$tl_dir")/SPEK_OUTPUTS")
    [ -n "${SPEK_DIR:-}" ] && spek_dirs+=("$SPEK_DIR")
    if [ -n "${MIX_ARCHIVE_DIR:-}" ]; then
        spek_dirs+=("${MIX_ARCHIVE_DIR%/}/SPEK_OUTPUTS")
    fi
    spek_dirs+=("$REPO_DIR/SPEK_OUTPUTS" "$HOME/.config/mix-manager/SPEK_OUTPUTS")

    local d cand
    for d in "${spek_dirs[@]}"; do
        [ -n "$d" ] && [ -d "$d" ] || continue
        for s in "${stems[@]}"; do
            [ -n "$s" ] || continue
            for cand in "$d/${s}_spectrogram.png" "$d/${s}.spek.png" "$d/${s}.spek" "$d/${s}_spectrogram.jpg"; do
                if [ -s "$cand" ]; then
                    echo "$cand"
                    return 0
                fi
            done
        done
    done
    return 1
}

generate_or_open_spek() {
    local audio_target existing_spek
    audio_target="$(resolve_mix_audio_file 2>/dev/null || true)"
    existing_spek="$(find_existing_spek_file "$audio_target" 2>/dev/null || true)"

    if [ -n "$existing_spek" ] && [ -s "$existing_spek" ]; then
        open_spek_image "$existing_spek"
        render_tracklist
        echo -e "\n  ${BOLD}${GREEN}✓ Spek already exists! Opened: $(basename "$existing_spek")${NC}"
        return 0
    fi

    if [ -z "$audio_target" ] || [ ! -f "$audio_target" ]; then
        render_tracklist
        echo -e "\n  ${BOLD}${RED}✗ Audio file not found for tracklist to generate Spek.${NC}"
        return 1
    fi

    echo -e "\n  ${BOLD}${YELLOW}⚡ Generating Spek spectrogram for $(basename "$audio_target")...${NC}"

    local generated_spek=""
    if [ -f "$REPO_DIR/MP_Audio_Player.py" ] && command -v python3 >/dev/null 2>&1; then
        generated_spek=$(python3 - "$REPO_DIR/MP_Audio_Player.py" "$audio_target" << 'PY' 2>/dev/null || true
import importlib.util, sys
spec = importlib.util.spec_from_file_location("mp_player", sys.argv[1])
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
ok, res = mod.generate_track_spek(sys.argv[2])
if ok:
    print(res)
PY
)
    fi

    if [ -z "$generated_spek" ] || [ ! -s "$generated_spek" ]; then
        if command -v ffmpeg >/dev/null 2>&1; then
            _load_archive_config
            local out_dir="$REPO_DIR/SPEK_OUTPUTS"
            [ -n "${MIX_ARCHIVE_DIR:-}" ] && [ -d "${MIX_ARCHIVE_DIR}" ] && out_dir="${MIX_ARCHIVE_DIR%/}/SPEK_OUTPUTS"
            mkdir -p "$out_dir" 2>/dev/null || out_dir="$(dirname "$audio_target")"
            local aud_base aud_stem clean_stem
            aud_base="$(basename "$audio_target")"
            aud_stem="${aud_base%.*}"
            clean_stem=$(printf '%s' "$aud_stem" | sed 's/[\/\\:*?"<>|]/_/g')
            local target_png="$out_dir/${clean_stem}_spectrogram.png"
            if ffmpeg -y -i "$audio_target" -lavfi "showspectrumpic=s=1920x1080:mode=combined:color=intensity:scale=log" -update 1 -frames:v 1 "$target_png" >/dev/null 2>&1 && [ -s "$target_png" ]; then
                generated_spek="$target_png"
            fi
        fi
    fi

    if [ -n "$generated_spek" ] && [ -s "$generated_spek" ]; then
        open_spek_image "$generated_spek"
        render_tracklist
        echo -e "\n  ${BOLD}${GREEN}✓ Spek generated and opened: $(basename "$generated_spek")${NC}"
        return 0
    else
        render_tracklist
        echo -e "\n  ${BOLD}${RED}✗ Failed to generate Spek spectrogram.${NC}"
        return 1
    fi
}

extract_and_copy_mix_audio() {
    local audio_target
    audio_target="$(resolve_mix_audio_file 2>/dev/null || true)"

    if [ -z "$audio_target" ] || [ ! -f "$audio_target" ]; then
        render_tracklist
        echo -e "\n  ${BOLD}${RED}✗ Mix audio file not found for this tracklist.${NC}"
        return 1
    fi

    echo ""
    echo -e "  ${BOLD}${CYAN}📂 Mix Audio File:${NC} ${GREEN}$(basename "$audio_target")${NC}"
    echo -ne "  ${BOLD}${YELLOW}Enter destination path to extract and copy mix audio file to:${NC} "
    local dest_path=""
    if [ -t 0 ]; then
        read -e -r dest_path
    else
        read -r dest_path
    fi

    dest_path="$(printf '%s' "$dest_path" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' -e 's/^["'"'"']//' -e 's/["'"'"']$//')"
    if [ -z "$dest_path" ]; then
        render_tracklist
        echo -e "\n  ${YELLOW}Notice: Copy cancelled (no destination path entered).${NC}"
        return 1
    fi

    dest_path="${dest_path/#\~/$HOME}"

    local target_dest=""
    if [ -d "$dest_path" ] || [[ "$dest_path" == */ ]]; then
        mkdir -p "$dest_path" 2>/dev/null || {
            render_tracklist
            echo -e "\n  ${BOLD}${RED}✗ Failed to create destination directory: ${dest_path}${NC}"
            return 1
        }
        target_dest="${dest_path%/}/$(basename "$audio_target")"
    else
        local parent_dir
        parent_dir="$(dirname "$dest_path")"
        if [ -d "$parent_dir" ] && [[ "$(basename "$dest_path")" == *.* ]]; then
            target_dest="$dest_path"
        else
            mkdir -p "$dest_path" 2>/dev/null || {
                render_tracklist
                echo -e "\n  ${BOLD}${RED}✗ Failed to create destination directory: ${dest_path}${NC}"
                return 1
            }
            target_dest="${dest_path%/}/$(basename "$audio_target")"
        fi
    fi

    echo -e "  ${BOLD}${YELLOW}⚡ Copying $(basename "$audio_target") to ${target_dest}...${NC}"
    if cp -f "$audio_target" "$target_dest" 2>/dev/null; then
        render_tracklist
        echo -e "\n  ${BOLD}${GREEN}✓ Mix audio file extracted and copied to: ${target_dest}${NC}"
        return 0
    else
        render_tracklist
        echo -e "\n  ${BOLD}${RED}✗ Failed to copy mix audio file to: ${target_dest}${NC}"
        return 1
    fi
}

render_tracklist() {
    clear
    local filename=$(basename "$TARGET_FILE")
    local total_lines=$(wc -l < "$TARGET_FILE" 2>/dev/null || echo "0")
    local filesize=$(ls -lh "$TARGET_FILE" 2>/dev/null | awk '{print $5}')

    echo -e "${BOLD}${MAGENTA}========================================================================================${NC}"
    echo -e "${BOLD}${CYAN}            🎶 STREAM OF FREQUENCY • DEDICATED CONSOLE TRACKLIST VIEWER 🎶              ${NC}"
    echo -e "${BOLD}${MAGENTA}========================================================================================${NC}"
    echo -e "  • ${BOLD}File:${NC}        ${GREEN}${filename}${NC} ${DIM}(${filesize}, ${total_lines} lines)${NC}"
    echo -e "  • ${BOLD}Location:${NC}    ${DIM}$(dirname "$TARGET_FILE")${NC}"
    echo -e "  • ${BOLD}Platform:${NC}    ${YELLOW}${HOST_DESC}${NC} ${DIM}(Borderless Console Mode)${NC}"
    echo -e "${BOLD}${MAGENTA}────────────────────────────────────────────────────────────────────────────────────────${NC}\n"

    local in_tracklist=0
    local track_count=0

    while IFS= read -r line || [ -n "$line" ]; do
        if [[ "$line" =~ ^={10,}$ || "$line" =~ ^-{10,}$ ]]; then
            echo -e "${DIM}${line}${NC}"
        elif [[ "$line" =~ (RELEASE\ INFO|TRACKLIST|SOURCE\ MANIFEST|SOURCE\ FILES) ]]; then
            echo -e "${BOLD}${YELLOW}${line}${NC}"
        elif [[ "$line" =~ ^([A-Za-z0-9\ ]+):([[:space:]]+)(.*)$ ]]; then
            local key="${BASH_REMATCH[1]}"
            local val="${BASH_REMATCH[3]}"
            echo -e "  ${BOLD}${BLUE}${key}:${NC} ${WHITE}${val}${NC}"
        elif [[ "$line" =~ ^([0-9]{1,3})[\.\)][[:space:]]+(.*)$ ]]; then
            local num="${BASH_REMATCH[1]}"
            local rest="${BASH_REMATCH[2]}"
            ((track_count++))
            if [[ "$rest" =~ ^([^-]+)[[:space:]]-[[:space:]](.+)$ ]]; then
                local artist="${BASH_REMATCH[1]}"
                local title="${BASH_REMATCH[2]}"
                if [[ "$title" =~ (.*)(\([^\)]+\))(.*) ]]; then
                    local tmain="${BASH_REMATCH[1]}"
                    local remix="${BASH_REMATCH[2]}"
                    local tend="${BASH_REMATCH[3]}"
                    printf "  ${BOLD}${CYAN}%02d.${NC} ${WHITE}%s${NC} - ${GREEN}%s${NC}${YELLOW}%s${NC}%s\n" "$((10#$num))" "$artist" "$tmain" "$remix" "$tend"
                else
                    printf "  ${BOLD}${CYAN}%02d.${NC} ${WHITE}%s${NC} - ${GREEN}%s${NC}\n" "$((10#$num))" "$artist" "$title"
                fi
            else
                printf "  ${BOLD}${CYAN}%02d.${NC} ${WHITE}%s${NC}\n" "$((10#$num))" "$rest"
            fi
        elif [ -z "$line" ]; then
            echo ""
        else
            echo -e "  ${WHITE}${line}${NC}"
        fi
    done < "$TARGET_FILE"

    echo ""
    echo -e "${BOLD}${MAGENTA}========================================================================================${NC}"
    if [ "$track_count" -gt 0 ]; then
        echo -e "  ${BOLD}${GREEN}✓ Total Tracks Parsed:${NC} ${BOLD}${WHITE}${track_count}${NC}"
    fi
    echo -e "  ${BOLD}${CYAN}[Q]${NC} Close Window    ${BOLD}${CYAN}[C]${NC} Copy to Clipboard    ${BOLD}${CYAN}[S]${NC} Full Scroll Mode (less)    ${BOLD}${CYAN}[R]${NC} Reload"
    echo -e "  ${BOLD}${CYAN}[E]${NC} Edit Tracklist in VI    ${BOLD}${CYAN}[G]${NC} Generate & Open Spek    ${BOLD}${CYAN}[D]${NC} Extract & Copy Mix Audio"
    echo -e "${BOLD}${MAGENTA}========================================================================================${NC}"
}

render_tracklist

while true; do
    if [ -t 0 ]; then
        read -r -s -n 1 key
    elif ! read -r -s -n 1 key; then
        sleep 3600
        exit 0
    fi

    case "$key" in
        [qQ]|$'\e')
            exit 0
            ;;
        [cC])
            if copy_tracklist_clipboard; then
                render_tracklist
                echo -e "\n  ${BOLD}${GREEN}✓ Tracklist copied to system clipboard!${NC}"
            else
                echo -e "\n  ${YELLOW}Notice: No clipboard utility found.${NC}"
            fi
            ;;
        [rR])
            render_tracklist
            echo -e "\n  ${BOLD}${CYAN}✓ Tracklist reloaded from disk.${NC}"
            ;;
        [sS])
            if command -v less >/dev/null 2>&1; then
                less -RFX "$TARGET_FILE"
                render_tracklist
            fi
            ;;
        [eE])
            if edit_tracklist_vi; then
                render_tracklist
                echo -e "\n  ${BOLD}${GREEN}✓ Tracklist edited in VI and reloaded from disk.${NC}"
            else
                render_tracklist
                echo -e "\n  ${YELLOW}Notice: VI editor not found.${NC}"
            fi
            ;;
        [gG])
            generate_or_open_spek
            ;;
        [dD])
            extract_and_copy_mix_audio
            ;;
    esac
done