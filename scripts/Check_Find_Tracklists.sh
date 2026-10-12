#!/usr/bin/env bash

# ================================
# PATHS & CONFIGURATION
# ================================

#!/bin/bash

set -euo pipefail

IFS=$'\n'
START_TIME=$(date +"%Y-%m-%d %H:%M:%S")
NEW_TRACKLISTS_COUNT=0
total_flacs_audited=0

history_cache_file="$HOME/.config/traktor/history_cache.txt"
temp_py_parser="$HOME/scripts/traktor_history_parser.py"

current_outs=("$HOME/Documents/MIX_ARCHIVE/FLAC_CONVERTED_OUTPUTS" "$HOME/GoogleDrive/MIX_ARCHIVE/FLAC_CONVERTED_OUTPUTS")

for current_out in "${current_outs[@]}"; do
    flacs=("$current_out"/*.flac)
    total_flacs_audited=$((total_flacs_audited + ${#flacs[@]}))
    
    for flac in "${flacs[@]}"; do
        flac_base=$(basename "$flac" .flac)
        tracklist_path="$current_out/${flac_base}.txt"
        
        if [ -s "$tracklist_path" ]; then
            continue
        fi
        
        source_wavs=("$current_out"/*.wav)
        readable_title=$(echo "$flac_base" | sed 's/[-_ ]/ /g' | sed 's/^.*\(Mix\|Episode\)[0-9]\{3\}.*$/\1/')
        
        session_year=$(echo "$flac_base" | grep -oE '20[0-9]{2}' | head -n 1)
        session_month=$(echo "$flac_base" | grep -oE '20[0-9]{2}-[0-9]{2}' | awk -F'-' '{print $2}')
        session_day=$(echo "$flac_base" | grep -oE '[0-9]{4}-[0-9]{2}-[0-9]{2}' | awk -F'-' '{print $3}')
        session_hour=$(echo "$flac_base" | grep -oE '[0-9]{1,2}h' | head -n 1 | tr -d 'h')
        session_min=$(echo "$flac_base" | grep -oE '[0-9]{2}m' | head -n 1 | tr -d 'm')
        
        if [ -z "$session_year" ]; then
            ep_token=$(echo "$flac_base" | grep -oE '(Mix|Episode)[-_ ]?[0-9]{3}' | grep -oE '[0-9]{3}' | head -n 1)
            for sib in "$current_out"/*"${ep_token}"*.flac; do
                [ ! -f "$sib" ] && continue
                sib_base=$(basename "$sib" .flac)
                s_yr=$(echo "$sib_base" | grep -oE '20[0-9]{2}' | head -n 1)
                if [ -n "$s_yr" ]; then
                    session_year="$s_yr"
                    session_month=$(echo "$sib_base" | grep -oE '20[0-9]{2}-[0-9]{2}' | awk -F'-' '{print $2}')
                    session_day=$(echo "$sib_base" | grep -oE '[0-9]{4}-[0-9]{2}-[0-9]{2}' | awk -F'-' '{print $3}')
                    session_hour=$(echo "$sib_base" | grep -oE '[0-9]{1,2}h' | head -n 1 | tr -d 'h')
                    session_min=$(echo "$sib_base" | grep -oE '[0-9]{2}m' | head -n 1 | tr -d 'm')
                    break
                fi
            done
        fi
        
        if [ -z "$session_year" ] && [ ${#source_wavs[@]} -gt 0 ]; then
            src_sample="${source_wavs[0]}"
            session_year=$(echo "$src_sample" | grep -oE '20[0-9]{2}' | head -n 1)
            session_month=$(echo "$src_sample" | grep -oE '20[0-9]{2}-[0-9]{2}' | awk -F'-' '{print $2}')
            session_day=$(echo "$src_sample" | grep -oE '[0-9]{4}-[0-9]{2}-[0-9]{2}' | awk -F'-' '{print $3}')
            session_hour=$(echo "$src_sample" | grep -oE '[0-9]{1,2}h' | head -n 1 | tr -d 'h')
            session_min=$(echo "$src_sample" | grep -oE '[0-9]{2}m' | head -n 1 | tr -d 'm')
        fi
        
        if [ -z "$session_year" ]; then
            continue
        fi
        
        session_date="${session_year}-${session_month}-${session_day}"
        fallback_pattern="history_${session_year}y${session_month}m${session_day}d"
        
        if [ -n "$session_hour" ] && [ -n "$session_min" ]; then
            traktor_pattern="history_${session_year}y${session_month}m${session_day}d_${session_hour}h${session_min}"
        fi
        
        if [ -n "$traktor_pattern" ]; then
            matched_history=$(grep -i -E -- "$traktor_pattern" "$history_cache_file" | head -n 1)
        fi
        
        if [ -z "$matched_history" ] && [ -n "$session_hour" ]; then
            matched_history=$(grep -i -E -- "history_${session_year}y${session_month}m${session_day}d_${session_hour}h" "$history_cache_file" | head -n 1)
        fi
        
        if [ -z "$matched_history" ]; then
            matched_history=$(grep -i -E -- "$fallback_pattern" "$history_cache_file" | sort | tail -n 1)
        fi
        
        if [ -z "$matched_history" ]; then
            matched_history=$(grep -i -E -- "$session_date" "$history_cache_file" | sort | tail -n 1)
        fi
        
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
        
        if [ -n "$matched_history" ] && [ -f "$matched_history" ]; then
            echo " -> Matched Traktor history file: $(basename "$matched_history")"
            echo "TRACKLIST (Extracted from Traktor Database)" >> "$tracklist_path"
            echo "==================================================" >> "$tracklist_path"
            
            python3 "$temp_py_parser" "$matched_history" >> "$tracklist_path"
            status=$?
            
            if [ $status -eq 0 ] && [ -s "$tracklist_path" ] && [ $(wc -l < "$tracklist_path") -gt 10 ]; then
                echo " -> Tracklist generated successfully."
            fi
        fi
        
        if [ ! -s "$tracklist_path" ]; then
            echo " -> Generating fallback standalone tracklist..."
            echo "TRACKLIST (Automatic Fallback)" >> "$tracklist_path"
            echo "==================================================" >> "$tracklist_path"
            echo "01. Live Mix Session - $readable_title" >> "$tracklist_path"
        fi
        
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