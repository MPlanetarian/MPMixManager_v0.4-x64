#!/usr/bin/env bash
# ==============================================================================
# MP_Random_Hawking.sh - Stephen Hawking Random Quote Audio & Text Player
# ==============================================================================
# Plays a random pre-generated Stephen Hawking quote audio file (.wav) while
# displaying the full text of the quote in the terminal.
#
# Controls:
#   - [Enter] : Play another random Stephen Hawking quote (or skip current)
#   - [q]     : Stop playback and exit
# ==============================================================================

set -u

# Terminal Styling
BOLD="\033[1m"
DIM="\033[2m"
GREEN="\033[1;32m"
CYAN="\033[1;36m"
YELLOW="\033[1;33m"
MAGENTA="\033[1;35m"
RED="\033[1;31m"
WHITE="\033[1;37m"
RESET="\033[0m"

# Default Quotes Audio & Text Folder
PRIMARY_DIR="/run/media/mplanetarian/GAMES1/DATA_DRIVE_MOVED/WAN2GP_TTSBATCH/STEPHEN_HAWKING_100_QUOTES"
CONVERTED_DIR="${PRIMARY_DIR}/TTS_CONVERTED"

# Allow custom directory override via CLI arg or environment variable
if [[ -n "${1:-}" && -d "${1:-}" ]]; then
    if [[ -d "${1}/TTS_CONVERTED" ]]; then
        CONVERTED_DIR="${1}/TTS_CONVERTED"
    else
        CONVERTED_DIR="${1}"
    fi
elif [[ -n "${HAWKING_QUOTES_DIR:-}" && -d "${HAWKING_QUOTES_DIR}" ]]; then
    CONVERTED_DIR="${HAWKING_QUOTES_DIR}"
elif [[ ! -d "${CONVERTED_DIR}" && -d "${PRIMARY_DIR}" ]]; then
    CONVERTED_DIR="${PRIMARY_DIR}"
fi

AUDIO_PID=""

cleanup_player() {
    if [[ -n "${AUDIO_PID}" ]] && kill -0 "${AUDIO_PID}" 2>/dev/null; then
        kill -TERM "${AUDIO_PID}" 2>/dev/null || true
        wait "${AUDIO_PID}" 2>/dev/null || true
    fi
    AUDIO_PID=""
}

on_exit() {
    cleanup_player
    tput cnorm 2>/dev/null || true
    echo -e "\n${CYAN}Remember to look up at the stars and not down at your feet. Goodbye!${RESET}"
    exit 0
}

trap on_exit SIGINT SIGTERM

# Detect best available CLI audio player
detect_audio_player() {
    if command -v pw-play >/dev/null 2>&1; then
        echo "pw-play"
    elif command -v aplay >/dev/null 2>&1; then
        echo "aplay -q"
    elif command -v paplay >/dev/null 2>&1; then
        echo "paplay"
    elif command -v ffplay >/dev/null 2>&1; then
        echo "ffplay -nodisp -autoexit -loglevel quiet"
    elif command -v mpv >/dev/null 2>&1; then
        echo "mpv --no-video --really-quiet"
    elif command -v cvlc >/dev/null 2>&1; then
        echo "cvlc --play-and-exit --quiet"
    else
        echo ""
    fi
}

PLAYER_CMD="$(detect_audio_player)"
if [[ -z "${PLAYER_CMD}" ]]; then
    echo -e "${RED}[-] Error: No supported audio player found (pw-play, aplay, paplay, ffplay, mpv, cvlc).${RESET}"
    exit 1
fi

# Collect all generated .wav files
mapfile -t WAV_FILES < <(find "${CONVERTED_DIR}" -maxdepth 2 -type f -name "*.wav" | sort)
TOTAL_FILES="${#WAV_FILES[@]}"

if (( TOTAL_FILES == 0 )); then
    echo -e "${RED}[-] No Stephen Hawking quote .wav files found in:${RESET} ${CONVERTED_DIR}"
    exit 1
fi

LAST_IDX=-1
PLAY_COUNT=0

while true; do
    # Pick a random index (avoiding immediate repeat when >1 file exists)
    if (( TOTAL_FILES > 1 )); then
        while true; do
            RAND_IDX=$(( RANDOM % TOTAL_FILES ))
            [[ "${RAND_IDX}" -ne "${LAST_IDX}" ]] && break
        done
    else
        RAND_IDX=0
    fi
    LAST_IDX="${RAND_IDX}"
    PLAY_COUNT=$(( PLAY_COUNT + 1 ))

    SELECTED_WAV="${WAV_FILES[$RAND_IDX]}"
    SELECTED_TXT="${SELECTED_WAV%.wav}.txt"

    # Extract quote number if present in filename (e.g. Quote_042)
    QUOTE_NUM="$(( RAND_IDX + 1 ))"
    if [[ "${SELECTED_WAV}" =~ Quote_([0-9]+) ]]; then
        QUOTE_NUM="$(( 10#${BASH_REMATCH[1]} ))"
    fi

    # Read quote text
    if [[ -f "${SELECTED_TXT}" ]]; then
        QUOTE_TEXT="$(cat "${SELECTED_TXT}")"
    else
        QUOTE_TEXT="(Quote text file not found for $(basename "${SELECTED_WAV}"))"
    fi

    clear
    echo -e "${BOLD}${MAGENTA}══════════════════════════════════════════════════════════════════════════════${RESET}"
    echo -e "${BOLD}${CYAN}       🌌 STEPHEN HAWKING RANDOM QUOTE GENERATOR & PLAYER (WAN2GP TTS) 🌌     ${RESET}"
    echo -e "${BOLD}${MAGENTA}══════════════════════════════════════════════════════════════════════════════${RESET}"
    echo -e "  ${BOLD}Archive Folder:${RESET} ${DIM}${CONVERTED_DIR}${RESET}"
    echo -e "  ${BOLD}Loaded Quotes:${RESET}  ${GREEN}${TOTAL_FILES}${RESET} pre-generated audio files  |  ${BOLD}Session Played:${RESET} ${YELLOW}#${PLAY_COUNT}${RESET}"
    echo -e "  ${BOLD}Audio File:${RESET}     ${CYAN}$(basename "${SELECTED_WAV}")${RESET}"
    echo -e "${BOLD}${MAGENTA}──────────────────────────────────────────────────────────────────────────────${RESET}"
    echo -e ""
    echo -e "  ${BOLD}${YELLOW}Quote #${QUOTE_NUM}:${RESET}"
    echo -e ""
    # Word-wrap quote cleanly to 72 columns with indentation
    echo "${QUOTE_TEXT}" | fold -s -w 70 | sed -e 's/^/    "/' -e '1!s/^    "/     /' -e '$s/$/"/'
    echo -e ""
    echo -e "                                        ${BOLD}${CYAN}— Professor Stephen Hawking${RESET}"
    echo -e ""
    echo -e "${BOLD}${MAGENTA}──────────────────────────────────────────────────────────────────────────────${RESET}"
    echo -e "  ${GREEN}▶ Now Playing Stephen Hawking Voice...${RESET}"
    echo -e "  ${BOLD}[Enter]${RESET} Play another random quote   |   ${BOLD}[q]${RESET} Quit"
    echo -e "${BOLD}${MAGENTA}══════════════════════════════════════════════════════════════════════════════${RESET}"

    # Start playing audio in background
    # shellcheck disable=SC2086
    ${PLAYER_CMD} "${SELECTED_WAV}" >/dev/null 2>&1 &
    AUDIO_PID=$!

    # Wait for user input:
    # - Pressing 'q' or 'Q' immediately stops playback and exits
    # - Pressing Enter (empty key) plays another random quote right away
    USER_ACTION=""
    while true; do
        if read -r -s -n 1 -t 0.2 KEY; then
            if [[ "${KEY}" == "q" || "${KEY}" == "Q" ]]; then
                cleanup_player
                on_exit
            elif [[ -z "${KEY}" ]]; then
                # User pressed Enter -> break to play next random quote
                cleanup_player
                USER_ACTION="next"
                break
            fi
        else
            # Check if audio finished playing; if so, wait quietly for Enter or q
            if ! kill -0 "${AUDIO_PID}" 2>/dev/null; then
                break
            fi
        fi
    done

    if [[ "${USER_ACTION}" == "next" ]]; then
        continue
    fi

    echo -e "\n  ${DIM}[✓] Playback complete. Press [Enter] for another random quote, or [q] to exit...${RESET}"
    while true; do
        read -r -s -n 1 KEY
        if [[ "${KEY}" == "q" || "${KEY}" == "Q" ]]; then
            on_exit
        elif [[ -z "${KEY}" ]]; then
            break
        fi
    done
done
