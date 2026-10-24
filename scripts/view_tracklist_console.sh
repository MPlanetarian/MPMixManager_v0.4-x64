#!/bin/bash

CLI_THEME=""
POSITIONAL_ARGS=()
while [ $# -gt 0 ]; do
    case "$1" in
        --theme=*)
            CLI_THEME="${1#*=}"
            shift
            ;;
        --theme|-t)
            CLI_THEME="${2:-}"
            shift 2 2>/dev/null || shift
            ;;
        *)
            POSITIONAL_ARGS+=("$1")
            shift
            ;;
    esac
done

TARGET_FILE="${POSITIONAL_ARGS[0]:-}"
AUDIO_FILE="${POSITIONAL_ARGS[1]:-${MP_TRACKLIST_AUDIO_FILE:-}}"

TRACKLIST_THEMES=(
    "stream_of_frequency"
    "dreamworlds"
    "dreamworlds_ultra"
    "cosmic_supernova"
    "dreamworlds_liquid"
    "dynamic_rainbow_liquid_glass"
    "cosmic_dreamworlds_radioactive"
    "cosmic_dreamworlds"
    "orbital_void_reflux"
    "sensorium_interface"
    "cyberpunk"
    "dracula"
    "nord"
    "matrix"
    "solarized"
    "tokyo"
    "monokai"
    "gruvbox"
    "emerald"
    "classic"
    "retro_terminal"
)

set_theme_colors() {
    local raw_name="${1:-dreamworlds}"
    local theme_name
    theme_name="$(printf '%s' "$raw_name" | tr '[:upper:]' '[:lower:]' | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"

    BOLD='\033[1m'
    DIM='\033[2m'
    ITALIC='\033[3m'
    UNDERLINE='\033[4m'
    WHITE='\033[1;37m'
    NC='\033[0m'

    case "$theme_name" in
        stream_of_frequency|stream|frequency|sof|frequency_stream|"stream of frequency"|"stream-of-frequency"|"stream of frequency mp mix manager")
            RED='\033[38;2;240;32;24m'
            GREEN='\033[38;2;76;217;123m'
            YELLOW='\033[38;2;245;237;106m'
            BLUE='\033[38;2;48;49;131m'
            MAGENTA='\033[38;2;151;79;249m'
            CYAN='\033[38;2;0;242;255m'
            CURRENT_THEME="stream_of_frequency"
            THEME_DISPLAY_NAME="Stream of Frequency"
            ;;
        dreamworlds|mplanetarian_dreamworlds|mplanetarian|default|"mplanetarian dreamworlds [default]"|"mplanetarian dreamworlds")
            RED='\033[38;2;237;37;78m'
            GREEN='\033[38;2;0;229;255m'
            YELLOW='\033[38;2;255;170;0m'
            BLUE='\033[38;2;155;89;182m'
            MAGENTA='\033[38;2;247;37;133m'
            CYAN='\033[38;2;0;193;228m'
            CURRENT_THEME="dreamworlds"
            THEME_DISPLAY_NAME="MPlanetarian Dreamworlds"
            ;;
        dreamworlds_ultra|ultra|dreamworlds_ultra_mp_mix_manager|hotpurple|trafficlight|"dreamworlds ultra mp mix manager"|"dreamworlds ultra"|"dreamworlds-ultra")
            RED='\033[38;2;255;0;0m'
            GREEN='\033[38;2;0;255;0m'
            YELLOW='\033[38;2;255;153;51m'
            BLUE='\033[38;2;102;102;255m'
            MAGENTA='\033[38;2;166;77;255m'
            CYAN='\033[38;2;153;153;255m'
            CURRENT_THEME="dreamworlds_ultra"
            THEME_DISPLAY_NAME="Dreamworlds Ultra"
            ;;
        cosmic_supernova|supernova|cosmic|cosmic_supernova_mp_mix_manager|"cosmic supernova mp mix manager"|"cosmic supernova"|"cosmic-supernova"|"cosmic supernova [special]"|"cosmic supernova [special edition]")
            RED='\033[38;2;255;51;102m'
            GREEN='\033[38;2;0;245;212m'
            YELLOW='\033[38;2;254;228;64m'
            BLUE='\033[38;2;94;96;206m'
            MAGENTA='\033[38;2;224;86;253m'
            CYAN='\033[38;2;76;201;240m'
            CURRENT_THEME="cosmic_supernova"
            THEME_DISPLAY_NAME="Cosmic Supernova"
            ;;
        dreamworlds_liquid|mp_dreamworlds_liquid_transparency|dreamworlds_liquid_transparency|liquid_transparency|liquid|glass|liquid_glass|mp_liquid|"mp dreamworlds liquid transparency"|"mp dreamworlds liquid transparency [special edition]")
            RED='\033[38;2;255;75;130m'
            GREEN='\033[38;2;0;245;212m'
            YELLOW='\033[38;2;255;215;0m'
            BLUE='\033[38;2;72;149;239m'
            MAGENTA='\033[38;2;199;125;255m'
            CYAN='\033[38;2;0;245;255m'
            CURRENT_THEME="dreamworlds_liquid"
            THEME_DISPLAY_NAME="MP Dreamworlds Liquid Transparency"
            ;;
        dynamic_rainbow_liquid_glass|dynamic_liquid_glass_rainbow|dynamic_rainbow|rainbow_liquid_glass|rainbow|dynamic_liquid_glass|"dynamic_liquid_glass_[rainbow_colours]_(new)"|"dynamic_liquid_glass_[rainbow_colours]"|"dynamic liquid glass [rainbow colours] (new)"|"dynamic liquid glass [rainbow colours]"|"dynamic liquid glass")
            RED='\033[38;2;255;45;142m'
            GREEN='\033[38;2;0;242;254m'
            YELLOW='\033[38;2;255;215;0m'
            BLUE='\033[38;2;90;130;255m'
            MAGENTA='\033[38;2;176;88;255m'
            CYAN='\033[38;2;0;242;254m'
            CURRENT_THEME="dynamic_rainbow_liquid_glass"
            THEME_DISPLAY_NAME="Dynamic Liquid Glass [Rainbow Colours]"
            ;;
        cosmic_dreamworlds_radioactive|radioactive|cosmic_radioactive|"cosmic_dreamworlds_radioactive_(liquid_glass_skin)"|"cosmic dreamworlds radioactive (liquid glass skin)"|"cosmic dreamworlds radioactive")
            RED='\033[38;2;57;255;20m'
            GREEN='\033[38;2;0;245;212m'
            YELLOW='\033[38;2;255;215;0m'
            BLUE='\033[38;2;102;102;255m'
            MAGENTA='\033[38;2;166;77;255m'
            CYAN='\033[38;2;0;245;212m'
            CURRENT_THEME="cosmic_dreamworlds_radioactive"
            THEME_DISPLAY_NAME="Cosmic Dreamworlds Radioactive"
            ;;
        cosmic_dreamworlds|cosmic_dreamworld|cosmic_dream|"cosmic_dreamworlds_(liquid_glass_skin)"|"cosmic dreamworlds (liquid glass skin)"|"cosmic dreamworlds"|"cosmic dreamworld"|"cosmic dream")
            RED='\033[38;2;232;13;104m'
            GREEN='\033[38;2;0;245;212m'
            YELLOW='\033[38;2;254;228;64m'
            BLUE='\033[38;2;94;96;206m'
            MAGENTA='\033[38;2;176;88;255m'
            CYAN='\033[38;2;0;245;212m'
            CURRENT_THEME="cosmic_dreamworlds"
            THEME_DISPLAY_NAME="Cosmic Dreamworlds"
            ;;
        orbital_void_reflux|orbital_void|void_reflux|orbital|"orbital_void_reflux_(liquid_glass_skin)"|"orbital void reflux (liquid glass skin)"|"orbital void reflux")
            RED='\033[38;2;255;0;127m'
            GREEN='\033[38;2;0;240;255m'
            YELLOW='\033[38;2;157;78;221m'
            BLUE='\033[38;2;123;44;191m'
            MAGENTA='\033[38;2;157;78;221m'
            CYAN='\033[38;2;0;240;255m'
            CURRENT_THEME="orbital_void_reflux"
            THEME_DISPLAY_NAME="Orbital Void Reflux"
            ;;
        sensorium_interface|sensorium|"sensorium_interface_(liquid_glass_skin)"|"sensorium interface (liquid glass skin)"|"sensorium interface")
            RED='\033[38;2;240;168;216m'
            GREEN='\033[38;2;0;245;255m'
            YELLOW='\033[38;2;245;232;180m'
            BLUE='\033[38;2;184;72;196m'
            MAGENTA='\033[38;2;240;168;216m'
            CYAN='\033[38;2;0;245;255m'
            CURRENT_THEME="sensorium_interface"
            THEME_DISPLAY_NAME="Sensorium Interface"
            ;;
        dreamworlds_neon|"dreamworlds neon")
            RED='\033[38;2;247;37;133m'
            GREEN='\033[38;2;0;245;212m'
            YELLOW='\033[38;2;255;215;0m'
            BLUE='\033[38;2;114;9;183m'
            MAGENTA='\033[38;2;247;37;133m'
            CYAN='\033[38;2;0;245;212m'
            CURRENT_THEME="dreamworlds_neon"
            THEME_DISPLAY_NAME="Dreamworlds Neon"
            ;;
        retro_studio|"retro studio")
            RED='\033[38;2;231;76;60m'
            GREEN='\033[38;2;241;196;15m'
            YELLOW='\033[38;2;243;156;18m'
            BLUE='\033[38;2;211;84;0m'
            MAGENTA='\033[38;2;241;196;15m'
            CYAN='\033[38;2;230;126;34m'
            CURRENT_THEME="retro_studio"
            THEME_DISPLAY_NAME="Retro Studio"
            ;;
        cyber_neon|"cyber neon")
            RED='\033[38;2;255;0;85m'
            GREEN='\033[38;2;0;245;212m'
            YELLOW='\033[38;2;254;228;64m'
            BLUE='\033[38;2;58;134;255m'
            MAGENTA='\033[38;2;255;0;85m'
            CYAN='\033[38;2;76;201;240m'
            CURRENT_THEME="cyber_neon"
            THEME_DISPLAY_NAME="Cyber Neon"
            ;;
        phosphor)
            RED='\033[38;2;57;255;20m'
            GREEN='\033[38;2;57;255;20m'
            YELLOW='\033[38;2;166;255;0m'
            BLUE='\033[38;2;0;180;60m'
            MAGENTA='\033[38;2;57;255;20m'
            CYAN='\033[38;2;0;255;102m'
            WHITE='\033[38;2;212;255;212m'
            CURRENT_THEME="phosphor"
            THEME_DISPLAY_NAME="Phosphor"
            ;;
        ice_cold|"ice cold")
            RED='\033[38;2;191;97;106m'
            GREEN='\033[38;2;136;192;208m'
            YELLOW='\033[38;2;235;203;139m'
            BLUE='\033[38;2;94;129;172m'
            MAGENTA='\033[38;2;0;229;255m'
            CYAN='\033[38;2;129;161;193m'
            CURRENT_THEME="ice_cold"
            THEME_DISPLAY_NAME="Ice Cold"
            ;;
        retro_terminal|unix_terminal|retro_unix|old_style_unix|unix_retro|white_on_black|retro|terminal|vt100|"old style unix terminal retro mode (white on black)"|"old style unix terminal retro mode"|"old style unix terminal"|"retro terminal")
            RED='\033[1;37m'
            GREEN='\033[1;37m'
            YELLOW='\033[1;37m'
            BLUE='\033[0;37m'
            MAGENTA='\033[1;37m'
            CYAN='\033[1;37m'
            WHITE='\033[1;37m'
            CURRENT_THEME="retro_terminal"
            THEME_DISPLAY_NAME="Retro Terminal"
            ;;
        dracula)
            RED='\033[38;5;212m'
            GREEN='\033[38;5;84m'
            YELLOW='\033[38;5;228m'
            BLUE='\033[38;5;62m'
            MAGENTA='\033[38;5;141m'
            CYAN='\033[38;5;117m'
            CURRENT_THEME="dracula"
            THEME_DISPLAY_NAME="Dracula"
            ;;
        nord)
            RED='\033[38;5;167m'
            GREEN='\033[38;5;108m'
            YELLOW='\033[38;5;221m'
            BLUE='\033[38;5;110m'
            MAGENTA='\033[38;5;139m'
            CYAN='\033[38;5;117m'
            CURRENT_THEME="nord"
            THEME_DISPLAY_NAME="Nord"
            ;;
        matrix|"the matrix")
            RED='\033[38;5;124m'
            GREEN='\033[38;5;46m'
            YELLOW='\033[38;5;190m'
            BLUE='\033[38;5;29m'
            MAGENTA='\033[38;5;35m'
            CYAN='\033[38;5;120m'
            CURRENT_THEME="matrix"
            THEME_DISPLAY_NAME="The Matrix"
            ;;
        solarized|"solarized dark")
            RED='\033[38;5;166m'
            GREEN='\033[38;5;64m'
            YELLOW='\033[38;5;136m'
            BLUE='\033[38;5;33m'
            MAGENTA='\033[38;5;125m'
            CYAN='\033[38;5;37m'
            CURRENT_THEME="solarized"
            THEME_DISPLAY_NAME="Solarized"
            ;;
        tokyo|tokyo_night|tokyo-night|tokyonight|"tokyo night")
            RED='\033[38;5;203m'
            GREEN='\033[38;5;114m'
            YELLOW='\033[38;5;222m'
            BLUE='\033[38;5;111m'
            MAGENTA='\033[38;5;176m'
            CYAN='\033[38;5;73m'
            CURRENT_THEME="tokyo"
            THEME_DISPLAY_NAME="Tokyo Night"
            ;;
        monokai|"monokai pro")
            RED='\033[38;5;197m'
            GREEN='\033[38;5;148m'
            YELLOW='\033[38;5;220m'
            BLUE='\033[38;5;141m'
            MAGENTA='\033[38;5;208m'
            CYAN='\033[38;5;81m'
            CURRENT_THEME="monokai"
            THEME_DISPLAY_NAME="Monokai"
            ;;
        gruvbox|"gruvbox dark")
            RED='\033[38;5;167m'
            GREEN='\033[38;5;142m'
            YELLOW='\033[38;5;214m'
            BLUE='\033[38;5;109m'
            MAGENTA='\033[38;5;175m'
            CYAN='\033[38;5;108m'
            CURRENT_THEME="gruvbox"
            THEME_DISPLAY_NAME="Gruvbox"
            ;;
        emerald|emerald_isle|"emerald isle")
            RED='\033[38;5;204m'
            GREEN='\033[38;5;48m'
            YELLOW='\033[38;5;221m'
            BLUE='\033[38;5;31m'
            MAGENTA='\033[38;5;78m'
            CYAN='\033[38;5;86m'
            CURRENT_THEME="emerald"
            THEME_DISPLAY_NAME="Emerald Isle"
            ;;
        classic|"classic ansi"|monochrome|mono)
            RED='\033[0;31m'
            GREEN='\033[0;32m'
            YELLOW='\033[0;33m'
            BLUE='\033[0;34m'
            MAGENTA='\033[0;35m'
            CYAN='\033[0;36m'
            CURRENT_THEME="classic"
            THEME_DISPLAY_NAME="Classic ANSI"
            ;;
        cyberpunk|cyber|*)
            RED='\033[38;5;196m'
            GREEN='\033[38;5;48m'
            YELLOW='\033[38;5;226m'
            BLUE='\033[38;5;45m'
            MAGENTA='\033[38;5;198m'
            CYAN='\033[38;5;51m'
            CURRENT_THEME="cyberpunk"
            THEME_DISPLAY_NAME="Cyberpunk"
            ;;
    esac
}

_get_theme_file_path() {
    if [ -n "${MP_THEME_FILE:-}" ]; then
        echo "$MP_THEME_FILE"
    else
        echo "$HOME/.config/mix-manager/theme"
    fi
}

_read_saved_theme_file() {
    local tf
    tf="$(_get_theme_file_path)"
    if [ -f "$tf" ]; then
        tr -d '\r\n' < "$tf" 2>/dev/null | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//'
    fi
}

_STARTUP_ENV_THEME="${MP_TRACKLIST_THEME:-${CURRENT_THEME:-${MIX_MANAGER_THEME:-}}}"
_STARTUP_FILE_THEME="$(_read_saved_theme_file)"
_LAST_SEEN_FILE_THEME="$_STARTUP_FILE_THEME"
_USER_CYCLED_THEME=""

load_tracklist_theme() {
    local file_theme
    file_theme="$(_read_saved_theme_file)"
    local chosen_theme="dreamworlds"

    if [ -n "$file_theme" ] && [ "$file_theme" != "$_LAST_SEEN_FILE_THEME" ]; then
        _LAST_SEEN_FILE_THEME="$file_theme"
        _USER_CYCLED_THEME=""
        CLI_THEME=""
        _STARTUP_ENV_THEME=""
        chosen_theme="$file_theme"
    elif [ -n "$_USER_CYCLED_THEME" ]; then
        chosen_theme="$_USER_CYCLED_THEME"
    elif [ -n "$CLI_THEME" ]; then
        chosen_theme="$CLI_THEME"
    elif [ -n "$file_theme" ] && [ "$file_theme" != "$_STARTUP_FILE_THEME" ]; then
        chosen_theme="$file_theme"
    elif [ -n "$_STARTUP_ENV_THEME" ]; then
        chosen_theme="$_STARTUP_ENV_THEME"
    elif [ -n "$file_theme" ]; then
        chosen_theme="$file_theme"
    fi

    set_theme_colors "$chosen_theme"
}

cycle_tracklist_theme() {
    local count="${#TRACKLIST_THEMES[@]}"
    local idx=0
    local i
    for ((i = 0; i < count; i++)); do
        if [ "${TRACKLIST_THEMES[$i]}" = "${CURRENT_THEME:-dreamworlds}" ]; then
            idx=$(( (i + 1) % count ))
            break
        fi
    done
    local next_theme="${TRACKLIST_THEMES[$idx]}"
    _USER_CYCLED_THEME="$next_theme"
    local tf
    tf="$(_get_theme_file_path)"
    mkdir -p "$(dirname "$tf")" 2>/dev/null || true
    printf '%s\n' "$next_theme" > "$tf" 2>/dev/null || true
    _LAST_SEEN_FILE_THEME="$next_theme"
    set_theme_colors "$next_theme"
}

load_tracklist_theme

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
    load_tracklist_theme
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
    echo -e "  • ${BOLD}Theme:${NC}       ${MAGENTA}${THEME_DISPLAY_NAME}${NC} ${DIM}(${CURRENT_THEME})${NC}"
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
    echo -e "  ${BOLD}${CYAN}[E]${NC} Edit Tracklist in VI    ${BOLD}${CYAN}[G]${NC} Generate & Open Spek    ${BOLD}${CYAN}[D]${NC} Extract & Copy Mix Audio    ${BOLD}${CYAN}[T]${NC} Theme"
    echo -e "${BOLD}${MAGENTA}========================================================================================${NC}"
}

render_tracklist

while true; do
    if [ -t 0 ]; then
        key=""
        if ! read -r -s -n 1 -t 1 key; then
            _cur_file_th="$(_read_saved_theme_file)"
            if [ -n "$_cur_file_th" ] && [ "$_cur_file_th" != "$_LAST_SEEN_FILE_THEME" ]; then
                render_tracklist
            fi
            continue
        fi
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
        [tT])
            cycle_tracklist_theme
            render_tracklist
            echo -e "\n  ${BOLD}${GREEN}✓ Theme switched to: ${THEME_DISPLAY_NAME} (${CURRENT_THEME})${NC}"
            ;;
    esac
done