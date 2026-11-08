#!/bin/bash

# Script to generate spectrograms for audio files using various tools
# Usage: ./script.sh

# Dependencies
DEPS=("spek" "sox" "praat" "kwave" "sonic-visualiser")

# Colors
BOLD=$(tput bold)
CYAN=$(tput setaf 6)
MAGENTA=$(tput setaf 5)
RED=$(tput setaf 1)
YELLOW=$(tput setaf 3)
NC=$(tput sgr0)

# Directories
all_flac_dirs=(
    "$HOME/Documents/Audio/FLAC"
    "$HOME/Music/FLAC"
    "$PWD"
)
all_wav_dirs=(
    "$HOME/Documents/Audio/WAV"
    "$HOME/Music/WAV"
    "$PWD"
)
OUTPUT_DIR="$HOME/Documents/Spectrograms"

# Functions
generate_single_spek() {
    local input="$1"
    local output="$2"
    local overwrite="$3"
    local filename=$(basename "$input")
    local spekname="${filename%.flac}.png"
    local spekpath="$output/$spekname"

    if [ "$overwrite" -eq 0 ] && [ -f "$spekpath" ]; then
        echo -e "${YELLOW}Spectrogram already exists for $filename.${NC}"
        return
    fi

    spek "$input" -o "$spekpath" && echo -e "${GREEN}Generated spectrogram for $filename.${NC}"
}

generate_multiple_speks_in_place() {
    local dir="$1"
    for file in "$dir"/*.flac "$dir"/*.wav; do
        [ -f "$file" ] && generate_single_spek "$file" "$dir" 0
    done
}

generate_sox_spectrogram() {
    local input="$1"
    local output="$2"
    local cmap="$3"
    local filename=$(basename "$input")
    local spekname="${filename%.flac}.png"
    local spekpath="$output/$spekname"

    sox "$input" -n spectrogram -Y 140 -X 500 -m -o "$spekpath" -c "$cmap" && echo -e "${GREEN}Generated sox spectrogram for $filename.${NC}"
}

launch_native_spek_gui() {
    spek --gui "$@"
}

open_image_viewer() {
    xdg-open "$1"
}

launch_sonic_visualiser() {
    sonic-visualiser "$1"
}

launch_praat_or_kwave() {
    if command -v praat &>/dev/null; then
        praat "$1"
    elif command -v kwave &>/dev/null; then
        kwave "$1"
    fi
}

# Check dependencies
for dep in "${DEPS[@]}"; do
    if ! command -v "$dep" &>/dev/null; then
        echo -e "${RED}Error: $dep not found. Please install it.${NC}"
        exit 1
    fi
done

# Main menu
echo -e "\n${BOLD}${MAGENTA}=== AUDIO SPECTROGRAM GENERATOR ===${NC}\n"
echo -e "  ${CYAN}1)${NC} Generate spectrogram for single WAV/MP3/FLAC (in-place)"
echo -e "  ${CYAN}2)${NC} Generate spectrograms for multiple WAV/MP3/FLAC files (in-place)"
echo -e "  ${CYAN}3)${NC} Generate spectrogram for selected mix (with selection)"
echo -e "  ${CYAN}4)${NC} Batch generate spectrograms for all FLACs in archive"
echo -e "  ${CYAN}5)${NC} Batch generate spectrograms for all WAVs in archive"
echo -e "  ${CYAN}6)${NC} Generate spectrograms for all WAV/FLACs in current directory"
echo -e "  ${CYAN}7)${NC} Launch native Spek GUI"
echo -e "  ${CYAN}8)${NC} Open directory with generated spectrograms"
echo -e "  ${CYAN}9)${NC} Launch Sonic Visualiser for selected audio mix"
echo -e "  ${CYAN}10)${NC} Generate SoX spectrogram for selected audio mix"
echo -e "  ${CYAN}11)${NC} Launch Praat/KWave for selected audio mix"
echo -e "  ${CYAN}0)${NC} Exit\n"

read -r -p "Enter choice [0-11]: " choice

case "$choice" in
    1)
        read -e -r -p "Audio File Path: " raw_path
        s_path=$(realpath "$raw_path")
        [ -n "$s_path" ] && generate_single_spek "$s_path" "$OUTPUT_DIR" 1
        ;;
    2)
        read -e -r -p "Directory Path: " raw_dir
        s_dir=$(realpath "$raw_dir")
        [ -n "$s_dir" ] && generate_multiple_speks_in_place "$s_dir"
        ;;
    3)
        audio_list=()
        shopt -s nullglob nocaseglob
        for fd in "${all_flac_dirs[@]}"; do
            audio_list+=("$fd"/*.flac)
        done
        for wd in "${all_wav_dirs[@]}"; do
            audio_list+=("$wd"/*.wav)
        done
        audio_list+=("$PWD"/*.wav "$PWD"/*.flac)
        shopt -u nullglob nocaseglob

        if [ ${#audio_list[@]} -eq 0 ]; then
            read -r -p "Enter path to an audio file manually: " manual_file
            [ -f "$manual_file" ] && generate_single_spek "$manual_file" "$OUTPUT_DIR" 1
            exit 0
        fi

        echo -e "\n${BOLD}Choose selection method:${NC}"
        echo -e "  ${CYAN}1)${NC} Search for mix by keyword or episode number"
        echo -e "  ${CYAN}2)${NC} Select from list of recent mixes (${#audio_list[@]} available)"
        read -r -p "Enter selection [1-2]: " smode

        sel_file=""
        if [ "$smode" = "1" ]; then
            read -r -p "Enter search query: " query
            matched=()
            for a in "${audio_list[@]}"; do
                if [[ "$(basename "$a")" =~ $query ]]; then
                    matched+=("$a")
                fi
            done
            if [ ${#matched[@]} -eq 0 ]; then
                echo -e "${RED}No audio files matched '${query}'.${NC}"
                exit 1
            fi
            echo -e "\n${BOLD}Matching Mixes:${NC}"
            for i in "${!matched[@]}"; do
                echo -e "  ${CYAN}$((i + 1)))${NC} $(basename "${matched[$i]}")"
            done
            read -r -p "Select mix number [1-${#matched[@]}]: " pick
            [ "$pick" =~ ^[0-9]+$ ] && [ "$pick" -ge 1 ] && [ "$pick" -le "${#matched[@]}" ] && sel_file="${matched[$((pick - 1))]}"
        else
            echo -e "\n${BOLD}Recent Mixes in Archive:${NC}"
            for i in "${!audio_list[@]}"; do
                [ "$i" -ge 25 ] && break
                echo -e "  ${CYAN}$((i + 1)))${NC} $(basename "${audio_list[$i]}")"
            done
            read -r -p "Select mix number [1-${#audio_list[@]}]: " pick
            [ "$pick" =~ ^[0-9]+$ ] && [ "$pick" -ge 1 ] && [ "$pick" -le "${#audio_list[@]}" ] && sel_file="${audio_list[$((pick - 1))]}"
        fi

        [ -n "$sel_file" ] && [ -f "$sel_file" ] && generate_single_spek "$sel_file" "$OUTPUT_DIR" 1
        ;;
    4)
        echo -e "\n${BOLD}${CYAN}Batch generating spectrograms across FLAC archive location(s)...${NC}\n"
        for fd in "${all_flac_dirs[@]}"; do
            [ -d "$fd" ] && "$0" -d "$fd" -o "$OUTPUT_DIR"
        done
        ;;
    5)
        echo -e "\n${BOLD}${CYAN}Batch generating spectrograms across WAV archive location(s)...${NC}\n"
        for wd in "${all_wav_dirs[@]}"; do
            [ -d "$wd" ] && "$0" -d "$wd" -o "$OUTPUT_DIR"
        done
        ;;
    6)
        "$0" -d "$PWD" -o "$OUTPUT_DIR"
        ;;
    7)
        launch_native_spek_gui
        ;;
    8)
        open_image_viewer "$OUTPUT_DIR"
        ;;
    9)
        read -r -p "Enter path to audio mix: " sfile
        [ -z "$sfile" ] && sfile=$(find "$HOME/Music" -type f \( -iname "*.flac" -o -iname "*.wav" \) -print | shuf -n 1)
        launch_sonic_visualiser "$sfile"
        ;;
    10)
        read -r -p "Enter path to audio mix: " input
        [ -z "$input" ] && input=$(find "$HOME/Music" -type f \( -iname "*.flac" -o -iname "*.wav" \) -print | shuf -n 1)
        read -r -p "Enter color map (default: hot): " cmap
        [ -z "$cmap" ] && cmap="hot"
        generate_sox_spectrogram "$input" "$OUTPUT_DIR" "$cmap"
        ;;
    11)
        read -r -p "Enter path to audio mix: " input
        [ -z "$input" ] && input=$(find "$HOME/Music" -type f \( -iname "*.flac" -o -iname "*.wav" \) -print | shuf -n 1)
        launch_praat_or_kwave "$input"
        ;;
    0)
        exit 0
        ;;
    *)
        echo -e "${RED}Invalid choice. Exiting.${NC}"
        exit 1
        ;;
esac