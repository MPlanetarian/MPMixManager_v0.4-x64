#!/usr/bin/env bash

# Setup colors
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'
BOLD='\033[1m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PARENT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Source config.env if present
for cfg in "$SCRIPT_DIR/config.env" "$PARENT_DIR/config.env" "$PWD/config.env" "${MIX_ARCHIVE_DIR:-}/config.env"; do
    if [ -f "$cfg" ]; then
        source "$cfg"
        break
    fi
done

CORRUPT_DIR="FLAC_CORRUPTED_FILES"
LOG_DIR="VERIFY_LOGS"

mkdir -p "$CORRUPT_DIR"
mkdir -p "$LOG_DIR"

TODAY=$(date '+%Y-%m-%d')
LOG_FILE="${LOG_DIR}/verify_${TODAY}.log"

echo "==================================================" | tee -a "$LOG_FILE"
echo "FLAC MULTI-ARCHIVE INTEGRITY CHECK STARTED AT $(date)" | tee -a "$LOG_FILE"
echo "==================================================" | tee -a "$LOG_FILE"

# Discover all FLAC directories
flac_scan_dirs=()
dirs=("$MIX_ARCHIVE_DIR/FLAC_CONVERTED_OUTPUTS" "$MIX_ARCHIVE_DIR" "$OUTPUT_DIR:-FLAC_CONVERTED_OUTPUTS" "$EXTRA_MIX_ARCHIVE_DIRS")
for d in "${dirs[@]}"; do
    d="${d:-$PWD}"
    d=$(cd "$d" && pwd)
    if [ -d "$d" ]; then
        flac_scan_dirs+=("$d")
    fi
done

echo "Active Archive Directories to Verify:" | tee -a "$LOG_FILE"
for d in "${flac_scan_dirs[@]}"; do
    echo "  • $d" | tee -a "$LOG_FILE"
done
echo "--------------------------------------------------" | tee -a "$LOG_FILE"

shopt -s nullglob nocaseglob
flac_files=()
for d in "${flac_scan_dirs[@]}"; do
    for f in "$d"/*.flac; do
        [ -f "$f" ] && flac_files+=("$f")
    done
done

if [ ${#flac_files[@]} -eq 0 ]; then
    echo "No FLAC files found in configured archive locations." | tee -a "$LOG_FILE"
    exit 0
fi

echo "Scanning ${#flac_files[@]} FLAC files across all archives for corruption..."
echo "This will decode each file to verify completeness. Please wait..."
echo "--------------------------------------------------"

results=$(printf '%s\n' "${flac_files[@]}" | xargs -d '\n' -P "$(nproc)" -I {} bash -c '
    flac="{}"
    filename=$(basename "$flac")
    error_output=$(ffmpeg -v error -i "$flac" -f null - 2>&1)
    status=$?
    if [ $status -ne 0 ] || [ -n "$error_output" ]; then
        clean_detail=$(echo "$error_output" | tr "\n" " ")
        echo "FAIL|$flac|$status|$clean_detail"
    else
        echo "OK|$flac"
    fi
')

checked_count=0
corrupt_count=0

while IFS='|' read -r status flac err_code err_detail; do
    [ -z "$status" ] && continue
    filename=$(basename "$flac")
    file_dir=$(dirname "$flac")
    if [ "$status" = "FAIL" ]; then
        echo -e "Checking: $filename ... ${RED}CORRUPT${NC}"
        echo "[CORRUPT] $flac - Error status: $err_code. Detail: $err_detail" >> "$LOG_FILE"
        mv "$flac" "$CORRUPT_DIR/"
        echo " -> Moved to $CORRUPT_DIR/" | tee -a "$LOG_FILE"
        flac_base="${filename%.*}"
        txt_path="${file_dir}/${flac_base}.txt"
        if [ -f "$txt_path" ]; then
            mv "$txt_path" "$CORRUPT_DIR/"
            echo " -> Moved tracklist $(basename "$txt_path") to $CORRUPT_DIR/" >> "$LOG_FILE"
        fi
        ((corrupt_count++))
    else
        echo -e "Checking: $filename ... ${GREEN}OK${NC}"
    fi
    ((checked_count++))
done <<< "$results"

echo "--------------------------------------------------" | tee -a "$LOG_FILE"
echo "Verification complete across all archives." | tee -a "$LOG_FILE"
echo "Total checked: $checked_count" | tee -a "$LOG_FILE"
echo "Total corrupt moved: $corrupt_count" | tee -a "$LOG_FILE"
echo "Log file: $LOG_FILE" | tee -a "$LOG_FILE"
echo "==================================================" | tee -a "$LOG_FILE" # 158 to 110