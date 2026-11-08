#!/usr/bin/env bash
# Optimized Audio Converter Script
source ~/audio_converter_config.conf 2>/dev/null || { echo "Config not found, using defaults"; exit 1; }

# Defaults (simplified)
: ${DEFAULT_OUT_DIR:="/outputs"}
: ${SUB_DIR:="default"}
: ${FMT_NAME:="mp3"}
: ${EXT:="mp3"}
: ${OPTS:="-q:a 2"}

DEFAULT_OUT_DIR="$DEFAULT_OUT_DIR/$SUB_DIR"

convert_file() {
    local src="$1" out_dir="$2" fmt="$3" opts="$4" ext="$5"
    local base="${src%.*}" dst="$out_dir/${base}.${ext}"
    
    mkdir -p "$out_dir" && ffmpeg -i "$src" $opts -vn -c:a "$fmt" "$dst" >/dev/null 2>&1
    [ $? -eq 0 ] && echo "✓ Converted: $src → $dst" || echo "✗ Failed: $src"
    return $?
}

get_files() {
    local dir="$1" ext="$2"
    find "$dir" -maxdepth 1 -type f -iname "*.$ext" 2>/dev/null
}

show_menu() {
    echo -e "\n${BOLD}${GREEN}=== AUDIO CONVERTER ===${NC}\n"
    echo "Select conversion scope:"
    echo "  1) Single file"
    echo "  2) Batch current directory"
    echo "  3) Batch WAV/OGG archives"
    echo "  4) Batch FLAC archives"
    read -r -p "Enter scope [1-4]: " scope
    case "$scope" in
        1) convert_single ;;
        2) convert_batch "." ;;
        3) convert_batch_array "${all_wav_dirs[*]}" ;;
        4) convert_batch_array "${all_flac_dirs[*]}" "flac" ;;
        *) echo -e "${RED}Invalid scope!${NC}"; exit 1 ;;
    esac
}

convert_single() {
    read -r -p "Enter file name (case-insensitive): " user_input
    
    local candidates=()
    for arch in "${all_mix_archive_roots[@]}"; do
        if [ -d "$arch" ]; then
            while IFS= read -r -d '' file; do
                [[ "$file" == *"$user_input"* ]] && candidates+=("$file")
            done < <(find "$arch" -maxdepth 1 -type f -iname "*.wav" -print0 2>/dev/null)
        fi
    done
    
    if [ ${#candidates[@]} -eq 0 ]; then
        echo -e "${RED}No files found!${NC}"; exit 1
    elif [ ${#candidates[@]} -eq 1 ]; then
        target_file="${candidates[0]}"
    else
        echo -e "\nFound ${#candidates[@]} files:"
        for i in "${!candidates[@]}"; do echo "$((i+1))) ${candidates[$i]}"; done
        read -r -p "Select file [1-${#candidates[@]}]: " pick
        target_file="${candidates[$((pick-1))]}"
    fi
    
    # Determine output dir based on extension
    target_archive_dir="${all_mix_archive_roots[0]}"
    for arch in "${all_mix_archive_roots[@]}"; do
        [[ "$target_file" == "$arch"* ]] && target_archive_dir="$arch" && break
    done
    
    DEFAULT_OUT_DIR="$target_archive_dir/${EXT^^}_CONVERTED_OUTPUTS"
    
    read -r -p "Output dir [default: $DEFAULT_OUT_DIR]: " custom_out
    final_out="${custom_out:-$DEFAULT_OUT_DIR}"
    
    convert_file "$target_file" "$final_out" "$FMT_NAME" "$OPTS" "$EXT"
}

convert_batch() {
    local dir="$1" ext="${2:-wav}"
    
    local files=()
    while IFS= read -r -d '' file; do
        files+=("$file")
    done < <(find "$dir" -maxdepth 1 -type f -iname "*.$ext" -print0 2>/dev/null)
    
    if [ ${#files[@]} -eq 0 ]; then
        echo -e "${RED}No $ext files found!${NC}"; exit 1
    fi
    
    read -r -p "Output dir [default: $DEFAULT_OUT_DIR]: " custom_out
    final_out="${custom_out:-$DEFAULT_OUT_DIR}"
    
    echo -e "\n${BOLD}${GREEN}=== CONVERTING ${#files[@]} FILES ===${NC}\n"
    
    success=0
    for f in "${files[@]}"; do
        convert_file "$f" "$final_out" "$FMT_NAME" "$OPTS" "$EXT" && ((success++))
    done
    echo -e "\n${BOLD}${GREEN}✓ Completed: $success / ${#files[@]} files!${NC}"
} # 200 to 104