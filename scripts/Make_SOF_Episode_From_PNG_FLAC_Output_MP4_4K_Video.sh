#!/usr/bin/env bash
# ==============================================================================
# Make_SOF_Episode_From_PNG_FLAC_Output_MP4_4K_Video.sh
# Generates 4K UHD YouTube Video (3840x2160 @ 30fps) from FLAC/WAV Audio & Cover Image
# Hardware Accelerated (NVENC / VideoToolbox / libx264 fallback)
# Uses dynamic audio bitrate matched directly to the source audio file.
# ==============================================================================

set -euo pipefail

export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:$PATH"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'
BOLD='\033[1m'

AUDIO_FILE="${1:-}"
IMAGE_FILE="${2:-}"
OUTPUT_DIR="${3:-${MP4_OUTPUT_DIR:-MP4_CONVERTED_OUTPUTS}}"

if [ -z "$AUDIO_FILE" ]; then
    echo -e "${RED}Error: Audio file not specified!${NC}"
    echo "Usage: $0 <path_to_audio.flac|wav> [path_to_cover.png] [output_dir]"
    exit 1
fi

# Strip surrounding quotes
AUDIO_FILE="${AUDIO_FILE#\"}"; AUDIO_FILE="${AUDIO_FILE%\"}"
AUDIO_FILE="${AUDIO_FILE#\'}"; AUDIO_FILE="${AUDIO_FILE%\'}"
IMAGE_FILE="${IMAGE_FILE#\"}"; IMAGE_FILE="${IMAGE_FILE%\"}"
IMAGE_FILE="${IMAGE_FILE#\'}"; IMAGE_FILE="${IMAGE_FILE%\'}"
OUTPUT_DIR="${OUTPUT_DIR#\"}"; OUTPUT_DIR="${OUTPUT_DIR%\"}"
OUTPUT_DIR="${OUTPUT_DIR#\'}"; OUTPUT_DIR="${OUTPUT_DIR%\'}"

# Locate audio file
if [ ! -f "$AUDIO_FILE" ]; then
    found=0
    for candidate in \
        "FLAC_CONVERTED_OUTPUTS/$AUDIO_FILE" \
        "WAV_CONVERTED_OUTPUTS/$AUDIO_FILE" \
        "CONVERTED_WAV_FILES/$AUDIO_FILE" \
        "$AUDIO_FILE.flac" \
        "$AUDIO_FILE.wav" \
        "FLAC_CONVERTED_OUTPUTS/$AUDIO_FILE.flac" \
        "WAV_CONVERTED_OUTPUTS/$AUDIO_FILE.wav" \
        "$OUTPUT_DIR/$AUDIO_FILE" \
        "FLAC_CORRUPTED_FILES/$AUDIO_FILE"; do
        if [ -f "$candidate" ]; then
            AUDIO_FILE="$candidate"
            found=1
            break
        fi
    done
    if [ "$found" -eq 0 ]; then
        echo -e "${RED}Error: Audio file '$AUDIO_FILE' not found!${NC}"
        exit 1
    fi
fi

# Locate image file
[ -z "$IMAGE_FILE" ] && IMAGE_FILE="Cover.png"
if [ ! -f "$IMAGE_FILE" ]; then
    found_img=0
    for candidate in "COVERS/$IMAGE_FILE" "Cover.png" "assets/Cover.png"; do
        if [ -f "$candidate" ]; then
            [ "$candidate" = "Cover.png" ] && [ "$IMAGE_FILE" != "Cover.png" ] && \
                echo -e "${YELLOW}Warning: Cover file '$IMAGE_FILE' not found. Using default Cover.png.${NC}"
            IMAGE_FILE="$candidate"
            found_img=1
            break
        fi
    done
    if [ "$found_img" -eq 0 ]; then
        echo -e "${RED}Error: Cover image '$IMAGE_FILE' not found!${NC}"
        exit 1
    fi
fi

mkdir -p "$OUTPUT_DIR"
AUDIO_BASE="${AUDIO_FILE##*/}"
OUTPUT_FILE="$OUTPUT_DIR/${AUDIO_BASE%.*}_4K.mp4"

FPS=30
WIDTH=3840
HEIGHT=2160

# Single ffprobe call to retrieve audio duration and bitrate
AUDIO_DURATION=""
RAW_BITRATE=""
while IFS='=' read -r key val; do
    val="${val%$'\r'}"
    case "$key" in
        duration) [ -z "$AUDIO_DURATION" ] && [ "$val" != "N/A" ] && AUDIO_DURATION="$val" ;;
        bit_rate) [ -z "$RAW_BITRATE" ] && [ "$val" != "N/A" ] && [ "${val:-0}" -gt 0 ] 2>/dev/null && RAW_BITRATE="$val" ;;
    esac
done < <(ffprobe -v error -select_streams a:0 -show_entries stream=bit_rate -show_entries format=duration,bit_rate -of default=noprint_wrappers=1 "$AUDIO_FILE" 2>/dev/null || true)

if [ -z "$AUDIO_DURATION" ]; then
    echo -e "${RED}Error: Could not retrieve duration from $AUDIO_FILE${NC}"
    exit 1
fi

# Fallback bitrate calculation from file size and duration if ffprobe bit_rate is N/A
if [[ ! "${RAW_BITRATE:-}" =~ ^[0-9]+$ ]] || [ "${RAW_BITRATE:-0}" -le 0 ]; then
    FILE_BYTES=$(stat -c%s "$AUDIO_FILE" 2>/dev/null || stat -f%z "$AUDIO_FILE" 2>/dev/null || echo 0)
    RAW_BITRATE=$(awk -v b="$FILE_BYTES" -v d="$AUDIO_DURATION" 'BEGIN { if (d > 0 && b > 0) printf "%.0f", (b * 8) / d; else print 320000 }')
fi

AUDIO_KBPS=$(( RAW_BITRATE / 1000 ))
[ "$AUDIO_KBPS" -le 0 ] && AUDIO_KBPS=320
AUDIO_BITRATE="${AUDIO_KBPS}k"

FADE_OUT_START=$(awk -v d="$AUDIO_DURATION" 'BEGIN { s = int(d + 0.5) - 5; print (s < 0 ? 0 : s) }')

clear 2>/dev/null || true
echo -e "${BOLD}${BLUE}============================================================${NC}"
echo -e "${BOLD}${CYAN}          YOUTUBE 4K UHD VIDEO GENERATION (2160p)           ${NC}"
echo -e "${BOLD}${BLUE}============================================================${NC}"
echo -e "  Audio File:   ${GREEN}$AUDIO_FILE${NC}"
echo -e "  Cover Image:  ${GREEN}$IMAGE_FILE${NC}"
echo -e "  Output Video: ${GREEN}$OUTPUT_FILE${NC}"
echo -e "${BLUE}------------------------------------------------------------${NC}"
echo -e "Audio Duration: ${BOLD}${AUDIO_DURATION}s${NC}"
echo -e "Audio Bitrate:  ${BOLD}${AUDIO_KBPS} kbps${NC}"
echo -e "Resolution:     ${BOLD}${WIDTH}x${HEIGHT} (4K UHD @ ${FPS}fps)${NC}"

# Detect optimal Video Encoder
VCODEC="libx264"
VPRESET_ARGS=(-preset medium -crf 20)
if ffmpeg -f lavfi -i color=c=black:s=256x256 -frames:v 1 -c:v h264_nvenc -f null - >/dev/null 2>&1; then
    VCODEC="h264_nvenc"
    VPRESET_ARGS=(-preset p3 -cq 19 -g 60)
    echo -e "Video Encoder:  ${BOLD}${GREEN}h264_nvenc (NVIDIA NVENC Hardware Accelerated)${NC}"
elif [ "$(uname -s)" = "Darwin" ] && ffmpeg -f lavfi -i color=c=black:s=256x256 -frames:v 1 -c:v h264_videotoolbox -f null - >/dev/null 2>&1; then
    VCODEC="h264_videotoolbox"
    VPRESET_ARGS=(-b:v 14000k)
    echo -e "Video Encoder:  ${BOLD}${GREEN}h264_videotoolbox (Apple Silicon Hardware Accelerated)${NC}"
else
    echo -e "Video Encoder:  ${BOLD}${YELLOW}libx264 (CPU Software Encoder)${NC}"
fi

# Detect optimal Audio Encoder (avoid grep -q SIGPIPE under pipefail)
ACODEC="aac"
if [[ "$(ffmpeg -hide_banner -encoders 2>/dev/null || true)" == *"libfdk_aac"* ]]; then
    ACODEC="libfdk_aac"
    echo -e "Audio Codec:    ${BOLD}${GREEN}libfdk_aac @ ${AUDIO_KBPS} kbps (Pristine)${NC}"
else
    echo -e "Audio Codec:    ${BOLD}${YELLOW}native aac @ ${AUDIO_KBPS} kbps${NC}"
fi

echo -e "Transitions:    ${BOLD}5s fade-in, 5s fade-out${NC}"
echo -e "${BLUE}------------------------------------------------------------${NC}"
echo -e "${YELLOW}Rendering 4K UHD MP4 with FFmpeg... Please wait.${NC}\n"

STATUS=0
ffmpeg -y \
  -err_detect ignore_err \
  -loop 1 -framerate "$FPS" -t "$AUDIO_DURATION" -i "$IMAGE_FILE" \
  -i "$AUDIO_FILE" \
  -vf "scale=${WIDTH}:${HEIGHT}:force_original_aspect_ratio=decrease,pad=${WIDTH}:${HEIGHT}:(ow-iw)/2:(oh-ih)/2:black,fade=t=in:st=0:d=5:color=black,fade=t=out:st=${FADE_OUT_START}:d=5:color=black,format=yuv420p" \
  -c:v "$VCODEC" \
  "${VPRESET_ARGS[@]}" \
  -c:a "$ACODEC" \
  -b:a "$AUDIO_BITRATE" \
  -movflags +faststart \
  "$OUTPUT_FILE" || STATUS=$?

echo -e "\n${BLUE}------------------------------------------------------------${NC}"
if [ "$STATUS" -eq 0 ]; then
    echo -e "${BOLD}${GREEN}✓ Successfully generated 4K UHD video!${NC}"
    ls -lh "$OUTPUT_FILE"
else
    echo -e "${BOLD}${RED}✗ Video rendering failed with exit code $STATUS!${NC}"
fi
echo -e "${BOLD}${BLUE}============================================================${NC}"
exit "$STATUS"
