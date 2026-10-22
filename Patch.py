import shutil, subprocess, sys
import os

TARGET = "Mix_Archive_Manager.sh"
if not os.path.exists(TARGET):
    print(f"Error: {TARGET} not found in the current directory ({os.getcwd()}).")
    sys.exit(1)

shutil.copy2(TARGET, TARGET + ".bak")
print(f"Backup created: {TARGET}.bak")

with open(TARGET, "r", encoding="utf-8", errors="replace") as f:
    content = f.read()

# 1. Fix _nav_take_ready timeout from 0.01s to 0.001s
old_nav_take = '''_nav_take_ready() {
local _dest="$1" _ch; _nav_mark_console; if [[ -n "$_nav_pending" ]]; then _ch="${_nav_pending:0:1}"; _nav_pending="${_nav_pending:1}"; elif IFS= read -rsn1 -t 0.01 _ch; then [[ -z "$_ch" ]] && return 2; else return 1; fi; printf -v "$_dest" '%s' "$_ch"
}'''

new_nav_take = '''_nav_take_ready() {
local _dest="$1" _ch; _nav_mark_console; if [[ -n "$_nav_pending" ]]; then _ch="${_nav_pending:0:1}"; _nav_pending="${_nav_pending:1}"; elif IFS= read -rsn1 -t 0.001 _ch; then [[ -z "$_ch" ]] && return 2; else return 1; fi; printf -v "$_dest" '%s' "$_ch"
}'''

if old_nav_take in content:
    content = content.replace(old_nav_take, new_nav_take, 1)
    print("✓ Updated _nav_take_ready")
else:
    print("ℹ Note: _nav_take_ready exact block already updated or formatted differently.")

# 2. Fix build_header_block in run_interactive_submenu
old_build_hdr = '''build_header_block() {
header_count=0; cached_header_block=""; local inner_w=$(( box_w - 2 )); local text_w=$(( box_w - 4 )); local h_border; printf -v h_border '%*s' "$inner_w" ''; h_border="${h_border// /─}"; if [ -n "$menu_title" ]; then cached_header_block+="  ${BOLD}${MAGENTA}╭${h_border}╮\\033[K${NC}\\n"; local title_line; printf -v title_line "  ${BOLD}${MAGENTA}│ %-${text_w}s │\\033[K${NC}\\n" "  ${menu_title}"; cached_header_block+="$title_line"; cached_header_block+="  ${BOLD}${MAGENTA}╰${h_border}╯\\033[K${NC}\\n"; fi; if [ -z "$menu_title" ] && command -v render_main_header &>/dev/null; then render_main_header "$box_w" >/dev/null; menu_header="${_RENDERED_MAIN_HEADER:-}"; fi; if [ -n "$menu_header" ]; then local exp_hdr=""; printf -v exp_hdr "%b" "$menu_header"; while IFS= read -r h_line; do cached_header_block+="${h_line}\\033[K\\n"; ((header_count++)); done <<< "$exp_hdr"; fi; if [ -n "$menu_title" ]; then cached_header_block+="  ${DIM}${BLUE}Use [↑/↓] Arrow Keys to navigate, [/] to search, [Enter] to select, [Esc] to return immediately\\033[K${NC}\\n"; else cached_header_block+="  ${DIM}${BLUE}Use [↑/↓] Arrow Keys to navigate, [/] to search, [Enter] to select, 'q' to exit\\033[K${NC}\\n"; fi; overhead=5; [ -n "$menu_title" ] && overhead=$((overhead + 3)); overhead=$((overhead + header_count)); cached_header_lines=$header_count; [ -n "$menu_title" ] && cached_header_lines=$((cached_header_lines + 3)); cached_header_lines=$((cached_header_lines + 1))
}'''

new_build_hdr = '''build_header_block() {
header_count=0; cached_header_block=""; cached_header_lines=0; local inner_w=$(( box_w - 2 )); local text_w=$(( box_w - 4 )); local h_border; printf -v h_border '%*s' "$inner_w" ''; h_border="${h_border// /─}"; if [ -n "$menu_title" ]; then cached_header_block+="  ${BOLD}${MAGENTA}╭${h_border}╮\\033[K${NC}\\n"; local title_line; printf -v title_line "  ${BOLD}${MAGENTA}│ %-${text_w}s │\\033[K${NC}\\n" "  ${menu_title}"; cached_header_block+="$title_line"; cached_header_block+="  ${BOLD}${MAGENTA}╰${h_border}╯\\033[K${NC}\\n"; cached_header_lines=$((cached_header_lines + 3)); fi; if [ -z "$menu_title" ] && command -v render_main_header &>/dev/null; then render_main_header "$box_w" >/dev/null; menu_header="${_RENDERED_MAIN_HEADER:-}"; fi; if [ -n "$menu_header" ]; then local exp_hdr=""; printf -v exp_hdr "%b" "$menu_header"; exp_hdr="${exp_hdr%$'\\n'}"; while IFS= read -r h_line; do cached_header_block+="${h_line}\\033[K\\n"; ((header_count++)); done <<< "$exp_hdr"; cached_header_lines=$((cached_header_lines + header_count)); fi; if [ -n "$menu_title" ]; then cached_header_block+="  ${DIM}${BLUE}Use [↑/↓] Arrow Keys to navigate, [/] to search, [Enter] to select, [Esc] to return immediately\\033[K${NC}\\n"; else cached_header_block+="  ${DIM}${BLUE}Use [↑/↓] Arrow Keys to navigate, [/] to search, [Enter] to select, 'q' to exit\\033[K${NC}\\n"; fi; ((cached_header_lines++)); overhead=$((cached_header_lines + 4))
}'''

if old_build_hdr in content:
    content = content.replace(old_build_hdr, new_build_hdr, 1)
    print("✓ Updated build_header_block")
else:
    print("ℹ Note: build_header_block exact block already updated or formatted differently.")

# 3. Fix player_banner subshells & p_top_dashes bug
old_player_banner = '''local st_sym="${BOLD}${st_color}${st_icon} $(tr '[:upper:]' '[:lower:]' <<< "$MP_PLAYER_STATE")${NC}"; local st_raw="${st_icon} $(tr '[:upper:]' '[:lower:]' <<< "$MP_PLAYER_STATE")"; if [ "${MP_PLAYER_RECORDING:-false}" = "true" ]; then st_sym+=" ${BOLD}${RED}● REC${NC}"; st_raw+=" ● REC"; fi; local p_mode_title="♫ MP AUDIO PLAYER"; [ "$MP_PLAYER_MODE" = "MUSIC" ] && p_mode_title="♫ MP AUDIO PLAYER [MUSIC MODE - TRACKS]"; local rem_dashes=$(( inner_w - ${#p_mode_title} - 6 )); [ "$rem_dashes" -lt 0 ] && rem_dashes=0; local p_top_dashes="${rem_dashes// /─}"; player_banner+="  ${BOLD}${MAGENTA}╭── ${p_mode_title} ${p_top_dashes}╮\\033[K${NC}\\n";'''

new_player_banner = '''local st_low="${MP_PLAYER_STATE,,}"; local st_sym="${BOLD}${st_color}${st_icon} ${st_low}${NC}"; local st_raw="${st_icon} ${st_low}"; if [ "${MP_PLAYER_RECORDING:-false}" = "true" ]; then st_sym+=" ${BOLD}${RED}● REC${NC}"; st_raw+=" ● REC"; fi; local p_mode_title="♫ MP AUDIO PLAYER"; [ "$MP_PLAYER_MODE" = "MUSIC" ] && p_mode_title="♫ MP AUDIO PLAYER [MUSIC MODE - TRACKS]"; local rem_dashes=$(( inner_w - ${#p_mode_title} - 6 )); [ "$rem_dashes" -lt 0 ] && rem_dashes=0; local p_top_dashes; printf -v p_top_dashes '%*s' "$rem_dashes" ''; p_top_dashes="${p_top_dashes// /─}"; player_banner+="  ${BOLD}${MAGENTA}╭── ${p_mode_title} ${p_top_dashes}╮\\033[K${NC}\\n";'''

if old_player_banner in content:
    content = content.replace(old_player_banner, new_player_banner, 1)
    print("✓ Updated player banner dashes calculation")

# 4. Fix open_cover_art_window flatpak word-splitting bug
old_cover_win = '''for viewer in flatpak run org.kde.gwenview gwenview loupe eog feh xdg-open; do if command -v "$viewer" &>/dev/null; then nohup "$viewer" "$target" &>/dev/null &
disown 2>/dev/null || true; align_mix_windows_on_screen --expect-cover; return 0; fi; done'''

new_cover_win = '''if _has_flatpak "org.kde.gwenview"; then nohup flatpak run org.kde.gwenview "$target" &>/dev/null &
disown 2>/dev/null || true; align_mix_windows_on_screen --expect-cover; return 0; fi; for viewer in gwenview loupe eog feh xdg-open; do if command -v "$viewer" &>/dev/null; then nohup "$viewer" "$target" &>/dev/null &
disown 2>/dev/null || true; align_mix_windows_on_screen --expect-cover; return 0; fi; done'''

if old_cover_win in content:
    content = content.replace(old_cover_win, new_cover_win, 1)
    print("✓ Updated open_cover_art_window flatpak check")

# 5. Cache get_audio_volume_and_mute to prevent system command calls on every tick
old_vol_fn = '''get_audio_volume_and_mute() {
local out vol; if out=$(wpctl get-volume @DEFAULT_AUDIO_SINK@ 2>/dev/null) && [[ -n "$out" ]]; then vol="${out#*: }"; vol="${vol%% *}"; vol="${vol//./}"; vol=$((10#$vol)); [[ "$out" == *MUTED* ]] && echo "Muted (${vol}%)" || echo "${vol}%"; elif out=$(pactl get-sink-volume @DEFAULT_SINK@ 2>/dev/null) && [[ "$out" =~ ([0-9]+%) ]]; then vol="${BASH_REMATCH[1]}"; [[ $(pactl get-sink-mute @DEFAULT_SINK@ 2>/dev/null) == *yes* ]] && echo "Muted ($vol)" || echo "$vol"; elif [[ "$OS_TYPE" = "macos" ]]; then out=$(osascript -e 'get volume settings' 2>/dev/null); [[ "$out" =~ output\\ volume:([0-9]+).*output\\ muted:(true|false) ]] && {
[[ "${BASH_REMATCH[2]}" = "true" ]] && echo "Muted (${BASH_REMATCH[1]}%)" || echo "${BASH_REMATCH[1]}%"
}
else echo "Active"; fi
}'''

new_vol_fn = '''_LAST_VOL_CHECK=0; _CACHED_VOL_STATUS="Active"
get_audio_volume_and_mute() {
local now="${EPOCHSECONDS:-0}"; if [ "${1:-}" != "--force" ] && (( now - _LAST_VOL_CHECK < 15 )) && [ -n "$_CACHED_VOL_STATUS" ]; then echo "$_CACHED_VOL_STATUS"; return 0; fi; _LAST_VOL_CHECK="$now"; local out vol res="Active"; if out=$(wpctl get-volume @DEFAULT_AUDIO_SINK@ 2>/dev/null) && [[ -n "$out" ]]; then vol="${out#*: }"; vol="${vol%% *}"; vol="${vol//./}"; vol=$((10#$vol)); [[ "$out" == *MUTED* ]] && res="Muted (${vol}%)" || res="${vol}%"; elif out=$(pactl get-sink-volume @DEFAULT_SINK@ 2>/dev/null) && [[ "$out" =~ ([0-9]+%) ]]; then vol="${BASH_REMATCH[1]}"; [[ $(pactl get-sink-mute @DEFAULT_SINK@ 2>/dev/null) == *yes* ]] && res="Muted ($vol)" || res="$vol"; elif [[ "$OS_TYPE" = "macos" ]]; then out=$(osascript -e 'get volume settings' 2>/dev/null); [[ "$out" =~ output\\ volume:([0-9]+).*output\\ muted:(true|false) ]] && {
[[ "${BASH_REMATCH[2]}" = "true" ]] && res="Muted (${BASH_REMATCH[1]}%)" || res="${BASH_REMATCH[1]}%"
}; fi; _CACHED_VOL_STATUS="$res"; echo "$res"
}'''

if old_vol_fn in content:
    content = content.replace(old_vol_fn, new_vol_fn, 1)
    print("✓ Cached get_audio_volume_and_mute")

# 6. Fix LaTeX escapes and literal formatting bugs
content = content.replace(r"WAVs \vert{}${YELLOW}", "WAVs | ${YELLOW}")
content = content.replace(r"^(0\vert{}[qQ])$", "^(0|[qQ])$")

with open(TARGET, "w", encoding="utf-8", newline="\n") as f:
    f.write(content)

print(f"\nSUCCESS: {TARGET} successfully patched and saved!")