#!/usr/bin/env bash
# ==============================================================================
# MP_Mix_Manager_v0.3 - Universal Audio Format & Bit Depth Converter
# Converts WAV (and other audio) to MP3, Ogg Vorbis, Apple AAC/ALAC, Opus,
# FLAC, and WAV to WAV with custom bit depths (32-bit, 24-bit, 16-bit).
# ==============================================================================

#!/bin/bash

# Load configuration
source ~/audio_converter_config.conf

# Define variables
OPTS="$DEFAULT_OPTS"
EXT="$DEFAULT_EXT"
DEFAULT_OUT_DIR="$DEFAULT_OUT_DIR"
FMT_NAME="$DEFAULT_FMT_NAME"
SUB_DIR="$DEFAULT_SUB_DIR"

# Set default output directory
if [ -n "$DEFAULT_OUT_DIR" ]; then
    DEFAULT_OUT_DIR="$DEFAULT_OUT_DIR/$SUB_DIR"
fi

# Function to convert a file
convert_file() {
    local src="$1" dst="$2" format="$3" options="$4" ext="$5"
    local base="${src%.*}"
    local dst_file="${dst}/${base}.${ext}"

    mkdir -p "$dst" && ffmpeg -i "$src" $options -vn -c:a "$format" "$dst_file"
    if [ $? -eq 0 ]; then
        echo -e "${BOLD}${GREEN}✓ Converted ${src} to ${dst_file}${NC}"
        return 0
    else
        echo -e "${BOLD}${RED}✗ Failed to convert ${src}${NC}"
        return 1
    fi
}

# Function to get all files of a type in a directory
get_files() {
    local dir="$1" ext="$2"
    shopt -s nullglob nocaseglob
    local files=("$dir"/*."$ext")
    shopt -u nullglob nocaseglob
    echo "${files[@]}"
}

# Main menu
echo -e "\n${BOLD}${GREEN}=== AUDIO CONVERTER ===${NC}\n"
echo "Select conversion scope:"
echo "  1) Single file"
echo "  2) Batch convert current directory"
echo "  3) Batch convert all configured WAV/OGG archives"
echo "  4) Batch convert all configured FLAC archives"
read -r -p "Enter scope [1-4]: " scope

case "$scope" in
    1)
        read -r -e -p "Enter file name or partial file name (case-insensitive): " user_input
        shopt -s nullglob nocaseglob
        raw_candidates=()
        for wd in "${all_mix_archive_roots[@]}"; do
            [ -d "$wd" ] && raw_candidates+=("$wd"/*"$user_input"*.[wW][aA][vV] "$wd"/*"$user_input"*.[oO][gG][gG])
        done
        if [ -z "$user_input" ]; then
            raw_candidates+=(*.[wW][aA][vV] *.[oO][gG][gG])
        fi
        shopt -u nullglob nocaseglob

        candidates=()
        declare -A seen_candidates=()
        for cand in "${raw_candidates[@]}"; do
            [ -f "$cand" ] || continue
            real_c="$(cd "$(dirname "$cand")" 2>/dev/null && pwd -P)/$(basename "$cand")"
            if [ -z "${seen_candidates[$real_c]:-}" ]; then
                seen_candidates[$real_c]=1
                candidates+=("$cand")
            fi
        done

        if [ ${#candidates[@]} -eq 0 ]; then
            echo -e "${RED}No audio files found matching '$user_input' across configured archives!${NC}"
            exit 1
        elif [ ${#candidates[@]} -eq 1 ]; then
            target_file="${candidates[0]}"
            echo -e "\n${GREEN}Found:${NC} $target_file"
        else
            echo -e "\nMatching files found across archives:"
            for i in "${!candidates[@]}"; do
                echo "  $((i+1))) [$(basename "$(dirname "${candidates[$i]}")")] $(basename "${candidates[$i]}")"
            done
            read -r -p "Select file [1-${#candidates[@]}]: " pick
            if [[ "$pick" =~ ^[0-9]+$ ]] && [ "$pick" -ge 1 ] && [ "$pick" -le "${#candidates[@]}" ]; then
                target_file="${candidates[$((pick-1))]}"
            else
                echo -e "${RED}Invalid selection!${NC}"
                exit 1
            fi
        fi

        target_dir="$(dirname "$target_file")"
        target_real="$(cd "$target_dir" 2>/dev/null && pwd -P || echo "$target_dir")"
        target_archive_dir=""
        for arch_d in "${all_mix_archive_roots[@]}"; do
            arch_real="$(cd "$arch_d" 2>/dev/null && pwd -P || echo "$arch_d")"
            if [ "$target_real" = "$arch_real" ] || [[ "$target_real" == "$arch_real"/* ]]; then
                target_archive_dir="$arch_d"
                break
            fi
        done

        if [ -n "$target_archive_dir" ] && [ -d "$target_archive_dir" ]; then
            if [ "$EXT" = "mp3" ]; then
                DEFAULT_OUT_DIR="$target_archive_dir/MP3_CONVERTED_OUTPUTS"
            elif [ "$EXT" = "wav" ]; then
                DEFAULT_OUT_DIR="$target_archive_dir/WAV_CONVERTED_OUTPUTS"
            elif [ "$EXT" = "flac" ]; then
                DEFAULT_OUT_DIR="$target_archive_dir/FLAC_CONVERTED_OUTPUTS"
            else
                DEFAULT_OUT_DIR="$target_archive_dir/CONVERTED_AUDIO_OUTPUTS/$SUB_DIR"
            fi
        fi

        echo ""
        read -r -e -p "Enter output directory [default: $DEFAULT_OUT_DIR]: " custom_out
        final_out="${custom_out:-$DEFAULT_OUT_DIR}"

        echo -e "\n${BOLD}${GREEN}=== STARTING CONVERSION ===${NC}\n"
        convert_file "$target_file" "$FMT_NAME" "$final_out" "$OPTS" "$EXT"
        ;;
    2)
        wav_files=($(get_files . "wav") $(get_files . "ogg"))
        if [ ${#wav_files[@]} -eq 0 ]; then
            echo -e "${RED}No WAV or OGG files found in current directory!${NC}"
            exit 1
        fi
        echo -e "\nFound ${#wav_files[@]} audio file(s)."
        read -r -e -p "Enter output directory [default: $DEFAULT_OUT_DIR]: " custom_out
        final_out="${custom_out:-$DEFAULT_OUT_DIR}"

        echo -e "\n${BOLD}${GREEN}=== BATCH CONVERSION STARTED (${#wav_files[@]} files) ===${NC}\n"
        success=0
        for wf in "${wav_files[@]}"; do
            if convert_file "$wf" "$FMT_NAME" "$final_out" "$OPTS" "$EXT"; then
                ((success++))
            fi
        done
        echo -e "${BOLD}${GREEN}✓ Batch conversion completed: $success / ${#wav_files[@]} succeeded!${NC}\n"
        ;;
    3)
        wav_files=()
        for wd in "${all_wav_dirs[@]}"; do
            wav_files+=($(get_files "$wd" "wav") $(get_files "$wd" "ogg"))
        done
        if [ ${#wav_files[@]} -eq 0 ]; then
            echo -e "${RED}No WAV or OGG files found across configured WAV/OGG archives!${NC}"
            exit 1
        fi
        echo -e "\nFound ${#wav_files[@]} audio file(s) across ${#all_wav_dirs[@]} archive location(s)."
        read -r -e -p "Enter output directory [default: $DEFAULT_OUT_DIR]: " custom_out
        final_out="${custom_out:-$DEFAULT_OUT_DIR}"

        echo -e "\n${BOLD}${GREEN}=== BATCH CONVERSION STARTED (${#wav_files[@]} files) ===${NC}\n"
        success=0
        for wf in "${wav_files[@]}"; do
            if convert_file "$wf" "$FMT_NAME" "$final_out" "$OPTS" "$EXT"; then
                ((success++))
            fi
        done
        echo -e "${BOLD}${GREEN}✓ Batch conversion completed: $success / ${#wav_files[@]} succeeded!${NC}\n"
        ;;
    4)
        flac_files=()
        for fd in "${all_flac_dirs[@]}"; do
            flac_files+=($(get_files "$fd" "flac"))
        done
        if [ ${#flac_files[@]} -eq 0 ]; then
            echo -e "${RED}No FLAC files found across configured FLAC archives!${NC}"
            exit 1
        fi
        echo -e "\nFound ${#flac_files[@]} FLAC file(s) across ${#all_flac_dirs[@]} archive location(s)."
        read -r -e -p "Enter output directory [default: $DEFAULT_OUT_DIR]: " custom_out
        final_out="${custom_out:-$DEFAULT_OUT_DIR}"

        echo -e "\n${BOLD}${GREEN}=== BATCH CONVERSION STARTED (${#flac_files[@]} files) ===${NC}\n"
        success=0
        for ff in "${flac_files[@]}"; do
            if convert_file "$ff" "$FMT_NAME" "$final_out" "$OPTS" "$EXT"; then
                ((success++))
            fi
        done
        echo -e "${BOLD}${GREEN}✓ Batch conversion completed: $success / ${#flac_files[@]} succeeded!${NC}\n"
        ;;
    *)
        echo -e "${RED}Invalid scope selected!${NC}"
        exit 1
        ;;
esac