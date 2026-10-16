#!/usr/bin/env bash

# ================================
# PATHS & CONFIGURATION
# ================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PARENT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Source config.env if present
for cfg in "$SCRIPT_DIR/config.env" "$PARENT_DIR/config.env" "$PWD/config.env" "${MIX_ARCHIVE_DIR:-}/config.env"; do
    if [ -f "$cfg" ]; then
        # shellcheck source=/dev/null
        source "$cfg"
        break
    fi
done

OUTPUT_DIR="${OUTPUT_DIR:-FLAC_CONVERTED_OUTPUTS}"
ARCHIVE_DIR="${ARCHIVE_DIR:-CONVERTED_WAV_FILES}"

# Direct Local Traktor History Directory (Auto-detected across Linux, macOS, and Windows)
LOCAL_HISTORY_DIR="${TRAKTOR_HISTORY_DIR:-}"
if [ -z "$LOCAL_HISTORY_DIR" ] || [ ! -d "$LOCAL_HISTORY_DIR" ]; then
    for cand in \
        "${MIX_ARCHIVE_DIR:-$PWD}/Traktor 3.11.1/History" \
        "./Traktor 3.11.1/History" \
        "/run/media/$USER/WD BLACK B/MIX_ARCHIVE/Traktor 3.11.1/History" \
        "/run/media/mplanetarian/WD BLACK B/MIX_ARCHIVE/Traktor 3.11.1/History" \
        "/Volumes/WD BLACK B/MIX_ARCHIVE/Traktor 3.11.1/History" \
        "/Volumes/MIX_ARCHIVE/Traktor 3.11.1/History" \
        "/d/MIX_ARCHIVE/Traktor 3.11.1/History" \
        "D:/MIX_ARCHIVE/Traktor 3.11.1/History" \
        "/mnt/d/MIX_ARCHIVE/Traktor 3.11.1/History" \
        "$HOME/Documents/Native Instruments/Traktor 3.11.1/History" \
        "$HOME/Native Instruments/Traktor 3.11.1/History"
    do
        if [ -d "$cand" ]; then
            LOCAL_HISTORY_DIR="$cand"
            break
        fi
    done
fi

START_TIME=$(date '+%Y-%m-%d %H:%M:%S')
NEW_TRACKLISTS_COUNT=0
total_flacs_audited=0

FORCE_REGENERATE="${FORCE_REGENERATE:-false}"
for arg in "$@"; do
    if [ "$arg" == "--force" ] || [ "$arg" == "-f" ]; then
        FORCE_REGENERATE=true
    fi
done

# Gather all FLAC output directories across Primary & Extra Archives
flac_scan_dirs=()
if [ -d "$OUTPUT_DIR" ]; then
    flac_scan_dirs+=("$(cd "$OUTPUT_DIR" && pwd)")
fi
if [ -n "${MIX_ARCHIVE_DIR:-}" ] && [ -d "$MIX_ARCHIVE_DIR/FLAC_CONVERTED_OUTPUTS" ]; then
    cand="$(cd "$MIX_ARCHIVE_DIR/FLAC_CONVERTED_OUTPUTS" && pwd)"
    [[ ! " ${flac_scan_dirs[*]} " =~ " ${cand} " ]] && flac_scan_dirs+=("$cand")
elif [ -n "${MIX_ARCHIVE_DIR:-}" ] && [ -d "$MIX_ARCHIVE_DIR" ]; then
    cand="$(cd "$MIX_ARCHIVE_DIR" && pwd)"
    [[ ! " ${flac_scan_dirs[*]} " =~ " ${cand} " ]] && flac_scan_dirs+=("$cand")
fi

if [ -n "${EXTRA_MIX_ARCHIVE_DIRS:-}" ]; then
    EXTRA_DIRS=()
    if [[ "$EXTRA_MIX_ARCHIVE_DIRS" == *";"* || "$EXTRA_MIX_ARCHIVE_DIRS" == *","* || "$EXTRA_MIX_ARCHIVE_DIRS" == *$'\n'* ]]; then
        IFS=';,'$'\n' read -ra EXTRA_DIRS <<< "$EXTRA_MIX_ARCHIVE_DIRS"
    elif [[ "$EXTRA_MIX_ARCHIVE_DIRS" =~ :[a-zA-Z]: ]]; then
        _fixed="$(printf '%s' "$EXTRA_MIX_ARCHIVE_DIRS" | sed -E 's/:([a-zA-Z]:)/;\1/g')"
        IFS=';' read -ra EXTRA_DIRS <<< "$_fixed"
    elif [[ ! "$EXTRA_MIX_ARCHIVE_DIRS" =~ ^[a-zA-Z]: && "$EXTRA_MIX_ARCHIVE_DIRS" == *":"* ]]; then
        IFS=':' read -ra EXTRA_DIRS <<< "$EXTRA_MIX_ARCHIVE_DIRS"
    else
        EXTRA_DIRS=("$EXTRA_MIX_ARCHIVE_DIRS")
    fi
    for ed in "${EXTRA_DIRS[@]}"; do
        ed="$(echo "$ed" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' -e 's/^["'"'"']//' -e 's/["'"'"']$//')"
        [ -z "$ed" ] && continue
        ed="${ed//\\//}"
        if [[ ! "$ed" =~ ^[a-zA-Z]:/$ && "$ed" != "/" ]]; then
            ed="${ed%/}"
        fi
        # Prefer local high-speed VFS cache path for GoogleDrive to avoid kernel FUSE locks
        if [[ "$ed" == *"GoogleDrive"* ]] && [ -d "$HOME/.cache/rclone/vfs/google3/MIX_ARCHIVE/FLAC_CONVERTED_OUTPUTS" ]; then
            cand="$HOME/.cache/rclone/vfs/google3/MIX_ARCHIVE/FLAC_CONVERTED_OUTPUTS"
            [[ ! " ${flac_scan_dirs[*]} " =~ " ${cand} " ]] && flac_scan_dirs+=("$cand")
            continue
        fi
        if [ -d "$ed/FLAC_CONVERTED_OUTPUTS" ]; then
            cand="$(cd "$ed/FLAC_CONVERTED_OUTPUTS" && pwd)"
            [[ ! " ${flac_scan_dirs[*]} " =~ " ${cand} " ]] && flac_scan_dirs+=("$cand")
        elif [ -d "$ed" ]; then
            cand="$(cd "$ed" && pwd)"
            [[ ! " ${flac_scan_dirs[*]} " =~ " ${cand} " ]] && flac_scan_dirs+=("$cand")
        fi
    done
fi

# Fallback to current directory if empty
if [ ${#flac_scan_dirs[@]} -eq 0 ]; then
    flac_scan_dirs+=("$PWD")
fi

# Gather all WAV archive directories
wav_scan_dirs=()
if [ -d "$ARCHIVE_DIR" ]; then
    wav_scan_dirs+=("$(cd "$ARCHIVE_DIR" && pwd)")
fi
if [ -n "${MIX_ARCHIVE_DIR:-}" ] && [ -d "$MIX_ARCHIVE_DIR/CONVERTED_WAV_FILES" ]; then
    cand="$(cd "$MIX_ARCHIVE_DIR/CONVERTED_WAV_FILES" && pwd)"
    [[ ! " ${wav_scan_dirs[*]} " =~ " ${cand} " ]] && wav_scan_dirs+=("$cand")
fi
if [ -n "${EXTRA_MIX_ARCHIVE_DIRS:-}" ]; then
    EXTRA_DIRS=()
    if [[ "$EXTRA_MIX_ARCHIVE_DIRS" == *";"* || "$EXTRA_MIX_ARCHIVE_DIRS" == *","* || "$EXTRA_MIX_ARCHIVE_DIRS" == *$'\n'* ]]; then
        IFS=';,'$'\n' read -ra EXTRA_DIRS <<< "$EXTRA_MIX_ARCHIVE_DIRS"
    elif [[ "$EXTRA_MIX_ARCHIVE_DIRS" =~ :[a-zA-Z]: ]]; then
        _fixed="$(printf '%s' "$EXTRA_MIX_ARCHIVE_DIRS" | sed -E 's/:([a-zA-Z]:)/;\1/g')"
        IFS=';' read -ra EXTRA_DIRS <<< "$_fixed"
    elif [[ ! "$EXTRA_MIX_ARCHIVE_DIRS" =~ ^[a-zA-Z]: && "$EXTRA_MIX_ARCHIVE_DIRS" == *":"* ]]; then
        IFS=':' read -ra EXTRA_DIRS <<< "$EXTRA_MIX_ARCHIVE_DIRS"
    else
        EXTRA_DIRS=("$EXTRA_MIX_ARCHIVE_DIRS")
    fi
    for ed in "${EXTRA_DIRS[@]}"; do
        ed="$(echo "$ed" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' -e 's/^["'"'"']//' -e 's/["'"'"']$//')"
        [ -z "$ed" ] && continue
        ed="${ed//\\//}"
        if [[ ! "$ed" =~ ^[a-zA-Z]:/$ && "$ed" != "/" ]]; then
            ed="${ed%/}"
        fi
        if [[ "$ed" == *"GoogleDrive"* ]] && [ -d "$HOME/.cache/rclone/vfs/google3/MIX_ARCHIVE/CONVERTED_WAV_FILES" ]; then
            cand="$HOME/.cache/rclone/vfs/google3/MIX_ARCHIVE/CONVERTED_WAV_FILES"
            [[ ! " ${wav_scan_dirs[*]} " =~ " ${cand} " ]] && wav_scan_dirs+=("$cand")
            continue
        fi
        if [ -d "$ed/CONVERTED_WAV_FILES" ]; then
            cand="$(cd "$ed/CONVERTED_WAV_FILES" && pwd)"
            [[ ! " ${wav_scan_dirs[*]} " =~ " ${cand} " ]] && wav_scan_dirs+=("$cand")
        fi
    done
fi

shopt -s nullglob nocaseglob

echo "=================================================="
echo "      CHECK & FIND TRACKLISTS SUITE               "
echo "=================================================="
echo "Active Archive Folders Being Scanned:"
for d in "${flac_scan_dirs[@]}"; do
    echo "  • FLAC Directory: $d"
done
echo "=================================================="

# Embedded python script for XML parsing
PY_PARSER_CONTENT=$(cat << 'PY_PARSER'
import sys
import xml.etree.ElementTree as ET

xml_file = sys.argv[1]
try:
    tree = ET.parse(xml_file)
    root = tree.getroot()

    collection_tracks = {}
    for entry in root.findall(".//ENTRY"):
        location = entry.find("LOCATION")
        if location is not None:
            dir_path = location.get("DIR", "")
            file_name = location.get("FILE", "")
            full_key = f"{location.get('VOLUME', '')}{dir_path}{file_name}"
        else:
            full_key = ""
        
        artist = entry.get("ARTIST", "")
        title = entry.get("TITLE", "")
        
        track_info = f"{artist} - {title}".strip()
        if track_info != "-":
            if full_key:
                collection_tracks[full_key] = track_info
            if file_name:
                collection_tracks[file_name] = track_info

    extracted_tracks = []
    seen = set()

    playlist_node = root.find(".//PLAYLIST")
    search_scope = playlist_node if playlist_node is not None else root

    for entry in search_scope.findall(".//ENTRY"):
        pkey = entry.find("PRIMARYKEY")
        if pkey is not None:
            key_val = pkey.get("KEY", "")
            track = None
            if key_val in collection_tracks:
                track = collection_tracks[key_val]
            else:
                for k, v in collection_tracks.items():
                    if k and k in key_val:
                        track = v
                        break
                if not track:
                    parts = key_val.split('/')
                    if parts:
                        track = parts[-1].replace('.flac', '').replace('.wav', '').replace('.mp3', '')
            
            if track and track != "-" and track not in seen:
                seen.add(track)
                extracted_tracks.append(track)

    if not extracted_tracks:
        for k, v in collection_tracks.items():
            if v != "-" and v not in seen:
                seen.add(v)
                extracted_tracks.append(v)

    gai_index = -1
    for idx, t in enumerate(extracted_tracks):
        if "Gai Barone" in t:
            gai_index = idx
            break

    if gai_index != -1:
        gai_track = extracted_tracks.pop(gai_index)
        if len(extracted_tracks) >= 13:
            extracted_tracks.insert(13, gai_track)
        else:
            extracted_tracks.append(gai_track)

    for idx, t in enumerate(extracted_tracks, start=1):
        print(f"{idx:02d}. {t}")
except Exception:
    sys.exit(1)
PY_PARSER
)

# Pre-cache Traktor history files and source WAV files for high-speed lookups
temp_py_parser=$(mktemp --suffix=_traktor_parser.py)
echo "$PY_PARSER_CONTENT" > "$temp_py_parser"

history_cache_file=$(mktemp --suffix=_hist_cache.txt)
if [ -d "$LOCAL_HISTORY_DIR" ]; then
    find "$LOCAL_HISTORY_DIR" -maxdepth 2 -type f \( -name "*.nml" -o -name "*.xml" -o -name "*.txt" \) 2>/dev/null > "$history_cache_file"
fi

wav_cache_file=$(mktemp --suffix=_wav_cache.txt)
for wdir in "${wav_scan_dirs[@]}" "$PWD"; do
    if [ -d "$wdir" ]; then
        find "$wdir" -maxdepth 1 -type f -name "*.wav" -printf "%f\n" 2>/dev/null >> "$wav_cache_file"
    fi
done

trap 'rm -f "$temp_py_parser" "$history_cache_file" "$wav_cache_file"' EXIT

# Function to extract date/time components from target string
extract_date_time() {
    local target="$1"
    session_year=$(echo "$target" | grep -oE '20[0-9]{2}' | head -n 1)
    session_month=$(echo "$target" | grep -oE '20[0-9]{2}-[0-9]{2}' | awk -F'-' '{print $2}')
    if [ -z "$session_month" ]; then
        session_month=$(echo "$target" | grep -oE '[0-9]{4}-[0-9]{2}-[0-9]{2}' | awk -F'-' '{print $2}')
    fi
    session_day=$(echo "$target" | grep -oE '[0-9]{4}-[0-9]{2}-[0-9]{2}' | awk -F'-' '{print $3}')
    session_hour=$(echo "$target" | grep -oE '[0-9]{1,2}h' | head -n 1 | tr -d 'h')
    if [ -n "$session_hour" ] && [ ${#session_hour} -eq 1 ]; then
        session_hour="0${session_hour}"
    fi
    session_min=$(echo "$target" | grep -oE '[0-9]{2}m' | head -n 1 | tr -d 'm')
}

# Function to find matching Traktor history file
find_matching_history() {
    local s_year="$1"
    local s_month="$2"
    local s_day="$3"
    local s_hour="$4"
    local s_min="$5"
    local f_base="$6"
    local matched=""

    # 1. Explicit alignment for verified episodes
    if [[ "$f_base" =~ (Mix_093|Episode_093|Episode 093|_093_) || "$f_base" == *"093"* ]]; then
        if [ -s "$history_cache_file" ]; then
            matched=$(grep -i "history_2026y05m21d_10h48m35s.nml" "$history_cache_file" | head -n 1)
            [ -n "$matched" ] && { echo "$matched"; return 0; }
        fi
        if [ -f "$LOCAL_HISTORY_DIR/history_2026y05m21d_10h48m35s.nml" ]; then
            echo "$LOCAL_HISTORY_DIR/history_2026y05m21d_10h48m35s.nml"
            return 0
        fi
    fi
    if [[ "$f_base" == *"081"* && "$f_base" =~ [Jj]orn ]] || [[ "$f_base" == *"2026-10-14_12h31m53"* ]]; then
        if [ -s "$history_cache_file" ]; then
            matched=$(grep -i "history_2026y10m14d_14h59m14s.nml" "$history_cache_file" | head -n 1)
            [ -n "$matched" ] && { echo "$matched"; return 0; }
        fi
        if [ -f "$LOCAL_HISTORY_DIR/history_2026y10m14d_14h59m14s.nml" ]; then
            echo "$LOCAL_HISTORY_DIR/history_2026y10m14d_14h59m14s.nml"
            return 0
        fi
    fi

    if [ ! -s "$history_cache_file" ]; then
        return 0
    fi

    # 2. Match exact hour and minute
    if [ -n "$s_year" ] && [ -n "$s_month" ] && [ -n "$s_day" ] && [ -n "$s_hour" ] && [ -n "$s_min" ]; then
        local pat="history_${s_year}y${s_month}m${s_day}d_${s_hour}h${s_min}"
        matched=$(grep -i -E -- "$pat" "$history_cache_file" | head -n 1)
        [ -n "$matched" ] && { echo "$matched"; return 0; }
    fi

    # 3. Match exact hour
    if [ -n "$s_year" ] && [ -n "$s_month" ] && [ -n "$s_day" ] && [ -n "$s_hour" ]; then
        local pat="history_${s_year}y${s_month}m${s_day}d_${s_hour}h"
        matched=$(grep -i -E -- "$pat" "$history_cache_file" | head -n 1)
        [ -n "$matched" ] && { echo "$matched"; return 0; }
    fi

    # 4. Fallback: match day or date pattern
    if [ -n "$s_year" ] && [ -n "$s_month" ] && [ -n "$s_day" ]; then
        local fb_pat="history_${s_year}y${s_month}m${s_day}d"
        matched=$(grep -i -E -- "$fb_pat" "$history_cache_file" | sort | tail -n 1)
        [ -n "$matched" ] && { echo "$matched"; return 0; }

        local s_date="${s_year}-${s_month}-${s_day}"
        matched=$(grep -i -E -- "$s_date" "$history_cache_file" | sort | tail -n 1)
        [ -n "$matched" ] && { echo "$matched"; return 0; }
    fi

    return 0
}

# Process each FLAC directory
for current_out in "${flac_scan_dirs[@]}"; do
    if [ ! -d "$current_out" ]; then
        continue
    fi

    flac_files=("$current_out"/*.flac)
    if [ ${#flac_files[@]} -eq 0 ]; then
        continue
    fi

    echo -e "\nScanning [${#flac_files[@]} mixes] in: $current_out..."

    for flac in "${flac_files[@]}"; do
        ((total_flacs_audited++))
        flac_base=$(basename "$flac" .flac)
        tracklist_path="${current_out}/${flac_base}.txt"
        
        if [ "$FORCE_REGENERATE" != "true" ] && [ -f "$tracklist_path" ]; then
            track_count=$(grep -cE '^[0-9]{2}\. ' "$tracklist_path" 2>/dev/null || echo 0)
            if [ "$track_count" -ge 2 ]; then
                continue
            fi
        fi
        
        echo "Found FLAC without tracklist (or fallback placeholder): $flac_base"
        
        # Extract base name matching the session ID pattern
        session_id=$(echo "$flac_base" | sed 's/^MPlanetarian - Stream of Frequency - //')
        readable_title=$(echo "$session_id" | sed 's/_/ /g')
        
        # Locate any source WAV files that match this session ID from the pre-cached index
        declare -a source_wavs=()
        if [ -s "$wav_cache_file" ]; then
            while IFS= read -r w; do
                [ -n "$w" ] && source_wavs+=("$w")
            done < <(grep -F "$session_id" "$wav_cache_file" 2>/dev/null)
        fi

        # Extract date/time components for Traktor history matching
        session_year="" session_month="" session_day="" session_hour="" session_min=""
        extract_date_time "$session_id"

        # Check sibling FLAC in current output folder if date missing
        if [ -z "$session_year" ]; then
            ep_token=$(echo "$flac_base" | grep -oE '(Mix|Episode)[-_ ]?[0-9]{3}' | grep -oE '[0-9]{3}' | head -n 1)
            if [ -n "$ep_token" ]; then
                for sib in "$current_out"/*"${ep_token}"*.flac; do
                    [ ! -f "$sib" ] && continue
                    sib_base=$(basename "$sib" .flac)
                    extract_date_time "$sib_base"
                    [ -n "$session_year" ] && break
                done
            fi
        fi

        # Fallback: if filename lacked date/time, inspect source WAV
        if [ -z "$session_year" ] && [ ${#source_wavs[@]} -gt 0 ]; then
            extract_date_time "${source_wavs[0]}"
        fi

        matched_history=$(find_matching_history "$session_year" "$session_month" "$session_day" "$session_hour" "$session_min" "$flac_base")
        
        # Generate the tracklist header
        {
            echo "=================================================="
            echo "RELEASE INFO & SOURCE MANIFEST"
            echo "=================================================="
            echo "Artist:        MPlanetarian"
            echo "Album:         Stream of Frequency"
            echo "Title:         $readable_title"
            echo "Conversion Date: $START_TIME"
            echo "--------------------------------------------------"
            echo "Source Files Merged/Converted (${#source_wavs[@]} file(s)):"
            for w in "${source_wavs[@]}"; do
                echo " - $w"
            done
            echo "=================================================="
        } > "$tracklist_path"
        
        tracklist_found=false
        if [ -n "$matched_history" ] && [ -f "$matched_history" ]; then
            echo " -> Matched Traktor history file: $(basename "$matched_history")"
            echo "TRACKLIST (Extracted from Traktor Database)" >> "$tracklist_path"
            echo "==================================================" >> "$tracklist_path"
            
            python3 "$temp_py_parser" "$matched_history" >> "$tracklist_path"
            status=$?
            
            if [ $status -eq 0 ] && [ -s "$tracklist_path" ] && [ $(wc -l < "$tracklist_path") -gt 10 ]; then
                tracklist_found=true
                echo " -> Tracklist generated successfully."
            fi
        fi
        
        if [ "$tracklist_found" = false ]; then
            echo " -> Generating fallback standalone tracklist..."
            echo "TRACKLIST (Automatic Fallback)" >> "$tracklist_path"
            echo "==================================================" >> "$tracklist_path"
            echo "01. Live Mix Session - $readable_title" >> "$tracklist_path"
        fi
        
        # Mirror to local VFS cache if processing GoogleDrive
        vfs_dest="$HOME/.cache/rclone/vfs/google3/MIX_ARCHIVE/FLAC_CONVERTED_OUTPUTS/${flac_base}.txt"
        if [[ "$current_out" == *"GoogleDrive"* ]] && [ -d "$(dirname "$vfs_dest")" ]; then
            cp -f "$tracklist_path" "$vfs_dest" 2>/dev/null
        fi
        
        ((NEW_TRACKLISTS_COUNT++))
    done
done

echo ""
echo "=================================================="
echo "Tracklist search complete across all archives."
echo "Total FLAC mixes checked:        $total_flacs_audited"
echo "New tracklists found and added:  $NEW_TRACKLISTS_COUNT"
echo "=================================================="