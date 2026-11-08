#!/usr/bin/env bash
# ==============================================================================
# Script: Cut_Video.sh
# Purpose: Cut video clips (.mp4 and .mkv) based on start and end points in seconds,
#          save cut video in the same directory, and open a file manager window.
# ==============================================================================

#!/bin/bash

# Function to open file manager
open_file_manager() {
    local dir="$1"
    if command -v xdg-open &>/dev/null; then
        xdg-open "$dir"
    elif command -v explorer &>/dev/null; then
        explorer "$dir"
    elif command -v open &>/dev/null; then
        open "$dir"
    fi
}

# Constants
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

# Check FFmpeg installation
if ! command -v ffmpeg &>/dev/null || ! command -v ffprobe &>/dev/null; then
    echo -e "${RED}Error: FFmpeg and ffprobe are required but not installed!${NC}"
    exit 1
fi

# Input file
input_path="$1"
if [ -z "$input_path" ] || [ ! -f "$input_path" ]; then
    echo -e "${RED}Error: No input file provided or file does not exist!${NC}"
    exit 1
fi

# Get video info
video_info=$(ffprobe -v error -show_entries format=duration -show_entries stream=codec_type,codec_name,width,height -of default=noprint_wrappers=1 "$input_path" 2>/dev/null)

# Extract relevant info
video_duration=$(echo "$video_info" | grep -Eo '^duration=\K[0-9.]+')
video_codec=$(echo "$video_info" | grep -Eo 'codec_name=[^ ]+' | head -n1 | cut -d'=' -f2)
video_res=$(echo "$video_info" | grep -Eo 'width=\K[0-9]+' | head -n1 | xargs -I{} echo "{}x$(echo "$video_info" | grep -Eo 'height=\K[0-9]+' | head -n1)")

# Display video info
echo -e "${BOLD}Video Information:${NC}"
echo -e "  Input:       $input_path"
echo -e "  Codec:       $video_codec"
[ -n "$video_res" ] && echo -e "  Resolution:  $video_res"

if [ -n "$video_duration" ]; then
    dur_formatted=$(awk -v d="$video_duration" 'BEGIN {
        sec=int(d)
        h=int(sec/3600)
        m=int((sec%3600)/60)
        s=sec%60
        if (h > 0) printf "%02d:%02d:%02d (%.2f sec)", h, m, s, d
        else printf "%02d:%02d (%.2f sec)", m, s, d
    }')
    echo -e "  Duration:    $dur_formatted"
fi
echo ""

# Get start point
start_sec="$2"
while true; do
    if [ -z "$start_sec" ]; then
        read -r -p "Enter start point in seconds (e.g. 0 or 15.5): " start_sec
    fi
    start_sec=$(echo "$start_sec" | tr -d '[:space:]')
    if ! [[ "$start_sec" =~ ^[0-9]+([.][0-9]+)?$ ]] || ( [ -n "$video_duration" ] && awk -v s="$start_sec" -v d="$video_duration" 'BEGIN { exit !(s >= d) }' ); then
        echo -e "${RED}Error: Invalid start point.${NC}"
        start_sec=""
        [ -n "$2" ] && exit 1
        continue
    fi
    break
done

# Get end point
end_sec="$3"
while true; do
    if [ -z "$end_sec" ]; then
        read -r -p "Enter end point in seconds (e.g. 45 or 120): " end_sec
    fi
    end_sec=$(echo "$end_sec" | tr -d '[:space:]')
    if ! [[ "$end_sec" =~ ^[0-9]+([.][0-9]+)?$ ]] || awk -v s="$start_sec" -v e="$end_sec" 'BEGIN { exit !(e <= s) }'; then
        echo -e "${RED}Error: Invalid end point.${NC}"
        end_sec=""
        [ -n "$3" ] && exit 1
        continue
    fi
    if [ -n "$video_duration" ] && awk -v e="$end_sec" -v d="$video_duration" 'BEGIN { exit !(e > d) }'; then
        echo -e "${YELLOW}Notice: End point exceeds video duration. Clip will cut to the end of the video.${NC}"
    fi
    break
done

# Cutting mode
cut_mode="$4"
if [ -z "$cut_mode" ]; then
    echo -e "\n${BOLD}Cutting Mode:${NC}"
    echo -e "  ${BOLD}${CYAN}1)${NC} Fast Stream Copy (Instant, lossless, cuts on keyframes) ${GREEN}[Default]${NC}"
    echo -e "  ${BOLD}${CYAN}2)${NC} Frame-Accurate Re-encode (Exact frame cut, visually lossless CRF 18)"
    read -r -p "Select mode [1/2, default: 1]: " user_mode || true
    cut_mode="${user_mode:-1}"
fi

# Output path
video_dir=$(dirname "$input_path")
filename=$(basename "$input_path")
name_no_ext="${filename%.*}"
ext="${filename##*.}"

output_filename="${name_no_ext}_cut_${start_sec}s-${end_sec}s.${ext}"
output_path="${video_dir}/${output_filename}"

if [ -f "$output_path" ]; then
    seq=1
    while [ -f "${video_dir}/${name_no_ext}_cut_${start_sec}s-${end_sec}s_${seq}.${ext}" ]; do
        ((seq++))
    done
    output_path="${video_dir}/${name_no_ext}_cut_${start_sec}s-${end_sec}s_${seq}.${ext}"
    output_filename=$(basename "$output_path")
fi

echo -e "\n${BOLD}${BLUE}=== PROCESSING CUT ===${NC}"
echo -e "  Input:       $input_path"
echo -e "  Output:      $output_path"
echo -e "  Start Point: ${start_sec}s"
echo -e "  End Point:   ${end_sec}s"
cut_len=$(awk -v s="$start_sec" -v e="$end_sec" 'BEGIN { printf "%.2f", (e - s) }')
echo -e "  Length:      ~${cut_len}s"
if [ "$cut_mode" = "2" ]; then
    echo -e "  Mode:        Frame-Accurate Re-encode (libx264 veryfast CRF 18)"
else
    echo -e "  Mode:        Fast Stream Copy (lossless)"
fi
echo -e "${BLUE}--------------------------------------------------${NC}"

# Execute FFmpeg cut
if [ "$cut_mode" = "2" ]; then
    ffmpeg -y -hide_banner -loglevel warning -stats \
        -i "$input_path" \
        -ss "$start_sec" -to "$end_sec" \
        -c:v libx264 -preset veryfast -crf 18 -c:a copy \
        "$output_path"
    ffmpeg_status=$?
    if [ $ffmpeg_status -ne 0 ]; then
        ffmpeg -y -hide_banner -loglevel warning -stats \
            -i "$input_path" \
            -ss "$start_sec" -to "$end_sec" \
            -c:v libx264 -preset veryfast -crf 18 -c:a aac -b:a 320k \
            "$output_path"
        ffmpeg_status=$?
    fi
else
    ffmpeg -y -hide_banner -loglevel warning -stats \
        -i "$input_path" \
        -ss "$start_sec" -to "$end_sec" \
        -c copy -avoid_negative_ts make_zero -map 0 \
        "$output_path"
    ffmpeg_status=$?
    if [ $ffmpeg_status -ne 0 ]; then
        ffmpeg -y -hide_banner -loglevel warning -stats \
            -i "$input_path" \
            -ss "$start_sec" -to "$end_sec" \
            -c:v copy -c:a copy -avoid_negative_ts make_zero \
            "$output_path"
        ffmpeg_status=$?
    fi
fi

echo -e "${BLUE}--------------------------------------------------${NC}"

if [ $ffmpeg_status -eq 0 ] && [ -f "$output_path" ] && [ -s "$output_path" ]; then
    final_size=$(ls -lh "$output_path" 2>/dev/null | awk '{print $5}')
    final_dur=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$output_path" 2>/dev/null)
    echo -e "${BOLD}${GREEN}✓ Video successfully cut and saved!${NC}"
    echo -e "  Size:        $final_size"
    echo -e "  Duration:    $final_dur"
    open_file_manager "$video_dir"
else
    echo -e "${RED}Error: Failed to cut video.${NC}"
fi