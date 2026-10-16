#!/usr/bin/env bash
# ==============================================================================
# Make_SOF_Episode_From_MP4_Audio_Output_MP4_1080p_Video.sh
# Generates YouTube Video (1080p Full HD @ 30fps default, also supports 4K / 720p)
# from an input MP4/MKV video and a FLAC/WAV audio soundtrack.
# Repeats the video seamlessly in segments with fade-in and fade-out to match
# the full duration of the audio, and adds optional Intro and Outro thumbnail cards.
# Hardware Accelerated (NVIDIA NVENC / Apple VideoToolbox / libx264 fallback).
# Uses dynamic audio bitrate matched directly to the source audio file.
# ==============================================================================

set -euo pipefail

export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:$PATH"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m'
BOLD='\033[1m'

ARG1="${1:-}"
ARG2="${2:-}"
ARG3="${3:-}"
ARG4="${4:-}"
RESOLUTION="${5:-1080p}"

# Smart parameter detection: identify which argument is audio vs video
detect_media_type() {
    local f="$1"
    [ -z "$f" ] && { echo "unknown"; return; }
    local ext="${f##*.}"
    case "${ext,,}" in
        wav|flac|aiff|aif|mp3|m4a|ogg|opus) echo "audio" ;;
        mp4|mkv|mov|avi|webm) echo "video" ;;
        png|jpg|jpeg|webp|ppm) echo "image" ;;
        *)
            if [ -f "$f" ]; then
                local streams
                streams=$(ffprobe -v error -show_entries stream=codec_type -of default=noprint_wrappers=1:nokey=1 "$f" 2>/dev/null || true)
                if [[ "$streams" == *"video"* ]] && [[ "$streams" != *"audio"* ]]; then
                    echo "video"
                elif [[ "$streams" == *"audio"* ]] && [[ "$streams" != *"video"* ]]; then
                    echo "audio"
                else
                    echo "unknown"
                fi
            else
                echo "unknown"
            fi
            ;;
    esac
}

t1=$(detect_media_type "$ARG1")
t2=$(detect_media_type "$ARG2")

if [ "$t1" = "video" ] && [ "$t2" = "audio" ]; then
    VIDEO_FILE="$ARG1"
    AUDIO_FILE="$ARG2"
elif [ "$t1" = "video" ] && [ "$t2" != "video" ]; then
    VIDEO_FILE="$ARG1"
    AUDIO_FILE="$ARG2"
else
    AUDIO_FILE="$ARG1"
    VIDEO_FILE="$ARG2"
fi

THUMB_FILE="$ARG3"
OUTPUT_TARGET="$ARG4"

# Interactive prompting if files missing
if [ -z "$AUDIO_FILE" ] || [ -z "$VIDEO_FILE" ]; then
    clear 2>/dev/null || true
    echo -e "${BOLD}${MAGENTA}======================================================================${NC}"
    echo -e "${BOLD}${MAGENTA}       YOUTUBE MP4-TO-MP4 VIDEO CREATOR (LOOPING & FADE SUITE)        ${NC}"
    echo -e "${BOLD}${MAGENTA}======================================================================${NC}\n"
    [ -z "$AUDIO_FILE" ] && read -r -p "Enter path to Audio file (.wav / .flac): " AUDIO_FILE
    [ -z "$VIDEO_FILE" ] && read -r -p "Enter path to Input Video file (.mp4 / .mkv): " VIDEO_FILE
    [ -z "$THUMB_FILE" ] && read -r -p "Enter path to Thumbnail/Cover image (optional): " THUMB_FILE
    [ -z "$OUTPUT_TARGET" ] && read -r -p "Enter output directory or file path (default: ${MP4_OUTPUT_DIR:-MP4_CONVERTED_OUTPUTS}): " OUTPUT_TARGET
fi

# Strip surrounding quotes via native bash parameter expansion
for var in AUDIO_FILE VIDEO_FILE THUMB_FILE OUTPUT_TARGET; do
    val="${!var}"
    val="${val#\"}"; val="${val%\"}"
    val="${val#\'}"; val="${val%\'}"
    printf -v "$var" '%s' "$val"
done

# Verify audio file
if [ ! -f "$AUDIO_FILE" ]; then
    for candidate in \
        "$AUDIO_FILE" \
        "${MP4_OUTPUT_DIR:-MP4_CONVERTED_OUTPUTS}/$AUDIO_FILE" \
        "FLAC_CONVERTED_OUTPUTS/$AUDIO_FILE" \
        "WAV_CONVERTED_OUTPUTS/$AUDIO_FILE" \
        "CONVERTED_WAV_FILES/$AUDIO_FILE" \
        "$AUDIO_FILE.wav" \
        "$AUDIO_FILE.flac" \
        "FLAC_CONVERTED_OUTPUTS/$AUDIO_FILE.flac" \
        "WAV_CONVERTED_OUTPUTS/$AUDIO_FILE.wav"; do
        if [ -f "$candidate" ]; then AUDIO_FILE="$candidate"; break; fi
    done
fi

if [ ! -f "$AUDIO_FILE" ]; then
    echo -e "${RED}Error: Audio file '$AUDIO_FILE' not found!${NC}"
    exit 1
fi

if [ ! -f "$VIDEO_FILE" ]; then
    echo -e "${RED}Error: Video file '$VIDEO_FILE' not found!${NC}"
    exit 1
fi

# Handle Thumbnail file
HAS_THUMB=0
for c in "$THUMB_FILE" "Cover.png" "assets/Cover.png" "COVERS/Cover.png"; do
    if [ -n "$c" ] && [ -f "$c" ]; then
        THUMB_FILE="$c"
        HAS_THUMB=1
        break
    fi
done

# Determine Resolution parameters
case "${RESOLUTION,,}" in
    4k|2160p|uhd)
        WIDTH=3840; HEIGHT=2160; RES_LABEL="4K UHD (2160p)"; RES_SUFFIX="_4K"
        CRF=19; CQ=18; BITRATE_V="18000k"
        ;;
    720p|hd)
        WIDTH=1280; HEIGHT=720; RES_LABEL="720p HD"; RES_SUFFIX="_720p"
        CRF=22; CQ=22; BITRATE_V="3500k"
        ;;
    *)
        WIDTH=1920; HEIGHT=1080; RES_LABEL="1080p Full HD"; RES_SUFFIX=""
        CRF=21; CQ=20; BITRATE_V="7500k"
        ;;
esac

# Output path calculation
AUDIO_BASE="${AUDIO_FILE##*/}"
OUTPUT_NAME="${AUDIO_BASE%.*}${RES_SUFFIX}.mp4"

if [ -z "$OUTPUT_TARGET" ]; then
    OUTPUT_DIR="${MP4_OUTPUT_DIR:-MP4_CONVERTED_OUTPUTS}"
    OUTPUT_FILE="$OUTPUT_DIR/$OUTPUT_NAME"
elif [[ "$OUTPUT_TARGET" == *.mp4 ]] || [[ "$OUTPUT_TARGET" == *.mkv ]]; then
    OUTPUT_FILE="$OUTPUT_TARGET"
    OUTPUT_DIR=$(dirname "$OUTPUT_FILE")
else
    OUTPUT_DIR="$OUTPUT_TARGET"
    OUTPUT_FILE="$OUTPUT_DIR/$OUTPUT_NAME"
fi
mkdir -p "$OUTPUT_DIR"

# Retrieve audio duration and bitrate in a single ffprobe pass
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
    echo -e "${RED}Error: Could not retrieve audio duration from $AUDIO_FILE${NC}"
    exit 1
fi

if [[ ! "${RAW_BITRATE:-}" =~ ^[0-9]+$ ]] || [ "${RAW_BITRATE:-0}" -le 0 ]; then
    FILE_BYTES=$(stat -c%s "$AUDIO_FILE" 2>/dev/null || stat -f%z "$AUDIO_FILE" 2>/dev/null || echo 0)
    RAW_BITRATE=$(awk -v b="$FILE_BYTES" -v d="$AUDIO_DURATION" 'BEGIN { if (d > 0 && b > 0) printf "%.0f", (b * 8) / d; else print 320000 }')
fi

AUDIO_KBPS=$(( RAW_BITRATE / 1000 ))
[ "$AUDIO_KBPS" -le 0 ] && AUDIO_KBPS=320
AUDIO_BITRATE="${AUDIO_KBPS}k"

# Retrieve video duration in a single ffprobe pass
VIDEO_DURATION=""
while IFS= read -r val; do
    val="${val%$'\r'}"
    if [ -n "$val" ] && [ "$val" != "N/A" ]; then
        VIDEO_DURATION="$val"
        break
    fi
done < <(ffprobe -v error -select_streams v:0 -show_entries stream=duration -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$VIDEO_FILE" 2>/dev/null || true)

if [ -z "$VIDEO_DURATION" ]; then
    echo -e "${RED}Error: Could not retrieve video duration from $VIDEO_FILE${NC}"
    exit 1
fi

# Detect optimal Video Encoder
VCODEC="libx264"
VPRESET_ARGS=(-preset medium -crf "$CRF")
if ffmpeg -f lavfi -i color=c=black:s=256x256 -frames:v 1 -c:v h264_nvenc -f null - >/dev/null 2>&1; then
    VCODEC="h264_nvenc"
    VPRESET_ARGS=(-preset p3 -cq "$CQ" -g 60)
    ENCODER_STR="h264_nvenc (NVIDIA NVENC Hardware Accelerated)"
elif [ "$(uname -s)" = "Darwin" ] && ffmpeg -f lavfi -i color=c=black:s=256x256 -frames:v 1 -c:v h264_videotoolbox -f null - >/dev/null 2>&1; then
    VCODEC="h264_videotoolbox"
    VPRESET_ARGS=(-b:v "$BITRATE_V")
    ENCODER_STR="h264_videotoolbox (Apple Silicon Hardware Accelerated)"
else
    ENCODER_STR="libx264 (CPU Software Encoder)"
fi

# Detect optimal Audio Encoder (avoid grep -q SIGPIPE under pipefail)
ACODEC="aac"
if [[ "$(ffmpeg -hide_banner -encoders 2>/dev/null || true)" == *"libfdk_aac"* ]]; then
    ACODEC="libfdk_aac"
    ACODEC_STR="libfdk_aac @ ${AUDIO_KBPS} kbps (Pristine)"
else
    ACODEC_STR="native aac @ ${AUDIO_KBPS} kbps"
fi

INTRO_SEC=5.0
OUTRO_SEC=5.0
SEG_FADE_DUR=1.5
AUDIO_FADE_DUR=5.0

# Calculate all segment timings and fade offsets in a single awk invocation
PLAN_OUTPUT=$(awk \
    -v ad="$AUDIO_DURATION" \
    -v vd="$VIDEO_DURATION" \
    -v ht="$HAS_THUMB" \
    -v isec="$INTRO_SEC" \
    -v osec="$OUTRO_SEC" \
    -v fd="$SEG_FADE_DUR" \
    -v afd="$AUDIO_FADE_DUR" \
    'BEGIN {
        intro = (ht == 1) ? isec : 0.0
        outro = (ht == 1) ? osec : 0.0
        if (ht == 1 && ad <= (intro + outro + 2.0)) {
            intro = (ad * 0.15 > 1.0) ? ad * 0.15 : 1.0
            outro = intro
        }
        mid = ad - intro - outro
        if (mid < 0.0) mid = 0.0

        if (mid <= 0.0) {
            nfull = 0; rem = 0.0
        } else if (vd >= mid) {
            nfull = 0; rem = mid
        } else {
            nfull = int(mid / vd)
            rem = mid - (nfull * vd)
        }

        do_intro = (ht == 1 && intro > 0.1) ? 1 : 0
        do_rem   = (rem > 0.05) ? 1 : 0
        do_outro = (ht == 1 && outro > 0.1) ? 1 : 0

        intro_fo = (intro - fd > 0.0) ? intro - fd : 0.0
        seg_fo   = (vd - fd > 0.0) ? vd - fd : 0.0
        rem_fd   = (fd < rem / 3.0) ? fd : rem / 3.0
        rem_fo   = (rem - rem_fd > 0.0) ? rem - rem_fd : 0.0
        outro_fo = (outro - fd > 0.0) ? outro - fd : 0.0
        aud_fo   = (ad - afd > 0.0) ? ad - afd : 0.0

        printf "%.6f|%.6f|%.6f|%d|%.6f|%.6f|%d|%d|%d|%.6f|%.6f|%.6f|%.6f|%.6f|%.6f\n",
            intro, outro, mid, nfull, rem, fd,
            do_intro, do_rem, do_outro,
            intro_fo, seg_fo, rem_fd, rem_fo, outro_fo, aud_fo
    }')

IFS='|' read -r CALC_INTRO CALC_OUTRO CALC_MID NUM_FULL REM_DUR CALC_FADE \
    DO_INTRO DO_REM DO_OUTRO \
    INTRO_FADE_OUT SEG_FADE_OUT REM_FADE_DUR REM_FADE_OUT OUTRO_FADE_OUT AUDIO_FADE_OUT_START <<< "$PLAN_OUTPUT"

echo -e "\n${BOLD}${BLUE}============================================================${NC}"
echo -e "${BOLD}${CYAN}      YOUTUBE MP4-TO-MP4 VIDEO GENERATION - ${RES_LABEL}     ${NC}"
echo -e "${BOLD}${BLUE}============================================================${NC}"
echo -e "  Audio File:       ${GREEN}$AUDIO_FILE${NC}"
echo -e "  Audio Duration:   ${BOLD}${AUDIO_DURATION}s${NC}"
echo -e "  Audio Bitrate:    ${BOLD}${AUDIO_KBPS} kbps${NC}"
echo -e "  Video File:       ${GREEN}$VIDEO_FILE${NC}"
echo -e "  Video Duration:   ${BOLD}${VIDEO_DURATION}s${NC}"
if [ "$HAS_THUMB" -eq 1 ]; then
    echo -e "  Thumbnail Image:  ${GREEN}$THUMB_FILE${NC}"
    echo -e "  Intro / Outro:    ${BOLD}${CALC_INTRO}s Intro / ${CALC_OUTRO}s Outro (with fade)${NC}"
else
    echo -e "  Thumbnail Image:  ${YELLOW}None (Continuous Video Mode)${NC}"
fi
echo -e "  Video Repeats:    ${BOLD}${NUM_FULL} full repeats + ${REM_DUR}s final segment${NC}"
echo -e "  Segment Fades:    ${BOLD}${CALC_FADE}s fade-in / fade-out per segment${NC}"
echo -e "  Video Encoder:    ${BOLD}${GREEN}${ENCODER_STR}${NC}"
echo -e "  Audio Codec:      ${BOLD}${GREEN}${ACODEC_STR}${NC}"
echo -e "  Output Video:     ${GREEN}$OUTPUT_FILE${NC}"
echo -e "${BLUE}------------------------------------------------------------${NC}"
echo -e "${YELLOW}Rendering ${RES_LABEL} looped MP4 video with FFmpeg... Please wait.${NC}\n"

# Create a secure temporary directory
TEMP_DIR=$(mktemp -d -t yt_mp4_loop_XXXXXX)
trap 'rm -rf "$TEMP_DIR"' EXIT

CONCAT_LIST="$TEMP_DIR/concat_list.txt"
: > "$CONCAT_LIST"

BASE_SCALE="scale=${WIDTH}:${HEIGHT}:force_original_aspect_ratio=decrease,pad=${WIDTH}:${HEIGHT}:(ow-iw)/2:(oh-ih)/2:black,setsar=1"

render_segment() {
    local label="$1" out="$2" dur="$3" f_in="$4" f_out="$5" is_img="$6" src="$7"
    echo -e "  -> $label"
    if [ "$is_img" -eq 1 ]; then
        ffmpeg -y -loop 1 -framerate 30 -t "$dur" -i "$src" \
          -vf "fps=30,${BASE_SCALE},fade=t=in:st=0:d=${f_in}:color=black,fade=t=out:st=${f_out}:d=${f_in}:color=black,format=yuv420p" \
          -t "$dur" -c:v "$VCODEC" "${VPRESET_ARGS[@]}" "$out" >/dev/null 2>&1
    else
        ffmpeg -y -i "$src" \
          -vf "setpts=PTS-STARTPTS,fps=30,${BASE_SCALE},fade=t=in:st=0:d=${f_in}:color=black,fade=t=out:st=${f_out}:d=${f_in}:color=black,format=yuv420p" \
          -t "$dur" -c:v "$VCODEC" "${VPRESET_ARGS[@]}" "$out" >/dev/null 2>&1
    fi
}

# 1. Render Intro Card if Thumbnail is present
if [ "$DO_INTRO" -eq 1 ]; then
    render_segment "Rendering Intro Thumbnail card (${CALC_INTRO}s)..." \
        "$TEMP_DIR/intro.mp4" "$CALC_INTRO" "$CALC_FADE" "$INTRO_FADE_OUT" 1 "$THUMB_FILE"
    echo "file '$TEMP_DIR/intro.mp4'" >> "$CONCAT_LIST"
fi

# 2. Render Full Video Segment (if needed)
if [ "$NUM_FULL" -gt 0 ]; then
    render_segment "Rendering Standard Looping Segment (${VIDEO_DURATION}s with fades)..." \
        "$TEMP_DIR/seg_full.mp4" "$VIDEO_DURATION" "$CALC_FADE" "$SEG_FADE_OUT" 0 "$VIDEO_FILE"
    for ((i=1; i<=NUM_FULL; i++)); do
        echo "file '$TEMP_DIR/seg_full.mp4'" >> "$CONCAT_LIST"
    done
fi

# 3. Render Final Partial Segment (if needed)
if [ "$DO_REM" -eq 1 ]; then
    render_segment "Rendering Final Trailing Segment (${REM_DUR}s with fades)..." \
        "$TEMP_DIR/seg_last.mp4" "$REM_DUR" "$REM_FADE_DUR" "$REM_FADE_OUT" 0 "$VIDEO_FILE"
    echo "file '$TEMP_DIR/seg_last.mp4'" >> "$CONCAT_LIST"
fi

# 4. Render Outro Card if Thumbnail is present
if [ "$DO_OUTRO" -eq 1 ]; then
    if [ "$DO_INTRO" -eq 1 ] && [ "$CALC_INTRO" = "$CALC_OUTRO" ]; then
        echo -e "  -> Reusing rendered Intro card for Outro (${CALC_OUTRO}s)..."
        echo "file '$TEMP_DIR/intro.mp4'" >> "$CONCAT_LIST"
    else
        render_segment "Rendering Outro Thumbnail card (${CALC_OUTRO}s)..." \
            "$TEMP_DIR/outro.mp4" "$CALC_OUTRO" "$CALC_FADE" "$OUTRO_FADE_OUT" 1 "$THUMB_FILE"
        echo "file '$TEMP_DIR/outro.mp4'" >> "$CONCAT_LIST"
    fi
fi

# 5. Merge all video segments and mux audio with studio fades at original audio bitrate
echo -e "  -> Concatenating video loop and muxing ${AUDIO_KBPS}kbps audio..."

STATUS=0
ffmpeg -y \
  -f concat -safe 0 -i "$CONCAT_LIST" \
  -i "$AUDIO_FILE" \
  -map 0:v:0 -map 1:a:0 \
  -c:v copy \
  -af "afade=t=in:st=0:d=${AUDIO_FADE_DUR},afade=t=out:st=${AUDIO_FADE_OUT_START}:d=${AUDIO_FADE_DUR}" \
  -c:a "$ACODEC" \
  -b:a "$AUDIO_BITRATE" \
  -t "$AUDIO_DURATION" \
  -movflags +faststart \
  "$OUTPUT_FILE" || STATUS=$?

echo -e "\n${BLUE}------------------------------------------------------------${NC}"
if [ "$STATUS" -eq 0 ]; then
    echo -e "${BOLD}${GREEN}✓ Successfully generated ${RES_LABEL} MP4 Video!${NC}"
    ls -lh "$OUTPUT_FILE"
else
    echo -e "${BOLD}${RED}✗ Video generation failed with exit code $STATUS!${NC}"
fi
echo -e "${BOLD}${BLUE}============================================================${NC}"

exit "$STATUS"
