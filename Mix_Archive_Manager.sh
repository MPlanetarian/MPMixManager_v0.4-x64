#!/usr/bin/env bash
if [[ "$OSTYPE" == "darwin"* && "${BASH_VERSINFO[0]:-0}" -lt 4 ]]; then for bash in /opt/homebrew/bin/bash /usr/local/bin/bash; do [[ -x "$bash" ]] && exec "$bash" "$0" "$@"; done; fi; SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; MANAGER_START_EPOCH="${MANAGER_START_EPOCH:-${EPOCHSECONDS:-$(date +%s 2>/dev/null || echo 0)}}"; export MANAGER_START_EPOCH; shopt -s checkwinsize 2>/dev/null || true; export PYTHONIOENCODING="utf-8" PYTHONUTF8=1; UNAME_S="${UNAME_S:-$(uname -s 2>/dev/null)}"; UNAME_M="${UNAME_M:-$(uname -m 2>/dev/null)}"; _TERM_LINES=""; _TERM_COLS=""; _TERM_RESIZED=1; _on_winch() { _TERM_RESIZED=1; }; trap '_on_winch' WINCH; S70="======================================================================"; D70="----------------------------------------------------------------------"; if [ -z "${VERSION:-}" ]; then if [ -f "$SCRIPT_DIR/VERSION" ]; then VERSION="$(head -n 1 "$SCRIPT_DIR/VERSION" | tr -d '\r\n')"; else VERSION="0.4.0 Stable"; fi; fi; export VERSION
_has_flatpak() { [[ -d "/var/lib/flatpak/app/$1" || -d "$HOME/.local/share/flatpak/app/$1" ]] && return 0; command -v flatpak &>/dev/null || return 1; [[ -z "${_FP_LIST_CACHE+x}" ]] && _FP_LIST_CACHE="$(flatpak list --columns=application 2>/dev/null)"; [[ "$_FP_LIST_CACHE" == *"$1"* ]]; }
_fmt_sec() { local t=${1:-0}; ((t<0)) && t=0; ((t>=3600)) && printf "%02d:%02d:%02d" $((t/3600)) $(((t%3600)/60)) $((t%60)) || printf "%02d:%02d" $(((t%3600)/60)) $((t%60)); }
format_seconds_aud() { _fmt_sec "$1"; }
format_seconds_straw() { _fmt_sec "$1"; }
format_seconds_cliamp() { _fmt_sec "$1"; }
clear_archive_dir_cache() { _CACHED_ARCHIVE_DIRS=(); _CACHED_ALL_FLAC_OUTPUT_DIRS=(); _CACHED_ALL_WAV_ARCHIVE_DIRS=(); }
parse_extra_mix_archive_dirs() { local IFS=':,;'$'\n' d; for d in $1; do [ -z "$d" ] && continue; _norm_path "$d"; [ -n "$REPLY" ] && printf '%s\n' "$REPLY"; done; }
if command -v cygpath &>/dev/null; then if [[ -z "$HOME" || ! -d "$HOME" || "$HOME" = "/home/$USER" ]]; then export HOME="$(cygpath -u "$USERPROFILE" 2>/dev/null || true)"; fi; fi; if ! command -v pkill &>/dev/null; then
pkill() {
local sig="TERM" pattern=""; while [[ $# -gt 0 ]]; do case "$1" in -9|-KILL) sig="KILL" ;; -15|-TERM) sig="TERM" ;;
-f|-i|-x| -*) ;;
*) pattern="$1" ;; esac; shift; done; [[ -z "$pattern" ]] && return 1; pgrep -f "$pattern" | xargs -I{} kill -$sig {} 2>/dev/null || true
}
export -f pkill 2>/dev/null || true; fi
_win_console_size() {
local _rows_var="$1" _cols_var="$2" pid="${_WIN_CURSOR_HIDER_PID:-}"
if [[ -n "$pid" ]]; then
    if [[ "$OS_TYPE" == "windows" ]] || [[ "$UNAME_S" =~ (MINGW|MSYS|CYGWIN) ]]; then
        ps -W 2>/dev/null | awk -v p="$pid" '$1 == p {found=1} END {exit !found}' || return 1
    else
        kill -0 "$pid" 2>/dev/null || return 1
    fi
fi
local f="${HOME}/.config/mix-manager/console_size"
[[ -f "$f" ]] || return 1
local r c
IFS=$' \t' read -r r c < "$f" 2>/dev/null || return 1
[[ "$r" =~ ^[0-9]+$ && "$c" =~ ^[0-9]+$ && "$r" -ge 1 && "$c" -ge 1 ]] || return 1
printf -v "$_rows_var" '%s' "$r"
printf -v "$_cols_var" '%s' "$c"
}
update_terminal_geometry() {
local force="${1:-0}" win_l="" win_c=""
if _win_console_size win_l win_c; then 
    if [[ "$force" -eq 1 || "${_TERM_RESIZED:-0}" -eq 1 || "$win_l" != "${_TERM_LINES:-}" || "$win_c" != "${_TERM_COLS:-}" ]]; then 
        _TERM_LINES="$win_l" 
        _TERM_COLS="$win_c" 
        _TERM_RESIZED=0
        
        # CRITICAL: Force Windows Bash / stty / shell variables to match the new dimensions instantly
        if [[ "$OS_TYPE" == "windows" ]] || [[ "$UNAME_S" =~ (MINGW|MSYS|CYGWIN) ]]; then
            stty cols "$win_c" rows "$win_l" 2>/dev/null || true
            export LINES="$win_l"
            export COLUMNS="$win_c"
        fi
        return 0
    fi
    return 1
fi

if [[ "$force" -eq 1 || "${_TERM_RESIZED:-0}" -eq 1 || -z "${_TERM_LINES:-}" || -z "${_TERM_COLS:-}" ]]; then 
    local new_l="" new_c=""
    local sz
    if sz="$(stty size 2>/dev/null)" && [[ -n "$sz" ]]; then 
        read -r new_l new_c <<< "$sz"
    fi
    if [[ ! "$new_l" =~ ^[0-9]+$ || "$new_l" -lt 10 ]]; then
        new_l=$(tput lines 2>/dev/null || echo "${LINES:-40}")
    fi
    if [[ ! "$new_c" =~ ^[0-9]+$ || "$new_c" -lt 20 ]]; then
        new_c=$(tput cols 2>/dev/null || echo "${COLUMNS:-100}")
    fi
    [[ "$new_l" =~ ^[0-9]+$ && "$new_l" -ge 10 ]] || new_l="${LINES:-40}"
    [[ "$new_l" =~ ^[0-9]+$ && "$new_l" -ge 10 ]] || new_l=40
    [[ "$new_c" =~ ^[0-9]+$ && "$new_c" -ge 20 ]] || new_c="${COLUMNS:-100}"
    [[ "$new_c" =~ ^[0-9]+$ && "$new_c" -ge 20 ]] || new_c=100
    _TERM_LINES="$new_l"
    _TERM_COLS="$new_c"
    _TERM_RESIZED=0
    export LINES="$_TERM_LINES"
    export COLUMNS="$_TERM_COLS"
    return 0
fi 
return 1
}
_set_menu_box_width() {
local _dest="$1" _cols="${2:-${_TERM_COLS:-80}}"; [[ "$_cols" =~ ^[0-9]+$ ]] || _cols=80; [[ "$_cols" -lt 1 ]] && _cols=1; local _w; if [[ "$_cols" -ge 8 ]]; then _w=$((_cols - 4)); elif [[ "$_cols" -ge 3 ]]; then _w=$((_cols - 2)); else _w=1; fi; printf -v "$_dest" '%s' "$_w"
}
set_theme_colors() {
local theme_name="${1:-dreamworlds}"; NC='\033[0m' BOLD='\033[1m' DIM='\033[2m'; case "$theme_name" in dreamworlds|mplanetarian_dreamworlds|mplanetarian|default) RED='\033[38;2;237;37;78m' GREEN='\033[38;2;0;229;255m' YELLOW='\033[38;2;255;170;0m'; BLUE='\033[38;2;155;89;182m' MAGENTA='\033[38;2;247;37;133m' CYAN='\033[38;2;0;193;228m'; CURRENT_THEME="dreamworlds" ;;
cosmic_dreamworlds|cosmic_dreamworld|cosmic_dream|"Cosmic Dreamworlds (Liquid Glass Skin)"|"Cosmic Dreamworlds")
RED='\033[38;2;232;13;104m'; GREEN='\033[38;2;0;245;212m'; YELLOW='\033[38;2;254;228;64m'; BLUE='\033[38;2;94;96;206m'; MAGENTA='\033[38;2;176;88;255m'; CYAN='\033[38;2;0;245;212m'; CURRENT_THEME="cosmic_dreamworlds" ;;
cosmic_dreamworlds_radioactive|radioactive|cosmic_radioactive|"Cosmic Dreamworlds Radioactive (Liquid Glass Skin)"|"Cosmic Dreamworlds Radioactive")
RED='\033[38;2;57;255;20m'; GREEN='\033[38;2;0;245;212m'; YELLOW='\033[38;2;255;215;0m'; BLUE='\033[38;2;102;102;255m'; MAGENTA='\033[38;2;166;77;255m'; CYAN='\033[38;2;0;245;212m'; CURRENT_THEME="cosmic_dreamworlds_radioactive" ;;
orbital_void_reflux|orbital_void|void_reflux|orbital|"Orbital Void Reflux (Liquid Glass Skin)"|"Orbital Void Reflux")
RED='\033[38;2;255;0;127m'; GREEN='\033[38;2;0;240;255m'; YELLOW='\033[38;2;157;78;221m'; BLUE='\033[38;2;123;44;191m'; MAGENTA='\033[38;2;157;78;221m'; CYAN='\033[38;2;0;240;255m'; CURRENT_THEME="orbital_void_reflux" ;;
dynamic_rainbow_liquid_glass|dynamic_liquid_glass_rainbow|dynamic_rainbow|rainbow_liquid_glass|rainbow|"Dynamic Liquid Glass [Rainbow Colours] (New)"|"Dynamic Liquid Glass [Rainbow Colours]"|"Dynamic Liquid Glass")
RED='\033[38;2;255;45;142m'; GREEN='\033[38;2;0;242;254m'; YELLOW='\033[38;2;255;215;0m'; BLUE='\033[38;2;90;130;255m'; MAGENTA='\033[38;2;176;88;255m'; CYAN='\033[38;2;0;242;254m'; CURRENT_THEME="dynamic_rainbow_liquid_glass" ;;
dreamworlds_liquid|mp_dreamworlds_liquid_transparency|liquid_transparency|liquid|glass|"MP Dreamworlds Liquid Transparency"|"MP Dreamworlds Liquid Transparency [Special Edition]")
RED='\033[38;2;255;75;130m'; GREEN='\033[38;2;0;245;212m'; YELLOW='\033[38;2;255;215;0m'; BLUE='\033[38;2;72;149;239m'; MAGENTA='\033[38;2;199;125;255m'; CYAN='\033[38;2;0;245;255m'; CURRENT_THEME="dreamworlds_liquid" ;;
dreamworlds_ultra|ultra|dreamworlds_ultra_mp_mix_manager|"Dreamworlds Ultra MP Mix Manager")
RED='\033[38;2;255;0;0m' GREEN='\033[38;2;0;255;0m' YELLOW='\033[38;2;255;153;51m'; BLUE='\033[38;2;102;102;255m' MAGENTA='\033[38;2;166;77;255m' CYAN='\033[38;2;153;153;255m'; CURRENT_THEME="dreamworlds_ultra" ;;
cosmic_supernova|supernova|cosmic|cosmic_supernova_mp_mix_manager|"Cosmic Supernova MP Mix Manager"|"Cosmic Supernova"|"Cosmic Supernova [Special]"|"Cosmic Supernova [Special Edition]")
RED='\033[38;2;255;51;102m'; GREEN='\033[38;2;0;245;212m'; YELLOW='\033[38;2;254;228;64m'; BLUE='\033[38;2;94;96;206m'; MAGENTA='\033[38;2;224;86;253m'; CYAN='\033[38;2;76;201;240m'; CURRENT_THEME="cosmic_supernova" ;;
retro_terminal|unix_terminal|retro_unix|old_style_unix|unix_retro|white_on_black|retro|terminal|vt100|"Old Style Unix Terminal Retro Mode (White on Black)"|"Old Style Unix Terminal Retro Mode"|"Old Style Unix Terminal")
RED='\033[1;37m' GREEN='\033[1;37m' YELLOW='\033[1;37m'; BLUE='\033[0;37m' MAGENTA='\033[1;37m' CYAN='\033[1;37m'; CURRENT_THEME="retro_terminal" ;; dracula|dreamworlds_neon) RED='\033[38;5;212m' GREEN='\033[38;5;84m' YELLOW='\033[38;5;228m'; BLUE='\033[38;5;62m' MAGENTA='\033[38;5;141m' CYAN='\033[38;5;117m'; CURRENT_THEME="dracula" ;; nord|ice_cold) RED='\033[38;5;167m' GREEN='\033[38;5;108m' YELLOW='\033[38;5;221m'; BLUE='\033[38;5;110m' MAGENTA='\033[38;5;139m' CYAN='\033[38;5;117m'; CURRENT_THEME="nord" ;; matrix|phosphor) RED='\033[38;5;124m' GREEN='\033[38;5;46m' YELLOW='\033[38;5;190m'; BLUE='\033[38;5;29m' MAGENTA='\033[38;5;35m' CYAN='\033[38;5;120m'; CURRENT_THEME="matrix" ;; solarized) RED='\033[38;5;166m' GREEN='\033[38;5;64m' YELLOW='\033[38;5;136m'; BLUE='\033[38;5;33m' MAGENTA='\033[38;5;125m' CYAN='\033[38;5;37m'; CURRENT_THEME="solarized" ;; tokyo) RED='\033[38;5;203m' GREEN='\033[38;5;114m' YELLOW='\033[38;5;222m'; BLUE='\033[38;5;111m' MAGENTA='\033[38;5;176m' CYAN='\033[38;5;73m'; CURRENT_THEME="tokyo" ;; monokai) RED='\033[38;5;197m' GREEN='\033[38;5;148m' YELLOW='\033[38;5;220m'; BLUE='\033[38;5;141m' MAGENTA='\033[38;5;208m' CYAN='\033[38;5;81m'; CURRENT_THEME="monokai" ;; gruvbox|retro_studio) RED='\033[38;5;167m' GREEN='\033[38;5;142m' YELLOW='\033[38;5;214m'; BLUE='\033[38;5;109m' MAGENTA='\033[38;5;175m' CYAN='\033[38;5;108m'; CURRENT_THEME="gruvbox" ;; emerald) RED='\033[38;5;204m' GREEN='\033[38;5;48m' YELLOW='\033[38;5;221m'; BLUE='\033[38;5;31m' MAGENTA='\033[38;5;78m' CYAN='\033[38;5;86m'; CURRENT_THEME="emerald" ;; classic) RED='\033[0;31m' GREEN='\033[0;32m' YELLOW='\033[0;33m'; BLUE='\033[0;34m' MAGENTA='\033[0;35m' CYAN='\033[0;36m'; CURRENT_THEME="classic" ;; cyberpunk|cyber_neon|*) RED='\033[38;5;196m' GREEN='\033[38;5;48m' YELLOW='\033[38;5;226m'; BLUE='\033[38;5;45m' MAGENTA='\033[38;5;198m' CYAN='\033[38;5;51m'; CURRENT_THEME="cyberpunk" ;; esac
export CURRENT_THEME
}
play_sound_effect() {
local sound_type="${1:-storage}" sound_file=""; if [[ "$sound_type" == "dreamworlds" || "$sound_type" == "theme" ]]; then for cand in /usr/share/sounds/Oxygen-Sys-Special.ogg /usr/share/sounds/oxygen/stereo/dialog-special.ogg /usr/share/sounds/ocean/stereo/theme-demo.oga /usr/share/sounds/ocean/stereo/desktop-login.oga /usr/share/sounds/freedesktop/stereo/service-login.oga; do [[ -f "$cand" ]] && { sound_file="$cand"; break; }; done; elif [[ "$sound_type" == "storage" ]]; then for cand in /usr/share/sounds/ocean/stereo/device-added.oga /usr/share/sounds/freedesktop/stereo/device-added.oga /usr/share/sounds/Oxygen-Sys-App-Positive.ogg /usr/share/sounds/ocean/stereo/completion-success.oga; do [[ -f "$cand" ]] && { sound_file="$cand"; break; }; done; fi; if [[ -n "$sound_file" ]]; then for player in pw-play paplay canberra-gtk-play aplay; do if command -v "$player" &>/dev/null; then "$player" "$sound_file" &>/dev/null & break; fi; done; fi
}
_resize_pending() {
local win_l win_c
if _win_console_size win_l win_c; then 
    if [[ "$win_l" != "${_TERM_LINES:-}" || "$win_c" != "${_TERM_COLS:-}" ]]; then 
        _TERM_RESIZED=1
        return 0
    fi
    return 1
fi
if [[ "${_TERM_RESIZED:-0}" -eq 1 ]]; then
    return 0
fi
local sz
if sz="$(stty size 2>/dev/null)" && [[ -n "$sz" ]]; then
    local cur_l cur_c
    read -r cur_l cur_c <<< "$sz"
    if [[ -n "$cur_l" && -n "$cur_c" ]]; then
        if [[ "$cur_l" != "${_TERM_LINES:-}" || "$cur_c" != "${_TERM_COLS:-}" ]]; then
            _TERM_RESIZED=1
            return 0
        fi
    fi
fi
return 1
}
_nav_pending=""; _NAV_WIN_CON=""; _NAV_ARROW_AT=""
_nav_just_arrowed() {
# Windows console arrow-echo guard: only true for a short window (150ms) after an arrow key. Previously this was a sticky flag that never cleared on TICK paths, so every Enter on Windows 10 consoles was swallowed as TICK.
local at="${_NAV_ARROW_AT:-}" now="${EPOCHREALTIME:-}"; [[ -n "$at" ]] || return 1; at="${at/[.,]/}"; now="${now/[.,]/}"; if [[ ! "$at" =~ ^[0-9]{7,}$ || ! "$now" =~ ^[0-9]{7,}$ ]]; then _NAV_ARROW_AT=""; return 1; fi; at=$((10#$at)); now=$((10#$now)); if (( now - at >= 0 && now - at < 150000 )); then return 0; fi; _NAV_ARROW_AT=""; return 1
}
_nav_mark_console() {
[[ -n "${_NAV_WIN_CON:-}" ]] && return 0; case "$(tty 2>/dev/null)" in /dev/cons*) _NAV_WIN_CON=1 ;; *) _NAV_WIN_CON=0 ;; esac
}
_nav_take_ready() {
local _dest="$1" _ch; _nav_mark_console; if [[ -n "$_nav_pending" ]]; then _ch="${_nav_pending:0:1}"; _nav_pending="${_nav_pending:1}"; elif IFS= read -rsn1 -t 0.001 _ch; then [[ -z "$_ch" ]] && return 2; else return 1; fi; printf -v "$_dest" '%s' "$_ch"
}
_nav_push_front() { _nav_pending="${1}${_nav_pending}"; }
_nav_pull() {
local _to="$1" _dest="$2"; if [[ -n "$_nav_pending" ]]; then printf -v "$_dest" '%s' "${_nav_pending:0:1}"; _nav_pending="${_nav_pending:1}"; return 0; fi; local _ch="" _rc=0; IFS= read -rsn1 -t "$_to" _ch; _rc=$?; if [[ "$_rc" -eq 0 ]]; then printf -v "$_dest" '%s' "$_ch"; return 0; fi; printf -v "$_dest" '%s' ""; return "$_rc"
}
_discard_buffered_vertical_arrows() {
local guard=0 b1="" b2="" b3="" b4="" seq="" cur="" steps=0 discard_it=0 ready_rc=0 empties=0; while [[ "$guard" -lt 200 ]]; do ((guard++)); b1=""; _nav_take_ready b1; ready_rc=$?; if [[ "$ready_rc" -eq 2 ]]; then if [[ "${_NAV_WIN_CON:-0}" -ne 1 ]]; then _nav_pending=$'\n'"${_nav_pending}"; return 0; fi; ((empties++)); [[ "$empties" -ge 2 ]] && return 0; continue; fi; [[ "$ready_rc" -eq 0 ]] || return 0; if [[ "${_NAV_WIN_CON:-0}" -eq 1 && ( "$b1" == "A" || "$b1" == "B" || "$b1" == $'\r' ) ]]; then continue; fi; if [[ "$b1" != $'\e' ]]; then _nav_push_front "$b1"; return 0; fi; if ! _nav_take_ready b2 || [[ "$b2" != "[" && "$b2" != "O" ]]; then _nav_push_front "${b1}${b2:-}"; return 0; fi; if [[ "$b2" == "[" ]]; then if ! _nav_take_ready b3 || [[ "$b3" != "A" && "$b3" != "B" ]]; then if [[ "$b3" == "[" ]]; then if ! _nav_take_ready b4 || [[ "$b4" != "A" && "$b4" != "B" ]]; then _nav_push_front "${b1}${b2}${b3}${b4:-}"; return 0; fi; discard_it=1; else seq="${b1}${b2}${b3}"; while [[ "$steps" -lt 16 ]]; do ((steps++)); cur=""; if ! _nav_take_ready cur; then _nav_push_front "$seq"; return 0; fi; seq+="$cur"; if [[ "$cur" == "A" || "$cur" == "B" ]]; then discard_it=1; break; fi; if [[ "$cur" =~ [A-Za-z~] ]]; then _nav_push_front "$seq"; return 0; fi; done; [[ "$discard_it" -ne 1 ]] && { _nav_push_front "$seq"; return 0; }; fi; fi; elif [[ "$b2" == "O" ]]; then if ! _nav_take_ready b3 || [[ "$b3" != "A" && "$b3" != "B" ]]; then _nav_push_front "${b1}${b2}${b3:-}"; return 0; fi; fi; done
}
read_nav_key() {
local _out_var="$1" _k=""
_emit_key() {
if [[ -n "$_out_var" ]]; then printf -v "$_out_var" "%s" "$1"; else echo "$1"; fi; return 0
}
_nav_mark_console; local read_rc=0; _nav_pull 0.05 _k; read_rc=$?; if [[ "$read_rc" -ne 0 ]]; then _k=""; if _resize_pending; then _emit_key "RESIZE"; return 0; fi; if [[ "$read_rc" -gt 128 ]]; then _emit_key "TICK"; return 0; fi; if [[ -n "$_out_var" ]]; then printf -v "$_out_var" "%s" ""; fi; return 1; fi; if [[ -z "$_k" || "$_k" == $'\n' || "$_k" == $'\r' ]]; then if [[ "${_NAV_WIN_CON:-0}" -eq 1 ]] && _nav_just_arrowed; then _emit_key "TICK"; return 0; fi; _NAV_ARROW_AT=""; _emit_key "ENTER"; elif [[ "$_k" == " " ]]; then _emit_key "SPACE"; elif [[ "$_k" == $'\x7f' || "$_k" == $'\x08' ]]; then _emit_key "BACKSPACE"; elif [[ "$_k" == $'\x1b' || "$_k" == $'\e' ]]; then local c2=""; if _nav_pull 0.02 c2; then if [[ "$c2" == "[" ]]; then local c3=""; if _nav_pull 0.02 c3; then case "$c3" in A) _emit_key "UP" ; _NAV_ARROW_AT=1 ;; B) _emit_key "DOWN" ; _NAV_ARROW_AT=1 ;; C) _emit_key "RIGHT" ;; D) _emit_key "LEFT" ;; H) _emit_key "HOME" ;; F) _emit_key "END" ;; "[") local c4=""; if _nav_pull 0.02 c4; then case "$c4" in A) _emit_key "UP" ; _NAV_ARROW_AT=1 ;; B) _emit_key "DOWN" ; _NAV_ARROW_AT=1 ;; C) _emit_key "RIGHT" ;; D) _emit_key "LEFT" ;; *) _emit_key "UNKNOWN" ;; esac; fi ;; [0-9]) local c4=""; if _nav_pull 0.02 c4; then case "${c3}${c4}" in
5~) _emit_key "PAGE_UP" ;;
6~) _emit_key "PAGE_DOWN" ;;
1~|7~) _emit_key "HOME" ;;
4~|8~) _emit_key "END" ;;
2~) _emit_key "INSERT" ;;
3~) _emit_key "DELETE" ;;
23|24) local c5=""; _nav_pull 0.02 c5 || true; _emit_key "TOGGLE_FULLSCREEN"; ;; *) local cur="${c4}"; while [[ ! "$cur" =~ [A-Za-z~] ]]; do _nav_pull 0.02 cur || break; done; case "$cur" in A) _emit_key "UP" ; _NAV_ARROW_AT=1 ;; B) _emit_key "DOWN" ; _NAV_ARROW_AT=1 ;; C) _emit_key "RIGHT" ;; D) _emit_key "LEFT" ;; H) _emit_key "HOME" ;; F) _emit_key "END" ;; *) _emit_key "UNKNOWN" ;; esac ;; esac; fi; ;; *) _emit_key "UNKNOWN" ;; esac; fi; elif [[ "$c2" == "O" ]]; then local c3=""; if _nav_pull 0.02 c3; then case "$c3" in A) _emit_key "UP" ; _NAV_ARROW_AT=1 ;; B) _emit_key "DOWN" ; _NAV_ARROW_AT=1 ;; C) _emit_key "RIGHT" ;; D) _emit_key "LEFT" ;; H) _emit_key "HOME" ;; F) _emit_key "END" ;; *) _emit_key "UNKNOWN" ;; esac; fi; else _emit_key "UNKNOWN"; fi; else _emit_key "ESC"; fi; else _emit_key "CHAR:$_k"; fi; [[ -n "$_NAV_ARROW_AT" ]] && { sleep 0.01; _NAV_ARROW_AT=""; } 2>/dev/null || true
}
highlight_menu_line() {
local key="$1" label="$2" extra="$3" color_idx="${4:-0}" _out_var="$5" box_width="${6:-74}" breath_factor="${7:-100}"; local c_mod=$(( (color_idx % 4 + 4) % 4 )); local base_r base_g base_b base_pr base_pg base_pb; if [ "${CURRENT_THEME:-}" = "retro_terminal" ]; then base_r=255; base_g=255; base_b=255; base_pr=255; base_pg=255; base_pb=255; elif [ "${CURRENT_THEME:-}" = "cosmic_supernova" ]; then case "$c_mod" in 0) base_r=224; base_g=86; base_b=253; base_pr=224; base_pg=86; base_pb=253 ;; 1) base_r=0; base_g=245; base_b=212; base_pr=0; base_pg=245; base_pb=212 ;; 2) base_r=254; base_g=228; base_b=64; base_pr=254; base_pg=228; base_pb=64 ;; 3) base_r=94; base_g=96; base_b=206; base_pr=140; base_pg=160; base_pb=255 ;; esac; else case "$c_mod" in 0) base_r=247; base_g=37; base_b=133; base_pr=247; base_pg=37; base_pb=133 ;; 1) base_r=0; base_g=229; base_b=255; base_pr=0; base_pg=229; base_pb=255 ;; 2) base_r=255; base_g=140; base_b=0; base_pr=255; base_pg=140; base_pb=0 ;; 3) base_r=88; base_g=98; base_b=118; base_pr=160; base_pg=175; base_pb=205 ;; esac; fi; local bf="${breath_factor:-100}"; [ "$bf" -lt 15 ] && bf=15; [ "$bf" -gt 100 ] && bf=100; local r=$(( base_r * bf / 100 )) g=$(( base_g * bf / 100 )) b=$(( base_b * bf / 100 )) pr=$(( base_pr * bf / 100 )) pg=$(( base_pg * bf / 100 )) pb=$(( base_pb * bf / 100 )); local bg="\033[48;2;${r};${g};${b}m" ptr_col="\033[1;38;2;${pr};${pg};${pb}m" fg_key fg_lbl; if [ "$bf" -ge 60 ]; then if [ "${CURRENT_THEME:-}" = "retro_terminal" ]; then fg_key="\033[1;38;2;0;0;0m"; fg_lbl="\033[1;38;2;0;0;0m"; elif [ "${CURRENT_THEME:-}" = "cosmic_supernova" ] && [ "$c_mod" -eq 3 ]; then fg_key="\033[1;38;2;255;255;255m"; fg_lbl="\033[1;38;2;255;255;255m"; elif [ "${CURRENT_THEME:-}" != "cosmic_supernova" ] && [ "$c_mod" -eq 3 ]; then fg_key="\033[1;38;2;255;255;255m"; fg_lbl="\033[1;38;2;255;255;255m"; else fg_key="\033[1;38;2;0;0;0m"; fg_lbl="\033[1;38;2;0;0;0m"; fi; else fg_key="\033[1;38;2;255;255;255m"; fg_lbl="\033[1;38;2;255;255;255m"; fi; local rst="\033[0m" ptr="${ptr_col} ▶ ❯${rst}"; printf -v formatted_key "[%2s]" "$key"; local line_content="${bg}${fg_key} ${formatted_key} ${fg_lbl}${label}${rst}"; local raw_len=$(( 1 + ${#formatted_key} + 1 + ${#label} )); local target_w=$(( box_width - 6 )); local pad_len=$(( target_w - raw_len )); [ "$pad_len" -lt 1 ] && pad_len=1; local pad_spaces; printf -v pad_spaces '%*s' "$pad_len" ''; local line_out="${ptr}${line_content}${pad_spaces} ${rst}\033[K"; if [ -n "$_out_var" ]; then printf -v "$_out_var" "%s" "$line_out"; else printf "%b\n" "$line_out"; fi
}

_start_win_cursor_hider() {
if [ -n "${_WIN_CURSOR_HIDER_PID:-}" ] && kill -0 "$_WIN_CURSOR_HIDER_PID" 2>/dev/null; then return 0; fi; local _os="${OS_TYPE:-}"; if [ -z "$_os" ]; then case "$UNAME_S" in CYGWIN*|MINGW*|MSYS*) _os="windows" ;; esac; fi; [ "$_os" != "windows" ] && return 0; local py=""; if command -v python3 &>/dev/null; then py="python3"; elif command -v python &>/dev/null; then py="python"; else return 0; fi; local conf_dir="${HOME}/.config/mix-manager"; mkdir -p "$conf_dir" 2>/dev/null || true; rm -f "$conf_dir/console_size" 2>/dev/null || true; local hider_py="$conf_dir/win_cursor_hider.py"; 

cat <<'PY' > "$hider_py"
import ctypes, os, sys, time
k = ctypes.WinDLL("kernel32", use_last_error=True)

k.CreateFileW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint, ctypes.c_uint, ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint, ctypes.c_void_p]
k.CreateFileW.restype = ctypes.c_void_p
k.GetConsoleCursorInfo.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
k.GetConsoleCursorInfo.restype = ctypes.c_int
k.SetConsoleCursorInfo.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
k.SetConsoleCursorInfo.restype = ctypes.c_int
k.GetConsoleScreenBufferInfo.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
k.GetConsoleScreenBufferInfo.restype = ctypes.c_int
k.SetConsoleScreenBufferSize.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
k.SetConsoleScreenBufferSize.restype = ctypes.c_int

GENERIC_RW = 0x80000000 | 0x40000000
h = k.CreateFileW("CONOUT$", GENERIC_RW, 0x1 | 0x2, None, 3, 0, None)
invalid = ctypes.c_void_p(-1).value
if not h or h == invalid:
    sys.exit(0)

class COORD(ctypes.Structure):
    _fields_ = [("X", ctypes.c_short), ("Y", ctypes.c_short)]
class SMALL_RECT(ctypes.Structure):
    _fields_ = [("Left", ctypes.c_short), ("Top", ctypes.c_short),
                ("Right", ctypes.c_short), ("Bottom", ctypes.c_short)]
class CSBI(ctypes.Structure):
    _fields_ = [
        ("dwSize", COORD),
        ("dwCursorPosition", ctypes.c_ulong),
        ("wAttributes", ctypes.c_ushort),
        ("srWindow", SMALL_RECT),
        ("dwMaximumWindowSize", ctypes.c_ulong),
    ]
class CCI(ctypes.Structure):
    _fields_ = [("dwSize", ctypes.c_ulong), ("bVisible", ctypes.c_int)]

def _native_path(p):
    if os.name != "nt" or not p:
        return p
    if len(p) >= 4 and p[0] == "/" and p[2] == "/" and p[1].isalpha():
        return p[1].upper() + ":" + p[2:].replace("/", "\\")
    if p.startswith("/cygdrive/") and len(p) > 11 and p[10].isalpha() and p[11] == "/":
        return p[10].upper() + ":" + p[11:].replace("/", "\\")
    return p

info = CCI()
csbi = CSBI()
size_path = _native_path(os.environ.get("MP_WIN_SIZE_FILE") or "")
if ctypes.sizeof(csbi) != 22:
    size_path = ""
last = None

def publish():
    global last
    if not k.GetConsoleScreenBufferInfo(h, ctypes.byref(csbi)):
        return
    rows = int(csbi.srWindow.Bottom) - int(csbi.srWindow.Top) + 1
    cols = int(csbi.srWindow.Right) - int(csbi.srWindow.Left) + 1
    
    if rows < 1 or cols < 1:
        return

    # Match screen buffer size to window dimensions strictly on-demand during resize/maximization.
    # This permanently hides the scrollbar and blocks the mouse scroll wheel from bringing it back,
    # while leaving the loop unblocked so normal window scaling works fluidly.
    if (rows, cols) != last:
        coord = (rows << 16) | (cols & 0xFFFF)
        k.SetConsoleScreenBufferSize(h, coord)

    if (rows, cols) == last:
        return

    if size_path:
        for _ in range(5):
            try:
                tmp = "%s.%d" % (size_path, os.getpid())
                with open(tmp, "w", encoding="ascii", newline="\n") as fh:
                    fh.write("%d %d\n" % (rows, cols))
                os.replace(tmp, size_path)
                break
            except OSError:
                time.sleep(0.01)
            
    last = (rows, cols)

publish()
while True:
    if k.GetConsoleCursorInfo(h, ctypes.byref(info)) and info.bVisible:
        info.bVisible = 0
        k.SetConsoleCursorInfo(h, ctypes.byref(info))
    publish()
    time.sleep(0.04)
PY

MP_WIN_SIZE_FILE="$conf_dir/console_size" "$py" -u "$hider_py" &>/dev/null &
_WIN_CURSOR_HIDER_PID=$!
}

_stop_win_cursor_hider() {
local pid="${_WIN_CURSOR_HIDER_PID:-}"; _WIN_CURSOR_HIDER_PID=""; if [ -n "$pid" ]; then if [[ "$UNAME_S" =~ (MINGW|MSYS|CYGWIN) ]]; then local _win_pid; _win_pid=$(ps -W 2>/dev/null | awk -v p="$pid" '$1 == p {print $4; exit}'); if [[ "$_win_pid" =~ ^[0-9]+$ ]]; then MSYS_NO_PATHCONV=1 taskkill.exe /PID "$_win_pid" /F &>/dev/null || true; fi; fi; kill -9 "$pid" 2>/dev/null || true; fi
}
run_interactive_submenu() {
local menu_title="$1"; local menu_header="$2"; local -n _opts_ref="$3"; local cur_idx="${4:-0}"; local total_opts="${#_opts_ref[@]}"; command -v update_mp_bridge_menu &>/dev/null && update_mp_bridge_menu "${menu_title:-Main Console / Workstation Menu}" "true"; if [ "$total_opts" -eq 0 ]; then REPLY="0"; return 0; fi; local start_attempts=0; while [ "$start_attempts" -lt "$total_opts" ]; do IFS='|' read -r k_chk _ _ <<< "${_opts_ref[$cur_idx]}"; if [ "$k_chk" != "SECTION" ] && [ "$k_chk" != "SEP" ]; then break; fi; cur_idx=$(( (cur_idx + 1) % total_opts )); ((start_attempts++)); done; local -a selectable_map=(); local s_count=0; local i; for (( i=0; i<total_opts; i++ )); do IFS='|' read -r k_chk _ _ <<< "${_opts_ref[$i]}"; if [ "$k_chk" != "SECTION" ] && [ "$k_chk" != "SEP" ]; then selectable_map[i]=$s_count; ((s_count++)); else selectable_map[i]=-1; fi; done; _find_menu_search_match() { local q="${1,,}" start="${2:-0}" dir="${3:-1}"; [ -z "$q" ] && return 0; local step=0 idx="$start"; while [ "$step" -lt "$total_opts" ]; do local ok="" ol="" oe=""; IFS='|' read -r ok ol oe <<< "${_opts_ref[$idx]}"; if [ "$ok" != "SECTION" ] && [ "$ok" != "SEP" ]; then local haystack="${ok} ${ol} ${oe}"; haystack="${haystack,,}"; if [[ "$haystack" == *"$q"* ]]; then cur_idx=$idx; return 0; fi; fi; idx=$(( (idx + dir + total_opts) % total_opts )); ((step++)); done; return 1; }; if [ ! -t 0 ]; then clear; if [ -n "$menu_title" ]; then echo -e "${BOLD}${MAGENTA}${S70}${NC}\n${BOLD}${MAGENTA}       $menu_title${NC}\n${BOLD}${MAGENTA}${S70}${NC}"; elif [ -z "$menu_title" ] && [ -z "$menu_header" ] && command -v render_main_header &>/dev/null; then update_terminal_geometry 0; render_main_header "$(( _TERM_COLS - 4 ))" >/dev/null; menu_header="${_RENDERED_MAIN_HEADER:-}"; fi; [ -n "$menu_header" ] && echo -e "$menu_header"; if get_mp_audio_player_track_info 2>/dev/null; then local st_sym="${BOLD}${GREEN}▶ PLAYING${NC}"; [ "$MP_PLAYER_STATE" = "paused" ] && st_sym="${BOLD}${YELLOW}⏸ PAUSED${NC}"; local disp_title="$MP_PLAYER_TITLE"; [ ${#disp_title} -gt 40 ] && disp_title="${disp_title:0:37}..."; local p_hdr="♫ MP AUDIO PLAYER"; [ "$MP_PLAYER_MODE" = "MUSIC" ] && p_hdr="♫ MP AUDIO PLAYER [MUSIC MODE - TRACKS]"; local p_dashes=$(( 74 - ${#p_hdr} - 4 )); [ "$p_dashes" -lt 0 ] && p_dashes=0; local p_dash_str; printf -v p_dash_str '%*s' "$p_dashes" ''; p_dash_str="${p_dash_str// /─}"; echo -e "  ${BOLD}${MAGENTA}╭── ${p_hdr} ${p_dash_str}╮${NC}"; printf "  ${BOLD}${MAGENTA}│${NC} %b  ${BOLD}${YELLOW}%-40s${NC}  ${CYAN}%s/%s${NC} ${DIM}(%2s%%)${NC} ${BOLD}${MAGENTA}│\n" "$st_sym" "$disp_title" "$MP_PLAYER_POS_FMT" "$MP_PLAYER_DUR_FMT" "${MP_PLAYER_PROGRESS_PCT%.*}"; printf "  ${BOLD}${MAGENTA}│${NC}   ${DIM}EQ:${NC} %b  ${DIM}Controls: [Space] Toggle [L] Liquid [n] Next [</>] Track [p] UI [f] FM ${NC} ${BOLD}${MAGENTA}│\n" "${CYAN}${MP_PLAYER_MINI_EQ:-        }${NC}"; echo -e "  ${BOLD}${MAGENTA}╰──────────────────────────────────────────────────────────────────────────╯${NC}"; fi; for opt_entry in "${_opts_ref[@]}"; do IFS='|' read -r o_key o_label o_extra <<< "$opt_entry"; case "$o_key" in SECTION) echo -e "\n  ${BOLD}${BLUE}─── [ $o_label ] ─────────${NC}" ;; SEP) echo -e "  ${BOLD}${BLUE}──────────────────────────────────────────────────────────────────────────${NC}" ;; *) echo -e "  ${BOLD}${CYAN}$o_key)${NC} $o_label ${DIM}$o_extra${NC}" ;; esac; done; echo ""; run_deferred_startup; read -r -p "Enter choice: " REPLY; return 0; fi; update_terminal_geometry 0; local box_w; _set_menu_box_width box_w "${_TERM_COLS:-80}"; _CURRENT_BOX_W="$box_w"; _MENU_CURSOR_LOCK=1; local header_count=0; local cached_header_block=""; local cached_header_lines=0; local overhead=4
build_header_block() {
header_count=0; cached_header_block=""; cached_header_lines=0; local inner_w=$(( box_w - 2 )); local text_w=$(( box_w - 4 )); local h_border; printf -v h_border '%*s' "$inner_w" ''; h_border="${h_border// /─}"; if [ -n "$menu_title" ]; then cached_header_block+="  ${BOLD}${MAGENTA}╭${h_border}╮\033[K${NC}\n"; local title_line; printf -v title_line "  ${BOLD}${MAGENTA}│ %-${text_w}s │\033[K${NC}\n" "  ${menu_title}"; cached_header_block+="$title_line"; cached_header_block+="  ${BOLD}${MAGENTA}╰${h_border}╯\033[K${NC}\n"; cached_header_lines=$((cached_header_lines + 3)); fi; if [ -z "$menu_title" ] && command -v render_main_header &>/dev/null; then render_main_header "$box_w" >/dev/null; menu_header="${_RENDERED_MAIN_HEADER:-}"; fi; if [ -n "$menu_header" ]; then local exp_hdr=""; printf -v exp_hdr "%b" "$menu_header"; exp_hdr="${exp_hdr%$'\n'}"; while IFS= read -r h_line; do cached_header_block+="${h_line}\033[K\n"; ((header_count++)); done <<< "$exp_hdr"; cached_header_lines=$((cached_header_lines + header_count)); fi; if [ -n "$menu_title" ]; then cached_header_block+="  ${DIM}${BLUE}Use [↑/↓] Arrow Keys to navigate, [/] to search, [Enter] to select, [Esc] to return immediately\033[K${NC}\n"; else cached_header_block+="  ${DIM}${BLUE}Use [↑/↓] Arrow Keys to navigate, [/] to search, [Enter] to select, 'q' to exit\033[K${NC}\n"; fi; ((cached_header_lines++)); overhead=$((cached_header_lines + 4))
}
build_header_block
_compose_menu_status() {
local _out="$1"; local cur_key="" cur_lbl="" cur_ext=""; local line=""; IFS='|' read -r cur_key cur_lbl cur_ext <<< "${_opts_ref[$cur_idx]}"; if [ "${search_mode:-0}" -eq 1 ] || [ -n "${search_query:-}" ]; then line="  ${BOLD}${CYAN}Filter / Search:${NC} ${BOLD}${YELLOW}[${search_query}█]${NC} ▏ ${DIM}[Option ${cur_key}: ${cur_lbl}]${NC} ▏ ${DIM}(Type to search, ↑/↓ Navigate, Enter: Select, Esc: Clear)\033[K"; elif [ -n "$typed_buffer" ]; then if [ -n "$menu_title" ]; then line="  ${BOLD}${CYAN}Selection:${NC} ${BOLD}${YELLOW}${typed_buffer}${NC} ▏ ${DIM}(Press Enter to confirm, Esc to return)\033[K"; else line="  ${BOLD}${CYAN}Selection:${NC} ${BOLD}${YELLOW}${typed_buffer}${NC} ▏ ${DIM}(Press Enter to confirm, 'q' to exit)\033[K"; fi; else if [ -n "$menu_title" ]; then line="  ${BOLD}${CYAN}Selection:${NC} ${DIM}[Option ${cur_key}: ${cur_lbl}]${NC} ▏ ${DIM}[↑/↓ to Navigate, [/] to Search, Enter to Select, Esc to Return]\033[K"; else line="  ${BOLD}${CYAN}Selection:${NC} ${DIM}[Option ${cur_key}: ${cur_lbl}]${NC} ▏ ${DIM}[↑/↓ to Navigate, [/] to Search, Enter to Select, 'q' to Exit]\033[K"; fi; fi; printf -v "$_out" '%s' "$line"
}
_menu_line_plain() {
local idx="$1"; local _out="$2"; local o_key="" o_label="" o_extra=""; IFS='|' read -r o_key o_label o_extra <<< "${_opts_ref[$idx]}"; local key_formatted=""; printf -v key_formatted "[%2s]" "$o_key"; local extra_display=""; [ -n "$o_extra" ] && extra_display="  ${DIM}${o_extra}${NC}"; printf -v "$_out" '%s' "     ${BOLD}${CYAN}${key_formatted}${NC} ${o_label}${extra_display}\033[K"
}
_menu_fast_paint_selection() {
local old_idx="$1"; [ "${_menu_fast_ok:-0}" -eq 1 ] || return 1; [[ "${_TERM_LINES:-}" =~ ^[0-9]+$ ]] || return 1; [ "$_menu_status_row" -ge 1 ] && [ "$_menu_status_row" -lt "$_TERM_LINES" ] || return 1; [ "${_menu_item_row[$old_idx]:-0}" -ge 1 ] && [ "${_menu_item_row[$old_idx]}" -lt "$_TERM_LINES" ] || return 1; [ "${_menu_item_row[$cur_idx]:-0}" -ge 1 ] && [ "${_menu_item_row[$cur_idx]}" -lt "$_TERM_LINES" ] || return 1; [[ "${view_top:-}" =~ ^[0-9]+$ && "${view_end:-}" =~ ^[0-9]+$ ]] || return 1; [ -n "${_menu_item_row[$old_idx]:-}" ] || return 1; [ -n "${_menu_item_row[$cur_idx]:-}" ] || return 1; [ "$cur_idx" -ge "$view_top" ] && [ "$cur_idx" -le "$view_end" ] || return 1; [ "$old_idx" -ge "$view_top" ] && [ "$old_idx" -le "$view_end" ] || return 1; local plain sel status; _menu_line_plain "$old_idx" plain
IFS='|' read -r o_key o_label o_extra <<< "${_opts_ref[$cur_idx]}"; highlight_menu_line "$o_key" "$o_label" "$o_extra" "${selectable_map[$cur_idx]:-0}" sel "$box_w"; _compose_menu_status status; printf '\033[?25l\033[?12l\033[?7l\033[0m\033[%s;1H%b\033[0m\033[%s;1H%b\033[0m\033[%s;1H%b\r\033[?25l' "${_menu_item_row[$old_idx]}" "$plain" "${_menu_item_row[$cur_idx]}" "$sel" "${_menu_status_row}" "$status"; return 0
}
cleanup_submenu_screen() {
_MENU_CURSOR_LOCK=0; _stop_win_cursor_hider; printf '\033[?7h\033[?12h\033[?25h\033[?2026l'
}                                            
_MENU_CURSOR_LOCK=1; _start_win_cursor_hider; printf '\033[?25l\033[?12l\033[?7l'; local _last_menu_frame=""; local typed_buffer=""; local search_mode=0; local search_query=""; local view_top=0; local last_term_lines="$_TERM_LINES"; local _MENU_FRAME_FRESH=0; local _LAST_MENU_TICK_S="${SECONDS:-0}"; local -a _menu_item_row=(); local _menu_status_row=0; local _menu_fast_ok=0; local _ARROW_HOLD=0; local _LAST_NAV_TIME="${SECONDS:-0}" _BREATH_STEP=0 _BREATH_TICK_DIV=0 _IS_BREATHING=0; local -a _BREATH_FACTORS=(100 98 94 88 82 74 66 58 50 42 35 30 26 24 22 20 20 22 24 26 30 35 42 50 58 66 74 82 88 94 98 100); while true; do update_terminal_geometry 0; local cur_box_w; _set_menu_box_width cur_box_w "${_TERM_COLS:-80}"; local _draw=1; if [ "$cur_box_w" -eq "$box_w" ] && [ "$_TERM_LINES" -eq "$last_term_lines" ] && [ -n "$_last_menu_frame" ] && [ "${_MENU_FRAME_FRESH:-0}" -eq 1 ]; then _draw=0; fi; if [ "$_draw" -eq 0 ]; then printf '\033[?25l\033[?12l\033[?7l'; else if [ "$cur_box_w" -ne "$box_w" ] || [ "$_TERM_LINES" -ne "$last_term_lines" ]; then box_w="$cur_box_w"; last_term_lines="$_TERM_LINES"; _CURRENT_BOX_W="$box_w"; build_header_block; fi; local inner_w=$(( box_w - 2 )); local text_w=$(( box_w - 4 )); local h_border; printf -v h_border '%*s' "$inner_w" ''; h_border="${h_border// /─}"; local player_banner=""; local banner_lines=0; if get_mp_audio_player_track_info 2>/dev/null; then local st_color="$GREEN"; local st_icon="▶"; if [ "$MP_PLAYER_STATE" = "paused" ]; then st_color="$YELLOW"; st_icon="⏸"; fi; local st_low="$(printf "%s" "$MP_PLAYER_STATE" | tr "A-Z" "a-z")"; local st_sym="${BOLD}${st_color}${st_icon} ${st_low}${NC}"; local st_raw="${st_icon} ${st_low}"; if [ "${MP_PLAYER_RECORDING:-false}" = "true" ]; then st_sym+=" ${BOLD}${RED}● REC${NC}"; st_raw+=" ● REC"; fi; local p_mode_title="♫ MP AUDIO PLAYER"; [ "$MP_PLAYER_MODE" = "MUSIC" ] && p_mode_title="♫ MP AUDIO PLAYER [MUSIC MODE - TRACKS]"; local rem_dashes=$(( inner_w - ${#p_mode_title} - 4 )); [ "$rem_dashes" -lt 0 ] && rem_dashes=0; local p_top_dashes; printf -v p_top_dashes '%*s' "$rem_dashes" ''; p_top_dashes="${p_top_dashes// /─}"; player_banner+="  ${BOLD}${MAGENTA}╭── ${p_mode_title} ${p_top_dashes}╮\033[K${NC}\n"; local pos_pct_str="${MP_PLAYER_POS_FMT}/${MP_PLAYER_DUR_FMT} (${MP_PLAYER_PROGRESS_PCT%.*}%)"; local max_t_len=$(( text_w - ${#pos_pct_str} - 16 )); [ "$max_t_len" -lt 4 ] && max_t_len=4; [ "$max_t_len" -gt "$text_w" ] && max_t_len="$text_w"; local disp_title="$MP_PLAYER_TITLE"; if [ ${#disp_title} -gt "$max_t_len" ]; then disp_title="${disp_title:0:$((max_t_len - 3))}..."; fi; local l1_left="${st_sym}  ${BOLD}${YELLOW}${disp_title}${NC}"; local l1_right="${CYAN}${MP_PLAYER_POS_FMT}/${MP_PLAYER_DUR_FMT}${NC} ${DIM}(${MP_PLAYER_PROGRESS_PCT%.*}%)${NC}"; local raw_l1_len=$(( ${#st_raw} + 2 + ${#disp_title} + ${#pos_pct_str} )); local l1_pad=$(( text_w - raw_l1_len )); [ "$l1_pad" -lt 2 ] && l1_pad=2; local l1_sp
printf -v l1_sp '%*s' "$l1_pad" ''; player_banner+="  ${BOLD}${MAGENTA}│${NC} ${l1_left}${l1_sp}${l1_right} ${BOLD}${MAGENTA}│\033[K${NC}\n"; local line2_ctrl="[Space] Toggle  [M] Mini  [L] Liquid  [n] Next  [</>] Track  [p] UI  [f] FM"; local eq_disp="${CYAN}${MP_PLAYER_MINI_EQ:-        }${NC}"; local raw_l2_len=$(( 6 + 8 + 10 + ${#line2_ctrl} )); local l2_pad=$(( text_w - raw_l2_len )); [ "$l2_pad" -lt 2 ] && l2_pad=2; local l2_sp; printf -v l2_sp '%*s' "$l2_pad" ''; player_banner+="  ${BOLD}${MAGENTA}│${NC}   ${DIM}EQ:${NC} ${eq_disp}${l2_sp}${DIM}Controls: ${line2_ctrl}${NC} ${BOLD}${MAGENTA}│\033[K${NC}\n"; player_banner+="  ${BOLD}${MAGENTA}╰${h_border}╯\033[K${NC}\n"; banner_lines=4; fi; local effective_overhead=$(( overhead + banner_lines )); local max_visible=$(( _TERM_LINES - effective_overhead - 1 )); max_visible=$(( max_visible < 2 ? 2 : max_visible )); if [ "$max_visible" -ge "$total_opts" ]; then max_visible=$total_opts; view_top=0; else view_top=$(( cur_idx < view_top ? cur_idx : view_top )); view_top=$(( cur_idx >= view_top + max_visible ? cur_idx - max_visible + 1 : view_top )); view_top=$(( view_top > total_opts - max_visible ? total_opts - max_visible : view_top )); view_top=$(( view_top < 0 ? 0 : view_top )); fi; if [ "$cur_idx" -le 1 ]; then view_top=0; elif [ "$cur_idx" -gt 0 ]; then local _pk=""; IFS='|' read -r _pk _ _ <<< "${_opts_ref[$((cur_idx - 1))]}"; [ "$_pk" = "SECTION" ] && [ "$((cur_idx - 1))" -lt "$view_top" ] && view_top=$((cur_idx - 1)); fi; local view_end=$(( view_top + max_visible - 1 )); [ "$view_end" -ge "$total_opts" ] && view_end=$(( total_opts - 1 )); local frame_buf="$cached_header_block"; [ -n "$player_banner" ] && frame_buf+="$player_banner"; _menu_item_row=(); _menu_fast_ok=0; local _menu_row=$(( cached_header_lines + banner_lines + 2 )); if [ "$view_top" -gt 0 ]; then frame_buf+="  ${BOLD}${YELLOW}▲  (${view_top} more option$([ "$view_top" -gt 1 ] && echo "s") above - press ↑ to scroll)\033[K${NC}\n"; else frame_buf+="\033[K\n"; fi; local idx; for (( idx=view_top; idx<=view_end; idx++ )); do _menu_item_row[$idx]=$((_menu_row++)); IFS='|' read -r o_key o_label o_extra <<< "${_opts_ref[$idx]}"; if [ "$o_key" = "SECTION" ]; then local sec_rem=$(( inner_w - ${#o_label} - 8 )); [ "$sec_rem" -lt 4 ] && sec_rem=4; local sec_dashes; printf -v sec_dashes '%*s' "$sec_rem" ''; sec_dashes="${sec_dashes// /─}"; frame_buf+="  ${BOLD}${BLUE}─── [ ${o_label} ] ${sec_dashes}\033[K${NC}\n"; continue; elif [ "$o_key" = "SEP" ]; then frame_buf+="  ${BOLD}${BLUE}${h_border}\033[K${NC}\n"; continue; fi; if [ "$idx" -eq "$cur_idx" ]; then local sel_color_idx="${selectable_map[$cur_idx]:-0}"; local h_line=""; highlight_menu_line "$o_key" "$o_label" "$o_extra" "$sel_color_idx" h_line "$box_w"; frame_buf+="${h_line}\n"; else local key_formatted; printf -v key_formatted "[%2s]" "$o_key"; local key_display="${BOLD}${CYAN}${key_formatted}${NC}"; local label_display="${o_label}"; local extra_display=""; [ -n "$o_extra" ] && extra_display="  ${DIM}${o_extra}${NC}"
frame_buf+="     ${key_display} ${label_display}${extra_display}\033[K\n"; fi; done; _menu_status_row=$((_menu_row + 2)); _menu_fast_ok=1; local remaining_below=$(( total_opts - 1 - view_end )); if [ "$remaining_below" -gt 0 ]; then frame_buf+="  ${BOLD}${YELLOW}▼  (${remaining_below} more option$([ "$remaining_below" -gt 1 ] && echo "s") below - press ↓ to scroll)\033[K${NC}\n"; else frame_buf+="\033[K\n"; fi; frame_buf+="  ${BOLD}${BLUE}${h_border}\033[K${NC}\n"; local _status_line=""; _compose_menu_status _status_line; frame_buf+="$_status_line"; if [ "$frame_buf" != "$_last_menu_frame" ]; then _last_menu_frame="$frame_buf"; printf '\033[?25l\033[?12l\033[?7l\033[H%b\033[J\r\033[?25l' "$frame_buf"; else printf '\033[?25l\033[?12l\033[?7l'; fi; if [ "${STARTUP_AUTOPLAY_EXECUTED:-0}" -eq 0 ]; then run_deferred_startup; fi; _MENU_FRAME_FRESH=1; fi; if [ "${_ARROW_HOLD:-0}" -eq 1 ]; then _discard_buffered_vertical_arrows; _ARROW_HOLD=0; fi; local key_action=""; read_nav_key key_action; if [ "$key_action" != "TICK" ]; then _MENU_FRAME_FRESH=0; _LAST_NAV_TIME="${SECONDS:-0}"; if [ "$_IS_BREATHING" -eq 1 ]; then _IS_BREATHING=0; _BREATH_STEP=0; _BREATH_TICK_DIV=0; fi; fi; case "$key_action" in TOGGLE_FULLSCREEN) toggle_manager_fullscreen; _TERM_RESIZED=1; last_term_lines=0; _last_menu_frame=""; printf '\033[?25l\033[?12l\033[?7l'; continue ;; 

RESIZE) 
    # Force full geometry re-evaluation
    update_terminal_geometry 1
    _TERM_RESIZED=0
    last_term_lines=0
    _last_menu_frame=""
    cached_header_block=""
    
    # Re-evaluate box widths and headers immediately
    if declare -F _set_menu_box_width >/dev/null; then
        _set_menu_box_width box_w "${_TERM_COLS:-80}"
        _CURRENT_BOX_W="$box_w"
    fi
    if declare -F build_header_block >/dev/null; then
        build_header_block
    fi
    printf '\033[2J\033[H\033[?25l\033[?12l\033[?7l'
    continue ;; 
TICK) 
    local _now_s="${SECONDS:-0}"
    # Continuously check for pending resizes on every tick to catch window drags/maximizations instantly
    if _resize_pending; then
        update_terminal_geometry 1
        _TERM_RESIZED=0
        last_term_lines=0
        _last_menu_frame=""
        cached_header_block=""
        if declare -F _set_menu_box_width >/dev/null; then
            _set_menu_box_width box_w "${_TERM_COLS:-80}"
            _CURRENT_BOX_W="$box_w"
        fi
        if declare -F build_header_block >/dev/null; then
            build_header_block
        fi
        printf '\033[2J\033[H\033[?25l\033[?12l\033[?7l'
    fi
    if [ "$_now_s" != "${_LAST_MENU_TICK_S:-}" ]; then 
        _LAST_MENU_TICK_S="$_now_s"
        update_terminal_geometry 0
        if [ -z "$menu_title" ]; then 
            load_header_cache 2>/dev/null || true
            build_header_block
            maybe_spawn_header_refresh
            _maybe_refresh_perf_cache
        fi
        _MENU_FRAME_FRESH=0
    fi ; local _idle_time=$(( _now_s - _LAST_NAV_TIME )); if [ "$_idle_time" -ge 10 ] && [ "${search_mode:-0}" -ne 1 ] && [ -z "${typed_buffer:-}" ]; then _IS_BREATHING=1; ((_BREATH_TICK_DIV++)); if [ "$_BREATH_TICK_DIV" -ge 2 ]; then _BREATH_TICK_DIV=0; _BREATH_STEP=$(( (_BREATH_STEP + 1) % 32 )); local cur_f="${_BREATH_FACTORS[_BREATH_STEP]}"; if [ "${_menu_item_row[$cur_idx]:-0}" -ge 1 ] && [ "${_menu_item_row[$cur_idx]}" -lt "$_TERM_LINES" ]; then local o_key="" o_label="" o_extra="" sel_breath=""; IFS='|' read -r o_key o_label o_extra <<< "${_opts_ref[$cur_idx]}"; highlight_menu_line "$o_key" "$o_label" "$o_extra" "${selectable_map[$cur_idx]:-0}" sel_breath "$box_w" "$cur_f"; printf '\033[?25l\033[%s;1H%b\r\033[?25l' "${_menu_item_row[$cur_idx]}" "$sel_breath"; fi; fi; elif [ "$_IS_BREATHING" -eq 1 ]; then _IS_BREATHING=0; _BREATH_STEP=0; _BREATH_TICK_DIV=0; if [ "${_menu_item_row[$cur_idx]:-0}" -ge 1 ] && [ "${_menu_item_row[$cur_idx]}" -lt "$_TERM_LINES" ]; then local o_key="" o_label="" o_extra="" sel_restored=""; IFS='|' read -r o_key o_label o_extra <<< "${_opts_ref[$cur_idx]}"; highlight_menu_line "$o_key" "$o_label" "$o_extra" "${selectable_map[$cur_idx]:-0}" sel_restored "$box_w" 100; printf '\033[?25l\033[%s;1H%b\r\033[?25l' "${_menu_item_row[$cur_idx]}" "$sel_restored"; fi; fi; continue ;; CHAR:/) if [ "$search_mode" -eq 1 ]; then search_query+="/"; _find_menu_search_match "$search_query" 0 1; else search_mode=1; search_query=""; typed_buffer=""; fi; _MENU_FRAME_FRESH=0; continue ;; SPACE) if [ "$search_mode" -eq 1 ]; then search_query+=" "; _find_menu_search_match "$search_query" 0 1; _MENU_FRAME_FRESH=0; continue; fi; toggle_mp_audio_player; _MENU_FRAME_FRESH=0; continue ;; CHAR:m|CHAR:M) if [ "$search_mode" -eq 1 ]; then search_query+="${key_action#CHAR:}"; _find_menu_search_match "$search_query" 0 1; _MENU_FRAME_FRESH=0; continue; fi; launch_mp_audio_player_window; _MENU_FRAME_FRESH=0; continue ;; CHAR:l|CHAR:L) if [ "$search_mode" -eq 1 ]; then search_query+="${key_action#CHAR:}"; _find_menu_search_match "$search_query" 0 1; _MENU_FRAME_FRESH=0; continue; fi; launch_mp_audio_player_liquid_glass >/dev/null 2>&1; _MENU_FRAME_FRESH=0; continue ;; CHAR:z|CHAR:Z) if [ "$search_mode" -eq 1 ]; then search_query+="${key_action#CHAR:}"; _find_menu_search_match "$search_query" 0 1; _MENU_FRAME_FRESH=0; continue; fi; launch_mp_liquid_visualizer >/dev/null 2>&1; _MENU_FRAME_FRESH=0; continue ;;
CHAR:K) if [ "$search_mode" -eq 1 ]; then search_query+="K"; _find_menu_search_match "$search_query" 0 1; _MENU_FRAME_FRESH=0; continue; fi; pkill -9 -f "MP_Audio_Player" 2>/dev/null || true; rm -f "${HOME}/.config/mix-manager/mp_player.pid" "${HOME}/.config/mix-manager/mp_audio_player.port" "${HOME}/.config/mix-manager/mp_audio_player.sock" 2>/dev/null || true; _CACHED_PLAYER_CHECK_TIME=0; _CACHED_PLAYER_ACTIVE_RES=1; MP_PLAYER_RUNNING=0; MP_PLAYER_STATE="stopped"; typed_buffer=""; _last_menu_frame=""; _MENU_FRAME_FRESH=0; continue ;;
CHAR:n|CHAR:N|CHAR:\>|CHAR:\])
if [ "$search_mode" -eq 1 ]; then search_query+="n"; _find_menu_search_match "$search_query" 0 1; _MENU_FRAME_FRESH=0; continue; fi; local mp_py="$SCRIPT_DIR/MP_Audio_Player.py"; [ ! -f "$mp_py" ] && mp_py="$SCRIPT_DIR/scripts/MP_Audio_Player.py"; [ -f "$mp_py" ] && python3 "$mp_py" --next &>/dev/null &
;;
CHAR:\<|CHAR:\[)
if [ "$search_mode" -eq 1 ]; then search_query+="["; _find_menu_search_match "$search_query" 0 1; _MENU_FRAME_FRESH=0; continue; fi; local mp_py="$SCRIPT_DIR/MP_Audio_Player.py"; [ ! -f "$mp_py" ] && mp_py="$SCRIPT_DIR/scripts/MP_Audio_Player.py"; [ -f "$mp_py" ] && python3 "$mp_py" --prev &>/dev/null &
;;
CHAR:+|CHAR:=)
if [ "$search_mode" -eq 1 ]; then search_query+="+"; _find_menu_search_match "$search_query" 0 1; _MENU_FRAME_FRESH=0; continue; fi; local mp_py="$SCRIPT_DIR/MP_Audio_Player.py"; [ ! -f "$mp_py" ] && mp_py="$SCRIPT_DIR/scripts/MP_Audio_Player.py"; [ -f "$mp_py" ] && python3 "$mp_py" --pitch-up &>/dev/null &
;; CHAR:-|CHAR:_) if [ "$search_mode" -eq 1 ]; then search_query+="-"; _find_menu_search_match "$search_query" 0 1; _MENU_FRAME_FRESH=0; continue; fi; local mp_py="$SCRIPT_DIR/MP_Audio_Player.py"; [ ! -f "$mp_py" ] && mp_py="$SCRIPT_DIR/scripts/MP_Audio_Player.py"; [ -f "$mp_py" ] && python3 "$mp_py" --pitch-down &>/dev/null &
;; CHAR:0) if [ "$search_mode" -eq 1 ]; then search_query+="0"; _find_menu_search_match "$search_query" 0 1; _MENU_FRAME_FRESH=0; continue; fi; local has_exact_0=0; for opt_entry in "${_opts_ref[@]}"; do IFS='|' read -r o_key _ _ <<< "$opt_entry"; if [ "$o_key" = "0" ]; then has_exact_0=1; break; fi; done; if [ "$has_exact_0" -eq 1 ]; then cleanup_submenu_screen; clear; REPLY="0"; return 0; fi; local mp_py="$SCRIPT_DIR/MP_Audio_Player.py"; [ ! -f "$mp_py" ] && mp_py="$SCRIPT_DIR/scripts/MP_Audio_Player.py"; [ -f "$mp_py" ] && python3 "$mp_py" --pitch-reset &>/dev/null &
;; UP) if [ "$search_mode" -eq 1 ] && [ -n "$search_query" ]; then _find_menu_search_match "$search_query" $(( (cur_idx - 1 + total_opts) % total_opts )) -1; _MENU_FRAME_FRESH=0; continue; fi; local old_idx="$cur_idx"; local hops=0; while [ "$hops" -lt "$total_opts" ]; do cur_idx=$(( (cur_idx - 1 + total_opts) % total_opts )); IFS='|' read -r k_chk _ _ <<< "${_opts_ref[$cur_idx]}"; [ "$k_chk" != "SECTION" ] && [ "$k_chk" != "SEP" ] && break; ((hops++)); done; typed_buffer=""; if [ "$old_idx" -ne "$cur_idx" ] && _menu_fast_paint_selection "$old_idx"; then _MENU_FRAME_FRESH=1; fi; _ARROW_HOLD=1; _NAV_ARROW_AT="${EPOCHREALTIME:-0}"; ;; PAGE_UP) local hops=0; local target_step=$(( max_visible > 5 ? max_visible - 2 : 5 )); while [ "$hops" -lt "$target_step" ]; do cur_idx=$(( (cur_idx - 1 + total_opts) % total_opts )); IFS='|' read -r k_chk _ _ <<< "${_opts_ref[$cur_idx]}"; if [ "$k_chk" != "SECTION" ] && [ "$k_chk" != "SEP" ]; then ((hops++)); fi; done; typed_buffer=""; ;; DOWN) if [ "$search_mode" -eq 1 ] && [ -n "$search_query" ]; then _find_menu_search_match "$search_query" $(( (cur_idx + 1) % total_opts )) 1; _MENU_FRAME_FRESH=0; continue; fi; local old_idx="$cur_idx"; local hops=0; while [ "$hops" -lt "$total_opts" ]; do cur_idx=$(( (cur_idx + 1) % total_opts )); IFS='|' read -r k_chk _ _ <<< "${_opts_ref[$cur_idx]}"; [ "$k_chk" != "SECTION" ] && [ "$k_chk" != "SEP" ] && break; ((hops++)); done; typed_buffer=""; if [ "$old_idx" -ne "$cur_idx" ] && _menu_fast_paint_selection "$old_idx"; then _MENU_FRAME_FRESH=1; fi; _ARROW_HOLD=1; _NAV_ARROW_AT="${EPOCHREALTIME:-0}"; ;; PAGE_DOWN) local hops=0; local target_step=$(( max_visible > 5 ? max_visible - 2 : 5 )); while [ "$hops" -lt "$target_step" ]; do cur_idx=$(( (cur_idx + 1) % total_opts )); IFS='|' read -r k_chk _ _ <<< "${_opts_ref[$cur_idx]}"; if [ "$k_chk" != "SECTION" ] && [ "$k_chk" != "SEP" ]; then ((hops++)); fi; done; typed_buffer=""; ;; HOME) cur_idx=0; while [ "$cur_idx" -lt "$total_opts" ]; do IFS='|' read -r k_chk _ _ <<< "${_opts_ref[$cur_idx]}"; [ "$k_chk" != "SECTION" ] && [ "$k_chk" != "SEP" ] && break; ((cur_idx++)); done; typed_buffer="" ;; END) cur_idx=$(( total_opts - 1 )); while [ "$cur_idx" -ge 0 ]; do IFS='|' read -r k_chk _ _ <<< "${_opts_ref[$cur_idx]}"; [ "$k_chk" != "SECTION" ] && [ "$k_chk" != "SEP" ] && break; ((cur_idx--)); done; typed_buffer=""; ;; ENTER) cleanup_submenu_screen; clear; if [ "$search_mode" -eq 1 ] || [ -n "$search_query" ]; then IFS='|' read -r sel_key _ _ <<< "${_opts_ref[$cur_idx]}"; REPLY="$sel_key"; elif [ -n "$typed_buffer" ]; then REPLY="$typed_buffer"; else IFS='|' read -r sel_key _ _ <<< "${_opts_ref[$cur_idx]}"; REPLY="$sel_key"; fi; return 0 ;; ESC) if [ "$search_mode" -eq 1 ] || [ -n "$search_query" ]; then search_mode=0; search_query=""; _MENU_FRAME_FRESH=0; continue; fi; cleanup_submenu_screen; clear; REPLY="ESC"; return 0 ;; BACKSPACE) if [ "$search_mode" -eq 1 ]; then search_query="${search_query%?}"; if [ -n "$search_query" ]; then _find_menu_search_match "$search_query" 0 1; fi; _MENU_FRAME_FRESH=0; continue; fi; typed_buffer="${typed_buffer%?}"; ;; CHAR:*) local ch="${key_action#CHAR:}"; if [ "$search_mode" -eq 1 ]; then search_query+="$ch"; _find_menu_search_match "$search_query" 0 1; _MENU_FRAME_FRESH=0; continue; fi; if [ "${_NAV_WIN_CON:-0}" -eq 1 ] && [[ "$ch" == "A" || "$ch" == "B" ]] && _nav_just_arrowed; then continue; fi; if [ -z "$typed_buffer" ] && ([ "$ch" = "p" ] || [ "$ch" = "P" ]); then local has_exact_p=0; for opt_entry in "${_opts_ref[@]}"; do IFS='|' read -r o_key _ _ <<< "$opt_entry"; if [ "$o_key" = "p" ] || [ "$o_key" = "P" ]; then has_exact_p=1; break; fi; done; if [ "$has_exact_p" -eq 0 ]; then cleanup_submenu_screen; manage_mp_audio_player; _MENU_CURSOR_LOCK=1; _start_win_cursor_hider; printf '\033[?25l\033[?12l\033[?7l'; clear; continue; fi; fi; if [ -z "$typed_buffer" ] && ([ "$ch" = "f" ] || [ "$ch" = "F" ]) && [ "${MP_PLAYER_ACTIVE:-0}" -eq 1 ]; then local has_exact_f=0; for opt_entry in "${_opts_ref[@]}"; do IFS='|' read -r o_key _ _ <<< "$opt_entry"; if [ "$o_key" = "f" ] || [ "$o_key" = "F" ]; then has_exact_f=1; break; fi; done; if [ "$has_exact_f" -eq 0 ]; then local mp_py="$SCRIPT_DIR/MP_Audio_Player.py"; [ ! -f "$mp_py" ] && mp_py="$SCRIPT_DIR/scripts/MP_Audio_Player.py"; [ -f "$mp_py" ] && python3 "$mp_py" --open-file-manager &>/dev/null &
continue; fi; fi; typed_buffer+="$ch"; local m_idx=0; for opt_entry in "${_opts_ref[@]}"; do IFS='|' read -r o_key _ _ <<< "$opt_entry"; if [ "$o_key" = "$typed_buffer" ]; then cur_idx=$m_idx; break; fi; ((m_idx++)); done; if [ "$typed_buffer" = "q" ] || [ "$typed_buffer" = "Q" ] || [ "$typed_buffer" = "b" ] || [ "$typed_buffer" = "B" ]; then cleanup_submenu_screen; clear; REPLY="$typed_buffer"; return 0; fi ;; esac; done
}
load_theme() {
local theme_file="$HOME/.config/mix-manager/theme"; if [ -f "$theme_file" ]; then local saved_theme; saved_theme="$(tr -d ' \t\n\r' < "$theme_file" 2>/dev/null)"; if [ -n "$saved_theme" ]; then set_theme_colors "$saved_theme"; _ensure_konsole_default_scheme; return; fi; fi; set_theme_colors "dreamworlds"; _ensure_konsole_default_scheme
}
_ensure_konsole_default_scheme() {
if [ -n "$KONSOLE_VERSION" ] || [ -n "$KONSOLE_DBUS_SERVICE" ]; then
    local def_prof="" def_scheme="WhiteOnBlack"
    if [ -f "$HOME/.config/konsolerc" ]; then
        def_prof=$(grep -E "^DefaultProfile=" "$HOME/.config/konsolerc" 2>/dev/null | cut -d= -f2 | tr -d ' \r\n')
    fi
    if [ -n "$def_prof" ] && [ -f "$HOME/.local/share/konsole/$def_prof" ]; then
        def_scheme=$(grep -E "^ColorScheme=" "$HOME/.local/share/konsole/$def_prof" 2>/dev/null | cut -d= -f2 | tr -d ' \r\n')
    fi
    printf '\033]50;ColorScheme=%s\a\033]111\007\033]110\007' "${def_scheme:-WhiteOnBlack}" 2>/dev/null || true
fi
}
save_theme() {
local new_theme="$1"; mkdir -p "$HOME/.config/mix-manager" 2>/dev/null; echo "$new_theme" > "$HOME/.config/mix-manager/theme" 2>/dev/null; set_theme_colors "$new_theme"; if [ "$new_theme" = "dreamworlds" ] || [ "$new_theme" = "mplanetarian_dreamworlds" ] || [ "$new_theme" = "default" ] || [ "$new_theme" = "dreamworlds_ultra" ] || [ "$new_theme" = "cosmic_supernova" ] || [ "$new_theme" = "dreamworlds_liquid" ] || [ "$new_theme" = "dynamic_rainbow_liquid_glass" ]; then play_sound_effect "dreamworlds"; fi; _sync_btop_theme "$new_theme"
}
_sync_btop_theme() {
local th="${1:-$CURRENT_THEME}" tn="" bd="$HOME/.config/btop"; [ "$th" = "dreamworlds_ultra" ] && tn="Dreamworlds_Ultra_MP_Mix_Manager"; [ "$th" = "cosmic_supernova" ] && tn="Cosmic_Supernova_MP_Mix_Manager"; [ -z "$tn" ] || [ ! -d "$bd" ] && return 0; mkdir -p "$bd/themes" 2>/dev/null; [ -f "$SCRIPT_DIR/themes/${tn}.theme" ] && cp -p "$SCRIPT_DIR/themes/${tn}.theme" "$bd/themes/" 2>/dev/null; [ -f "$bd/btop.conf" ] && sed -i "s|^color_theme = .*|color_theme = \"${tn}\"|" "$bd/btop.conf" 2>/dev/null
}
load_theme; _STOP_AUDIO_ON_EXIT=0; _MP_AUDIO_DAEMON_STOPPED=0
_mp_player_pid_alive() {
local pid="$1"; local comm=""; if [[ "$UNAME_S" =~ (MINGW|MSYS|CYGWIN) ]]; then comm=$(ps -W 2>/dev/null | awk -v pid="$pid" '$4 == pid {print $NF; found=1; exit} END {exit !found}') || return 1; else kill -0 "$pid" 2>/dev/null || return 1; return 0; fi; case "$comm" in *[Pp]ython*) return 0 ;; *) return 1 ;; esac
}
is_liquid_glass_open() {
    if pgrep -f "MP_Audio_Player_Liquid_Glass|MP_Liquid_Visualizer|mp_liquid_visualizer_vulkan" &>/dev/null; then
        return 0
    fi
    if command -v wmctrl &>/dev/null; then
        if wmctrl -l 2>/dev/null | grep -iE "Liquid Glass|MP_Liquid_Visualizer" &>/dev/null; then
            return 0
        fi
    fi
    return 1
}
is_liquid_glass_pid() {
    local check_pid="$1"
    [ -z "$check_pid" ] && return 1
    local cmdline=""
    cmdline="$(ps -p "$check_pid" -o command= 2>/dev/null || true)"
    case "$cmdline" in
        *MP_Audio_Player_Liquid_Glass*|*liquid_glass*|*liquid-glass*|*MP_Liquid_Visualizer*|*mp_liquid_visualizer_vulkan*)
            return 0
            ;;
    esac
    local lg_pids
    lg_pids="$(pgrep -f "MP_Audio_Player_Liquid_Glass|MP_Liquid_Visualizer|mp_liquid_visualizer_vulkan" 2>/dev/null || true)"
    if [ -n "$lg_pids" ]; then
        for lp in $lg_pids; do
            [ "$check_pid" -eq "$lp" ] && return 0
            if pgrep -P "$lp" 2>/dev/null | grep -q "^${check_pid}$"; then
                return 0
            fi
        done
    fi
    return 1
}
_stop_mp_audio_daemon() {
    local force=0
    [ "${1:-}" = "--force" ] && force=1
    if [ "$force" -eq 0 ] && type is_liquid_glass_open &>/dev/null && is_liquid_glass_open; then
        return 0
    fi
    save_playback_resume_state 2>/dev/null || true
    if [ -n "${_AUTOPLAY_PID:-}" ]; then
        if [[ "$UNAME_S" =~ (MINGW|MSYS|CYGWIN) ]]; then
            local _ap_win=""
            _ap_win=$(ps -W 2>/dev/null | awk -v pid="$_AUTOPLAY_PID" '$1 == pid {print $4; exit}')
            if [[ "$_ap_win" =~ ^[0-9]+$ ]]; then
                MSYS_NO_PATHCONV=1 taskkill.exe /PID "$_ap_win" /T /F &>/dev/null || true
            else
                kill "$_AUTOPLAY_PID" 2>/dev/null || true
            fi
        else
            kill -TERM "$_AUTOPLAY_PID" 2>/dev/null || true
            kill -KILL "$_AUTOPLAY_PID" 2>/dev/null || true
        fi
        _AUTOPLAY_PID=""
    fi
    local pid_file="${HOME}/.config/mix-manager/mp_player.pid"
    local port_file="${HOME}/.config/mix-manager/mp_audio_player.port"
    local sock_file="${HOME}/.config/mix-manager/mp_audio_player.sock"
    local state_file="${HOME}/.config/mix-manager/mp_player_state.json"
    local s4_pid_file="${HOME}/.config/mix-manager/traktor_s4_midi.pid"
    local port=""
    [ -f "$port_file" ] && IFS= read -r port < "$port_file" 2>/dev/null || true
    local py=""
    if command -v python3 &>/dev/null; then py="python3"
    elif command -v python &>/dev/null; then py="python"; fi
    if [ -n "$py" ]; then
        MP_STOP_PORT="$port" MP_STOP_SOCK="$sock_file" "$py" - &>/dev/null << 'PY' || true
import os, socket
sent = False
sock_path = os.environ.get("MP_STOP_SOCK", "")
if sock_path and os.path.exists(sock_path) and hasattr(socket, "AF_UNIX"):
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(0.5)
        s.connect(sock_path)
        s.sendall(b'{"cmd":"stop"}')
        try:
            s.recv(1024)
        except Exception:
            pass
        s.close()
        sent = True
    except Exception:
        pass
if not sent:
    try:
        port = int(os.environ.get("MP_STOP_PORT", "0"))
        if port > 0:
            sock = socket.create_connection(("127.0.0.1", port), 0.5)
            sock.settimeout(0.5)
            sock.sendall(b'{"cmd":"stop"}')
            try:
                sock.recv(1024)
            except Exception:
                pass
            sock.close()
    except Exception:
        pass
PY
    fi
    if [ -f "$pid_file" ]; then
        local pid=""
        IFS= read -r pid < "$pid_file" 2>/dev/null || true
        if [[ "$pid" =~ ^[0-9]+$ ]]; then
            if [[ "$UNAME_S" =~ (MINGW|MSYS|CYGWIN) ]]; then
                MSYS_NO_PATHCONV=1 taskkill.exe /PID "$pid" /F &>/dev/null || true
            else
                kill -TERM "$pid" 2>/dev/null || true
                kill -KILL "$pid" 2>/dev/null || true
            fi
        fi
    fi
    if [ -f "$s4_pid_file" ]; then
        local s4_pid=""
        IFS= read -r s4_pid < "$s4_pid_file" 2>/dev/null || true
        if [[ "$s4_pid" =~ ^[0-9]+$ ]]; then
            kill -TERM "$s4_pid" 2>/dev/null || true
            kill -KILL "$s4_pid" 2>/dev/null || true
        fi
        rm -f "$s4_pid_file" 2>/dev/null || true
    fi
    if [[ "$UNAME_S" =~ (MINGW|MSYS|CYGWIN) ]]; then
        powershell.exe -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { \$_.CommandLine -like '*MP_Audio_Player*' -or \$_.CommandLine -like '*mp_audio_player*' } | ForEach-Object { Stop-Process -Id \$_.ProcessId -Force }" &>/dev/null || true
        taskkill.exe /F /FI "WINDOWTITLE eq MP Audio Player*" &>/dev/null || true
        taskkill.exe /F /FI "WINDOWTITLE eq MP Mini Audio Player*" &>/dev/null || true
        taskkill.exe /F /FI "WINDOWTITLE eq MP Micro Audio Player*" &>/dev/null || true
    else
        local cur_pid="$$" cur_bpid="${BASHPID:-$$}" mgr_pid="${MANAGER_MAIN_PID:-0}"
        local _pids_to_kill=()
        local _raw_pids=""
        _raw_pids="$(pgrep -i -f "MP_Audio_Player" 2>/dev/null; pgrep -i -f "mp_audio_player" 2>/dev/null; ps -eo pid,command 2>/dev/null | grep -iE '(MP_Audio_Player|mp_audio_player)' | grep -v grep | awk '{print $1}')"
        if [ -n "$_raw_pids" ]; then
            local _uniq_pids
            _uniq_pids=$(printf '%s\n' "$_raw_pids" | tr ' ' '\n' | grep -E '^[0-9]+$' | sort -u)
            for p in $_uniq_pids; do
                [ "$p" -le 1 ] && continue
                [ "$p" -eq "$cur_pid" ] && continue
                [ "$p" -eq "$cur_bpid" ] && continue
                [ "$p" -eq "$mgr_pid" ] && continue
                _pids_to_kill+=("$p")
            done
        fi
        for p in "${_pids_to_kill[@]}"; do
            kill -TERM "$p" 2>/dev/null || true
        done
        pkill -i -f "MP_Audio_Player" 2>/dev/null || true
        pkill -i -f "mp_audio_player" 2>/dev/null || true
        pkill -f "pactl subscribe" 2>/dev/null || true
        sleep 0.1
        for p in "${_pids_to_kill[@]}"; do
            if kill -0 "$p" 2>/dev/null; then
                kill -KILL "$p" 2>/dev/null || true
            fi
        done
        pkill -9 -i -f "MP_Audio_Player" 2>/dev/null || true
        pkill -9 -i -f "mp_audio_player" 2>/dev/null || true
        pkill -9 -f "pactl subscribe" 2>/dev/null || true
        if command -v wmctrl >/dev/null 2>&1; then
            wmctrl -lp 2>/dev/null | while read -r win_id desktop_num win_pid host win_title; do
                if [[ "$win_title" == *"MP Audio Player"* || "$win_title" == *"MP Mini Audio Player"* || "$win_title" == *"MP Micro Audio Player"* ]]; then
                    wmctrl -c "$win_id" 2>/dev/null || true
                fi
            done
        fi
    fi
    rm -f "$pid_file" "$port_file" "$sock_file" 2>/dev/null || true
    if [ -f "$state_file" ] && [ -n "$py" ]; then
        "$py" -c '
import json, sys
sf = sys.argv[1]
try:
    with open(sf, "r", encoding="utf-8") as f: d = json.load(f)
    if isinstance(d, dict):
        d["running"] = False
        d["state"] = "stopped"
        with open(sf, "w", encoding="utf-8") as f: json.dump(d, f)
except Exception:
    with open(sf, "w", encoding="utf-8") as f: f.write("{\"running\": false, \"state\": \"stopped\"}\n")
' "$state_file" 2>/dev/null || printf '%s\n' '{"running": false, "state": "stopped"}' > "$state_file" 2>/dev/null || true
    else
        printf '%s\n' '{"running": false, "state": "stopped"}' > "$state_file" 2>/dev/null || true
    fi
}
kill_all_mp_audio_players() {
    local force=0
    [ "${1:-}" = "--force" ] && force=1
    if [ "$force" -eq 0 ] && type is_liquid_glass_open &>/dev/null && is_liquid_glass_open; then
        return 0
    fi
    _stop_mp_audio_daemon "$@"
}
update_mp_bridge_menu() {
local cur_m="${1:-Main Console / Workstation Menu}" is_r="${2:-true}" br_sh="$SCRIPT_DIR/mp_software_bridge.sh" br_py="$SCRIPT_DIR/scripts/mp_software_bridge.py"
if [ -x "$br_sh" ]; then "$br_sh" update-menu --menu "$cur_m" --running "$is_r" --pid "$$" &>/dev/null &
elif [ -f "$br_py" ]; then (python3 "$br_py" update-menu --menu "$cur_m" --running "$is_r" --pid "$$" &>/dev/null &)
fi
}
update_mp_bridge_action() {
local act="$1" cat="${2:-operation}" br_sh="$SCRIPT_DIR/mp_software_bridge.sh" br_py="$SCRIPT_DIR/scripts/mp_software_bridge.py"
if [ -x "$br_sh" ]; then "$br_sh" update-action --action "$act" --category "$cat" &>/dev/null &
elif [ -f "$br_py" ]; then (python3 "$br_py" update-action --action "$act" --category "$cat" &>/dev/null &)
fi
}
_IN_EXIT_MIX_MANAGER=0
exit_mix_manager() {
    [ "${_IN_EXIT_MIX_MANAGER:-0}" -eq 1 ] && return 0
    _IN_EXIT_MIX_MANAGER=1
    trap - EXIT INT TERM HUP
    update_mp_bridge_menu "Stopped / Inactive" "false"
    save_playback_resume_state 2>/dev/null || true
    _STOP_AUDIO_ON_EXIT=1; _MENU_CURSOR_LOCK=0; _stop_win_cursor_hider
    local _lg_open=0
    if type is_liquid_glass_open &>/dev/null && is_liquid_glass_open; then
        _lg_open=1
    fi
    if [ "$_lg_open" -eq 1 ]; then
        echo ""
        echo -e "${BOLD}${CYAN}♫ MP Liquid Glass Audio Player is open — leaving playback active.${NC}"
    else
        _stop_mp_audio_daemon; kill_all_mp_audio_players 2>/dev/null || true
    fi
    local _bg_jobs
    _bg_jobs="$(jobs -p 2>/dev/null || true)"
    if [ -n "$_bg_jobs" ]; then
        for _jp in $_bg_jobs; do
            if [ "$_lg_open" -eq 1 ] && type is_liquid_glass_pid &>/dev/null && is_liquid_glass_pid "$_jp"; then
                continue
            fi
            kill "$_jp" 2>/dev/null || true
        done
    fi
    # Switch back from alternate screen buffer and restore cursor/wrap
    printf '\033[?1049l\033[?7h\033[?12h\033[?25h\033[?2026l' 2>/dev/null || true
    echo ""
    echo -e "${BOLD}${GREEN}You are exiting the MP Mix Archive Manager.${NC}"
    if [ "$_lg_open" -eq 1 ]; then
        echo -e "${DIM}Your Liquid Glass Audio Player will continue running on your desktop.${NC}"
    fi
    echo ""
    exit 0
}
if [[ "$UNAME_S" =~ (MINGW|MSYS|CYGWIN) ]]; then for _py_cand in "/c/Users/${USER:-Mathe}/AppData/Local/Programs/Python/Python312" "/c/Users/${USER:-Mathe}/AppData/Local/Programs/Python/Python312/Scripts" "/c/Program Files/Python312" "/c/Program Files/Python312/Scripts" "/c/Users/${USER:-Mathe}/AppData/Local/Microsoft/WinGet/Links"; do [ -d "$_py_cand" ] && export PATH="$_py_cand:$PATH"; done; _py3_path="$(type -p python3 2>/dev/null || true)"; if [ -z "$_py3_path" ] || [[ "$_py3_path" =~ WindowsApps ]]; then _py_path="$(type -p python 2>/dev/null || true)"; if [ -n "$_py_path" ] && [[ ! "$_py_path" =~ WindowsApps ]]; then
python3() { python "$@"; }
export -f python3 2>/dev/null || true; elif command -v py &>/dev/null; then
python3() { py -3 "$@"; }
export -f python3 2>/dev/null || true; fi; fi; fi; OS_TYPE="linux"; case "$UNAME_S" in Darwin*) OS_TYPE="macos"; ;; CYGWIN*|MINGW*|MSYS*) OS_TYPE="windows" ;; FreeBSD*) OS_TYPE="freebsd"; ;; Linux*) if grep -qi microsoft /proc/version 2>/dev/null; then OS_TYPE="wsl"; else OS_TYPE="linux"; fi ;; *) case "${OSTYPE:-}" in msys*|cygwin*|win32*) OS_TYPE="windows" ;; darwin*) OS_TYPE="macos" ;; freebsd*) OS_TYPE="freebsd" ;; *) OS_TYPE="linux" ;; esac ;; esac; export OS_TYPE
open_path() {
local target="$1"; [ -z "$target" ] && return 0; if [ "$OS_TYPE" = "macos" ]; then open "$target" &>/dev/null &
elif [ "$OS_TYPE" = "windows" ]; then cmd.exe /c start "" "$(cygpath -w "$target" 2>/dev/null || echo "$target")" &>/dev/null &
elif [ "$OS_TYPE" = "wsl" ]; then explorer.exe "$(wslpath -w "$target" 2>/dev/null || echo "$target")" &>/dev/null &
elif command -v xdg-open &>/dev/null; then xdg-open "$target" &>/dev/null &
fi
}
ensure_bazzite_borderless_kwin_rule() {
[ ! -d "$HOME/.config" ] && return 0; local rc_path="$HOME/.config/kwinrulesrc"; if command -v python3 &>/dev/null; then
python3 -c "
import configparser, os, uuid, subprocess
rc_path = os.path.expanduser('~/.config/kwinrulesrc')
if not os.path.exists(rc_path):
    os.makedirs(os.path.dirname(rc_path), exist_ok=True)
    with open(rc_path, 'w') as f:
        f.write('[General]\ncount=0\nrules=\n')
cp = configparser.ConfigParser()
cp.read(rc_path)
rule_tl_desc = 'Mix Tracklist Viewer (Borderless)'
tl_found = False
for sec in cp.sections():
    if cp.has_option(sec, 'description') and cp.get(sec, 'description') == rule_tl_desc:
        tl_found = True
        cp.set(sec, 'above', 'true')
        cp.set(sec, 'aboverule', '2')
        break
if not tl_found:
    new_uuid = str(uuid.uuid4())
    cp.add_section(new_uuid)
    cp.set(new_uuid, 'description', rule_tl_desc)
    cp.set(new_uuid, 'wmclass', 'konsole')
    cp.set(new_uuid, 'wmclassmatch', '1')
    cp.set(new_uuid, 'title', 'Mix Tracklist Viewer')
    cp.set(new_uuid, 'titlematch', '1')
    cp.set(new_uuid, 'types', '1')
    cp.set(new_uuid, 'noborder', 'true')
    cp.set(new_uuid, 'noborderrule', '2')
    cp.set(new_uuid, 'above', 'true')
    cp.set(new_uuid, 'aboverule', '2')
    if not cp.has_section('General'):
        cp.add_section('General')
    count = int(cp.get('General', 'count', fallback='0')) + 1
    cp.set('General', 'count', str(count))
    existing_rules = cp.get('General', 'rules', fallback='')
    rules_list = [r.strip() for r in existing_rules.split(',') if r.strip()]
    rules_list.append(new_uuid)
    cp.set('General', 'rules', ','.join(rules_list))
rule_cov_desc = 'Mix Cover Art Viewer (Keep Above)'
cov_found = False
for sec in cp.sections():
    if cp.has_option(sec, 'description') and cp.get(sec, 'description') == rule_cov_desc:
        cov_found = True
        break
if not cov_found:
    new_uuid2 = str(uuid.uuid4())
    cp.add_section(new_uuid2)
    cp.set(new_uuid2, 'description', rule_cov_desc)
    cp.set(new_uuid2, 'wmclass', 'gwenview')
    cp.set(new_uuid2, 'wmclassmatch', '2')
    cp.set(new_uuid2, 'title', 'Cover')
    cp.set(new_uuid2, 'titlematch', '2')
    cp.set(new_uuid2, 'types', '1')
    cp.set(new_uuid2, 'above', 'true')
    cp.set(new_uuid2, 'aboverule', '2')
    if not cp.has_section('General'):
        cp.add_section('General')
    count = int(cp.get('General', 'count', fallback='0')) + 1
    cp.set('General', 'count', str(count))
    existing_rules = cp.get('General', 'rules', fallback='')
    rules_list = [r.strip() for r in existing_rules.split(',') if r.strip()]
    rules_list.append(new_uuid2)
    cp.set('General', 'rules', ','.join(rules_list))
with open(rc_path, 'w') as f:
    cp.write(f)
if os.path.exists('/usr/bin/qdbus'):
    subprocess.run(['/usr/bin/qdbus', 'org.kde.KWin', '/KWin', 'reconfigure'], capture_output=True)
" 2>/dev/null || true
fi
}
get_connected_displays_count() {
if command -v kscreen-doctor &>/dev/null; then kscreen-doctor -o 2>/dev/null | grep -c "Output: " || echo 1; elif command -v xrandr &>/dev/null; then xrandr --listmonitors 2>/dev/null | awk '/Monitors:/{print $2}' || echo 1; else echo 1; fi
}
_IS_FULLSCREEN=0
toggle_manager_fullscreen() {
local app_ver; app_ver="v${VERSION#v}"; if [ "${_IS_FULLSCREEN:-0}" -eq 1 ]; then _IS_FULLSCREEN=0; printf '\033[10;0t\033[9;0t\033]0;%s\007' "MP Mix Archive Manager [${app_ver}]" 2>/dev/null || true; else _IS_FULLSCREEN=1; printf '\033[10;1t\033[9;1t\033]0;%s\007' "MP Mix Archive Manager [${app_ver}] (Fullscreen)" 2>/dev/null || true; fi
}
ensure_manager_windowed() {
_IS_FULLSCREEN=0; local app_ver; app_ver="v${VERSION#v}"; printf '\033]0;%s\007' "MP Mix Archive Manager [${app_ver}]" 2>/dev/null || true
}
ensure_manager_fullscreen() {
_IS_FULLSCREEN=1; local app_ver; app_ver="v${VERSION#v}"; printf '\033[10;1t\033[9;1t\033]0;%s\007' "MP Mix Archive Manager [${app_ver}] (Fullscreen)" 2>/dev/null || true
}
align_mix_windows_on_screen() {
[ "$OS_TYPE" = "windows" ] && return 0; local align_sh="$SCRIPT_DIR/scripts/align_mix_windows.py"; [ ! -f "$align_sh" ] && align_sh="$HOME/MP_Mix_Manager_v0.3/scripts/align_mix_windows.py"; [ ! -f "$align_sh" ] && align_sh="/var/home/mplanetarian/MP_Mix_Manager_v0.3/scripts/align_mix_windows.py"; [ ! -f "$align_sh" ] && align_sh="$HOME/MP_Mix_Manager_v0.3/scripts/align_mix_windows.py"; [ ! -f "$align_sh" ] && align_sh="/var/home/mplanetarian/MP_Mix_Manager_v0.3/scripts/align_mix_windows.py"; [ ! -f "$align_sh" ] && align_sh="$HOME/Documents/BASH_SCRIPTS/scripts/align_mix_windows.py"; [ ! -f "$align_sh" ] && align_sh="$PWD/scripts/align_mix_windows.py"; if [ -f "$align_sh" ] && command -v python3 &>/dev/null; then local mgr_pid="$$"; local parent_pid="$PPID"; (python3 "$align_sh" --mgr-pid "$mgr_pid" --parent-pid "$parent_pid" "$@" &>/dev/null || true) &
disown 2>/dev/null || true; fi
}
open_cover_art_window() {
local target="$1"; [ -z "$target" ] || [ ! -f "$target" ] && return 1; local cover_title="Mix Cover Art Viewer"; if [ "$OS_TYPE" = "linux" ] || [ "$OS_TYPE" = "freebsd" ]; then ensure_bazzite_borderless_kwin_rule; if _has_flatpak "org.kde.gwenview"; then nohup flatpak run org.kde.gwenview "$target" &>/dev/null &
disown 2>/dev/null || true; align_mix_windows_on_screen --expect-cover; return 0; fi; for viewer in gwenview loupe eog feh xdg-open; do if command -v "$viewer" &>/dev/null; then nohup "$viewer" "$target" &>/dev/null &
disown 2>/dev/null || true; align_mix_windows_on_screen --expect-cover; return 0; fi; done; fi; if [ "$OS_TYPE" = "macos" ]; then open -a Preview "$target" &>/dev/null &
align_mix_windows_on_screen --expect-cover; return 0; fi; if [ "$OS_TYPE" = "windows" ]; then cmd.exe /c start "" "$target" &>/dev/null &
return 0; elif [ "$OS_TYPE" = "wsl" ]; then for viewer in wslview explorer.exe; do if command -v "$viewer" &>/dev/null; then "$viewer" "$(wslpath -w "$target" 2>/dev/null || echo "$target")" &>/dev/null &
return 0; fi; done; fi; open_path "$target"
}
open_tracklist_window() {
local target="$1" audio_arg="${2:-}"; [ -z "$target" ] || [ ! -f "$target" ] && return 1; [ -n "$audio_arg" ] && export MP_TRACKLIST_AUDIO_FILE="$audio_arg"; [ -n "${CURRENT_THEME:-}" ] && export CURRENT_THEME MP_TRACKLIST_THEME="$CURRENT_THEME"; local viewer_sh="$SCRIPT_DIR/scripts/view_tracklist_console.sh"; [ ! -f "$viewer_sh" ] && viewer_sh="$PWD/scripts/view_tracklist_console.sh"; [ ! -f "$viewer_sh" ] && viewer_sh="$SCRIPT_DIR/view_tracklist_console.sh"; [ ! -f "$viewer_sh" ] && viewer_sh="$PWD/view_tracklist_console.sh"; local tl_title="Mix Tracklist Viewer"; local viewer="${TRACKLIST_VIEWER:-console}"; if [ "$viewer" != "console" ] && [ "$viewer" != "auto" ] && [ -n "$viewer" ]; then if command -v "$viewer" &>/dev/null; then "$viewer" "$target" &>/dev/null &
return 0; fi; fi; if [ "$OS_TYPE" = "linux" ] || [ "$OS_TYPE" = "freebsd" ]; then ensure_bazzite_borderless_kwin_rule; if command -v konsole &>/dev/null; then konsole --hide-menubar --hide-tabbar --separate --qwindowtitle "$tl_title" -p tabtitle="$tl_title" -p TerminalMargin=0 -p TerminalColumns=95 -p TerminalRows=35 -e bash "$viewer_sh" "$target" ${audio_arg:+"$audio_arg"} &>/dev/null &
(sleep 0.15; command -v xprop &>/dev/null && xprop -name "$tl_title" -f _MOTIF_WM_HINTS 32c -set _MOTIF_WM_HINTS "0x2, 0x0, 0x0, 0x0, 0x0" 2>/dev/null || true) &
return 0; elif command -v gnome-terminal &>/dev/null; then gnome-terminal --title="$tl_title" --hide-menubar -- bash "$viewer_sh" "$target" ${audio_arg:+"$audio_arg"} &>/dev/null &
return 0; elif command -v xfce4-terminal &>/dev/null; then xfce4-terminal --title="$tl_title" --hide-menubar --hide-borders -e "bash '$viewer_sh' '$target'${audio_arg:+ '$audio_arg'}" &>/dev/null &
return 0; elif command -v alacritty &>/dev/null; then alacritty --title "$tl_title" -e bash "$viewer_sh" "$target" ${audio_arg:+"$audio_arg"} &>/dev/null &
return 0; elif command -v foot &>/dev/null; then foot -T "$tl_title" bash "$viewer_sh" "$target" ${audio_arg:+"$audio_arg"} &>/dev/null &
return 0; elif command -v xterm &>/dev/null; then xterm -title "$tl_title" -bd 0 -geometry 95x35 -e bash "$viewer_sh" "$target" ${audio_arg:+"$audio_arg"} &>/dev/null &
return 0; fi; fi; if [ "$OS_TYPE" = "macos" ]; then local escaped_viewer escaped_target; escaped_viewer=$(printf '%s' "$viewer_sh" | sed 's/"/\\"/g'); escaped_target=$(printf '%s' "$target" | sed 's/"/\\"/g'); osascript -e "tell application \"Terminal\" to do script \"bash \\\"$escaped_viewer\\\" \\\"$escaped_target\\\"\"" &>/dev/null &
return 0; fi; if [ "$OS_TYPE" = "windows" ]; then if command -v wt.exe &>/dev/null; then wt.exe -w new --title "$tl_title" bash "$viewer_sh" "$target" ${audio_arg:+"$audio_arg"} &>/dev/null &
return 0; elif command -v cmd.exe &>/dev/null; then cmd.exe /c start "$tl_title" bash "$viewer_sh" "$target" ${audio_arg:+"$audio_arg"} &>/dev/null &
return 0; fi; elif [ "$OS_TYPE" = "wsl" ]; then if command -v wt.exe &>/dev/null; then wt.exe -w 0 nt --title "$tl_title" wsl.exe -e bash "$viewer_sh" "$target" ${audio_arg:+"$audio_arg"} &>/dev/null &
return 0; fi; fi; open_path "$target"
}
find_mix_tracklist() {
local mix_file="$1"; [ -z "$mix_file" ] && return 1; local mix_basename; mix_basename=$(basename "$mix_file"); local mix_stem="${mix_basename%.*}"; local mix_dir; mix_dir="$(dirname "$mix_file")"; local ep_num=""; if [[ "$mix_stem" =~ [_\ -]([0-9]{2,3})([_\ -]|$) ]]; then ep_num="${BASH_REMATCH[1]}"; fi; local date_str=""; if [[ "$mix_stem" =~ ([0-9]{4}-[0-9]{2}-[0-9]{2}) ]]; then date_str="${BASH_REMATCH[1]}"; fi; local candidate_dirs=("$mix_dir" "$OUTPUT_DIR" "${MIX_ARCHIVE_DIR:-$PWD}/FLAC_CONVERTED_OUTPUTS" "${MIX_ARCHIVE_DIR:-$PWD}" "$PWD/FLAC_CONVERTED_OUTPUTS" "$PWD" "${MIX_ARCHIVE_DIR:-$PWD}/TEMP"); if command -v get_all_flac_output_dirs &>/dev/null; then while IFS= read -r f_dir; do [ -n "$f_dir" ] && candidate_dirs+=("$f_dir"); done < <(get_all_flac_output_dirs); fi; if command -v get_all_mix_archive_dirs &>/dev/null; then while IFS= read -r a_dir; do [ -n "$a_dir" ] && candidate_dirs+=("$a_dir"); done < <(get_all_mix_archive_dirs); fi; if [ -f "${mix_file%.*}.txt" ]; then echo "${mix_file%.*}.txt"; return 0; fi; for d in "${candidate_dirs[@]}"; do if [ -f "$d/${mix_stem}.txt" ]; then echo "$d/${mix_stem}.txt"; return 0; fi; done; if [ -n "$ep_num" ]; then shopt -s nullglob nocaseglob; for d in "${candidate_dirs[@]}"; do for match in "$d"/*"${ep_num}"*.txt; do if [ -f "$match" ]; then shopt -u nullglob nocaseglob; echo "$match"; return 0; fi; done; done; shopt -u nullglob nocaseglob; fi; if [ -n "$date_str" ]; then shopt -s nullglob nocaseglob; for d in "${candidate_dirs[@]}"; do for match in "$d"/*"${date_str}"*.txt; do if [ -f "$match" ]; then shopt -u nullglob nocaseglob; echo "$match"; return 0; fi; done; done; shopt -u nullglob nocaseglob; fi; local clean_kw; clean_kw=$(echo "$mix_stem" | sed -E 's/MPlanetarian|Stream|of|Frequency|Part|WMI|Mix//gi' | tr '_-' ' ' | awk '{print $1}'); if [ -n "$clean_kw" ] && [ "${#clean_kw}" -ge 4 ]; then shopt -s nullglob nocaseglob; for d in "${candidate_dirs[@]}"; do for match in "$d"/*"${clean_kw}"*.txt; do if [ -f "$match" ]; then shopt -u nullglob nocaseglob; echo "$match"; return 0; fi; done; done; shopt -u nullglob nocaseglob; fi; if [ -d "${MIX_ARCHIVE_DIR:-$PWD}" ]; then if [ -n "$ep_num" ]; then local deep_match; deep_match=$(find "${MIX_ARCHIVE_DIR:-$PWD}" -maxdepth 3 -type f -name "*${ep_num}*.txt" ! -path "*/SPEK_OUTPUTS/*" 2>/dev/null | head -1); if [ -n "$deep_match" ] && [ -f "$deep_match" ]; then echo "$deep_match"; return 0; fi; fi; if [ -n "$date_str" ]; then local deep_match_date; deep_match_date=$(find "${MIX_ARCHIVE_DIR:-$PWD}" -maxdepth 3 -type f -name "*${date_str}*.txt" ! -path "*/SPEK_OUTPUTS/*" 2>/dev/null | head -1); if [ -n "$deep_match_date" ] && [ -f "$deep_match_date" ]; then echo "$deep_match_date"; return 0; fi; fi; fi; local tmp_tl="/tmp/Tracklist_${mix_stem}.txt"; { echo "=================================================="; echo "STREAM OF FREQUENCY - MIX TRACKLIST"; echo "=================================================="; echo "Mix File:       $mix_basename"; [ -n "$ep_num" ] && echo "Episode:        Episode $ep_num"; [ -n "$date_str" ] && echo "Recorded Date:  $date_str"; echo "Directory:      $mix_dir"; echo "Detected on:    $(date '+%Y-%m-%d %H:%M:%S')"; echo "--------------------------------------------------"; echo "A standalone .txt tracklist file was not yet found"; echo "directly on disk for this mix file."; echo ""; echo "To auto-generate complete tracklists from your Traktor"; echo "history or audio metadata, launch Option 16 in the"; echo "MP Mix Archive Manager."; echo "=================================================="; } > "$tmp_tl" 2>/dev/null; if [ -f "$tmp_tl" ]; then echo "$tmp_tl"; return 0; fi; return 1
}
find_mix_cover() {
local mix_file="$1"; [ -z "$mix_file" ] && return 1; local mix_basename; mix_basename=$(basename "$mix_file"); local mix_stem="${mix_basename%.*}"; local mix_dir; mix_dir="$(dirname "$mix_file")"; local ep_num=""; if [[ "$mix_stem" =~ [_\ -]([0-9]{2,3})([_\ -]|$) ]]; then ep_num="${BASH_REMATCH[1]}"; fi; local date_str=""; if [[ "$mix_stem" =~ ([0-9]{4}-[0-9]{2}-[0-9]{2}) ]]; then date_str="${BASH_REMATCH[1]}"; fi; local candidate_dirs=("$mix_dir" "$mix_dir/COVERS" "${MIX_ARCHIVE_DIR:-$PWD}/COVERS" "$PWD/COVERS" "${MIX_ARCHIVE_DIR:-$PWD}" "$PWD" "$SCRIPT_DIR/COVERS" "$SCRIPT_DIR"); if command -v get_all_mix_archive_dirs &>/dev/null; then while IFS= read -r a_dir; do [ -n "$a_dir" ] && candidate_dirs+=("$a_dir" "$a_dir/COVERS"); done < <(get_all_mix_archive_dirs); fi; for d in "${candidate_dirs[@]}"; do for ext in png jpg jpeg webp; do if [ -f "$d/${mix_stem}.${ext}" ]; then echo "$d/${mix_stem}.${ext}"; return 0; fi; done; done; if [ -n "$ep_num" ]; then shopt -s nullglob nocaseglob; for d in "${candidate_dirs[@]}"; do for match in "$d"/*"${ep_num}"*.png "$d"/*"${ep_num}"*.jpg; do if [ -f "$match" ]; then shopt -u nullglob nocaseglob; echo "$match"; return 0; fi; done; done; shopt -u nullglob nocaseglob; fi; if [ -n "$date_str" ]; then shopt -s nullglob nocaseglob; for d in "${candidate_dirs[@]}"; do for match in "$d"/*"${date_str}"*.png "$d"/*"${date_str}"*.jpg; do if [ -f "$match" ]; then shopt -u nullglob nocaseglob; echo "$match"; return 0; fi; done; done; shopt -u nullglob nocaseglob; fi; if [ -d "${MIX_ARCHIVE_DIR:-$PWD}" ]; then if [ -n "$ep_num" ]; then local deep_cov; deep_cov=$(find "${MIX_ARCHIVE_DIR:-$PWD}" -maxdepth 3 -type f \( -name "*${ep_num}*.png" -o -name "*${ep_num}*.jpg" \) ! -path "*/SPEK_OUTPUTS/*" 2>/dev/null | head -1); if [ -n "$deep_cov" ] && [ -f "$deep_cov" ]; then echo "$deep_cov"; return 0; fi; fi; fi; for d in "${candidate_dirs[@]}"; do if [ -f "$d/Cover_4K.png" ]; then echo "$d/Cover_4K.png"; return 0; fi; if [ -f "$d/Cover.png" ]; then echo "$d/Cover.png"; return 0; fi; if [ -f "$d/Cover.jpg" ]; then echo "$d/Cover.jpg"; return 0; fi; if [ -f "$d/001.png" ]; then echo "$d/001.png"; return 0; fi; done; if [ -f "$SCRIPT_DIR/assets/Cover.png" ]; then echo "$SCRIPT_DIR/assets/Cover.png"; return 0; fi; return 1
}
find_mix_spek() {
local mix_file="$1"; [ -n "$mix_file" ] || return 1; local mix_stem; mix_stem="$(basename "${mix_file%.*}")"; [ -n "$mix_stem" ] || return 1; local -a dirs=()
add_spek_dir() {
local cand="$1"; local resolved seen; [ -n "$cand" ] && [ -d "$cand" ] || return 0; resolved="$(cd "$cand" 2>/dev/null && pwd -P)" || return 0; for seen in "${dirs[@]}"; do [ "$seen" = "$resolved" ] && return 0; done; dirs+=("$resolved")
}
add_spek_dir "$(dirname "$mix_file")"; add_spek_dir "${SPEK_DIR:-}"; if [ -n "${MIX_ARCHIVE_DIR:-}" ]; then add_spek_dir "${MIX_ARCHIVE_DIR%/}/SPEK_OUTPUTS"; if [ -n "${SPEK_DIR:-}" ] && [[ "$SPEK_DIR" != /* ]]; then add_spek_dir "${MIX_ARCHIVE_DIR%/}/${SPEK_DIR}"; fi; fi; add_spek_dir "${PWD}/SPEK_OUTPUTS"; if command -v get_all_mix_archive_dirs &>/dev/null; then local archive_dir; while IFS= read -r archive_dir; do [ -z "$archive_dir" ] && continue; add_spek_dir "${archive_dir%/}/SPEK_OUTPUTS"; add_spek_dir "$(dirname "$archive_dir")/SPEK_OUTPUTS"; done < <(get_all_mix_archive_dirs); fi; local spek_dir spek_name; for spek_dir in "${dirs[@]}"; do for spek_name in "${mix_stem}_spectrogram.png" "${mix_stem}.spek.png" "${mix_stem}.spek" "${mix_stem}_spectrogram.jpg"; do if [ -s "$spek_dir/$spek_name" ]; then echo "$spek_dir/$spek_name"; return 0; fi; done; done; return 1
}
open_startup_mix_spek() {
local saved_mode="${AUTO_PLAY_MIX_SELECTION:-latest}"; local selected_mix=""; AUTO_PLAY_MIX_SELECTION="latest"; selected_mix="$(select_startup_mix)" || true; AUTO_PLAY_MIX_SELECTION="$saved_mode"; if [ -z "$selected_mix" ] || [ ! -s "$selected_mix" ]; then return 0; fi; if is_remote_or_cloud_path "$selected_mix" && ! is_internet_connected; then return 0; fi; local spek=""; spek="$(find_mix_spek "$selected_mix" 2>/dev/null || true)"; if [ -z "$spek" ] || [ ! -s "$spek" ]; then return 0; fi; STARTUP_SPEK_NOTICE="Spectrogram: $(basename "$spek")"; open_cover_art_window "$spek" || open_path "$spek"
}
copy_to_clipboard() {
local text="$1"; local cmd; if [ "$OS_TYPE" = "macos" ] || [ "$OS_TYPE" = "wsl" ]; then cmd="pbcopy"; elif [ "$OS_TYPE" = "windows" ]; then cmd="clip.exe"; else if command -v wl-copy &>/dev/null; then cmd="wl-copy"; elif command -v xclip &>/dev/null; then cmd="xclip -selection clipboard"; elif command -v pbcopy &>/dev/null; then cmd="pbcopy"; elif command -v clip.exe &>/dev/null; then cmd="clip.exe"; fi; fi; if [ -n "$cmd" ]; then printf "%s" "$text" | $cmd; return 0; fi; return 1
}
launch_in_terminal() {
local title="$1"; local cmd="$2"; local mode="${3:-tab}"; if [ "$OS_TYPE" = "macos" ]; then if [ "${TERM_PROGRAM:-}" = "iTerm.app" ]; then
osascript - "$cmd" <<'APPLESCRIPT' &>/dev/null
on run argv
    set cmdText to item 1 of argv
    tell application "iTerm"
        activate
        if (count of windows) = 0 then
            create window with default profile
        end if
        tell current window
            create tab with default profile
            tell current session of current tab
                write text cmdText
            end tell
        end tell
    end tell
end run
APPLESCRIPT
return 0; fi; if [ "$mode" = "window" ]; then
osascript - "$cmd" <<'APPLESCRIPT' &>/dev/null
on run argv
    tell application "Terminal"
        activate
        do script (item 1 of argv)
    end tell
end run
APPLESCRIPT
return 0; fi; local launch_result=""
launch_result="$(osascript - "$cmd" <<'APPLESCRIPT'
on run argv
    set cmdText to item 1 of argv
    tell application "System Events"
        tell process "Terminal"
            set frontmost to true
            key code 53
        end tell
    end tell
    delay 0.1
    set beforeCount to 0
    tell application "System Events"
        tell process "Terminal"
            repeat with w in windows
                try
                    set beforeCount to beforeCount + (count of radio buttons of tab group 1 of w)
                end try
            end repeat
        end tell
    end tell
    tell application "Terminal"
        set oldIds to {}
        repeat with w in windows
            try
                set end of oldIds to (id of w as integer) as string
            end try
        end repeat
    end tell
    ignoring application responses
        tell application "System Events"
            tell process "Terminal"
                set frontmost to true
                click button 1 of tab group 1 of window 1
            end tell
        end tell
    end ignoring
    delay 0.7
    set afterCount to 0
    tell application "System Events"
        tell process "Terminal"
            repeat with w in windows
                try
                    set afterCount to afterCount + (count of radio buttons of tab group 1 of w)
                end try
            end repeat
        end tell
    end tell
    tell application "Terminal"
        set targetWin to missing value
        repeat with w in windows
            try
                set wid to (id of w as integer) as string
                set known to false
                repeat with oldId in oldIds
                    if (oldId as string) is equal to wid then set known to true
                end repeat
                if not known then
                    set hist to history of selected tab of w
                    set nm to name of w
                    if (count of hist) < 900 and hist contains "Last login" and nm does not contain "grok" and nm does not contain "ffmpeg" and nm does not contain "Mix Archive" then
                        set targetWin to w
                        exit repeat
                    end if
                end if
            end try
        end repeat
        if targetWin is not missing value then
            do script cmdText in selected tab of targetWin
            if afterCount > beforeCount then
                return "tab"
            end if
            return "window"
        end if
        do script cmdText
        return "fallback"
    end tell
end run
APPLESCRIPT
)" || launch_result="fail"
case "$launch_result" in tab*|window*|fallback*) return 0 ;; esac
osascript - "$cmd" <<'APPLESCRIPT' &>/dev/null
on run argv
    tell application "Terminal" to do script (item 1 of argv)
end run
APPLESCRIPT
return 0; elif [ "$OS_TYPE" = "windows" ]; then if command -v wt.exe &>/dev/null; then if [ "$mode" = "tab" ]; then wt.exe new-tab --title "$title" bash -c "$cmd" >/dev/null 2>&1 &
else wt.exe -w new --title "$title" bash -c "$cmd" >/dev/null 2>&1 &
fi; return 0; elif command -v start >/dev/null 2>&1; then start "$title" bash -c "$cmd" >/dev/null 2>&1 &
return 0; elif command -v cmd.exe &>/dev/null; then cmd.exe /c start "$title" bash -c "$cmd" >/dev/null 2>&1 &
return 0; fi; elif [ "$OS_TYPE" = "wsl" ]; then if command -v wt.exe &>/dev/null; then wt.exe -w 0 nt --title "$title" wsl.exe -e bash -c "$cmd" >/dev/null 2>&1 &
return 0; fi; fi; if [ "$mode" = "window" ]; then local _k_extra=(); if [[ "$title" == *"Mini"* || "$title" == *"Micro"* ]]; then _k_extra=(--profile MP_Mini_Player --hide-menubar --hide-tabbar); fi; if command -v konsole >/dev/null 2>&1; then nohup konsole "${_k_extra[@]}" --separate --workdir "$PWD" -p tabtitle="$title" -e bash -c "$cmd" >/dev/null 2>&1 &
return 0; elif command -v xdg-terminal-exec &>/dev/null; then nohup xdg-terminal-exec bash -c "$cmd" >/dev/null 2>&1 &
return 0; elif command -v gnome-terminal &>/dev/null; then nohup gnome-terminal --title="$title" -- bash -c "$cmd" >/dev/null 2>&1 &
return 0; elif command -v xterm &>/dev/null; then nohup xterm -T "$title" -e bash -c "$cmd" >/dev/null 2>&1 &
return 0; fi; else local qdbus_bin=""; if command -v qdbus-qt6 &>/dev/null; then qdbus_bin="qdbus-qt6"; elif command -v qdbus &>/dev/null; then qdbus_bin="qdbus"; fi; if [ -n "$qdbus_bin" ]; then local k_svc="${KONSOLE_DBUS_SERVICE:-}"; local k_win="${KONSOLE_DBUS_WINDOW:-}"; if [ -z "$k_svc" ]; then k_svc=$("$qdbus_bin" 2>/dev/null | grep -m1 -E "org\.kde\.konsole-[0-9]+" || true); fi; k_svc=$(echo "$k_svc" | xargs); if [ -n "$k_svc" ]; then if [ -z "$k_win" ] || ! "$qdbus_bin" "$k_svc" "$k_win" org.kde.konsole.Window.sessionCount &>/dev/null; then for candidate_win in "/Windows/1" "/Windows/2" "/Windows/3"; do if "$qdbus_bin" "$k_svc" "$candidate_win" org.kde.konsole.Window.sessionCount &>/dev/null; then k_win="$candidate_win"; break; fi; done; fi; if [ -n "$k_win" ]; then local session_id; session_id=$("$qdbus_bin" "$k_svc" "$k_win" org.kde.konsole.Window.newSession "" "$PWD" 2>/dev/null || true); session_id=$(echo "$session_id" | xargs); if [ -n "$session_id" ] && [ "$session_id" -gt 0 ] 2>/dev/null; then "$qdbus_bin" "$k_svc" "/Sessions/$session_id" org.kde.konsole.Session.setTitle 1 "$title" 2>/dev/null || true; for ((_w=0; _w<25; _w++)); do local disp; disp=$("$qdbus_bin" "$k_svc" "/Sessions/$session_id" org.kde.konsole.Session.getAllDisplayedText 2>/dev/null || true); if [[ "$disp" =~ (\$) || "$disp" =~ (\#) || "$disp" =~ (@) ]]; then break; fi; sleep 0.08; done; if "$qdbus_bin" "$k_svc" "/Sessions/$session_id" org.kde.konsole.Session.runCommand "$cmd" &>/dev/null; then sleep 0.25; local check_disp; check_disp=$("$qdbus_bin" "$k_svc" "/Sessions/$session_id" org.kde.konsole.Session.getAllDisplayedText 2>/dev/null || true); if [[ "$check_disp" =~ \$\ $ ]] || [[ "$check_disp" =~ @.*:\~.*\$ ]]; then "$qdbus_bin" "$k_svc" "/Sessions/$session_id" org.kde.konsole.Session.runCommand "$cmd" &>/dev/null || true; fi; return 0; else local child_pid; child_pid=$("$qdbus_bin" "$k_svc" "/Sessions/$session_id" org.kde.konsole.Session.processId 2>/dev/null || true); [ -n "$child_pid" ] && [ "$child_pid" -gt 0 ] 2>/dev/null && kill -9 "$child_pid" 2>/dev/null || true; fi; fi; fi; fi; fi; if command -v konsole >/dev/null 2>&1; then local _k_extra_f=(); if [[ "$title" == *"Mini"* || "$title" == *"Micro"* ]]; then _k_extra_f=(--profile MP_Mini_Player --hide-menubar --hide-tabbar); fi; nohup konsole "${_k_extra_f[@]}" --separate --workdir "$PWD" -p tabtitle="$title" -e bash -c "$cmd" >/dev/null 2>&1 &
return 0; elif command -v xdg-terminal-exec &>/dev/null; then nohup xdg-terminal-exec bash -c "$cmd" >/dev/null 2>&1 &
return 0; elif command -v gnome-terminal &>/dev/null; then nohup gnome-terminal --tab --title="$title" --working-directory="$PWD" -- bash -c "$cmd" >/dev/null 2>&1 &
return 0; elif command -v xfce4-terminal &>/dev/null; then local xfce_cmd; xfce_cmd="$(printf '%q' "$cmd")"; nohup xfce4-terminal --tab --title="$title" --working-directory="$PWD" -e "bash -lc ${xfce_cmd}" &>/dev/null &
return 0; fi; fi; return 1
}
toggle_mp_audio_player() {
local mp_py="$SCRIPT_DIR/MP_Audio_Player.py"; [ ! -f "$mp_py" ] && mp_py="$SCRIPT_DIR/scripts/MP_Audio_Player.py"; [ -f "$mp_py" ] && python3 "$mp_py" --toggle --only-if-running &>/dev/null &
}
launch_mp_audio_player_window() {
local mp_py="$SCRIPT_DIR/MP_Audio_Player.py"; [ ! -f "$mp_py" ] && mp_py="$SCRIPT_DIR/scripts/MP_Audio_Player.py"; if [ -f "$mp_py" ]; then
if python3 "$mp_py" --mini --new-window &>/dev/null; then return 0; fi; if python3 "$mp_py" --new-window &>/dev/null; then return 0; fi; launch_in_terminal "MP Mini Audio Player" "python3 \"$mp_py\" --interactive --mini" "window"
fi
}
launch_mp_audio_player_liquid_glass() {
    local os_type="$(uname -s)"
    local arch_type="$(uname -m)"
    local py=""
    local backend_name="OpenGL"

    if [ "$os_type" = "Darwin" ]; then
        if [ "$arch_type" != "arm64" ]; then
            echo -e "\n${RED}Liquid Glass Metal mode requires Apple Silicon (M1/M2/M3/M4+). Intel Macs are not supported.${NC}\n"
            manage_mp_audio_player
            return
        fi
        py="$SCRIPT_DIR/MP_Audio_Player_Liquid_Glass_macOS.py"
        [ ! -f "$py" ] && py="$SCRIPT_DIR/scripts/MP_Audio_Player_Liquid_Glass_macOS.py"
        backend_name="Metal (Apple Silicon)"
    elif [ "$os_type" = "Linux" ] || [[ "$os_type" =~ ^(MINGW|MSYS|CYGWIN) ]]; then
        local backend="${LIQUID_GLASS_BACKEND:-opengl}"
        backend="$(echo "$backend" | tr '[:upper:]' '[:lower:]')"
        if [ "$backend" = "vulkan" ]; then
            py="$SCRIPT_DIR/MP_Audio_Player_Liquid_Glass.py"
            [ ! -f "$py" ] && py="$SCRIPT_DIR/scripts/MP_Audio_Player_Liquid_Glass.py"
            backend_name="Vulkan"
        else
            py="$SCRIPT_DIR/MP_Audio_Player_Liquid_Glass_OpenGL.py"
            [ ! -f "$py" ] && py="$SCRIPT_DIR/scripts/MP_Audio_Player_Liquid_Glass_OpenGL.py"
            backend_name="OpenGL"
            if [ ! -f "$py" ]; then
                py="$SCRIPT_DIR/MP_Audio_Player_Liquid_Glass.py"
                [ ! -f "$py" ] && py="$SCRIPT_DIR/scripts/MP_Audio_Player_Liquid_Glass.py"
                backend_name="Vulkan"
            fi
        fi
    else
        echo -e "\n${YELLOW}Liquid Glass Mode requires Linux, Windows 10/11, or Apple Silicon macOS. Opening the standard MP Audio Player.${NC}\n"
        manage_mp_audio_player
        return
    fi

    if [ -z "$py" ] || [ ! -f "$py" ]; then
        echo -e "\n${RED}Liquid Glass player script was not found. Opening the standard MP Audio Player.${NC}\n"
        manage_mp_audio_player
        return
    fi

    mkdir -p "$HOME/.config/mix-manager" 2>/dev/null || true
    echo -e "\n${BOLD}${CYAN}Opening MP Audio Player (Liquid Glass Mode - ${backend_name}) in its own window.${NC}\n"
    nohup python3 "$py" >> "$HOME/.config/mix-manager/liquid_glass.log" 2>&1 &
    disown
}
launch_mp_liquid_visualizer() {
    local preset_arg="${1:-}"
    local vis_py="$SCRIPT_DIR/MP_Liquid_Visualizer.py"
    [ ! -f "$vis_py" ] && vis_py="$SCRIPT_DIR/scripts/mp_liquid_visualizer_vulkan.py"
    if [ ! -f "$vis_py" ]; then
        echo -e "\n${RED}Error: MP_Liquid_Visualizer.py was not found in ${SCRIPT_DIR}!${NC}\n"
        return 1
    fi
    mkdir -p "$HOME/.config/mix-manager" 2>/dev/null || true
    local preset_label="Cosmic Dreamworlds (Liquid)"
    if [ -f "$HOME/.config/mix-manager/visualizer_preset" ]; then
        local saved_key
        saved_key="$(cat "$HOME/.config/mix-manager/visualizer_preset" 2>/dev/null || true)"
        [ "$saved_key" = "cosmic_dreamworlds_liquid" ] && preset_label="Cosmic Dreamworlds (Liquid)"
        [ "$saved_key" = "orbital_void_reflux" ] && preset_label="Orbital Void Reflux"
        [ "$saved_key" = "dreamworlds_ultra_defasten" ] && preset_label="Dreamworlds Ultra (Defasten Biomech)"
    fi
    if [ -n "$preset_arg" ]; then
        case "$preset_arg" in
            orbital_void_reflux|*orbital*|*void*|*reflux*) preset_label="Orbital Void Reflux" ;;
            dreamworlds_ultra_defasten|*defasten*|*ultra*|*biomech*) preset_label="Dreamworlds Ultra (Defasten Biomech)" ;;
            *) preset_label="Cosmic Dreamworlds (Liquid)" ;;
        esac
    fi
    echo -e "\n${BOLD}${CYAN}Opening MP_Liquid_Visualizer [Preset: ${preset_label}] — 1400x1400 Fixed Borderless Vulkan Window...${NC}"
    echo -e "${DIM}Continually generates 3D synced to currently playing music (pauses in-place when stopped). Press Esc or 'q' to close.${NC}\n"
    if [ -n "$preset_arg" ]; then
        nohup python3 "$vis_py" --preset "$preset_arg" >> "$HOME/.config/mix-manager/liquid_visualizer.log" 2>&1 &
    else
        nohup python3 "$vis_py" >> "$HOME/.config/mix-manager/liquid_visualizer.log" 2>&1 &
    fi
    disown
}
manage_mp_liquid_visualizer_presets() {
    local vis_py="$SCRIPT_DIR/MP_Liquid_Visualizer.py"
    [ ! -f "$vis_py" ] && vis_py="$SCRIPT_DIR/scripts/mp_liquid_visualizer_vulkan.py"
    while true; do
        clear
        local active_key="cosmic_dreamworlds_liquid"
        [ -f "$HOME/.config/mix-manager/visualizer_preset" ] && active_key="$(cat "$HOME/.config/mix-manager/visualizer_preset" 2>/dev/null || echo "cosmic_dreamworlds_liquid")"
        local p1_mark="  "
        local p2_mark="  "
        local p3_mark="  "
        if [ "$active_key" = "orbital_void_reflux" ]; then
            p2_mark="★ "
        elif [ "$active_key" = "dreamworlds_ultra_defasten" ]; then
            p3_mark="★ "
        else
            p1_mark="★ "
        fi

        echo -e "${BOLD}${MAGENTA}======================================================================${NC}"
        echo -e "${BOLD}${MAGENTA}         MP_LIQUID_VISUALIZER — NATIVE VULKAN 3D PRESET SUITE         ${NC}"
        echo -e "${BOLD}${MAGENTA}======================================================================${NC}\n"
        echo -e "  ${BOLD}${CYAN}Engine:${NC}            Vulkan 1.x Native 3D Raymarching & Liquid Glass"
        echo -e "  ${BOLD}${CYAN}Window:${NC}            1400x1400 Fixed Borderless (Zero Text Overlay • Esc/q to Close)"
        echo -e "  ${BOLD}${CYAN}Audio Sync:${NC}        Continually generates 3D to playing music; freezes when paused/stopped"
        echo -e "  ${BOLD}${CYAN}Customization:${NC}     Preset selection only (1 Bandcamp Cover per Preset)\n"
        echo -e "${BOLD}Available Visualizer Presets (3 of 5 Planned):${NC}"
        echo -e "  ${BOLD}${CYAN}1)${NC} ${BOLD}${GREEN}${p1_mark}Cosmic Dreamworlds (Liquid)${NC}        ${DIM}[MPlanetarian - Cosmic Dreamworlds Deluxe Edition]${NC}"
        echo -e "  ${BOLD}${CYAN}2)${NC} ${BOLD}${GREEN}${p2_mark}Orbital Void Reflux${NC}                ${DIM}[MPlanetarian - Orbital Void Reflux (Cover_WMI_V2.png)]${NC}"
        echo -e "  ${BOLD}${CYAN}3)${NC} ${BOLD}${GREEN}${p3_mark}Dreamworlds Ultra (Defasten Biomech)${NC} ${DIM}[Defasten Xinri D & Start_Menu_Icon.png]${NC}"
        echo -e "  ${BOLD}${CYAN}4)${NC} Launch MP_Liquid_Visualizer Now (1400x1400 Borderless Vulkan Window)"
        echo -e "  ${BOLD}${CYAN}0)${NC} Return\n"
        read -r -p "Select option [0-4]: " vp_choice
        case "$vp_choice" in
            1)
                [ -f "$vis_py" ] && python3 "$vis_py" --set-preset "Cosmic Dreamworlds (Liquid)"
                echo -e "\n${GREEN}✔ Active Preset set to: Cosmic Dreamworlds (Liquid)${NC}"
                sleep 1
                ;;
            2)
                [ -f "$vis_py" ] && python3 "$vis_py" --set-preset "Orbital Void Reflux"
                echo -e "\n${GREEN}✔ Active Preset set to: Orbital Void Reflux${NC}"
                sleep 1
                ;;
            3)
                [ -f "$vis_py" ] && python3 "$vis_py" --set-preset "Dreamworlds Ultra (Defasten Biomech)"
                echo -e "\n${GREEN}✔ Active Preset set to: Dreamworlds Ultra (Defasten Biomech)${NC}"
                sleep 1
                ;;
            4|l|L|z|Z)
                launch_mp_liquid_visualizer
                sleep 1
                return 0
                ;;
            0|[qQ]|ESC)
                return 0
                ;;
            *)
                echo -e "\n${RED}Invalid selection.${NC}"
                sleep 1
                ;;
        esac
    done
}
configure_liquid_glass_backend() {
while true; do
clear
local cur="${LIQUID_GLASS_BACKEND:-opengl}"
cur="$(echo "$cur" | tr '[:upper:]' '[:lower:]')"
local og_mark="" vk_mark=""
[ "$cur" = "opengl" ] && og_mark="${GREEN}★ ACTIVE (DEFAULT)${NC}"
[ "$cur" = "vulkan" ] && vk_mark="${GREEN}★ ACTIVE${NC}"
echo -e "${BOLD}${MAGENTA}======================================================================${NC}"
echo -e "${BOLD}${MAGENTA}       CONFIGURE STANDALONE LIQUID GLASS PLAYER BACKEND        ${NC}"
echo -e "${BOLD}${MAGENTA}======================================================================${NC}\n"
echo -e "  Current Active Backend: ${BOLD}${GREEN}${cur^^}${NC}\n"
echo -e "  ${BOLD}Select Backend Engine:${NC}"
echo -e "  ${BOLD}${CYAN} 1)${NC} ${BOLD}OpenGL${NC} (Recommended / Default) ${og_mark}"
echo -e "      ${DIM}Broad compatibility: AMD Radeon, Intel HD/Iris/Arc, NVIDIA, Mesa & older GPUs${NC}"
echo -e "  ${BOLD}${CYAN} 2)${NC} ${BOLD}Vulkan${NC} (Hardware Acceleration) ${vk_mark}"
echo -e "      ${DIM}Direct Vulkan pipeline (Requires NVIDIA discrete GPU and libvulkan)${NC}"
echo -e "  ${BOLD}${CYAN} 3)${NC} Toggle between OpenGL & Vulkan"
echo -e "  ${BOLD}${CYAN} 0)${NC} Return to Previous Menu\n"
read -r -p "Enter choice [0-3]: " lg_choice
case "$lg_choice" in
1|opengl|OpenGL|gl|GL)
LIQUID_GLASS_BACKEND="opengl"
save_config_setting "LIQUID_GLASS_BACKEND" "opengl"
echo -e "\n${GREEN}✓ Liquid Glass backend set to 'opengl' (Default - AMD/Intel/NVIDIA/Older Cards) and saved!${NC}"
sleep 1
return 0
;;
2|vulkan|Vulkan|vk|VK)
LIQUID_GLASS_BACKEND="vulkan"
save_config_setting "LIQUID_GLASS_BACKEND" "vulkan"
echo -e "\n${GREEN}✓ Liquid Glass backend set to 'vulkan' (NVIDIA Vulkan Hardware) and saved!${NC}"
sleep 1
return 0
;;
3|toggle)
if [ "$cur" = "opengl" ]; then
LIQUID_GLASS_BACKEND="vulkan"
else
LIQUID_GLASS_BACKEND="opengl"
fi
save_config_setting "LIQUID_GLASS_BACKEND" "$LIQUID_GLASS_BACKEND"
echo -e "\n${GREEN}✓ Liquid Glass backend toggled to: ${LIQUID_GLASS_BACKEND^^} and saved!${NC}"
sleep 1
return 0
;;
0|[qQ]|ESC)
return 0
;;
*)
echo -e "\n${RED}Invalid choice!${NC}"
sleep 1
;;
esac
done
}
if [ -f "$SCRIPT_DIR/config.env" ]; then source "$SCRIPT_DIR/config.env"; elif [ -f "$HOME/.config/mix-manager/config.env" ]; then source "$HOME/.config/mix-manager/config.env"; fi; OUTPUT_DIR="${OUTPUT_DIR:-FLAC_CONVERTED_OUTPUTS}"; ARCHIVE_DIR="${ARCHIVE_DIR:-CONVERTED_WAV_FILES}"; MP3_OUTPUT_DIR="${MP3_OUTPUT_DIR:-MP3_CONVERTED_OUTPUTS}"; WAV_OUTPUT_DIR="${WAV_OUTPUT_DIR:-WAV_CONVERTED_OUTPUTS}"; MP4_OUTPUT_DIR="${MP4_OUTPUT_DIR:-MP4_CONVERTED_OUTPUTS}"; EXTRA_MIX_ARCHIVE_DIRS="${EXTRA_MIX_ARCHIVE_DIRS:-${MIX_ARCHIVE_DIRS:-}}"; export OUTPUT_DIR ARCHIVE_DIR MP3_OUTPUT_DIR WAV_OUTPUT_DIR MP4_OUTPUT_DIR EXTRA_MIX_ARCHIVE_DIRS
is_mix_archive_configured() {
if [ "${MIX_ARCHIVE_CONFIGURED:-false}" = "true" ] && [ -n "${MIX_ARCHIVE_DIR:-}" ]; then return 0; fi; return 1
}
WAN2GP_CONFIGURED="${WAN2GP_CONFIGURED:-false}"; WAN2GP_DIR="${WAN2GP_DIR:-}"; WAN2GP_PYTHON="${WAN2GP_PYTHON:-}"; WAN2GP_OUTPUTS="${WAN2GP_OUTPUTS:-}"; WAN2GP_FLUX_BATCH_DIR="${WAN2GP_FLUX_BATCH_DIR:-}"; WAN2GP_LTX_BATCH_DIR="${WAN2GP_LTX_BATCH_DIR:-}"; WAN2GP_INFTLKBATCH_DIR="${WAN2GP_INFTLKBATCH_DIR:-/run/media/mplanetarian/GAMES1/DATA_DRIVE_MOVED/WAN2GP_INFTLKBATCH}"; export WAN2GP_CONFIGURED WAN2GP_DIR WAN2GP_PYTHON WAN2GP_OUTPUTS WAN2GP_FLUX_BATCH_DIR WAN2GP_LTX_BATCH_DIR WAN2GP_INFTLKBATCH_DIR
is_wan2gp_configured() {
if [ "${WAN2GP_CONFIGURED:-false}" = "true" ] && [ -n "${WAN2GP_OUTPUTS:-}" ] && [ -n "${WAN2GP_FLUX_BATCH_DIR:-}" ] && [ -n "${WAN2GP_LTX_BATCH_DIR:-}" ]; then return 0; fi; return 1
}
_LAST_INTERNET_CHECK=0; _CACHED_INTERNET_STATUS=""
load_header_cache() {
local c_file="$HOME/.config/mix-manager/header_cache.env"; if [ -f "$c_file" ]; then source "$c_file" 2>/dev/null || true; local now="${EPOCHSECONDS:-0}"; [ "$now" -eq 0 ] && now=$(date +%s 2>/dev/null || echo 0); _LAST_STATS_CHECK="$now"; _LAST_CLOUD_CHECK="$now"; _LAST_WEATHER_CHECK="$now"; _LAST_PLANETS_CHECK="$now"; _LAST_AUDIO_IFACE_CHECK="$now"; _LAST_OS_UPDATE_CHECK="$now"; _LAST_INTERNET_CHECK="$now"; _LAST_ALARM_STATUS_CHECK="$now"; fi
}
save_header_cache() {
local c_dir="$HOME/.config/mix-manager"; [ ! -d "$c_dir" ] && mkdir -p "$c_dir" 2>/dev/null || true; local c_file="$c_dir/header_cache.env"; local c_tmp="$c_file.$$.tmp"; { printf '_CACHED_STATS_CORE=%q\n' "${_CACHED_STATS_CORE:-}"; printf '_CACHED_CLOUD_STATUS=%q\n' "${_CACHED_CLOUD_STATUS:-}"; printf '_CACHED_WEATHER_DISPLAY=%q\n' "${_CACHED_WEATHER_DISPLAY:-}"; printf '_CACHED_PLANETS_DISPLAY=%q\n' "${_CACHED_PLANETS_DISPLAY:-}"; printf '_CACHED_AUDIO_IFACE_DISPLAY=%q\n' "${_CACHED_AUDIO_IFACE_DISPLAY:-}"; printf '_CACHED_ALARM_CLOCK_STATUS=%q\n' "${_CACHED_ALARM_CLOCK_STATUS:-}"; printf '_CACHED_OS_BADGE=%q\n' "${_CACHED_OS_BADGE:-}"; printf '_CACHED_OS_UPDATE_STATUS=%q\n' "${_CACHED_OS_UPDATE_STATUS:-}"; printf '_CACHED_INTERNET_STATUS=%q\n' "${_CACHED_INTERNET_STATUS:-online}"; printf '_CACHED_TOP_5_BADGE=%q\n' "${_CACHED_TOP_5_BADGE:-}"; printf '_CACHED_NOW_PLAYING=%q\n' "${_CACHED_NOW_PLAYING:-}"; } > "$c_tmp" 2>/dev/null && mv -f "$c_tmp" "$c_file" 2>/dev/null || rm -f "$c_tmp" 2>/dev/null || true
}
header_cache_signature() {
printf -v "$1" '%s' "${_CACHED_STATS_CORE:-}|${_CACHED_CLOUD_STATUS:-}|${_CACHED_WEATHER_DISPLAY:-}|${_CACHED_PLANETS_DISPLAY:-}|${_CACHED_AUDIO_IFACE_DISPLAY:-}|${_CACHED_ALARM_CLOCK_STATUS:-}|${_CACHED_OS_UPDATE_STATUS:-}|${_CACHED_INTERNET_STATUS:-}|${_CACHED_TOP_5_BADGE:-}|${_CACHED_NOW_PLAYING:-}"
}
refresh_header_cache_worker() {
local lock_dir="$HOME/.config/mix-manager"; local lock_file="$lock_dir/.header_refresh_stamp"; local now="${EPOCHSECONDS:-0}"; [ "$now" -eq 0 ] && now=$(date +%s 2>/dev/null || echo 0); [ -f "$lock_file" ] && [ $((now - $(cat "$lock_file"))) -lt 30 ] && return 0; mkdir -p "$lock_dir" 2>/dev/null; echo "$now" > "$lock_file"; _LAST_CLOUD_CHECK=0 _LAST_WEATHER_CHECK=0 _LAST_PLANETS_CHECK=0 _LAST_AUDIO_IFACE_CHECK=0; _LAST_OS_UPDATE_CHECK=0 _LAST_INTERNET_CHECK=0 _LAST_ALARM_STATUS_CHECK=0 _LAST_TOP_5_CHECK=0; (is_internet_connected; get_os_badge; get_os_update_status; save_header_cache; refresh_now_playing_lines; save_header_cache; get_active_audio_interface_display; get_alarm_clock_status_display; get_top_5_status_badge; get_current_weather; get_planets_above_horizon; save_header_cache; ensure_playlists_generated_dirs --all; show_stats --force; get_cloud_backup_badge; save_header_cache) 2>/dev/null
}
_LAST_HDR_REFRESH_SPAWN=0
maybe_spawn_header_refresh() {
local now="${EPOCHSECONDS:-0}"; [ "$now" -eq 0 ] && now=$(date +%s 2>/dev/null || echo 0); if [ $((now - _LAST_HDR_REFRESH_SPAWN)) -ge 60 ]; then _LAST_HDR_REFRESH_SPAWN="$now"; (refresh_header_cache_worker &>/dev/null &); fi
}
load_header_cache; declare -A _CACHED_ARCHIVE_DIRS
is_internet_connected() {
local now=${EPOCHSECONDS:-0}; if [ "$now" -eq 0 ]; then now=$(date +%s 2>/dev/null || echo 0); fi; if [ $((now - _LAST_INTERNET_CHECK)) -lt 30 ] && [ -n "$_CACHED_INTERNET_STATUS" ]; then [ "$_CACHED_INTERNET_STATUS" = "online" ]; return $?; fi; _LAST_INTERNET_CHECK="$now"; curl -s -I --connect-timeout 0.25 http://1.1.1.1 &>/dev/null && _CACHED_INTERNET_STATUS="online" || _CACHED_INTERNET_STATUS="offline"
}
is_remote_or_cloud_path() {
local p="$1"; [ -z "$p" ] && return 1; case "$p" in *GoogleDrive*|*google-drive*|*rclone*|*Dropbox*|*dropbox*|*iCloud*|*icloud*|*OneDrive*|*onedrive*|*Nextcloud*|*nextcloud*) return 0 ;; esac; if [ -f /proc/mounts ]; then while read -r _ mpoint fstype _; do case "$fstype" in fuse.rclone|nfs|nfs4|cifs|smbfs|fuse.sshfs|davfs) if [[ "$p" == "$mpoint"* ]]; then return 0; fi; ;; esac; done < /proc/mounts 2>/dev/null; fi; return 1
}
get_all_mix_archive_dirs() {
local key="all_mix_archive_dirs"; if [[ -n "${_CACHED_ARCHIVE_DIRS[$key]}" ]]; then printf '%s\n' "${_CACHED_ARCHIVE_DIRS[$key]}"; return 0; fi; local dirs=(); local primary="${MIX_ARCHIVE_DIR:-$SCRIPT_DIR/MIX_ARCHIVE}"; if [ -n "$primary" ]; then local clean_p="${primary//\\//}"; if [[ ! "$clean_p" =~ ^[a-zA-Z]:/$ && "$clean_p" != "/" ]]; then clean_p="${clean_p%/}"; fi; if ! is_remote_or_cloud_path "$clean_p" || is_internet_connected; then dirs+=("$clean_p"); fi; fi; local raw_extras="${EXTRA_MIX_ARCHIVE_DIRS:-${MIX_ARCHIVE_DIRS:-}}"; if [ -n "$raw_extras" ]; then local IFS_BACK="$IFS"; IFS=':,;'$'\n'; for item in $raw_extras; do IFS="$IFS_BACK"; item="${item#"${item%%[![:space:]]*}"}"; item="${item%"${item##*[![:space:]]}"}"; item="${item%\"}"; item="${item#\"}"; item="${item%\'}"; item="${item#\'}"; if [ -n "$item" ]; then local clean_d="$item"; if [[ ! "$clean_d" =~ ^[a-zA-Z]:/$ && "$clean_d" != "/" ]]; then clean_d="${clean_d%/}"; fi; if is_remote_or_cloud_path "$clean_d" && ! is_internet_connected; then continue; fi; dirs+=("$clean_d"); fi; IFS=':,;'$'\n'; done; IFS="$IFS_BACK"; fi; if [ -n "${ICLOUD_PATH:-}" ] && [ -d "$ICLOUD_PATH" ]; then dirs+=("${ICLOUD_PATH%/}"); fi; if [ -n "${DROPBOX_PATH:-}" ] && [ -d "$DROPBOX_PATH" ]; then dirs+=("${DROPBOX_PATH%/}"); fi; _CACHED_ARCHIVE_DIRS[$key]=$(IFS=$'\n'; echo "${dirs[*]}"); printf '%s\n' "${_CACHED_ARCHIVE_DIRS[$key]}"
}
get_all_flac_output_dirs() {
if [ "${1:-}" != "--refresh" ] && [ ${#_CACHED_ALL_FLAC_OUTPUT_DIRS[@]} -gt 0 ]; then printf '%s\n' "${_CACHED_ALL_FLAC_OUTPUT_DIRS[@]}"; return 0; fi; local flac_dirs=(); local seen=(); if [ -n "${OUTPUT_DIR:-}" ] && [ -d "$OUTPUT_DIR" ]; then local clean_out="${OUTPUT_DIR%/}"; flac_dirs+=("$clean_out"); seen+=("$clean_out"); fi; while IFS= read -r adir; do [ -z "$adir" ] && continue; local clean_a="${adir%/}"; if [[ "$clean_a" =~ FLAC_CONVERTED_OUTPUTS$ ]]; then if [ -d "$clean_a" ] && [[ ! " ${seen[*]} " =~ " ${clean_a} " ]]; then seen+=("$clean_a"); flac_dirs+=("$clean_a"); fi; elif [ -d "$clean_a/FLAC_CONVERTED_OUTPUTS" ]; then local sub="$clean_a/FLAC_CONVERTED_OUTPUTS"; if [[ ! " ${seen[*]} " =~ " ${sub} " ]]; then seen+=("$sub"); flac_dirs+=("$sub"); fi; elif [ -d "$clean_a" ]; then if [[ ! " ${seen[*]} " =~ " ${clean_a} " ]]; then local has_flac=0; shopt -s nullglob nocaseglob; local test_flacs=("$clean_a"/*.flac); shopt -u nullglob nocaseglob; [ ${#test_flacs[@]} -gt 0 ] && has_flac=1; if [ "$has_flac" -eq 1 ]; then seen+=("$clean_a"); flac_dirs+=("$clean_a"); fi; fi; fi; done < <(get_all_mix_archive_dirs); _CACHED_ALL_FLAC_OUTPUT_DIRS=("${flac_dirs[@]}"); printf '%s\n' "${flac_dirs[@]}"
}
get_all_wav_archive_dirs() {
if [ "${1:-}" != "--refresh" ] && [ ${#_CACHED_ALL_WAV_ARCHIVE_DIRS[@]} -gt 0 ]; then printf '%s\n' "${_CACHED_ALL_WAV_ARCHIVE_DIRS[@]}"; return 0; fi; local wav_dirs=(); local seen=(); if [ -n "${ARCHIVE_DIR:-}" ] && [ -d "$ARCHIVE_DIR" ]; then local clean_a="${ARCHIVE_DIR%/}"; wav_dirs+=("$clean_a"); seen+=("$clean_a"); fi; while IFS= read -r adir; do [ -z "$adir" ] && continue; local clean_a="${adir%/}"; if [[ "$clean_a" =~ CONVERTED_WAV_FILES$ ]]; then if [ -d "$clean_a" ] && [[ ! " ${seen[*]} " =~ " ${clean_a} " ]]; then seen+=("$clean_a"); wav_dirs+=("$clean_a"); fi; elif [ -d "$clean_a/CONVERTED_WAV_FILES" ]; then local sub="$clean_a/CONVERTED_WAV_FILES"; if [[ ! " ${seen[*]} " =~ " ${sub} " ]]; then seen+=("$sub"); wav_dirs+=("$sub"); fi; fi; done < <(get_all_mix_archive_dirs); _CACHED_ALL_WAV_ARCHIVE_DIRS=("${wav_dirs[@]}"); printf '%s\n' "${wav_dirs[@]}"
}
if is_mix_archive_configured && { ! is_remote_or_cloud_path "$MIX_ARCHIVE_DIR" || is_internet_connected; } && [ -d "$MIX_ARCHIVE_DIR" ]; then cd "$MIX_ARCHIVE_DIR" || exit 1; else MIX_ARCHIVE_DIR="${MIX_ARCHIVE_DIR:-$SCRIPT_DIR/MIX_ARCHIVE}"; [ -d "$SCRIPT_DIR/MIX_ARCHIVE/FLAC_CONVERTED_OUTPUTS" ] || mkdir -p "$SCRIPT_DIR/MIX_ARCHIVE"/{FLAC_CONVERTED_OUTPUTS,CONVERTED_WAV_FILES,MP3_CONVERTED_OUTPUTS,WAV_CONVERTED_OUTPUTS,MP4_CONVERTED_OUTPUTS} 2>/dev/null || true; if [ -d "$MIX_ARCHIVE_DIR" ]; then cd "$MIX_ARCHIVE_DIR" 2>/dev/null || cd "$SCRIPT_DIR/MIX_ARCHIVE" 2>/dev/null || cd "$SCRIPT_DIR" || exit 1; else cd "$SCRIPT_DIR/MIX_ARCHIVE" 2>/dev/null || cd "$SCRIPT_DIR" || exit 1; fi; fi; if [ -n "${MIX_ARCHIVE_DIR:-}" ] && { ! is_remote_or_cloud_path "$MIX_ARCHIVE_DIR" || is_internet_connected; } && [ -d "$MIX_ARCHIVE_DIR" ]; then if ! is_remote_or_cloud_path "$MIX_ARCHIVE_DIR"; then [ -d "$MIX_ARCHIVE_DIR/FLAC_CONVERTED_OUTPUTS" ] || mkdir -p "$MIX_ARCHIVE_DIR"/{FLAC_CONVERTED_OUTPUTS,CONVERTED_WAV_FILES,MP3_CONVERTED_OUTPUTS,WAV_CONVERTED_OUTPUTS,MP4_CONVERTED_OUTPUTS} 2>/dev/null || true; fi; if [ ! -d "$OUTPUT_DIR" ] && [ -d "$MIX_ARCHIVE_DIR/$OUTPUT_DIR" ]; then OUTPUT_DIR="$MIX_ARCHIVE_DIR/$OUTPUT_DIR"; elif [ ! -d "$OUTPUT_DIR" ]; then OUTPUT_DIR="$MIX_ARCHIVE_DIR/FLAC_CONVERTED_OUTPUTS"; fi; if [ ! -d "$ARCHIVE_DIR" ] && [ -d "$MIX_ARCHIVE_DIR/$ARCHIVE_DIR" ]; then ARCHIVE_DIR="$MIX_ARCHIVE_DIR/$ARCHIVE_DIR"; elif [ ! -d "$ARCHIVE_DIR" ]; then ARCHIVE_DIR="$MIX_ARCHIVE_DIR/CONVERTED_WAV_FILES"; fi; if [ ! -d "$MP3_OUTPUT_DIR" ] && [ -d "$MIX_ARCHIVE_DIR/$MP3_OUTPUT_DIR" ]; then MP3_OUTPUT_DIR="$MIX_ARCHIVE_DIR/$MP3_OUTPUT_DIR"; elif [ ! -d "$MP3_OUTPUT_DIR" ]; then MP3_OUTPUT_DIR="$MIX_ARCHIVE_DIR/MP3_CONVERTED_OUTPUTS"; fi; if [ ! -d "$WAV_OUTPUT_DIR" ] && [ -d "$MIX_ARCHIVE_DIR/$WAV_OUTPUT_DIR" ]; then WAV_OUTPUT_DIR="$MIX_ARCHIVE_DIR/$WAV_OUTPUT_DIR"; elif [ ! -d "$WAV_OUTPUT_DIR" ]; then WAV_OUTPUT_DIR="$MIX_ARCHIVE_DIR/WAV_CONVERTED_OUTPUTS"; fi; if [ ! -d "$MP4_OUTPUT_DIR" ] && [ -d "$MIX_ARCHIVE_DIR/$MP4_OUTPUT_DIR" ]; then MP4_OUTPUT_DIR="$MIX_ARCHIVE_DIR/$MP4_OUTPUT_DIR"; elif [ ! -d "$MP4_OUTPUT_DIR" ]; then MP4_OUTPUT_DIR="$MIX_ARCHIVE_DIR/MP4_CONVERTED_OUTPUTS"; fi; export OUTPUT_DIR ARCHIVE_DIR MP3_OUTPUT_DIR WAV_OUTPUT_DIR MP4_OUTPUT_DIR; fi
ensure_playlists_generated_dirs() {
local mode="${1:-}"; [ -d "$SCRIPT_DIR/PLAYLISTS_GENERATED" ] || mkdir -p "$SCRIPT_DIR/PLAYLISTS_GENERATED" 2>/dev/null || true; if [ "$mode" != "--all" ]; then local primary="${MIX_ARCHIVE_DIR:-}"; primary="${primary//\\//}"; primary="${primary%/}"; if [ -n "$primary" ] && ! is_remote_or_cloud_path "$primary" && [ -d "$primary" ]; then [ -d "$primary/PLAYLISTS_GENERATED" ] || mkdir -p "$primary/PLAYLISTS_GENERATED" 2>/dev/null || true; fi; return 0; fi; local all_arch_dirs=(); while IFS= read -r adir; do [ -n "$adir" ] && all_arch_dirs+=("$adir"); done < <(get_all_mix_archive_dirs 2>/dev/null); for pdir in "${all_arch_dirs[@]}"; do if is_remote_or_cloud_path "$pdir"; then continue; fi; if [ -d "$pdir" ]; then [ -d "$pdir/PLAYLISTS_GENERATED" ] || mkdir -p "$pdir/PLAYLISTS_GENERATED" 2>/dev/null || true; if [[ "$pdir" =~ (FLAC_CONVERTED_OUTPUTS|CONVERTED_WAV_FILES|MP3_CONVERTED_OUTPUTS)/?$ ]]; then local pparent; pparent="$(dirname "$pdir")"; if [ -d "$pparent" ] && [ ! -d "$pparent/PLAYLISTS_GENERATED" ]; then mkdir -p "$pparent/PLAYLISTS_GENERATED" 2>/dev/null || true; fi; fi; fi; done
}
ensure_playlists_generated_dirs; DEFAULT_AUDIO_PLAYER="${DEFAULT_AUDIO_PLAYER:-mp_liquid_glass}"; LIQUID_GLASS_BACKEND="${LIQUID_GLASS_BACKEND:-opengl}"; export LIQUID_GLASS_BACKEND; AUTO_PLAY_ON_STARTUP="${AUTO_PLAY_ON_STARTUP:-true}"; AUTO_SHOW_COVER_ON_STARTUP="${AUTO_SHOW_COVER_ON_STARTUP:-false}"; AUTO_SHOW_TRACKLIST_ON_STARTUP="${AUTO_SHOW_TRACKLIST_ON_STARTUP:-false}"; TRACKLIST_VIEWER="${TRACKLIST_VIEWER:-console}"; AUTO_PLAY_MIX_SELECTION="${AUTO_PLAY_MIX_SELECTION:-latest}"; DEFAULT_VIDEO_PLAYER="${DEFAULT_VIDEO_PLAYER:-vlc}"; AUTO_PLAY_YOUTUBE_ON_STARTUP="${AUTO_PLAY_YOUTUBE_ON_STARTUP:-false}"; STARTUP_YOUTUBE_URL="${STARTUP_YOUTUBE_URL:-}"; WEATHER_ENABLED="${WEATHER_ENABLED:-true}"; WEATHER_LOCATION="${WEATHER_LOCATION:-Swansea, UK}"; STARTUP_AUTOPLAY_EXECUTED=0; STARTUP_AUTOPLAY_NOTICE=""; STARTUP_SPEK_NOTICE=""
DAILY_REPORTS_ENABLED="${DAILY_REPORTS_ENABLED:-true}"; DAILY_REPORTS_TIME="${DAILY_REPORTS_TIME:-10:00}"; MONTHLY_REPORTS_ENABLED="${MONTHLY_REPORTS_ENABLED:-true}"; YEARLY_REPORTS_ENABLED="${YEARLY_REPORTS_ENABLED:-true}"; LAST_DAILY_REPORT_DATE="${LAST_DAILY_REPORT_DATE:-}"; LAST_MONTHLY_REPORT_DATE="${LAST_MONTHLY_REPORT_DATE:-}"; LAST_YEARLY_REPORT_DATE="${LAST_YEARLY_REPORT_DATE:-}"
save_config_setting() {
local key="$1" val="${2//\\//}" cfg="${SCRIPT_DIR:-$PWD}/config.env" f line found out; [ ! -f "$cfg" ] && [ ! -w "${cfg%/*}" ] && cfg="$PWD/config.env"; local targets=("$cfg"); [ -d "$HOME/.config/mix-manager" ] && targets+=("$HOME/.config/mix-manager/config.env"); for f in "${targets[@]}"; do found=0; out=""; if [ -f "$f" ]; then while IFS= read -r line || [ -n "$line" ]; do if [[ "$line" =~ ^[[:space:]]*${key}= ]]; then out+="${key}=\"${val}\""$'\n'; found=1; else out+="${line}"$'\n'; fi; done < "$f"; fi; (( !found )) && out+="${key}=\"${val}\""$'\n'; printf '%s' "$out" > "$f" 2>/dev/null || true; done
}
log_mp_error() {
local comp="${1:-MixManager}" msg="${2:-Unknown error}" details="${3:-}" log_file="${SCRIPT_DIR}/MP_Error.log" stamp; stamp="$(date '+%Y-%m-%d %H:%M:%S')"
{ echo "[$stamp] [ERROR] [$comp] $msg"; [ -n "$details" ] && echo "  Details: $details"; echo "----------------------------------------------------------------------"; } >> "$log_file" 2>/dev/null || true
[ -d "$HOME/.config/mix-manager" ] && { echo "[$stamp] [ERROR] [$comp] $msg"; [ -n "$details" ] && echo "  Details: $details"; echo "----------------------------------------------------------------------"; } >> "$HOME/.config/mix-manager/MP_Error.log" 2>/dev/null || true
}
track_user_activity() {
local action="$1" cat="${2:-menu_operation}" dur="${3:-0}" st="${4:-success}" det="${5:-}"
command -v update_mp_bridge_action &>/dev/null && update_mp_bridge_action "$action" "$cat"
[ -f "$SCRIPT_DIR/scripts/mp_activity_tracker.py" ] && python3 "$SCRIPT_DIR/scripts/mp_activity_tracker.py" --record "$action" "$cat" "$dur" "$det" &>/dev/null || true
}
run_sub_script() {
local script_name="$1"; shift; local bash_bin="${BASH:-bash}" rc=0 t_start="${EPOCHSECONDS:-$(date +%s 2>/dev/null || echo 0)}"
track_user_activity "Run Script: $script_name" "script_execution" 0 "pending" "Args: $*"
if [ -x "$SCRIPT_DIR/scripts/$script_name" ]; then "$SCRIPT_DIR/scripts/$script_name" "$@"; rc=$?; elif [ -f "$SCRIPT_DIR/scripts/$script_name" ]; then "$bash_bin" "$SCRIPT_DIR/scripts/$script_name" "$@"; rc=$?; elif [ -x "$SCRIPT_DIR/$script_name" ]; then "$SCRIPT_DIR/$script_name" "$@"; rc=$?; elif [ -f "$SCRIPT_DIR/$script_name" ]; then "$bash_bin" "$SCRIPT_DIR/$script_name" "$@"; elif [ -x "./$script_name" ]; then "./$script_name" "$@"; rc=$?; elif [ -f "./$script_name" ]; then "$bash_bin" "./$script_name" "$@"; elif command -v "$script_name" &>/dev/null; then "$script_name" "$@"; rc=$?; else echo -e "${RED}Error: Script '$script_name' not found in $(pwd) or $SCRIPT_DIR!${NC}"; rc=1; fi
local t_end="${EPOCHSECONDS:-$(date +%s 2>/dev/null || echo 0)}" dur=$((t_end - t_start))
if [ "$rc" -ne 0 ]; then log_mp_error "run_sub_script" "Script '$script_name' failed with exit code $rc" "Args: $*"; track_user_activity "Run Script: $script_name" "script_execution" "$dur" "error" "Exit code: $rc"; else track_user_activity "Run Script: $script_name" "script_execution" "$dur" "success" "Completed"; fi
return "$rc"
}
is_mix_in_strawberry_playlist() {
local mix_file="$1"; [ -z "$mix_file" ] && return 1
python3 -c "
import sqlite3, os, sys, urllib.parse
filepath = sys.argv[1]
fname = os.path.basename(filepath)
stem = os.path.splitext(fname)[0]
enc_fname = urllib.parse.quote(fname)
db_candidates = [
    os.path.expanduser('~/.local/share/strawberry/strawberry/strawberry.db'),
    os.path.expanduser('~/.var/app/org.strawberrymusicplayer.strawberry/data/strawberry/strawberry/strawberry.db'),
    os.path.expanduser('~/Library/Application Support/Strawberry/strawberry/strawberry.db'),
]
found = False
for db in db_candidates:
    if os.path.isfile(db):
        try:
            conn = sqlite3.connect(f'file:{db}?mode=ro', uri=True)
            cur = conn.cursor()
            query = '''SELECT count(*) FROM playlist_items WHERE url LIKE ? OR url LIKE ? OR url LIKE ? OR title = ? OR title LIKE ?'''
            cur.execute(query, (f'%{fname}%', f'%{enc_fname}%', f'%{filepath}%', stem, f'%{stem}%'))
            cnt = cur.fetchone()[0]
            conn.close()
            if cnt > 0:
                found = True
                break
        except Exception:
            pass
sys.exit(0 if found else 1)
" "$mix_file" 2>/dev/null
}
is_mix_in_audacious_playlist() {
local mix_file="$1"; [ -z "$mix_file" ] && return 1; local bname; bname="$(basename "$mix_file")"; local stem="${bname%.*}"; if command -v audtool &>/dev/null; then if audtool playlist-display 2>/dev/null | grep -i -F "$stem" &>/dev/null; then return 0; fi; fi; return 1
}
_mpris_player_info() {
local pfx="$1" pname="$2"; eval "${pfx}_RUNNING=0 ${pfx}_STATE='' ${pfx}_TITLE='' ${pfx}_ARTIST='' ${pfx}_ALBUM='' ${pfx}_RAW_PATH='' ${pfx}_RESOLVED_PATH='' ${pfx}_FILE_EXISTS=0 ${pfx}_FILE_SIZE='' ${pfx}_POSITION=0 ${pfx}_DURATION=0 ${pfx}_POS_FMT='00:00' ${pfx}_DUR_FMT='00:00' ${pfx}_PROGRESS_PCT=0"; if [ "$pname" = "audacious" ]; then pgrep -x audacious &>/dev/null || (command -v qdbus &>/dev/null && timeout 0.5 qdbus org.mpris.MediaPlayer2.audacious &>/dev/null) || return 1; else pgrep -x "$pname" &>/dev/null || (command -v qdbus &>/dev/null && timeout 0.5 qdbus "org.mpris.MediaPlayer2.$pname" &>/dev/null) || return 1; fi; local raw
raw=$(python3 -c '
import subprocess, urllib.parse, sys, os, shutil
pname = sys.argv[1]
dest, path, iface = f"org.mpris.MediaPlayer2.{pname}", "/org/mpris/MediaPlayer2", "org.mpris.MediaPlayer2.Player"
def run(cmd):
    return subprocess.check_output(cmd, stderr=subprocess.DEVNULL, timeout=1.5).decode("utf-8", errors="ignore").strip()
def get_prop(prop):
    try: return run(["qdbus", dest, path, f"{iface}.{prop}"])
    except Exception: pass
    if pname == "strawberry":
        try:
            if prop == "PlaybackStatus": return run(["playerctl", "-p", "strawberry", "status"])
            if prop == "Position": return run(["playerctl", "-p", "strawberry", "position"])
        except Exception: pass
    try:
        for line in run(["dbus-send", "--print-reply", f"--dest={dest}", path, "org.freedesktop.DBus.Properties.Get", "string:" + iface, "string:" + prop]).splitlines():
            if "variant" in line:
                p = line.strip().split(None, 2)
                if len(p) >= 3: return p[2].strip().strip("\"")
    except Exception: pass
    return ""
def get_meta():
    try:
        m = {k.strip(): v.strip() for l in run(["qdbus", dest, path, f"{iface}.Metadata"]).splitlines() if ": " in l for k, v in [l.split(": ", 1)]}
        if m: return m
    except Exception: pass
    if pname == "strawberry":
        try:
            return {k: run(["playerctl", "-p", "strawberry", "metadata", k]) for k in ("xesam:url", "xesam:title", "xesam:artist", "xesam:album", "mpris:length")}
        except Exception: pass
    return {}
status, meta = get_prop("PlaybackStatus"), get_meta()
aud_cmd = ["audtool"] if (shutil.which("audtool") and pname == "audacious") else None
if aud_cmd and (not status or not meta):
    try:
        if not status: status = run(aud_cmd + ["playback-status"])
        if not meta:
            fn, ln = run(aud_cmd + ["current-song-filename"]), run(aud_cmd + ["current-song-length-seconds"])
            meta = {"xesam:title": run(aud_cmd + ["current-song"]), "xesam:url": ("file://" + fn) if fn else "", "mpris:length": str(int(ln)*1000000) if ln.isdigit() else "0"}
    except Exception: pass
if not status: sys.exit(1)
u = meta.get("xesam:url", "")
u = urllib.parse.unquote(u[7:] if u.startswith("file://") else (u[6:] if u.startswith("file:/") else u))
title, artist, album = meta.get("xesam:title", ""), meta.get("xesam:artist", ""), meta.get("xesam:album", "") or meta.get("album", "")
if not title and u: title = os.path.splitext(os.path.basename(u))[0]
def to_sec(v):
    try: return int(v) // 1000000
    except Exception:
        try: return int(float(v))
        except Exception: return 0
dur_s, pos_s = to_sec(meta.get("mpris:length", "0")), to_sec(get_prop("Position"))
if aud_cmd and (dur_s == 0 or pos_s == 0):
    try:
        if dur_s == 0:
            ln = run(aud_cmd + ["current-song-length-seconds"])
            if ln.isdigit(): dur_s = int(ln)
        if pos_s == 0:
            oln = run(aud_cmd + ["current-song-output-length-seconds"])
            if oln.isdigit(): pos_s = int(oln)
    except Exception: pass
print("\x1f".join([status.lower(), title, artist, album, u, str(max(0, int(pos_s))), str(max(0, int(dur_s)))]))
' "$pname" 2>/dev/null) || return 1
[ -z "$raw" ] && return 1; local st ti ar al rp po du; IFS=$'\x1f' read -r st ti ar al rp po du <<< "$raw"; po=${po:-0}; du=${du:-0}; local pf df pct=0 res="$rp" ex=0 sz=""; pf=$(_fmt_sec "$po"); df=$(_fmt_sec "$du"); (( du > 0 )) && pct=$(( po * 100 / du )); if [ -n "$res" ] && [ -e "$res" ]; then ex=1; else local alt="${rp/#\/media\//\/run\/media\/}"; if [ -n "$alt" ] && [ -e "$alt" ]; then res="$alt"; ex=1; else local pid fd lt; for pid in $(pgrep -x "$pname" 2>/dev/null); do for fd in /proc/"$pid"/fd/*; do [ -e "$fd" ] || continue; lt=$(readlink "$fd" 2>/dev/null); case "$lt" in *.flac|*.wav|*.mp3|*.m4a|*.ogg) [ -f "$lt" ] && { res="$lt"; ex=1; break 2; } ;; esac; done; done; fi; fi; (( ex )) && sz=$(ls -lh "$res" 2>/dev/null | awk '{print $5}'); printf -v "${pfx}_RUNNING" '%s' 1; printf -v "${pfx}_STATE" '%s' "$st"; printf -v "${pfx}_TITLE" '%s' "$ti"; printf -v "${pfx}_ARTIST" '%s' "$ar"; printf -v "${pfx}_ALBUM" '%s' "$al"; printf -v "${pfx}_RAW_PATH" '%s' "$rp"; printf -v "${pfx}_RESOLVED_PATH" '%s' "$res"; printf -v "${pfx}_FILE_EXISTS" '%s' "$ex"; printf -v "${pfx}_FILE_SIZE" '%s' "$sz"; printf -v "${pfx}_POSITION" '%s' "$po"; printf -v "${pfx}_DURATION" '%s' "$du"; printf -v "${pfx}_POS_FMT" '%s' "$pf"; printf -v "${pfx}_DUR_FMT" '%s' "$df"; printf -v "${pfx}_PROGRESS_PCT" '%s' "$pct"; return 0
}
get_audacious_track_info() { _mpris_player_info AUDACIOUS audacious; }
get_strawberry_track_info() { _mpris_player_info STRAWBERRY strawberry; }
_CACHED_PID_CHECK_PID=""; _CACHED_PID_CHECK_TIME=0; _CACHED_PID_CHECK_RES=1
is_system_pid_alive() {
local pid_to_check="$1"; [ -z "$pid_to_check" ] && return 1; local now="$SECONDS"; if [ "$pid_to_check" = "$_CACHED_PID_CHECK_PID" ] && [ $(( now - _CACHED_PID_CHECK_TIME )) -lt 3 ]; then return "$_CACHED_PID_CHECK_RES"; fi; local alive=1; if [[ "$UNAME_S" =~ (MINGW|MSYS|CYGWIN) ]]; then if ps -W 2>/dev/null | awk -v pid="$pid_to_check" '$4 == pid {found=1; exit} END {exit !found}'; then alive=0; fi; else if kill -0 "$pid_to_check" 2>/dev/null; then alive=0; fi; fi; _CACHED_PID_CHECK_PID="$pid_to_check"; _CACHED_PID_CHECK_TIME="$now"; _CACHED_PID_CHECK_RES="$alive"; return "$alive"
}
_CACHED_PLAYER_CHECK_TIME=-10; _CACHED_PLAYER_ACTIVE_RES=1
get_mp_audio_player_track_info() {
local now="$SECONDS"; if [ $(( now - _CACHED_PLAYER_CHECK_TIME )) -lt 1 ] && [ -n "$MP_PLAYER_STATE" ]; then return "$_CACHED_PLAYER_ACTIVE_RES"; fi; _CACHED_PLAYER_CHECK_TIME="$now"; MP_PLAYER_RUNNING=0; MP_PLAYER_STATE=""; MP_PLAYER_MODE="MIX_ARCHIVE"; MP_PLAYER_TITLE=""; MP_PLAYER_RAW_PATH=""; MP_PLAYER_RESOLVED_PATH=""; MP_PLAYER_FILE_EXISTS=0; MP_PLAYER_FILE_SIZE=""; MP_PLAYER_POS_SEC=0; MP_PLAYER_DUR_SEC=0; MP_PLAYER_POS_FMT="00:00"; MP_PLAYER_DUR_FMT="00:00"; MP_PLAYER_PROGRESS_PCT=0; MP_PLAYER_MINI_EQ=""; MP_PLAYER_VOLUME=85; MP_PLAYER_RECORDING="false"; local state_file="$HOME/.config/mix-manager/mp_player_state.json"; if [ ! -f "$state_file" ]; then _CACHED_PLAYER_ACTIVE_RES=1; return 1; fi; local content=""; read -r content < "$state_file" 2>/dev/null || true; if [ -z "$content" ]; then _CACHED_PLAYER_ACTIVE_RES=1; return 1; fi; local is_run="false" p_pid=0; [[ "$content" =~ \"running\":\ *(true|false) ]] && is_run="${BASH_REMATCH[1]}"; if [ "$is_run" != "true" ]; then _CACHED_PLAYER_ACTIVE_RES=1; return 1; fi; [[ "$content" =~ \"state\":\ *\"([^\"]+)\" ]] && MP_PLAYER_STATE="${BASH_REMATCH[1]}"; if [ "$MP_PLAYER_STATE" = "stopped" ]; then _CACHED_PLAYER_ACTIVE_RES=1; return 1; fi; [[ "$content" =~ \"mode\":\ *\"([^\"]+)\" ]] && MP_PLAYER_MODE="${BASH_REMATCH[1]}"; [[ "$content" =~ \"position_sec\":\ *([0-9.]+) ]] && MP_PLAYER_POS_SEC="${BASH_REMATCH[1]}"; [[ "$content" =~ \"duration_sec\":\ *([0-9.]+) ]] && MP_PLAYER_DUR_SEC="${BASH_REMATCH[1]}"; [[ "$content" =~ \"position_fmt\":\ *\"([^\"]+)\" ]] && MP_PLAYER_POS_FMT="${BASH_REMATCH[1]}"; [[ "$content" =~ \"duration_fmt\":\ *\"([^\"]+)\" ]] && MP_PLAYER_DUR_FMT="${BASH_REMATCH[1]}"; [[ "$content" =~ \"progress_pct\":\ *([0-9.]+) ]] && MP_PLAYER_PROGRESS_PCT="${BASH_REMATCH[1]}"; [[ "$content" =~ \"title\":\ *\"([^\"]+)\" ]] && MP_PLAYER_TITLE="${BASH_REMATCH[1]}"; [[ "$content" =~ \"mini_eq\":\ *\"([^\"]*)\" ]] && MP_PLAYER_MINI_EQ="${BASH_REMATCH[1]}"; [[ "$content" =~ \"volume\":\ *([0-9]+) ]] && MP_PLAYER_VOLUME="${BASH_REMATCH[1]}"; [[ "$content" =~ \"recording\":\ *(true|false) ]] && MP_PLAYER_RECORDING="${BASH_REMATCH[1]}"; [[ "$content" =~ \"path\":\ *\"([^\"]+)\" ]] && MP_PLAYER_RAW_PATH="${BASH_REMATCH[1]}"; [[ "$content" =~ \"pid\":\ *([0-9]+) ]] && p_pid="${BASH_REMATCH[1]}"; if [ -n "$p_pid" ] && [ "$p_pid" -gt 0 ] 2>/dev/null; then if ! is_system_pid_alive "$p_pid"; then _CACHED_PLAYER_ACTIVE_RES=1; return 1; fi; fi; MP_PLAYER_RUNNING=1; MP_PLAYER_RESOLVED_PATH="$MP_PLAYER_RAW_PATH"; [ -n "$MP_PLAYER_RESOLVED_PATH" ] && [ -f "$MP_PLAYER_RESOLVED_PATH" ] && MP_PLAYER_FILE_EXISTS=1; _CACHED_PLAYER_ACTIVE_RES=0; return 0
}
manage_mp_audio_player() {
local py_script="$SCRIPT_DIR/MP_Audio_Player.py"; [ ! -f "$py_script" ] && py_script="$SCRIPT_DIR/scripts/MP_Audio_Player.py"; if [ -f "$py_script" ]; then python3 "$py_script" --interactive "$@"; else echo -e "${RED}Error: MP_Audio_Player.py not found!${NC}"; press_enter; fi
}
manage_music_folders_menu() {
local py_script="$SCRIPT_DIR/scripts/music_folders_manager.py"; [ ! -f "$py_script" ] && py_script="$SCRIPT_DIR/music_folders_manager.py"; if [ -f "$py_script" ]; then python3 "$py_script" --menu "$@"; else echo -e "${RED}Error: music_folders_manager.py not found!${NC}"; press_enter; fi
}
run_wan2gp_infinite_talker() {
local script="$SCRIPT_DIR/scripts/MP_Infinite_Talker.py"; [ ! -f "$script" ] && script="$SCRIPT_DIR/MP_Infinite_Talker.py"; [ ! -f "$script" ] && script="$SCRIPT_DIR/MP_Infinite_Talker.sh"; if [ -f "$script" ]; then python3 "$script" "$@"; else echo -e "${RED}Error: MP_Infinite_Talker.py not found at $script!${NC}"; press_enter; fi
}
get_cliamp_track_info() {
CLIAMP_RUNNING=0 CLIAMP_STATE="" CLIAMP_TITLE="" CLIAMP_ARTIST="" CLIAMP_RAW_PATH="" CLIAMP_RESOLVED_PATH="" CLIAMP_FILE_EXISTS=0 CLIAMP_FILE_SIZE="" CLIAMP_POSITION=0 CLIAMP_DURATION=0 CLIAMP_POS_FMT="00:00" CLIAMP_DUR_FMT="00:00" CLIAMP_PROGRESS_PCT=0; local cliamp_bin="cliamp"; if ! command -v cliamp &>/dev/null; then if [ -x "$SCRIPT_DIR/bin/cliamp" ]; then cliamp_bin="$SCRIPT_DIR/bin/cliamp"; elif [ -x "$HOME/.local/bin/cliamp" ]; then cliamp_bin="$HOME/.local/bin/cliamp"; else return 1; fi; fi; local pids; pids=$(pgrep -x cliamp 2>/dev/null); [ -z "$pids" ] && return 1; CLIAMP_RUNNING=1; local status_json parsed; status_json=$("$cliamp_bin" status --json 2>/dev/null); [ -z "$status_json" ] && return 1; parsed=$(jq -r 'select(.ok==true)|[(.state//"unknown"),(.track.title//""),(.track.artist//""),(.track.path//""),((.position//0)|floor|tostring),((.duration//0)|floor|tostring)]|join("\u001f")' <<<"$status_json" 2>/dev/null); [ -z "$parsed" ] && return 1; IFS=$'\x1f' read -r CLIAMP_STATE CLIAMP_TITLE CLIAMP_ARTIST CLIAMP_RAW_PATH CLIAMP_POSITION CLIAMP_DURATION <<< "$parsed"; CLIAMP_POSITION=${CLIAMP_POSITION:-0}; CLIAMP_DURATION=${CLIAMP_DURATION:-0}; CLIAMP_POS_FMT=$(_fmt_sec "$CLIAMP_POSITION"); CLIAMP_DUR_FMT=$(_fmt_sec "$CLIAMP_DURATION"); (( CLIAMP_DURATION > 0 )) && CLIAMP_PROGRESS_PCT=$((CLIAMP_POSITION * 100 / CLIAMP_DURATION)); CLIAMP_RESOLVED_PATH="$CLIAMP_RAW_PATH"; if [ -n "$CLIAMP_RESOLVED_PATH" ] && [ -e "$CLIAMP_RESOLVED_PATH" ]; then CLIAMP_FILE_EXISTS=1; else local alt="${CLIAMP_RAW_PATH/#\/media\//\/run\/media\/}" bname="${CLIAMP_RAW_PATH##*/}"; if [ -n "$alt" ] && [ -e "$alt" ]; then CLIAMP_RESOLVED_PATH="$alt"; CLIAMP_FILE_EXISTS=1; else local pid fd target dir; for pid in $pids; do for fd in /proc/"$pid"/fd/*; do [ -e "$fd" ] || continue; target=$(readlink "$fd" 2>/dev/null); if [ -n "$target" ] && [ "$bname" = "${target##*/}" ] && [ -e "$target" ]; then CLIAMP_RESOLVED_PATH="$target"; CLIAMP_FILE_EXISTS=1; break 2; fi; done; done; if [ "$CLIAMP_FILE_EXISTS" -eq 0 ] && [ -n "$bname" ]; then for dir in "${MIX_ARCHIVE_DIR:-}" "${MIX_ARCHIVE_DIR:-}/CONVERTED_WAV_FILES" "${MIX_ARCHIVE_DIR:-}/FLAC_CONVERTED_OUTPUTS" "$SCRIPT_DIR/MIX_ARCHIVE" "$SCRIPT_DIR/MIX_ARCHIVE/CONVERTED_WAV_FILES" "$SCRIPT_DIR/MIX_ARCHIVE/FLAC_CONVERTED_OUTPUTS" "/Volumes/WD BLACK B/MIX_ARCHIVE" "/Volumes/WD BLACK B/MIX_ARCHIVE/CONVERTED_WAV_FILES" "/Volumes/WD BLACK B/MIX_ARCHIVE/FLAC_CONVERTED_OUTPUTS" "/Volumes/MIX_ARCHIVE" "/d/MIX_ARCHIVE" "/e/MIX_ARCHIVE" "D:/MIX_ARCHIVE" "E:/MIX_ARCHIVE" "/mnt/d/MIX_ARCHIVE" "$SCRIPT_DIR" "$SCRIPT_DIR/CONVERTED_WAV_FILES" "$SCRIPT_DIR/FLAC_CONVERTED_OUTPUTS" "$PWD"; do if [ -n "$dir" ] && [ -f "$dir/$bname" ]; then CLIAMP_RESOLVED_PATH="$dir/$bname"; CLIAMP_FILE_EXISTS=1; break; fi; done; fi; fi; fi; (( CLIAMP_FILE_EXISTS )) && CLIAMP_FILE_SIZE=$(ls -lh "$CLIAMP_RESOLVED_PATH" 2>/dev/null | awk '{print $5}'); return 0
}
save_playback_resume_state() {
    local resume_file="$HOME/.config/mix-manager/playback_resume.json"
    local r_path="" r_pos=0 r_dur=0 r_title="" r_player="${DEFAULT_AUDIO_PLAYER:-mp_audio_player}" r_mode="MIX_ARCHIVE"
    if get_mp_audio_player_track_info 2>/dev/null && [ -n "${MP_PLAYER_RAW_PATH:-}" ] && [ -f "${MP_PLAYER_RAW_PATH:-}" ]; then
        r_path="$MP_PLAYER_RAW_PATH"
        r_pos="${MP_PLAYER_POS_SEC:-0}"
        r_dur="${MP_PLAYER_DUR_SEC:-0}"
        r_title="${MP_PLAYER_TITLE:-}"
        r_player="mp_audio_player"
        r_mode="${MP_PLAYER_MODE:-MIX_ARCHIVE}"
    elif get_audacious_track_info 2>/dev/null && [ -n "${AUDACIOUS_RESOLVED_PATH:-}" ] && [ -f "${AUDACIOUS_RESOLVED_PATH:-}" ]; then
        r_path="$AUDACIOUS_RESOLVED_PATH"
        r_pos="${AUDACIOUS_POSITION:-0}"
        r_dur="${AUDACIOUS_DURATION:-0}"
        r_title="${AUDACIOUS_TITLE:-}"
        r_player="audacious"
    elif get_strawberry_track_info 2>/dev/null && [ -n "${STRAWBERRY_RESOLVED_PATH:-}" ] && [ -f "${STRAWBERRY_RESOLVED_PATH:-}" ]; then
        r_path="$STRAWBERRY_RESOLVED_PATH"
        r_pos="${STRAWBERRY_POSITION:-0}"
        r_dur="${STRAWBERRY_DURATION:-0}"
        r_title="${STRAWBERRY_TITLE:-}"
        r_player="strawberry"
    elif get_cliamp_track_info 2>/dev/null && [ -n "${CLIAMP_RESOLVED_PATH:-}" ] && [ -f "${CLIAMP_RESOLVED_PATH:-}" ]; then
        r_path="$CLIAMP_RESOLVED_PATH"
        r_pos="${CLIAMP_POSITION:-0}"
        r_dur="${CLIAMP_DURATION:-0}"
        r_title="${CLIAMP_TITLE:-}"
        r_player="cliamp"
    elif command -v detect_currently_playing_mix &>/dev/null; then
        local detected=""
        detected="$(detect_currently_playing_mix 2>/dev/null || true)"
        if [ -n "$detected" ] && [ -f "$detected" ]; then
            r_path="$detected"
            r_title="$(basename "$detected")"
            r_player="${DEFAULT_AUDIO_PLAYER:-audacious}"
        fi
    fi
    if [ -n "$r_path" ] && [ -f "$r_path" ]; then
        mkdir -p "$(dirname "$resume_file")" 2>/dev/null || true
        python3 - "$resume_file" "$r_path" "$r_pos" "$r_dur" "$r_title" "$r_player" "$r_mode" << 'PY' 2>/dev/null || true
import sys, json, time, os
dst, path, pos, dur, title, player, mode = sys.argv[1:8]
try: pos = float(pos)
except Exception: pos = 0.0
try: dur = float(dur)
except Exception: dur = 0.0
if pos <= 0.0 and os.path.exists(dst):
    try:
        with open(dst, "r", encoding="utf-8") as f_prev:
            prev_data = json.load(f_prev)
        if isinstance(prev_data, dict) and prev_data.get("path") == path:
            prev_pos = float(prev_data.get("position_sec", 0.0))
            if prev_pos > 0.0:
                pos = prev_pos
    except Exception:
        pass
data = dict(
    path=path,
    position_sec=round(pos, 2),
    duration_sec=round(dur, 2),
    title=title or os.path.basename(path),
    player=player,
    mode=mode,
    timestamp=time.time(),
)
tmp = dst + ".tmp"
with open(tmp, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2)
os.replace(tmp, dst)
PY
    fi
}
case "${1:-}" in --music|--music-mode|music) shift; manage_music_folders_menu "$@"; exit 0 ;; --track|--current-track|--audacious-path|--strawberry-path|--cliamp-path|-p) if get_audacious_track_info 2>/dev/null && [ -n "$AUDACIOUS_RESOLVED_PATH" ]; then echo "$AUDACIOUS_RESOLVED_PATH"; exit 0; elif get_strawberry_track_info 2>/dev/null && [ -n "$STRAWBERRY_RESOLVED_PATH" ]; then echo "$STRAWBERRY_RESOLVED_PATH"; exit 0; elif get_cliamp_track_info 2>/dev/null && [ -n "$CLIAMP_RESOLVED_PATH" ]; then echo "$CLIAMP_RESOLVED_PATH"; exit 0; else detected_p=$(detect_currently_playing_mix 2>/dev/null); [ -n "$detected_p" ] && [ -f "$detected_p" ] && { echo "$detected_p"; exit 0; }; echo "Error: No track currently playing in Audacious, Strawberry, cliamp, or supported players." >&2; exit 1; fi ;; --audacious-info) if get_audacious_track_info 2>/dev/null; then printf "State: %s\nTitle: %s\nArtist: %s\nAlbum: %s\nTime: %s / %s (%s%%)\nPath: %s\n" "$AUDACIOUS_STATE" "$AUDACIOUS_TITLE" "$AUDACIOUS_ARTIST" "$AUDACIOUS_ALBUM" "$AUDACIOUS_POS_FMT" "$AUDACIOUS_DUR_FMT" "$AUDACIOUS_PROGRESS_PCT" "$AUDACIOUS_RESOLVED_PATH"; [ -n "$AUDACIOUS_FILE_SIZE" ] && echo "Size: $AUDACIOUS_FILE_SIZE"; exit 0; else echo "Error: Audacious is not running or no track playing." >&2; exit 1; fi ;; --strawberry-info) if get_strawberry_track_info 2>/dev/null; then printf "State: %s\nTitle: %s\nArtist: %s\nAlbum: %s\nTime: %s / %s (%s%%)\nPath: %s\n" "$STRAWBERRY_STATE" "$STRAWBERRY_TITLE" "$STRAWBERRY_ARTIST" "$STRAWBERRY_ALBUM" "$STRAWBERRY_POS_FMT" "$STRAWBERRY_DUR_FMT" "$STRAWBERRY_PROGRESS_PCT" "$STRAWBERRY_RESOLVED_PATH"; [ -n "$STRAWBERRY_FILE_SIZE" ] && echo "Size: $STRAWBERRY_FILE_SIZE"; exit 0; else echo "Error: Strawberry is not running or no track playing." >&2; exit 1; fi ;; --cliamp-info) if get_cliamp_track_info 2>/dev/null; then printf "State: %s\nTitle: %s\nArtist: %s\nTime: %s / %s (%s%%)\nPath: %s\n" "$CLIAMP_STATE" "$CLIAMP_TITLE" "$CLIAMP_ARTIST" "$CLIAMP_POS_FMT" "$CLIAMP_DUR_FMT" "$CLIAMP_PROGRESS_PCT" "$CLIAMP_RESOLVED_PATH"; [ -n "$CLIAMP_FILE_SIZE" ] && echo "Size: $CLIAMP_FILE_SIZE"; exit 0; else echo "Error: cliamp is not running or no track playing." >&2; exit 1; fi ;; --help|-h|help) shift; [ -x "$SCRIPT_DIR/scripts/show_help.sh" ] && exec bash "$SCRIPT_DIR/scripts/show_help.sh" "$@"; [ -x "$SCRIPT_DIR/show_help.sh" ] && exec bash "$SCRIPT_DIR/show_help.sh" "$@"; exit 0 ;; --version|-v|version) shift; [ -x "$SCRIPT_DIR/scripts/update_manager.sh" ] && exec bash "$SCRIPT_DIR/scripts/update_manager.sh" --version "$@"; [ -x "$SCRIPT_DIR/update_manager.sh" ] && exec bash "$SCRIPT_DIR/update_manager.sh" --version "$@"; exit 0 ;; update|--update) shift; [ -x "$SCRIPT_DIR/scripts/update_manager.sh" ] && exec bash "$SCRIPT_DIR/scripts/update_manager.sh" "$@"; [ -x "$SCRIPT_DIR/update_manager.sh" ] && exec bash "$SCRIPT_DIR/update_manager.sh" "$@"; exit 0 ;; --top5|--top-5|top5|top-5) shift; [ -x "$SCRIPT_DIR/scripts/manage_top_5_tracks.sh" ] && exec bash "$SCRIPT_DIR/scripts/manage_top_5_tracks.sh" "$@"; [ -f "$SCRIPT_DIR/scripts/top_5_tracks_manager.py" ] && exec python3 "$SCRIPT_DIR/scripts/top_5_tracks_manager.py" "$@"; exit 0 ;; --infinite-talk*|--inftlk*|--infinite-talker*|--stephen-hawking*) shift; run_wan2gp_infinite_talker "$@"; exit 0 ;; esac; CLI_INITIAL_ACTION="${1:-}"; _LAST_STATS_CHECK=0; _CACHED_STATS_CORE=""
invalidate_archive_stats_cache() {
_LAST_STATS_CHECK=0; _CACHED_STATS_CORE=""
}
show_stats() {
local force="${1:-}"; local now="${EPOCHSECONDS:-0}"; [ "$now" -eq 0 ] && now=$(date +%s 2>/dev/null || echo 0); if [ "$force" != "--force" ] && [ "$force" != "-f" ]; then if [ -z "$_CACHED_STATS_CORE" ]; then load_header_cache 2>/dev/null || true; fi; if [ -n "$_CACHED_STATS_CORE" ]; then echo -e "$_CACHED_STATS_CORE"; else _LAST_STATS_CHECK="$now"; _CACHED_STATS_CORE="${BOLD}${BLUE}=== CURRENT STATUS & STATISTICS ===${NC}\n  ${DIM}⚡ Loading archive statistics in background...${NC}"; echo -e "$_CACHED_STATS_CORE"; fi; else _LAST_STATS_CHECK="$now"; local stats_buff=""; stats_buff+="${BOLD}${BLUE}=== CURRENT STATUS & STATISTICS ===${NC}\n"; if ! is_internet_connected; then stats_buff+="  ${DIM}${YELLOW}⚡ Offline Mode: Cloud storage excluded from scan${NC}\n"; fi; local wav_dirs=(); while IFS= read -r wdir; do [ -n "$wdir" ] && [ -d "$wdir" ] && wav_dirs+=("$wdir"); done < <(get_all_wav_archive_dirs); local all_flac_dirs=(); while IFS= read -r fdir; do [ -n "$fdir" ] && [ -d "$fdir" ] && all_flac_dirs+=("$fdir"); done < <(get_all_flac_output_dirs); local all_parent_dirs=(); while IFS= read -r pdir; do [ -n "$pdir" ] && [ -d "$pdir" ] && all_parent_dirs+=("$pdir"); done < <(get_all_mix_archive_dirs); local root_wav_count=0; local root_wav_size_mb=0; local archive_wav_count=0; local archive_wav_size_gb="0.00"; local total_flac_count=0; local missing_tl_count=0; local mp3_count=0; local wav_out_count=0; local mp4_count=0; local w_str f_str p_str stats_out; w_str="$(printf '%s\n' "${wav_dirs[@]}")"; f_str="$(printf '%s\n' "${all_flac_dirs[@]}")"; p_str="$(printf '%s\n' "${all_parent_dirs[@]}")"
stats_out=$(python3 - "$PWD" "$w_str" "$f_str" "$p_str" << 'PY' 2>/dev/null || true
import os, sys
root_dir = sys.argv[1]
wav_dirs = [d for d in sys.argv[2].splitlines() if d and os.path.isdir(d)]
flac_dirs = [d for d in sys.argv[3].splitlines() if d and os.path.isdir(d)]
parent_dirs = [d for d in sys.argv[4].splitlines() if d and os.path.isdir(d)]
root_wav_count = 0
root_wav_size = 0
if os.path.isdir(root_dir):
    try:
        with os.scandir(root_dir) as it:
            for entry in it:
                if entry.name.lower().endswith('.wav') and entry.is_file():
                    root_wav_count += 1
                    root_wav_size += entry.stat().st_size
    except Exception:
        pass
root_wav_size_mb = root_wav_size // (1024 * 1024)
archive_wav_count = 0
archive_wav_size = 0
for d in wav_dirs:
    try:
        with os.scandir(d) as it:
            for entry in it:
                if entry.name.lower().endswith('.wav') and entry.is_file():
                    archive_wav_count += 1
                    archive_wav_size += entry.stat().st_size
    except Exception:
        pass
archive_wav_size_gb = f"{archive_wav_size / (1024**3):.2f}"
total_flac_count = 0
missing_tl_count = 0
for d in flac_dirs:
    try:
        names = set(os.listdir(d))
        flacs = [n for n in names if n.lower().endswith('.flac')]
        total_flac_count += len(flacs)
        for f in flacs:
            stem = f.rsplit('.', 1)[0]
            if f"{stem}.txt" not in names:
                missing_tl_count += 1
    except Exception:
        pass
mp3_count = 0
wav_out_count = 0
mp4_count = 0
for p in parent_dirs:
    for kind, ext in [('MP3_CONVERTED_OUTPUTS', '.mp3'), ('WAV_CONVERTED_OUTPUTS', '.wav'), ('MP4_CONVERTED_OUTPUTS', '.mp4')]:
        sub_d = os.path.join(p, kind)
        if os.path.isdir(sub_d):
            try:
                count = sum(1 for e in os.scandir(sub_d) if e.name.lower().endswith(ext) and e.is_file())
                if ext == '.mp3': mp3_count += count
                elif ext == '.wav': wav_out_count += count
                elif ext == '.mp4': mp4_count += count
            except Exception:
                pass
print(f"{root_wav_count}|{root_wav_size_mb}|{archive_wav_count}|{archive_wav_size_gb}|{total_flac_count}|{missing_tl_count}|{mp3_count}|{wav_out_count}|{mp4_count}")
PY
)
if [ -n "$stats_out" ]; then IFS='|' read -r root_wav_count root_wav_size_mb archive_wav_count archive_wav_size_gb total_flac_count missing_tl_count mp3_count wav_out_count mp4_count <<< "$stats_out"; else shopt -s nullglob nocaseglob; local root_wavs=(./*.wav); root_wav_count=${#root_wavs[@]}; local root_wav_size=0; for w in "${root_wavs[@]}"; do [ -f "$w" ] && root_wav_size=$((root_wav_size + $(stat -c %s "$w" 2>/dev/null || wc -c < "$w"))); done; root_wav_size_mb=$((root_wav_size / 1024 / 1024)); for wdir in "${wav_dirs[@]}"; do local cur_wavs=("$wdir"/*.wav); archive_wav_count=$((archive_wav_count + ${#cur_wavs[@]})); done; for fdir in "${all_flac_dirs[@]}"; do local cur_flacs=("$fdir"/*.flac); total_flac_count=$((total_flac_count + ${#cur_flacs[@]})); done; shopt -u nullglob nocaseglob; fi; local loc_count=${#all_flac_dirs[@]}; local loc_note=""; if [ "$loc_count" -gt 1 ]; then loc_note=" across ${BOLD}${WHITE}${loc_count}${NC}${CYAN} storage archives${NC}"; fi; stats_buff+="  Root Directory WAVs (Pending Conversion):  ${BOLD}${YELLOW}${root_wav_count}${NC} files (${root_wav_size_mb} MB)\n"; stats_buff+="  Archive Directory WAVs (Converted):       ${BOLD}${GREEN}${archive_wav_count}${NC} files (${archive_wav_size_gb} GB)\n"; stats_buff+="  Total FLAC Files Generated:               ${BOLD}${CYAN}${total_flac_count}${NC} files${loc_note}\n"; [ "$mp3_count" -gt 0 ] && stats_buff+="  Total MP3 Files Generated:                ${BOLD}${CYAN}${mp3_count}${NC} files\n"; [ "$wav_out_count" -gt 0 ] && stats_buff+="  Total WAV Converted Outputs:              ${BOLD}${CYAN}${wav_out_count}${NC} files\n"; [ "$mp4_count" -gt 0 ] && stats_buff+="  Total MP4 Videos Generated:               ${BOLD}${CYAN}${mp4_count}${NC} videos\n"; if [ "$missing_tl_count" -gt 0 ]; then stats_buff+="  FLAC Files Missing Tracklists:            ${BOLD}${RED}${missing_tl_count}${NC} files\n"; else stats_buff+="  FLAC Files Missing Tracklists:            ${BOLD}${GREEN}0${NC} files (All complete!)\n"; fi; local cloud_stat; cloud_stat=$(get_cloud_backup_badge 2>/dev/null); [ -n "$cloud_stat" ] && stats_buff+="  ${cloud_stat}\n"; _CACHED_STATS_CORE="$(printf '%b' "$stats_buff")"; save_header_cache 2>/dev/null || true; echo -e "$_CACHED_STATS_CORE"; fi; if [ "$force" = "--force" ] || [ "$force" = "-f" ]; then _CACHED_NOW_PLAYING="$(refresh_now_playing_lines 2>/dev/null || true)"; save_header_cache 2>/dev/null || true; fi; [ -n "${_CACHED_NOW_PLAYING:-}" ] && printf '%s\n' "$_CACHED_NOW_PLAYING"; echo -e "${BLUE}===================================${NC}"
}
refresh_now_playing_lines() {
if get_audacious_track_info 2>/dev/null; then local st_badge; case "$AUDACIOUS_STATE" in playing) st_badge="${BOLD}${GREEN}▶ PLAYING${NC}" ;; paused)  st_badge="${BOLD}${YELLOW}⏸ PAUSED${NC}" ;; stopped) st_badge="${BOLD}${RED}⏹ STOPPED${NC}" ;; *)       st_badge="${BOLD}${CYAN}${AUDACIOUS_STATE^^}${NC}" ;; esac; echo -e "  --------------------------------------------------\n  Audacious Audio Player:                   ${st_badge} [${AUDACIOUS_POS_FMT} / ${AUDACIOUS_DUR_FMT}] (${AUDACIOUS_PROGRESS_PCT}%)\n  Audacious Current Track:                  ${BOLD}${YELLOW}${AUDACIOUS_TITLE}${NC}${AUDACIOUS_ARTIST:+ - $AUDACIOUS_ARTIST}"; [ -n "$AUDACIOUS_RESOLVED_PATH" ] && echo -e "  Audacious Active File Path:               ${BOLD}${CYAN}${AUDACIOUS_RESOLVED_PATH}${NC}"; if [ -n "$AUDACIOUS_RESOLVED_PATH" ] && [ -f "$AUDACIOUS_RESOLVED_PATH" ]; then local audio_spec; audio_spec=$(get_playing_audio_spec_summary "$AUDACIOUS_RESOLVED_PATH"); [ -n "$audio_spec" ] && echo -e "  Audio Specifications:                     ${BOLD}${GREEN}${audio_spec}${NC}"; fi; elif get_strawberry_track_info 2>/dev/null; then local st_badge; case "$STRAWBERRY_STATE" in playing) st_badge="${BOLD}${GREEN}▶ PLAYING${NC}" ;; paused)  st_badge="${BOLD}${YELLOW}⏸ PAUSED${NC}" ;; stopped) st_badge="${BOLD}${RED}⏹ STOPPED${NC}" ;; *)       st_badge="${BOLD}${CYAN}${STRAWBERRY_STATE^^}${NC}" ;; esac; echo -e "  --------------------------------------------------\n  Strawberry Music Player:                  ${st_badge} [${STRAWBERRY_POS_FMT} / ${STRAWBERRY_DUR_FMT}] (${STRAWBERRY_PROGRESS_PCT}%)\n  Strawberry Current Track:                 ${BOLD}${YELLOW}${STRAWBERRY_TITLE}${NC}${STRAWBERRY_ARTIST:+ - $STRAWBERRY_ARTIST}"; [ -n "$STRAWBERRY_RESOLVED_PATH" ] && echo -e "  Strawberry Active File Path:              ${BOLD}${CYAN}${STRAWBERRY_RESOLVED_PATH}${NC}"; if [ -n "$STRAWBERRY_RESOLVED_PATH" ] && [ -f "$STRAWBERRY_RESOLVED_PATH" ]; then local audio_spec; audio_spec=$(get_playing_audio_spec_summary "$STRAWBERRY_RESOLVED_PATH"); [ -n "$audio_spec" ] && echo -e "  Audio Specifications:                     ${BOLD}${GREEN}${audio_spec}${NC}"; fi; elif get_cliamp_track_info 2>/dev/null; then local st_badge; case "$CLIAMP_STATE" in playing) st_badge="${BOLD}${GREEN}▶ PLAYING${NC}" ;; paused)  st_badge="${BOLD}${YELLOW}⏸ PAUSED${NC}" ;; stopped) st_badge="${BOLD}${RED}⏹ STOPPED${NC}" ;; *)       st_badge="${BOLD}${CYAN}${CLIAMP_STATE}${NC}" ;; esac; echo -e "  --------------------------------------------------\n  Cliamp Music Player:                      ${st_badge} [${CLIAMP_POS_FMT} / ${CLIAMP_DUR_FMT}] (${CLIAMP_PROGRESS_PCT}%)\n  Cliamp Current Track:                     ${BOLD}${YELLOW}${CLIAMP_TITLE}${NC} - ${CLIAMP_ARTIST}\n  Cliamp Active File Path:                  ${BOLD}${CYAN}${CLIAMP_RESOLVED_PATH}${NC}"; if [ -n "$CLIAMP_RESOLVED_PATH" ] && [ -f "$CLIAMP_RESOLVED_PATH" ]; then local audio_spec; audio_spec=$(get_playing_audio_spec_summary "$CLIAMP_RESOLVED_PATH"); [ -n "$audio_spec" ] && echo -e "  Audio Specifications:                     ${BOLD}${GREEN}${audio_spec}${NC}"; fi; else local other_mix; other_mix=$(detect_currently_playing_mix 2>/dev/null); if [ -n "$other_mix" ] && [ -f "$other_mix" ]; then local audio_spec; audio_spec=$(get_playing_audio_spec_summary "$other_mix"); echo -e "  --------------------------------------------------"; echo -e "  Active Playing Mix:                       ${BOLD}${GREEN}$(basename "$other_mix")${NC}"; [ -n "$audio_spec" ] && echo -e "  Audio Specifications:                     ${BOLD}${GREEN}${audio_spec}${NC}"; fi; fi
}
press_enter() {
echo ""
local prompt_msg="${1:-Press [Enter] to return to the main menu...}"
printf '%s' "$prompt_msg"
while true; do
    local key=""
    IFS= read -rsn1 key 2>/dev/null || { local _rc=$?; if (( _rc > 128 )); then continue; fi; read -r _discard 2>/dev/null || true; break; }
    case "$key" in
        "") echo ""; break ;;
        " ")
            toggle_mp_audio_player
            printf '\r\033[K%s \033[1;32m[♫ Playback Toggled]\033[0m' "$prompt_msg"
            ;;
        m|M)
            launch_mp_audio_player_window
            printf '\r\033[K%s \033[1;36m[♫ Mini Player Launched]\033[0m' "$prompt_msg"
            ;;
        l|L)
            launch_mp_audio_player_liquid_glass >/dev/null 2>&1
            printf '\r\033[K%s \033[1;36m[♫ Liquid Glass Player Launched]\033[0m' "$prompt_msg"
            ;;
        K)
            pkill -9 -f "MP_Audio_Player" 2>/dev/null || true
            rm -f "${HOME}/.config/mix-manager/mp_player.pid" "${HOME}/.config/mix-manager/mp_audio_player.port" "${HOME}/.config/mix-manager/mp_audio_player.sock" 2>/dev/null || true
            _CACHED_PLAYER_CHECK_TIME=0
            _CACHED_PLAYER_ACTIVE_RES=1
            MP_PLAYER_RUNNING=0
            MP_PLAYER_STATE="stopped"
            printf '\r\033[K%s \033[1;31m[♫ MP Audio Player Terminated (Shift+K)]\033[0m' "$prompt_msg"
            ;;
        $'\e') local rest=""; read -rsn2 -t 0.05 rest 2>/dev/null || true; echo ""; break ;;
        q|Q) echo ""; break ;;
        *) echo ""; break ;;
    esac
done
}
rename_mix() {
echo -e "\n${BOLD}${BLUE}=== RENAME MIX FILE & ASSOCIATED ASSETS ===${NC}"; read -r -p "Enter current FLAC filename (or search keyword): " src_flac; src_flac_name=$(basename "$src_flac" | tr -d '\r' | tr -d '\n'); local src_path=""; local found_dir=""; if [ -f "$src_flac" ]; then src_path="$src_flac"; found_dir="$(dirname "$src_path")"; src_flac_name="$(basename "$src_path")"; else while IFS= read -r fdir; do if [ -n "$fdir" ] && [ -f "$fdir/$src_flac_name" ]; then src_path="$fdir/$src_flac_name"; found_dir="$fdir"; break; fi; done < <(get_all_flac_output_dirs); fi; if [ -z "$src_path" ]; then local candidates=(); while IFS= read -r fdir; do if [ -d "$fdir" ]; then shopt -s nullglob nocaseglob; for mf in "$fdir"/*"$src_flac"*.flac; do [ -f "$mf" ] && candidates+=("$mf"); done; shopt -u nullglob nocaseglob; fi; done < <(get_all_flac_output_dirs); if [ ${#candidates[@]} -eq 1 ]; then src_path="${candidates[0]}"; found_dir="$(dirname "$src_path")"; src_flac_name="$(basename "$src_path")"; elif [ ${#candidates[@]} -gt 1 ]; then echo -e "\nMultiple matching FLAC files found:"; for i in "${!candidates[@]}"; do echo "  $((i+1))) [$(basename "$(dirname "${candidates[$i]}")")] $(basename "${candidates[$i]}")"; done; read -r -p "Select mix to rename [1-${#candidates[@]}]: " pick; if [[ "$pick" =~ ^[0-9]+$ ]] && [ "$pick" -ge 1 ] && [ "$pick" -le "${#candidates[@]}" ]; then src_path="${candidates[$((pick-1))]}"; found_dir="$(dirname "$src_path")"; src_flac_name="$(basename "$src_path")"; else echo -e "${RED}Invalid selection.${NC}"; return; fi; fi; fi; if [ -z "$src_path" ] || [ ! -f "$src_path" ]; then echo -e "${RED}Error: File '$src_flac' not found across any configured archive directories!${NC}"; return; fi; echo -e "\n${CYAN}Located Mix in:${NC} ${found_dir}\nCurrent file: ${WHITE}$src_flac_name${NC}"; read -r -p "Enter destination filename for final FLAC: " dest_flac; dest_flac_name=$(basename "$dest_flac" | tr -d '\r' | tr -d '\n'); [[ "$dest_flac_name" != *.flac ]] && dest_flac_name="${dest_flac_name}.flac"; dest_path="${found_dir}/${dest_flac_name}"; if [ -f "$dest_path" ]; then echo -e "${RED}Error: Destination file '$dest_path' already exists!${NC}"; return; fi; mv "$src_path" "$dest_path"; echo -e "${GREEN}✓ Renamed FLAC: $src_flac_name ➔ $dest_flac_name${NC}"; src_base="${src_flac_name%.*}"; dest_base="${dest_flac_name%.*}"; src_txt="${found_dir}/${src_base}.txt"; dest_txt="${found_dir}/${dest_base}.txt"; if [ -f "$src_txt" ]; then mv "$src_txt" "$dest_txt"; echo -e "${GREEN}✓ Renamed Tracklist: $(basename "$src_txt") ➔ $(basename "$dest_txt")${NC}"; fi; local spek_dirs=("SPEK_OUTPUTS" "${found_dir}/SPEK_OUTPUTS" "$(dirname "$found_dir")/SPEK_OUTPUTS"); for s_dir in "${spek_dirs[@]}"; do if [ -f "$s_dir/${src_base}_spectrogram.png" ]; then mv "$s_dir/${src_base}_spectrogram.png" "$s_dir/${dest_base}_spectrogram.png"; echo -e "${GREEN}✓ Renamed Spectrogram in $s_dir: ${src_base}_spectrogram.png ➔ ${dest_base}_spectrogram.png${NC}"; fi; done
}
view_tasks() {
echo -e "\n${BOLD}${BLUE}=== RUNNING BACKGROUND TASKS ===${NC}"; local tasks_found=0; if pgrep -f "Make_SOF_FLAC_CONVERSION.sh" > /dev/null || pgrep -x "ffmpeg" > /dev/null; then echo -e "  [${YELLOW}RUNNING${NC}] FLAC Conversion Batch Job (Make_SOF_FLAC_CONVERSION.sh / ffmpeg)"; ((tasks_found++)); fi; if pgrep -f "Check_Find_Tracklists.sh" > /dev/null; then echo -e "  [${YELLOW}RUNNING${NC}] Tracklist Generator Job (Check_Find_Tracklists.sh)"; ((tasks_found++)); fi; if pgrep -f "Verify_FLAC_Files.sh" > /dev/null; then echo -e "  [${YELLOW}RUNNING${NC}] FLAC Verification Scan (Verify_FLAC_Files.sh)"; ((tasks_found++)); fi; if pgrep -f "backup_to_gdrive.sh" > /dev/null || pgrep -f "backup_mix_archive.sh" > /dev/null || pgrep -x "rclone" > /dev/null; then echo -e "  [${YELLOW}RUNNING${NC}] Cloud Backup / Active Transfer (backup_mix_archive.sh / rclone)"; ((tasks_found++)); fi; if pgrep -f "import_new_mixes.sh" > /dev/null; then echo -e "  [${YELLOW}RUNNING${NC}] SMB Import Process (import_new_mixes.sh)"; ((tasks_found++)); fi; if pgrep -f "SOF_Live_Tracker.sh" > /dev/null; then echo -e "  [${YELLOW}RUNNING${NC}] Live Tracklist Monitor (SOF_Live_Tracker.sh)"; ((tasks_found++)); fi; local chrome_upload_info=""; if command -v chrome-upload-monitor &>/dev/null; then chrome_upload_info=$(chrome-upload-monitor --check 2>/dev/null || true); elif [ -x "$HOME/.local/bin/chrome-upload-monitor" ]; then chrome_upload_info=$("$HOME/.local/bin/chrome-upload-monitor" --check 2>/dev/null || true); elif [ -x "./chrome_upload_monitor.py" ]; then chrome_upload_info=$(python3 ./chrome_upload_monitor.py --check 2>/dev/null || true); fi; if [ -n "$chrome_upload_info" ]; then echo -e "  [${YELLOW}RUNNING${NC}] Chrome Podcast Connect / Web Upload: ${CYAN}${chrome_upload_info}${NC}"; ((tasks_found++)); fi; if pgrep -f "python.*wgp\.py" > /dev/null; then local wgp_pids; wgp_pids=$(pgrep -f "python.*wgp\.py" | tr '\n' ' '); echo -e "  [${GREEN}RUNNING${NC}] WAN2GP AI Video Server (PID: ${wgp_pids})"; ((tasks_found++)); fi; if pgrep -f "wan2gp_flux_batch" > /dev/null; then local flux_pids; flux_pids=$(pgrep -f "wan2gp_flux_batch" | tr '\n' ' '); echo -e "  [${GREEN}RUNNING${NC}] WAN2GP Flux 2 Klein Batch Processor (PID: ${flux_pids})"; ((tasks_found++)); fi; if pgrep -f "wan2gp_ltx.*batch" > /dev/null; then local ltx_pids; ltx_pids=$(pgrep -f "wan2gp_ltx.*batch" | tr '\n' ' '); echo -e "  [${GREEN}RUNNING${NC}] WAN2GP LTX Video Batch Processor (PID: ${ltx_pids})"; ((tasks_found++)); fi; if pgrep -f "remove_duplicate_images\.py" > /dev/null; then local dup_pids; dup_pids=$(pgrep -f "remove_duplicate_images\.py" | tr '\n' ' '); echo -e "  [${GREEN}RUNNING${NC}] Duplicate Image Remover (PID: ${dup_pids})"; ((tasks_found++)); fi; if pgrep -f "traktor_monitor" > /dev/null; then local tm_pids
tm_pids=$(pgrep -f "traktor_monitor" | tr '\n' ' '); echo -e "  [${GREEN}RUNNING${NC}] Traktor Live Monitor & Audio Recorder (PID: ${tm_pids})"; ((tasks_found++)); fi; if pgrep -x "Traktor" > /dev/null || pgrep -x "Traktor.exe" > /dev/null || pgrep -f "Traktor Pro" > /dev/null; then local tp_pids; tp_pids=$(pgrep -x "Traktor" 2>/dev/null || pgrep -x "Traktor.exe" 2>/dev/null || pgrep -f "Traktor Pro" 2>/dev/null | tr '\n' ' '); echo -e "  [${GREEN}RUNNING${NC}] Native Instruments Traktor Pro DJ (PID: ${tp_pids})"; ((tasks_found++)); fi; if systemctl is-active --quiet sshd || pgrep -x sshd > /dev/null; then local ssh_pids; ssh_pids=$(pgrep -x sshd | tr '\n' ' '); echo -e "  [${GREEN}RUNNING${NC}] SSH Server (sshd - Port 22, PID: ${ssh_pids})"; ((tasks_found++)); fi; if systemctl is-active --quiet smb || pgrep -x smbd > /dev/null; then local smb_pids; smb_pids=$(pgrep -x smbd | tr '\n' ' '); echo -e "  [${GREEN}RUNNING${NC}] Samba File Sharing (smbd, nmbd, wsdd - Ports 139, 445, PID: ${smb_pids})"; ((tasks_found++)); fi; if systemctl is-active --quiet vsftpd || pgrep -x vsftpd > /dev/null; then local ftp_pids; ftp_pids=$(pgrep -x vsftpd | tr '\n' ' '); echo -e "  [${GREEN}RUNNING${NC}] FTP Server (vsftpd - Port 21, PID: ${ftp_pids})"; ((tasks_found++)); fi; if pgrep -f "ujust" > /dev/null || pgrep -f "rpm-ostree" > /dev/null; then echo -e "  [${YELLOW}RUNNING${NC}] System Maintenance / Update (ujust / rpm-ostree)"; ((tasks_found++)); fi; if pgrep -i -f "audacious" > /dev/null; then local aud_pids aud_desc=""; aud_pids=$(pgrep -i -f audacious | tr '\n' ' '); if get_audacious_track_info 2>/dev/null; then aud_desc=" [${AUDACIOUS_STATE^^}: ${AUDACIOUS_TITLE} - ${AUDACIOUS_POS_FMT}/${AUDACIOUS_DUR_FMT}]"; fi; echo -e "  [${GREEN}RUNNING${NC}] Audacious Audio Player (PID: ${aud_pids})${aud_desc}"; ((tasks_found++)); fi; if pgrep -i -f "strawberry" > /dev/null; then local straw_pids straw_desc=""; straw_pids=$(pgrep -i -f strawberry | tr '\n' ' '); if get_strawberry_track_info 2>/dev/null; then straw_desc=" [${STRAWBERRY_STATE^^}: ${STRAWBERRY_TITLE} - ${STRAWBERRY_POS_FMT}/${STRAWBERRY_DUR_FMT}]"; fi; echo -e "  [${GREEN}RUNNING${NC}] Strawberry Music Player (PID: ${straw_pids})${straw_desc}"; ((tasks_found++)); fi; if pgrep -x "cliamp" > /dev/null; then local cliamp_pids cliamp_desc=""; cliamp_pids=$(pgrep -x cliamp | tr '\n' ' '); if get_cliamp_track_info 2>/dev/null; then cliamp_desc=" [${CLIAMP_STATE^^}: ${CLIAMP_TITLE} - ${CLIAMP_POS_FMT}/${CLIAMP_DUR_FMT}]"; fi; echo -e "  [${GREEN}RUNNING${NC}] cliamp Retro Music Player (PID: ${cliamp_pids})${cliamp_desc}"; ((tasks_found++)); fi; local dsh_running=false dsh_pids=""; if [ "$OS_TYPE" = "windows" ] && command -v netstat.exe &>/dev/null; then if netstat.exe -ano 2>/dev/null | grep -E ":3080\s+.*LISTENING" &>/dev/null; then dsh_running=true; dsh_pids=$(netstat.exe -ano 2>/dev/null | grep -E ":3080\s+.*LISTENING" | sed -e 's/.*LISTENING *//' | tr -d '\r' | sort -u | tr '\n' ' ')
fi; fi; if [ "$dsh_running" = "false" ] && command -v curl &>/dev/null; then local code; code=$(curl -s -m 1 -o /dev/null -w "%{http_code}" "http://192.168.1.11:3080/" 2>/dev/null || true); if [ "$code" != "000" ] && [ -n "$code" ]; then dsh_running=true; fi; fi; if [ "$dsh_running" = "false" ]; then if ss -tuln 2>/dev/null | grep -q ":3080 " || { command -v pgrep &>/dev/null && pgrep -f "dsh.*web|apps/cli/src/bin\.ts.*web" &>/dev/null; }; then dsh_running=true; dsh_pids=$(lsof -ti:3080 2>/dev/null || pgrep -f "dsh.*web|apps/cli/src/bin\.ts.*web" 2>/dev/null | tr '\n' ' '); fi; fi; if [ "$dsh_running" = "true" ]; then local pid_str=""; [ -n "$dsh_pids" ] && pid_str=", PID: ${dsh_pids% }"; echo -e "  [${GREEN}RUNNING${NC}] DeepSeek Harness (dsh-mobile - http://192.168.1.11:3080${pid_str})"; ((tasks_found++)); fi; local bsz_running=false; local bsz_has_agent=false; if command -v netstat.exe &>/dev/null; then if netstat.exe -ano 2>/dev/null | grep -E ":8090\s+.*LISTENING" &>/dev/null; then bsz_running=true; fi; if netstat.exe -ano 2>/dev/null | grep -E ":45876\s+.*LISTENING" &>/dev/null; then bsz_has_agent=true; fi; elif command -v curl &>/dev/null; then if curl -s -m 1 -o /dev/null "http://localhost:8090/" 2>/dev/null; then bsz_running=true; fi; fi; if [ "$bsz_running" = false ] && command -v tasklist.exe &>/dev/null; then if tasklist.exe //FI "IMAGENAME eq beszel.exe" 2>/dev/null | grep -qi "beszel.exe"; then bsz_running=true; fi; if tasklist.exe //FI "IMAGENAME eq beszel-agent.exe" 2>/dev/null | grep -qi "beszel-agent.exe"; then bsz_has_agent=true; fi; fi; if [ "$bsz_running" = false ] && command -v podman &>/dev/null; then if podman ps --filter "name=beszel" --format "{{.Names}}" 2>/dev/null | grep -q "^beszel$"; then bsz_running=true; if podman ps --filter "name=beszel-agent" --format "{{.Names}}" 2>/dev/null | grep -q "^beszel-agent$"; then bsz_has_agent=true; fi; fi; fi; if [ "$bsz_running" = true ]; then local bsz_status="Hub :8090"; [ "$bsz_has_agent" = true ] && bsz_status="Hub :8090 + Agent"; echo -e "  [${GREEN}RUNNING${NC}] Beszel Server Monitoring (${bsz_status})"; ((tasks_found++)); fi; local olm_running=false olm_pids=""; if curl -s --connect-timeout 1 "http://127.0.0.1:11434/" 2>/dev/null | grep -qi "Ollama is running"; then olm_running=true; fi; if [ "$OS_TYPE" = "windows" ]; then if command -v netstat.exe &>/dev/null; then olm_pids=$(netstat.exe -ano 2>/dev/null | grep -E ":11434\s+.*LISTENING" | awk '{print $5}' | sort -u | tr '\n' ' ')
[ -n "$olm_pids" ] && olm_running=true; fi; if [ "$olm_running" = "false" ] && command -v tasklist.exe &>/dev/null; then if tasklist.exe //FI "IMAGENAME eq ollama.exe" 2>/dev/null | grep -qi "ollama.exe"; then olm_running=true; olm_pids=$(tasklist.exe //FI "IMAGENAME eq ollama.exe" //FO CSV //NH 2>/dev/null | awk -F'","' '{print $2}' | tr -d '"\r ' | tr '\n' ' '); fi; fi; else if pgrep -f "ollama serve" &>/dev/null; then olm_running=true; olm_pids=$(pgrep -f "ollama serve" 2>/dev/null | tr '\n' ' '); fi; fi; if [ "$olm_running" = "true" ]; then local olm_pid_str=""; [ -n "$olm_pids" ] && olm_pid_str=", PID: ${olm_pids% }"; echo -e "  [${GREEN}RUNNING${NC}] Ollama Local AI Server (http://127.0.0.1:11434${olm_pid_str})"; ((tasks_found++)); fi; local webui_running=false webui_pids="" webui_port=8080; for p in 8080 42004; do if curl -s -I --connect-timeout 0.75 "http://127.0.0.1:${p}/" 2>/dev/null | grep -qi "HTTP/" || curl -s -I --connect-timeout 0.75 "http://localhost:${p}/" 2>/dev/null | grep -qi "HTTP/"; then webui_running=true; webui_port=$p; break; fi; done; if [ "$OS_TYPE" = "windows" ]; then if command -v netstat.exe &>/dev/null; then local n_pids; n_pids=$(netstat.exe -ano 2>/dev/null | tr -d '\r' | awk -v port=":${webui_port}" '$2 ~ port && $4 == "LISTENING" {print $5}' | sort -u | tr '\n' ' '); if [ -n "$n_pids" ]; then webui_pids="$n_pids"; webui_running=true; fi; fi; if [ "$webui_running" = "false" ] && command -v tasklist.exe &>/dev/null; then if tasklist.exe //FI "WINDOWTITLE eq Open WebUI*" 2>/dev/null | grep -qi "cmd.exe\|python.exe"; then webui_running=true; fi; fi; else if systemctl --user is-active --quiet "open-webui.service" 2>/dev/null || pgrep -f "open-webui" &>/dev/null; then webui_running=true; webui_pids=$(pgrep -f "open-webui" 2>/dev/null | tr '\n' ' '); fi; fi; if [ "$webui_running" = "true" ]; then local webui_pid_str=""; [ -n "$webui_pids" ] && webui_pid_str=", PID: ${webui_pids% }"; echo -e "  [${GREEN}RUNNING${NC}] Open WebUI Server (http://localhost:${webui_port}${webui_pid_str})"; ((tasks_found++)); fi; if [ $tasks_found -eq 0 ]; then echo -e "  ${GREEN}No active background tasks found.${NC}"; fi; echo -e "${BLUE}================================${NC}"
}
view_cover() {
echo -e "\n${BOLD}${BLUE}=== VIEW COVER ART BY MIX NUMBER ===${NC}"; read -r -p "Enter the mix/episode number (e.g. 037, 063): " mix_num; if [ -z "$mix_num" ]; then echo -e "${RED}Error: Mix number cannot be empty.${NC}"; return; fi; shopt -s nullglob nocaseglob; local matches=(COVERS/*"${mix_num}"*.png COVERS/*"${mix_num}"*.jpg COVERS/*"${mix_num}"*.jpeg); if [ ${#matches[@]} -eq 0 ]; then echo -e "${YELLOW}No matching cover art found in COVERS/ for mix number '${mix_num}'.${NC}"; return; fi; echo -e "${GREEN}Found match(es):${NC}"; local i=1; for m in "${matches[@]}"; do echo "  $i) $(basename "$m")"; ((i++)); done; local choice=1; if [ ${#matches[@]} -gt 1 ]; then read -r -p "Select which file to view [1-$((i-1))]: " choice; fi; local target_index=$((choice - 1)); local selected_cover="${matches[$target_index]}"; if [ -f "$selected_cover" ]; then echo -e "${CYAN}Launching external image viewer for $(basename "$selected_cover")...${NC}"; open_path "$selected_cover"; else echo -e "${RED}Error: Selected file does not exist.${NC}"; fi
}
generate_youtube_video() {
clear
echo -e "
${BOLD}${MAGENTA}======================================================================${NC}"
echo -e "${BOLD}${MAGENTA}       YOUTUBE VIDEO GENERATION SUITE (4K UHD / 1080p / 720p)         ${NC}"
echo -e "${BOLD}${MAGENTA}======================================================================${NC}
"
echo -e "  Encodes video with hardware acceleration (NVENC / VideoToolbox / libx264)"
echo -e "  and studio-grade 320kbps AAC audio with smooth 5-second audio fading.
"
echo -e "  ${BOLD}Select Video Generation Option:${NC}\n  ${BOLD}${CYAN}1)${NC} 4K UHD (3840x2160 @ 30fps) - ${GREEN}Ultra High Definition (Still Cover Art + Audio)${NC}\n  ${BOLD}${CYAN}2)${NC} 1080p Full HD (1920x1080 @ 30fps) - ${GREEN}Standard High Definition (Still Cover Art + Audio)${NC}\n  ${BOLD}${CYAN}3)${NC} 720p HD (1280x720 @ 30fps) - ${YELLOW}Fast Export & Compact File Size (Still Cover Art + Audio)${NC}\n  ${BOLD}${CYAN}4)${NC} Looping MP4-to-MP4 Video Creator (${GREEN}Loop MP4 with Segment Fades, Audio & Thumbnails${NC})\n  ${BOLD}${CYAN}5)${NC} Launch Universal Video Generator Wizard (${GREEN}generate_youtube_video.sh${NC})\n  ${BOLD}${CYAN}6)${NC} Download YouTube Videos & Shorts in 1080p (${GREEN}Single URL, 1/3/6 Mo, All Videos/Shorts - MP_YouTube_Channel_Downloader.sh${NC})\n  ${BOLD}${CYAN}7)${NC} Generate YouTube Shorts Promo Video (${GREEN}1080x1920 Vertical 42s Dreamworlds Promo - generate_youtube_short_promo.py${NC})"
echo -e "  ${BOLD}${CYAN}8)${NC} Cancel & Return to Main Menu
"
read -r -p "Enter choice [1-8, default: 2]: " v_choice; local res="1080p"; case "$v_choice" in 1) res="4k" ;; 2) res="1080p" ;; 3) res="720p" ;; 4) echo -e "\n${BOLD}${CYAN}--- MP4 to MP4 Looping Video Creator ---${NC}\n"; read -r -p "Enter Audio file path (.wav / .flac): " mp4_audio; read -r -p "Enter Input Video file path (.mp4 / .mkv): " mp4_video; read -r -p "Enter Intro/Outro Thumbnail image (optional, leave blank for auto): " mp4_thumb; read -r -p "Enter Output directory or target file path (default: $MP4_OUTPUT_DIR): " mp4_out; [ -z "$mp4_out" ] && mp4_out="$MP4_OUTPUT_DIR"; run_sub_script "Make_SOF_Episode_From_MP4_Audio_Output_MP4_1080p_Video.sh" "$mp4_audio" "$mp4_video" "$mp4_thumb" "$mp4_out" "1080p"; press_enter; return 0; ;; 5) run_sub_script "generate_youtube_video.sh"; press_enter; return 0 ;; 6) run_sub_script "MP_YouTube_Channel_Downloader.sh"; press_enter; return 0; ;; 7|short|shorts) echo -e "\n${BOLD}${CYAN}--- YouTube Shorts Promo Video Generator (1080x1920) ---${NC}\n"; python3 "$SCRIPT_DIR/scripts/generate_youtube_short_promo.py"; press_enter; return 0; ;; 8|[qQ]) return 0 ;; *) res="1080p"; ;; esac; local flac_list=(); local search_dirs=(); [ -d "$OUTPUT_DIR" ] && search_dirs+=("$OUTPUT_DIR"); [ -d "$WAV_OUTPUT_DIR" ] && search_dirs+=("$WAV_OUTPUT_DIR"); [ -d "$ARCHIVE_DIR" ] && search_dirs+=("$ARCHIVE_DIR"); [ -n "${MIX_ARCHIVE_DIR:-}" ] && [ -d "$MIX_ARCHIVE_DIR/FLAC_CONVERTED_OUTPUTS" ] && search_dirs+=("$MIX_ARCHIVE_DIR/FLAC_CONVERTED_OUTPUTS"); [ -n "${MIX_ARCHIVE_DIR:-}" ] && [ -d "$MIX_ARCHIVE_DIR/WAV_CONVERTED_OUTPUTS" ] && search_dirs+=("$MIX_ARCHIVE_DIR/WAV_CONVERTED_OUTPUTS"); [ -n "${MIX_ARCHIVE_DIR:-}" ] && [ -d "$MIX_ARCHIVE_DIR/CONVERTED_WAV_FILES" ] && search_dirs+=("$MIX_ARCHIVE_DIR/CONVERTED_WAV_FILES"); [ -d "$SCRIPT_DIR/FLAC_CONVERTED_OUTPUTS" ] && search_dirs+=("$SCRIPT_DIR/FLAC_CONVERTED_OUTPUTS"); search_dirs+=("$PWD"); local patterns=(); for sdir in "${search_dirs[@]}"; do patterns+=("$sdir"/*.flac "$sdir"/*.wav); done; local seen_stems="|"; local f; while IFS= read -r f; do if [ -n "$f" ] && [ -f "$f" ]; then local bname stem stem_lower preferred_f; bname=$(basename "$f"); stem="${bname%.*}"; stem_lower=$(echo "$stem" | tr '[:upper:]' '[:lower:]'); if [[ "$seen_stems" != *"|$stem_lower|"* ]]; then seen_stems="${seen_stems}${stem_lower}|"
preferred_f="$f"; if [[ "$f" == *.wav ]] || [[ "$f" == *.WAV ]]; then local flac_companion="${f%.*}.flac"; [ -f "$flac_companion" ] && preferred_f="$flac_companion"; fi; flac_list+=("$preferred_f"); fi; fi; done < <(ls -td "${patterns[@]}" 2>/dev/null); local flac_input=""; if [ ${#flac_list[@]} -gt 0 ]; then echo -e "\n${BOLD}${CYAN}Available Mixes in Archive (Showing Latest 10 Mixes):${NC}"; local limit=10; [ ${#flac_list[@]} -lt $limit ] && limit=${#flac_list[@]}; for ((i=0; i<limit; i++)); do printf "  %2d) %s\n" "$((i + 1))" "$(basename "${flac_list[$i]}")"; done; echo ""; read -r -p "Select mix number [1-${limit}] or enter custom filename: " chosen_mix; if [[ "$chosen_mix" =~ ^[0-9]+$ ]] && [ "$chosen_mix" -ge 1 ] && [ "$chosen_mix" -le "$limit" ]; then flac_input="${flac_list[$((chosen_mix - 1))]}"; elif [ -n "$chosen_mix" ]; then flac_input="$chosen_mix"; fi; fi; if [ -z "$flac_input" ]; then read -r -p "Enter filename/path of the audio file (.flac / .wav): " flac_input; fi; flac_input=$(echo "$flac_input" | sed -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'$//"); [ -z "$flac_input" ] && { echo -e "${RED}Error: Audio file is required.${NC}"; return; }; read -r -p "Enter Cover PNG path (leave blank for auto-detect / Cover.png): " cover_input; cover_input=$(echo "$cover_input" | sed -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'$//"); case "$res" in 4k) run_sub_script "Make_SOF_Episode_From_PNG_FLAC_Output_MP4_4K_Video.sh" "$flac_input" "$cover_input" "$MP4_OUTPUT_DIR" ;; 720p) run_sub_script "Make_SOF_Episode_From_PNG_FLAC_Output_MP4_720p_Video.sh" "$flac_input" "$cover_input" "$MP4_OUTPUT_DIR"; ;; *) run_sub_script "Make_SOF_Episode_From_PNG_FLAC_Output_MP4_1080p_Video.sh" "$flac_input" "$cover_input" "$MP4_OUTPUT_DIR" ;; esac
}
cut_video_clip() {
echo -e "\n${BOLD}${BLUE}=== CUT VIDEO FILE (.MP4 / .MKV) ===${NC}\n"; run_sub_script "Cut_Video.sh" "$@"
}
split_flac_audio() {
echo -e "\n${BOLD}${BLUE}=== SPLIT FLAC AUDIO FILE ===${NC}\n"; run_sub_script "Split_FLAC_File.sh" "$@"
}
split_video_clip() {
echo -e "\n${BOLD}${BLUE}=== SPLIT VIDEO FILE (.MP4) ===${NC}\n"; run_sub_script "Split_Video_File.sh" "$@"
}
manage_video_cut_and_split() {
while true; do clear; echo -e "${BOLD}${MAGENTA}${S70}${NC}\n${BOLD}${MAGENTA}                   VIDEO CUTTING & SPLITTING SUITE                    ${NC}\n${BOLD}${MAGENTA}${S70}${NC}\n\n  ${BOLD}${CYAN}1)${NC} Cut / Trim Video File by Start & End Time (${GREEN}Cut_Video.sh${NC})\n  ${BOLD}${CYAN}2)${NC} Split Video File (.mp4) into Equal Parts (${GREEN}Split_Video_File.sh${NC})\n  ${BOLD}${CYAN}3)${NC} Return to Main Menu\n"; read -r -p "Enter choice [1-3]: " v_choice; case "$v_choice" in 1) run_sub_script "Cut_Video.sh"; press_enter; ;; 2) run_sub_script "Split_Video_File.sh"; press_enter; ;; 3|[qQ]) return 0 ;; *) echo -e "\n${RED}Invalid option!${NC}"; sleep 1.2 ;; esac; done
}
launch_cliamp() {
echo -e "\n${BOLD}${YELLOW}Launching cliamp Music Player in a new window...${NC}\n"; local cliamp_bin
if command -v cliamp &>/dev/null; then cliamp_bin="cliamp"; elif [ -x "$SCRIPT_DIR/bin/cliamp" ]; then cliamp_bin="$SCRIPT_DIR/bin/cliamp"; elif [ -x "$HOME/.local/bin/cliamp" ]; then cliamp_bin="$HOME/.local/bin/cliamp"; else echo -e "${RED}Error: cliamp command not found in PATH or bin!${NC}"; press_enter; return 1; fi; if launch_in_terminal "cliamp" "$cliamp_bin" "window"; then echo -e "${GREEN}✓ cliamp launched in a new window.${NC}"; sleep 1.2; else echo -e "${RED}Error: No supported terminal emulator found to launch in a new window.${NC}"; press_enter; return 1; fi
}
monitor_cliamp_live() {
echo -e "\n${BOLD}${YELLOW}Starting Real-Time cliamp Monitor (Press 'q' or Ctrl+C to exit)...${NC}\n"; sleep 0.5; trap 'break' INT; while true; do if ! get_cliamp_track_info 2>/dev/null; then clear; echo -e "${BOLD}${MAGENTA}=== CLIAMP LIVE TRACKLIST MONITOR ===${NC}\n\n${YELLOW}cliamp is currently idle or no active track is playing.${NC}\n${DIM}Waiting for playback... (Press 'q' to quit)${NC}"; read -r -t 1 -n 1 key 2>/dev/null || true; if [[ "$key" == "q" || "$key" == "Q" ]]; then break; fi; continue; fi; clear; echo -e "${BOLD}${MAGENTA}==================================================${NC}\n${BOLD}${MAGENTA}           CLIAMP LIVE REAL-TIME MONITOR          ${NC}\n${BOLD}${MAGENTA}==================================================${NC}\n"; local st_badge; case "$CLIAMP_STATE" in playing) st_badge="${BOLD}${GREEN}▶ PLAYING${NC}" ;; paused)  st_badge="${BOLD}${YELLOW}⏸ PAUSED${NC}" ;; stopped) st_badge="${BOLD}${RED}⏹ STOPPED${NC}" ;; *)       st_badge="${BOLD}${CYAN}${CLIAMP_STATE}${NC}" ;; esac; local bar_len=32; local filled_len=$(( CLIAMP_PROGRESS_PCT * bar_len / 100 )); local empty_len=$(( bar_len - filled_len )); local bar=""; for ((i=0; i<filled_len; i++)); do bar="${bar}="; done; if [ $filled_len -lt $bar_len ]; then bar="${bar}>"; empty_len=$((empty_len - 1)); fi; for ((i=0; i<empty_len; i++)); do bar="${bar}-"; done; echo -e "  Status:        ${st_badge}\n  Title:         ${BOLD}${YELLOW}${CLIAMP_TITLE}${NC}\n  Artist:        ${BOLD}${WHITE}${CLIAMP_ARTIST}${NC}\n  Position:      ${BOLD}${CYAN}${CLIAMP_POS_FMT} / ${CLIAMP_DUR_FMT}${NC} [${bar}] (${CLIAMP_PROGRESS_PCT}%)"; echo ""; echo -e "  ${BOLD}${GREEN}Current File:${NC}  ${BOLD}${CYAN}${CLIAMP_RESOLVED_PATH}${NC}"; if [ "$CLIAMP_FILE_EXISTS" -eq 1 ]; then echo -e "  File Size:     ${GREEN}${CLIAMP_FILE_SIZE}${NC}"; else echo -e "  File Status:   ${RED}File not found at path${NC}"; fi; echo ""; echo -e "${DIM}Shortcuts: [p] Play/Pause  [n] Next  [b] Prev  [c] Copy Path  [o] Open Folder  [q] Exit${NC}"; read -r -t 1 -n 1 key 2>/dev/null || true; case "$key" in c|C) copy_to_clipboard "$CLIAMP_RESOLVED_PATH" || true ;; o|O) open_path "$(dirname "$CLIAMP_RESOLVED_PATH")"; ;; p|P) cliamp toggle 2>/dev/null || true ;; n|N) cliamp next 2>/dev/null || true ;; b|B) cliamp prev 2>/dev/null || true ;; q|Q) break ;; esac; done; trap 'exit_mix_manager' INT
}
manage_cliamp() {
while true; do clear; echo -e "${BOLD}${MAGENTA}==================================================${NC}\n${BOLD}${MAGENTA}       CLIAMP MUSIC PLAYER & NOW PLAYING INFO     ${NC}\n${BOLD}${MAGENTA}==================================================${NC}"; echo ""; if ! get_cliamp_track_info 2>/dev/null; then local cliamp_pids; cliamp_pids=$(pgrep -x cliamp 2>/dev/null); if [ -z "$cliamp_pids" ]; then echo -e "  Player Status:  ${BOLD}${RED}○ NOT RUNNING${NC}"; else echo -e "  Player Status:  ${BOLD}${YELLOW}● RUNNING (Idle / No Active Track)${NC} (PID: ${cliamp_pids})"; fi; echo ""; echo -e "${BOLD}Options:${NC}\n  ${BOLD}${CYAN}1)${NC} Launch cliamp in New Terminal Window\n  ${BOLD}${CYAN}2)${NC} Resume / Start Playback (${GREEN}cliamp play${NC})\n  ${BOLD}${CYAN}0)${NC} Return to Main Menu"; echo ""; read -r -p "Enter choice [0-2]: " c_opt; case "$c_opt" in 1) launch_cliamp; break ;; 2) cliamp play 2>/dev/null; sleep 0.5 ;; 0|q|Q|"") break ;; *) echo -e "${RED}Invalid option!${NC}"; sleep 1 ;; esac; continue; fi; local pids; pids=$(pgrep -x cliamp 2>/dev/null | tr '\n' ' '); local st_badge; case "$CLIAMP_STATE" in playing) st_badge="${BOLD}${GREEN}▶ PLAYING${NC}" ;; paused)  st_badge="${BOLD}${YELLOW}⏸ PAUSED${NC}" ;; stopped) st_badge="${BOLD}${RED}⏹ STOPPED${NC}" ;; *)       st_badge="${BOLD}${CYAN}${CLIAMP_STATE}${NC}" ;; esac; local bar_len=30; local filled_len=$(( CLIAMP_PROGRESS_PCT * bar_len / 100 )); local empty_len=$(( bar_len - filled_len )); local bar=""; for ((i=0; i<filled_len; i++)); do bar="${bar}="; done; if [ $filled_len -lt $bar_len ]; then bar="${bar}>"; empty_len=$((empty_len - 1)); fi; for ((i=0; i<empty_len; i++)); do bar="${bar}-"; done; echo -e "  Player Status:  ${st_badge} (PID: ${pids})\n  Current Track:  ${BOLD}${YELLOW}${CLIAMP_TITLE}${NC}\n  Artist:         ${BOLD}${WHITE}${CLIAMP_ARTIST}${NC}\n  Playback Time:  ${BOLD}${CYAN}${CLIAMP_POS_FMT} / ${CLIAMP_DUR_FMT}${NC} [${bar}] (${CLIAMP_PROGRESS_PCT}%)"; echo ""; echo -e "  ${BOLD}${GREEN}Current Track File Path:${NC}\n  ${BOLD}${CYAN}${CLIAMP_RESOLVED_PATH}${NC}"; if [ "$CLIAMP_RAW_PATH" != "$CLIAMP_RESOLVED_PATH" ]; then echo -e "  ${DIM}(Raw cliamp Path: ${CLIAMP_RAW_PATH})${NC}"; fi; if [ "$CLIAMP_FILE_EXISTS" -eq 1 ]; then echo -e "  File Status:    ${GREEN}✓ File exists on disk${NC} (${CLIAMP_FILE_SIZE})"; local cli_spec; cli_spec=$(get_playing_audio_spec_summary "$CLIAMP_RESOLVED_PATH"); [ -n "$cli_spec" ] && echo -e "  Audio Specs:    ${BOLD}${GREEN}${cli_spec}${NC}"; else echo -e "  File Status:    ${RED}✗ File not found at resolved location${NC}"; fi; echo ""; echo -e "${BOLD}Select an operation:${NC}\n  ${BOLD}${CYAN} 1)${NC} Copy File Path to Clipboard (${GREEN}System Clipboard${NC})\n  ${BOLD}${CYAN} 2)${NC} Open Containing Folder in File Browser (${GREEN}File Manager${NC})\n  ${BOLD}${CYAN} 3)${NC} View Spek Spectrogram of Current Track\n  ${BOLD}${CYAN} 4)${NC} View Tracklist Text File of Current Track\n  ${BOLD}${CYAN} 5)${NC} View Full Audio File Specifications & Stream Analysis (${GREEN}inspect_audio${NC})\n  ${BOLD}${CYAN} 6)${NC} Play / Pause Toggle (${GREEN}cliamp toggle${NC})\n  ${BOLD}${CYAN} 7)${NC} Skip to Next Track (${GREEN}cliamp next${NC})\n  ${BOLD}${CYAN} 8)${NC} Skip to Previous Track (${GREEN}cliamp prev${NC})\n  ${BOLD}${CYAN} 9)${NC} Launch / Bring Up cliamp Terminal Window\n  ${BOLD}${CYAN}10)${NC} Live Real-Time Monitor (Updates Every Second)\n  ${BOLD}${CYAN} 0)${NC} Return to Main Menu"; echo ""; read -r -p "Enter choice [0-10 or c/o/s/t/i/p/n/b/l/w/Enter]: " c_opt; case "$c_opt" in 1|[cC]) if copy_to_clipboard "$CLIAMP_RESOLVED_PATH"; then echo -e "\n${GREEN}✓ File path copied to clipboard!${NC}"; else echo -e "\n${YELLOW}Clipboard utility not available.${NC}"
fi; sleep 1.2; ;; 2|[oO]) local folder_dir; folder_dir=$(dirname "$CLIAMP_RESOLVED_PATH"); if [ -d "$folder_dir" ]; then echo -e "\n${GREEN}Opening $folder_dir in file manager...${NC}"; open_path "$folder_dir"; else echo -e "\n${RED}Directory $folder_dir does not exist!${NC}"; fi; sleep 1.2 ;; 3|[sS]) local bname_no_ext; bname_no_ext=$(basename "$CLIAMP_RESOLVED_PATH"); bname_no_ext="${bname_no_ext%.*}"; shopt -s nullglob nocaseglob; local spek_matches=(SPEK_OUTPUTS/*"${bname_no_ext}"*.png SPEK_OUTPUTS/*"${CLIAMP_TITLE}"*.png); shopt -u nullglob nocaseglob; if [ ${#spek_matches[@]} -gt 0 ] && [ -f "${spek_matches[0]}" ]; then echo -e "\n${GREEN}Opening spectrogram: $(basename "${spek_matches[0]}")...${NC}"; open_path "${spek_matches[0]}"; else echo -e "\n${YELLOW}No matching spectrogram found for '${bname_no_ext}' in SPEK_OUTPUTS/.${NC}"; fi; sleep 1.5; ;; 4|[tT]) local bname_no_ext; bname_no_ext=$(basename "$CLIAMP_RESOLVED_PATH"); bname_no_ext="${bname_no_ext%.*}"; shopt -s nullglob nocaseglob; local tl_matches=("${OUTPUT_DIR}/${bname_no_ext}.txt" "${bname_no_ext}.txt" "${OUTPUT_DIR}/*${CLIAMP_TITLE}*.txt"); shopt -u nullglob nocaseglob; local found_tl=""; for tm in "${tl_matches[@]}"; do if [ -f "$tm" ]; then found_tl="$tm"; break; fi; done; if [ -n "$found_tl" ]; then echo -e "\n${BOLD}${CYAN}=== TRACKLIST: $(basename "$found_tl") ===${NC}\n"; cat "$found_tl"; press_enter; else echo -e "\n${YELLOW}No tracklist .txt file found for '${bname_no_ext}'.${NC}"; sleep 1.5; fi; ;; 5|[iI]) inspect_playing_audio_file "$CLIAMP_RESOLVED_PATH" ;; 6|[pP]) cliamp toggle 2>/dev/null || true; sleep 0.4 ;; 7|[nN]) cliamp next 2>/dev/null || true; sleep 0.5 ;; 8|[bB]) cliamp prev 2>/dev/null || true; sleep 0.5 ;; 9|[lL]) launch_cliamp; break ;; 10|[wW]) monitor_cliamp_live; ;; 0|q|Q|"") break ;; *) echo -e "\n${RED}Invalid choice!${NC}"; sleep 1 ;; esac; done
}
launch_video_playlists() {
echo -e "\n${BOLD}${BLUE}=== LAUNCH VIDEO PLAYLISTS (VLC) ===${NC}\n  ${BOLD}${CYAN}1)${NC} Play NFT Videos Playlist in VLC (${GREEN}NFT_VIDEOS.xspf${NC})\n  ${BOLD}${CYAN}2)${NC} Regenerate NFT Playlist from /run/media/mplanetarian/DATA/NFT_VIDEOS\n  ${BOLD}${CYAN}3)${NC} Return to Main Menu"; echo ""; read -r -p "Enter choice [1-3]: " v_choice; case $v_choice in 1) if [ -x "$HOME/.local/bin/update-nft-playlist" ]; then "$HOME/.local/bin/update-nft-playlist" --quiet; fi; local nft_pl="$HOME/Desktop/DESKTOP/NFT_VIDEOS.xspf"; [ ! -f "$nft_pl" ] && nft_pl="$HOME/Desktop/NFT_VIDEOS.xspf"; [ ! -f "$nft_pl" ] && nft_pl="$HOME/Desktop/DESKTOP/NFT_VIDEOS.m3u"; [ ! -f "$nft_pl" ] && nft_pl="$HOME/Desktop/NFT_VIDEOS.m3u"; if [ -f "$nft_pl" ]; then echo -e "${GREEN}Launching VLC with NFT Videos playlist...${NC}"; nohup vlc "$nft_pl" &>/dev/null &
sleep 1.2; else echo -e "${RED}Error: NFT Videos playlist not found on Desktop or Desktop/DESKTOP!${NC}"; press_enter; fi ;; 2) if [ -x "$HOME/.local/bin/update-nft-playlist" ]; then "$HOME/.local/bin/update-nft-playlist"; else echo -e "${RED}Error: update-nft-playlist helper not found!${NC}"; fi; press_enter ;; 3) return; ;; *) echo -e "${RED}Invalid selection.${NC}"; sleep 1; ;; esac
}
close_all_desktop_apps() {
echo -e "\n${BOLD}${RED}=== CLOSE ALL DESKTOP APPLICATIONS ===${NC}\n${YELLOW}This will close all open desktop application windows while keeping the Manager open.${NC}"; read -r -p "Are you sure you want to proceed? [y/N]: " confirm; if [[ ! "$confirm" =~ ^[Yy]$ ]]; then echo -e "${BLUE}Operation canceled.${NC}"; sleep 1; return; fi; echo -e "\n${CYAN}Identifying active Manager session and closing other windows...${NC}"; if [ "$OS_TYPE" = "macos" ]; then
osascript -e 'tell application "System Events"
            set appList to name of every application process whose visible is true and name is not "Terminal" and name is not "iTerm2" and name is not "Finder" and name is not "Ghostty" and name is not "Alacritty" and name is not "kitty"
            repeat with appName in appList
                tell application appName to quit
            end repeat
        end tell' 2>/dev/null
echo -e "${GREEN}✓ Closed open macOS applications.${NC}"; press_enter; return 0; elif [ "$OS_TYPE" = "windows" ] || [ "$OS_TYPE" = "wsl" ]; then powershell.exe -Command "Get-Process | Where-Object { \$_.MainWindowTitle -ne '' -and \$_.ProcessName -notmatch 'bash|cmd|powershell|WindowsTerminal|mintty|conhost|explorer' } | ForEach-Object { \$_.CloseMainWindow() }" 2>/dev/null; echo -e "${GREEN}✓ Closed open Windows desktop applications.${NC}"; press_enter; return 0; fi; local current_pid=$$; local mgr_pids=("$current_pid"); local p=$current_pid; while [ "$p" -gt 1 ]; do p=$(ps -o ppid= -p "$p" 2>/dev/null | tr -d ' '); if [ -n "$p" ] && [ "$p" -gt 0 ]; then mgr_pids+=("$p"); else break; fi; done; local my_win_hex=""; if [ -n "${WINDOWID:-}" ]; then my_win_hex=$(printf "0x%08x" "$WINDOWID" 2>/dev/null || true); fi; local closed_count=0; if command -v wmctrl &>/dev/null; then while read -r win_id desktop_num win_pid host win_title; do if [ "$desktop_num" -lt 0 ] || [[ "$win_title" == *"plasmashell"* ]]; then continue; fi; if [ -n "$my_win_hex" ] && [ "$win_id" = "$my_win_hex" ]; then continue; fi; local is_mgr=false; for mp in "${mgr_pids[@]}"; do if [ "$win_pid" = "$mp" ]; then is_mgr=true; break; fi; done; if [ "$is_mgr" = true ]; then continue; fi; wmctrl -c "$win_id"; ((closed_count++)); done < <(wmctrl -lp 2>/dev/null); fi; sleep 1; local apps_to_clean=("vlc" "mpv" "strawberry" "cliamp" "btop" "nvtop" "top" "cpu-x" "GPUViewer" "steam" "steamwebhelper"); for app in "${apps_to_clean[@]}"; do pkill -f "$app" 2>/dev/null || true; done; echo -e "${GREEN}✓ Closed $closed_count application window(s).${NC}\n${GREEN}✓ Active MP Mix Archive Manager kept open and protected.${NC}"; press_enter
}
block_internet() {
echo -e "\n${BOLD}${RED}=== BLOCK INTERNET ACCESS (LAN ONLY) ===${NC}"; local script="$HOME/Documents/BASH_SCRIPTS/block-internet"; [ ! -f "$script" ] && script="$HOME/bin/block-internet"; [ ! -f "$script" ] && script="$SCRIPT_DIR/bin/block-internet"; [ ! -f "$script" ] && script="$SCRIPT_DIR/block-internet"; if command -v systemd-run &>/dev/null; then echo -e "${YELLOW}Running via systemd-run...${NC}\n"; if command -v block-internet &>/dev/null; then systemd-run --user --pipe block-internet; elif [ -f "$script" ]; then systemd-run --user --pipe "$script"; else echo -e "${RED}Error: block-internet script not found!${NC}"; fi; elif [ -f "$script" ]; then echo -e "${YELLOW}Running $script...${NC}\n"; sudo bash "$script"; elif command -v block-internet &>/dev/null; then echo -e "${YELLOW}Running block-internet...${NC}\n"; sudo block-internet; else echo -e "${RED}Error: block-internet script not found at $script!${NC}"; fi; press_enter
}
unblock_internet() {
echo -e "\n${BOLD}${GREEN}=== RESTORE / UNBLOCK INTERNET ACCESS ===${NC}"; local script="$HOME/Documents/BASH_SCRIPTS/unblock-internet"; [ ! -f "$script" ] && script="$HOME/bin/unblock-internet"; [ ! -f "$script" ] && script="$SCRIPT_DIR/bin/unblock-internet"; [ ! -f "$script" ] && script="$SCRIPT_DIR/unblock-internet"; if command -v systemd-run &>/dev/null; then echo -e "${YELLOW}Running via systemd-run...${NC}\n"; if command -v unblock-internet &>/dev/null; then systemd-run --user --pipe unblock-internet; elif [ -f "$script" ]; then systemd-run --user --pipe "$script"; else echo -e "${RED}Error: unblock-internet script not found!${NC}"; fi; elif [ -f "$script" ]; then echo -e "${YELLOW}Running $script...${NC}\n"; sudo bash "$script"; elif command -v unblock-internet &>/dev/null; then echo -e "${YELLOW}Running unblock-internet...${NC}\n"; sudo unblock-internet; else echo -e "${RED}Error: unblock-internet script not found at $script!${NC}"; fi; press_enter
}
launch_geexlab_demos() {
echo -e "\n${BOLD}${YELLOW}Launching GeeXLab Demo Launcher (FurMark)...${NC}\n"; local furmark_dir="/var/home/mplanetarian/Documents/FurMark_linux64"; if [ -d "$furmark_dir" ] && [ -x "$furmark_dir/demo_launcher.sh" ]; then sleep 0.5; trap ':' INT; (cd "$furmark_dir" && ./demo_launcher.sh); trap 'exit_mix_manager' INT; else echo -e "${RED}Error: demo_launcher.sh not found or not executable in $furmark_dir!${NC}"; press_enter; fi
}
list_usb_midi_devices() {
echo -e "\n${BOLD}${CYAN}=== CONNECTED USB MIDI DEVICES ===${NC}\n"; if command -v list-midi-devices &>/dev/null; then list-midi-devices; elif [ -x "$HOME/bin/list-midi-devices" ]; then "$HOME/bin/list-midi-devices"; else echo -e "${RED}Error: list-midi-devices command not found in PATH or ~/bin!${NC}"; press_enter; return; fi; echo ""; echo -e "${DIM}Options: Press [Enter] to return to menu, or [w] for real-time live monitor...${NC}"; read -r -p "> " midi_opt; if [[ "$midi_opt" =~ ^[wW]$ ]]; then echo -e "\n${BOLD}${YELLOW}Launching Live MIDI Monitor (Press Ctrl+C to return)...${NC}\n"; sleep 0.5; trap ':' INT; if command -v list-midi-devices &>/dev/null; then list-midi-devices -w; else "$HOME/bin/list-midi-devices" -w; fi; trap 'exit_mix_manager' INT; fi
}
switch_to_wayland() {
if [ "$OS_TYPE" = "macos" ]; then echo -e "\n${BOLD}${YELLOW}macOS uses Quartz / WindowServer compositor.${NC}\n${CYAN}Opening macOS Display Settings...${NC}"; open "x-apple.systempreferences:com.apple.Displays-Settings.extension" 2>/dev/null || open /System/Library/PreferencePanes/Displays.prefPane 2>/dev/null; press_enter; return 0; elif [ "$OS_TYPE" = "windows" ] || [ "$OS_TYPE" = "wsl" ]; then echo -e "\n${BOLD}${YELLOW}Windows 10/11 uses Desktop Window Manager (DWM).${NC}\n${CYAN}Opening Windows Display Settings...${NC}"; cmd.exe /c start ms-settings:display 2>/dev/null; press_enter; return 0; fi; local script="$SCRIPT_DIR/switch-to-plasma-wayland.sh"; [ ! -f "$script" ] && script="$SCRIPT_DIR/scripts/switch-to-plasma-wayland.sh"; [ ! -f "$script" ] && script="$HOME/Documents/BASH_SCRIPTS/switch-to-plasma-wayland.sh"; if [ -x "$script" ]; then "$script"; elif [ -f "$script" ]; then bash "$script"; else echo -e "${RED}Error: Switch script not found at $script!${NC}"; press_enter; fi
}
switch_to_x11() {
if [ "$OS_TYPE" = "macos" ]; then echo -e "\n${BOLD}${YELLOW}macOS Audio & Sound Configuration.${NC}\n${CYAN}Opening Audio MIDI Setup...${NC}"; open -a "Audio MIDI Setup" 2>/dev/null || open /System/Applications/Utilities/Audio\ MIDI\ Setup.app 2>/dev/null; press_enter; return 0; elif [ "$OS_TYPE" = "windows" ] || [ "$OS_TYPE" = "wsl" ]; then echo -e "\n${BOLD}${YELLOW}Windows Audio Control Panel.${NC}\n${CYAN}Opening Windows Sound Settings...${NC}"; cmd.exe /c start control.exe mmsys.cpl 2>/dev/null; press_enter; return 0; fi; local script="$SCRIPT_DIR/switch-to-plasma-x11.sh"; [ ! -f "$script" ] && script="$SCRIPT_DIR/scripts/switch-to-plasma-x11.sh"; [ ! -f "$script" ] && script="$HOME/Documents/BASH_SCRIPTS/switch-to-plasma-x11.sh"; if [ -x "$script" ]; then "$script"; elif [ -f "$script" ]; then bash "$script"; else echo -e "${RED}Error: Switch script not found at $script!${NC}"; press_enter; fi
}
launch_wan2gp_terminal() {
local profile="$1"; local title="WAN2GP (Profile $profile)"; local script="$SCRIPT_DIR/scripts/wan2gp.sh"; [ ! -f "$script" ] && script="$SCRIPT_DIR/wan2gp.sh"; [ ! -f "$script" ] && script="$HOME/wan2gp.sh"; [ ! -f "$script" ] && script="/var/home/mplanetarian/MP_Mix_Manager_v0.3/scripts/wan2gp.sh"; [ ! -f "$script" ] && script="$HOME/Documents/BASH_SCRIPTS/wan2gp.sh"; export WAN2GP_OUTPUTS WAN2GP_FLUX_BATCH_DIR WAN2GP_LTX_BATCH_DIR WAN2GP_DIR WAN2GP_PYTHON; local cmd="export WAN2GP_OUTPUTS=\"$WAN2GP_OUTPUTS\" WAN2GP_FLUX_BATCH_DIR=\"$WAN2GP_FLUX_BATCH_DIR\" WAN2GP_LTX_BATCH_DIR=\"$WAN2GP_LTX_BATCH_DIR\" WAN2GP_DIR=\"$WAN2GP_DIR\" WAN2GP_PYTHON=\"$WAN2GP_PYTHON\"; bash \"$script\" \"$profile\"; echo ''; echo 'WAN2GP finished. Press [Enter] to exit...'; read -r"; if launch_in_terminal "$title" "$cmd" "tab"; then echo -e "${GREEN}✓ WAN2GP launched in a new console tab/window (Profile $profile).${NC}"; sleep 1.2; return 0; else echo -e "${RED}Error: No supported terminal emulator found to launch in a new window/tab.${NC}"; press_enter; return 1; fi
}
launch_wan2gp_flux_batch_terminal() {
local mode="$1"; local title="WAN2GP Flux 2 Klein Batch"; if [[ "$mode" == *"--multi-control"* ]]; then title="WAN2GP Flux Multi-Control Batch"; fi; local script="$SCRIPT_DIR/scripts/wan2gp_flux_batch.py"; [ ! -f "$script" ] && script="$SCRIPT_DIR/wan2gp_flux_batch.py"; [ ! -f "$script" ] && script="$HOME/wan2gp_flux_batch.py"; [ ! -f "$script" ] && script="$HOME/Documents/BASH_SCRIPTS/scripts/wan2gp_flux_batch.py"; [ ! -f "$script" ] && script="/var/home/mplanetarian/MP_Mix_Manager_v0.3/scripts/wan2gp_flux_batch.py"; if [ ! -f "$script" ]; then echo -e "${RED}Error: wan2gp_flux_batch.py not found!${NC}"; press_enter; return 1; fi; chmod +x "$script" 2>/dev/null || true; export WAN2GP_OUTPUTS WAN2GP_FLUX_BATCH_DIR WAN2GP_LTX_BATCH_DIR WAN2GP_DIR WAN2GP_PYTHON; local cmd="export WAN2GP_OUTPUTS=\"$WAN2GP_OUTPUTS\" WAN2GP_FLUX_BATCH_DIR=\"$WAN2GP_FLUX_BATCH_DIR\" WAN2GP_LTX_BATCH_DIR=\"$WAN2GP_LTX_BATCH_DIR\" WAN2GP_DIR=\"$WAN2GP_DIR\" WAN2GP_PYTHON=\"$WAN2GP_PYTHON\"; bash \"$script\" --batch-dir \"$WAN2GP_FLUX_BATCH_DIR\" --output-dir \"$WAN2GP_OUTPUTS\" $mode; echo ''; echo 'Batch process finished. Press [Enter] to exit...'; read -r"; if launch_in_terminal "$title" "$cmd" "tab"; then echo -e "${GREEN}✓ Flux 2 Klein 9B Batch Processor launched in a new console tab/window.${NC}"; sleep 1.2; return 0; else echo -e "${RED}Error: No supported terminal emulator found to launch in a new window/tab.${NC}"; press_enter; return 1; fi
}
launch_wan2gp_ltx_batch_terminal() {
local mode="$1"; local model="${2:-2b}"; local lora="${3:-${WAN2GP_LTX_LORA:-bfs_head_swap}}"; local title="WAN2GP LTX Video ${model^^} Batch"; if [ -n "$lora" ] && [ "$lora" != "none" ]; then title="WAN2GP LTX Video ${model^^} [${lora}]"; elif [[ "$mode" == *"--no-control"* ]]; then title="WAN2GP LTX Video ${model^^} (Pure I2V)"; elif [[ "$mode" == *"--watch"* ]]; then title="WAN2GP LTX Video ${model^^} (Watch Mode)"; fi; local script="$SCRIPT_DIR/scripts/wan2gp_ltx_batch.py"; [ ! -f "$script" ] && script="$SCRIPT_DIR/wan2gp_ltx_batch.py"; [ ! -f "$script" ] && script="$HOME/wan2gp_ltx_batch.py"; [ ! -f "$script" ] && script="$HOME/Documents/BASH_SCRIPTS/scripts/wan2gp_ltx_batch.py"; [ ! -f "$script" ] && script="/var/home/mplanetarian/MP_Mix_Manager_v0.3/scripts/wan2gp_ltx_batch.py"; if [ ! -f "$script" ]; then echo -e "${RED}Error: wan2gp_ltx_batch.py not found!${NC}"; press_enter; return 1; fi; chmod +x "$script" 2>/dev/null || true; local lora_arg=""; if [ -n "$lora" ] && [ "$lora" != "none" ]; then lora_arg="--lora $lora"; fi; export WAN2GP_OUTPUTS WAN2GP_FLUX_BATCH_DIR WAN2GP_LTX_BATCH_DIR WAN2GP_DIR WAN2GP_PYTHON; local cmd="export WAN2GP_OUTPUTS=\"$WAN2GP_OUTPUTS\" WAN2GP_FLUX_BATCH_DIR=\"$WAN2GP_FLUX_BATCH_DIR\" WAN2GP_LTX_BATCH_DIR=\"$WAN2GP_LTX_BATCH_DIR\" WAN2GP_DIR=\"$WAN2GP_DIR\" WAN2GP_PYTHON=\"$WAN2GP_PYTHON\"; bash \"$script\" --model $model $lora_arg --batch-dir \"$WAN2GP_LTX_BATCH_DIR\" --output-dir \"$WAN2GP_OUTPUTS\" $mode; echo ''; echo 'Batch process finished. Press [Enter] to exit...'; read -r"; if launch_in_terminal "$title" "$cmd" "tab"; then echo -e "${GREEN}✓ LTX Video ${model^^} Batch Processor launched in a new console tab/window.${NC}"; sleep 1.2; return 0; else echo -e "${RED}Error: No supported terminal emulator found to launch in a new window/tab.${NC}"; press_enter; return 1; fi
}
launch_wan2gp_inftlk_batch_terminal() {
local mode="$1"; local title="MP Infinite Talker (Stephen Hawking)"; if [[ "$mode" == *"--watch"* ]]; then title="MP Infinite Talker (Watch Mode)"; fi; local script="$SCRIPT_DIR/scripts/MP_Infinite_Talker.py"; [ ! -f "$script" ] && script="$SCRIPT_DIR/MP_Infinite_Talker.py"; [ ! -f "$script" ] && script="$HOME/MP_Infinite_Talker.py"; if [ ! -f "$script" ]; then echo -e "${RED}Error: MP_Infinite_Talker.py not found!${NC}"; press_enter; return 1; fi; chmod +x "$script" 2>/dev/null || true; export WAN2GP_OUTPUTS WAN2GP_INFTLKBATCH_DIR WAN2GP_FLUX_BATCH_DIR WAN2GP_LTX_BATCH_DIR WAN2GP_DIR WAN2GP_PYTHON; local batch_d="${WAN2GP_INFTLKBATCH_DIR:-/run/media/mplanetarian/GAMES1/DATA_DRIVE_MOVED/WAN2GP_INFTLKBATCH}"; local cmd="export WAN2GP_OUTPUTS=\"$WAN2GP_OUTPUTS\" WAN2GP_INFTLKBATCH_DIR=\"$batch_d\" WAN2GP_FLUX_BATCH_DIR=\"$WAN2GP_FLUX_BATCH_DIR\" WAN2GP_LTX_BATCH_DIR=\"$WAN2GP_LTX_BATCH_DIR\" WAN2GP_DIR=\"$WAN2GP_DIR\" WAN2GP_PYTHON=\"$WAN2GP_PYTHON\"; bash \"$script\" --batch-dir \"$batch_d\" --output-dir \"$WAN2GP_OUTPUTS\" $mode; echo ''; echo 'Infinite Talk process finished. Press [Enter] to exit...'; read -r"; if launch_in_terminal "$title" "$cmd" "tab"; then echo -e "${GREEN}✓ MP Infinite Talker launched in a new console tab/window.${NC}"; sleep 1.2; return 0; else echo -e "${RED}Error: No supported terminal emulator found to launch in a new window/tab.${NC}"; press_enter; return 1; fi
}
run_wan2gp_infinite_talker() {
local script="$SCRIPT_DIR/scripts/MP_Infinite_Talker.py"; [ ! -f "$script" ] && script="$SCRIPT_DIR/MP_Infinite_Talker.py"; [ ! -f "$script" ] && script="$SCRIPT_DIR/MP_Infinite_Talker.sh"; if [ -f "$script" ]; then python3 "$script" "$@"; else echo -e "${RED}Error: MP_Infinite_Talker.py not found at $script!${NC}"; press_enter; fi
}
clear_wan2gp_logs() {
local script="$SCRIPT_DIR/clear-wan2gp-logs.sh"; [ ! -f "$script" ] && script="$SCRIPT_DIR/scripts/clear-wan2gp-logs.sh"; [ ! -f "$script" ] && script="$HOME/Documents/BASH_SCRIPTS/clear-wan2gp-logs.sh"; if [ -x "$script" ]; then "$script"; elif [ -f "$script" ]; then bash "$script"; else echo -e "${RED}Error: Clear WAN2GP logs script not found at $script!${NC}"; press_enter; fi
}
run_duplicate_image_remover() {
echo -e "\n${BOLD}${GREEN}=== BYTE-FOR-BYTE DUPLICATE IMAGE REMOVER ===${NC}\n"; local script="./remove_duplicate_images.py"; [ ! -f "$script" ] && script="$SCRIPT_DIR/remove_duplicate_images.py"; [ ! -f "$script" ] && script="$SCRIPT_DIR/scripts/remove_duplicate_images.py"; [ ! -f "$script" ] && script="${MIX_ARCHIVE_DIR:-$SCRIPT_DIR/MIX_ARCHIVE}/remove_duplicate_images.py"; [ ! -f "$script" ] && script="$HOME/Documents/BASH_SCRIPTS/remove_duplicate_images.py"; if [ -f "$script" ]; then python3 "$script"; else echo -e "${RED}Error: remove_duplicate_images.py not found at $script!${NC}"; fi; echo ""; read -r -p "Press [Enter] to return to the WAN2GP menu..."
}
run_wan2gp_tts_batch() {
local script="$SCRIPT_DIR/scripts/wan2gp_tts_batch.py"; [ ! -f "$script" ] && script="$SCRIPT_DIR/wan2gp_tts_batch.py"; [ ! -f "$script" ] && script="$HOME/wan2gp_tts_batch.py"; [ ! -f "$script" ] && script="$HOME/bin/wan2gp_tts_batch"; if [ -f "$script" ]; then python3 "$script" "$@"; else echo -e "${RED}Error: wan2gp_tts_batch.py not found at $script!${NC}"; press_enter; fi
}
run_wan2gp_output_monitor() {
local script="$SCRIPT_DIR/scripts/MP_Video_Image_Dir_WAN2GP_Output_Monitor.py"; [ ! -f "$script" ] && script="$SCRIPT_DIR/MP_Video_Image_Dir_WAN2GP_Output_Monitor.py"; [ ! -f "$script" ] && script="$HOME/MP_Mix_Manager_v0.3/scripts/MP_Video_Image_Dir_WAN2GP_Output_Monitor.py"; [ ! -f "$script" ] && script="$HOME/Downloads/MP_Video_Image_Dir_WAN2GP_Output_Monitor.py"; if [ ! -f "$script" ]; then echo -e "${RED}Error: MP_Video_Image_Dir_WAN2GP_Output_Monitor.py not found!${NC}"; press_enter; return 1; fi; chmod +x "$script" 2>/dev/null || true; local target_dir="${1:-${WAN2GP_OUTPUTS:-}}"; if [ -z "$target_dir" ] || [ ! -d "$target_dir" ]; then if [ -d "/run/media/mplanetarian/GAMES1/DATA_DRIVE_MOVED/WAN2GP_OUTPUTS" ]; then target_dir="/run/media/mplanetarian/GAMES1/DATA_DRIVE_MOVED/WAN2GP_OUTPUTS"; elif [ -d "$HOME/Documents/WAN2GP_OUTPUTS" ]; then target_dir="$HOME/Documents/WAN2GP_OUTPUTS"; elif [ -d "$HOME/WAN2GP_OUTPUTS" ]; then target_dir="$HOME/WAN2GP_OUTPUTS"; fi; fi
local mon_opts=(
"1|Launch Output Monitor in Current Terminal|(Live console view)"
"2|Launch Output Monitor in New Terminal Window/Tab|(Keeps Manager running)"
"3|Configure / Change Output Directory to Monitor|(Select Any Directory)"
"4|Set Current Selection as Default WAN2GP_OUTPUTS|(Save to config.env)"
"SEP|SEP|"
"0|Return to WAN2GP Menu|(or Esc / q)"
)
while true; do
local hdr="  Current Monitored Directory: ${BOLD}${CYAN}${target_dir:-Not Configured}${NC}\n  Default WAN2GP Outputs Dir:  ${BOLD}${GREEN}${WAN2GP_OUTPUTS:-Not Configured}${NC}\n"
run_interactive_submenu "MP VIDEO & IMAGE DIRECTORY OUTPUT MONITOR" "$hdr" mon_opts 0
case "$REPLY" in
1)
echo -e "\n${GREEN}Starting MP Video & Image Directory Output Monitor...${NC}\n"
export WAN2GP_OUTPUTS="$target_dir"
python3 "$script" --dir "$target_dir"
echo ""
read -r -p "Press [Enter] to return to the Monitor menu..."
;;
2)
local title="MP Media Output Monitor"
local cmd="export WAN2GP_OUTPUTS=\"$target_dir\"; python3 \"$script\" --dir \"$target_dir\"; echo ''; echo 'Monitor stopped. Press [Enter] to exit...'; read -r"
if launch_in_terminal "$title" "$cmd" "tab"; then
echo -e "\n${GREEN}✓ MP Video & Image Directory Output Monitor launched in a new terminal tab/window.${NC}"
sleep 1.5
else
echo -e "\n${YELLOW}Could not open new terminal window; running in current terminal...${NC}\n"
export WAN2GP_OUTPUTS="$target_dir"
python3 "$script" --dir "$target_dir"
echo ""
read -r -p "Press [Enter] to return to the Monitor menu..."
fi
;;
3)
echo -e "\n${BOLD}${CYAN}Configure Output Directory to Monitor:${NC}\nEnter path of any directory to monitor (e.g. /path/to/folder or ~/Documents/WAN2GP_OUTPUTS):"
read -r -e -p "Directory path: " new_dir
new_dir="${new_dir#"${new_dir%%[![:space:]]*}"}"
new_dir="${new_dir%"${new_dir##*[![:space:]]}"}"
if [[ "$new_dir" == "~"* ]]; then new_dir="${HOME}${new_dir:1}"; fi
if [ -n "$new_dir" ]; then
if [ ! -d "$new_dir" ]; then
echo -e "${YELLOW}Directory does not exist: $new_dir${NC}"
read -r -p "Would you like to create this directory? [y/N]: " create_ans
if [[ "$create_ans" =~ ^[yY] ]]; then mkdir -p "$new_dir" 2>/dev/null && echo -e "${GREEN}Created directory: $new_dir${NC}" || echo -e "${RED}Failed to create directory.${NC}"; fi
fi
if [ -d "$new_dir" ]; then
target_dir="$new_dir"
echo -e "${GREEN}✓ Monitored directory set to: $target_dir${NC}"
read -r -p "Also set this as the default WAN2GP_OUTPUTS in config.env? [y/N]: " save_ans
if [[ "$save_ans" =~ ^[yY] ]]; then
save_config_setting "WAN2GP_OUTPUTS" "$target_dir"
WAN2GP_OUTPUTS="$target_dir"
export WAN2GP_OUTPUTS
echo -e "${GREEN}✓ Saved to config.env as WAN2GP_OUTPUTS.${NC}"
fi
sleep 1.2
else
echo -e "${RED}Path is not a valid directory.${NC}"
sleep 1.5
fi
fi
;;
4)
if [ -n "$target_dir" ] && [ -d "$target_dir" ]; then
save_config_setting "WAN2GP_OUTPUTS" "$target_dir"
WAN2GP_OUTPUTS="$target_dir"
export WAN2GP_OUTPUTS
echo -e "\n${GREEN}✓ Successfully saved WAN2GP_OUTPUTS=\"$target_dir\" to config.env!${NC}"
sleep 1.5
else
echo -e "\n${RED}Current target directory is invalid or not found.${NC}"
sleep 1.5
fi
;;
0|[qQ]|[eE][xX][iI][tT]|ESC) return 0 ;;
*)
local expanded_path="$REPLY"
if [[ "$expanded_path" == "~"* ]]; then expanded_path="${HOME}${expanded_path:1}"; fi
if [ -n "$expanded_path" ] && [ -d "$expanded_path" ]; then
target_dir="$expanded_path"
echo -e "\n${GREEN}✓ Monitored directory set to: $target_dir${NC}"
sleep 1
else
echo -e "\n${RED}Invalid option!${NC}"
sleep 1
fi
;;
esac
done
}
configure_wan2gp_directories() {
clear; echo -e "${BOLD}${MAGENTA}${S70}${NC}\n${BOLD}${MAGENTA}          CONFIGURE WAN2GP WORKSPACE & OUTPUT DIRECTORIES             ${NC}\n${BOLD}${MAGENTA}${S70}${NC}\n\nWAN2GP operations require four directory locations to be configured:\n  ${BOLD}1. WAN2GP Outputs Directory${NC}     : Master destination for generated videos/images\n  ${BOLD}2. Flux Batch Workspace${NC}         : Input/working folder for Flux 2 Klein 9B\n  ${BOLD}3. LTX Video Batch Workspace${NC}    : Input/working folder for LTX Video models\n  ${BOLD}4. Infinite Talk Batch Workspace${NC}: Input/working folder for Infinite Talk (Stephen Hawking & Voice Cloning)\n"; local is_win=false; if [[ "$OSTYPE" == "msys"* || "$OSTYPE" == "cygwin"* ]] || [ -n "${WINDIR:-}" ] || command -v cmd.exe &>/dev/null; then is_win=true; fi; local def_outputs def_flux def_ltx def_inftlk; if [ "$is_win" = true ]; then def_outputs="D:/DATA_DRIVE_MOVED/WAN2GP_OUTPUTS"; def_flux="D:/DATA_DRIVE_MOVED/WAN2GP_FLUX_BATCH"; def_ltx="D:/DATA_DRIVE_MOVED/WAN2GP_LTX_BATCH"; def_inftlk="D:/DATA_DRIVE_MOVED/WAN2GP_INFTLKBATCH"; else def_outputs="/run/media/${USER:-user}/GAMES1/DATA_DRIVE_MOVED/WAN2GP_OUTPUTS"; def_flux="/run/media/${USER:-user}/GAMES1/DATA_DRIVE_MOVED/WAN2GP_FLUX_BATCH"; def_ltx="/run/media/${USER:-user}/GAMES1/DATA_DRIVE_MOVED/WAN2GP_LTX_BATCH"; def_inftlk="/run/media/${USER:-user}/GAMES1/DATA_DRIVE_MOVED/WAN2GP_INFTLKBATCH"; fi; [ -n "$WAN2GP_OUTPUTS" ] && def_outputs="$WAN2GP_OUTPUTS"; [ -n "$WAN2GP_FLUX_BATCH_DIR" ] && def_flux="$WAN2GP_FLUX_BATCH_DIR"; [ -n "$WAN2GP_LTX_BATCH_DIR" ] && def_ltx="$WAN2GP_LTX_BATCH_DIR"; [ -n "$WAN2GP_INFTLKBATCH_DIR" ] && def_inftlk="$WAN2GP_INFTLKBATCH_DIR"; if [ "$is_win" = true ]; then echo -e "${YELLOW}[Windows Mode] You can enter paths like: D:\\DATA_DRIVE_MOVED\\WAN2GP_OUTPUTS or D:/DATA_DRIVE_MOVED/...${NC}\n"; else echo -e "${YELLOW}[Linux/Unix Mode] You can enter paths like: /run/media/$USER/... or ~/WAN2GP_OUTPUTS${NC}\n"; fi; local in_outputs; echo -e "${BOLD}${CYAN}[1/4] WAN2GP General Outputs Directory:${NC}\nCurrent / Default: ${BOLD}${GREEN}${def_outputs}${NC}"; read -r -p "Enter path [Press Enter to keep default, or 'q' to cancel]: " in_outputs; in_outputs="${in_outputs#"${in_outputs%%[![:space:]]*}"}"; in_outputs="${in_outputs%"${in_outputs##*[![:space:]]}"}"; if [ "$in_outputs" = "q" ] || [ "$in_outputs" = "Q" ]; then echo -e "\n${YELLOW}Configuration canceled.${NC}"; sleep 1; return 1; fi; [ -z "$in_outputs" ] && in_outputs="$def_outputs"; in_outputs="${in_outputs//\\//}"; local in_flux; echo -e "\n${BOLD}${CYAN}[2/4] Flux 2 Klein 9B Batch Workspace Directory:${NC}\nCurrent / Default: ${BOLD}${GREEN}${def_flux}${NC}"; read -r -p "Enter path [Press Enter to keep default, or 'q' to cancel]: " in_flux; in_flux="${in_flux#"${in_flux%%[![:space:]]*}"}"; in_flux="${in_flux%"${in_flux##*[![:space:]]}"}"; if [ "$in_flux" = "q" ] || [ "$in_flux" = "Q" ]; then echo -e "\n${YELLOW}Configuration canceled.${NC}"; sleep 1; return 1; fi; [ -z "$in_flux" ] && in_flux="$def_flux"; in_flux="${in_flux//\\//}"; local in_ltx; echo -e "\n${BOLD}${CYAN}[3/4] LTX Video Batch Workspace Directory:${NC}\nCurrent / Default: ${BOLD}${GREEN}${def_ltx}${NC}"; read -r -p "Enter path [Press Enter to keep default, or 'q' to cancel]: " in_ltx; in_ltx="${in_ltx#"${in_ltx%%[![:space:]]*}"}"; in_ltx="${in_ltx%"${in_ltx##*[![:space:]]}"}"; if [ "$in_ltx" = "q" ] || [ "$in_ltx" = "Q" ]; then echo -e "\n${YELLOW}Configuration canceled.${NC}"; sleep 1; return 1; fi; [ -z "$in_ltx" ] && in_ltx="$def_ltx"; in_ltx="${in_ltx//\\//}"; local in_inftlk; echo -e "\n${BOLD}${CYAN}[4/4] Infinite Talk Batch Workspace Directory:${NC}\nCurrent / Default: ${BOLD}${GREEN}${def_inftlk}${NC}"; read -r -p "Enter path [Press Enter to keep default, or 'q' to cancel]: " in_inftlk; in_inftlk="${in_inftlk#"${in_inftlk%%[![:space:]]*}"}"; in_inftlk="${in_inftlk%"${in_inftlk##*[![:space:]]}"}"; if [ "$in_inftlk" = "q" ] || [ "$in_inftlk" = "Q" ]; then echo -e "\n${YELLOW}Configuration canceled.${NC}"; sleep 1; return 1; fi; [ -z "$in_inftlk" ] && in_inftlk="$def_inftlk"; in_inftlk="${in_inftlk//\\//}"; echo -e "\n${CYAN}Creating and verifying directory structures...${NC}"; mkdir -p "$in_outputs" 2>/dev/null || true; mkdir -p "$in_flux" "$in_flux/CTRL_IMAGE" "$in_flux/PROCESSED" "$in_flux/PENDING_ICONIC" 2>/dev/null || true; mkdir -p "$in_ltx" "$in_ltx/CTRL_VIDEO" "$in_ltx/PROCESSED" 2>/dev/null || true; mkdir -p "$in_inftlk" "$in_inftlk/CTRL_IMAGE" "$in_inftlk/PROCESSED" "$in_inftlk/OUTPUTS" "$in_inftlk/VOICES" "$in_inftlk/TTS_CONVERTED" 2>/dev/null || true
save_config_setting "WAN2GP_OUTPUTS" "$in_outputs"; save_config_setting "WAN2GP_FLUX_BATCH_DIR" "$in_flux"; save_config_setting "WAN2GP_LTX_BATCH_DIR" "$in_ltx"; save_config_setting "WAN2GP_INFTLKBATCH_DIR" "$in_inftlk"; save_config_setting "WAN2GP_CONFIGURED" "true"; WAN2GP_OUTPUTS="$in_outputs"; WAN2GP_FLUX_BATCH_DIR="$in_flux"; WAN2GP_LTX_BATCH_DIR="$in_ltx"; WAN2GP_INFTLKBATCH_DIR="$in_inftlk"; WAN2GP_CONFIGURED="true"; export WAN2GP_OUTPUTS WAN2GP_FLUX_BATCH_DIR WAN2GP_LTX_BATCH_DIR WAN2GP_INFTLKBATCH_DIR WAN2GP_CONFIGURED; echo -e "${GREEN}✓ Successfully configured WAN2GP Directories:${NC}\n  • Outputs : ${BOLD}${in_outputs}${NC}\n  • Flux    : ${BOLD}${in_flux}${NC} (with CTRL_IMAGE, PROCESSED, PENDING_ICONIC)\n  • LTX     : ${BOLD}${in_ltx}${NC} (with CTRL_VIDEO, PROCESSED)\n  • InfTalk : ${BOLD}${in_inftlk}${NC} (with CTRL_IMAGE, PROCESSED, OUTPUTS, VOICES, TTS_CONVERTED)"; echo ""; press_enter; return 0
}
manage_wan2gp() {
local init_opts=(
"1|Configure WAN2GP Directories Now|(Outputs, Flux, LTX, InfTalk)"
"0|Return to Previous Menu|(or Esc / q)"
)
local init_hdr="  ${YELLOW}Notice: WAN2GP Output & Batch Directories are not yet configured.${NC}\n  Before accessing WAN2GP operations, you must configure directory paths.\n"
while ! is_wan2gp_configured; do
run_interactive_submenu "WAN2GP DIRECTORY CONFIGURATION" "$init_hdr" init_opts 0
case "$REPLY" in
1) configure_wan2gp_directories ;;
0|[qQ]|[eE][xX][iI][tT]|ESC) return 0 ;;
*) echo -e "${RED}Invalid selection.${NC}"; sleep 1 ;;
esac
done

local w_opts=(
"SECTION|SERVER ENGINE CONTROL|"
"1|Start in Profile 2 (High Speed)|(2B Models & VRAM-Resident - New Tab/Window)"
"2|Start in Profile 4.5 (Low VRAM)|(14B Models Offload - New Tab/Window)"
"3|Stop Running WAN2GP Server|(Kill wgp.py server process)"
"4|Restart in Profile 2|(High Speed / 2B Models)"
"5|Restart in Profile 4.5|(Low VRAM / 14B Models)"
"6|View Detailed Status & Memory Usage|(wgp status)"
"7|Clear WAN2GP Logs|(clear-wan2gp-logs.sh)"
"SECTION|FLUX 2 KLEIN 9B IMAGE BATCH|"
"8|Run Flux 2 Klein 9B Image Processor|[Single Control Image]"
"9|Run Flux 2 Klein 9B Image Processor|[Multi-Control Images] (All in CTRL_IMAGE)"
"10|Run Flux 2 Klein 9B in Watch Mode|[Single Control Image]"
"11|Run Flux 2 Klein 9B in Watch Mode|[Multi-Control Images]"
"SECTION|LTX VIDEO GENERATION & LORA BATCH|"
"12|Run LTX Video 2B Batch Video Processor|[Single Control Video] (CTRL_VIDEO)"
"13|Run LTX Video 2B Batch Video Processor|[Pure Image-to-Video] (No Control Video)"
"14|Run LTX Video 2B in Watch Mode|[Single Control Video]"
"15|Run LTX Video 2B in Watch Mode|[Pure Image-to-Video]"
"16|Run LTX Video 13B Batch Video Processor|[Single Control Video] (CTRL_VIDEO)"
"17|Run LTX Video 13B Batch Video Processor|[Pure Image-to-Video] (No Control Video)"
"18|Run LTX Video 13B in Watch Mode|[Single Control Video]"
"19|Run LTX Video 13B in Watch Mode|[Pure Image-to-Video]"
"20|Run LTX-2 2.5 22B Batch Processor|[EditAnything v2 LoRA]"
"21|Run LTX-2 2.5 22B Batch Processor|[BFS Head Swap IC-LoRA]"
"22|Run LTX-2 2.5 22B Batch Processor|[Deblur & Decompression LoRAs]"
"23|Run LTX-2 2.5 22B Batch Processor|[Clean Base / Video+Audio]"
"SECTION|INFINITE TALKER & AUDIO / IMAGE UTILITIES|"
"24|Scan & Remove Byte-for-Byte Duplicate Images|(remove_duplicate_images.py)"
"25|Text to Speech (TTS) Batch Converter & Audio Player|(wan2gp_tts_batch.py)"
"26|Run MP Infinite Talker Batch|[Stephen Hawking / Control Image]"
"27|Run MP Infinite Talker in Watch Mode|[Auto-process incoming inputs]"
"28|Generate Single Infinite Talk Video|[Interactive Prompt / Text / Audio]"
"29|Infinite Talk Voice Manager|[Edge-TTS, Custom Voices & Stephen Hawking]"
"30|MP Video Image Directory Output Monitor|(FLUX / LTX / WAN2GP)"
"SECTION|CONFIGURATION & UPDATES|"
"31|Update WAN2GP Server to Latest Upstream Release|(Git Rebase + uv pip)"
"32|Configure / Change Output & Batch Directory Paths|(Outputs, Flux, LTX, InfTalk)"
"SEP|SEP|"
"0|Return to Previous Menu|(or Esc / q / 33)"
)

while true; do
local wgp_pids flux_pids ltx_pids inftlk_pids dup_pids
wgp_pids=$(pgrep -f "python.*wgp\.py" 2>/dev/null | tr '\n' ' ' || true)
flux_pids=$(pgrep -f "wan2gp_flux_batch" 2>/dev/null | tr '\n' ' ' || true)
ltx_pids=$(pgrep -f "wan2gp_ltx.*batch" 2>/dev/null | tr '\n' ' ' || true)
inftlk_pids=$(pgrep -f "MP_Infinite_Talker" 2>/dev/null | tr '\n' ' ' || true)
dup_pids=$(pgrep -f "remove_duplicate_images\.py" 2>/dev/null | tr '\n' ' ' || true)

local wgp_st="${RED}○ STOPPED${NC}"
[ -n "$wgp_pids" ] && wgp_st="${GREEN}● RUNNING${NC} (PID: ${wgp_pids% })"
local flux_st="${RED}○ STOPPED${NC}"
[ -n "$flux_pids" ] && flux_st="${GREEN}● RUNNING${NC} (PID: ${flux_pids% })"
local ltx_st="${RED}○ STOPPED${NC}"
[ -n "$ltx_pids" ] && ltx_st="${GREEN}● RUNNING${NC} (PID: ${ltx_pids% })"
local inftlk_st="${RED}○ STOPPED${NC}"
[ -n "$inftlk_pids" ] && inftlk_st="${GREEN}● RUNNING${NC} (PID: ${inftlk_pids% })"

local inftlk_info=""
local inftlk_d="${WAN2GP_INFTLKBATCH_DIR:-/run/media/mplanetarian/GAMES1/DATA_DRIVE_MOVED/WAN2GP_INFTLKBATCH}"
if [ -d "$inftlk_d" ]; then
shopt -s nullglob nocaseglob
local inftlk_inputs=("$inftlk_d"/*.wav "$inftlk_d"/*.mp3 "$inftlk_d"/*.flac "$inftlk_d"/*.m4a "$inftlk_d"/*.ogg "$inftlk_d"/*.txt)
shopt -u nullglob nocaseglob
local inftlk_ctrl="${inftlk_d}/CTRL_IMAGE/Stephen_Hawking.png"
local ctrl_st="${YELLOW}Custom${NC}"
[ -f "$inftlk_ctrl" ] && ctrl_st="${GREEN}Stephen_Hawking.png${NC}"
inftlk_info="  InfTalk Batch:       ${BOLD}${CYAN}${#inftlk_inputs[@]} pending input(s)${NC} | Avatar: ${ctrl_st}\n"
fi

local ltx_info=""
local ltx_ctrl_dir="${WAN2GP_LTX_BATCH_DIR:-/run/media/mplanetarian/GAMES1/DATA_DRIVE_MOVED/WAN2GP_LTX_BATCH}/CTRL_VIDEO"
[ ! -d "$ltx_ctrl_dir" ] && ltx_ctrl_dir="/run/media/mplanetarian/DATA/WAN2GP_LTX_BATCH/CTRL_VIDEO"
if [ -d "$ltx_ctrl_dir" ]; then
shopt -s nullglob nocaseglob
local ltx_ctrl_vids=("$ltx_ctrl_dir"/*.mp4 "$ltx_ctrl_dir"/*.mov "$ltx_ctrl_dir"/*.avi "$ltx_ctrl_dir"/*.mkv "$ltx_ctrl_dir"/*.webm)
shopt -u nullglob nocaseglob
if [ ${#ltx_ctrl_vids[@]} -gt 0 ]; then
ltx_info="  LTX Control Video:   ${BOLD}${YELLOW}${#ltx_ctrl_vids[@]} video(s) detected in CTRL_VIDEO${NC}\n"
fi
fi

local dup_info=""
[ -n "$dup_pids" ] && dup_info="  Duplicate Cleaner:   ${BOLD}${GREEN}● RUNNING${NC} (PID: ${dup_pids% })\n"

local tts_info=""
local tts_dir="${WAN2GP_TTSBATCH_DIR:-$(dirname "$WAN2GP_OUTPUTS")/WAN2GP_TTSBATCH}"
[ ! -d "$tts_dir" ] && tts_dir="/run/media/mplanetarian/GAMES1/DATA_DRIVE_MOVED/WAN2GP_TTSBATCH"
[ ! -d "$tts_dir" ] && tts_dir="/run/media/mplanetarian/DATA/WAN2GP_TTSBATCH"
if [ -d "$tts_dir" ]; then
shopt -s nullglob
local tts_txts=("$tts_dir"/*.txt)
local tts_wavs=("$tts_dir"/TTS_CONVERTED/*.wav)
shopt -u nullglob
tts_info="  TTS Batch:           ${BOLD}${CYAN}${#tts_txts[@]} .txt pending${NC} | ${BOLD}${GREEN}${#tts_wavs[@]} audio converted in TTS_CONVERTED${NC}\n"
fi

local hdr="  Outputs Dir:         ${BOLD}${CYAN}${WAN2GP_OUTPUTS}${NC}\n  Flux Batch Dir:      ${BOLD}${CYAN}${WAN2GP_FLUX_BATCH_DIR}${NC}\n  LTX Batch Dir:       ${BOLD}${CYAN}${WAN2GP_LTX_BATCH_DIR}${NC}\n  Server Status:       ${wgp_st} | Flux: ${flux_st}\n  LTX Video Batch:     ${ltx_st} | InfTalk: ${inftlk_st}\n${inftlk_info}${ltx_info}${dup_info}${tts_info}"

run_interactive_submenu "WAN2GP AI VIDEO & IMAGE WORKSTATION SUITE" "$hdr" w_opts 0
case "$REPLY" in
1)
if [ -n "$wgp_pids" ]; then
echo -e "\n${YELLOW}WAN2GP is already running (PID: $wgp_pids). Stop or restart it first.${NC}"
sleep 2
else
echo -e "\n${GREEN}Launching WAN2GP in Profile 2...${NC}"
launch_wan2gp_terminal "2"
fi
;;
2)
if [ -n "$wgp_pids" ]; then
echo -e "\n${YELLOW}WAN2GP is already running (PID: $wgp_pids). Stop or restart it first.${NC}"
sleep 2
else
echo -e "\n${YELLOW}Launching WAN2GP in Profile 4.5...${NC}"
launch_wan2gp_terminal "4.5"
fi
;;
3)
echo -e "\n${YELLOW}Stopping WAN2GP...${NC}"
run_sub_script "wan2gp.sh" stop
press_enter
;;
4)
echo -e "\n${YELLOW}Stopping existing WAN2GP instance...${NC}"
run_sub_script "wan2gp.sh" stop
sleep 1
echo -e "${GREEN}Restarting WAN2GP in Profile 2...${NC}"
launch_wan2gp_terminal "2"
;;
5)
echo -e "\n${YELLOW}Stopping existing WAN2GP instance...${NC}"
run_sub_script "wan2gp.sh" stop
sleep 1
echo -e "${YELLOW}Restarting WAN2GP in Profile 4.5...${NC}"
launch_wan2gp_terminal "4.5"
;;
6)
echo -e "\n${BOLD}${BLUE}=== WAN2GP STATUS ===${NC}\n"
run_sub_script "wan2gp.sh" status
press_enter
;;
7)
clear_wan2gp_logs
;;
8)
echo -e "\n${GREEN}Launching Flux 2 Klein 9B Batch Image Processor (Single Control)...${NC}"
launch_wan2gp_flux_batch_terminal "--single-control"
;;
9)
echo -e "\n${GREEN}Launching Flux 2 Klein 9B Batch Image Processor (Multi-Control Images)...${NC}"
launch_wan2gp_flux_batch_terminal "--multi-control"
;;
10)
echo -e "\n${GREEN}Launching Flux 2 Klein 9B in Watch Mode (Single Control)...${NC}"
launch_wan2gp_flux_batch_terminal "--watch --single-control"
;;
11)
echo -e "\n${GREEN}Launching Flux 2 Klein 9B in Watch Mode (Multi-Control Images)...${NC}"
launch_wan2gp_flux_batch_terminal "--watch --multi-control"
;;
12)
echo -e "\n${GREEN}Launching LTX Video 2B Batch Video Processor (Single Control Video)...${NC}"
launch_wan2gp_ltx_batch_terminal "" "2b"
;;
13)
echo -e "\n${GREEN}Launching LTX Video 2B Batch Video Processor (Pure Image-to-Video)...${NC}"
launch_wan2gp_ltx_batch_terminal "--no-control" "2b"
;;
14)
echo -e "\n${GREEN}Launching LTX Video 2B in Watch Mode (Single Control Video)...${NC}"
launch_wan2gp_ltx_batch_terminal "--watch" "2b"
;;
15)
echo -e "\n${GREEN}Launching LTX Video 2B in Watch Mode (Pure Image-to-Video)...${NC}"
launch_wan2gp_ltx_batch_terminal "--watch --no-control" "2b"
;;
16)
echo -e "\n${GREEN}Launching LTX Video 13B Batch Video Processor (Single Control Video)...${NC}"
launch_wan2gp_ltx_batch_terminal "" "13b"
;;
17)
echo -e "\n${GREEN}Launching LTX Video 13B Batch Video Processor (Pure Image-to-Video)...${NC}"
launch_wan2gp_ltx_batch_terminal "--no-control" "13b"
;;
18)
echo -e "\n${GREEN}Launching LTX Video 13B in Watch Mode (Single Control Video)...${NC}"
launch_wan2gp_ltx_batch_terminal "--watch" "13b"
;;
19)
echo -e "\n${GREEN}Launching LTX Video 13B in Watch Mode (Pure Image-to-Video)...${NC}"
launch_wan2gp_ltx_batch_terminal "--watch --no-control" "13b"
;;
20)
echo -e "\n${GREEN}Launching LTX-2 2.5 22B Batch Processor with EditAnything v2 LoRA...${NC}"
launch_wan2gp_ltx_batch_terminal "" "25_22b" "editanything_v2"
;;
21)
echo -e "\n${GREEN}Launching LTX-2 2.5 22B Batch Processor with BFS Head Swap IC-LoRA...${NC}"
launch_wan2gp_ltx_batch_terminal "" "25_22b" "bfs_head_swap"
;;
22)
echo -e "\n${GREEN}Launching LTX-2 2.5 22B Batch Processor with Deblur LoRA...${NC}"
launch_wan2gp_ltx_batch_terminal "" "25_22b" "deblur"
;;
23)
echo -e "\n${GREEN}Launching LTX-2 2.5 22B Batch Processor (Clean Base / Video+Audio)...${NC}"
launch_wan2gp_ltx_batch_terminal "" "25_22b" "none"
;;
24)
run_duplicate_image_remover
;;
25)
run_wan2gp_tts_batch
;;
26)
echo -e "\n${GREEN}Launching MP Infinite Talker Batch (Stephen Hawking)...${NC}"
launch_wan2gp_inftlk_batch_terminal ""
;;
27)
echo -e "\n${GREEN}Launching MP Infinite Talker in Watch Mode...${NC}"
launch_wan2gp_inftlk_batch_terminal "--watch"
;;
28)
run_wan2gp_infinite_talker
;;
29)
run_wan2gp_infinite_talker --list-voices
press_enter
;;
30|monitor|output-monitor)
run_wan2gp_output_monitor
;;
31|[uU]|update)
echo -e "\n${BOLD}${MAGENTA}==================================================${NC}\n${BOLD}${MAGENTA}       UPDATE WAN2GP TO LATEST RELEASE            ${NC}\n${BOLD}${MAGENTA}==================================================${NC}\n"
read -r -p "Proceed with updating WAN2GP from upstream git repository? [Y/n]: " _up_confirm
if [[ -z "$_up_confirm" || "$_up_confirm" =~ ^[Yy]$ ]]; then
run_sub_script "wan2gp.sh" update
else
echo -e "\n${YELLOW}Update cancelled.${NC}"
fi
press_enter
;;
32|[cC]|config|dirs)
configure_wan2gp_directories
;;
0|33|[qQ]|[eE][xX][iI][tT]|ESC)
return 0
;;
*)
echo -e "\n${RED}Invalid option!${NC}"
sleep 1.2
;;
esac
done
}
manage_beszel() {
if [ $# -gt 0 ]; then run_sub_script "beszel.sh" "$@"; return; fi
local b_opts=(
"SECTION|SERVICES CONTROL|"
"1|Start Beszel Monitoring Hub & Local Agent|(Background Services)"
"2|Start Beszel Monitoring Hub Only|(Web Dashboard :8090)"
"3|Start Beszel Agent Only|(Hardware & GPU Telemetry Reporter)"
"SECTION|BROWSER ACCESS|"
"4|Open Beszel Web Dashboard in Browser|(http://localhost:8090)"
"SECTION|STOP & RESTART|"
"5|Stop Beszel Hub & Agent Services|(Kill running instances)"
"6|Stop Beszel Hub Only|(Stop Web Dashboard)"
"7|Stop Beszel Agent Only|(Stop Telemetry Reporter)"
"8|Restart Beszel Hub & Agent Services|(Clean restart all)"
"SECTION|DIAGNOSTICS & LOGS|"
"9|View Beszel Server Log Files|(beszel-hub.log & agent.log)"
"10|View Beszel Detailed Service Status|(PIDs, Ports, Systemd / Podman)"
"SEP|SEP|"
"0|Return to Previous Menu|(or Esc / q)"
)
while true; do
local hub_pids agent_pids
hub_pids=$(pgrep -f "beszel.*hub" 2>/dev/null | tr '\n' ' ' || true)
agent_pids=$(pgrep -f "beszel.*agent" 2>/dev/null | tr '\n' ' ' || true)
local h_st="${RED}○ STOPPED${NC}"
[ -n "$hub_pids" ] && h_st="${GREEN}● RUNNING${NC} (PID: ${hub_pids% })"
local a_st="${RED}○ STOPPED${NC}"
[ -n "$agent_pids" ] && a_st="${GREEN}● RUNNING${NC} (PID: ${agent_pids% })"
local hdr="  Beszel Hub (Port 8090):    ${h_st}\n  Beszel Agent (Port 45876): ${a_st}\n"
run_interactive_submenu "BESZEL WORKSTATION & GPU MONITORING SUITE" "$hdr" b_opts 0
case "$REPLY" in
1) run_sub_script "beszel.sh" start; press_enter ;;
2) run_sub_script "beszel.sh" start-hub; press_enter ;;
3) run_sub_script "beszel.sh" start-agent; press_enter ;;
4) run_sub_script "beszel.sh" open; press_enter ;;
5) run_sub_script "beszel.sh" stop; press_enter ;;
6) run_sub_script "beszel.sh" stop-hub; press_enter ;;
7) run_sub_script "beszel.sh" stop-agent; press_enter ;;
8) run_sub_script "beszel.sh" restart; press_enter ;;
9) run_sub_script "beszel.sh" logs; press_enter ;;
10) run_sub_script "beszel.sh" status; press_enter ;;
0|[qQ]|[eE][xX][iI][tT]|ESC) return 0 ;;
*) echo -e "\n${RED}Invalid option!${NC}"; sleep 1.2 ;;
esac
done
}
manage_ollama() {
if [ $# -gt 0 ]; then run_sub_script "manage_ollama.sh" "$@"; return; fi
local ol_opts=(
"SECTION|SERVER ENGINE CONTROL|"
"1|Start Ollama Server (Background Daemon)|[ollama serve / container]"
"2|Start Ollama Server in New Terminal Window|(Live output & logs)"
"3|Stop Running Ollama Server|(Kill serve daemon / container)"
"4|Restart Ollama Server|(Clean restart backend)"
"SECTION|INTERACTIVE CHAT & VOICE AI|"
"5|Chat with a Local Model|(Interactive CLI: Qwen, LLaMA, DeepSeek...)"
"6|Start Voice Chat with Local Models|(Matrix Cast: Morpheus, Smith, Neo, Trinity...)"
"7|View Archived Audio Responses & Transcripts|(MP Harmony & Voice AI Archive)"
"SECTION|DIAGNOSTICS & LOGS|"
"8|View Server Log File|(ollama-serve.log)"
"9|View Detailed Status & Models|(run_sub_script manage_ollama.sh status)"
"SEP|SEP|"
"0|Return to Previous Menu|(or Esc / q)"
)
while true; do
local st_str="${RED}○ STOPPED${NC}"
local pids=""
if [ "$OS_TYPE" = "windows" ]; then
if command -v tasklist.exe &>/dev/null && tasklist.exe //FI "IMAGENAME eq ollama.exe" 2>/dev/null | grep -qi "ollama.exe"; then
st_str="${GREEN}● RUNNING${NC}"
fi
elif curl -s --connect-timeout 1 "http://127.0.0.1:11434/" 2>/dev/null | grep -qi "Ollama is running"; then
pids=$(pgrep -f "ollama serve" 2>/dev/null | tr '\n' ' ' || true)
st_str="${GREEN}● RUNNING${NC}${pids:+ (PID: ${pids% })}"
elif pgrep -f "ollama serve" &>/dev/null; then
pids=$(pgrep -f "ollama serve" 2>/dev/null | tr '\n' ' ' || true)
st_str="${GREEN}● RUNNING${NC}${pids:+ (PID: ${pids% })}"
fi
local hdr="  Server Status:  ${st_str}\n  Endpoint:       ${CYAN}http://127.0.0.1:11434${NC}\n"
run_interactive_submenu "OLLAMA LOCAL LLM SERVER MANAGER" "$hdr" ol_opts 0
case "$REPLY" in
1) run_sub_script "manage_ollama.sh" start; press_enter ;;
2) run_sub_script "manage_ollama.sh" start-window; press_enter ;;
3) run_sub_script "manage_ollama.sh" stop; press_enter ;;
4) run_sub_script "manage_ollama.sh" restart; press_enter ;;
5) run_sub_script "manage_ollama.sh" chat ;;
6) run_sub_script "manage_ollama.sh" voice ;;
7) run_sub_script "manage_ollama.sh" audio; press_enter ;;
8) run_sub_script "manage_ollama.sh" logs; press_enter ;;
9) run_sub_script "manage_ollama.sh" status; press_enter ;;
0|[qQ]|[eE][xX][iI][tT]|ESC) return 0 ;;
*) echo -e "\n${RED}Invalid option!${NC}"; sleep 1.2 ;;
esac
done
}
manage_open_webui() {
if [ $# -gt 0 ]; then run_sub_script "manage_open_webui.sh" "$@"; return; fi
local ow_opts=(
"SECTION|BROWSER ACCESS|"
"1|Open in Web Browser|(http://localhost:42004 or http://localhost:8080)"
"SECTION|SERVICE CONTROLS|"
"2|Start Server|(start_openwebui.bat / conda env daemon)"
"3|Stop Server|(taskkill / stop webui backend)"
"4|Restart Server|(Clean restart backend)"
"SECTION|MAINTENANCE & LOGS|"
"5|View Server Logs / Console Output|(open-webui.log)"
"6|Check / Install Open WebUI Updates|(pip / git pull)"
"SEP|SEP|"
"0|Return to Previous Menu|(or Esc / q)"
)
while true; do
local port="42004"
[ "$OS_TYPE" = "windows" ] && port="8080"
local st_str="${RED}○ STOPPED${NC}"
local pids=""
if curl -s --connect-timeout 1 "http://127.0.0.1:${port}/" &>/dev/null; then
pids=$(pgrep -f "open-webui serve|open_webui" 2>/dev/null | tr '\n' ' ' || true)
st_str="${GREEN}● RUNNING${NC}${pids:+ (PID: ${pids% })}"
elif pgrep -f "open-webui serve|open_webui" &>/dev/null; then
pids=$(pgrep -f "open-webui serve|open_webui" 2>/dev/null | tr '\n' ' ' || true)
st_str="${GREEN}● RUNNING${NC}${pids:+ (PID: ${pids% })}"
fi
local hdr="  Server Status:  ${st_str}\n  Web Endpoint:   ${CYAN}http://localhost:${port}${NC}\n  Data Directory: ${CYAN}X:\\OPENWEBUI\\data${NC}\n"
run_interactive_submenu "OPEN WEBUI SERVER & WEB CHAT MANAGER" "$hdr" ow_opts 0
case "$REPLY" in
1) run_sub_script "manage_open_webui.sh" open; press_enter ;;
2) run_sub_script "manage_open_webui.sh" start; press_enter ;;
3) run_sub_script "manage_open_webui.sh" stop; press_enter ;;
4) run_sub_script "manage_open_webui.sh" restart; press_enter ;;
5) run_sub_script "manage_open_webui.sh" logs; press_enter ;;
6) run_sub_script "manage_open_webui.sh" update; press_enter ;;
0|[qQ]|[eE][xX][iI][tT]|ESC) return 0 ;;
*) echo -e "\n${RED}Invalid option!${NC}"; sleep 1.2 ;;
esac
done
}
manage_harmony_agent() {
if [ $# -gt 0 ]; then run_sub_script "manage_harmony_agent.sh" "$@"; return; fi
local ha_opts=(
"SECTION|INTERACTIVE CHAT & VOICE AI|"
"1|Launch Interactive Chat CLI with MP Harmony Agent|(Terminal Console)"
"2|Launch Voice Chat CLI with MP Harmony Agent|(Matrix Cast: Smith, Morpheus, Neo, Trinity, Oracle, Zion)"
"3|Launch Voice Chat with Ollama Models|(Matrix Cast Voice AI with Local Models)"
"SECTION|SERVER & VOICE BRIDGE (:11435)|"
"4|Start MP Harmony Voice Bridge / Server|(Background Daemon :11435)"
"5|Start MP Harmony Voice Bridge in New Window|(Live Logs & Interactive Audio)"
"6|Stop Running MP Harmony Agent / Server|(Kill server daemon)"
"7|Restart MP Harmony Agent / Server|(Clean restart backend)"
"SECTION|AUDIO ARCHIVE & LOGS|"
"8|View Archived Audio Responses & Transcripts|(MP Harmony Agent Speech Archive)"
"9|View Server Log File|(harmony-agent.log)"
"10|View Server Status & Diagnostic Details|(run_sub_script manage_harmony_agent.sh status)"
"SEP|SEP|"
"0|Return to Previous Menu|(or Esc / q)"
)
while true; do
local st_str="${RED}○ STOPPED${NC}"
local pids=""
if curl -s --connect-timeout 1 "http://127.0.0.1:11435/health" 2>/dev/null | grep -qi "ok"; then
pids=$(pgrep -f "harmony.*agent|harmony_bridge" 2>/dev/null | tr '\n' ' ' || true)
st_str="${GREEN}● RUNNING${NC}${pids:+ (PID: ${pids% })}"
elif pgrep -f "harmony.*agent|harmony_bridge" &>/dev/null; then
pids=$(pgrep -f "harmony.*agent|harmony_bridge" 2>/dev/null | tr '\n' ' ' || true)
st_str="${GREEN}● RUNNING${NC}${pids:+ (PID: ${pids% })}"
fi
local hdr="  Server Status:  ${st_str}\n  Endpoint:       ${CYAN}http://127.0.0.1:11435${NC}\n"
run_interactive_submenu "MP HARMONY AI AGENT & VOICE BRIDGE (:11435)" "$hdr" ha_opts 0
case "$REPLY" in
1) run_sub_script "manage_harmony_agent.sh" chat ;;
2) run_sub_script "manage_harmony_agent.sh" voice ;;
3) run_sub_script "manage_harmony_agent.sh" ollama-voice ;;
4) run_sub_script "manage_harmony_agent.sh" start; press_enter ;;
5) run_sub_script "manage_harmony_agent.sh" start-window; press_enter ;;
6) run_sub_script "manage_harmony_agent.sh" stop; press_enter ;;
7) run_sub_script "manage_harmony_agent.sh" restart; press_enter ;;
8) run_sub_script "manage_harmony_agent.sh" audio; press_enter ;;
9) run_sub_script "manage_harmony_agent.sh" logs; press_enter ;;
10) run_sub_script "manage_harmony_agent.sh" status; press_enter ;;
0|[qQ]|[eE][xX][iI][tT]|ESC) return 0 ;;
*) echo -e "\n${RED}Invalid option!${NC}"; sleep 1.2 ;;
esac
done
}
manage_dsh_mobile() {
if [ $# -gt 0 ]; then run_sub_script "dsh_mobile.sh" "$@"; return; fi
local dsh_opts=(
"SECTION|SERVER LAUNCHERS|"
"1|Launch dsh-mobile in Terminal Window / Tab|(Standard live server)"
"2|Launch dsh-mobile in Background Daemon|(Log output to file)"
"SECTION|BROWSER & CONTROLS|"
"3|Open dsh-mobile Web UI in Browser|(http://192.168.1.11:3080)"
"4|Stop Running dsh-mobile Server|(Kill server process)"
"5|Restart dsh-mobile Server|(Clean restart backend)"
"SECTION|DIAGNOSTICS & LOGS|"
"6|View Server Log File|(dsh-mobile.log)"
"7|View Server Status & Diagnostic Details|(run_sub_script dsh_mobile.sh status)"
"SEP|SEP|"
"0|Return to Previous Menu|(or Esc / q)"
)
while true; do
local st_str="${RED}○ STOPPED${NC}"
local pids=""
if curl -s --connect-timeout 1 "http://127.0.0.1:3080/" &>/dev/null; then
pids=$(pgrep -f "dsh-mobile|dsh_server" 2>/dev/null | tr '\n' ' ' || true)
st_str="${GREEN}● RUNNING${NC}${pids:+ (PID: ${pids% })}"
elif pgrep -f "dsh-mobile|dsh_server" &>/dev/null; then
pids=$(pgrep -f "dsh-mobile|dsh_server" 2>/dev/null | tr '\n' ' ' || true)
st_str="${GREEN}● RUNNING${NC}${pids:+ (PID: ${pids% })}"
fi
local hdr="  Server Status:  ${st_str}\n  Web UI URL:     ${CYAN}http://192.168.1.11:3080${NC}\n"
run_interactive_submenu "DEEPSEEK HARNESS (DSH-MOBILE) SERVER MANAGER" "$hdr" dsh_opts 0
case "$REPLY" in
1) run_sub_script "dsh_mobile.sh" start; press_enter ;;
2) run_sub_script "dsh_mobile.sh" start-bg; press_enter ;;
3) run_sub_script "dsh_mobile.sh" web; press_enter ;;
4) run_sub_script "dsh_mobile.sh" stop; press_enter ;;
5) run_sub_script "dsh_mobile.sh" restart; press_enter ;;
6) run_sub_script "dsh_mobile.sh" logs; press_enter ;;
7) run_sub_script "dsh_mobile.sh" status; press_enter ;;
0|[qQ]|[eE][xX][iI][tT]|ESC) return 0 ;;
*) echo -e "\n${RED}Invalid option!${NC}"; sleep 1.2 ;;
esac
done
}
launch_dsh_mobile() {
run_sub_script "dsh_mobile.sh" start
}
_control_net_service() {
local action="$1"; local target="$2"; if command -v systemctl &>/dev/null; then case "$target" in all) sudo systemctl "$action" sshd smb nmb wsdd vsftpd 2>/dev/null || true ;; ssh) sudo systemctl "$action" sshd ;; smb) sudo systemctl "$action" smb nmb wsdd ;; ftp) sudo systemctl "$action" vsftpd ;; esac; elif [ "$OS_TYPE" = "freebsd" ] || command -v service &>/dev/null; then case "$target" in all) sudo service sshd "$action" 2>/dev/null || true; sudo service samba_server "$action" 2>/dev/null || sudo service smbd "$action" 2>/dev/null || true; sudo service vsftpd "$action" 2>/dev/null || sudo service ftpd "$action" 2>/dev/null || true ;; ssh) sudo service sshd "$action" 2>/dev/null || true ;; smb) sudo service samba_server "$action" 2>/dev/null || sudo service smbd "$action" 2>/dev/null || true ;; ftp) sudo service vsftpd "$action" 2>/dev/null || sudo service ftpd "$action" 2>/dev/null || true ;; esac; elif [ "$OS_TYPE" = "macos" ]; then case "$target" in all) sudo systemsetup -setremotelogin "$([ "$action" = "stop" ] && echo "off" || echo "on")" 2>/dev/null || true; if [ "$action" = "start" ]; then sudo launchctl load -w /System/Library/LaunchDaemons/com.apple.smbd.plist 2>/dev/null || true; elif [ "$action" = "stop" ]; then sudo launchctl unload -w /System/Library/LaunchDaemons/com.apple.smbd.plist 2>/dev/null || true; fi ;; ssh) if [ "$action" = "start" ]; then sudo systemsetup -setremotelogin on 2>/dev/null || sudo launchctl load -w /System/Library/LaunchDaemons/ssh.plist 2>/dev/null; elif [ "$action" = "stop" ]; then sudo systemsetup -setremotelogin off 2>/dev/null || sudo launchctl unload -w /System/Library/LaunchDaemons/ssh.plist 2>/dev/null; else sudo launchctl stop com.openssh.sshd 2>/dev/null; sudo launchctl start com.openssh.sshd 2>/dev/null; fi; ;; smb) if [ "$action" = "start" ]; then sudo launchctl load -w /System/Library/LaunchDaemons/com.apple.smbd.plist 2>/dev/null; elif [ "$action" = "stop" ]; then sudo launchctl unload -w /System/Library/LaunchDaemons/com.apple.smbd.plist 2>/dev/null; else sudo launchctl unload -w /System/Library/LaunchDaemons/com.apple.smbd.plist 2>/dev/null; sleep 0.5; sudo launchctl load -w /System/Library/LaunchDaemons/com.apple.smbd.plist 2>/dev/null; fi ;; ftp) echo -e "${YELLOW}macOS does not provide a built-in FTP daemon in modern versions.${NC}"; ;; esac; elif [ "$OS_TYPE" = "windows" ] || [ "$OS_TYPE" = "wsl" ]; then if command -v powershell.exe &>/dev/null; then local ps_action="Start-Service"; [ "$action" = "stop" ] && ps_action="Stop-Service"; [ "$action" = "restart" ] && ps_action="Restart-Service"; case "$target" in all) powershell.exe -NoProfile -Command "$ps_action -Name 'sshd','LanmanServer' -ErrorAction SilentlyContinue" 2>/dev/null || true ;; ssh) powershell.exe -NoProfile -Command "$ps_action -Name 'sshd' -ErrorAction SilentlyContinue" 2>/dev/null || true ;; smb) powershell.exe -NoProfile -Command "$ps_action -Name 'LanmanServer' -ErrorAction SilentlyContinue" 2>/dev/null || true ;; ftp) powershell.exe -NoProfile -Command "$ps_action -Name 'ftpsvc' -ErrorAction SilentlyContinue" 2>/dev/null || true ;; esac; else echo -e "${YELLOW}Please manage Windows Services using services.msc.${NC}"; fi; else echo -e "${RED}No supported service manager found (systemctl or service).${NC}"; fi
}
manage_network_services() {
while true; do clear; echo -e "${BOLD}${MAGENTA}==================================================${NC}\n${BOLD}${MAGENTA}          NETWORK SERVICES MANAGER                ${NC}\n${BOLD}${MAGENTA}       (SSH, Samba File Sharing, vsftpd FTP)      ${NC}\n${BOLD}${MAGENTA}==================================================${NC}"; echo ""; local ssh_status="${BOLD}${RED}○ STOPPED${NC}"; if (command -v systemctl &>/dev/null && systemctl is-active --quiet sshd 2>/dev/null) || pgrep -x sshd >/dev/null; then local ssh_pids; ssh_pids=$(pgrep -x sshd | tr '\n' ' '); ssh_status="${BOLD}${GREEN}● RUNNING${NC} (Port 22, PID: ${ssh_pids})"; fi; local smb_status="${BOLD}${RED}○ STOPPED${NC}"; if (command -v systemctl &>/dev/null && systemctl is-active --quiet smb 2>/dev/null) || pgrep -x smbd >/dev/null; then local smb_pids; smb_pids=$(pgrep -x smbd | tr '\n' ' '); smb_status="${BOLD}${GREEN}● RUNNING${NC} (Ports 139, 445, PID: ${smb_pids})"; fi; local ftp_status="${BOLD}${RED}○ STOPPED${NC}"; if (command -v systemctl &>/dev/null && systemctl is-active --quiet vsftpd 2>/dev/null) || pgrep -x vsftpd >/dev/null || pgrep -x ftpd >/dev/null; then local ftp_pids; ftp_pids=$( (pgrep -x vsftpd 2>/dev/null || pgrep -x ftpd 2>/dev/null) | tr '\n' ' '); ftp_status="${BOLD}${GREEN}● RUNNING${NC} (Port 21, PID: ${ftp_pids})"; fi; echo -e "  SSH Server (sshd):          ${ssh_status}\n  Samba Share (smbd/wsdd):    ${smb_status}\n  FTP Server (vsftpd/ftpd):   ${ftp_status}"; echo ""; echo -e "${BOLD}Bulk Actions (All Services):${NC}\n  ${BOLD}${CYAN}1)${NC} ${GREEN}Start All Services${NC}   (SSH, SMB, FTP)\n  ${BOLD}${CYAN}2)${NC} ${RED}Stop All Services${NC}    (SSH, SMB, FTP)\n  ${BOLD}${CYAN}3)${NC} ${YELLOW}Restart All Services${NC} (SSH, SMB, FTP)"; echo ""; echo -e "${BOLD}Individual Service Controls:${NC}\n  ${BOLD}${CYAN}4)${NC} Start SSH               ${BOLD}${CYAN}7)${NC} Start Samba (SMB)        ${BOLD}${CYAN}10)${NC} Start FTP\n  ${BOLD}${CYAN}5)${NC} Stop SSH                ${BOLD}${CYAN}8)${NC} Stop Samba (SMB)         ${BOLD}${CYAN}11)${NC} Stop FTP\n  ${BOLD}${CYAN}6)${NC} Restart SSH             ${BOLD}${CYAN}9)${NC} Restart Samba (SMB)      ${BOLD}${CYAN}12)${NC} Restart FTP"; echo ""; echo -e "  ${BOLD}${CYAN}13)${NC} View Detailed Service Status\n  ${BOLD}${CYAN}14)${NC} Return to Main Menu"; echo ""; read -r -p "Enter choice [1-14]: " s_choice; case $s_choice in 1) echo -e "\n${BOLD}${GREEN}Starting all network services (SSH, SMB, FTP)...${NC}\n"; _control_net_service "start" "all"; sleep 1; press_enter ;; 2) echo -e "\n${BOLD}${RED}Stopping all network services (SSH, SMB, FTP)...${NC}\n"; _control_net_service "stop" "all"; sleep 1; press_enter ;; 3) echo -e "\n${BOLD}${YELLOW}Restarting all network services (SSH, SMB, FTP)...${NC}\n"; _control_net_service "restart" "all"; sleep 1; press_enter ;; 4) echo -e "\n${BOLD}${GREEN}Starting SSH Server (sshd)...${NC}\n"; _control_net_service "start" "ssh"; sleep 1; press_enter ;; 5) echo -e "\n${BOLD}${RED}Stopping SSH Server (sshd)...${NC}\n"; _control_net_service "stop" "ssh"; sleep 1; press_enter ;; 6) echo -e "\n${BOLD}${YELLOW}Restarting SSH Server (sshd)...${NC}\n"
_control_net_service "restart" "ssh"; sleep 1; press_enter ;; 7) echo -e "\n${BOLD}${GREEN}Starting Samba Server (smb, nmb, wsdd)...${NC}\n"; _control_net_service "start" "smb"; sleep 1; press_enter ;; 8) echo -e "\n${BOLD}${RED}Stopping Samba Server (smb, nmb, wsdd)...${NC}\n"; _control_net_service "stop" "smb"; sleep 1; press_enter ;; 9) echo -e "\n${BOLD}${YELLOW}Restarting Samba Server (smb, nmb, wsdd)...${NC}\n"; _control_net_service "restart" "smb"; sleep 1; press_enter ;; 10) echo -e "\n${BOLD}${GREEN}Starting FTP Server (vsftpd)...${NC}\n"; _control_net_service "start" "ftp"; sleep 1; press_enter ;; 11) echo -e "\n${BOLD}${RED}Stopping FTP Server (vsftpd)...${NC}\n"; _control_net_service "stop" "ftp"; sleep 1; press_enter ;; 12) echo -e "\n${BOLD}${YELLOW}Restarting FTP Server (vsftpd)...${NC}\n"; _control_net_service "restart" "ftp"; sleep 1; press_enter ;; 13) echo -e "\n${BOLD}${BLUE}=== DETAILED NETWORK SERVICES STATUS ===${NC}\n"; if command -v systemctl &>/dev/null; then systemctl status sshd smb wsdd vsftpd --no-pager -l; elif [ "$OS_TYPE" = "freebsd" ] || command -v service &>/dev/null; then echo -e "${CYAN}--- SSH Server ---${NC}"; service sshd status 2>/dev/null || true; echo -e "\n${CYAN}--- Samba File Sharing ---${NC}"; service samba_server status 2>/dev/null || service smbd status 2>/dev/null || true; echo -e "\n${CYAN}--- FTP Server ---${NC}"; service vsftpd status 2>/dev/null || service ftpd status 2>/dev/null || true; elif [ "$OS_TYPE" = "macos" ]; then echo -e "${CYAN}--- SSH Server ---${NC}"; sudo systemsetup -getremotelogin 2>/dev/null || launchctl list | grep ssh || true; echo -e "\n${CYAN}--- Samba File Sharing ---${NC}"; launchctl list | grep smbd || true; elif [ "$OS_TYPE" = "windows" ] || [ "$OS_TYPE" = "wsl" ]; then if command -v powershell.exe &>/dev/null; then powershell.exe -NoProfile -Command "Get-Service -Name 'sshd','LanmanServer','ftpsvc' -ErrorAction SilentlyContinue | Format-Table -AutoSize" 2>/dev/null || true; fi; fi; echo ""; press_enter ;; 14) return 0; ;; *) echo -e "\n${RED}Invalid option!${NC}"; sleep 1.5; ;; esac; done
}
launch_system_process_monitor() {
local refresh="${1:-10}"; local mon="$SCRIPT_DIR/scripts/MP_Monitor_Bash.sh"; [ ! -f "$mon" ] && mon="$SCRIPT_DIR/MP_Monitor_Bash.sh"; if [ ! -f "$mon" ]; then echo -e "\n${RED}Monitor script not found: MP_Monitor_Bash.sh${NC}"; press_enter; return 1; fi; local mon_q dir_q run_cmd; mon_q="$(printf '%q' "$mon")"; dir_q="$(printf '%q' "$SCRIPT_DIR")"; run_cmd="cd ${dir_q} && exec bash ${mon_q} --refresh ${refresh}"; echo -e "\n${BOLD}${GREEN}Opening Monitor System Processes and Bash Commands with System Info in a new terminal tab...${NC}\n"; if launch_in_terminal "Monitor System Processes and Bash Commands with System Info" "$run_cmd" "tab"; then echo -e "${GREEN}✓ Monitor is running in a new tab of this Terminal. This menu stays here.${NC}\n${DIM}Refresh interval: ${refresh}s. History log: ${SCRIPT_DIR}/running_history.log${NC}"; sleep 1.2; else echo -e "${YELLOW}No separate terminal tab was available. Running the monitor here. Ctrl+C returns to the menu.${NC}\n"; sleep 0.6; trap ':' INT; bash "$mon" --refresh "$refresh"; trap 'exit_mix_manager' INT; press_enter; fi
}
manage_process_and_bash_monitor() {
while true; do clear; echo -e "${BOLD}${MAGENTA}==================================================${NC}\n${BOLD}${MAGENTA} Monitor System Processes and Bash Commands with System Info ${NC}\n${BOLD}${MAGENTA}==================================================${NC}"; echo ""; echo -e "  ${DIM}macOS and Linux. Opens in a new tab of the terminal running Mix Manager.${NC}\n  ${DIM}Snapshots append to running_history.log and are never cleared.${NC}"; echo ""; echo -e "  ${BOLD}${CYAN}1)${NC} Launch monitor ${GREEN}(refresh every 10 seconds)${NC}\n  ${BOLD}${CYAN}2)${NC} Launch monitor ${GREEN}(refresh every 5 seconds)${NC}\n  ${BOLD}${CYAN}3)${NC} Launch monitor ${GREEN}(refresh every 2 seconds)${NC}\n  ${BOLD}${CYAN}4)${NC} Return"; echo ""; read -r -p "Enter choice [1-4]: " mon_choice; case "$mon_choice" in 1) launch_system_process_monitor 10 ;; 2) launch_system_process_monitor 5 ;; 3) launch_system_process_monitor 2 ;; 4|0|[qQ]|back) return 0 ;; *) echo -e "\n${RED}Invalid choice!${NC}"; sleep 1.2 ;; esac; done
}
manage_system_maintenance() {
while true; do clear; echo -e "${BOLD}${MAGENTA}==================================================${NC}"; if [ "$OS_TYPE" = "macos" ]; then echo -e "${BOLD}${MAGENTA}         macOS SYSTEM MAINTENANCE & CLEANUP       ${NC}"; elif [ "$OS_TYPE" = "windows" ] || [ "$OS_TYPE" = "wsl" ]; then echo -e "${BOLD}${MAGENTA}       WINDOWS 10/11 MAINTENANCE & CLEANUP        ${NC}"; elif [ "$OS_TYPE" = "freebsd" ]; then echo -e "${BOLD}${MAGENTA}        FreeBSD SYSTEM MAINTENANCE & CLEANUP      ${NC}"; else echo -e "${BOLD}${MAGENTA}           SYSTEM MAINTENANCE & CLEANUP           ${NC}"; fi; echo -e "${BOLD}${MAGENTA}==================================================${NC}"; echo ""; if [ "$OS_TYPE" = "macos" ]; then local brew_count="N/A"; local brew_formulae="N/A"; if command -v brew &>/dev/null; then brew_count=$(brew list --cask 2>/dev/null | wc -l | tr -d ' '); brew_formulae=$(brew list --formula 2>/dev/null | wc -l | tr -d ' '); echo -e "  Homebrew Packages Installed: ${CYAN}${brew_formulae} formulae, ${brew_count} casks${NC}"; fi; echo -e "  macOS Version:               ${GREEN}$(sw_vers -productVersion 2>/dev/null || uname -r)${NC}"; echo ""; echo -e "${BOLD}Select a maintenance operation:${NC}\n  ${BOLD}${CYAN}1)${NC} Check Drive Space Statistics (${GREEN}Get_All_Drive_Space.sh${NC}) [Mounted & Unmounted]\n  ${BOLD}${CYAN}2)${NC} Open macOS Software Update Window (${GREEN}System Settings / Software Update${NC})\n  ${BOLD}${CYAN}3)${NC} Clean Homebrew Caches & Old Packages (${GREEN}brew cleanup -s && brew autoremove${NC})\n  ${BOLD}${CYAN}4)${NC} Full Homebrew Package Upgrade (${GREEN}brew update && brew upgrade${NC})\n  ${BOLD}${CYAN}5)${NC} Purge Inactive System RAM Memory (${GREEN}sudo purge${NC})\n  ${BOLD}${CYAN}6)${NC} Clear User Caches & Temporary Files (${GREEN}rm -rf ~/Library/Caches/*${NC})\n  ${BOLD}${CYAN}7)${NC} ${BOLD}${YELLOW}Run Complete macOS Maintenance Suite${NC}\n  ${BOLD}${CYAN}8)${NC} Monitor System Processes and Bash Commands with System Info ${GREEN}(MP_Monitor_Bash.sh, new Terminal tab)${NC}\n  ${BOLD}${CYAN}9)${NC} Return to Main Menu"; echo ""; read -r -p "Enter choice [1-9, or m]: " m_choice; case "$m_choice" in 1) local drive_sh="$SCRIPT_DIR/Get_All_Drive_Space.sh"; [ ! -f "$drive_sh" ] && drive_sh="$SCRIPT_DIR/scripts/Get_All_Drive_Space.sh"; if [ -f "$drive_sh" ]; then echo ""; bash "$drive_sh"; else echo -e "\n${RED}Drive space script not found: $drive_sh${NC}"; fi; echo ""; press_enter ;; 2) echo -e "\n${BOLD}${YELLOW}Opening macOS Software Update Window in System Settings...${NC}\n"; open "x-apple.systempreferences:com.apple.preferences.softwareupdate" 2>/dev/null || open /System/Library/PreferencePanes/SoftwareUpdate.prefPane 2>/dev/null || true; echo -e "${GREEN}✓ macOS Software Update settings opened.${NC}"; press_enter ;; 3) echo -e "\n${BOLD}${YELLOW}Cleaning Homebrew...${NC}\n"; brew cleanup -s && brew autoremove; press_enter; ;; 4) echo -e "\n${BOLD}${YELLOW}Updating Homebrew & packages...${NC}\n"; brew update && brew upgrade; press_enter ;; 5) echo -e "\n${BOLD}${YELLOW}Purging inactive memory...${NC}\n"; sudo purge 2>/dev/null || purge 2>/dev/null || echo "Purge completed."; press_enter; ;; 6) echo -e "\n${BOLD}${YELLOW}Clearing user caches...${NC}\n"; rm -rf ~/Library/Caches/* 2>/dev/null || true
echo -e "${GREEN}✓ User caches cleared.${NC}"; press_enter; ;; 7) echo -e "\n${BOLD}${GREEN}=== RUNNING COMPLETE macOS CLEANUP SUITE ===${NC}\n\n${BOLD}${BLUE}[1/4] Opening Software Update window...${NC}"; open "x-apple.systempreferences:com.apple.preferences.softwareupdate" 2>/dev/null || open /System/Library/PreferencePanes/SoftwareUpdate.prefPane 2>/dev/null || true; echo -e "${BOLD}${BLUE}[2/4] Cleaning Homebrew caches...${NC}"; command -v brew &>/dev/null && brew cleanup -s && brew autoremove; echo -e "${BOLD}${BLUE}[3/4] Clearing user caches...${NC}"; rm -rf ~/Library/Caches/* 2>/dev/null || true; echo -e "${BOLD}${BLUE}[4/4] Purging inactive RAM...${NC}"; sudo purge 2>/dev/null || true; echo -e "${GREEN}✓ Cleanup suite finished!${NC}"; press_enter; ;; 8|m|monitor|mp-monitor) manage_process_and_bash_monitor ;; 9|0|[qQ]) return 0; ;; *) echo -e "\n${RED}Invalid choice!${NC}"; sleep 1.2; ;; esac; elif [ "$OS_TYPE" = "windows" ] || [ "$OS_TYPE" = "wsl" ]; then local win_disp="Windows 10/11"; if [[ "$UNAME_S" =~ MINGW.*NT-([0-9.]+) ]]; then win_disp="Windows NT ${BASH_REMATCH[1]}"; fi; echo -e "  Windows Edition:             ${GREEN}${win_disp}${NC}"; echo ""; echo -e "${BOLD}Select a maintenance operation:${NC}\n  ${BOLD}${CYAN}1)${NC} Check Drive Space Statistics (${GREEN}Get_All_Drive_Space.sh${NC}) [Mounted & Unmounted]\n  ${BOLD}${CYAN}2)${NC} Open Windows Update Window (${GREEN}ms-settings:windowsupdate${NC})\n  ${BOLD}${CYAN}3)${NC} Upgrade All Installed Packages (${GREEN}winget upgrade --all${NC})\n  ${BOLD}${CYAN}4)${NC} Clear Windows Temporary Files (${GREEN}%TEMP% & System Temp${NC})\n  ${BOLD}${CYAN}5)${NC} Empty Windows Recycle Bin (${GREEN}Clear-RecycleBin${NC})\n  ${BOLD}${CYAN}6)${NC} Optimize / TRIM Primary Drive C: (${GREEN}Optimize-Volume${NC})\n  ${BOLD}${CYAN}7)${NC} ${BOLD}${YELLOW}Run Complete Windows Maintenance Suite${NC}\n  ${BOLD}${CYAN}8)${NC} Monitor System Processes and Bash Commands with System Info ${GREEN}(MP_Monitor_Bash.sh, new Terminal tab)${NC}\n  ${BOLD}${CYAN}9)${NC} Return to Main Menu"; echo ""; read -r -p "Enter choice [1-9, or m]: " m_choice; case "$m_choice" in 1) local drive_sh="$SCRIPT_DIR/Get_All_Drive_Space.sh"; [ ! -f "$drive_sh" ] && drive_sh="$SCRIPT_DIR/scripts/Get_All_Drive_Space.sh"; if [ -f "$drive_sh" ]; then echo ""; bash "$drive_sh"; else echo -e "\n${RED}Drive space script not found: $drive_sh${NC}"; fi; echo ""; press_enter; ;; 2) echo -e "\n${BOLD}${YELLOW}Opening Windows Update Window in Settings...${NC}\n"; cmd.exe /c "start ms-settings:windowsupdate" 2>/dev/null || powershell.exe -Command "Start-Process 'ms-settings:windowsupdate'" 2>/dev/null || true; echo -e "${GREEN}✓ Windows Update window opened.${NC}"; press_enter; ;; 3) echo -e "\n${BOLD}${YELLOW}Upgrading packages via winget...${NC}\n"; cmd.exe /c "winget upgrade --all" 2>/dev/null || echo -e "${RED}winget not found.${NC}"; press_enter ;; 4) echo -e "\n${BOLD}${YELLOW}Clearing Windows temp directory...${NC}\n"; powershell.exe -Command "Remove-Item -Path \$env:TEMP\* -Recurse -Force -ErrorAction SilentlyContinue" 2>/dev/null || true; echo -e "${GREEN}✓ Temporary files removed.${NC}"
press_enter ;; 5) echo -e "\n${BOLD}${YELLOW}Emptying Recycle Bin...${NC}\n"; powershell.exe -Command "Clear-RecycleBin -Force -ErrorAction SilentlyContinue" 2>/dev/null || true; echo -e "${GREEN}✓ Recycle bin emptied.${NC}"; press_enter ;; 6) echo -e "\n${BOLD}${YELLOW}Optimizing C: drive...${NC}\n"; powershell.exe -Command "Optimize-Volume -DriveLetter C -Verbose" 2>/dev/null || true; press_enter; ;; 7) echo -e "\n${BOLD}${GREEN}=== RUNNING COMPLETE WINDOWS CLEANUP SUITE ===${NC}\n\n${BOLD}${BLUE}[1/5] Opening Windows Update window...${NC}"; cmd.exe /c "start ms-settings:windowsupdate" 2>/dev/null || powershell.exe -Command "Start-Process 'ms-settings:windowsupdate'" 2>/dev/null || true; echo -e "${BOLD}${BLUE}[2/5] Clearing temporary files...${NC}"; powershell.exe -Command "Remove-Item -Path \$env:TEMP\* -Recurse -Force -ErrorAction SilentlyContinue" 2>/dev/null || true; echo -e "${BOLD}${BLUE}[3/5] Emptying Recycle Bin...${NC}"; powershell.exe -Command "Clear-RecycleBin -Force -ErrorAction SilentlyContinue" 2>/dev/null || true; echo -e "${BOLD}${BLUE}[4/5] Upgrading installed applications via winget...${NC}"; cmd.exe /c "winget upgrade --all" 2>/dev/null || true; echo -e "${BOLD}${BLUE}[5/5] Optimizing C: drive...${NC}"; powershell.exe -Command "Optimize-Volume -DriveLetter C -Verbose" 2>/dev/null || true; echo -e "${GREEN}✓ Windows maintenance suite finished!${NC}"; press_enter; ;; 8|m|monitor|mp-monitor) manage_process_and_bash_monitor ;; 9|0|[qQ]) return 0; ;; *) echo -e "\n${RED}Invalid choice!${NC}"; sleep 1.2; ;; esac; elif [ "$OS_TYPE" = "freebsd" ]; then local pkg_count="N/A"; if command -v pkg &>/dev/null; then pkg_count=$(pkg info 2>/dev/null | wc -l | tr -d ' '); fi; echo -e "  FreeBSD Version:             ${GREEN}$(uname -r) ($(uname -m))${NC}\n  Packages Installed (pkg):    ${CYAN}${pkg_count}${NC}"; echo ""; echo -e "${BOLD}Select a maintenance operation:${NC}\n  ${BOLD}${CYAN}1)${NC} Check Drive Space Statistics (${GREEN}Get_All_Drive_Space.sh${NC}) [Mounted & Unmounted]\n  ${BOLD}${CYAN}2)${NC} Clean Package Caches & Old Deps (${GREEN}pkg clean -a && pkg autoremove${NC})\n  ${BOLD}${CYAN}3)${NC} Full FreeBSD Package Upgrade (${GREEN}pkg upgrade${NC})\n  ${BOLD}${CYAN}4)${NC} Audit Installed Packages for Vulnerabilities (${GREEN}pkg audit -F${NC})\n  ${BOLD}${CYAN}5)${NC} Clear User Caches & /tmp (${GREEN}rm -rf ~/.cache/* /tmp/*${NC})\n  ${BOLD}${CYAN}6)${NC} ${BOLD}${YELLOW}Run Complete FreeBSD Maintenance Suite${NC}\n  ${BOLD}${CYAN}7)${NC} Monitor System Processes and Bash Commands with System Info ${GREEN}(MP_Monitor_Bash.sh, new Terminal tab)${NC}\n  ${BOLD}${CYAN}8)${NC} Return to Main Menu"; echo ""; read -r -p "Enter choice [1-8, or m]: " m_choice; case "$m_choice" in 1) local drive_sh="$SCRIPT_DIR/Get_All_Drive_Space.sh"; [ ! -f "$drive_sh" ] && drive_sh="$SCRIPT_DIR/scripts/Get_All_Drive_Space.sh"; if [ -f "$drive_sh" ]; then echo ""; bash "$drive_sh"; else echo -e "\n${RED}Drive space script not found: $drive_sh${NC}"; fi; echo ""; press_enter; ;; 2) echo -e "\n${BOLD}${YELLOW}Cleaning pkg caches...${NC}\n"; sudo pkg clean -a -y && sudo pkg autoremove -y || pkg clean -a -y
press_enter ;; 3) echo -e "\n${BOLD}${YELLOW}Upgrading FreeBSD packages...${NC}\n"; sudo pkg upgrade || pkg upgrade; press_enter; ;; 4) echo -e "\n${BOLD}${YELLOW}Auditing FreeBSD packages...${NC}\n"; pkg audit -F; press_enter ;; 5) echo -e "\n${BOLD}${YELLOW}Clearing user cache and /tmp...${NC}\n"; rm -rf ~/.cache/* 2>/dev/null || true; echo -e "${GREEN}✓ User caches cleared.${NC}"; press_enter ;; 6) echo -e "\n${BOLD}${GREEN}=== RUNNING COMPLETE FreeBSD CLEANUP SUITE ===${NC}\n"; sudo pkg clean -a -y 2>/dev/null || true; sudo pkg autoremove -y 2>/dev/null || true; pkg audit -F 2>/dev/null || true; rm -rf ~/.cache/* 2>/dev/null || true; echo -e "${GREEN}✓ FreeBSD maintenance suite finished!${NC}"; press_enter; ;; 7|m|monitor|mp-monitor) manage_process_and_bash_monitor ;; 8|0|[qQ]) return 0; ;; *) echo -e "\n${RED}Invalid choice!${NC}"; sleep 1.2; ;; esac; else local journal_usage; journal_usage=$(journalctl --disk-usage 2>/dev/null | grep -o '[0-9.]*[KMGT]B*' || echo "N/A"); echo -e "  System Journal Log Usage:   ${CYAN}${journal_usage}${NC}"; if command -v free &>/dev/null; then local ram_info; ram_info=$(free -h 2>/dev/null | awk '/^Mem:/ {print $3 "/" $2 " used, " $6 " cached, " $7 " avail"}'); [ -n "$ram_info" ] && echo -e "  System Memory (RAM):        ${CYAN}${ram_info}${NC}"; fi; local distro_desc=""; if [ -f /etc/os-release ]; then distro_desc=$(grep -E '^PRETTY_NAME=' /etc/os-release 2>/dev/null | cut -d= -f2 | tr -d '"'); fi; [ -z "$distro_desc" ] && distro_desc="Linux ($(uname -r))"; if command -v rpm-ostree &>/dev/null; then local ostree_status; ostree_status=$(rpm-ostree status 2>/dev/null | grep -E '^\*? State:' | head -n 1 | awk '{print $2}' || echo "idle"); [ -z "$ostree_status" ] && ostree_status="idle"; echo -e "  Operating System:           ${GREEN}${distro_desc}${NC} (rpm-ostree: ${ostree_status})"; else echo -e "  Operating System:           ${GREEN}${distro_desc}${NC}"; fi; echo ""; local clean_label="Clean System (Package Caches, Unused Runtimes)"; local update_label="Full System & Package Update"; if command -v ujust &>/dev/null; then
clean_label="Clean System (${GREEN}ujust clean-system${NC}) [Podman, Flatpak, ostree, Brew]"; update_label="Full System & Package Update (${GREEN}ujust update${NC}) [OS, Flatpaks, Brew]"; elif command -v dnf5 &>/dev/null; then clean_label="Clean System (${GREEN}sudo dnf5 clean all && autoremove${NC}) [DNF caches, Flatpaks]"; update_label="Full System & Package Update (${GREEN}sudo dnf5 upgrade --refresh${NC}) [Fedora packages, Flatpaks]"; elif command -v dnf &>/dev/null; then clean_label="Clean System (${GREEN}sudo dnf clean all && autoremove${NC}) [DNF caches, Flatpaks]"; update_label="Full System & Package Update (${GREEN}sudo dnf upgrade --refresh${NC}) [Fedora / RHEL packages, Flatpaks]"; elif command -v rpm-ostree &>/dev/null; then clean_label="Clean System (${GREEN}rpm-ostree cleanup -m${NC}) [ostree, Flatpaks]"; update_label="Full System & Package Update (${GREEN}rpm-ostree upgrade${NC}) [Atomic OS, Flatpaks]"; elif command -v apt-get &>/dev/null; then clean_label="Clean System (${GREEN}sudo apt autoremove && clean${NC}) [APT caches, Flatpaks]"; update_label="Full System & Package Update (${GREEN}sudo apt update && upgrade${NC}) [Debian/Ubuntu packages, Flatpaks]"; elif command -v pacman &>/dev/null; then clean_label="Clean System (${GREEN}sudo pacman -Sc${NC}) [Pacman caches, Flatpaks]"; update_label="Full System & Package Update (${GREEN}sudo pacman -Syu${NC}) [Arch packages, Flatpaks]"; elif command -v zypper &>/dev/null; then clean_label="Clean System (${GREEN}sudo zypper clean -a${NC}) [Zypper caches, Flatpaks]"; update_label="Full System & Package Update (${GREEN}sudo zypper refresh && update${NC}) [openSUSE packages]"; fi; echo -e "${BOLD}Select a maintenance operation:${NC}\n  ${BOLD}${CYAN}1)${NC} Check Drive Space Statistics (${GREEN}Get_All_Drive_Space.sh${NC}) [Mounted & Unmounted]\n  ${BOLD}${CYAN}2)${NC} ${clean_label}\n  ${BOLD}${CYAN}3)${NC} ${update_label}\n  ${BOLD}${CYAN}4)${NC} Vacuum System Logs (${GREEN}sudo journalctl --vacuum-size=200M${NC})\n  ${BOLD}${CYAN}5)${NC} Optimize & Trim SSD Storage (${GREEN}sudo fstrim -av${NC})\n  ${BOLD}${CYAN}6)${NC} Clear System Memory & Page Cache (${GREEN}sudo sync && drop_caches=3${NC})\n  ${BOLD}${CYAN}7)${NC} ${BOLD}${YELLOW}Run Complete Cleanup Suite${NC} (Clean System + Drop RAM Cache + Vacuum Logs + SSD Trim)\n  ${BOLD}${CYAN}8)${NC} Monitor System Processes and Bash Commands with System Info ${GREEN}(MP_Monitor_Bash.sh, new Terminal tab)${NC}\n  ${BOLD}${CYAN}9)${NC} Return to Main Menu"; echo ""; read -r -p "Enter choice [1-9, or m]: " m_choice; case $m_choice in 1) local drive_sh="$SCRIPT_DIR/Get_All_Drive_Space.sh"; [ ! -f "$drive_sh" ] && drive_sh="$SCRIPT_DIR/scripts/Get_All_Drive_Space.sh"; if [ -f "$drive_sh" ]; then echo ""; bash "$drive_sh"; else
echo -e "\n${RED}Drive space script not found: $drive_sh${NC}"; fi; echo ""; press_enter; ;; 2) echo -e "\n${BOLD}${YELLOW}=== RUNNING SYSTEM CLEANUP ===${NC}\n"; if command -v ujust &>/dev/null; then echo -e "${BOLD}${CYAN}» Running ujust clean-system...${NC}"; ujust clean-system; else if command -v dnf5 &>/dev/null; then echo -e "${BOLD}${CYAN}» Cleaning dnf5 caches & unused packages...${NC}"; sudo dnf5 clean all && sudo dnf5 autoremove -y || true; elif command -v dnf &>/dev/null; then echo -e "${BOLD}${CYAN}» Cleaning dnf caches & unused packages...${NC}"; sudo dnf clean all && sudo dnf autoremove -y || true; elif command -v apt-get &>/dev/null; then echo -e "${BOLD}${CYAN}» Cleaning APT caches & unused packages...${NC}"; sudo apt-get autoremove -y && sudo apt-get clean || true; elif command -v pacman &>/dev/null; then echo -e "${BOLD}${CYAN}» Cleaning Pacman caches...${NC}"; sudo pacman -Sc --noconfirm || true; elif command -v zypper &>/dev/null; then echo -e "${BOLD}${CYAN}» Cleaning Zypper caches...${NC}"; sudo zypper clean -a || true; fi; if command -v rpm-ostree &>/dev/null; then echo -e "${BOLD}${CYAN}» Cleaning ostree metadata...${NC}"; rpm-ostree cleanup -m 2>/dev/null || true; fi; if command -v flatpak &>/dev/null; then echo -e "${BOLD}${CYAN}» Uninstalling unused Flatpak runtimes...${NC}"; flatpak uninstall --unused -y 2>/dev/null || true; fi; if command -v podman &>/dev/null; then echo -e "${BOLD}${CYAN}» Pruning unused podman images & containers...${NC}"; podman system prune -f 2>/dev/null || true; elif command -v docker &>/dev/null; then echo -e "${BOLD}${CYAN}» Pruning unused docker images & containers...${NC}"; docker system prune -f 2>/dev/null || true; fi; if command -v brew &>/dev/null; then echo -e "${BOLD}${CYAN}» Cleaning Homebrew packages...${NC}"; brew cleanup -s 2>/dev/null && brew autoremove 2>/dev/null || true; fi; fi; echo -e "${BOLD}${CYAN}» Clearing user thumbnails & cache...${NC}"; rm -rf "$HOME/.cache/thumbnails"/* 2>/dev/null || true; echo -e "\n${GREEN}[✓] System cleanup completed successfully.${NC}"; echo ""; press_enter; ;; 3) echo -e "\n${BOLD}${YELLOW}=== DOWNLOADING & APPLYING SYSTEM UPDATES ===${NC}\n"; local updated=0; if command -v ujust &>/dev/null; then echo -e "${BOLD}${CYAN}» Running ujust update (Bazzite / Universal Blue)...${NC}"; ujust update && updated=1; elif command -v rpm-ostree &>/dev/null; then echo -e "${BOLD}${CYAN}» Upgrading ostree deployment (rpm-ostree upgrade)...${NC}"; rpm-ostree upgrade && updated=1; elif command -v dnf5 &>/dev/null; then echo -e "${BOLD}${CYAN}» Updating Fedora packages (dnf5 upgrade)...${NC}"
sudo dnf5 upgrade --refresh -y && updated=1; elif command -v dnf &>/dev/null; then echo -e "${BOLD}${CYAN}» Updating Fedora / RHEL packages (dnf upgrade)...${NC}"; sudo dnf upgrade --refresh -y && updated=1; elif command -v apt-get &>/dev/null; then echo -e "${BOLD}${CYAN}» Updating APT packages (apt update && apt upgrade)...${NC}"; sudo apt-get update && sudo apt-get upgrade -y && updated=1; elif command -v pacman &>/dev/null; then echo -e "${BOLD}${CYAN}» Updating Pacman packages (pacman -Syu)...${NC}"; sudo pacman -Syu --noconfirm && updated=1; elif command -v zypper &>/dev/null; then echo -e "${BOLD}${CYAN}» Updating Zypper packages...${NC}"; sudo zypper refresh && sudo zypper update -y && updated=1; elif command -v apk &>/dev/null; then echo -e "${BOLD}${CYAN}» Updating Alpine packages (apk upgrade)...${NC}"; sudo apk update && sudo apk upgrade && updated=1; fi; if command -v flatpak &>/dev/null; then echo -e "\n${BOLD}${CYAN}» Updating Flatpak applications and runtimes...${NC}"; flatpak update -y && updated=1; fi; if command -v snap &>/dev/null; then echo -e "\n${BOLD}${CYAN}» Refreshing Snap packages...${NC}"; sudo snap refresh 2>/dev/null && updated=1; fi; if command -v brew &>/dev/null; then echo -e "\n${BOLD}${CYAN}» Updating Homebrew on Linux...${NC}"; brew update && brew upgrade && updated=1; fi; if [ "$updated" -eq 1 ]; then echo -e "\n${GREEN}[✓] System update completed successfully.${NC}"; else echo -e "\n${RED}No supported package manager found to update.${NC}"; fi; echo ""; press_enter; ;; 4) echo -e "\n${BOLD}${YELLOW}Vacuuming system logs down to 200MB...${NC}\n"; sudo journalctl --vacuum-size=200M 2>/dev/null || true; echo ""; journalctl --disk-usage 2>/dev/null || true; echo ""; press_enter; ;; 5) echo -e "\n${BOLD}${YELLOW}Trimming and optimizing SSD storage (fstrim)...${NC}\n"; sudo fstrim -av 2>/dev/null || true; echo ""; press_enter; ;; 6) echo -e "\n${BOLD}${YELLOW}=== CLEAR SYSTEM MEMORY (RAM & PAGE CACHE) ===${NC}\n"; if command -v free &>/dev/null; then echo -e "${BOLD}Memory status before cleanup:${NC}"; free -h; echo ""; fi; echo -e "${CYAN}Syncing filesystem buffers to disk...${NC}"; sync; echo -e "${CYAN}Dropping pagecache, dentries, and inodes (drop_caches=3)...${NC}"; if echo 3 | sudo tee /proc/sys/vm/drop_caches &>/dev/null; then echo -e "${GREEN}✓ PageCache, dentries, and inodes successfully cleared!${NC}"; elif sudo sysctl -w vm.drop_caches=3 &>/dev/null; then echo -e "${GREEN}✓ PageCache, dentries, and inodes successfully cleared via sysctl!${NC}"; else echo -e "${RED}Failed to drop caches (sudo permissions required).${NC}"; fi; local swap_used_kb=0; if [ -f /proc/meminfo ]; then swap_used_kb=$(awk '/SwapTotal:/ {st=$2} /SwapFree:/ {sf=$2} END {print (st - sf)}' /proc/meminfo 2>/dev/null || echo 0); fi; if [ "$swap_used_kb" -gt 51200 ]; then local swap_used_human
swap_used_human=$(awk '/SwapTotal:/ {st=$2} /SwapFree:/ {sf=$2} END {printf "%.1f MB", (st - sf)/1024}' /proc/meminfo 2>/dev/null || echo "Swap in use")
echo ""; echo -e "Swap memory currently in use: ${YELLOW}${swap_used_human}${NC}"; read -r -p "Would you also like to flush swap memory back into RAM? [y/N]: " swap_choice; case "$swap_choice" in [yY]|[yY][eE][sS]) echo -e "${CYAN}Flushing swap back to RAM (sudo swapoff -a && sudo swapon -a)...${NC}"; if sudo swapoff -a && sudo swapon -a; then echo -e "${GREEN}✓ Swap memory flushed successfully!${NC}"; else echo -e "${RED}Warning: Could not cycle swap.${NC}"; fi ;; *) echo -e "${DIM}Skipping swap flush.${NC}"; ;; esac; fi; echo ""; if command -v free &>/dev/null; then echo -e "${BOLD}Memory status after cleanup:${NC}"; free -h; fi; echo ""; press_enter; ;; 7) echo -e "\n${BOLD}${GREEN}=== RUNNING COMPLETE CLEANUP SUITE ===${NC}\n\n${BOLD}${BLUE}[1/4] Running System Cleanup...${NC}"; if command -v ujust &>/dev/null; then ujust clean-system; else if command -v dnf5 &>/dev/null; then sudo dnf5 clean all && sudo dnf5 autoremove -y || true; elif command -v dnf &>/dev/null; then sudo dnf clean all && sudo dnf autoremove -y || true; elif command -v apt-get &>/dev/null; then sudo apt-get autoremove -y && sudo apt-get clean || true; elif command -v pacman &>/dev/null; then sudo pacman -Sc --noconfirm || true; elif command -v zypper &>/dev/null; then sudo zypper clean -a || true; fi; if command -v rpm-ostree &>/dev/null; then rpm-ostree cleanup -m 2>/dev/null || true; fi; if command -v flatpak &>/dev/null; then flatpak uninstall --unused -y 2>/dev/null || true; fi; if command -v podman &>/dev/null; then podman system prune -f 2>/dev/null || true; fi; rm -rf "$HOME/.cache/thumbnails"/* 2>/dev/null || true; fi; echo ""; echo -e "${BOLD}${BLUE}[2/4] Clearing System Memory (RAM Cache)...${NC}"; sync; echo 3 | sudo tee /proc/sys/vm/drop_caches &>/dev/null || sudo sysctl -w vm.drop_caches=3 &>/dev/null || true; echo -e "${GREEN}✓ System RAM cache cleared.${NC}"; echo ""; echo -e "${BOLD}${BLUE}[3/4] Vacuuming system logs to 200MB...${NC}"; sudo journalctl --vacuum-size=200M 2>/dev/null || true; echo ""; echo -e "${BOLD}${BLUE}[4/4] Trimming SSD filesystems (fstrim)...${NC}"; sudo fstrim -av 2>/dev/null || true; echo ""; echo -e "${BOLD}${GREEN}[✓] Complete cleanup finished!${NC}"; journalctl --disk-usage 2>/dev/null || true; if command -v free &>/dev/null; then echo ""; free -h; fi; echo ""; press_enter; ;; 8|m|monitor|mp-monitor) manage_process_and_bash_monitor ;; 9|0|[qQ]) return 0; ;; *) echo -e "\n${RED}Invalid option!${NC}"; sleep 1.5; ;; esac; fi; done
}
launch_ai_session() {
local target_arg="$1"; local title="$2"; local agy_bin
if command -v agy &>/dev/null; then agy_bin="agy"; elif [ -x "$HOME/.local/bin/agy.bin" ]; then agy_bin="$HOME/.local/bin/agy.bin"; else agy_bin="agy"; fi; local run_cmd="\"$agy_bin\""; if [ -n "$target_arg" ]; then if [[ "$target_arg" =~ ^-- ]]; then run_cmd="\"$agy_bin\" $target_arg"; else run_cmd="\"$agy_bin\" --model \"$target_arg\""; fi; fi; if [ -z "${DISPLAY:-}" ] && [ -z "${WAYLAND_DISPLAY:-}" ]; then echo -e "\n${BOLD}${YELLOW}No GUI display detected; launching ${title} in current terminal...${NC}\n"; sleep 0.8; trap ':' INT; eval "$run_cmd"; trap 'exit_mix_manager' INT; press_enter; return 0; fi; echo ""; echo -e "${BOLD}Select launch target for ${title}:${NC}\n  ${BOLD}${CYAN}1)${NC} New Terminal Tab (Default - keeps Manager running in background)\n  ${BOLD}${CYAN}2)${NC} New Standalone Terminal Window\n  ${BOLD}${CYAN}3)${NC} Current Terminal Window (Returns to Manager upon exit)"; read -r -p "Enter choice [1-3, default: 1]: " t_choice; case "$t_choice" in 2) echo -e "\n${BOLD}${GREEN}Launching ${title} in a new window...${NC}\n"; local full_cmd="$run_cmd; echo ''; echo 'Session ended. Press [Enter] to close window...'; read -r"; if launch_in_terminal "$title" "$full_cmd" "window"; then echo -e "${GREEN}✓ ${title} launched in a new window.${NC}"; sleep 1.2; else echo -e "${YELLOW}No external terminal emulator found; launching in current window...${NC}"; sleep 0.5; trap ':' INT; eval "$run_cmd"; trap 'exit_mix_manager' INT; press_enter; return 0; fi ;; 3) echo -e "\n${BOLD}${YELLOW}Launching ${title} in current terminal (Type /exit or Ctrl+D twice to return)...${NC}\n"; sleep 0.8; trap ':' INT; eval "$run_cmd"; trap 'exit_mix_manager' INT; press_enter ;; *) echo -e "\n${BOLD}${GREEN}Launching ${title} in a new terminal tab...${NC}\n"; local full_cmd="$run_cmd; echo ''; echo 'Session ended. Press [Enter] to close tab...'; read -r"; if launch_in_terminal "$title" "$full_cmd" "tab"; then echo -e "${GREEN}✓ ${title} launched in a new terminal tab.${NC}"; sleep 1.2; else echo -e "${YELLOW}No external terminal emulator found; launching in current window...${NC}"; sleep 0.5; trap ':' INT; eval "$run_cmd"; trap 'exit_mix_manager' INT; press_enter; return 0; fi ;; esac
}
manage_ai_models() {
local ai_opts=(
"SECTION|CLAUDE & GPT MODELS (Shared Partner Quota)|"
"1|Claude Sonnet 4.6 (Thinking)|[claude-sonnet-4-6]"
"2|Claude Opus 4.6 (Thinking)|[claude-opus-4-6-thinking]"
"3|GPT-OSS 120B (Medium)|[gpt-oss-120b-medium]"
"SECTION|GOOGLE GEMINI MODELS (High Volume Quota)|"
"4|Gemini 3.8 Flash (High)|[gemini-3.8-flash-high]"
"5|Gemini 3.1 Pro (High)|[gemini-3.1-pro-high]"
"SECTION|LOCAL OLLAMA & AI WEB INTERFACES|"
"6|Manage Ollama Server & Local Models|[ollama serve / chat / voice / status]"
"7|Launch dsh-mobile Web Server|[http://192.168.1.11:3080]"
"8|Manage DeepSeek Harness Server|[Start, Stop, Browser, Status]"
"SECTION|SESSIONS & UTILITIES|"
"9|Launch Default Session|[agy]"
"10|Resume Most Recent Conversation|[agy --continue]"
"11|View All Available Models & Status|[agy models]"
"SEP|SEP|"
"0|Return to Previous Menu|(or Esc / q)"
)
local hdr="  Account:   ${CYAN}mathewkjohn2026@gmail.com${NC}\n  Workspace: ${GREEN}${PWD}${NC}\n"
while true; do
run_interactive_submenu "AI ASSISTANT & MODEL LAUNCHER (AGY)" "$hdr" ai_opts 0
case "$REPLY" in
1) launch_ai_session "claude-sonnet-4-6" "Claude Sonnet" ;;
2) launch_ai_session "claude-opus-4-6-thinking" "Claude Opus" ;;
3) launch_ai_session "gpt-oss-120b-medium" "GPT-OSS 120B" ;;
4) launch_ai_session "gemini-3.8-flash-high" "Gemini 3.8 Flash" ;;
5) launch_ai_session "gemini-3.1-pro-high" "Gemini 3.1 Pro" ;;
6) manage_ollama ;;
7) launch_dsh_mobile; press_enter ;;
8) manage_dsh_mobile ;;
9) launch_ai_session "" "Antigravity AI" ;;
10) echo -e "\n${BOLD}${YELLOW}Resuming most recent conversation...${NC}\n"; launch_ai_session "--continue" "Resume Session" ;;
11) echo -e "\n${BOLD}${BLUE}=== AVAILABLE MODELS IN AGY ===${NC}\n"; if command -v agy &>/dev/null; then agy models; elif [ -x "$HOME/.local/bin/agy.bin" ]; then "$HOME/.local/bin/agy.bin" models; fi; echo ""; press_enter ;;
0|12|[qQ]|[eE][xX][iI][tT]|ESC) return 0 ;;
*) echo -e "\n${RED}Invalid option!${NC}"; sleep 1.2 ;;
esac
done
}
burn_iso_to_usb() {
echo -e "\n${BOLD}${MAGENTA}==================================================${NC}\n${BOLD}${MAGENTA}          BURN ISO IMAGE TO USB DRIVE (DD)        ${NC}\n${BOLD}${MAGENTA}==================================================${NC}\n"; local iso_path=""; read -r -e -p "Enter full path to the ISO file: " iso_path; iso_path=$(echo "$iso_path" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'$//"); if [ -z "$iso_path" ]; then echo -e "${RED}Error: ISO file path cannot be empty!${NC}"; press_enter; return 1; fi; if [[ "$iso_path" == ~* ]]; then iso_path="${iso_path/#~/$HOME}"; fi; if [ ! -f "$iso_path" ]; then echo -e "${RED}Error: File not found at '$iso_path'!${NC}"; press_enter; return 1; fi; local iso_size; iso_size=$(ls -lh "$iso_path" 2>/dev/null | awk '{print $5}'); echo -e "${GREEN}✓ Found ISO:${NC} $iso_path (${CYAN}${iso_size}${NC})"; if [ "$OS_TYPE" = "macos" ]; then echo -e "\n${BOLD}Available External USB Drives (macOS diskutil):${NC}"; diskutil list external; echo ""; read -r -p "Enter target disk name (e.g. disk2 or /dev/disk2): " target_dev; target_dev=$(echo "$target_dev" | tr -d ' ' | sed 's|^/dev/||'); if [ -z "$target_dev" ]; then echo -e "${RED}Error: Target disk cannot be empty!${NC}"; press_enter; return 1; fi; local full_dev="/dev/$target_dev"; if ! diskutil info "$full_dev" &>/dev/null; then echo -e "${RED}Error: Disk '$full_dev' not found!${NC}"; press_enter; return 1; fi; if diskutil info "$full_dev" | grep -qi "Internal:[[:space:]]*Yes"; then echo -e "${BOLD}${RED}FATAL: $full_dev is reported as an INTERNAL drive! Aborting for safety.${NC}"; press_enter; return 1; fi; echo -e "\n${BOLD}${RED}!!!!!!!!!!!!!!!!!!!!!!!!!! WARNING !!!!!!!!!!!!!!!!!!!!!!!!!!${NC}\n${BOLD}${RED}ALL EXISTING DATA ON $full_dev WILL BE PERMANENTLY ERASED!${NC}\n${BOLD}${RED}Source: $iso_path (${iso_size})${NC}\n${BOLD}${RED}Target: $full_dev${NC}\n${BOLD}${RED}!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!${NC}\n"; read -r -p "Type 'YES' (in capitals) to confirm writing to $full_dev: " confirm_burn; if [ "$confirm_burn" != "YES" ]; then echo -e "\n${YELLOW}Operation canceled. No changes were made.${NC}"; press_enter; return 0; fi; echo -e "\n${CYAN}Unmounting $full_dev...${NC}"; diskutil unmountDisk "$full_dev"; local r_dev="/dev/r${target_dev}"; echo -e "\n${BOLD}${GREEN}Executing dd (writing ISO to $r_dev)...${NC}\n"; sudo dd if="$iso_path" of="$r_dev" bs=4m status=progress; local dd_status=$?; if [ $dd_status -eq 0 ]; then echo -e "\n${BOLD}${GREEN}✓ Successfully wrote ISO to $r_dev!${NC}\n${CYAN}Disk ejected. USB drive is ready to boot.${NC}"; diskutil eject "$full_dev" 2>/dev/null || true; else echo -e "\n${BOLD}${RED}✗ Error occurred during dd write (exit code: $dd_status)!${NC}"; fi; press_enter; return $dd_status; elif [ "$OS_TYPE" = "windows" ] || [ "$OS_TYPE" = "wsl" ]; then
echo -e "\n${BOLD}Available Disks (Windows PowerShell):${NC}"; powershell.exe -NoProfile -Command "Get-Disk | Select-Object Number, FriendlyName, BusType, @{Name='Size_GB';Expression={[math]::Round(\$_.Size / 1GB, 2)}} | Format-Table -AutoSize" 2>/dev/null; echo -e "\n${YELLOW}Note: Direct block-level raw writing to physical drives on Windows requires elevated privileges.${NC}\n${CYAN}For Windows 10/11, it is highly recommended to use:${NC}\n  • ${BOLD}Rufus${NC} (https://rufus.ie) - Best for bootable USB creation\n  • ${BOLD}BalenaEtcher${NC} (https://etcher.balena.io) - Easy cross-platform image flasher"; echo ""; read -r -p "Press [Enter] to open Rufus download page or 'q' to return: " w_burn_opt; if [ "$w_burn_opt" != "q" ] && [ "$w_burn_opt" != "Q" ]; then open_path "https://rufus.ie"; fi; return 0; fi; echo -e "\n${BOLD}Available USB Removable Devices:${NC}"; lsblk -d -o NAME,MODEL,SIZE,TRAN,VENDOR,TYPE | grep -E "usb|NAME"; echo ""; local target_dev=""; read -r -p "Enter target device name (e.g. sdf or /dev/sdf): " target_dev; target_dev=$(echo "$target_dev" | tr -d ' ' | sed 's|^/dev/||'); if [ -z "$target_dev" ]; then echo -e "${RED}Error: Target device cannot be empty!${NC}"; press_enter; return 1; fi; local full_dev="/dev/$target_dev"; if [ ! -b "$full_dev" ]; then echo -e "${RED}Error: Block device '$full_dev' does not exist!${NC}"; press_enter; return 1; fi; local dev_type; dev_type=$(lsblk -no TYPE "$full_dev" 2>/dev/null | head -n 1); if [ "$dev_type" != "disk" ]; then echo -e "${RED}Error: '$full_dev' is a $dev_type, not a whole disk (e.g. specify 'sdf', not 'sdf1')!${NC}"; press_enter; return 1; fi; local mounts; mounts=$(lsblk -no MOUNTPOINTS "$full_dev" 2>/dev/null | tr '\n' ' '); if echo "$mounts" | grep -qE '(^|[[:space:]])/(sysroot|boot|var|etc|home|var/home)?([[:space:]]|$)'; then echo -e "${BOLD}${RED}FATAL: $full_dev contains active operating system mounts! Aborting.${NC}"; press_enter; return 1; fi; local tran; tran=$(lsblk -no TRAN "$full_dev" 2>/dev/null | head -n 1); if [ "$tran" != "usb" ]; then echo -e "${BOLD}${YELLOW}WARNING: Device $full_dev transport is '$tran' (not USB)!${NC}"; fi; echo -e "\n${BOLD}${BLUE}Target Drive Details:${NC}"; lsblk -o NAME,MODEL,SIZE,LABEL,FSTYPE,MOUNTPOINTS "$full_dev"; echo ""; echo -e "${BOLD}${RED}!!!!!!!!!!!!!!!!!!!!!!!!!! WARNING !!!!!!!!!!!!!!!!!!!!!!!!!!${NC}\n${BOLD}${RED}ALL EXISTING DATA ON $full_dev WILL BE PERMANENTLY ERASED!${NC}\n${BOLD}${RED}Source: $iso_path (${iso_size})${NC}\n${BOLD}${RED}Target: $full_dev${NC}\n${BOLD}${RED}!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!${NC}\n"; read -r -p "Type 'YES' (in capitals) to confirm writing to $full_dev: " confirm_burn; if [ "$confirm_burn" != "YES" ]; then echo -e "\n${YELLOW}Operation canceled. No changes were made.${NC}"; press_enter; return 0; fi; echo -e "\n${CYAN}Unmounting any active partitions on $full_dev...${NC}"; local part_names; part_names=$(lsblk -lno NAME "$full_dev" 2>/dev/null | tail -n +2); for part in $part_names; do if grep -qs "/dev/$part" /proc/mounts; then echo -e "  Unmounting /dev/$part..."; udisksctl unmount -b "/dev/$part" 2>/dev/null || sudo umount "/dev/$part" 2>/dev/null || true; fi; done; echo -e "\n${BOLD}${GREEN}Executing dd (writing ISO to $full_dev)...${NC}\n"; sudo dd if="$iso_path" of="$full_dev" bs=4M status=progress oflag=sync; local dd_status=$?; if [ $dd_status -eq 0 ]; then sync; echo -e "\n${BOLD}${GREEN}✓ Successfully wrote ISO to $full_dev!${NC}\n${CYAN}Disk synced. The USB drive is now ready to boot.${NC}"; else echo -e "\n${BOLD}${RED}✗ Error occurred during dd write (exit code: $dd_status)!${NC}"; fi; press_enter; return $dd_status
}
is_app_installed() {
local bin_name="$1"; local flatpak_id="$2"; local mac_app_name="$3"; local win_exe_name="$4"; if [ -n "$bin_name" ] && command -v "$bin_name" &>/dev/null; then return 0; fi; if [ "$OS_TYPE" = "macos" ] && [ -n "$mac_app_name" ]; then if [ -d "/Applications/${mac_app_name}.app" ] || [ -d "$HOME/Applications/${mac_app_name}.app" ] || osascript -e "id of application \"$mac_app_name\"" &>/dev/null; then return 0; fi; fi; if { [ "$OS_TYPE" = "windows" ] || [ "$OS_TYPE" = "wsl" ]; } && [ -n "$win_exe_name" ]; then if [ -f "/c/Program Files/${win_exe_name}" ] || [ -f "/c/Program Files (x86)/${win_exe_name}" ] || [ -f "$LOCALAPPDATA/${win_exe_name}" ]; then return 0; fi; if command -v cmd.exe &>/dev/null; then if [ -n "$bin_name" ] && cmd.exe /c "where $bin_name" &>/dev/null; then return 0; fi; fi; fi; if [ -n "$flatpak_id" ] && command -v flatpak &>/dev/null; then if flatpak info "$flatpak_id" &>/dev/null; then return 0; fi; fi; return 1
}
launch_gui_app() {
local app_name="$1"; local bin_name="$2"; local flatpak_id="$3"; local mac_app_name="$4"; local brew_cask="$5"; local win_exe_name="$6"; local winget_id="$7"; echo -e "\n${BOLD}${YELLOW}Launching ${app_name}...${NC}\n"; if [ -n "$bin_name" ] && command -v "$bin_name" &>/dev/null; then nohup "$bin_name" &>/dev/null &
echo -e "${GREEN}✓ ${app_name} launched successfully.${NC}"; sleep 1.2; return 0; fi; if [ "$OS_TYPE" = "macos" ]; then if [ -n "$mac_app_name" ]; then if osascript -e "id of application \"$mac_app_name\"" &>/dev/null || [ -d "/Applications/${mac_app_name}.app" ] || [ -d "$HOME/Applications/${mac_app_name}.app" ]; then open -a "$mac_app_name" &>/dev/null &
echo -e "${GREEN}✓ ${app_name} launched (macOS App).${NC}"; sleep 1.2; return 0; fi; fi; if [ -n "$brew_cask" ] && command -v brew &>/dev/null; then echo -e "${YELLOW}${app_name} is not installed.${NC}"; read -r -p "Install ${app_name} via Homebrew now? [y/N]: " mac_inst; if [[ "$mac_inst" =~ ^[Yy]$ ]]; then echo -e "${CYAN}Running: brew install --cask ${brew_cask}...${NC}"; if brew install --cask "$brew_cask"; then open -a "$mac_app_name" &>/dev/null &
echo -e "${GREEN}✓ ${app_name} installed and launched!${NC}"; sleep 1.2; return 0; else echo -e "${RED}Error: Homebrew installation failed.${NC}"; press_enter; return 1; fi; fi; fi; echo -e "${RED}Error: ${app_name} is not installed!${NC}"; press_enter; return 1; fi; if [ "$OS_TYPE" = "windows" ] || [ "$OS_TYPE" = "wsl" ]; then if [ -n "$win_exe_name" ]; then local win_paths=("/c/Program Files/${win_exe_name}" "/c/Program Files (x86)/${win_exe_name}" "$LOCALAPPDATA/${win_exe_name}"); for p in "${win_paths[@]}"; do if [ -f "$p" ]; then if command -v cygpath &>/dev/null; then cmd.exe /c start "" "$(cygpath -w "$p")" &>/dev/null &
else cmd.exe /c start "" "$p" &>/dev/null &
fi; echo -e "${GREEN}✓ ${app_name} launched (Windows).${NC}"; sleep 1.2; return 0; fi; done; fi; if [ -n "$bin_name" ] && command -v cmd.exe &>/dev/null; then if cmd.exe /c "where $bin_name" &>/dev/null; then cmd.exe /c start "" "$bin_name" &>/dev/null &
echo -e "${GREEN}✓ ${app_name} launched (Windows).${NC}"; sleep 1.2; return 0; fi; fi; if [ -n "$winget_id" ] && command -v winget.exe &>/dev/null; then echo -e "${YELLOW}${app_name} is not installed.${NC}"; read -r -p "Install ${app_name} via winget now? [y/N]: " win_inst; if [[ "$win_inst" =~ ^[Yy]$ ]]; then echo -e "${CYAN}Running: winget install ${winget_id}...${NC}"; winget.exe install --id "$winget_id" -e --accept-source-agreements --accept-package-agreements; echo -e "${GREEN}✓ Installation finished. Please re-run to launch.${NC}"; press_enter; return 0; fi; fi; echo -e "${RED}Error: ${app_name} is not installed!${NC}"; press_enter; return 1; fi; if [ -n "$flatpak_id" ] && command -v flatpak &>/dev/null; then if flatpak info "$flatpak_id" &>/dev/null; then nohup flatpak run "$flatpak_id" &>/dev/null &
echo -e "${GREEN}✓ ${app_name} launched (Flatpak).${NC}"; sleep 1.2; return 0; fi; echo -e "${YELLOW}${app_name} is not installed on this system.${NC}"; read -r -p "Would you like to install ${app_name} via Flatpak now? [y/N]: " do_install; if [[ "$do_install" =~ ^[Yy]$ ]]; then echo -e "${CYAN}Installing ${flatpak_id} from Flathub...${NC}"; if flatpak install -y --user flathub "$flatpak_id"; then nohup flatpak run "$flatpak_id" &>/dev/null &
echo -e "${GREEN}✓ ${app_name} installed and launched!${NC}"; sleep 1.2; return 0; fi; fi; fi; echo -e "${RED}Error: ${app_name} is not installed!${NC}"; press_enter; return 1
}
launch_audacity() {
launch_gui_app "Audacity" "audacity" "org.audacityteam.Audacity" "Audacity" "audacity" "Audacity/Audacity.exe" "Audacity.Audacity"
}
launch_or_install_picard() {
launch_gui_app "MusicBrainz Picard" "picard" "org.musicbrainz.Picard" "MusicBrainz Picard" "musicbrainz-picard" "MusicBrainz Picard/picard.exe" "MusicBrainz.Picard"
}
launch_vlc() {
launch_gui_app "VLC Media Player" "vlc" "org.videolan.VLC" "VLC" "vlc" "VideoLAN/VLC/vlc.exe" "VideoLAN.VLC"
}
launch_haruna() {
launch_gui_app "Haruna Media Player" "haruna" "org.kde.haruna" "IINA" "iina" "mpv/mpv.exe" ""
}
launch_kodi() {
launch_gui_app "Kodi" "kodi" "tv.kodi.Kodi" "Kodi" "kodi" "Kodi/kodi.exe" "XBMCFoundation.Kodi"
}
launch_audacious() {
launch_gui_app "Audacious Audio Player" "audacious" "org.atheme.audacious" "Audacious" "audacious" "Audacious/bin/audacious.exe" "Audacious.Audacious"
}
launch_strawberry() {
launch_gui_app "Strawberry Music Player" "strawberry" "org.strawberrymusicplayer.strawberry" "Strawberry" "strawberry" "Strawberry Music Player/strawberry.exe" "JonasKvinge.Strawberry"
}
launch_gimp() {
launch_gui_app "GIMP Image Editor" "gimp" "org.gimp.GIMP" "GIMP" "gimp" "GIMP 2/bin/gimp-2.10.exe" "GIMP.GIMP"
}
launch_electricsheep() {
if [ -x "$HOME/.local/share/electricsheep/electricsheep.AppImage" ]; then nohup "$HOME/.local/share/electricsheep/electricsheep.AppImage" &>/dev/null &
echo -e "${GREEN}✓ Electric Sheep launched (AppImage).${NC}"; sleep 1.2; return 0; fi; launch_gui_app "Electric Sheep" "electricsheep" "" "Electric Sheep" "" "ElectricSheep/electricsheep.exe" ""
}
launch_gpu_screen_recorder() {
echo -e "\n${BOLD}${YELLOW}Launching GPU Screen Recorder in a new window...${NC}\n"; if [ "$OS_TYPE" != "linux" ]; then echo -e "${RED}GPU Screen Recorder is available on Linux only.${NC}"; return 1; fi; if command -v gpu-screen-recorder-gtk &>/dev/null; then nohup gpu-screen-recorder-gtk &>/dev/null &
disown 2>/dev/null || true; echo -e "${GREEN}✓ GPU Screen Recorder launched in a new window.${NC}"; return 0; fi; if command -v flatpak &>/dev/null && flatpak info com.dec05eba.gpu_screen_recorder &>/dev/null; then nohup flatpak run --command=gpu-screen-recorder-gtk com.dec05eba.gpu_screen_recorder &>/dev/null &
disown 2>/dev/null || true; echo -e "${GREEN}✓ GPU Screen Recorder launched in a new window.${NC}"; return 0; fi; if command -v gtk-launch &>/dev/null && gtk-launch com.dec05eba.gpu_screen_recorder &>/dev/null; then echo -e "${GREEN}✓ GPU Screen Recorder launched in a new window.${NC}"; return 0; fi; echo -e "${RED}Error: GPU Screen Recorder is not installed.${NC}\n${YELLOW}Install it on Linux with: flatpak install flathub com.dec05eba.gpu_screen_recorder${NC}"; return 1
}
launch_or_install_flatpak_app() {
local app_id="$1"; local bin_name="$2"; local app_name="$3"; local mac_app_name="${4:-$app_name}"; local brew_cask="${5:-$bin_name}"; local win_exe="${6:-$bin_name.exe}"; local winget_id="${7:-}"; launch_gui_app "$app_name" "$bin_name" "$app_id" "$mac_app_name" "$brew_cask" "$win_exe" "$winget_id"
}
launch_logic_pro() {
local file="${1:-}"; if [ "$OS_TYPE" != "macos" ]; then echo -e "\n${BOLD}${RED}⚠️  Apple Logic Pro is exclusively available on macOS.${NC}\n${YELLOW}To work with audio projects on Linux/Windows, REAPER or Audacity is recommended.${NC}"; press_enter; return 1; fi; echo -e "\n${BOLD}${YELLOW}Launching Apple Logic Pro...${NC}\n"; if [ -n "$file" ] && [ -f "$file" ]; then if open -a "Logic Pro" "$file" 2>/dev/null || open -a "Logic Pro X" "$file" 2>/dev/null; then echo -e "${GREEN}✓ Opened '$(basename "$file")' in Apple Logic Pro.${NC}"; sleep 1.2; return 0; fi; else if open -a "Logic Pro" 2>/dev/null || open -a "Logic Pro X" 2>/dev/null; then echo -e "${GREEN}✓ Apple Logic Pro launched.${NC}"; sleep 1.2; return 0; fi; fi; echo -e "${RED}Error: Apple Logic Pro was not found in /Applications.${NC}"; press_enter; return 1
}
launch_garageband() {
local file="${1:-}"; if [ "$OS_TYPE" != "macos" ]; then echo -e "\n${BOLD}${RED}⚠️  Apple GarageBand is exclusively available on macOS.${NC}"; press_enter; return 1; fi; echo -e "\n${BOLD}${YELLOW}Launching Apple GarageBand...${NC}\n"; if [ -n "$file" ] && [ -f "$file" ]; then if open -a "GarageBand" "$file" 2>/dev/null; then echo -e "${GREEN}✓ Opened '$(basename "$file")' in Apple GarageBand.${NC}"; sleep 1.2; return 0; fi; else if open -a "GarageBand" 2>/dev/null; then echo -e "${GREEN}✓ Apple GarageBand launched.${NC}"; sleep 1.2; return 0; fi; fi; echo -e "${RED}Error: Apple GarageBand was not found in /Applications.${NC}"; press_enter; return 1
}
launch_traktor() {
if [ "$OS_TYPE" = "macos" ]; then echo -e "\n${BOLD}${YELLOW}Launching Native Instruments Traktor Pro on macOS...${NC}\n"; if [ -d "/Applications/Native Instruments/Traktor Pro 3/Traktor.app" ] && open "/Applications/Native Instruments/Traktor Pro 3/Traktor.app" 2>/dev/null; then echo -e "${GREEN}✓ Traktor Pro launched successfully.${NC}"; sleep 1.2; return 0; elif [ -d "/Applications/Native Instruments/Traktor Pro 4/Traktor.app" ] && open "/Applications/Native Instruments/Traktor Pro 4/Traktor.app" 2>/dev/null; then echo -e "${GREEN}✓ Traktor Pro launched successfully.${NC}"; sleep 1.2; return 0; elif open -b "com.native-instruments.Traktor" 2>/dev/null; then echo -e "${GREEN}✓ Traktor Pro launched successfully.${NC}"; sleep 1.2; return 0; elif open -a "Traktor Pro 4" 2>/dev/null || open -a "Traktor Pro 3" 2>/dev/null || open -a "Traktor" 2>/dev/null; then echo -e "${GREEN}✓ Traktor Pro launched successfully.${NC}"; sleep 1.2; return 0; else echo -e "${RED}Traktor Pro was not found in /Applications.${NC}"; press_enter; return 1; fi; elif [ "$OS_TYPE" = "windows" ] || [ "$OS_TYPE" = "wsl" ]; then echo -e "\n${BOLD}${YELLOW}Launching Native Instruments Traktor Pro on Windows...${NC}\n"; local traktor_paths=("/c/Program Files/Native Instruments/Traktor Pro 4/Traktor.exe" "/c/Program Files/Native Instruments/Traktor Pro 3/Traktor.exe" "/c/Program Files/Native Instruments/Traktor 2/Traktor.exe" "/c/Program Files (x86)/Native Instruments/Traktor Pro 3/Traktor.exe"); for p in "${traktor_paths[@]}"; do if [ -f "$p" ]; then local win_p; win_p="$(cygpath -w "$p" 2>/dev/null || wslpath -w "$p" 2>/dev/null || echo "$p")"; cmd.exe /c start "" "$win_p" &>/dev/null &
echo -e "${GREEN}✓ Traktor Pro launched successfully.${NC}"; sleep 1.2; return 0; fi; done; if command -v cmd.exe &>/dev/null && cmd.exe /c "where Traktor.exe" &>/dev/null; then cmd.exe /c start "" "Traktor.exe" &>/dev/null &
echo -e "${GREEN}✓ Traktor Pro launched successfully.${NC}"; sleep 1.2; return 0; fi; echo -e "${RED}Traktor Pro was not found in standard Program Files directories.${NC}"; press_enter; return 1; else echo -e "\n${BOLD}${RED}═══════════════════════════════════════════════════════════════════════════════${NC}\n${BOLD}${RED}            ⚠️  PLATFORM NOT SUPPORTED FOR TRAKTOR PRO ⚠️                      ${NC}\n${BOLD}${RED}═══════════════════════════════════════════════════════════════════════════════${NC}\n  • ${BOLD}Platform:${NC}           $(uname -s)\n  • ${BOLD}Status:${NC}             ${RED}Unsupported by Native Instruments${NC}\n  • ${BOLD}Compatibility:${NC}      Native Instruments Traktor Pro is officially supported\n                          on ${BOLD}${GREEN}macOS${NC} and ${BOLD}${CYAN}Windows${NC} only.\n  • ${BOLD}Recommended Alternative:${NC}\n                          For Linux & FreeBSD DJing, ${BOLD}${GREEN}Mixxx${NC} is the industry standard\n                          open-source DJ platform (Flatpak: org.mixxx.Mixxx, pkg: mixxx).\n${BOLD}${RED}═══════════════════════════════════════════════════════════════════════════════${NC}\n"; press_enter; return 1; fi
}
get_traktor_version_mac() {
if [ "$OS_TYPE" != "macos" ]; then echo ""; return 1; fi; local ver=""; if [ -x "/usr/libexec/PlistBuddy" ] && [ -f "/Applications/Native Instruments/Traktor Pro 3/Traktor.app/Contents/Info.plist" ]; then ver="$(/usr/libexec/PlistBuddy -c "Print :CFBundleShortVersionString" "/Applications/Native Instruments/Traktor Pro 3/Traktor.app/Contents/Info.plist" 2>/dev/null | awk '{print $1}')"; elif [ -x "/usr/libexec/PlistBuddy" ] && [ -f "/Applications/Traktor Pro 3.app/Contents/Info.plist" ]; then ver="$(/usr/libexec/PlistBuddy -c "Print :CFBundleShortVersionString" "/Applications/Traktor Pro 3.app/Contents/Info.plist" 2>/dev/null | awk '{print $1}')"; elif [ -x "/usr/libexec/PlistBuddy" ] && [ -f "/Applications/Traktor.app/Contents/Info.plist" ]; then ver="$(/usr/libexec/PlistBuddy -c "Print :CFBundleShortVersionString" "/Applications/Traktor.app/Contents/Info.plist" 2>/dev/null | awk '{print $1}')"; fi; if [ -z "$ver" ] && [ -d "$HOME/Documents/Native Instruments" ]; then ver="$(find "$HOME/Documents/Native Instruments" -maxdepth 1 -type d -name "Traktor 3*" 2>/dev/null | sort -V | tail -n 1 | sed 's/.*Traktor //')"; fi; echo "${ver:-3}"
}
generate_traktor_playlist_from_history() {
if [ "$OS_TYPE" != "macos" ]; then echo -e "\n${BOLD}${RED}═══════════════════════════════════════════════════════════════════════════════${NC}\n${BOLD}${RED}            ⚠️  PLATFORM NOT SUPPORTED FOR TRAKTOR PLAYLISTS ⚠️                 ${NC}\n${BOLD}${RED}═══════════════════════════════════════════════════════════════════════════════${NC}\n  • ${BOLD}Platform:${NC}           $(uname -s)\n  • ${BOLD}Notice:${NC}             Traktor Pro does not run on Linux natively.\n                          This feature is exclusively supported on ${BOLD}${GREEN}macOS${NC}.\n  • ${BOLD}Remote Access:${NC}      To generate Traktor playlists, execute MP Mix Archive Manager\n                          directly on your macOS workstation.\n${BOLD}${RED}═══════════════════════════════════════════════════════════════════════════════${NC}\n"; press_enter; return 1; fi; local gen_py="$SCRIPT_DIR/scripts/generate_traktor_playlist_from_history.py"; local gen_sh="$SCRIPT_DIR/scripts/generate_traktor_playlist_from_history.sh"; if [ -x "$gen_sh" ]; then "$gen_sh" "$@"; elif [ -f "$gen_py" ]; then python3 "$gen_py" "$@"; elif [ -f "./scripts/generate_traktor_playlist_from_history.py" ]; then python3 "./scripts/generate_traktor_playlist_from_history.py" "$@"; else echo -e "\n${RED}Error: generate_traktor_playlist_from_history.py was not found in scripts/!${NC}\n"; press_enter; return 1; fi
}
launch_fl_studio() {
local file="${1:-}"; echo -e "\n${BOLD}${YELLOW}Launching Image-Line FL Studio (Fruity Loops)...${NC}\n"; if [ "$OS_TYPE" = "macos" ]; then local fl_mac_apps=("FL Studio 2024" "FL Studio 21" "FL Studio 20" "FL Studio"); for app in "${fl_mac_apps[@]}"; do if [ -d "/Applications/${app}.app" ] || [ -d "$HOME/Applications/${app}.app" ]; then if [ -n "$file" ] && [ -f "$file" ]; then open -a "$app" "$file" &>/dev/null &
echo -e "${GREEN}✓ Opened '$(basename "$file")' in ${app}.${NC}"; else open -a "$app" &>/dev/null &
echo -e "${GREEN}✓ ${app} launched on macOS.${NC}"; fi; sleep 1.2; return 0; fi; done; if [ -n "$file" ]; then open -a "FL Studio" "$file" 2>/dev/null && return 0; else open -a "FL Studio" 2>/dev/null && return 0; fi; echo -e "${RED}FL Studio was not found in /Applications.${NC}"; press_enter; return 1; elif [ "$OS_TYPE" = "windows" ] || [ "$OS_TYPE" = "wsl" ]; then local fl_win_paths=("/c/Program Files/Image-Line/FL Studio 2024/FL64.exe" "/c/Program Files/Image-Line/FL Studio 21/FL64.exe" "/c/Program Files/Image-Line/FL Studio 20/FL64.exe" "/c/Program Files (x86)/Image-Line/FL Studio 20/FL.exe"); local win_file=""; [ -n "$file" ] && [ -f "$file" ] && win_file="$(cygpath -w "$file" 2>/dev/null || wslpath -w "$file" 2>/dev/null || echo "$file")"; for p in "${fl_win_paths[@]}"; do if [ -f "$p" ]; then local win_p; win_p="$(cygpath -w "$p" 2>/dev/null || wslpath -w "$p" 2>/dev/null || echo "$p")"; if [ -n "$win_file" ]; then cmd.exe /c start "" "$win_p" "$win_file" &>/dev/null &
else cmd.exe /c start "" "$win_p" &>/dev/null &
fi; echo -e "${GREEN}✓ FL Studio launched on Windows.${NC}"; sleep 1.2; return 0; fi; done; if command -v cmd.exe &>/dev/null && cmd.exe /c "where FL64.exe" &>/dev/null; then if [ -n "$win_file" ]; then cmd.exe /c start "" "FL64.exe" "$win_file" &>/dev/null &
else cmd.exe /c start "" "FL64.exe" &>/dev/null &
fi; echo -e "${GREEN}✓ FL Studio launched on Windows.${NC}"; sleep 1.2; return 0; fi; echo -e "${RED}FL Studio was not found in Program Files or PATH on Windows.${NC}"; press_enter; return 1; else if command -v flstudio &>/dev/null; then nohup flstudio ${file:+"$file"} &>/dev/null &
echo -e "${GREEN}✓ FL Studio launched (native wrapper).${NC}"; sleep 1.2; return 0; elif command -v fl-studio &>/dev/null; then nohup fl-studio ${file:+"$file"} &>/dev/null &
echo -e "${GREEN}✓ FL Studio launched (native wrapper).${NC}"; sleep 1.2; return 0; fi; if command -v bottles-cli &>/dev/null; then if bottles-cli list bottles 2>/dev/null | grep -qi "fl.*studio"; then local b_name; b_name=$(bottles-cli list bottles 2>/dev/null | grep -i "fl.*studio" | head -n 1 | awk -F: '{print $1}' | tr -d ' '); nohup bottles-cli run -b "$b_name" -p "FL Studio" &>/dev/null &
echo -e "${GREEN}✓ FL Studio launched via Bottles bottle: $b_name.${NC}"; sleep 1.2; return 0; fi; elif command -v flatpak &>/dev/null && flatpak info com.usebottles.bottles &>/dev/null; then if flatpak run --command=bottles-cli com.usebottles.bottles list bottles 2>/dev/null | grep -qi "fl.*studio"; then flatpak run --command=bottles-cli com.usebottles.bottles run -b "FL Studio" -p "FL Studio" &>/dev/null &
echo -e "${GREEN}✓ FL Studio launched via Bottles Flatpak.${NC}"; sleep 1.2; return 0; fi; fi; local wine_fl_paths=("$HOME/.wine/drive_c/Program Files/Image-Line/FL Studio 2024/FL64.exe" "$HOME/.wine/drive_c/Program Files/Image-Line/FL Studio 21/FL64.exe" "$HOME/.wine/drive_c/Program Files/Image-Line/FL Studio 20/FL64.exe" "$HOME/.local/share/bottles/bottles/FL-Studio/drive_c/Program Files/Image-Line/FL Studio 21/FL64.exe" "$HOME/.var/app/com.usebottles.bottles/data/bottles/bottles/FL-Studio/drive_c/Program Files/Image-Line/FL Studio 21/FL64.exe"); for wp in "${wine_fl_paths[@]}"; do if [ -f "$wp" ] && command -v wine &>/dev/null; then nohup wine "$wp" ${file:+"$file"} &>/dev/null &
echo -e "${GREEN}✓ FL Studio launched via Wine.${NC}"; sleep 1.2; return 0; fi; done; echo -e "${YELLOW}FL Studio is not currently installed or detected on this system.${NC}\nFL Studio is supported on Linux through ${BOLD}Bottles${NC} or ${BOLD}Wine${NC}.\nOptions:\n  1. Install ${CYAN}Bottles${NC} (flatpak install flathub com.usebottles.bottles) and run FL Studio installer.\n  2. Or run: ${CYAN}wine \"FL_Studio_Installer.exe\"${NC}"; press_enter; return 1; fi
}
launch_winamp() {
local file="${1:-}"; if [ "$OS_TYPE" = "windows" ] || [ "$OS_TYPE" = "wsl" ]; then echo -e "\n${BOLD}${YELLOW}Launching Winamp on Windows...${NC}\n"; local win_file=""; [ -n "$file" ] && [ -f "$file" ] && win_file="$(cygpath -w "$file" 2>/dev/null || wslpath -w "$file" 2>/dev/null || echo "$file")"; local winamp_paths=("/c/Program Files (x86)/Winamp/winamp.exe" "/c/Program Files/Winamp/winamp.exe" "$LOCALAPPDATA/Programs/Winamp/winamp.exe"); for p in "${winamp_paths[@]}"; do if [ -f "$p" ]; then local win_p; win_p="$(cygpath -w "$p" 2>/dev/null || wslpath -w "$p" 2>/dev/null || echo "$p")"; if [ -n "$win_file" ]; then cmd.exe /c start "" "$win_p" "$win_file" &>/dev/null &
else cmd.exe /c start "" "$win_p" &>/dev/null &
fi; echo -e "${GREEN}✓ Winamp launched on Windows.${NC}"; sleep 1.2; return 0; fi; done; if command -v cmd.exe &>/dev/null && cmd.exe /c "where winamp.exe" &>/dev/null; then if [ -n "$win_file" ]; then cmd.exe /c start "" "winamp.exe" "$win_file" &>/dev/null &
else cmd.exe /c start "" "winamp.exe" &>/dev/null &
fi; echo -e "${GREEN}✓ Winamp launched on Windows.${NC}"; sleep 1.2; return 0; fi; echo -e "${RED}Winamp was not found on Windows.${NC}"; press_enter; return 1; else echo -e "\n${BOLD}${RED}⚠️  Winamp is a native Windows application.${NC}\n${YELLOW}On Linux & FreeBSD, retro Winamp skin support is available via cliamp retro terminal player or Audacious (audacious -k).${NC}"; press_enter; return 1; fi
}
launch_foobar2000() {
local file="${1:-}"; if [ "$OS_TYPE" = "macos" ]; then echo -e "\n${BOLD}${YELLOW}Launching foobar2000 on macOS...${NC}\n"; if [ -n "$file" ] && [ -f "$file" ]; then if open -a "foobar2000" "$file" 2>/dev/null; then echo -e "${GREEN}✓ Opened '$(basename "$file")' in foobar2000.${NC}"; sleep 1.2; return 0; fi; else if open -a "foobar2000" 2>/dev/null; then echo -e "${GREEN}✓ foobar2000 launched on macOS.${NC}"; sleep 1.2; return 0; fi; fi; echo -e "${RED}foobar2000 was not found in /Applications.${NC}\nInstall with Homebrew: ${CYAN}brew install --cask foobar2000${NC}"; press_enter; return 1; elif [ "$OS_TYPE" = "windows" ] || [ "$OS_TYPE" = "wsl" ]; then echo -e "\n${BOLD}${YELLOW}Launching foobar2000 on Windows...${NC}\n"; local win_file=""; [ -n "$file" ] && [ -f "$file" ] && win_file="$(cygpath -w "$file" 2>/dev/null || wslpath -w "$file" 2>/dev/null || echo "$file")"; local fb_paths=("/c/Program Files/foobar2000/foobar2000.exe" "/c/Program Files (x86)/foobar2000/foobar2000.exe" "$LOCALAPPDATA/Programs/foobar2000/foobar2000.exe"); for p in "${fb_paths[@]}"; do if [ -f "$p" ]; then local win_p; win_p="$(cygpath -w "$p" 2>/dev/null || wslpath -w "$p" 2>/dev/null || echo "$p")"; if [ -n "$win_file" ]; then cmd.exe /c start "" "$win_p" "$win_file" &>/dev/null &
else cmd.exe /c start "" "$win_p" &>/dev/null &
fi; echo -e "${GREEN}✓ foobar2000 launched on Windows.${NC}"; sleep 1.2; return 0; fi; done; if command -v cmd.exe &>/dev/null && cmd.exe /c "where foobar2000.exe" &>/dev/null; then if [ -n "$win_file" ]; then cmd.exe /c start "" "foobar2000.exe" "$win_file" &>/dev/null &
else cmd.exe /c start "" "foobar2000.exe" &>/dev/null &
fi; echo -e "${GREEN}✓ foobar2000 launched on Windows.${NC}"; sleep 1.2; return 0; fi; echo -e "${RED}foobar2000 was not found on Windows.${NC}\nInstall with winget: ${CYAN}winget install foobar2000.foobar2000${NC}"; press_enter; return 1; else echo -e "\n${YELLOW}foobar2000 is officially supported on macOS and Windows.${NC}\nOn Linux/FreeBSD, Strawberry Music Player, VLC, or cliamp is recommended."; press_enter; return 1; fi
}
launch_apple_music() {
local file="${1:-}"; if [ "$OS_TYPE" != "macos" ]; then echo -e "\n${BOLD}${RED}⚠️  Apple Music is exclusively available on macOS.${NC}"; press_enter; return 1; fi; echo -e "\n${BOLD}${YELLOW}Launching Apple Music...${NC}\n"; if [ -n "$file" ] && [ -f "$file" ]; then open -a "Music" "$file" &>/dev/null &
echo -e "${GREEN}✓ Opened '$(basename "$file")' in Apple Music.${NC}"; else open -a "Music" &>/dev/null &
echo -e "${GREEN}✓ Apple Music launched.${NC}"; fi; sleep 1.2; return 0
}
launch_apple_podcasts() {
if [ "$OS_TYPE" != "macos" ]; then echo -e "\n${BOLD}${RED}⚠️  Apple Podcasts is exclusively available on macOS.${NC}"; press_enter; return 1; fi; echo -e "\n${BOLD}${YELLOW}Launching Apple Podcasts...${NC}\n"; open -a "Podcasts" &>/dev/null &
echo -e "${GREEN}✓ Apple Podcasts launched.${NC}"; sleep 1.2; return 0
}
open_mix_in_daw() {
clear; echo -e "${BOLD}${MAGENTA}${S70}${NC}\n${BOLD}${MAGENTA}            OPEN MIX AUDIO FILE (WAV/FLAC) IN DAW                     ${NC}\n${BOLD}${MAGENTA}   (REAPER, Apple Logic Pro, GarageBand, FL Studio, Audacity, etc.)   ${NC}\n${BOLD}${MAGENTA}${S70}${NC}\n"; shopt -s nullglob nocaseglob; local wav_candidates=("${ARCHIVE_DIR}"/*.wav "${MIX_ARCHIVE_DIR:-$SCRIPT_DIR/MIX_ARCHIVE}/CONVERTED_WAV_FILES"/*.wav "${MIX_ARCHIVE_DIR:-$SCRIPT_DIR/MIX_ARCHIVE}"/*.wav "${OUTPUT_DIR}"/*.flac "$PWD"/*.flac); shopt -u nullglob nocaseglob; local selected_file=""; echo -e "${BOLD}How would you like to select the mix to open?${NC}\n  ${BOLD}${CYAN}1)${NC} Search mix by keyword or episode number (e.g., 033, 041, Who am I)\n  ${BOLD}${CYAN}2)${NC} Select from mixes currently in archiver (${#wav_candidates[@]} available)\n  ${BOLD}${CYAN}3)${NC} Enter custom audio file path manually\n  ${BOLD}${CYAN}0)${NC} Cancel and return\n"; read -r -p "Enter choice [0-3]: " s_method; case "$s_method" in 1) read -r -p "Enter search query: " query; [ -z "$query" ] && return 0; local matches=(); for f in "${wav_candidates[@]}"; do if echo "$(basename "$f")" | grep -qi "$query"; then matches+=("$f"); fi; done; if [ ${#matches[@]} -eq 0 ]; then echo -e "\n${RED}No mixes found matching '${query}'.${NC}"; press_enter; return 1; fi; echo -e "\n${BOLD}Matching Mixes:${NC}"; for i in "${!matches[@]}"; do echo -e "  ${CYAN}$((i + 1)))${NC} $(basename "${matches[$i]}")"; done; read -r -p "Select mix number [1-${#matches[@]}]: " pick; if [[ "$pick" =~ ^[0-9]+$ ]] && [ "$pick" -ge 1 ] && [ "$pick" -le "${#matches[@]}" ]; then selected_file="${matches[$((pick - 1))]}"; else echo -e "${RED}Invalid selection.${NC}"; sleep 1; return 1; fi ;; 2) if [ ${#wav_candidates[@]} -eq 0 ]; then echo -e "\n${YELLOW}No audio files found in archive directories.${NC}"; press_enter; return 1; fi; echo -e "\n${BOLD}Available Mixes in Archiver:${NC}"; local max_show=30; for i in "${!wav_candidates[@]}"; do [ "$i" -ge "$max_show" ] && break; echo -e "  ${CYAN}$((i + 1)))${NC} $(basename "${wav_candidates[$i]}")"; done; read -r -p "Select mix number [1-${#wav_candidates[@]}]: " pick; if [[ "$pick" =~ ^[0-9]+$ ]] && [ "$pick" -ge 1 ] && [ "$pick" -le "${#wav_candidates[@]}" ]; then selected_file="${wav_candidates[$((pick - 1))]}"; else echo -e "${RED}Invalid selection.${NC}"; sleep 1; return 1; fi; ;; 3) read -r -p "Enter absolute path to WAV or FLAC file: " selected_file; if [ ! -f "$selected_file" ]; then echo -e "${RED}Error: File does not exist!${NC}"; press_enter; return 1; fi; ;; 0|[qQ]) return 0 ;; *) echo -e "${RED}Invalid choice!${NC}"; sleep 1; return 1; ;; esac; [ -z "$selected_file" ] && return 0; echo -e "\n${BOLD}Selected Mix:${NC} ${GREEN}$(basename "$selected_file")${NC}"; echo -e "Full Path:    ${CYAN}${selected_file}${NC}\n\n${BOLD}Select target DAW / Audio Editor to open this mix in:${NC}\n  ${BOLD}${CYAN}1)${NC} Cockos REAPER DAW          ${DIM}(Cross-Platform: Linux, macOS, Windows, FreeBSD)${NC}\n  ${BOLD}${CYAN}2)${NC} Apple Logic Pro             ${DIM}(macOS Exclusive)${NC}\n  ${BOLD}${CYAN}3)${NC} Apple GarageBand            ${DIM}(macOS Exclusive)${NC}\n  ${BOLD}${CYAN}4)${NC} Image-Line FL Studio (Fruity Loops) ${DIM}(macOS, Windows, Linux via Wine)${NC}\n  ${BOLD}${CYAN}5)${NC} Audacity Audio Editor       ${DIM}(Cross-Platform: Linux, macOS, Windows, FreeBSD)${NC}\n  ${BOLD}${CYAN}6)${NC} Ardour Digital Audio Workstation\n  ${BOLD}${CYAN}7)${NC} Bitwig Studio\n  ${BOLD}${CYAN}0)${NC} Cancel\n"; read -r -p "Enter choice [0-7]: " daw_pick; case "$daw_pick" in 1) echo -e "\n${BOLD}${YELLOW}Opening mix in Cockos REAPER...${NC}\n"; if [ "$OS_TYPE" = "macos" ]; then open -a "REAPER" "$selected_file" &>/dev/null &
elif [ "$OS_TYPE" = "windows" ] || [ "$OS_TYPE" = "wsl" ]; then local win_p; win_p="$(cygpath -w "$selected_file" 2>/dev/null || wslpath -w "$selected_file" 2>/dev/null || echo "$selected_file")"; cmd.exe /c start "" "reaper.exe" "$win_p" &>/dev/null &
elif command -v reaper &>/dev/null; then nohup reaper "$selected_file" &>/dev/null &
elif _has_flatpak "fm.reaper.Reaper"; then nohup flatpak run fm.reaper.Reaper "$selected_file" &>/dev/null &
else echo -e "${RED}REAPER is not installed.${NC}"; press_enter; return 1; fi; echo -e "${GREEN}✓ Mix dispatched to REAPER.${NC}"; sleep 1.2 ;; 2) launch_logic_pro "$selected_file"; ;; 3) launch_garageband "$selected_file" ;; 4) launch_fl_studio "$selected_file"; ;; 5) echo -e "\n${BOLD}${YELLOW}Opening mix in Audacity...${NC}\n"; play_audio_file "audacity" "$selected_file"; echo -e "${GREEN}✓ Mix dispatched to Audacity.${NC}"; sleep 1.2; ;; 6) if [ "$OS_TYPE" = "macos" ]; then open -a "Ardour" "$selected_file" 2>/dev/null &
elif command -v ardour &>/dev/null; then nohup ardour "$selected_file" &>/dev/null &
elif _has_flatpak "org.ardour.Ardour"; then nohup flatpak run org.ardour.Ardour "$selected_file" &>/dev/null &
fi; echo -e "${GREEN}✓ Mix dispatched to Ardour.${NC}"; sleep 1.2 ;; 7) if [ "$OS_TYPE" = "macos" ]; then open -a "Bitwig Studio" "$selected_file" 2>/dev/null &
elif command -v bitwig-studio &>/dev/null; then nohup bitwig-studio "$selected_file" &>/dev/null &
elif _has_flatpak "com.bitwig.BitwigStudio"; then nohup flatpak run com.bitwig.BitwigStudio "$selected_file" &>/dev/null &
fi; echo -e "${GREEN}✓ Mix dispatched to Bitwig Studio.${NC}"; sleep 1.2 ;; 0|[qQ]) return 0; ;; *) echo -e "${RED}Invalid choice!${NC}"; sleep 1; ;; esac
}
generate_spek_single_file() {
echo -e "\n${BOLD}${MAGENTA}${S70}${NC}\n${BOLD}${MAGENTA}   GENERATE SPECTROGRAM USING SPEK FOR WAV/MP3/FLAC (SINGLE FILE)     ${NC}\n${BOLD}${MAGENTA}${S70}${NC}\n\n${CYAN}Please enter the full path to the .FLAC, MP3 or WAV audio mix file:${NC}"; read -e -r -p "Audio Mix Path: " raw_path; local audio_path; audio_path="$(echo "$raw_path" | sed -e "s/^['\"]//" -e "s/['\"]$//" | xargs 2>/dev/null || echo "$raw_path")"; if [ -z "$audio_path" ]; then echo -e "${YELLOW}Operation cancelled.${NC}"; press_enter; return 0; fi; if [[ "$audio_path" == "~"* ]]; then audio_path="${HOME}${audio_path:1}"; fi; if [ "$OS_TYPE" = "wsl" ] && command -v wslpath &>/dev/null; then if [[ "$audio_path" =~ ^[A-Za-z]: ]]; then audio_path="$(wslpath -u "$audio_path" 2>/dev/null || echo "$audio_path")"; fi; elif [ "$OS_TYPE" = "windows" ] && command -v cygpath &>/dev/null; then audio_path="$(cygpath -u "$audio_path" 2>/dev/null || echo "$audio_path")"; fi; if [ ! -f "$audio_path" ]; then echo -e "\n${RED}Error: Audio mix file not found at '$audio_path'!${NC}"; press_enter; return 1; fi; local script="$SCRIPT_DIR/generate_spek.sh"; [ ! -f "$script" ] && script="./generate_spek.sh"; [ ! -f "$script" ] && script="$SCRIPT_DIR/scripts/generate_spek.sh"; if [ -f "$script" ]; then bash "$script" --single-file "$audio_path"; else local dir_path; dir_path="$(cd "$(dirname "$audio_path")" 2>/dev/null && pwd || dirname "$audio_path")"; local base_name; base_name="$(basename "$audio_path")"; local stem="${base_name%.*}"; local out_spek="${dir_path}/${stem}.spek"; local out_spek_png="${dir_path}/${stem}.spek.png"; echo -e "\n${BOLD}${CYAN}Generating Spek spectrogram...${NC}\n  • ${BOLD}Input Audio:${NC}   ${GREEN}${base_name}${NC}\n  • ${BOLD}Location:${NC}      ${dir_path}\n  • ${BOLD}Output File:${NC}   ${stem}.spek"; if ! command -v ffmpeg &>/dev/null; then echo -e "${RED}Error: ffmpeg is required to generate spectrograms.${NC}"; press_enter; return 1; fi; local start_time; start_time=${EPOCHSECONDS:-$(printf "%(%s)T" -1)}; ffmpeg -hide_banner -loglevel error -y -i "$audio_path" -lavfi "showspectrumpic=s=1920x1080:mode=combined:color=intensity:scale=log:legend=1:saturation=1.2" -frames:v 1 "$out_spek_png"; if [ $? -eq 0 ] && [ -f "$out_spek_png" ]; then cp -f "$out_spek_png" "$out_spek"; local sz; sz=$(du -h "$out_spek_png" | cut -f1); local end_time; end_time=${EPOCHSECONDS:-$(printf "%(%s)T" -1)}; local elapsed=$((end_time - start_time)); echo -e "\n${BOLD}${GREEN}${S70}${NC}\n${BOLD}${GREEN}✓ Spek Spectrogram Generated Successfully!${NC}\n  • ${BOLD}Spek File:${NC}      ${GREEN}${out_spek}${NC}\n  • ${BOLD}Image File:${NC}     ${GREEN}${out_spek_png}${NC}\n  • ${BOLD}Saved to:${NC}       ${dir_path}\n  • ${BOLD}Size / Time:${NC}    ${sz} (completed in ${elapsed}s)\n${BOLD}${GREEN}${S70}${NC}\n"; read -r -p "Do you want to view the Spek file after it has been fully generated? [Y/n]: " view_ask; if [[ "$view_ask" =~ ^[Yy]?$ ]] || [ -z "$view_ask" ]; then echo -e "${CYAN}Displaying Spek file in image viewer...${NC}"; open_path "$out_spek_png"; fi; else echo -e "\n${RED}✗ Failed to generate Spek spectrogram for '$base_name'.${NC}"; fi; fi; press_enter
}
generate_spek_multiple_files() {
echo -e "\n${BOLD}${MAGENTA}${S70}${NC}\n${BOLD}${MAGENTA}       GENERATE SPEKS FOR MULTIPLE WAV/MP3/FLAC FILES                 ${NC}\n${BOLD}${MAGENTA}${S70}${NC}\n\n${CYAN}Please enter a path where one or more audio files exist:${NC}"; read -e -r -p "Directory Path: " raw_dir; local dir_path; dir_path="$(echo "$raw_dir" | sed -e "s/^['\"]//" -e "s/['\"]$//" | xargs 2>/dev/null || echo "$raw_dir")"; if [ -z "$dir_path" ]; then echo -e "${YELLOW}Operation cancelled.${NC}"; press_enter; return 0; fi; if [[ "$dir_path" == "~"* ]]; then dir_path="${HOME}${dir_path:1}"; fi; if [ "$OS_TYPE" = "wsl" ] && command -v wslpath &>/dev/null; then if [[ "$dir_path" =~ ^[A-Za-z]: ]]; then dir_path="$(wslpath -u "$dir_path" 2>/dev/null || echo "$dir_path")"; fi; elif [ "$OS_TYPE" = "windows" ] && command -v cygpath &>/dev/null; then dir_path="$(cygpath -u "$dir_path" 2>/dev/null || echo "$dir_path")"; fi; if [ ! -d "$dir_path" ]; then echo -e "\n${RED}Error: Directory not found at '$dir_path'!${NC}"; press_enter; return 1; fi; local script="$SCRIPT_DIR/generate_spek.sh"; [ ! -f "$script" ] && script="./generate_spek.sh"; [ ! -f "$script" ] && script="$SCRIPT_DIR/scripts/generate_spek.sh"; if [ -f "$script" ]; then bash "$script" --multiple-dir "$dir_path"; else dir_path="$(cd "$dir_path" 2>/dev/null && pwd || echo "$dir_path")"; shopt -s nullglob nocaseglob; local audio_files=("$dir_path"/*.flac "$dir_path"/*.wav "$dir_path"/*.mp3 "$dir_path"/*.m4a "$dir_path"/*.ogg "$dir_path"/*.aiff "$dir_path"/*.aif); shopt -u nullglob nocaseglob; if [ ${#audio_files[@]} -eq 0 ]; then echo -e "\n${YELLOW}No WAV, MP3, or FLAC audio files found in '$dir_path'.${NC}"; press_enter; return 0; fi; echo -e "\n${BOLD}${CYAN}Found ${#audio_files[@]} audio file(s) in '$dir_path'. Starting Spek generation...${NC}\n"; local count=0; local success_count=0; local total=${#audio_files[@]}; for f in "${audio_files[@]}"; do count=$((count + 1)); local base; base="$(basename "$f")"; local stem="${base%.*}"; local file_dir; file_dir="$(dirname "$f")"; local out_spek="${file_dir}/${stem}.spek"; local out_spek_png="${file_dir}/${stem}.spek.png"; echo -e "  ${BOLD}[${count}/${total}]${NC} ${CYAN}Analyzing:${NC} ${base}"; ffmpeg -hide_banner -loglevel error -y -i "$f" -lavfi "showspectrumpic=s=1920x1080:mode=combined:color=intensity:scale=log:legend=1:saturation=1.2" -frames:v 1 "$out_spek_png"; if [ $? -eq 0 ] && [ -f "$out_spek_png" ]; then cp -f "$out_spek_png" "$out_spek"; local sz; sz=$(du -h "$out_spek_png" | cut -f1); echo -e "      ${GREEN}✓ Generated:${NC} ${stem}.spek (${sz})"; success_count=$((success_count + 1)); else echo -e "      ${RED}✗ Failed generating Spek for: ${base}${NC}"; fi; done; echo -e "\n${BOLD}${GREEN}${S70}${NC}\n${BOLD}${GREEN}✓ Batch Spek Generation Complete!${NC}\n  • ${BOLD}Success:${NC}        ${success_count} / ${total} Spek files generated\n  • ${BOLD}Location:${NC}       ${dir_path}\n  • ${BOLD}File Format:${NC}    <filename>.spek & <filename>.spek.png\n${BOLD}${GREEN}${S70}${NC}\n"; fi; press_enter
}
manage_spek_generation() {
local script="$SCRIPT_DIR/generate_spek.sh"; [ ! -f "$script" ] && script="./generate_spek.sh"; [ ! -f "$script" ] && script="$SCRIPT_DIR/scripts/generate_spek.sh"; while true; do clear; echo -e "${BOLD}${MAGENTA}${S70}${NC}\n${BOLD}${MAGENTA}       ACOUSTIC SPECTRUM ANALYSER & SPECTROGRAM SUITE (SPEK)          ${NC}\n${BOLD}${MAGENTA}         Cross-Platform: Linux • macOS • Windows • FreeBSD            ${NC}\n${BOLD}${MAGENTA}${S70}${NC}\n\n${BOLD}Select a Spectrogram Generation Option:${NC}\n  ${BOLD}${CYAN} 1)${NC} ${BOLD}${GREEN}Generate Spectrogram using Spek for WAV/MP3/FLAC (Single File)${NC}\n  ${BOLD}${CYAN} 2)${NC} ${BOLD}${GREEN}Generate Speks for Multiple WAV/MP3/FLAC Files (Scan Directory Path)${NC}\n  ${BOLD}${BLUE}──────────────────────────────────────────────────────────────────${NC}\n  ${BOLD}${CYAN} 3)${NC} Generate Spek for Single Mix from Archive (${GREEN}Search or Select & Auto-Open${NC})\n  ${BOLD}${CYAN} 4)${NC} Batch Generate Speks for all FLACs in ${BOLD}FLAC_CONVERTED_OUTPUTS/${NC}\n  ${BOLD}${CYAN} 5)${NC} Batch Generate Speks for all WAVs in ${BOLD}CONVERTED_WAV_FILES/${NC}\n  ${BOLD}${CYAN} 6)${NC} Batch Generate Speks for all Audio Files in Current Directory ($PWD)\n  ${BOLD}${CYAN} 7)${NC} Launch Native Spek GUI Application (${GREEN}Spek.app / spek.exe / spek${NC})\n  ${BOLD}${CYAN} 8)${NC} Browse Generated Spectrograms in ${BOLD}SPEK_OUTPUTS/${NC}\n  ${BOLD}${CYAN} 9)${NC} Sonic Visualiser, SoX & Spectral Analyzers Menu\n  ${BOLD}${CYAN} 0)${NC} Return to Main Menu\n"; read -r -p "Enter choice [0-9]: " sp_choice; case "$sp_choice" in 1) generate_spek_single_file; ;; 2) generate_spek_multiple_files ;; 3) echo ""; bash "$script"; press_enter; ;; 4) echo -e "\n${BOLD}${YELLOW}Batch generating spectrograms for FLAC_CONVERTED_OUTPUTS/...${NC}\n"; bash "$script" -d "FLAC_CONVERTED_OUTPUTS" -o "SPEK_OUTPUTS"; press_enter ;; 5) echo -e "\n${BOLD}${YELLOW}Batch generating spectrograms for CONVERTED_WAV_FILES/...${NC}\n"; bash "$script" -d "CONVERTED_WAV_FILES" -o "SPEK_OUTPUTS"; press_enter; ;; 6) echo -e "\n${BOLD}${YELLOW}Batch generating spectrograms for Current Directory ($PWD)...${NC}\n"; bash "$script" -d "$PWD" -o "SPEK_OUTPUTS"; press_enter ;; 7) echo ""; bash "$script" -g; press_enter; ;; 8) echo -e "\n${CYAN}Opening SPEK_OUTPUTS/ directory...${NC}"; open_path "$PWD/SPEK_OUTPUTS"; sleep 1 ;; 9) echo -e "\n${BOLD}${MAGENTA}=== ADVANCED SPECTRAL ANALYZERS & SOX SUITE ===${NC}\n\n  ${BOLD}${CYAN}1)${NC} Launch Sonic Visualiser (Open mix in Spectrogram pane)\n  ${BOLD}${CYAN}2)${NC} Generate SoX High-Resolution Spectrogram (Viridis, Magma, Rainbow, Mono)\n  ${BOLD}${CYAN}3)${NC} Launch Praat / Kwave / Audacity Spectral Analyzer\n  ${BOLD}${CYAN}0)${NC} Back to Spek Menu\n"; read -r -p "Enter choice [0-3]: " a_choice; case "$a_choice" in 1) read -e -r -p "Enter path to audio mix (or press Enter): " sfile; bash "$script" -i "$sfile" --gui 2>/dev/null || bash "$script"; press_enter; ;; 2) read -e -r -p "Enter path to audio mix: " sxfile; bash "$script" -i "$sxfile" -c "magma"; press_enter ;; 3) read -e -r -p "Enter path to audio mix: " prfile; bash "$script" -i "$prfile" --gui 2>/dev/null || true; press_enter; ;; esac; ;; 0|[qQ]) return 0 ;; *) echo -e "\n${RED}Invalid choice!${NC}"; sleep 1.2 ;; esac; done
}
manage_daws() {
while true; do clear; echo -e "${BOLD}${MAGENTA}====================================================${NC}\n${BOLD}${MAGENTA}     DIGITAL AUDIO WORKSTATIONS (DAWs) & EDITORS    ${NC}\n${BOLD}${MAGENTA}====================================================${NC}"; local current_datetime; current_datetime=$(date "+%A, %B %d, %Y  •  %T %Z"); echo -e "       ${BOLD}${CYAN}📅 ${current_datetime}${NC}"; echo ""; local reaper_badge="${RED}[NOT INSTALLED]${NC}"; local audacity_badge="${RED}[NOT INSTALLED]${NC}"; local ardour_badge="${YELLOW}[AVAILABLE]${NC}"; local lmms_badge="${YELLOW}[AVAILABLE]${NC}"; local bitwig_badge="${YELLOW}[AVAILABLE]${NC}"; local bespoke_badge="${YELLOW}[AVAILABLE]${NC}"; local logic_badge="${YELLOW}[macOS Only]${NC}"; local garage_badge="${YELLOW}[macOS Only]${NC}"; local fl_badge="${YELLOW}[AVAILABLE]${NC}"; local traktor_badge="${YELLOW}[macOS & Windows Only]${NC}"; is_app_installed "reaper" "fm.reaper.Reaper" "REAPER" "REAPER (x64)/reaper.exe" && reaper_badge="${GREEN}✓ INSTALLED${NC}"; is_app_installed "audacity" "org.audacityteam.Audacity" "Audacity" "Audacity/Audacity.exe" && audacity_badge="${GREEN}✓ INSTALLED${NC}"; is_app_installed "ardour" "org.ardour.Ardour" "Ardour" "Ardour/bin/ardour.exe" && ardour_badge="${GREEN}✓ INSTALLED${NC}"; is_app_installed "lmms" "io.lmms.LMMS" "LMMS" "LMMS/lmms.exe" && lmms_badge="${GREEN}✓ INSTALLED${NC}"; is_app_installed "bitwig-studio" "com.bitwig.BitwigStudio" "Bitwig Studio" "Bitwig Studio/bin/BitwigStudio.exe" && bitwig_badge="${GREEN}✓ INSTALLED${NC}"; is_app_installed "bespokesynth" "com.bespokesynth.BespokeSynth" "BespokeSynth" "BespokeSynth/BespokeSynth.exe" && bespoke_badge="${GREEN}✓ INSTALLED${NC}"; if [ "$OS_TYPE" = "macos" ]; then if [ -d "/Applications/Logic Pro.app" ] || [ -d "/Applications/Logic Pro X.app" ] || osascript -e 'id of application "Logic Pro"' &>/dev/null; then logic_badge="${GREEN}✓ INSTALLED${NC}"; else logic_badge="${RED}[NOT INSTALLED]${NC}"; fi; if [ -d "/Applications/GarageBand.app" ] || osascript -e 'id of application "GarageBand"' &>/dev/null; then garage_badge="${GREEN}✓ INSTALLED${NC}"; else
garage_badge="${RED}[NOT INSTALLED]${NC}"; fi; if [ -d "/Applications/Native Instruments/Traktor Pro 3/Traktor.app" ] || [ -d "/Applications/Native Instruments/Traktor Pro 4/Traktor.app" ] || [ -d "/Applications/Traktor Pro 4.app" ] || [ -d "/Applications/Traktor Pro 3.app" ] || [ -d "/Applications/Traktor.app" ] || osascript -e 'id of application "Traktor"' &>/dev/null; then traktor_badge="${GREEN}✓ INSTALLED${NC}"; else traktor_badge="${RED}[NOT INSTALLED]${NC}"; fi; if [ -d "/Applications/FL Studio 2024.app" ] || [ -d "/Applications/FL Studio 21.app" ] || [ -d "/Applications/FL Studio.app" ]; then fl_badge="${GREEN}✓ INSTALLED${NC}"; fi; elif [ "$OS_TYPE" = "windows" ] || [ "$OS_TYPE" = "wsl" ]; then if [ -f "/c/Program Files/Native Instruments/Traktor Pro 4/Traktor.exe" ] || [ -f "/c/Program Files/Native Instruments/Traktor Pro 3/Traktor.exe" ]; then traktor_badge="${GREEN}✓ INSTALLED${NC}"; else traktor_badge="${YELLOW}[AVAILABLE]${NC}"; fi; if [ -f "/c/Program Files/Image-Line/FL Studio 2024/FL64.exe" ] || [ -f "/c/Program Files/Image-Line/FL Studio 21/FL64.exe" ]; then fl_badge="${GREEN}✓ INSTALLED${NC}"; fi; fi; echo -e "${BOLD}Select a DAW or Audio Editor to launch (or install):${NC}\n  ${BOLD}${CYAN} 1)${NC} Launch REAPER DAW (${reaper_badge}${NC})\n  ${BOLD}${CYAN} 2)${NC} Launch Audacity Audio Editor (${audacity_badge}${NC})\n  ${BOLD}${CYAN} 3)${NC} Launch / Install Ardour DAW (${ardour_badge}${NC})\n  ${BOLD}${CYAN} 4)${NC} Launch / Install LMMS Studio (${lmms_badge}${NC})\n  ${BOLD}${CYAN} 5)${NC} Launch / Install Bitwig Studio (${bitwig_badge}${NC})\n  ${BOLD}${CYAN} 6)${NC} Launch / Install Bespoke Synth (${bespoke_badge}${NC})\n  ${BOLD}${CYAN} 7)${NC} Launch Apple Logic Pro (${logic_badge}${NC})\n  ${BOLD}${CYAN} 8)${NC} Launch Apple GarageBand (${garage_badge}${NC})\n  ${BOLD}${CYAN} 9)${NC} Launch Image-Line FL Studio / Fruity Loops (${fl_badge}${NC})\n  ${BOLD}${CYAN}10)${NC} Launch Native Instruments Traktor Pro (${traktor_badge}${NC})\n  ${BOLD}${CYAN}11)${NC} Launch Traktor Live Monitor & Audio Recorder (${GREEN}New Window - CPU, Decks, Recording, Audio I/O${NC})"; if [ "$OS_TYPE" = "macos" ]; then local t_ver; t_ver="$(get_traktor_version_mac 2>/dev/null || echo "3")"; if [ -n "$t_ver" ] && [ "$t_ver" != "3" ]; then echo -e "  ${BOLD}${CYAN}12)${NC} Generate Playlist from History Files on Traktor 3 (${GREEN}v${t_ver} Key Sorted / Decks Ready${NC})"; else echo -e "  ${BOLD}${CYAN}12)${NC} Generate Playlist from History Files on Traktor 3 (${GREEN}Key Sorted / Decks Ready${NC})"; fi; echo -e "  ${BOLD}${BLUE}────────────────────────────────────────────────────${NC}\n  ${BOLD}${CYAN}13)${NC} ${BOLD}${GREEN}Open Mix WAV/FLAC Audio File in DAW...${NC} (Reaper, Logic Pro, FL Studio)\n  ${BOLD}${CYAN} 0)${NC} Return to Main Menu"; echo ""; read -r -p "Enter choice [0-13]: " d_choice; else echo -e "  ${BOLD}${BLUE}────────────────────────────────────────────────────${NC}\n  ${BOLD}${CYAN}12)${NC} ${BOLD}${GREEN}Open Mix WAV/FLAC Audio File in DAW...${NC} (Reaper, Logic Pro, FL Studio)\n  ${BOLD}${CYAN} 0)${NC} Return to Main Menu"; echo ""; read -r -p "Enter choice [0-12]: " d_choice; fi; case "$d_choice" in 1) launch_gui_app "REAPER" "reaper" "fm.reaper.Reaper" "REAPER" "reaper" "REAPER (x64)/reaper.exe" "Cockos.REAPER"; ;; 2) launch_audacity ;; 3) launch_gui_app "Ardour" "ardour" "org.ardour.Ardour" "Ardour" "ardour" "Ardour/bin/ardour.exe" ""; ;; 4) launch_gui_app "LMMS" "lmms" "io.lmms.LMMS" "LMMS" "lmms" "LMMS/lmms.exe" "LMMS.LMMS" ;; 5) launch_gui_app "Bitwig Studio" "bitwig-studio" "com.bitwig.BitwigStudio" "Bitwig Studio" "bitwig-studio" "Bitwig Studio/bin/BitwigStudio.exe" "Bitwig.BitwigStudio"; ;; 6) launch_gui_app "Bespoke Synth" "bespokesynth" "com.bespokesynth.BespokeSynth" "BespokeSynth" "bespoke-synth" "BespokeSynth/BespokeSynth.exe" "" ;; 7) launch_logic_pro; ;; 8) launch_garageband ;; 9) launch_fl_studio
;; 10) launch_traktor ;; 11) launch_traktor_monitor_window; ;; 12) if [ "$OS_TYPE" = "macos" ]; then generate_traktor_playlist_from_history; else open_mix_in_daw; fi ;; 13) if [ "$OS_TYPE" = "macos" ]; then open_mix_in_daw; else echo -e "\n${RED}Invalid choice!${NC}"; sleep 1.2; fi ;; 0|[qQ]) return 0; ;; *) echo -e "\n${RED}Invalid choice!${NC}"; sleep 1.2; ;; esac; done
}
play_audio_file() {
local player="${1:-${DEFAULT_AUDIO_PLAYER:-mp_liquid_glass}}"; local file="$2"; local seek_pos="${3:-}"; local mode="${4:-MIX_ARCHIVE}"; [ -z "$file" ] && return 1; file="$(realpath "$file" 2>/dev/null || echo "$file")"; case "$player" in
mp_liquid_glass|liquid_glass|liquid|glass)
    launch_mp_audio_player_liquid_glass
    local mp_py="$SCRIPT_DIR/MP_Audio_Player.py"; [ ! -f "$mp_py" ] && mp_py="$SCRIPT_DIR/scripts/MP_Audio_Player.py"
    if [ -f "$mp_py" ]; then
        local play_args=("--play" "$file"); [ -n "$seek_pos" ] && [ "$seek_pos" != "0" ] && [ "$seek_pos" != "0.0" ] && play_args+=(--seek-to "$seek_pos"); [ "$mode" = "MUSIC" ] && play_args+=(--music-mode)
        (sleep 0.8; python3 "$mp_py" "${play_args[@]}" &>/dev/null) &
    fi ;;
mp_audio_player|mp_player|mp-player|mpplayer|mp) local mp_py="$SCRIPT_DIR/MP_Audio_Player.py"; [ ! -f "$mp_py" ] && mp_py="$SCRIPT_DIR/scripts/MP_Audio_Player.py"; if [ -f "$mp_py" ]; then local play_args=("--play" "$file"); [ -n "$seek_pos" ] && [ "$seek_pos" != "0" ] && [ "$seek_pos" != "0.0" ] && play_args+=(--seek-to "$seek_pos"); [ "$mode" = "MUSIC" ] && play_args+=(--music-mode); python3 "$mp_py" "${play_args[@]}" &>/dev/null; fi; ;; audacious) if get_audacious_track_info 2>/dev/null && [ "$AUDACIOUS_STATE" = "playing" ]; then if [ "$AUDACIOUS_RESOLVED_PATH" = "$file" ] || [ "$AUDACIOUS_RAW_PATH" = "$file" ]; then align_mix_windows_on_screen --expect-audacious; return 0; fi; fi; if command -v audacious &>/dev/null; then nohup audacious "$file" &>/dev/null &
disown 2>/dev/null || true; elif _has_flatpak "org.atheme.audacious"; then nohup flatpak run org.atheme.audacious "$file" &>/dev/null &
disown 2>/dev/null || true; elif [ "$OS_TYPE" = "macos" ]; then open -a Audacious "$file" &>/dev/null &
fi; if [ -n "$seek_pos" ] && [ "$seek_pos" != "0" ] && [ "$seek_pos" != "0.0" ]; then (for _i in {1..20}; do sleep 0.2; command -v audtool &>/dev/null && audtool playback-seek "${seek_pos%.*}" &>/dev/null && break; done) & fi; align_mix_windows_on_screen --expect-audacious; ;; cliamp) local cliamp_bin="cliamp"; command -v cliamp &>/dev/null || cliamp_bin="$SCRIPT_DIR/bin/cliamp"; [ ! -x "$cliamp_bin" ] && cliamp_bin="$HOME/.local/bin/cliamp"; if pgrep -x cliamp &>/dev/null; then "$cliamp_bin" queue "$file" 2>/dev/null || true; sleep 0.3; "$cliamp_bin" play 2>/dev/null || true; else local full_cmd="\"$cliamp_bin\" queue \"$file\" 2>/dev/null; \"$cliamp_bin\" --auto-play play 2>/dev/null || \"$cliamp_bin\" --auto-play"; launch_in_terminal "cliamp - $(basename "$file")" "$full_cmd" "window"; fi ;; strawberry) if get_strawberry_track_info 2>/dev/null && [ "$STRAWBERRY_STATE" = "playing" ]; then if [ "$STRAWBERRY_RESOLVED_PATH" = "$file" ] || [ "$STRAWBERRY_RAW_PATH" = "$file" ]; then align_mix_windows_on_screen --expect-strawberry; return 0; fi; fi; if command -v strawberry &>/dev/null; then nohup strawberry "$file" &>/dev/null &
disown 2>/dev/null || true; elif _has_flatpak "org.strawberrymusicplayer.strawberry"; then nohup flatpak run org.strawberrymusicplayer.strawberry "$file" &>/dev/null &
disown 2>/dev/null || true; elif [ "$OS_TYPE" = "macos" ]; then open -a Strawberry "$file" &>/dev/null &
fi; if [ -n "$seek_pos" ] && [ "$seek_pos" != "0" ] && [ "$seek_pos" != "0.0" ]; then (for _i in {1..20}; do sleep 0.3; command -v playerctl &>/dev/null && playerctl -p strawberry position "${seek_pos%.*}" &>/dev/null && break; done) & fi; align_mix_windows_on_screen --expect-strawberry; ;; vlc) if command -v vlc &>/dev/null; then nohup vlc "$file" &>/dev/null &
elif _has_flatpak "org.videolan.VLC"; then nohup flatpak run org.videolan.VLC "$file" &>/dev/null &
elif [ "$OS_TYPE" = "macos" ]; then open -a VLC "$file" &>/dev/null &
fi ;; haruna) if command -v haruna &>/dev/null; then nohup haruna "$file" &>/dev/null &
elif _has_flatpak "org.kde.haruna"; then nohup flatpak run org.kde.haruna "$file" &>/dev/null &
fi ;; kodi) if command -v kodi &>/dev/null; then nohup kodi "$file" &>/dev/null &
elif _has_flatpak "tv.kodi.Kodi"; then nohup flatpak run tv.kodi.Kodi "$file" &>/dev/null &
fi ;; audacity) if command -v audacity &>/dev/null; then nohup audacity "$file" &>/dev/null &
elif _has_flatpak "org.audacityteam.Audacity"; then nohup flatpak run org.audacityteam.Audacity "$file" &>/dev/null &
fi ;; mpv) if command -v mpv &>/dev/null; then nohup mpv "$file" &>/dev/null &
fi ;; winamp) launch_winamp "$file"; ;; foobar2000) launch_foobar2000 "$file" ;; music|apple_music) launch_apple_music "$file"; ;; garageband) launch_garageband "$file" ;; logic|logic_pro) launch_logic_pro "$file"; ;; reaper) if [ "$OS_TYPE" = "macos" ]; then open -a "REAPER" "$file" &>/dev/null &
elif [ "$OS_TYPE" = "windows" ] || [ "$OS_TYPE" = "wsl" ]; then local win_p; win_p="$(cygpath -w "$file" 2>/dev/null || wslpath -w "$file" 2>/dev/null || echo "$file")"; cmd.exe /c start "" "reaper.exe" "$win_p" &>/dev/null &
elif command -v reaper &>/dev/null; then nohup reaper "$file" &>/dev/null &
elif _has_flatpak "fm.reaper.Reaper"; then nohup flatpak run fm.reaper.Reaper "$file" &>/dev/null &
fi ;; flstudio|fl_studio) launch_fl_studio "$file"; ;; *) if command -v "$player" &>/dev/null; then nohup "$player" "$file" &>/dev/null &
elif [ "$player" != "audacious" ] && (command -v audacious &>/dev/null || _has_flatpak "org.atheme.audacious"); then play_audio_file "audacious" "$file"; elif [ "$player" != "strawberry" ] && command -v strawberry &>/dev/null; then play_audio_file "strawberry" "$file"; else play_audio_file "cliamp" "$file"; fi ;; esac; if [ "${AUTO_SHOW_PLAYING_ASSETS:-true}" = "true" ] && [ "${SKIP_PLAYING_ASSETS:-0}" -ne 1 ]; then auto_show_playing_mix_assets "$file" "$player"; fi
}
collect_converted_mix_dirs() {
local -a dirs=(); local seen="|"; local cand resolved rel adir kind
add_converted_dir() {
cand="$1"; [ -n "$cand" ] || return 0; if is_remote_or_cloud_path "$cand" && ! is_internet_connected; then return 0; fi; [ -d "$cand" ] || return 0; resolved="$(cd "$cand" 2>/dev/null && pwd -P)" || return 0; case "$seen" in *"|$resolved|"*) return 0 ;; esac; seen="${seen}${resolved}|"; dirs+=("$resolved")
}
for rel in "${OUTPUT_DIR:-}" "${MP3_OUTPUT_DIR:-}" "${WAV_OUTPUT_DIR:-}"; do [ -z "$rel" ] && continue; add_converted_dir "$rel"; if [ -n "${MIX_ARCHIVE_DIR:-}" ]; then add_converted_dir "${MIX_ARCHIVE_DIR%/}/$rel"; fi; done; if command -v get_all_mix_archive_dirs &>/dev/null; then while IFS= read -r adir; do [ -z "$adir" ] && continue; case "$adir" in
*FLAC_CONVERTED_OUTPUTS|*FLAC_CONVERTED_OUTPUTS/| *MP3_CONVERTED_OUTPUTS|*MP3_CONVERTED_OUTPUTS/| *WAV_CONVERTED_OUTPUTS|*WAV_CONVERTED_OUTPUTS/)
add_converted_dir "$adir" ;; esac; for kind in FLAC_CONVERTED_OUTPUTS MP3_CONVERTED_OUTPUTS WAV_CONVERTED_OUTPUTS; do add_converted_dir "${adir%/}/$kind"; done; done < <(get_all_mix_archive_dirs); fi; [ ${#dirs[@]} -gt 0 ] && printf '%s\n' "${dirs[@]}"
}
select_startup_mix() {
local mode="${AUTO_PLAY_MIX_SELECTION:-latest}"; local list d f found_any=0; list="$(mktemp "${TMPDIR:-/tmp}/sof_startup_XXXXXX")"; while IFS= read -r d; do if is_remote_or_cloud_path "$d" && ! is_internet_connected; then continue; fi; [ -d "$d" ] || continue; for f in "$d"/*.flac "$d"/*.mp3 "$d"/*.wav "$d"/*.FLAC "$d"/*.MP3 "$d"/*.WAV; do [ -f "$f" ] || continue; printf '%s\n' "$f" >> "$list"; found_any=1; done; done < <(collect_converted_mix_dirs); if [ "$found_any" -eq 0 ] || [ ! -s "$list" ]; then rm -f "$list"; return 1; fi
python3 - "$mode" "$list" << 'PY'
import os, random, re, sys
mode = sys.argv[1]
def paths_open_for_write(candidates):
    wanted = set()
    for path in candidates:
        wanted.add(path)
        try:
            wanted.add(os.path.realpath(path))
        except OSError:
            pass
    writing = set()
    if not os.path.isdir("/proc"):
        return writing
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        fd_dir = "/proc/" + pid + "/fd"
        try:
            fds = os.listdir(fd_dir)
        except OSError:
            continue
        for fd in fds:
            fd_path = fd_dir + "/" + fd
            try:
                target = os.path.realpath(os.readlink(fd_path))
            except OSError:
                continue
            if target not in wanted:
                continue
            try:
                info = open("/proc/" + pid + "/fdinfo/" + fd, encoding="utf-8", errors="ignore").read()
            except OSError:
                continue
            flags = ""
            for line in info.splitlines():
                if line.startswith("flags:"):
                    parts = line.split()
                    flags = parts[1] if len(parts) > 1 else ""
                    break
            try:
                if int(flags, 8) & 3:
                    writing.add(target)
            except ValueError:
                continue
    return writing
raw_files = []
seen = set()
with open(sys.argv[2], encoding="utf-8", errors="ignore") as fh:
    for line in fh:
        path = line.strip()
        if not path or path in seen or not os.path.isfile(path):
            continue
        seen.add(path)
        raw_files.append(path)
writing = paths_open_for_write(raw_files)
files = []
for path in raw_files:
    try:
        if os.path.getsize(path) <= 0:
            continue
        if os.path.realpath(path) in writing:
            continue
    except OSError:
        continue
    files.append(path)
if not files:
    sys.exit(1)
def stem(path):
    return os.path.splitext(os.path.basename(path))[0].lower()
rank = {".flac": 0, ".wav": 1, ".mp3": 2}
def prefer_sibling(chosen):
    chosen_stem = stem(chosen)
    siblings = [path for path in files if stem(path) == chosen_stem]
    siblings.sort(key=lambda path: (rank.get(os.path.splitext(path)[1].lower(), 9), -os.path.getmtime(path)))
    return siblings[0]
if mode == "random":
    pick = prefer_sibling(random.choice(files))
elif mode == "latest":
    pick = prefer_sibling(max(files, key=lambda path: os.path.getmtime(path)))
else:
    try:
        pattern = re.compile(mode, re.IGNORECASE)
        matched = [path for path in files if pattern.search(os.path.basename(path))]
    except re.error:
        needle = mode.lower()
        matched = [path for path in files if needle in os.path.basename(path).lower()]
    pool = matched or files
    pool.sort(key=lambda path: os.path.getmtime(path), reverse=True)
    pick = prefer_sibling(pool[0])
print(pick)
PY
local py_rc=$?; rm -f "$list"; return "$py_rc"
}
same_mix_file() {
local left="$1" right="$2"; [ -n "$left" ] && [ -n "$right" ] || return 1; [ "$left" = "$right" ] && return 0; local left_real right_real; left_real="$(readlink -f "$left" 2>/dev/null || echo "$left")"; right_real="$(readlink -f "$right" 2>/dev/null || echo "$right")"; [ "$left_real" = "$right_real" ] && return 0; [ "$(basename "$left_real")" = "$(basename "$right_real")" ]
}
audacious_dbus_ready() {
qdbus org.atheme.audacious /org/atheme/audacious org.atheme.audacious.Length &>/dev/null
}
play_audacious_file_now() {
local file="$1"; [ -s "$file" ] || return 1; if ! audacious_dbus_ready; then if command -v audacious &>/dev/null; then nohup audacious &>/dev/null &
disown 2>/dev/null || true; elif _has_flatpak "org.atheme.audacious"; then nohup flatpak run org.atheme.audacious &>/dev/null &
disown 2>/dev/null || true; elif [ "${OS_TYPE:-}" = "macos" ]; then open -a Audacious "$file" &>/dev/null &
return 0; else return 1; fi; local wait_i; for wait_i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30 31 32 33 34 35 36 37 38 39 40; do audacious_dbus_ready && break; sleep 0.5; done; fi; audacious_dbus_ready || return 1
python3 - "$file" << 'PY'
import os, sys, time, urllib.parse
target = os.path.realpath(sys.argv[1])
target_base = os.path.basename(target)
uri = "file://" + urllib.parse.quote(target)
def normalize(raw):
    text = urllib.parse.unquote(str(raw or ""))
    if text.startswith("file://"):
        text = text[7:]
    elif text.startswith("file:"):
        text = text[5:]
    if text and os.path.exists(text):
        text = os.path.realpath(text)
    return text
def matches(raw):
    path = normalize(raw)
    return path == target or os.path.basename(path) == target_base
try:
    import dbus
except Exception:
    sys.exit(1)
bus = dbus.SessionBus()
obj = bus.get_object("org.atheme.audacious", "/org/atheme/audacious")
player = dbus.Interface(obj, "org.atheme.audacious")
def length():
    return int(player.Length())
def position():
    return int(player.Position())
def song_at(index):
    return player.SongFilename(dbus.UInt32(index))
def current_matches():
    try:
        return matches(song_at(position()))
    except Exception:
        return False
last = None
stable = 0
deadline = time.time() + 4
while time.time() < deadline:
    try:
        current = length()
    except Exception:
        time.sleep(0.2)
        continue
    if current == last:
        stable += 1
        if stable >= 3:
            break
    else:
        stable = 0
        last = current
    time.sleep(0.2)
def find_index():
    total = length()
    for index in range(total):
        try:
            if matches(song_at(index)):
                return index
        except Exception:
            continue
    return None
def ensure_index():
    found = find_index()
    if found is not None:
        return found
    try:
        player.Add(uri)
    except Exception:
        return None
    wait_until = time.time() + 2.5
    while time.time() < wait_until:
        found = find_index()
        if found is not None:
            return found
        time.sleep(0.15)
    return None
try:
    shuffle_on = bool(player.Shuffle())
except Exception:
    shuffle_on = False
for _attempt in range(3):
    found = ensure_index()
    if found is None:
        time.sleep(0.3)
        continue
    try:
        if shuffle_on and bool(player.Shuffle()):
            player.ToggleShuffle()
        player.Stop()
        player.Jump(dbus.UInt32(found))
        player.Play()
        if shuffle_on and not bool(player.Shuffle()):
            player.ToggleShuffle()
    except Exception:
        time.sleep(0.3)
        continue
    held = True
    for _sample in range(4):
        time.sleep(0.2)
        if not current_matches():
            held = False
            break
    if held:
        sys.exit(0)
sys.exit(1)
PY
}
execute_startup_autoplay() {
if [ "${AUTO_PLAY_ON_STARTUP:-true}" != "true" ]; then return 0; fi; local player="${DEFAULT_AUDIO_PLAYER:-mp_audio_player}"; local SKIP_PLAYING_ASSETS=1; local current_path=""; local current_state=""; if get_mp_audio_player_track_info 2>/dev/null && [ "$MP_PLAYER_STATE" = "playing" ] && [ -n "${MP_PLAYER_RAW_PATH:-}" ]; then STARTUP_AUTOPLAY_NOTICE="Already playing: $(basename "$MP_PLAYER_RAW_PATH") (MP Audio Player)"; return 0; fi; if get_audacious_track_info 2>/dev/null && [ "$AUDACIOUS_STATE" = "playing" ] && [ -n "${AUDACIOUS_RESOLVED_PATH:-}" ]; then STARTUP_AUTOPLAY_NOTICE="Already playing: $(basename "$AUDACIOUS_RESOLVED_PATH") (Audacious)"; return 0; fi; if get_strawberry_track_info 2>/dev/null && [ "$STRAWBERRY_STATE" = "playing" ] && [ -n "${STRAWBERRY_RESOLVED_PATH:-}" ]; then STARTUP_AUTOPLAY_NOTICE="Already playing: $(basename "$STRAWBERRY_RESOLVED_PATH") (Strawberry)"; return 0; fi; if get_cliamp_track_info 2>/dev/null && [ "$CLIAMP_STATE" = "playing" ] && [ -n "${CLIAMP_RESOLVED_PATH:-}" ]; then STARTUP_AUTOPLAY_NOTICE="Already playing: $(basename "$CLIAMP_RESOLVED_PATH") (cliamp)"; return 0; fi; local detected_now=""; detected_now="$(detect_currently_playing_mix 2>/dev/null || true)"; if [ -n "$detected_now" ] && [ -f "$detected_now" ]; then STARTUP_AUTOPLAY_NOTICE="Already playing: $(basename "$detected_now")"; return 0; fi; local resume_file="$HOME/.config/mix-manager/playback_resume.json"; local state_file="$HOME/.config/mix-manager/mp_player_state.json"; local resume_info=""; if [ -f "$resume_file" ]; then resume_info=$(python3 - "$resume_file" << 'PY' 2>/dev/null || true
import sys, json, os
try:
    with open(sys.argv[1], "r", encoding="utf-8") as f:
        d = json.load(f)
    p = d.get("path") or ""
    if p and os.path.isfile(p):
        pos = d.get("position_sec", 0.0) or 0.0
        dur = d.get("duration_sec", 0.0) or 0.0
        plr = d.get("player", "") or ""
        mode = d.get("mode", "MIX_ARCHIVE") or "MIX_ARCHIVE"
        print(f"{p}\t{pos}\t{dur}\t{plr}\t{mode}")
except Exception: pass
PY
); fi; if [ -z "$resume_info" ] && [ -f "$state_file" ]; then resume_info=$(python3 - "$state_file" << 'PY' 2>/dev/null || true
import sys, json, os
try:
    with open(sys.argv[1], "r", encoding="utf-8") as f:
        d = json.load(f)
    p = d.get("path") or ""
    if p and os.path.isfile(p):
        pos = d.get("position_sec", 0.0) or 0.0
        dur = d.get("duration_sec", 0.0) or 0.0
        mode = d.get("mode", "MIX_ARCHIVE") or "MIX_ARCHIVE"
        print(f"{p}\t{pos}\t{dur}\tmp_audio_player\t{mode}")
except Exception: pass
PY
); fi; if [ -z "$resume_info" ]; then return 0; fi; local selected_mix="" resume_pos=0 resume_dur=0 saved_player="" saved_mode="MIX_ARCHIVE"; IFS=$'\t' read -r selected_mix resume_pos resume_dur saved_player saved_mode <<< "$resume_info"; [ -z "$selected_mix" ] || [ ! -f "$selected_mix" ] && return 0; if is_remote_or_cloud_path "$selected_mix" && ! is_internet_connected; then STARTUP_AUTOPLAY_NOTICE="Previous mix is on cloud storage (offline, playback skipped)"; return 0; fi; player="${DEFAULT_AUDIO_PLAYER:-${saved_player:-mp_liquid_glass}}"; local player_display="$player"; case "$player" in mp_liquid_glass|liquid_glass|liquid|glass) player_display="MP Liquid Glass Player" ;; mp_audio_player|mp_player|mp-player|mpplayer|mp) player_display="MP Audio Player" ;; audacious) player_display="Audacious" ;; strawberry) player_display="Strawberry" ;; cliamp) player_display="cliamp" ;; esac; local pos_fmt; if command -v _fmt_sec &>/dev/null; then pos_fmt=$(_fmt_sec "${resume_pos%.*}"); else pos_fmt="${resume_pos%.*}s"; fi; STARTUP_AUTOPLAY_NOTICE="Resumed playback: $(basename "$selected_mix") at ${pos_fmt} (${player_display})"; if [ "$player" = "audacious" ]; then if same_mix_file "${AUDACIOUS_RESOLVED_PATH:-}" "$selected_mix" 2>/dev/null; then qdbus org.atheme.audacious /org/atheme/audacious org.atheme.audacious.Play &>/dev/null || audtool playback-play &>/dev/null || true; if [ -n "$resume_pos" ] && [ "$resume_pos" != "0" ] && [ "$resume_pos" != "0.0" ]; then audtool playback-seek "${resume_pos%.*}" &>/dev/null || true; fi; else play_audio_file "$player" "$selected_mix" "$resume_pos" "$saved_mode"; fi; else play_audio_file "$player" "$selected_mix" "$resume_pos" "$saved_mode"; fi; local found_cover=""; if [ "${AUTO_SHOW_COVER_ON_STARTUP:-false}" = "true" ]; then found_cover=$(find_mix_cover "$selected_mix" 2>/dev/null); if [ -n "$found_cover" ] && [ -f "$found_cover" ]; then open_cover_art_window "$found_cover"; fi; fi; local align_args=(); [ "$player" = "audacious" ] && align_args+=(--expect-audacious); [ "$player" = "strawberry" ] && align_args+=(--expect-strawberry); [ -n "$found_cover" ] && align_args+=(--expect-cover); align_mix_windows_on_screen "${align_args[@]}"; if [ "${AUTO_PLAY_YOUTUBE_ON_STARTUP:-false}" = "true" ] && [ -n "${STARTUP_YOUTUBE_URL:-}" ]; then (sleep 0.6; open_video_url "$STARTUP_YOUTUBE_URL" &>/dev/null || true) &
fi; return 0
}
configure_audio_player_and_startup() {
while true; do clear; echo -e "${BOLD}${MAGENTA}${S70}${NC}\n${BOLD}${MAGENTA}      DEFAULT AUDIO PLAYER & STARTUP AUTOPLAY CONFIGURATION           ${NC}\n${BOLD}${MAGENTA}${S70}${NC}\n"; local audacious_st="Not Installed"; (command -v audacious &>/dev/null || _has_flatpak "org.atheme.audacious") && audacious_st="${GREEN}Installed${NC}"; local cliamp_st="Not Installed"; (command -v cliamp &>/dev/null || [ -x "$SCRIPT_DIR/bin/cliamp" ] || [ -x "$HOME/.local/bin/cliamp" ]) && cliamp_st="${GREEN}Installed${NC}"; local straw_st="Not Installed"; (command -v strawberry &>/dev/null || _has_flatpak "org.strawberrymusicplayer.strawberry") && straw_st="${GREEN}Installed${NC}"; local vlc_st="Not Installed"; (command -v vlc &>/dev/null || _has_flatpak "org.videolan.VLC") && vlc_st="${GREEN}Installed${NC}"; local haruna_st="Not Installed"; (command -v haruna &>/dev/null || _has_flatpak "org.kde.haruna") && haruna_st="${GREEN}Installed${NC}"; local kodi_st="Not Installed"; (command -v kodi &>/dev/null || _has_flatpak "tv.kodi.Kodi") && kodi_st="${GREEN}Installed${NC}"; local audacity_st="Not Installed"; (command -v audacity &>/dev/null || _has_flatpak "org.audacityteam.Audacity") && audacity_st="${GREEN}Installed${NC}"; local mpv_st="Not Installed"; command -v mpv &>/dev/null && mpv_st="${GREEN}Installed${NC}"; local foobar_st="Not Installed"; (command -v foobar2000 &>/dev/null || [ -d "/Applications/foobar2000.app" ] || [ -f "/c/Program Files/foobar2000/foobar2000.exe" ]) && foobar_st="${GREEN}Installed${NC}"; local winamp_st="Not Installed"; ([ -f "/c/Program Files (x86)/Winamp/winamp.exe" ] || [ -f "/c/Program Files/Winamp/winamp.exe" ] || command -v winamp &>/dev/null) && winamp_st="${GREEN}Installed${NC}"; local music_st="Not Installed"; ([ "$OS_TYPE" = "macos" ] && osascript -e 'id of application "Music"' &>/dev/null) && music_st="${GREEN}Installed${NC}"; echo -e "  ${BOLD}Current Settings:${NC}\n  • Default Audio Player:          ${BOLD}${GREEN}${DEFAULT_AUDIO_PLAYER:-mp_liquid_glass}${NC}"; local ap_badge="${RED}DISABLED${NC}"; [ "${AUTO_PLAY_ON_STARTUP:-true}" = "true" ] && ap_badge="${GREEN}ENABLED${NC}"; echo -e "  • Auto-Play Mix on Startup:      ${ap_badge}"; local cov_badge="${RED}DISABLED${NC}"; [ "${AUTO_SHOW_COVER_ON_STARTUP:-false}" = "true" ] && cov_badge="${GREEN}ENABLED${NC}"; echo -e "  • Auto-Show Cover Art on Boot:   ${cov_badge}"
echo -e "  • Tracklist Window Viewer:       ${BOLD}${CYAN}${TRACKLIST_VIEWER:-console}${NC} (Dedicated Window)\n  • Startup Mix Selection Mode:    ${BOLD}${CYAN}${AUTO_PLAY_MIX_SELECTION:-latest}${NC} (Newest converted mix, or Random)\n  • Default Video Player:          ${BOLD}${GREEN}${DEFAULT_VIDEO_PLAYER:-vlc}${NC}"; local yt_badge="${RED}DISABLED${NC}"; [ "${AUTO_PLAY_YOUTUBE_ON_STARTUP:-false}" = "true" ] && yt_badge="${GREEN}ENABLED${NC}"; echo -e "  • Startup YouTube Autoplay:      ${yt_badge} ${DIM}(Plays only when mix audio is playing)${NC}"; if [ -n "${STARTUP_YOUTUBE_URL:-}" ]; then echo -e "  • Startup YouTube URL:           ${CYAN}${STARTUP_YOUTUBE_URL}${NC}"; fi; local w_badge="${RED}DISABLED${NC}"; [ "${WEATHER_ENABLED:-true}" = "true" ] && w_badge="${GREEN}ENABLED${NC}"; echo -e "  • Live Weather Banner:           ${w_badge} ${DIM}(${WEATHER_LOCATION:-Swansea, UK})${NC}"; local lg_backend_display="${LIQUID_GLASS_BACKEND:-opengl}"; lg_backend_display="$(echo "$lg_backend_display" | tr '[:lower:]' '[:upper:]')"; local lg_info="[OpenGL Default • AMD Radeon / Intel / NVIDIA / Older Cards]"; [ "$lg_backend_display" = "VULKAN" ] && lg_info="[NVIDIA Vulkan Hardware Pipeline]"; echo -e "  • Liquid Glass Mode Backend:     ${BOLD}${CYAN}${lg_backend_display}${NC} ${DIM}${lg_info}${NC}\n  • Config File Location:          ${DIM}${SCRIPT_DIR}/config.env${NC}\n\n${BOLD}Select Player or Setting to Change:${NC}\n  ${BOLD}${CYAN} 1)${NC} Set Default Player to: ${BOLD}MP Liquid Glass Audio Player${NC} (Liquid Transparent Glass Mode) [${GREEN}Installed • Default${NC}]\n  ${BOLD}${CYAN} 2)${NC} Set Default Player to: ${BOLD}MP Audio Player${NC} (Built-in Console Player, Animated EQ) [${GREEN}Installed${NC}]\n  ${BOLD}${CYAN} 3)${NC} Set Default Player to: ${BOLD}Audacious${NC} (Audio Player) [${audacious_st}]\n  ${BOLD}${CYAN} 4)${NC} Set Default Player to: ${BOLD}cliamp${NC} (Retro Terminal Player) [${cliamp_st}]\n  ${BOLD}${CYAN} 5)${NC} Set Default Player to: ${BOLD}Strawberry${NC} (Music Player) [${straw_st}]\n  ${BOLD}${CYAN} 6)${NC} Set Default Player to: ${BOLD}VLC Media Player${NC} [${vlc_st}]\n  ${BOLD}${CYAN} 7)${NC} Set Default Player to: ${BOLD}Haruna Media Player${NC} [${haruna_st}]\n  ${BOLD}${CYAN} 8)${NC} Set Default Player to: ${BOLD}Kodi Entertainment Center${NC} [${kodi_st}]\n  ${BOLD}${CYAN} 9)${NC} Set Default Player to: ${BOLD}foobar2000${NC} (macOS & Windows) [${foobar_st}]\n  ${BOLD}${CYAN}10)${NC} Set Default Player to: ${BOLD}Winamp${NC} (Windows) [${winamp_st}]\n  ${BOLD}${CYAN}11)${NC} Set Default Player to: ${BOLD}Apple Music${NC} (macOS) [${music_st}]\n  ${BOLD}${CYAN}12)${NC} Set Default Player to: ${BOLD}Audacity Audio Editor${NC} [${audacity_st}]\n  ${BOLD}${CYAN}13)${NC} Set Default Player to: ${BOLD}mpv Video/Audio Player${NC} [${mpv_st}]\n  ${BOLD}${CYAN}14)${NC} Set Custom Audio Player Command / Binary\n  ${BOLD}${BLUE}──────────────────────────────────────────────────────────────────${NC}\n  ${BOLD}${CYAN}15)${NC} Toggle Auto-Play Mix on Startup (${ap_badge})\n  ${BOLD}${CYAN}16)${NC} Toggle Auto-Show Cover Art on Startup (${cov_badge})\n  ${BOLD}${CYAN}17)${NC} Toggle Startup Mix Selection (Latest vs Random)\n  ${BOLD}${CYAN}18)${NC} Test-Play Latest Mix Right Now in Default Player (${DEFAULT_AUDIO_PLAYER})\n  ${BOLD}${CYAN}19)${NC} Configure Tracklist Window Viewer (${BOLD}${TRACKLIST_VIEWER:-console}${NC})\n  ${BOLD}${CYAN}20)${NC} Configure Default Video Player (${BOLD}${DEFAULT_VIDEO_PLAYER:-vlc}${NC})\n  ${BOLD}${CYAN}21)${NC} Configure Startup YouTube URL & Autoplay (${yt_badge})\n  ${BOLD}${CYAN}22)${NC} Configure Live Weather Banner & Location (${BOLD}${WEATHER_LOCATION:-Swansea, UK}${NC})\n  ${BOLD}${CYAN}23)${NC} Configure Liquid Glass Backend (${BOLD}${lg_backend_display}${NC} • OpenGL [Default] / Vulkan)\n  ${BOLD}${CYAN} 0)${NC} Return to Main Menu\n"; read -r -p "Enter choice [0-23]: " set_choice; case "$set_choice" in 1|liquid|glass|mp_liquid_glass|liquid_glass) DEFAULT_AUDIO_PLAYER="mp_liquid_glass"
save_config_setting "DEFAULT_AUDIO_PLAYER" "mp_liquid_glass"; echo -e "\n${GREEN}✓ Default audio player set to 'mp_liquid_glass' (MP Liquid Glass Audio Player) and saved to config.env!${NC}"; sleep 1 ;; 2|mp|mp_player|mpplayer|p|P) DEFAULT_AUDIO_PLAYER="mp_audio_player"
save_config_setting "DEFAULT_AUDIO_PLAYER" "mp_audio_player"; echo -e "\n${GREEN}✓ Default audio player set to 'mp_audio_player' (MP Audio Player) and saved to config.env!${NC}"; sleep 1 ;; 3|audacious) DEFAULT_AUDIO_PLAYER="audacious"; save_config_setting "DEFAULT_AUDIO_PLAYER" "audacious"; echo -e "\n${GREEN}✓ Default audio player set to 'audacious' and saved to config.env!${NC}"; sleep 1 ;; 4|cliamp) DEFAULT_AUDIO_PLAYER="cliamp"; save_config_setting "DEFAULT_AUDIO_PLAYER" "cliamp"; echo -e "\n${GREEN}✓ Default audio player set to 'cliamp' and saved to config.env!${NC}"; sleep 1 ;; 5|strawberry) DEFAULT_AUDIO_PLAYER="strawberry"; save_config_setting "DEFAULT_AUDIO_PLAYER" "strawberry"; echo -e "\n${GREEN}✓ Default audio player set to 'strawberry' and saved to config.env!${NC}"; sleep 1 ;; 6|vlc) DEFAULT_AUDIO_PLAYER="vlc"; save_config_setting "DEFAULT_AUDIO_PLAYER" "vlc"; echo -e "\n${GREEN}✓ Default audio player set to 'vlc' and saved to config.env!${NC}"; sleep 1 ;; 7|haruna) DEFAULT_AUDIO_PLAYER="haruna"; save_config_setting "DEFAULT_AUDIO_PLAYER" "haruna"; echo -e "\n${GREEN}✓ Default audio player set to 'haruna' and saved to config.env!${NC}"; sleep 1 ;; 8|kodi) DEFAULT_AUDIO_PLAYER="kodi"; save_config_setting "DEFAULT_AUDIO_PLAYER" "kodi"; echo -e "\n${GREEN}✓ Default audio player set to 'kodi' and saved to config.env!${NC}"; sleep 1 ;; 9|foobar|foobar2000) DEFAULT_AUDIO_PLAYER="foobar2000"; save_config_setting "DEFAULT_AUDIO_PLAYER" "foobar2000"; echo -e "\n${GREEN}✓ Default audio player set to 'foobar2000' and saved to config.env!${NC}"; sleep 1 ;; 10|winamp) DEFAULT_AUDIO_PLAYER="winamp"; save_config_setting "DEFAULT_AUDIO_PLAYER" "winamp"; echo -e "\n${GREEN}✓ Default audio player set to 'winamp' and saved to config.env!${NC}"; sleep 1 ;;
11|music|"apple music")
DEFAULT_AUDIO_PLAYER="music"; save_config_setting "DEFAULT_AUDIO_PLAYER" "music"; echo -e "\n${GREEN}✓ Default audio player set to 'music' (Apple Music) and saved to config.env!${NC}"; sleep 1; ;; 12|audacity) DEFAULT_AUDIO_PLAYER="audacity"; save_config_setting "DEFAULT_AUDIO_PLAYER" "audacity"; echo -e "\n${GREEN}✓ Default audio player set to 'audacity' and saved to config.env!${NC}"; sleep 1; ;; 13|mpv) DEFAULT_AUDIO_PLAYER="mpv"; save_config_setting "DEFAULT_AUDIO_PLAYER" "mpv"; echo -e "\n${GREEN}✓ Default audio player set to 'mpv' and saved to config.env!${NC}"; sleep 1; ;; 14) read -r -p "Enter custom audio player executable command: " cust_p; if [ -n "$cust_p" ]; then DEFAULT_AUDIO_PLAYER="$cust_p"; save_config_setting "DEFAULT_AUDIO_PLAYER" "$cust_p"; echo -e "\n${GREEN}✓ Default audio player set to '${cust_p}' and saved to config.env!${NC}"; sleep 1.2; fi ;; 15) if [ "${AUTO_PLAY_ON_STARTUP:-true}" = "true" ]; then AUTO_PLAY_ON_STARTUP="false"; else AUTO_PLAY_ON_STARTUP="true"; fi; save_config_setting "AUTO_PLAY_ON_STARTUP" "$AUTO_PLAY_ON_STARTUP"; echo -e "\n${GREEN}✓ Startup autoplay toggled to: ${AUTO_PLAY_ON_STARTUP}!${NC}"; sleep 1 ;; 16) if [ "${AUTO_SHOW_COVER_ON_STARTUP:-false}" = "true" ]; then AUTO_SHOW_COVER_ON_STARTUP="false"; else AUTO_SHOW_COVER_ON_STARTUP="true"; fi; save_config_setting "AUTO_SHOW_COVER_ON_STARTUP" "$AUTO_SHOW_COVER_ON_STARTUP"; echo -e "\n${GREEN}✓ Auto-show cover art toggled to: ${AUTO_SHOW_COVER_ON_STARTUP}!${NC}"; sleep 1 ;; 17) if [ "${AUTO_PLAY_MIX_SELECTION:-latest}" = "latest" ]; then AUTO_PLAY_MIX_SELECTION="random"; else AUTO_PLAY_MIX_SELECTION="latest"; fi; save_config_setting "AUTO_PLAY_MIX_SELECTION" "$AUTO_PLAY_MIX_SELECTION"; echo -e "\n${GREEN}✓ Startup mix selection toggled to: ${AUTO_PLAY_MIX_SELECTION}!${NC}"
sleep 1 ;; 17) echo -e "\n${BOLD}${YELLOW}Testing startup playback right now with player: ${DEFAULT_AUDIO_PLAYER}...${NC}\n"; execute_startup_autoplay; press_enter; ;; 18) clear; echo -e "${BOLD}${MAGENTA}${S70}${NC}\n${BOLD}${MAGENTA}             CONFIGURE DEDICATED TRACKLIST WINDOW VIEWER              ${NC}\n${BOLD}${MAGENTA}${S70}${NC}\n\n  Current Viewer: ${BOLD}${GREEN}${TRACKLIST_VIEWER:-console}${NC}\n\n  ${BOLD}${CYAN} 1)${NC} ${BOLD}console${NC} (Default OS Console • Entirely Borderless Window on Bazzite Linux)\n  ${BOLD}${CYAN} 2)${NC} ${BOLD}auto${NC} (External GUI Editor: KWrite/Kate on KDE, TextEdit on macOS, Notepad on Windows)\n  ${BOLD}${CYAN} 3)${NC} ${BOLD}kwrite${NC} (KDE Lightweight Dedicated Editor Window)\n  ${BOLD}${CYAN} 4)${NC} ${BOLD}kate${NC} (KDE Advanced Text Editor - New Window)\n  ${BOLD}${CYAN} 5)${NC} ${BOLD}gedit${NC} (GNOME Text Editor - New Window)\n  ${BOLD}${CYAN} 6)${NC} ${BOLD}mousepad${NC} (XFCE Lightweight Text Editor)\n  ${BOLD}${CYAN} 7)${NC} ${BOLD}konsole${NC} (Standard Konsole Window with less viewer)\n  ${BOLD}${CYAN} 8)${NC} ${BOLD}xdg-open${NC} (Desktop Environment Default MIME Handler)\n  ${BOLD}${CYAN} 9)${NC} Custom Text Viewer / Editor Executable Command\n  ${BOLD}${CYAN} 0)${NC} Cancel\n"; read -r -p "Enter choice [0-9]: " tv_choice; case "$tv_choice" in 1) TRACKLIST_VIEWER="console" ;; 2) TRACKLIST_VIEWER="auto" ;; 3) TRACKLIST_VIEWER="kwrite" ;; 4) TRACKLIST_VIEWER="kate" ;; 5) TRACKLIST_VIEWER="gedit" ;; 6) TRACKLIST_VIEWER="mousepad" ;; 7) TRACKLIST_VIEWER="konsole" ;; 8) TRACKLIST_VIEWER="xdg-open" ;; 9) read -r -p "Enter custom text viewer command: " cust_tv; [ -n "$cust_tv" ] && TRACKLIST_VIEWER="$cust_tv" ;; *) ;; esac; save_config_setting "TRACKLIST_VIEWER" "$TRACKLIST_VIEWER"; echo -e "\n${GREEN}✓ Tracklist window viewer set to '${TRACKLIST_VIEWER}' and saved to config.env!${NC}"; sleep 1.2 ;; 19) clear
echo -e "${BOLD}${MAGENTA}${S70}${NC}\n${BOLD}${MAGENTA}                CONFIGURE DEFAULT VIDEO PLAYER                        ${NC}\n${BOLD}${MAGENTA}${S70}${NC}\n\n  Current Video Player: ${BOLD}${GREEN}${DEFAULT_VIDEO_PLAYER:-vlc}${NC}\n\n  ${BOLD}${CYAN} 1)${NC} ${BOLD}vlc${NC} (VLC Media Player • Recommended)\n  ${BOLD}${CYAN} 2)${NC} ${BOLD}mpv${NC} (High-performance minimalist player)\n  ${BOLD}${CYAN} 3)${NC} ${BOLD}haruna${NC} (KDE Qt/QML Video Player)\n  ${BOLD}${CYAN} 4)${NC} ${BOLD}kodi${NC} (Kodi Media Center)\n  ${BOLD}${CYAN} 5)${NC} Custom video player command / executable\n  ${BOLD}${CYAN} 0)${NC} Cancel\n"; read -r -p "Enter choice [0-5]: " vp_choice; case "$vp_choice" in 1) DEFAULT_VIDEO_PLAYER="vlc" ;; 2) DEFAULT_VIDEO_PLAYER="mpv" ;; 3) DEFAULT_VIDEO_PLAYER="haruna" ;; 4) DEFAULT_VIDEO_PLAYER="kodi" ;; 5) read -r -p "Enter custom video player command: " cust_vp; [ -n "$cust_vp" ] && DEFAULT_VIDEO_PLAYER="$cust_vp"; ;; *) ;; esac; save_config_setting "DEFAULT_VIDEO_PLAYER" "$DEFAULT_VIDEO_PLAYER"; echo -e "\n${GREEN}✓ Default video player set to '${DEFAULT_VIDEO_PLAYER}' and saved to config.env!${NC}"; sleep 1.2; ;; 20) clear; echo -e "${BOLD}${MAGENTA}${S70}${NC}\n${BOLD}${MAGENTA}        CONFIGURE STARTUP CUSTOM YOUTUBE VIDEO AUTOPLAY               ${NC}\n${BOLD}${MAGENTA}${S70}${NC}\n"; local cur_yt="${RED}DISABLED${NC}"; [ "${AUTO_PLAY_YOUTUBE_ON_STARTUP:-false}" = "true" ] && cur_yt="${GREEN}ENABLED${NC}"; echo -e "  • Startup YouTube Autoplay: ${cur_yt}\n  • Note: Autoplays ONLY if a mix is playing already in a music player!\n\n  Current YouTube URL: ${CYAN}${STARTUP_YOUTUBE_URL:-None}${NC}\n\n  ${BOLD}${CYAN} 1)${NC} Toggle Autoplay on/off\n  ${BOLD}${CYAN} 2)${NC} Set / Change Custom YouTube Video URL\n  ${BOLD}${CYAN} 3)${NC} Clear YouTube URL & Disable Autoplay\n  ${BOLD}${CYAN} 0)${NC} Cancel\n"; read -r -p "Enter choice [0-3]: " yt_choice; case "$yt_choice" in 1) if [ "${AUTO_PLAY_YOUTUBE_ON_STARTUP:-false}" = "true" ]; then AUTO_PLAY_YOUTUBE_ON_STARTUP="false"; else AUTO_PLAY_YOUTUBE_ON_STARTUP="true"; fi; save_config_setting "AUTO_PLAY_YOUTUBE_ON_STARTUP" "$AUTO_PLAY_YOUTUBE_ON_STARTUP"; echo -e "\n${GREEN}✓ Startup YouTube autoplay set to: ${AUTO_PLAY_YOUTUBE_ON_STARTUP}!${NC}"; sleep 1; ;; 2) echo ""; read -r -p "Enter YouTube video URL (e.g. https://www.youtube.com/watch?v=...): " new_yt; if [ -n "$new_yt" ]; then STARTUP_YOUTUBE_URL="$new_yt"; AUTO_PLAY_YOUTUBE_ON_STARTUP="true"; save_config_setting "STARTUP_YOUTUBE_URL" "$STARTUP_YOUTUBE_URL"; save_config_setting "AUTO_PLAY_YOUTUBE_ON_STARTUP" "true"; echo -e "\n${GREEN}✓ Startup YouTube URL updated and enabled!${NC}"; sleep 1.2; fi; ;; 3) STARTUP_YOUTUBE_URL=""; AUTO_PLAY_YOUTUBE_ON_STARTUP="false"; save_config_setting "STARTUP_YOUTUBE_URL" ""; save_config_setting "AUTO_PLAY_YOUTUBE_ON_STARTUP" "false"; echo -e "\n${YELLOW}✓ Startup YouTube URL cleared and disabled.${NC}"; sleep 1.2; ;; *) ;; esac ;; 21) manage_weather_menu; ;; 22|liquid|glass|backend) configure_liquid_glass_backend ;; 0|[qQ]) return 0 ;; *) echo -e "\n${RED}Invalid choice!${NC}"; sleep 1.2 ;; esac; done
}
manage_bluetooth_audio() {
clear; echo -e "${BOLD}${MAGENTA}====================================================${NC}\n${BOLD}${MAGENTA}       BLUETOOTH AUDIO & INTELLIGENT STREAM ROUTER  ${NC}\n${BOLD}${MAGENTA}====================================================${NC}\n"; local bt_py="$SCRIPT_DIR/scripts/monitor_bluetooth_audio.py"; [ ! -f "$bt_py" ] && bt_py="$SCRIPT_DIR/monitor_bluetooth_audio.py"; if [ ! -f "$bt_py" ]; then echo -e "${RED}Error: monitor_bluetooth_audio.py not found!${NC}"; press_enter; return 1; fi; python3 "$bt_py" --status; echo ""; echo -e "${BOLD}Select an action:${NC}\n  ${BOLD}${CYAN}1)${NC} Intelligently Route / Switch to Bluetooth Audio Now\n  ${BOLD}${CYAN}2)${NC} Revert Audio to Primary Fallback Output (HDMI / Speakers)\n  ${BOLD}${CYAN}3)${NC} Run Live Bluetooth Audio Monitor in Terminal\n  ${BOLD}${CYAN}0)${NC} Return"; echo ""; read -r -p "Enter choice [0-3]: " bt_opt; case "$bt_opt" in 1) python3 "$bt_py" --route; press_enter; ;; 2) python3 "$bt_py" --revert; press_enter; ;; 3) python3 "$bt_py" --monitor ;; *) return 0; ;; esac
}
manage_audio_players() {
while true; do clear; echo -e "${BOLD}${MAGENTA}====================================================${NC}\n${BOLD}${MAGENTA}             AUDIO PLAYERS & PLAYBACK SUITE         ${NC}\n${BOLD}${MAGENTA}====================================================${NC}"; local current_datetime; current_datetime=$(date "+%A, %B %d, %Y  •  %T %Z"); echo -e "       ${BOLD}${CYAN}📅 ${current_datetime}${NC}"; echo ""; if get_mp_audio_player_track_info 2>/dev/null; then local st_badge; case "$MP_PLAYER_STATE" in playing) st_badge="${BOLD}${GREEN}▶ PLAYING${NC}" ;; paused)  st_badge="${BOLD}${YELLOW}⏸ PAUSED${NC}" ;; stopped) st_badge="${BOLD}${RED}⏹ STOPPED${NC}" ;; *)       st_badge="${BOLD}${CYAN}${MP_PLAYER_STATE^^}${NC}" ;; esac; local m_badge=""; [ "$MP_PLAYER_MODE" = "MUSIC" ] && m_badge=" ${BOLD}${GREEN}[MUSIC MODE - DJ TRACKS]${NC}"; local rec_badge=""; [ "${MP_PLAYER_RECORDING:-false}" = "true" ] && rec_badge=" ${BOLD}${RED}● REC${NC}"; echo -e "  MP Audio Player:   ${st_badge}${m_badge}${rec_badge} [${MP_PLAYER_POS_FMT} / ${MP_PLAYER_DUR_FMT}] (${MP_PLAYER_PROGRESS_PCT}%) ${CYAN}${MP_PLAYER_MINI_EQ}${NC}\n  Current Track:     ${BOLD}${YELLOW}${MP_PLAYER_TITLE}${NC}"; [ -n "$MP_PLAYER_RESOLVED_PATH" ] && echo -e "  Active File Path:  ${BOLD}${CYAN}${MP_PLAYER_RESOLVED_PATH}${NC}"; echo -e "  --------------------------------------------------"; elif get_audacious_track_info 2>/dev/null; then local st_badge; case "$AUDACIOUS_STATE" in playing) st_badge="${BOLD}${GREEN}▶ PLAYING${NC}" ;; paused)  st_badge="${BOLD}${YELLOW}⏸ PAUSED${NC}" ;; stopped) st_badge="${BOLD}${RED}⏹ STOPPED${NC}" ;; *)       st_badge="${BOLD}${CYAN}${AUDACIOUS_STATE^^}${NC}" ;; esac; echo -e "  Audacious Player:  ${st_badge} [${AUDACIOUS_POS_FMT} / ${AUDACIOUS_DUR_FMT}] (${AUDACIOUS_PROGRESS_PCT}%)\n  Current Track:     ${BOLD}${YELLOW}${AUDACIOUS_TITLE}${NC}${AUDACIOUS_ARTIST:+ - $AUDACIOUS_ARTIST}"; [ -n "$AUDACIOUS_RESOLVED_PATH" ] && echo -e "  Active File Path:  ${BOLD}${CYAN}${AUDACIOUS_RESOLVED_PATH}${NC}"; echo -e "  --------------------------------------------------"; elif get_cliamp_track_info 2>/dev/null; then local st_badge; case "$CLIAMP_STATE" in
playing) st_badge="${BOLD}${GREEN}▶ PLAYING${NC}" ;; paused)  st_badge="${BOLD}${YELLOW}⏸ PAUSED${NC}" ;; stopped) st_badge="${BOLD}${RED}⏹ STOPPED${NC}" ;; *)       st_badge="${BOLD}${CYAN}${CLIAMP_STATE}${NC}" ;; esac; echo -e "  cliamp Player:     ${st_badge} [${CLIAMP_POS_FMT} / ${CLIAMP_DUR_FMT}] (${CLIAMP_PROGRESS_PCT}%)\n  Current Track:     ${BOLD}${YELLOW}${CLIAMP_TITLE}${NC} - ${CLIAMP_ARTIST}\n  Active File Path:  ${BOLD}${CYAN}${CLIAMP_RESOLVED_PATH}${NC}\n  --------------------------------------------------"; fi; local fb_badge="${YELLOW}[macOS & Windows]${NC}"; local wa_badge="${YELLOW}[Windows Only]${NC}"; local am_badge="${YELLOW}[macOS Only]${NC}"; local ap_badge="${YELLOW}[macOS Only]${NC}"; if [ "$OS_TYPE" = "macos" ]; then [ -d "/Applications/foobar2000.app" ] && fb_badge="${GREEN}✓ INSTALLED${NC}"; am_badge="${GREEN}✓ macOS APP${NC}"; ap_badge="${GREEN}✓ macOS APP${NC}"; elif [ "$OS_TYPE" = "windows" ] || [ "$OS_TYPE" = "wsl" ]; then ([ -f "/c/Program Files/foobar2000/foobar2000.exe" ] || command -v foobar2000.exe &>/dev/null) && fb_badge="${GREEN}✓ INSTALLED${NC}"; ([ -f "/c/Program Files (x86)/Winamp/winamp.exe" ] || [ -f "/c/Program Files/Winamp/winamp.exe" ] || command -v winamp.exe &>/dev/null) && wa_badge="${GREEN}✓ INSTALLED${NC}"; fi; echo -e "${BOLD}Select an Audio Player to launch / manage:${NC}\n  ${BOLD}${CYAN} 1)${NC} Play Mix/Audio File (MP Audio Player) (${GREEN}Built-in Audio Player, Animated EQ${NC})\n  ${BOLD}${CYAN} 2)${NC} Launch Audacious Audio Player (New Window) (${GREEN}audacious / org.atheme.audacious${NC})\n  ${BOLD}${CYAN} 3)${NC} Cliamp Music Player & Current Track Info (${GREEN}Now Playing Path, Controls & Launch${NC})\n  ${BOLD}${CYAN} 4)${NC} Launch VLC Media Player (${GREEN}vlc / org.videolan.VLC${NC})\n  ${BOLD}${CYAN} 5)${NC} Launch Haruna Media Player (${GREEN}org.kde.haruna${NC})\n  ${BOLD}${CYAN} 6)${NC} Launch Kodi Entertainment Center (${GREEN}tv.kodi.Kodi${NC})\n  ${BOLD}${CYAN} 7)${NC} Launch Strawberry Music Player (Legacy) (${GREEN}strawberry${NC})\n  ${BOLD}${CYAN} 8)${NC} Launch foobar2000 Player (${fb_badge})\n  ${BOLD}${CYAN} 9)${NC} Launch Winamp Player (${wa_badge})\n  ${BOLD}${CYAN}10)${NC} Launch Apple Music Player (${am_badge})\n  ${BOLD}${CYAN}11)${NC} Launch Apple Podcasts App (${ap_badge})\n  ${BOLD}${CYAN}12)${NC} Launch Audacity Audio Editor (${GREEN}audacity${NC})\n  ${BOLD}${CYAN}13)${NC} Show Connected USB MIDI Devices (${GREEN}list-midi-devices${NC})\n  ${BOLD}${CYAN}14)${NC} Configure Default Audio Player & Startup Autoplay (${GREEN}Current: ${DEFAULT_AUDIO_PLAYER:-mp_audio_player}${NC})\n  ${BOLD}${CYAN}15)${NC} View Playing Mix Audio Specifications & Stream Metadata (${GREEN}Bit Depth, Sample Rate, Codec, Title${NC})\n  ${BOLD}${CYAN}16)${NC} Manage Bluetooth Audio & Auto Stream Routing (${GREEN}Intelligent BT Monitor, Auto-Switch${NC})\n  ${BOLD}${CYAN}17)${NC} Configure Standalone Liquid Glass Player Backend (${GREEN}Current: ${LIQUID_GLASS_BACKEND:-opengl^^}${NC})\n  ${BOLD}${CYAN} 0)${NC} Return to Main Menu"; echo ""; read -r -p "Enter choice [0-17]: " p_choice; case "$p_choice" in 1|mp|mp_player|mpplayer|p|P) manage_mp_audio_player ;; 2|audacious) launch_audacious; ;; 3|cliamp) manage_cliamp ;; 4|vlc) launch_vlc; ;; 5|haruna) launch_haruna ;; 6|kodi) launch_kodi; ;; 7|strawberry) launch_strawberry ;; 8|foobar|foobar2000) launch_foobar2000; ;; 9|winamp) launch_winamp ;;
10|music|"apple music")
launch_apple_music ;;
11|podcasts|"apple podcasts")
launch_apple_podcasts ;; 12|audacity) launch_audacity; ;; 13|midi) list_usb_midi_devices ;; 14|config|setup) configure_audio_player_and_startup; ;; 15|meta|metadata) inspect_playing_audio_file ;;
16|bt|bluetooth|"bluetooth audio")
manage_bluetooth_audio ;; 17|liquid|glass|backend) configure_liquid_glass_backend ;; 0|[qQ]) return 0; ;; *) echo -e "\n${RED}Invalid choice!${NC}"; sleep 1.5; ;; esac; done
}
manage_visual_media_launchers() {
local vml_choice; while true; do clear; echo -e "${BOLD}${MAGENTA}====================================================${NC}\n${BOLD}${MAGENTA}         VISUAL, VIDEO & ART LAUNCHERS SUITE        ${NC}\n${BOLD}${MAGENTA}====================================================${NC}"; echo ""; echo -e "${BOLD}Select a visual or media application to launch:${NC}\n  ${BOLD}${CYAN}1)${NC} Launch MP_Liquid_Visualizer — 3D Vulkan Audio-Reactive Visualizer (${GREEN}1400x1400 Borderless • Cosmic Dreamworlds / Orbital Void Reflux${NC})\n  ${BOLD}${CYAN}2)${NC} Select MP_Liquid_Visualizer Preset (${GREEN}Cosmic Dreamworlds / Orbital Void Reflux${NC})\n  ${BOLD}${CYAN}3)${NC} Launch Video Playlists (${GREEN}NFT Videos in VLC${NC})\n  ${BOLD}${CYAN}4)${NC} Launch Specific Video in Default Video Player (${GREEN}${DEFAULT_VIDEO_PLAYER:-vlc}${NC})\n  ${BOLD}${CYAN}5)${NC} Launch GIMP Image Editor (${GREEN}gimp / org.gimp.GIMP${NC})\n  ${BOLD}${CYAN}6)${NC} Launch Electric Sheep Generative Screensaver (${GREEN}electricsheep / infinidream${NC})\n  ${BOLD}${CYAN}7)${NC} Launch GeeXLab Demo Launcher (${GREEN}FurMark_linux64/demo_launcher.sh${NC})\n  ${BOLD}${CYAN}0)${NC} Return to Main Menu"; echo ""; read -r -p "Enter choice [0-7]: " vml_choice; case "$vml_choice" in 1|z|Z|visualizer|liquid-visualizer) launch_mp_liquid_visualizer ;; 2|preset|presets) manage_mp_liquid_visualizer_presets ;; 3) launch_video_playlists ;; 4) manage_video_dispatcher ;; 5) launch_gimp ;; 6) launch_electricsheep ;; 7) launch_geexlab_demos ;; 0|[qQ]) return 0 ;; *) echo -e "\n${RED}Invalid choice!${NC}"; sleep 1; ;; esac; done
}
manage_live_monitors() {
local lm_choice; while true; do clear; echo -e "${BOLD}${MAGENTA}====================================================${NC}\n${BOLD}${MAGENTA}         LIVE SESSION & STREAM MONITORS SUITE       ${NC}\n${BOLD}${MAGENTA}====================================================${NC}"; echo ""; echo -e "${BOLD}Select a live monitor to launch:${NC}\n  ${BOLD}${CYAN}1)${NC} Launch Live Tracklist Monitor (${GREEN}SOF_Live_Tracker.sh${NC})\n  ${BOLD}${CYAN}2)${NC} Launch Traktor Live Monitor & Audio Recorder (${GREEN}New Window - CPU, Tracks, Audio I/O${NC})\n  ${BOLD}${CYAN}3)${NC} Launch Live File Transfer Monitor (${GREEN}transfer-monitor${NC})\n  ${BOLD}${CYAN}4)${NC} Launch Chrome Upload Monitor (${GREEN}Podcast Connect / Web Uploads${NC})\n  ${BOLD}${CYAN}5)${NC} View Running Background Tasks (${GREEN}Track and inspect background jobs${NC})\n  ${BOLD}${CYAN}6)${NC} Live Audio & Video Output Conversion Monitor (${GREEN}MP_Mix_Manager_Audio_File_Output_Monitor.py${NC})\n  ${BOLD}${CYAN}0)${NC} Return to Main Menu"; echo ""; read -r -p "Enter choice [0-6]: " lm_choice; case "$lm_choice" in 1) echo -e "\n${BOLD}${YELLOW}Launching Live Tracklist Monitor (Press Ctrl+C to return)...${NC}\n"; sleep 0.8; trap ':' INT; run_sub_script "SOF_Live_Tracker.sh"; trap 'exit_mix_manager' INT; press_enter; ;; 2) launch_traktor_monitor_window ;; 3) echo -e "\n${BOLD}${YELLOW}Launching Live File Transfer Monitor (Press Ctrl+C to return)...${NC}\n"; sleep 0.8; trap ':' INT; if command -v transfer-monitor &>/dev/null; then transfer-monitor; elif [ -x "$HOME/.local/bin/transfer-monitor" ]; then "$HOME/.local/bin/transfer-monitor"; else echo -e "${RED}Error: transfer-monitor command not found in PATH or ~/.local/bin!${NC}"; fi; trap 'exit_mix_manager' INT; press_enter ;; 4) echo -e "\n${BOLD}${YELLOW}Launching Chrome Upload Monitor (Press Ctrl+C to return)...${NC}\n"; sleep 0.8; trap ':' INT; if command -v chrome-upload-monitor &>/dev/null; then chrome-upload-monitor; elif [ -x "$HOME/.local/bin/chrome-upload-monitor" ]; then "$HOME/.local/bin/chrome-upload-monitor"; elif [ -x "./chrome_upload_monitor.py" ]; then python3 ./chrome_upload_monitor.py; elif [ -x "$SCRIPT_DIR/chrome_upload_monitor.py" ]; then python3 "$SCRIPT_DIR/chrome_upload_monitor.py"; elif [ -x "./Monitor_Chrome_Uploads.sh" ]; then ./Monitor_Chrome_Uploads.sh; elif [ -x "$SCRIPT_DIR/Monitor_Chrome_Uploads.sh" ]; then "$SCRIPT_DIR/Monitor_Chrome_Uploads.sh"; else echo -e "${RED}Error: chrome-upload-monitor command not found in PATH or ~/.local/bin!${NC}"; fi; trap 'exit_mix_manager' INT; press_enter ;; 5) view_tasks; press_enter ;; 6) local mon_py="$SCRIPT_DIR/scripts/MP_Mix_Manager_Audio_File_Output_Monitor.py"; [ ! -f "$mon_py" ] && mon_py="$SCRIPT_DIR/MP_Mix_Manager_Audio_File_Output_Monitor.py"; if [ -f "$mon_py" ]; then python3 "$mon_py"; else echo -e "${RED}Error: MP_Mix_Manager_Audio_File_Output_Monitor.py not found!${NC}"; press_enter; fi ;; 0|[qQ]) return 0; ;; *) echo -e "\n${RED}Invalid choice!${NC}"; sleep 1; ;; esac; done
}
manage_system_process_monitors() {
local spm_choice; while true; do clear; echo -e "${BOLD}${MAGENTA}====================================================${NC}\n${BOLD}${MAGENTA}        SYSTEM & HARDWARE PROCESS MONITORS          ${NC}\n${BOLD}${MAGENTA}====================================================${NC}"; echo ""; echo -e "${BOLD}Select a process / resource monitor to launch:${NC}\n  ${BOLD}${CYAN}1)${NC} Launch Resource Monitor (${GREEN}btop${NC}) [CPU, RAM, Disks, Network]\n  ${BOLD}${CYAN}2)${NC} Launch GPU Process Monitor (${GREEN}nvtop${NC}) [NVIDIA / AMD / Intel GPU VRAM & Cores]\n  ${BOLD}${CYAN}3)${NC} Launch System Process Monitor (${GREEN}top${NC}) [Standard UNIX Process Table]\n  ${BOLD}${CYAN}0)${NC} Return to Main Menu"; echo ""; read -r -p "Enter choice [0-3]: " spm_choice; case "$spm_choice" in 1) echo -e "\n${BOLD}${YELLOW}Launching btop Resource Monitor (Press 'q' to exit)...${NC}\n"; sleep 0.5; trap ':' INT; if command -v btop &>/dev/null; then _sync_btop_theme "$CURRENT_THEME"; btop; else echo -e "${RED}Error: btop command not found in PATH!${NC}"; press_enter; fi; trap 'exit_mix_manager' INT ;; 2) echo -e "\n${BOLD}${YELLOW}Launching nvtop GPU Monitor (Press 'q' to exit)...${NC}\n"; sleep 0.5; trap ':' INT; if command -v nvtop &>/dev/null; then nvtop; else echo -e "${RED}Error: nvtop command not found in PATH!${NC}"; press_enter; fi; trap 'exit_mix_manager' INT ;; 3) echo -e "\n${BOLD}${YELLOW}Launching top Process Monitor (Press 'q' to exit)...${NC}\n"; sleep 0.5; trap ':' INT; if command -v top &>/dev/null; then top; else echo -e "${RED}Error: top command not found in PATH!${NC}"; press_enter; fi; trap 'exit_mix_manager' INT ;; 0|[qQ]) return 0; ;; *) echo -e "\n${RED}Invalid choice!${NC}"; sleep 1; ;; esac; done
}
run_bash_cli() {
local cli_choice user_cmd; echo -e "\n${BOLD}${MAGENTA}====================================================${NC}\n${BOLD}${MAGENTA}             Interactive Bash CLI Runner            ${NC}\n${BOLD}${MAGENTA}====================================================${NC}\n${CYAN}Choose an option:${NC}\n  ${BOLD}${CYAN}1)${NC} Open an interactive Bash shell session ${DIM}(type 'exit' to return to Manager)${NC}\n  ${BOLD}${CYAN}2)${NC} Execute a single Bash command and return\n  ${BOLD}${CYAN}0)${NC} Return to Main Menu"; echo ""; read -r -p "Enter choice [0-2]: " cli_choice; case "$cli_choice" in 1) echo -e "\n${BOLD}${GREEN}Spawning interactive Bash subshell. Type 'exit' to return.${NC}\n"; export PS1="\[\033[01;32m\][MixManager-CLI] \[\033[01;34m\]\w\[\033[00m\]\$ "; bash --norc -i 2>/dev/null || bash -i; echo -e "\n${GREEN}Returned from Bash subshell.${NC}"; sleep 1 ;; 2) echo ""; read -r -p "Enter Bash command to execute: " user_cmd; if [ -n "$user_cmd" ]; then echo -e "\n${BOLD}${YELLOW}Executing:${NC} $user_cmd\n"; eval "$user_cmd"; echo ""; press_enter; fi ;; 0|[qQ]) return 0; ;; *) echo -e "\n${RED}Invalid choice!${NC}"; sleep 1.2; ;; esac
}
manage_themes() {
while true; do local m1="" m2="" m3="" m4="" m5="" m6="" m7="" m8="" m9="" m10="" m11="" m12="" m13="" m14="" m15="" m16="" m17="" m18="" m19=""; case "$CURRENT_THEME" in dreamworlds)       m1=" ${GREEN}★ ACTIVE (DEFAULT)${NC}" ;; dreamworlds_ultra) m2=" ${GREEN}★ ACTIVE${NC}" ;; cyberpunk)         m3=" ${GREEN}★ ACTIVE${NC}" ;; dracula)           m4=" ${GREEN}★ ACTIVE${NC}" ;; nord)              m5=" ${GREEN}★ ACTIVE${NC}" ;; matrix)            m6=" ${GREEN}★ ACTIVE${NC}" ;; solarized)         m7=" ${GREEN}★ ACTIVE${NC}" ;; tokyo)             m8=" ${GREEN}★ ACTIVE${NC}" ;; monokai)           m9=" ${GREEN}★ ACTIVE${NC}" ;; gruvbox)           m10=" ${GREEN}★ ACTIVE${NC}" ;; emerald)           m11=" ${GREEN}★ ACTIVE${NC}" ;; classic)           m12=" ${GREEN}★ ACTIVE${NC}" ;; cosmic_supernova)  m13=" ${GREEN}★ ACTIVE (SPECIAL)${NC}" ;; retro_terminal)   m14=" ${GREEN}★ ACTIVE (RETRO)${NC}" ;; dreamworlds_liquid) m15=" ${GREEN}★ ACTIVE (LIQUID GLASS)${NC}" ;; dynamic_rainbow_liquid_glass) m16=" ${GREEN}★ ACTIVE (DYNAMIC RAINBOW)${NC}" ;; cosmic_dreamworlds_radioactive) m17=" ${GREEN}★ ACTIVE (LIQUID GLASS SKIN)${NC}" ;; cosmic_dreamworlds) m18=" ${GREEN}★ ACTIVE (LIQUID GLASS SKIN)${NC}" ;; orbital_void_reflux) m19=" ${GREEN}★ ACTIVE (LIQUID GLASS SKIN)${NC}" ;; esac; local opts=("1|MPlanetarian Dreamworlds [Default]|[Sweet Hot Pink, Electric Cyan, Lavender & Violet]${m1}" "2|Dreamworlds Ultra MP Mix Manager|[BTOP HotPurpleTrafficLight: Hot Purple, Indigo & Traffic Light RGB]${m2}" "3|Cyberpunk|[Neon Hot Pink, Electric Cyan & High-Volt Yellow]${m3}" "4|Dracula|[Vampiric Purple, Neon Green & Coral Pink]${m4}" "5|Nord|[Arctic Slate, Frost Polar Ice & Sage Aurora]${m5}" "6|The Matrix|[Pure Phosphor Green, Terminal Crimson & Mint]${m6}" "7|Solarized|[Warm Amber, Solar Yellow, Cyan & Terracotta]${m7}" "8|Tokyo Night|[Deep Violet, Lavender, Soft Blue & Coral]${m8}" "9|Monokai|[Electric Pink, Tangerine, Lime & Vivid Blue]${m9}" "10|Gruvbox|[Retro Warm Earth, Dusty Rose, Rust & Gold]${m10}" "11|Emerald Isle|[Deep Ocean, Spring Emerald & Mint Cyan]${m11}" "12|Classic ANSI|[Standard 16-Color Terminal Fallback]${m12}" "13|Cosmic Supernova [Special Edition]|[Supernova Crimson, Aurora Mint, Solar Gold & Nebula Orchid]${m13}" "14|Old Style Unix Terminal Retro Mode (White on Black)|[Monochrome VT100: White Text Only on Black Background]${m14}" "15|MP Dreamworlds Liquid Transparency [Special Edition]|[Deep Liquid Ocean Glass, Crystalline Aqua, Seafoam Mint & Liquid Amethyst]${m15}" "16|Dynamic Liquid Glass [Rainbow Colours] (New)|[Dynamic Rainbow Liquid Glass • ±9% Breathing Transparency • 6-Second Cycle]${m16}" "17|Cosmic Dreamworlds Radioactive (Liquid Glass Skin)|[Cover Wrapped Liquid Glass • Crystal Clear Refractive Water • Neon Radioactive & Cosmic Glow]${m17}" "18|Cosmic Dreamworlds (Liquid Glass Skin)|[Cover Wrapped Liquid Glass • Crystal Clear Refractive Water • Cosmic Dreamworlds Pink & Neon Cyan]${m18}" "19|Orbital Void Reflux (Liquid Glass Skin)|[Cover Wrapped Liquid Glass • Crystal Clear Refractive Water • Orbital Void Violet & Reflux Cyan]${m19}" "0|Return to Main Menu|(or Esc / q)"); run_interactive_submenu "Themes & Color Palette Switcher" "  Current Active Theme: ${BOLD}${YELLOW}${CURRENT_THEME}${NC}\n" opts 0; local tchoice="$REPLY"; case "$tchoice" in 1|dreamworlds|default) save_theme "dreamworlds"; echo -e "\n${BOLD}${GREEN}✓ Theme switched to MPlanetarian Dreamworlds [Default]!${NC}"; sleep 0.8 ;;
2|ultra|dreamworlds_ultra|hotpurple|trafficlight|"dreamworlds ultra"|"Dreamworlds Ultra MP Mix Manager")
save_theme "dreamworlds_ultra"; echo -e "\n${BOLD}${GREEN}✓ Theme switched to Dreamworlds Ultra MP Mix Manager!${NC}"; sleep 0.8 ;; 3|cyberpunk) save_theme "cyberpunk"; echo -e "\n${GREEN}✓ Theme switched to Cyberpunk!${NC}"; sleep 0.8; ;; 4|dracula) save_theme "dracula"; echo -e "\n${GREEN}✓ Theme switched to Dracula!${NC}"; sleep 0.8 ;; 5|nord) save_theme "nord"; echo -e "\n${GREEN}✓ Theme switched to Nord!${NC}"; sleep 0.8; ;; 6|matrix) save_theme "matrix"; echo -e "\n${GREEN}✓ Theme switched to The Matrix!${NC}"; sleep 0.8 ;; 7|solarized) save_theme "solarized"; echo -e "\n${GREEN}✓ Theme switched to Solarized!${NC}"; sleep 0.8; ;; 8|tokyo) save_theme "tokyo"; echo -e "\n${GREEN}✓ Theme switched to Tokyo Night!${NC}"; sleep 0.8 ;; 9|monokai) save_theme "monokai"; echo -e "\n${GREEN}✓ Theme switched to Monokai!${NC}"; sleep 0.8; ;; 10|gruvbox) save_theme "gruvbox"; echo -e "\n${GREEN}✓ Theme switched to Gruvbox!${NC}"; sleep 0.8 ;; 11|emerald) save_theme "emerald"; echo -e "\n${GREEN}✓ Theme switched to Emerald Isle!${NC}"; sleep 0.8; ;; 12|classic) save_theme "classic"; echo -e "\n${GREEN}✓ Theme switched to Classic ANSI!${NC}"; sleep 0.8 ;;
13|cosmic|supernova|cosmic_supernova|"cosmic supernova"|"Cosmic Supernova"|"Cosmic Supernova [Special Edition]"|"Cosmic Supernova MP Mix Manager")
save_theme "cosmic_supernova"; echo -e "\n${BOLD}${GREEN}✓ Theme switched to Cosmic Supernova [Special Edition]!${NC}"; sleep 0.8 ;;
14|retro|terminal|retro_terminal|unix_terminal|retro_unix|old_style_unix|unix_retro|white_on_black|"Old Style Unix Terminal Retro Mode (White on Black)"|"Old Style Unix Terminal Retro Mode"|"Old Style Unix Terminal")
save_theme "retro_terminal"; echo -e "\n${BOLD}${GREEN}✓ Theme switched to Old Style Unix Terminal Retro Mode (White on Black)!${NC}"; sleep 0.8 ;;
15|liquid|glass|dreamworlds_liquid|mp_dreamworlds_liquid_transparency|liquid_transparency|"MP Dreamworlds Liquid Transparency"|"MP Dreamworlds Liquid Transparency [Special Edition]")
save_theme "dreamworlds_liquid"; echo -e "\n${BOLD}${GREEN}✓ Theme switched to MP Dreamworlds Liquid Transparency [Special Edition]!${NC}"; sleep 0.8 ;;
16|dynamic_rainbow_liquid_glass|dynamic_liquid_glass_rainbow|dynamic_rainbow|rainbow|"Dynamic Liquid Glass [Rainbow Colours] (New)"|"Dynamic Liquid Glass [Rainbow Colours]")
save_theme "dynamic_rainbow_liquid_glass"; echo -e "\n${BOLD}${GREEN}✓ Theme switched to Dynamic Liquid Glass [Rainbow Colours] (New)!${NC}"; sleep 0.8 ;;
17|cosmic_dreamworlds_radioactive|radioactive|cosmic_radioactive|"Cosmic Dreamworlds Radioactive (Liquid Glass Skin)"|"Cosmic Dreamworlds Radioactive")
save_theme "cosmic_dreamworlds_radioactive"; echo -e "\n${BOLD}${GREEN}✓ Theme switched to Cosmic Dreamworlds Radioactive (Liquid Glass Skin)!${NC}"; sleep 0.8 ;;
18|cosmic_dreamworlds|cosmic_dream|cosmic_dreamworld|"Cosmic Dreamworlds (Liquid Glass Skin)"|"Cosmic Dreamworlds")
save_theme "cosmic_dreamworlds"; echo -e "\n${BOLD}${GREEN}✓ Theme switched to Cosmic Dreamworlds (Liquid Glass Skin)!${NC}"; sleep 0.8 ;;
19|orbital_void_reflux|orbital_void|void_reflux|orbital|"Orbital Void Reflux (Liquid Glass Skin)"|"Orbital Void Reflux")
save_theme "orbital_void_reflux"; echo -e "\n${BOLD}${GREEN}✓ Theme switched to Orbital Void Reflux (Liquid Glass Skin)!${NC}"; sleep 0.8 ;; 0|[bB]|[qQ]|ESC) return 0; ;; *) echo -e "\n${RED}Invalid choice!${NC}"; sleep 1.2; ;; esac; done
}
_LAST_PERF_CHECK=0; _CACHED_PERF_DISPLAY=""
get_system_perf_stats() {
local now="${EPOCHSECONDS:-0}"; [ "$now" -eq 0 ] && printf -v now '%(%s)T' -1 2>/dev/null; [ "${now:-0}" -eq 0 ] && now=$(date +%s 2>/dev/null || echo 0); local _perf_dir="${HOME}/.config/mix-manager"; local _perf_file="${_perf_dir}/perf_display.cache"; local _perf_stamp="${_perf_dir}/perf_display.stamp"; local _perf_last=0; if [ -f "$_perf_stamp" ]; then read -r _perf_last < "$_perf_stamp" 2>/dev/null || _perf_last=0; fi; [[ "${_perf_last:-}" =~ ^[0-9]+$ ]] || _perf_last=0; local _perf_fresh=0; if [ -f "$_perf_file" ] && [ $((now - _perf_last)) -lt 30 ]; then _perf_fresh=1; fi; if [ "$_perf_fresh" -eq 1 ] || [ "${_MENU_CURSOR_LOCK:-0}" -eq 1 ]; then if [ -f "$_perf_file" ]; then local _perf_cached=""; IFS= read -r _perf_cached < "$_perf_file" || true; if [ -n "$_perf_cached" ]; then _CACHED_PERF_DISPLAY="$_perf_cached"; printf '%b\n' "$_perf_cached"; return 0; fi; fi; if [ "${_MENU_CURSOR_LOCK:-0}" -eq 1 ]; then return 0; fi; fi; if [ $((now - _LAST_PERF_CHECK)) -lt 5 ] && [ -n "$_CACHED_PERF_DISPLAY" ]; then echo -e "$_CACHED_PERF_DISPLAY"; return 0; fi; _LAST_PERF_CHECK="$now"; local cpu_info="" ram_info="" disk_info=""; if [ "$OS_TYPE" = "windows" ] || [ "$OS_TYPE" = "wsl" ]; then cpu_info="Active"; elif [ -f /proc/loadavg ]; then local l1 l5 _; read -r l1 l5 _ < /proc/loadavg; cpu_info="${l1} (1m), ${l5} (5m)"; elif [ "$OS_TYPE" = "macos" ] || [ "$OS_TYPE" = "freebsd" ]; then local raw_load l1 l5; raw_load=$(sysctl -n vm.loadavg 2>/dev/null); raw_load="${raw_load#\{ }"; raw_load="${raw_load% \}}"; read -r l1 l5 _ <<< "$raw_load"; [ -n "$l1" ] && cpu_info="${l1} ${l5}" || cpu_info="Active"; else cpu_info="Active"; fi; if [ -f /proc/meminfo ]; then local mem_total="" mem_avail="" mem_used mem_total_g mem_used_g mem_pct key val; while read -r key val _; do case "$key" in MemTotal:*)     mem_total="$val" ;; MemAvailable:*) mem_avail="$val" ;; esac; [ -n "$mem_total" ] && [ -n "$mem_avail" ] && break; done < /proc/meminfo; if [ -n "$mem_total" ] && [ -n "$mem_avail" ] && [ "$mem_total" -gt 0 ]; then mem_used=$((mem_total - mem_avail)); mem_total_g="$((mem_total / 1048576)).$(( (mem_total % 1048576) * 10 / 1048576 ))"; mem_used_g="$((mem_used / 1048576)).$(( (mem_used % 1048576) * 10 / 1048576 ))"; mem_pct=$(( (mem_used * 100) / mem_total )); ram_info="${mem_used_g}G/${mem_total_g}G (${mem_pct}%)"; fi; elif [ "$OS_TYPE" = "freebsd" ]; then local mem_bytes page_size free_pages mem_total_g mem_used_g mem_pct; mem_bytes=$(sysctl -n hw.physmem 2>/dev/null); page_size=$(sysctl -n hw.pagesize 2>/dev/null || echo 4096); free_pages=$(sysctl -n vm.stats.vm.v_free_count 2>/dev/null || echo 0); if [ -n "$mem_bytes" ] && [ "$mem_bytes" -gt 0 ]; then local free_bytes=$(( free_pages * page_size )); local used_bytes=$(( mem_bytes - free_bytes )); mem_total_g="$((mem_bytes / 1073741824)).$(( (mem_bytes % 1073741824) * 10 / 1073741824 ))"; mem_used_g="$((used_bytes / 1073741824)).$(( (used_bytes % 1073741824) * 10 / 1073741824 ))"; mem_pct=$(( (used_bytes * 100) / mem_bytes )); ram_info="${mem_used_g}G/${mem_total_g}G (${mem_pct}%)"; fi; fi; [ -z "$ram_info" ] && ram_info="Available"; local mix_target="${MIX_ARCHIVE_DIR:-$SCRIPT_DIR/MIX_ARCHIVE}"; local d_avail="" d_pct="" a="" p=""; while read -r _ _ _ a p _; do [ -n "$a" ] && [ "$a" != "Avail" ] && d_avail="$a" && d_pct="$p"; done < <(df -h "$mix_target" 2>/dev/null); if [ -n "$d_avail" ]; then disk_info="${d_avail} free (${d_pct} used)"; else disk_info="Mounted"; fi; _CACHED_PERF_DISPLAY="  ${BOLD}${CYAN}⚡ CPU Load:${NC} ${cpu_info}  ${BOLD}${BLUE}│${NC}  ${BOLD}${CYAN}🧠 RAM:${NC} ${ram_info}  ${BOLD}${BLUE}│${NC}  ${BOLD}${CYAN}💾 Mix Drive Free:${NC} ${disk_info}"; mkdir -p "$_perf_dir" 2>/dev/null || true; local _perf_tmp="${_perf_file}.$$"; printf '%s\n' "$_CACHED_PERF_DISPLAY" > "$_perf_tmp" 2>/dev/null && mv -f "$_perf_tmp" "$_perf_file" 2>/dev/null || rm -f "$_perf_tmp" 2>/dev/null || true; printf '%s\n' "$now" > "$_perf_stamp" 2>/dev/null || true; echo -e "$_CACHED_PERF_DISPLAY"
}
_maybe_refresh_perf_cache() {
local now="${EPOCHSECONDS:-0}"; [ "$now" -eq 0 ] && printf -v now '%(%s)T' -1 2>/dev/null; [ "${now:-0}" -eq 0 ] && now=$(date +%s 2>/dev/null || echo 0); local stamp="${HOME}/.config/mix-manager/perf_display.stamp"; local last=0; [ -f "$stamp" ] && { read -r last < "$stamp" 2>/dev/null || last=0; }; [[ "$last" =~ ^[0-9]+$ ]] || last=0; [ $((now - last)) -lt 30 ] && return 0; if [ -n "${_PERF_REFRESH_PID:-}" ] && kill -0 "$_PERF_REFRESH_PID" 2>/dev/null; then return 0; fi
(
_MENU_CURSOR_LOCK=0; get_system_perf_stats &>/dev/null || true
) &
_PERF_REFRESH_PID=$!
}
_LAST_AUDIO_IFACE_CHECK=0; _CACHED_AUDIO_IFACE_DISPLAY=""
get_active_audio_interface_display() {
local now="${EPOCHSECONDS:-0}"; [ "$now" -eq 0 ] && printf -v now '%(%s)T' -1 2>/dev/null; [ "${now:-0}" -eq 0 ] && now=$(date +%s 2>/dev/null || echo 0); if [ $((now - _LAST_AUDIO_IFACE_CHECK)) -lt 30 ] && [ -n "$_CACHED_AUDIO_IFACE_DISPLAY" ]; then echo -e "$_CACHED_AUDIO_IFACE_DISPLAY"; return 0; fi; _LAST_AUDIO_IFACE_CHECK="$now"; local script_py="$SCRIPT_DIR/scripts/get_audio_interface.py"; [ ! -f "$script_py" ] && script_py="$PWD/scripts/get_audio_interface.py"; if [ -f "$script_py" ]; then local raw; raw=$(python3 "$script_py" 2>/dev/null); if [ -n "$raw" ]; then local iface latency sys_mode; IFS='|' read -r iface latency sys_mode <<< "$raw"; if [ -n "$iface" ]; then _CACHED_AUDIO_IFACE_DISPLAY="  ${BOLD}${CYAN}🎧 Audio Interface:${NC} ${WHITE}${iface}${NC}  ${BOLD}${BLUE}│${NC}  ${BOLD}${CYAN}⚡ Latency:${NC} ${GREEN}${latency:-Active}${NC}  ${BOLD}${BLUE}│${NC}  ${BOLD}${CYAN}🎛️ Engine:${NC} ${sys_mode:-Audio}"; echo -e "$_CACHED_AUDIO_IFACE_DISPLAY"; return 0; fi; fi; fi; return 1
}
_LAST_ALARM_STATUS_CHECK=0; _CACHED_ALARM_CLOCK_STATUS=""
get_alarm_clock_status_display() {
local now="${EPOCHSECONDS:-0}"; [ "$now" -eq 0 ] && printf -v now '%(%s)T' -1 2>/dev/null; [ "${now:-0}" -eq 0 ] && now=$(date +%s 2>/dev/null || echo 0); if [ $((now - _LAST_ALARM_STATUS_CHECK)) -lt 30 ] && [ -n "$_CACHED_ALARM_CLOCK_STATUS" ]; then echo -e "$_CACHED_ALARM_CLOCK_STATUS"; return 0; fi; _LAST_ALARM_STATUS_CHECK="$now"; local script_py="$SCRIPT_DIR/scripts/get_alarm_clock_status.py"; [ ! -f "$script_py" ] && script_py="$PWD/scripts/get_alarm_clock_status.py"; if [ -f "$script_py" ] && command -v python3 &>/dev/null; then _CACHED_ALARM_CLOCK_STATUS="$(python3 "$script_py" 2>/dev/null)"; elif [ -x "$SCRIPT_DIR/scripts/get_alarm_clock_status.sh" ]; then _CACHED_ALARM_CLOCK_STATUS="$("$SCRIPT_DIR/scripts/get_alarm_clock_status.sh" 2>/dev/null)"; fi; [ -n "$_CACHED_ALARM_CLOCK_STATUS" ] && echo -e "$_CACHED_ALARM_CLOCK_STATUS"
}
_LAST_SPEC_TARGET=""; _CACHED_SPEC_SUMMARY=""
get_playing_audio_spec_summary() {
local target_file="$1"; if [ -n "$target_file" ] && [ "$target_file" = "$_LAST_SPEC_TARGET" ] && [ -n "$_CACHED_SPEC_SUMMARY" ]; then echo "$_CACHED_SPEC_SUMMARY"; return 0; fi; local script_py="$SCRIPT_DIR/scripts/inspect_playing_audio.py"; [ ! -f "$script_py" ] && script_py="$PWD/scripts/inspect_playing_audio.py"; if [ -f "$script_py" ]; then if [ -n "$target_file" ] && [ -f "$target_file" ]; then _CACHED_SPEC_SUMMARY="$(python3 "$script_py" "$target_file" --summary 2>/dev/null)"; _LAST_SPEC_TARGET="$target_file"; else _CACHED_SPEC_SUMMARY="$(python3 "$script_py" --summary 2>/dev/null)"; _LAST_SPEC_TARGET=""; fi; [ -n "$_CACHED_SPEC_SUMMARY" ] && echo "$_CACHED_SPEC_SUMMARY"; fi
}
inspect_playing_audio_file() {
local target="$1"; local script_sh="$SCRIPT_DIR/scripts/inspect_playing_audio.sh"; [ ! -f "$script_sh" ] && script_sh="$PWD/scripts/inspect_playing_audio.sh"; if [ -x "$script_sh" ]; then if [ -n "$target" ]; then "$script_sh" "$target"; else "$script_sh"; fi; else local script_py="$SCRIPT_DIR/scripts/inspect_playing_audio.py"; [ ! -f "$script_py" ] && script_py="$PWD/scripts/inspect_playing_audio.py"; if [ -f "$script_py" ]; then if [ -n "$target" ]; then python3 "$script_py" "$target"; else python3 "$script_py"; fi; else echo -e "\n${RED}Error: inspect_playing_audio script not found in scripts/!${NC}"; sleep 1.5; fi; fi
}
launch_traktor_monitor_window() {
local mon_sh=""; if [ -x "$SCRIPT_DIR/scripts/traktor_monitor.sh" ]; then mon_sh="$SCRIPT_DIR/scripts/traktor_monitor.sh"; elif [ -x "$SCRIPT_DIR/traktor_monitor.sh" ]; then mon_sh="$SCRIPT_DIR/traktor_monitor.sh"; elif [ -x "$HOME/.local/bin/traktor-monitor" ]; then mon_sh="$HOME/.local/bin/traktor-monitor"; elif command -v traktor-monitor &>/dev/null; then mon_sh="$(command -v traktor-monitor)"; elif [ -f "$SCRIPT_DIR/scripts/traktor_monitor.py" ]; then mon_sh="$SCRIPT_DIR/scripts/traktor_monitor.py"; elif [ -f "$PWD/scripts/traktor_monitor.py" ]; then mon_sh="$PWD/scripts/traktor_monitor.py"; fi; if [ -z "$mon_sh" ]; then echo -e "\n${RED}Error: traktor_monitor.sh / traktor-monitor was not found in scripts/ or PATH!${NC}"; press_enter; return 1; fi; echo -e "\n${BOLD}${CYAN}═══════════════════════════════════════════════════════════════════════════════${NC}\n${BOLD}${CYAN}       🎛️  TRAKTOR PRO LIVE MONITOR & AUDIO RECORDER CONTROL  🎛️               ${NC}\n${BOLD}${CYAN}═══════════════════════════════════════════════════════════════════════════════${NC}\n  ${BOLD}Process Metrics:${NC}   Traktor CPU %, RSS RAM, Thread Count & Execution State\n  ${BOLD}Deck Tracking:${NC}     Active open audio files & deck playback detection\n  ${BOLD}Audio Recorder:${NC}    Live WAV write detection, file-growth tracking & standby\n  ${BOLD}Hardware & I/O:${NC}    Traktor audio device, sample rate, latency & buffer size\n  ${BOLD}Hotkeys in Live:${NC}   [s] Start Rec  │  [x] Stop Rec  │  [t] Toggle Rec  │  [c] Switch Theme  │  [q] Quit\n  ${BOLD}Cross-Platform:${NC}    macOS (AppleScript UI), Windows 10 & 11, Linux (Bazzite/Fedora)\n${BOLD}${CYAN}───────────────────────────────────────────────────────────────────────────────${NC}\nSelect launch target:\n  ${BOLD}${CYAN}1)${NC} Launch Live Monitor in ${BOLD}${GREEN}New Terminal Window${NC} (Recommended)\n  ${BOLD}${CYAN}2)${NC} Run Live Monitor in Current Terminal Window\n  ${BOLD}${CYAN}3)${NC} Single Diagnostic Status Snapshot (--once)\n  ${BOLD}${CYAN}4)${NC} Trigger Traktor Audio Recording: ${GREEN}START RECORDING${NC}\n  ${BOLD}${CYAN}5)${NC} Trigger Traktor Audio Recording: ${RED}STOP RECORDING${NC}\n  ${BOLD}${CYAN}6)${NC} Trigger Traktor Audio Recording: ${YELLOW}TOGGLE RECORDING${NC}\n  ${BOLD}${CYAN}7)${NC} Traktor Monitor Color Themes (14 MP Themes & Previews)\n  ${BOLD}${CYAN}0)${NC} Return to Main Menu"; echo ""; local tm_choice; read -r -p "Enter choice [1-7, default: 1]: " tm_choice; tm_choice="${tm_choice:-1}"; case "$tm_choice" in 1) if ! pgrep -i -f "Traktor" &>/dev/null; then echo -e "\n${BOLD}${YELLOW}Traktor Pro is not running. Opening Traktor Pro...${NC}"; launch_traktor &>/dev/null || true; sleep 1.5; fi; echo -e "\n${BOLD}${GREEN}Launching Traktor Live Monitor in a new terminal window...${NC}\n"; local full_cmd; printf -v full_cmd '%q; echo ""; echo "Traktor monitor closed. Press [Enter] to exit..."; read -r' "$mon_sh"; if launch_in_terminal "Traktor Live Monitor" "$full_cmd" "window"; then echo -e "${GREEN}✓ Traktor Live Monitor launched in standalone window.${NC}"; sleep 1.2; else echo -e "${YELLOW}External terminal emulator not available; running in current window...${NC}\n"; sleep 0.8; trap ':' INT; "$mon_sh"; trap 'exit_mix_manager' INT; press_enter; fi ;; 2) if ! pgrep -i -f "Traktor" &>/dev/null; then echo -e "\n${BOLD}${YELLOW}Traktor Pro is not running. Opening Traktor Pro...${NC}"; launch_traktor &>/dev/null || true; sleep 1.5; fi; echo -e "\n${BOLD}${YELLOW}Launching Traktor Live Monitor in current window (Press 'q' to quit)...${NC}\n"; sleep 0.8; trap ':' INT; "$mon_sh"; trap 'exit_mix_manager' INT; press_enter; ;; 3) echo -e "\n${BOLD}${YELLOW}Querying Traktor Diagnostic Snapshot...${NC}\n"; "$mon_sh" --once; echo ""; press_enter
;; 4) echo -e "\n${BOLD}${YELLOW}Sending START RECORDING trigger to Traktor...${NC}\n"; "$mon_sh" --start-recording; echo ""; press_enter; ;; 5) echo -e "\n${BOLD}${YELLOW}Sending STOP RECORDING trigger to Traktor...${NC}\n"; "$mon_sh" --stop-recording; echo ""; press_enter; ;; 6) echo -e "\n${BOLD}${YELLOW}Sending TOGGLE RECORDING trigger to Traktor...${NC}\n"; "$mon_sh" --toggle-recording; echo ""; press_enter; ;; 7) echo -e "\n${BOLD}${CYAN}Loading Traktor Monitor Theme Browser...${NC}\n"; "$mon_sh" --list-themes; echo ""; read -r -p "Enter theme name to activate (or press Enter to cancel): " thm_in; thm_in="${thm_in//[\'\"]}"; if [ -n "$thm_in" ]; then "$mon_sh" --set-theme "$thm_in"; fi; echo ""; press_enter; ;; 0|[qQ]) return 0 ;; *) echo -e "\n${RED}Invalid choice!${NC}"; sleep 1.2 ;; esac
}
show_mix_drive_space() {
clear; echo -e "${BOLD}${MAGENTA}${S70}${NC}\n${BOLD}${MAGENTA}       MIX STORAGE DRIVES - DISK SPACE & INVENTORY USAGE REPORT       ${NC}\n${BOLD}${MAGENTA}${S70}${NC}\n"; local all_arch_dirs=(); local adir; while IFS= read -r adir; do [ -n "$adir" ] && all_arch_dirs+=("$adir"); done < <(get_all_mix_archive_dirs); if [ ${#all_arch_dirs[@]} -eq 0 ]; then all_arch_dirs=("${MIX_ARCHIVE_DIR:-$SCRIPT_DIR/MIX_ARCHIVE}"); fi; local folder_audio_bytes=(); local folder_audio_gbs=(); local folder_flacs=(); local folder_wavs=(); local folder_mp3s=(); local total_audio_bytes=0; local total_flacs_all=0; local total_wavs_all=0; local total_mp3s_all=0; local d_path d_bytes d_gb d_flac d_wav d_mp3; while IFS=$'\t' read -r d_path d_bytes d_gb d_flac d_wav d_mp3; do folder_audio_bytes+=("${d_bytes:-0}"); folder_audio_gbs+=("${d_gb:-0.00}"); folder_flacs+=("${d_flac:-0}"); folder_wavs+=("${d_wav:-0}"); folder_mp3s+=("${d_mp3:-0}"); total_audio_bytes=$((total_audio_bytes +${d_bytes:-0})); total_flacs_all=$((total_flacs_all +${d_flac:-0})); total_wavs_all=$((total_wavs_all +${d_wav:-0})); total_mp3s_all=$((total_mp3s_all +${d_mp3:-0}))
done < <(python3 -c "
import os, sys
for d in sys.argv[1:]:
    total = flacs = wavs = mp3s = 0
    if os.path.isdir(d):
        d_norm = os.path.normpath(d)
        is_mp3_dir = os.path.basename(d_norm).lower() == 'mp3_converted_outputs'
        has_mp3_sub = os.path.isdir(os.path.join(d, 'MP3_CONVERTED_OUTPUTS'))
        for root, _, files in os.walk(d):
            rel = '' if root == d else os.path.relpath(root, d)
            depth = 0 if not rel or rel == '.' else rel.count(os.sep) + 1
            in_mp3_sub = 'mp3_converted_outputs' in root.lower()
            if depth > 1 and not in_mp3_sub:
                continue
            for f in files:
                ext = os.path.splitext(f)[1].lower()
                fp = os.path.join(root, f)
                if ext == '.flac' and depth <= 1:
                    flacs += 1
                    try: total += os.path.getsize(fp)
                    except OSError: pass
                elif ext == '.wav' and depth <= 1:
                    wavs += 1
                    try: total += os.path.getsize(fp)
                    except OSError: pass
                elif ext == '.mp3':
                    if (has_mp3_sub and in_mp3_sub and depth == 1) or ((not has_mp3_sub or is_mp3_dir) and depth == 0):
                        mp3s += 1
                        try: total += os.path.getsize(fp)
                        except OSError: pass
    print(f'{d}\t{total}\t{total / (1024 ** 3):.2f}\t{flacs}\t{wavs}\t{mp3s}')
" "${all_arch_dirs[@]}")
local loc_num=1; local total_free_kb=0; declare -A seen_mounts=(); local folder_fs=(); local folder_mounts=(); local folder_totals=(); local folder_used=(); local folder_free=(); local folder_pcts=(); local full_blocks="███████████████████████████████████"; local empty_blocks="░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░"; local idx; for idx in "${!all_arch_dirs[@]}"; do local mix_target="${all_arch_dirs[$idx]}"; echo -e "${BOLD}${CYAN}──────────────────────────────────────────────────────────────────────${NC}"; local label="Primary Archive"; [ "$loc_num" -gt 1 ] && label="Additional Storage Location #${loc_num}"; echo -e "  [${BOLD}${YELLOW}${label}${NC}] ➔ ${BOLD}${WHITE}${mix_target}${NC}\n${BOLD}${CYAN}──────────────────────────────────────────────────────────────────────${NC}"; if [ ! -d "$mix_target" ]; then echo -e "  ${YELLOW}⚠️  Directory is currently unmounted or not accessible.${NC}\n"; folder_fs+=("N/A"); folder_mounts+=("Unmounted"); folder_totals+=("N/A"); folder_used+=("N/A"); folder_free+=("N/A"); folder_pcts+=("N/A"); ((loc_num++)); continue; fi; local _df_line fs total_kb used_kb avail_kb cap_pct mount_pt; { read -r _; read -r _df_line; } < <(df -k -P "$mix_target" 2>/dev/null); read -r fs total_kb used_kb avail_kb cap_pct mount_pt <<< "$_df_line"; if [ -n "$mount_pt" ] && [ -z "${seen_mounts[$mount_pt]+_}" ]; then seen_mounts["$mount_pt"]=1; total_free_kb=$((total_free_kb +${avail_kb:-0})); fi; local _hdr _line fs_dev type total used avail pct mount; if { read -r _hdr && read -r _line; } < <(df -h -T "$mix_target" 2>/dev/null); then read -r fs_dev type total used avail pct mount <<< "$_line"; elif { read -r _hdr && read -r _line; } < <(df -h "$mix_target" 2>/dev/null); then read -r fs_dev total used avail pct mount <<< "$_line"; type="filesystem"; fi; echo -e "  ${BOLD}Device Filesystem:${NC}   ${CYAN}${fs_dev}${NC} (${type})\n  ${BOLD}Mount Point:${NC}${GREEN}${mount}${NC}\n  ${BOLD}Total Capacity:${NC}${total}\n  ${BOLD}Space Used:${NC}          ${YELLOW}${used}${NC} (${pct})\n  ${BOLD}Space Remaining:${NC}     ${BOLD}${GREEN}${avail}${NC} free"; local pct_num="${pct//[!0-9]/}"; if [ -n "$pct_num" ]; then local bar_len=35; local filled=$(( (pct_num * bar_len) / 100 )); [ "$filled" -gt "$bar_len" ] && filled="$bar_len"; local empty=$(( bar_len - filled )); local bar="${full_blocks:0:filled}${empty_blocks:0:empty}"; local bar_color="${GREEN}"; [ "$pct_num" -ge 75 ] && bar_color="${YELLOW}"; [ "$pct_num" -ge 90 ] && bar_color="${RED}"; echo -e "  ${BOLD}Usage Graph:${NC}         [${bar_color}${bar}${NC}]${BOLD}${pct}${NC}"; fi; local flac_count="${folder_flacs[$idx]:-0}"; local wav_count="${folder_wavs[$idx]:-0}"; local mp3_count="${folder_mp3s[$idx]:-0}"; local f_gb="${folder_audio_gbs[$idx]:-0.00}"; folder_fs+=("$fs_dev")
folder_mounts+=("$mount"); folder_totals+=("$total"); folder_used+=("$used"); folder_free+=("$avail"); folder_pcts+=("$pct"); echo -e "  ${BOLD}Audio Consumed:${NC}${CYAN}${f_gb} GB${NC}\n  ${BOLD}Audio Files Hosted:${NC}${GREEN}${flac_count}${NC} FLACs | ${CYAN}${wav_count}${NC} WAVs | ${YELLOW}${mp3_count}${NC} MP3s\n"; ((loc_num++)); done; local total_master_mixes=$((total_flacs_all + total_wavs_all + total_mp3s_all)); local total_folders_configured=${#all_arch_dirs[@]}; local cons_int=$(( total_audio_bytes / 1073741824 )); local cons_frac=$(( (total_audio_bytes % 1073741824) * 100 / 1073741824 )); local total_consumed_gb; printf -v total_consumed_gb "%d.%02d" "$cons_int" "$cons_frac"; local free_int=$(( total_free_kb / 1048576 )); local free_frac=$(( (total_free_kb % 1048576) * 100 / 1048576 )); local total_free_gb; printf -v total_free_gb "%d.%02d" "$free_int" "$free_frac"; echo -e "${BOLD}${MAGENTA}${S70}${NC}\n  Total FLAC Master Mixes Across All Drives: ${BOLD}${GREEN}${total_flacs_all}${NC}\n  Total WAV Master Mixes Across All Drives:  ${BOLD}${CYAN}${total_wavs_all}${NC}\n  Total MP3 Master Mixes Across All Drives:  ${BOLD}${YELLOW}${total_mp3s_all}${NC}\n${BOLD}${MAGENTA}${S70}${NC}\n  Total Mix Archive Master Mixes:              ${BOLD}${WHITE}${total_master_mixes}${NC}\n  Total Mix Archive Storage Folders Configured: ${BOLD}${GREEN}${total_folders_configured}${NC}\n  Total Space Consumed:                        ${BOLD}${CYAN}${total_consumed_gb} GB${NC}\n  Total Space Free:                            ${BOLD}${GREEN}${total_free_gb} GB${NC}\n${BOLD}${MAGENTA}${S70}${NC}\n\n${BOLD}${CYAN}──────────────────────────────────────────────────────────────────────${NC}\n  ${BOLD}${WHITE}Configured Mix Archive Storage Folders Breakdown${NC}\n${BOLD}${CYAN}──────────────────────────────────────────────────────────────────────${NC}"; for ((idx=0; idx<${#all_arch_dirs[@]}; idx++)); do local f_num=$((idx + 1)); local f_path="${all_arch_dirs[$idx]}"; local f_fs="${folder_fs[$idx]}"; local f_mount="${folder_mounts[$idx]}"; local f_total="${folder_totals[$idx]}"; local f_used="${folder_used[$idx]}"; local f_free="${folder_free[$idx]}"; local f_pct="${folder_pcts[$idx]}"; local f_flac="${folder_flacs[$idx]:-0}"; local f_wav="${folder_wavs[$idx]:-0}"; local f_mp3="${folder_mp3s[$idx]:-0}"; local f_audio_gb="${folder_audio_gbs[$idx]:-0.00}"; local f_mix_total=$((f_flac + f_wav + f_mp3)); echo -e "  📁 ${BOLD}${YELLOW}[Folder #${f_num}]${NC} ${BOLD}${WHITE}${f_path}${NC}\n     ${BOLD}Drive Mount:${NC}    ${GREEN}${f_mount}${NC} (${CYAN}${f_fs}${NC})\n     ${BOLD}Space Free:${NC}     ${BOLD}${GREEN}${f_free}${NC} free\n     ${BOLD}Space Used:${NC}${YELLOW}${f_used}${NC} (${f_pct} of${f_total} capacity)\n     ${BOLD}Audio Consumed:${NC}${CYAN}${f_audio_gb} GB${NC}\n     ${BOLD}Mixes Tally:${NC}${GREEN}${f_flac}${NC} FLACs | ${CYAN}${f_wav}${NC} WAVs | ${YELLOW}${f_mp3}${NC} MP3s (Total: ${BOLD}${WHITE}${f_mix_total}${NC} mixes)"; echo ""; done; echo -e "${BOLD}${MAGENTA}${S70}${NC}"; press_enter
}
_norm_path() {
local p="${1#"${1%%[![:space:]]*}"}"; p="${p%"${p##*[![:space:]]}"}"; p="${p#[\"\']}"; p="${p%[\"\']}"; [[ "$p" =~ ^~(/.*)?$ ]] && p="${HOME}${p:1}"; p="${p//\\//}"; [[ ! "$p" =~ ^[a-zA-Z]:/$ && "$p" != "/" ]] && p="${p%/}"; REPLY="$p"
}
_load_extras() {
_EXTRA_LIST=(); local raw="${EXTRA_MIX_ARCHIVE_DIRS:-${MIX_ARCHIVE_DIRS:-}}" line; [ -z "$raw" ] && return; while IFS= read -r line || [ -n "$line" ]; do line="${line%$'\r'}"; [ -n "$line" ] && _EXTRA_LIST+=("$line"); done < <(parse_extra_mix_archive_dirs "$raw")
}
_cnt_flacs() {
local d="$1" depth="${2:-1}" f=(); [ ! -d "$d" ] && { echo 0; return; }; shopt -s nullglob nocaseglob; if [ "$depth" -eq 2 ]; then f=("$d"/*.flac "$d"/*/*.flac); else f=("$d"/*.flac); fi; shopt -u nullglob nocaseglob; echo "${#f[@]}"
}
_set_primary_dir() {
local d="$1" save_subs="${2:-1}"; mkdir -p "$d"/{FLAC_CONVERTED_OUTPUTS,CONVERTED_WAV_FILES,MP3_CONVERTED_OUTPUTS,WAV_CONVERTED_OUTPUTS,MP4_CONVERTED_OUTPUTS} 2>/dev/null || true; MIX_ARCHIVE_DIR="$d" MIX_ARCHIVE_CONFIGURED="true"; OUTPUT_DIR="$d/FLAC_CONVERTED_OUTPUTS" ARCHIVE_DIR="$d/CONVERTED_WAV_FILES"; MP3_OUTPUT_DIR="$d/MP3_CONVERTED_OUTPUTS" WAV_OUTPUT_DIR="$d/WAV_CONVERTED_OUTPUTS" MP4_OUTPUT_DIR="$d/MP4_CONVERTED_OUTPUTS"; export MIX_ARCHIVE_DIR MIX_ARCHIVE_CONFIGURED OUTPUT_DIR ARCHIVE_DIR MP3_OUTPUT_DIR WAV_OUTPUT_DIR MP4_OUTPUT_DIR; save_config_setting "MIX_ARCHIVE_DIR" "$d"; save_config_setting "MIX_ARCHIVE_CONFIGURED" "true"; if [ "$save_subs" -eq 1 ]; then save_config_setting "OUTPUT_DIR" "$OUTPUT_DIR"; save_config_setting "ARCHIVE_DIR" "$ARCHIVE_DIR"; save_config_setting "MP3_OUTPUT_DIR" "$MP3_OUTPUT_DIR"; save_config_setting "WAV_OUTPUT_DIR" "$WAV_OUTPUT_DIR"; save_config_setting "MP4_OUTPUT_DIR" "$MP4_OUTPUT_DIR"; fi; cd "$d" 2>/dev/null || true; play_sound_effect "storage"
}
add_extra_mix_archive_dir() {
_norm_path "$1"; local new_dir="$REPLY"; [ -z "$new_dir" ] && return 1; _load_extras; local e; for e in "${_EXTRA_LIST[@]}"; do [ "$e" = "$new_dir" ] && return 0; done; _EXTRA_LIST+=("$new_dir"); local IFS=';'; EXTRA_MIX_ARCHIVE_DIRS="${_EXTRA_LIST[*]}"; unset IFS; export EXTRA_MIX_ARCHIVE_DIRS; clear_archive_dir_cache; save_config_setting "EXTRA_MIX_ARCHIVE_DIRS" "$EXTRA_MIX_ARCHIVE_DIRS"; save_config_setting "MIX_ARCHIVE_CONFIGURED" "true"
}
remove_extra_mix_archive_dir() {
_norm_path "$1"; local target="$REPLY"; _load_extras; local kept=() e; for e in "${_EXTRA_LIST[@]}"; do [ -n "$e" ] && [ "$e" != "$target" ] && kept+=("$e"); done; local IFS=';'; EXTRA_MIX_ARCHIVE_DIRS="${kept[*]}"; unset IFS; export EXTRA_MIX_ARCHIVE_DIRS; clear_archive_dir_cache; save_config_setting "EXTRA_MIX_ARCHIVE_DIRS" "$EXTRA_MIX_ARCHIVE_DIRS"
}
configure_mix_archive_folder() {
local is_win=0; [[ "$OS_TYPE" =~ ^(windows|wsl)$ || "$UNAME_S" =~ (MINGW|MSYS|CYGWIN) ]] && is_win=1; while true; do local current_path="${MIX_ARCHIVE_DIR:-}" status_str prim_flacs=0; if is_mix_archive_configured && [ -d "$current_path" ]; then status_str="${GREEN}Configured & Accessible${NC}"; elif is_mix_archive_configured; then status_str="${YELLOW}Configured but Unmounted / Not Found${NC}"; else status_str="${RED}Not Configured (Defaulting to: ${SCRIPT_DIR}/MIX_ARCHIVE)${NC}"; fi; if [ -d "$current_path/FLAC_CONVERTED_OUTPUTS" ]; then prim_flacs=$(_cnt_flacs "$current_path/FLAC_CONVERTED_OUTPUTS" 1); elif [ -d "$current_path" ]; then prim_flacs=$(_cnt_flacs "$current_path" 1); fi; _load_extras; local status_hdr="Primary Archive Path     : ${BOLD}${CYAN}${current_path:-$SCRIPT_DIR/MIX_ARCHIVE}${NC} ${DIM}(${prim_flacs} FLACs)${NC}\n  • Primary Status           : ${status_str}\n"; if [ ${#_EXTRA_LIST[@]} -gt 0 ]; then status_hdr+="Additional Storage Paths :\n"; local e_idx=1 ed ed_stat; for ed in "${_EXTRA_LIST[@]}"; do ed_stat="${RED}Not Found${NC}"; [ -d "$ed" ] && ed_stat="${GREEN}Accessible ($(_cnt_flacs "$ed" 2) FLACs)${NC}"; status_hdr+="      ${BOLD}${CYAN}[${e_idx}]${NC} ${WHITE}${ed}${NC} ➔ ${ed_stat}\n"; ((e_idx++)); done; else status_hdr+="Additional Storage Paths : ${DIM}None configured (Single Archive Mode)${NC}\n"; fi; local cfg_opts=("1|Enter New Primary Mix Archive Folder Path|(Custom Directory Path)" "2|Auto-Detect & Select Primary from Connected Drives / Volumes|" "3|Reset Primary to Application Root Folder|(${SCRIPT_DIR}/MIX_ARCHIVE)" "4|Add New Additional Mix Archive Storage Location Folder|" "5|Remove an Additional Mix Archive Storage Location|" "6|Auto-Detect & Add Other Mix Folders from Connected Drives|" "7|View Detailed Space & Mix Inventory Across All Storage Folders|" "8|Clear All Additional Mix Archive Storage Locations|" "0|Return to Main Menu|(or Esc / q)"); run_interactive_submenu "CONFIGURE MIX ARCHIVE STORAGE FOLDERS (PRIMARY & MULTIPLE)" "$status_hdr" cfg_opts 0; local opt="$REPLY"; case "$opt" in 1|4) echo ""; if [ "$opt" = 1 ]; then echo -e "${BOLD}Enter full path to your Primary Mix Archive storage directory:${NC}"; [ "$is_win" -eq 1 ] && echo -e "${DIM}(e.g. Windows: G:\\My Drive\\MIX_ARCHIVE  or  B:\\MIX_ARCHIVE  or  /g/My Drive/MIX_ARCHIVE)${NC}" || echo -e "${DIM}(e.g. Linux: /run/media/${USER:-user}/WD BLACK B/MIX_ARCHIVE  or  macOS: /Volumes/EXTERNAL/MIX_ARCHIVE)${NC}"; read -e -r -p "Path: " raw_in
else echo -e "${BOLD}Enter full path to the Additional Mix Archive folder:${NC}"; [ "$is_win" -eq 1 ] && echo -e "${DIM}(e.g. Windows: G:\\My Drive\\MIX_ARCHIVE  or  D:\\Mixes\\FLAC_CONVERTED_OUTPUTS  or  /g/My Drive/MIX_ARCHIVE)${NC}" || echo -e "${DIM}(e.g. Linux: /run/media/${USER:-user}/DATA/MIX_ARCHIVE2/FLAC_CONVERTED_OUTPUTS/  or  macOS: /Volumes/EXTERNAL/MIX_ARCHIVE)${NC}"; read -e -r -p "Additional Archive Path: " raw_in
fi; _norm_path "$raw_in"; local target_dir="$REPLY"; [ -z "$target_dir" ] && continue; if [ ! -d "$target_dir" ]; then echo -e "\n${YELLOW}Directory does not exist:${NC} ${target_dir}"; read -r -p "Create this directory now? [y/N]: " ans; [[ ! "$ans" =~ ^[yY] ]] && continue; mkdir -p "$target_dir" 2>/dev/null || { echo -e "${RED}Error: Failed to create directory.${NC}"; sleep 2; continue; }; fi; if [ "$opt" = 1 ]; then _set_primary_dir "$target_dir" 1; echo -e "\n${GREEN}✓ Primary Mix Archive Folder successfully configured and saved!${NC}\n  Primary Location: ${BOLD}${WHITE}${target_dir}${NC}"; else add_extra_mix_archive_dir "$target_dir"; play_sound_effect "storage"; echo -e "\n${GREEN}✓ Additional Mix Archive Location successfully added and saved!${NC}\n  Location: ${BOLD}${WHITE}${target_dir}${NC}"; fi; sleep 2 ;; 2|6) echo -e "\n${CYAN}Scanning mounted drives and volumes for candidate mix folders...${NC}"; shopt -s nullglob; local candidates=("/run/media/$USER"/* "/run/media/mplanetarian"/* "/Volumes"/* "/media/$USER"/* "/mnt"/*); if [ "$is_win" -eq 1 ]; then local ltr; for ltr in {a..z}; do [ -d "/$ltr" ] && candidates+=("/$ltr"); done; fi; local found=() d sub; for d in "${candidates[@]}"; do [ ! -d "$d" ] && continue; if [ "$opt" = 6 ]; then for sub in "FLAC_CONVERTED_OUTPUTS" "MIX_ARCHIVE/FLAC_CONVERTED_OUTPUTS" "MIX_ARCHIVE2/FLAC_CONVERTED_OUTPUTS" "My Drive/MIX_ARCHIVE/FLAC_CONVERTED_OUTPUTS"; do [ -d "$d/$sub" ] && found+=("$d/$sub"); done; fi; for sub in "MIX_ARCHIVE" "MIX_ARCHIVE2" "My Drive/MIX_ARCHIVE" "Mixes" "MIXES"; do [ -d "$d/$sub" ] && found+=("$d/$sub"); done; [ "$opt" = 2 ] && found+=("$d"); done; shopt -u nullglob; local unique=() seen=" " prim_real=""; [ "$opt" = 6 ] && prim_real="$(cd "${MIX_ARCHIVE_DIR:-$SCRIPT_DIR/MIX_ARCHIVE}" 2>/dev/null && pwd -P)"; for d in "${found[@]}"; do local rd="$(cd "$d" 2>/dev/null && pwd -P || echo "$d")"; if [ "$opt" = 6 ]; then [ "$rd" = "$prim_real" ] && continue; local skip=0 ex; for ex in "${_EXTRA_LIST[@]}"; do [ "$rd" = "$(cd "$ex" 2>/dev/null && pwd -P || echo "$ex")" ] && { skip=1; break; }; done; [ "$skip" -eq 1 ] && continue; fi; if [[ "$seen" != *" $rd "* ]]; then seen+="$rd "; unique+=("$d"); fi; done; if [ ${#unique[@]} -eq 0 ]; then echo -e "\n${YELLOW}No candidate mix archive folders detected on mounted drives.${NC}"; sleep 1.5; continue; fi; echo -e "\n${BOLD}Available Storage Locations:${NC}"; local idx=1 u note; for u in "${unique[@]}"; do if [ "$opt" = 2 ]; then note=""; [ -d "$u/FLAC_CONVERTED_OUTPUTS" ] && note=" ${GREEN}(Contains FLAC_CONVERTED_OUTPUTS)${NC}"
else note=" ${GREEN}($(_cnt_flacs "$u" 2) FLAC files)${NC}"; fi; echo -e "  ${BOLD}${CYAN}${idx})${NC} ${u}${note}"; ((idx++)); done; echo -e "  ${BOLD}0)${NC} Back"; read -r -p "Select a location [1-${#unique[@]}, 0]: " sel; if [[ "$sel" =~ ^[0-9]+$ ]] && [ "$sel" -ge 1 ] && [ "$sel" -le "${#unique[@]}" ]; then local chosen="${unique[$((sel - 1))]//\\//}"; if [ "$opt" = 2 ]; then _set_primary_dir "$chosen" 1; echo -e "\n${GREEN}✓ Primary Mix Archive Folder successfully set to:${NC} ${BOLD}${WHITE}${chosen}${NC}"; else add_extra_mix_archive_dir "$chosen"; play_sound_effect "storage"; echo -e "\n${GREEN}✓ Added additional mix archive location:${NC} ${chosen}"; fi; sleep 2; fi ;; 3) local root_arch="$SCRIPT_DIR/MIX_ARCHIVE"; _set_primary_dir "$root_arch" 0; echo -e "\n${GREEN}✓ Primary Mix Archive Folder reset to Application Root Folder:${NC} ${BOLD}${WHITE}${root_arch}${NC}"; sleep 2 ;; 5) if [ ${#_EXTRA_LIST[@]} -eq 0 ]; then echo -e "\n${YELLOW}No additional mix archive locations currently configured.${NC}"; sleep 1.5; continue; fi; echo -e "\n${BOLD}Select an Additional Mix Archive Location to Remove:${NC}"; local r_idx=1 ed; for ed in "${_EXTRA_LIST[@]}"; do echo -e "  ${BOLD}${CYAN}${r_idx})${NC} ${ed}"; ((r_idx++)); done; echo -e "  ${BOLD}0)${NC} Cancel"; read -r -p "Enter number to remove [1-${#_EXTRA_LIST[@]}, 0]: " rem; if [[ "$rem" =~ ^[0-9]+$ ]] && [ "$rem" -ge 1 ] && [ "$rem" -le "${#_EXTRA_LIST[@]}" ]; then local target="${_EXTRA_LIST[$((rem - 1))]}"; remove_extra_mix_archive_dir "$target"; echo -e "\n${GREEN}✓ Removed:${NC} ${target}"; sleep 1.5; fi ;; 7) show_mix_drive_space ;; 8) read -r -p $'\n'"${YELLOW}Are you sure you want to clear all additional mix archive locations? [y/N]:${NC} " clr; if [[ "$clr" =~ ^[yY] ]]; then EXTRA_MIX_ARCHIVE_DIRS=""; export EXTRA_MIX_ARCHIVE_DIRS; clear_archive_dir_cache; save_config_setting "EXTRA_MIX_ARCHIVE_DIRS" ""; echo -e "\n${GREEN}✓ All additional storage locations cleared.${NC}"; sleep 1.5; fi ;; 0|[qQ]|ESC) return 0 ;; esac; done
}
manage_mix_conversion() {
local conv_sh="" s
for s in "$SCRIPT_DIR/Make_SOF_FLAC_CONVERSION.sh" "$SCRIPT_DIR/scripts/Make_SOF_FLAC_CONVERSION.sh" "./Make_SOF_FLAC_CONVERSION.sh"; do
[ -f "$s" ] && { conv_sh="$s"; break; };
done
[ -z "$conv_sh" ] && { echo -e "\n${RED}Error: Make_SOF_FLAC_CONVERSION.sh script not found!${NC}"; press_enter; return 1; }
local conv_opts=(
"1|Run Mix Conversion Wizard|(Interactive Output Format, Tags & Artwork Selection)"
"2|Convert to FLAC Lossless|(24-bit Lossless Archive Standard)"
"3|Convert to MP3 320 kbps|(High Quality CBR with Embedded Tags & Cover)"
"4|Convert to 24-bit WAV|(Mastering Quality Uncompressed Studio Audio)"
"5|Convert to YouTube Video MP4|(1080p / 4K with Static Cover Art)"
"6|Convert to OGG Vorbis|(320 kbps / Quality 8)"
"7|Retrieve Unconverted WAVs from Archive|(MOVE_NOT_CONVERTED_WAVS.sh)"
"8|Review Recent Conversion Logs & History|(FLAC_CONVERSION_SOF.log & JSONL)"
"0|Return to Main Menu|(or Esc / q)"
)
local conv_hdr="  ${BOLD}Stream of Frequency — Automated Ingestion & Batch Audio Conversion${NC}\n  Converts live DJ mixes into tagged, mastered formats with spectrograms & playlists.\n"
while true; do
run_interactive_submenu "STREAM OF FREQUENCY — RUN MIX CONVERSION SUITE" "$conv_hdr" conv_opts 1
case "$REPLY" in
1)
unset SOF_OUTPUT_FORMAT 2>/dev/null || true
bash "$conv_sh"
press_enter
;;
2)
SOF_OUTPUT_FORMAT="flac" bash "$conv_sh"
press_enter
;;
3)
SOF_OUTPUT_FORMAT="mp3" bash "$conv_sh"
press_enter
;;
4)
SOF_OUTPUT_FORMAT="wav" bash "$conv_sh"
press_enter
;;
5)
SOF_OUTPUT_FORMAT="mp4" bash "$conv_sh"
press_enter
;;
6)
SOF_OUTPUT_FORMAT="ogg" bash "$conv_sh"
press_enter
;;
7)
echo -e "\n${BOLD}${YELLOW}Retrieving unconverted WAV files...${NC}\n"
run_sub_script "MOVE_NOT_CONVERTED_WAVS.sh"
press_enter
;;
8)
local log_file="FLAC_CONVERSION_SOF.log"
[ ! -f "$log_file" ] && log_file="$SCRIPT_DIR/FLAC_CONVERSION_SOF.log"
if [ -s "$log_file" ]; then
echo -e "\n${BOLD}${CYAN}=== RECENT CONVERSION LOG: ${log_file} ===${NC}\n"
if command -v bat &>/dev/null; then
bat --paging=always "$log_file"
elif command -v less &>/dev/null; then
less -R "$log_file"
else
tail -n 45 "$log_file"
fi
else
echo -e "\n${YELLOW}No conversion log found yet (${log_file}).${NC}"
fi
press_enter
;;
0|[qQ]|[eE][xX][iI][tT]|ESC)
return 0
;;
*)
echo -e "\n${RED}Invalid option!${NC}"
sleep 1.2
;;
esac
done
}
manage_audio_conversion() {
local script="" s; for s in "$SCRIPT_DIR/convert_audio_format.sh" "$SCRIPT_DIR/scripts/convert_audio_format.sh" "./convert_audio_format.sh"; do [ -f "$s" ] && { script="$s"; break; }; done; [ -z "$script" ] && { echo -e "\n${RED}Error: convert_audio_format.sh script not found!${NC}"; press_enter; return 1; }; local conv_opts=("1|Convert Single Audio File|(Interactive Selection & Auto-Split Prompt)" "2|Convert Current Staging WAV / OGG Files|(in ${PWD})" "3|Convert All WAV / OGG in CONVERTED_WAV_FILES/|(Archive batch)" "4|Convert FLAC Outputs to MP3 & OGG Vorbis|(320kbps CBR / Vorbis q8)" "5|WAV-to-WAV Bit Depth Conversion|(16/24/32-bit Float)" "6|Split Audio File into Parts & Generate Spek Spectrograms|(FLAC, MP3, OGG, WAV)" "7|EBU R128 Loudness Scanner & True-Peak Analyzer|(master_audio_loudness.py)" "8|Master & Normalize Loudness|(-14 LUFS Streaming / -16 LUFS Podcast / -23 LUFS)" "9|Standard Red Book CUE Sheet Generator & Audio Splitter|(generate_cue_sheet.py)" "10|Launch Full Interactive Converter CLI|(convert_audio_format.sh)" "11|Verify Audio Mastering Quality, True Peak & Mono Phase|(verify_audio_mastering.py)" "12|Embed Cover Art, Vorbis Tags & ReplayGain into Mixes|(tag_audio_metadata.py)" "0|Return to Main Menu|(or Esc / q)"); local conv_hdr="  Supported Formats: ${BOLD}FLAC, MP3, Ogg Vorbis, Opus, Apple AAC, WAV${NC}\n  WAV Bit Depths:    ${BOLD}32-bit Float, 32-bit Int, 24-bit PCM, 16-bit 44.1kHz PCM${NC}\n"; while true; do run_interactive_submenu "AUDIO FORMAT & BIT DEPTH CONVERTER" "$conv_hdr" conv_opts 0; case "$REPLY" in 1)  bash "$script" -i; press_enter ;; 2)  bash "$script" -c; press_enter ;; 3)  bash "$script" -w; press_enter ;; 4)  bash "$script" -f -o mp3 -b 320k; press_enter ;; 5)  bash "$script" -w -o wav -d 24; press_enter ;; 6)  split_flac_audio; press_enter ;; 7|8) [ -f "$SCRIPT_DIR/scripts/master_audio_loudness.py" ] && python3 "$SCRIPT_DIR/scripts/master_audio_loudness.py" || echo -e "\n${RED}Error: master_audio_loudness.py not found!${NC}"; press_enter ;; 9) [ -f "$SCRIPT_DIR/scripts/generate_cue_sheet.py" ] && python3 "$SCRIPT_DIR/scripts/generate_cue_sheet.py" || echo -e "\n${RED}Error: generate_cue_sheet.py not found!${NC}"; press_enter ;; 10) bash "$script"; press_enter ;; 11) echo -e "\n${BOLD}${BLUE}=== VERIFY AUDIO MASTERING QUALITY & MONO COMPATIBILITY ===${NC}\n"; read -r -p "Enter path to audio file (or drag & drop): " v_t; _norm_path "$v_t"; v_t="$REPLY"; [ -n "$v_t" ] && [ -f "$v_t" ] && python3 "$SCRIPT_DIR/scripts/verify_audio_mastering.py" "$v_t" || echo -e "${RED}Error: File not found.${NC}"; press_enter ;; 12) echo -e "\n${BOLD}${BLUE}=== EMBED COVER ART, METADATA & REPLAYGAIN ===${NC}\n"; read -r -p "Enter path to audio file or directory: " t_t; _norm_path "$t_t"; t_t="$REPLY"; if [ -n "$t_t" ]; then python3 "$SCRIPT_DIR/scripts/tag_audio_metadata.py" "$t_t"; invalidate_archive_stats_cache; else echo -e "${RED}Error: Target path cannot be empty.${NC}"; fi; press_enter ;; 0|[qQ]|[eE][xX][iI][tT]|ESC) return 0 ;; *) echo -e "\n${RED}Invalid option!${NC}"; sleep 1.2 ;; esac; done
}
detect_active_music_player() {
DETECTED_PLAYER_NAME="" DETECTED_TRACK_PATH="" DETECTED_TRACK_TITLE="" DETECTED_PLAYER_LABEL=""; local mp_ok=0 a_ok=0 s_ok=0 c_ok=0; get_mp_audio_player_track_info 2>/dev/null && mp_ok=1; get_audacious_track_info 2>/dev/null && a_ok=1; get_strawberry_track_info 2>/dev/null && s_ok=1; get_cliamp_track_info 2>/dev/null && c_ok=1; if [ "$mp_ok" -eq 1 ] && [ "$MP_PLAYER_STATE" = "playing" ]; then DETECTED_PLAYER_NAME="MP Audio Player" DETECTED_TRACK_PATH="$MP_PLAYER_RESOLVED_PATH" DETECTED_TRACK_TITLE="$MP_PLAYER_TITLE"; elif [ "$a_ok" -eq 1 ] && [ "$AUDACIOUS_STATE" = "playing" ]; then DETECTED_PLAYER_NAME="Audacious" DETECTED_TRACK_PATH="$AUDACIOUS_RESOLVED_PATH" DETECTED_TRACK_TITLE="$AUDACIOUS_TITLE"; elif [ "$s_ok" -eq 1 ] && [ "$STRAWBERRY_STATE" = "playing" ]; then DETECTED_PLAYER_NAME="Strawberry" DETECTED_TRACK_PATH="$STRAWBERRY_RESOLVED_PATH" DETECTED_TRACK_TITLE="$STRAWBERRY_TITLE"; elif [ "$c_ok" -eq 1 ] && [ "$CLIAMP_STATE" = "playing" ]; then DETECTED_PLAYER_NAME="cliamp" DETECTED_TRACK_PATH="$CLIAMP_RESOLVED_PATH" DETECTED_TRACK_TITLE="$CLIAMP_TITLE"; elif [ "$mp_ok" -eq 1 ] && [ -n "$MP_PLAYER_TITLE" ]; then DETECTED_PLAYER_NAME="MP Audio Player" DETECTED_TRACK_PATH="$MP_PLAYER_RESOLVED_PATH" DETECTED_TRACK_TITLE="$MP_PLAYER_TITLE"; elif [ "$a_ok" -eq 1 ] && [ -n "$AUDACIOUS_TITLE" ]; then DETECTED_PLAYER_NAME="Audacious" DETECTED_TRACK_PATH="$AUDACIOUS_RESOLVED_PATH" DETECTED_TRACK_TITLE="$AUDACIOUS_TITLE"; elif [ "$s_ok" -eq 1 ] && [ -n "$STRAWBERRY_TITLE" ]; then DETECTED_PLAYER_NAME="Strawberry" DETECTED_TRACK_PATH="$STRAWBERRY_RESOLVED_PATH" DETECTED_TRACK_TITLE="$STRAWBERRY_TITLE"; elif [ "$c_ok" -eq 1 ] && [ -n "$CLIAMP_TITLE" ]; then DETECTED_PLAYER_NAME="cliamp" DETECTED_TRACK_PATH="$CLIAMP_RESOLVED_PATH" DETECTED_TRACK_TITLE="$CLIAMP_TITLE"; else local procs; procs=$(pgrep -x "audacious|strawberry|cliamp|vlc|audacity|haruna|mpv|kodi" 2>/dev/null | xargs -r ps -o comm= -p 2>/dev/null || true); case "${procs,,}" in *audacious*)  DETECTED_PLAYER_NAME="Audacious"; DETECTED_TRACK_PATH="$AUDACIOUS_RESOLVED_PATH"; DETECTED_TRACK_TITLE="$AUDACIOUS_TITLE" ;; *strawberry*) DETECTED_PLAYER_NAME="Strawberry"; DETECTED_TRACK_PATH="$STRAWBERRY_RESOLVED_PATH"; DETECTED_TRACK_TITLE="$STRAWBERRY_TITLE" ;; *cliamp*)     DETECTED_PLAYER_NAME="cliamp"; DETECTED_TRACK_PATH="$CLIAMP_RESOLVED_PATH"; DETECTED_TRACK_TITLE="$CLIAMP_TITLE" ;; *vlc*)        DETECTED_PLAYER_NAME="VLC" ;; *audacity*)   DETECTED_PLAYER_NAME="Audacity" ;; *haruna*)     DETECTED_PLAYER_NAME="Haruna" ;; *mpv*)        DETECTED_PLAYER_NAME="mpv" ;; *kodi*)       DETECTED_PLAYER_NAME="Kodi" ;; *) if command -v playerctl &>/dev/null; then local raw_p; raw_p=$(timeout 1 playerctl -l 2>/dev/null | head -1); raw_p="${raw_p%%.*}"; if [ -n "$raw_p" ]; then case "${raw_p,,}" in audacious*)  DETECTED_PLAYER_NAME="Audacious" ;; strawberry*) DETECTED_PLAYER_NAME="Strawberry" ;; vlc*)        DETECTED_PLAYER_NAME="VLC" ;; haruna*)     DETECTED_PLAYER_NAME="Haruna" ;; mpv*)        DETECTED_PLAYER_NAME="mpv" ;; audacity*)   DETECTED_PLAYER_NAME="Audacity" ;; kodi*)       DETECTED_PLAYER_NAME="Kodi" ;; *)           DETECTED_PLAYER_NAME="$raw_p" ;; esac; fi; fi ;; esac; fi; if [ -n "$DETECTED_PLAYER_NAME" ] && [ -z "$DETECTED_TRACK_PATH" ]; then if command -v playerctl &>/dev/null; then local u; u=$(timeout 1 playerctl metadata xesam:url 2>/dev/null || true); [[ "$u" == file://* ]] && printf -v DETECTED_TRACK_PATH '%b' "${u#file://}" && DETECTED_TRACK_PATH=$(printf '%b' "${DETECTED_TRACK_PATH//%/\\x}"); [ -z "$DETECTED_TRACK_TITLE" ] && DETECTED_TRACK_TITLE=$(timeout 1 playerctl metadata xesam:title 2>/dev/null || true); fi; if [ -z "$DETECTED_TRACK_PATH" ]; then local dp; dp=$(detect_currently_playing_mix 2>/dev/null || true); [ -n "$dp" ] && [ -f "$dp" ] && DETECTED_TRACK_PATH="$dp"; fi; fi; if [ -n "$DETECTED_PLAYER_NAME" ]; then DETECTED_PLAYER_LABEL="${GREEN}${DETECTED_PLAYER_NAME}${NC}"; return 0; fi; DETECTED_PLAYER_LABEL="${RED}No Player Detected${NC}"; return 1
}
manage_tracklists() {
local doc_script="" s viewer_sh=""; for s in "$SCRIPT_DIR/generate_tracklist_docs.py" "$SCRIPT_DIR/scripts/generate_tracklist_docs.py" "./generate_tracklist_docs.py"; do [ -f "$s" ] && { doc_script="$s"; break; }; done; for s in "$SCRIPT_DIR/scripts/view_tracklist_console.sh" "$SCRIPT_DIR/view_tracklist_console.sh" "./scripts/view_tracklist_console.sh"; do [ -f "$s" ] && { viewer_sh="$s"; break; }; done
_view_single_tracklist() {
local tf="$1" af="${2:-}"; [ -z "$tf" ] || [ ! -f "$tf" ] && return 1; [ -n "${CURRENT_THEME:-}" ] && export CURRENT_THEME MP_TRACKLIST_THEME="$CURRENT_THEME"; if [ -n "$viewer_sh" ]; then bash "$viewer_sh" "$tf" ${af:+"$af"}; elif command -v bat &>/dev/null; then bat --paging=always "$tf"; elif command -v less &>/dev/null; then less -R "$tf"; else echo -e "\n${BOLD}${CYAN}=== TRACKLIST: ${tf##*/} ===${NC}\n"; cat "$tf"; press_enter; fi
}
_collect_all_archive_tracklists() {
local -a s_dirs=("$OUTPUT_DIR" "$PWD" "${MIX_ARCHIVE_DIR:-}") f_dir a_dir; if command -v get_all_flac_output_dirs &>/dev/null; then while IFS= read -r f_dir; do [ -n "$f_dir" ] && s_dirs+=("$f_dir"); done < <(get_all_flac_output_dirs); fi; if command -v get_all_mix_archive_dirs &>/dev/null; then while IFS= read -r a_dir; do [ -n "$a_dir" ] && s_dirs+=("$a_dir"); done < <(get_all_mix_archive_dirs); fi; local -A seen=(); ALL_TRACKLIST_FILES=(); shopt -s nullglob nocaseglob; local sd f bn; for sd in "${s_dirs[@]}"; do [ -z "$sd" ] || [ ! -d "$sd" ] && continue; for f in "$sd"/*.txt; do [ -f "$f" ] || continue; bn="${f##*/}"; case "${bn,,}" in requirements.txt|checksums*|*.sha256.txt|*log*.txt|todo*.txt) continue ;; esac; if [ -z "${seen[$f]}" ]; then seen["$f"]=1; ALL_TRACKLIST_FILES+=("$f"); fi; done; done; shopt -u nullglob nocaseglob
}
local tl_opts=("1|Browse & View Tracklists|(Select from Archive List)" "2|Search Tracklist by Title, Episode or Keyword|(Quick Search)" "3|View Tracklist of Currently Playing Track|(Live Player Tracklist)" "4|Export Tracklist to Styled HTML Document|(generate_tracklist_docs.py)" "5|Export Tracklist to Printable PDF Document|(generate_tracklist_docs.py)" "6|Batch Export All Archive Tracklists to HTML & PDF|(Full Archive)" "7|Scan & Generate Missing Tracklists|(Check_Find_Tracklists.sh)" "8|Generate Master Tracklist HTML Index|(Generate_Master_Tracklist.sh)" "0|Return to Main Menu|(or Esc / q / 9)"); while true; do detect_active_music_player; local p_label="${DETECTED_PLAYER_NAME:-None Detected}"; [ -n "$DETECTED_PLAYER_NAME" ] && p_label="${GREEN}${DETECTED_PLAYER_NAME}${NC}" || p_label="${RED}None Detected${NC}"; local tl_hdr="  Active Player: ${p_label}  ${BOLD}${BLUE}│${NC}  Archive Root: ${BOLD}${CYAN}${MIX_ARCHIVE_DIR:-$PWD}${NC}\n"; run_interactive_submenu "TRACKLIST & METADATA MANAGEMENT" "$tl_hdr" tl_opts 0; case "$REPLY" in 1) _collect_all_archive_tracklists; if [ ${#ALL_TRACKLIST_FILES[@]} -eq 0 ]; then echo -e "\n${YELLOW}No tracklist .txt files found in archive directories.${NC}"; press_enter; continue; fi; echo -e "\n${BOLD}${CYAN}Available Tracklists (${#ALL_TRACKLIST_FILES[@]} found):${NC}\n"; local idx=1 display_files=() tf bname; for tf in "${ALL_TRACKLIST_FILES[@]}"; do bname="${tf##*/}"; printf "  %2d) %s\n" "$idx" "$bname"; display_files+=("$tf"); ((idx++)); if [ "$idx" -gt 40 ]; then echo -e "  ${DIM}...and $(( ${#ALL_TRACKLIST_FILES[@]} - 40 )) more (use search option 2 for specific mix)${NC}"; break; fi; done; echo ""; read -r -p "Enter number to view [1-${#display_files[@]}, or q to cancel]: " sel_idx; if [[ "$sel_idx" =~ ^[0-9]+$ ]] && [ "$sel_idx" -ge 1 ] && [ "$sel_idx" -le "${#display_files[@]}" ]; then local chosen_file="${display_files[$((sel_idx - 1))]}"; _view_single_tracklist "$chosen_file"; fi ;; 2) read -r -p "Enter search keyword (e.g. 033, Escape, Episode): " query; if [ -n "$query" ]; then _collect_all_archive_tracklists; local matches=() f bn q_lower="${query,,}"; for f in "${ALL_TRACKLIST_FILES[@]}"; do bn="${f##*/}"; if [[ "${bn,,}" == *"$q_lower"* ]]; then matches+=("$f"); fi; done; if [ ${#matches[@]} -eq 0 ]; then echo -e "\n${YELLOW}No tracklists matching '${query}' found.${NC}"; press_enter; else echo -e "\n${BOLD}${GREEN}Matches Found (${#matches[@]} files):${NC}\n"; local m_idx=1 m; for m in "${matches[@]}"; do printf "  %2d) %s  ${DIM}(%s)${NC}\n" "$m_idx" "${m##*/}" "$(dirname "$m")"; ((m_idx++)); if [ "$m_idx" -gt 40 ]; then echo -e "  ${DIM}...and $(( ${#matches[@]} - 40 )) more${NC}"; break; fi; done; echo ""; read -r -p "Select file to view [1-$((m_idx - 1)), or q to cancel]: " chosen; if [[ "$chosen" =~ ^[0-9]+$ ]] && [ "$chosen" -ge 1 ] && [ "$chosen" -lt "$m_idx" ]; then local chosen_file="${matches[$((chosen - 1))]}"; _view_single_tracklist "$chosen_file"; fi; fi; fi ;; 3) detect_active_music_player; local cur_p="${DETECTED_PLAYER_NAME:-}" cur_path="${DETECTED_TRACK_PATH:-}" cur_title="${DETECTED_TRACK_TITLE:-}"; if [ -z "$cur_p" ]; then echo -e "\n${RED}No music player is currently running.${NC}"; press_enter; continue; fi; if [ -z "$cur_path" ] || [ ! -f "$cur_path" ]; then local fb; fb=$(detect_currently_playing_mix 2>/dev/null || true); [ -n "$fb" ] && [ -f "$fb" ] && cur_path="$fb"; fi; if [ -z "$cur_path" ] && [ -z "$cur_title" ]; then echo -e "\n${YELLOW}${cur_p} is running, but no track is loaded or playing.${NC}"; press_enter; continue; fi; local found_tl=""; [ -n "$cur_path" ] && [ -f "$cur_path" ] && found_tl=$(find_mix_tracklist "$cur_path" 2>/dev/null || true); [ -z "$found_tl" ] && [ -n "$cur_title" ] && found_tl=$(find_mix_tracklist "$cur_title" 2>/dev/null || true); if [ -z "$found_tl" ]; then local st="${cur_title:-${cur_path##*/}}" ep=""; st="${st%.*}"; if [[ "$st" =~ [_\ -]([0-9]{2,3})([_\ -]|$) ]] || [[ "$st" =~ ([0-9]{2,3}) ]]; then ep="${BASH_REMATCH[1]}"; fi; _collect_all_archive_tracklists; local tm bn; if [ -n "$ep" ]; then for tm in "${ALL_TRACKLIST_FILES[@]}"; do bn="${tm##*/}"; if [[ "$bn" =~ [_\ -]0*${ep#0}([_\ -]|$) ]]; then found_tl="$tm"; break; fi; done; fi; if [ -z "$found_tl" ]; then for tm in "${ALL_TRACKLIST_FILES[@]}"; do bn="${tm##*/}"; if [[ "${bn,,}" == *"${st,,}"* ]]; then found_tl="$tm"; break; fi; done; fi; fi; if [ -n "$found_tl" ] && [ -f "$found_tl" ]; then _view_single_tracklist "$found_tl" "$cur_path"; else echo -e "\n${YELLOW}No tracklist found for current track '${cur_title:-${cur_path##*/}}' playing in ${cur_p}.${NC}"; press_enter; fi ;; 4|5) local fmt="html"; [ "$REPLY" = "5" ] && fmt="pdf"; if [ -z "$doc_script" ]; then echo -e "\n${RED}Error: generate_tracklist_docs.py not found!${NC}"; press_enter; continue; fi; echo -e "\n${BOLD}${CYAN}=== EXPORT TRACKLIST TO ${fmt^^} ===${NC}\n"; local def_tl=""; if [ -n "$DETECTED_TRACK_PATH" ] && [ -f "$DETECTED_TRACK_PATH" ]; then def_tl=$(find_mix_tracklist "$DETECTED_TRACK_PATH" 2>/dev/null || true); fi; if [ -z "$def_tl" ]; then _collect_all_archive_tracklists; [ ${#ALL_TRACKLIST_FILES[@]} -gt 0 ] && def_tl="${ALL_TRACKLIST_FILES[0]}"; fi; read -r -p "Enter path to tracklist .txt file [Default: ${def_tl:-none}]: " inp_tl; inp_tl="${inp_tl:-$def_tl}"; inp_tl="${inp_tl#[\'\"]}"; inp_tl="${inp_tl%[\'\"]}"; _norm_path "$inp_tl"; inp_tl="$REPLY"; if [ -n "$inp_tl" ] && [ -f "$inp_tl" ]; then echo -e "\n${GREEN}Generating ${fmt^^} document for: ${inp_tl##*/}${NC}\n"; python3 "$doc_script" -i "$inp_tl" -f "$fmt"; else echo -e "\n${RED}Error: Tracklist file not found: ${inp_tl}${NC}"; fi; press_enter ;; 6) if [ -n "$doc_script" ]; then local all_dirs=() f_dir; while IFS= read -r f_dir; do [ -n "$f_dir" ] && [ -d "$f_dir" ] && all_dirs+=("$f_dir"); done < <(get_all_flac_output_dirs); [ ${#all_dirs[@]} -eq 0 ] && [ -d "$OUTPUT_DIR" ] && all_dirs+=("$OUTPUT_DIR"); [ ${#all_dirs[@]} -eq 0 ] && all_dirs+=("$PWD"); echo -e "\n${BOLD}${YELLOW}Batch exporting all tracklists across ${#all_dirs[@]} archive(s) to HTML and PDF...${NC}\n"; python3 "$doc_script" -d "${all_dirs[@]}" -f both; else echo -e "\n${RED}Error: generate_tracklist_docs.py not found!${NC}"; fi; press_enter ;; 7) run_sub_script "Check_Find_Tracklists.sh"; press_enter ;; 8) [ -f "$SCRIPT_DIR/Generate_Master_Tracklist.sh" ] && bash "$SCRIPT_DIR/Generate_Master_Tracklist.sh" || run_sub_script "Generate_Master_Tracklist.sh"; press_enter ;; 0|9|[qQ]|[eE][xX][iI][tT]|ESC) return 0 ;; *) echo -e "\n${RED}Invalid option!${NC}"; sleep 1.2 ;; esac; done
}
manage_promo_outreach() {
local py_script="" s; for s in "$SCRIPT_DIR/send_promo_email.py" "$SCRIPT_DIR/scripts/send_promo_email.py" "./send_promo_email.py"; do [ -f "$s" ] && { py_script="$s"; break; }; done; [ -z "$py_script" ] && { echo -e "\n${RED}Error: send_promo_email.py not found!${NC}"; press_enter; return 1; }; while true; do clear; local c_cnt=0 c_file="$SCRIPT_DIR/assets/promo_contacts.json"; [ ! -f "$c_file" ] && [ -f "./assets/promo_contacts.json" ] && c_file="./assets/promo_contacts.json"; [ -f "$c_file" ] && c_cnt=$(grep -c '"email":' "$c_file" 2>/dev/null || echo 0); echo -e "${BOLD}${MAGENTA}${S70}\n             PROMOTIONAL & PUBLISHER OUTREACH SYSTEM                  \n         (Promoters, Podcast Publishers, Radio & Labels)              \n${S70}${NC}\n\n  Sender Name:          ${GREEN}${PROMO_SENDER_NAME:-MPlanetarian}${NC}\n  Sender Email:         ${CYAN}${PROMO_SENDER_EMAIL:-Not Set (Direct desktop mailto/preview)}${NC}\n  SMTP Outgoing Server: ${YELLOW}${SMTP_HOST:-None Configured (Mail client / Browser preview)}${NC}\n  Outreach Contacts:    ${GREEN}${c_cnt} contacts in address book${NC}\n\n${BOLD}Send Enquiries & Promotional Pitches:${NC}\n  ${BOLD}${CYAN} 1)${NC} ${GREEN}Interactive Outreach Wizard${NC} (Step-by-step custom email builder)\n  ${BOLD}${CYAN} 2)${NC} Pitch Episode to Podcast Publishers & Syndicators (${CYAN}Apple Podcasts, DI.FM, Proton...${NC})\n  ${BOLD}${CYAN} 3)${NC} Send Booking / Guest Mix Enquiry to Promoters & Venues (${CYAN}Clubs, Festivals...${NC})\n  ${BOLD}${CYAN} 4)${NC} Send New Episode Press & Promo Release Blast\n  ${BOLD}${CYAN} 5)${NC} Send Track Support Courtesy Notice to Labels & Producers\n  ${BOLD}${CYAN} 6)${NC} Submit Radio Guest Mix & Syndication Proposal\n\n${BOLD}Tools, Contacts & Preferences:${NC}\n  ${BOLD}${CYAN} 7)${NC} Preview HTML & Plaintext Email in Browser & Terminal\n  ${BOLD}${CYAN} 8)${NC} Browse & Search Outreach Contacts Book\n  ${BOLD}${CYAN} 9)${NC} Add New Contact (Promoter, Publisher, Label, Radio, Press)\n  ${BOLD}${CYAN}10)${NC} View Sent Email History & Delivery Logs\n  ${BOLD}${CYAN}11)${NC} Configure Sender Profile & SMTP Server Settings\n\n  ${BOLD}${CYAN}12)${NC} Return to Main Menu\n"; read -r -p "Enter choice [1-12]: " p_choice; case "$p_choice" in 1) python3 "$py_script" --interactive; press_enter ;; 2|3|4|5|6) local hdrs=("" "" "PITCH TO PODCAST PUBLISHERS & SYNDICATORS" "PROMOTER & VENUE BOOKING ENQUIRY" "NEW EPISODE PROMO RELEASE BLAST" "TRACK SUPPORT COURTESY NOTICE TO LABELS" "RADIO GUEST MIX & SYNDICATION PROPOSAL"); local prompts=("" "" "saved publishers" "saved promoters" "press/media contacts" "saved labels" "saved radio stations"); local cats=("" "" "publisher" "promoter" "press" "label" "radio"); local tpls=("" "" "podcast_publisher" "promoter_booking" "episode_promo" "track_support" "radio_guestmix"); echo -e "\n${BOLD}${CYAN}=== ${hdrs[$p_choice]} ===${NC}\n"; read -r -p "Enter episode number or keyword (or ENTER for latest): " ep_q; read -r -p "Enter recipient email (or ENTER to select from ${prompts[$p_choice]}): " to_em; local args=(--template "${tpls[$p_choice]}"); [ -n "$to_em" ] && args+=(--to "$to_em") || args+=(--category "${cats[$p_choice]}"); [ -n "$ep_q" ] && args+=(--episode "$ep_q"); python3 "$py_script" "${args[@]}" --interactive; press_enter ;; 7) echo -e "\n${BOLD}${CYAN}=== PREVIEW EMAIL IN WEB BROWSER ===${NC}\n"; python3 "$py_script" --list-templates; read -r -p "Enter template name [podcast_publisher]: " t_n; read -r -p "Enter episode number or keyword (or ENTER for latest): " ep_q
local p_args=(--template "${t_n:-podcast_publisher}" --preview); [ -n "$ep_q" ] && p_args+=(--episode "$ep_q"); python3 "$py_script" "${p_args[@]}"; press_enter ;; 8) python3 "$py_script" --list-contacts; press_enter ;; 9) python3 "$py_script" --add-contact; press_enter ;; 10) local l_file="$SCRIPT_DIR/assets/promo_logs/sent_promo_emails.log"; [ ! -f "$l_file" ] && [ -f "./assets/promo_logs/sent_promo_emails.log" ] && l_file="./assets/promo_logs/sent_promo_emails.log"; echo -e "\n${BOLD}${CYAN}=== OUTREACH & DELIVERY LOGS ===${NC}\n"; [ -s "$l_file" ] && tail -n 35 "$l_file" || echo -e "${DIM}No sent emails or drafts logged yet.${NC}"; echo ""; press_enter ;; 11) echo -e "\n${BOLD}${CYAN}=== CONFIGURE SENDER PROFILE & SMTP SERVER ===${NC}\n"; read -r -p "Sender Full Name [${PROMO_SENDER_NAME:-MPlanetarian}]: " n_name; read -r -p "Sender Email Address [${PROMO_SENDER_EMAIL}]: " n_email; read -r -p "SMTP Host (e.g. smtp.gmail.com) [${SMTP_HOST}]: " n_host; read -r -p "SMTP Port [${SMTP_PORT:-587}]: " n_port; read -r -p "SMTP Username / Login Email [${SMTP_USER}]: " n_user; read -r -s -p "SMTP Password / App Password (leave blank to keep existing): " n_pass; echo ""; local cfg="$SCRIPT_DIR/config.env" sed_args=(); [ ! -f "$cfg" ] && [ -f "./config.env" ] && cfg="./config.env"; [ -n "$n_name" ]  && { PROMO_SENDER_NAME="$n_name";  sed_args+=(-e "s|^PROMO_SENDER_NAME=.*|PROMO_SENDER_NAME=\"$n_name\"|"); }; [ -n "$n_email" ] && { PROMO_SENDER_EMAIL="$n_email"; sed_args+=(-e "s|^PROMO_SENDER_EMAIL=.*|PROMO_SENDER_EMAIL=\"$n_email\"|"); }; [ -n "$n_host" ]  && { SMTP_HOST="$n_host";          sed_args+=(-e "s|^SMTP_HOST=.*|SMTP_HOST=\"$n_host\"|"); }; [ -n "$n_port" ]  && { SMTP_PORT="$n_port";          sed_args+=(-e "s|^SMTP_PORT=.*|SMTP_PORT=\"$n_port\"|"); }; [ -n "$n_user" ]  && { SMTP_USER="$n_user";          sed_args+=(-e "s|^SMTP_USER=.*|SMTP_USER=\"$n_user\"|"); }; [ -n "$n_pass" ]  && { SMTP_PASSWORD="$n_pass";      sed_args+=(-e "s|^SMTP_PASSWORD=.*|SMTP_PASSWORD=\"$n_pass\"|"); }; [ ${#sed_args[@]} -gt 0 ] && sed -i "${sed_args[@]}" "$cfg" 2>/dev/null || true; echo -e "\n${GREEN}✔ Outreach settings updated in ${cfg}!${NC}"; press_enter ;; 12|[qQ]) return 0 ;; *) echo -e "\n${RED}Invalid option!${NC}"; sleep 1.2 ;; esac; done
}
_find_scr() {
for s in "$SCRIPT_DIR/$1" "$SCRIPT_DIR/scripts/$1" "./$1"; do [[ -f "$s" ]] && { REPLY="$s"; return 0; }; done; echo -e "\n${RED}Error: $1 not found!${NC}"; press_enter; return 1
}
search_and_play_mix() {
clear; echo -e "${BOLD}${MAGENTA}${S70}\n            SEARCH FOR MIX & AUTO-PLAY WITH LIVE TRACKLIST            \n${S70}${NC}\n"; read -r -p "Enter mix search query (Episode #, Title, Date, Artist): " query; [[ -z "$query" ]] && { echo -e "\n${YELLOW}Search cancelled.${NC}"; sleep 1; return 0; }; echo -e "\n${CYAN}Searching archive for '${query}'...${NC}"; local raw_dirs=("$OUTPUT_DIR" "$PWD" "${OUTPUT_DIR%/*}/CONVERTED_WAV_FILES" "${MIX_ARCHIVE_DIR:-$SCRIPT_DIR/MIX_ARCHIVE}" "${MIX_ARCHIVE_DIR:-$SCRIPT_DIR/MIX_ARCHIVE}/FLAC_CONVERTED_OUTPUTS" "${ICLOUD_PATH:-}" "${DROPBOX_PATH:-}"); local d valid_dirs=() flac_matches=() wav_matches=() other_matches=() matches=(); local -A seen_dirs=() seen_real=(); while IFS= read -r d; do [[ -n "$d" && -d "$d" && -z "${seen_dirs[$d]}" ]] && { valid_dirs+=("$d"); seen_dirs["$d"]=1; }; done < <(printf "%s\n" "${raw_dirs[@]}"; get_all_flac_output_dirs; get_all_wav_archive_dirs; get_all_mix_archive_dirs); if ((${#valid_dirs[@]})); then while IFS= read -r -d '' file; do local rp; rp="$(realpath "$file" 2>/dev/null || echo "$file")"; if [[ -z "${seen_real[$rp]}" ]]; then seen_real["$rp"]=1; case "${file,,}" in *.flac) flac_matches+=("$file") ;; *.wav) wav_matches+=("$file") ;; *) other_matches+=("$file") ;; esac; fi; done < <(find "${valid_dirs[@]}" -maxdepth 3 -type f \( -iname "*$query*.flac" -o -iname "*$query*.wav" -o -iname "*$query*.mp3" \) -print0 2>/dev/null); fi; matches=("${flac_matches[@]}" "${wav_matches[@]}" "${other_matches[@]}"); ((${#matches[@]} == 0)) && { echo -e "\n${YELLOW}No audio mixes matching '${query}' were found.${NC}"; press_enter; return 0; }; local selected_mix="${matches[0]}"; if ((${#matches[@]} == 1)); then local ext="${selected_mix##*.}"; echo -e "\n${GREEN}Found 1 matching mix:${NC} [${ext^^}] ${selected_mix##*/}"; else echo -e "\n${BOLD}${CYAN}Multiple matches found (${#matches[@]} files):${NC}"; for i in "${!matches[@]}"; do local m_ext="${matches[$i]##*.}"; printf "  %2d) %-7s %s\n" "$((i + 1))" "[${m_ext^^}]" "${matches[$i]##*/}"; done; read -r -p $'\n'"Select mix to play [1-${#matches[@]}, or q to cancel]: " sel_idx; if [[ "$sel_idx" =~ ^[0-9]+$ ]] && ((sel_idx >= 1 && sel_idx <= ${#matches[@]})); then selected_mix="${matches[$((sel_idx - 1))]}"; else echo -e "\n${YELLOW}Selection cancelled.${NC}"; sleep 1; return 0; fi; fi; selected_mix="$(realpath "$selected_mix" 2>/dev/null || echo "$selected_mix")"; local bname="${selected_mix##*/}" py_player="$SCRIPT_DIR/MP_Audio_Player.py"; [ ! -f "$py_player" ] && py_player="$SCRIPT_DIR/scripts/MP_Audio_Player.py"; echo -e "\n${BOLD}${YELLOW}Preparing playback for:${NC} $bname"; echo -e "${CYAN}Launching playback in MP Audio Player...${NC}"; python3 "$py_player" --play "$selected_mix" 2>/dev/null || true; echo -e "${CYAN}Verifying playback status in MP Audio Player...${NC}"; local attempt started=0; for ((attempt=1; attempt<=10; attempt++)); do sleep 0.4; if get_mp_audio_player_track_info 2>/dev/null && { [[ "$MP_PLAYER_STATE" = "playing" ]] || ((MP_PLAYER_RUNNING == 1)); }; then started=1; break; fi; done; if ((started)) || pgrep -f "MP_Audio_Player.*--daemon" &>/dev/null; then echo -e "${BOLD}${GREEN}✓ Playback active in MP Audio Player!${NC}\n${CYAN}Loading tracklist...${NC}\n"; local bname_no_ext="${bname%.*}" found_tl; found_tl=$(find_mix_tracklist "$selected_mix" 2>/dev/null || true); if [[ ! -f "$found_tl" ]]; then shopt -s nullglob nocaseglob; for tc in "$OUTPUT_DIR/$bname_no_ext.txt" "${selected_mix%.*}.txt" "${selected_mix%/*}/$bname_no_ext.txt" "$PWD/$bname_no_ext.txt" "$OUTPUT_DIR/"*"$query"*".txt" "$PWD/"*"$query"*".txt"; do [[ -f "$tc" ]] && { found_tl="$tc"; break; }; done; shopt -u nullglob nocaseglob; fi; if [[ -f "$found_tl" ]]; then echo -e "${BOLD}${MAGENTA}${S70}\n           CURRENTLY PLAYING TRACKLIST: ${found_tl##*/}\n${S70}${NC}\n"; cat "$found_tl"; echo -e "\n${BOLD}${BLUE}──────────────────────────────────────────────────────────────────────${NC}\n${DIM}Playback active in MP Audio Player. Press [Enter] to return...${NC}"; read -r; else echo -e "\n${YELLOW}Track playing in MP Audio Player, no matching .txt found for '${bname_no_ext}'.${NC}"; press_enter; fi; else echo -e "\n${YELLOW}⚠️ MP Audio Player did not start. Skipping tracklist.${NC}"; sleep 1.8; fi
}
extract_tracklist_from_traktor_history() {
clear; echo -e "${BOLD}${MAGENTA}${S70}\n      EXTRACT TRACKLIST FROM TRAKTOR HISTORY FILES BY RANGE           \n${S70}${NC}\n"; echo -e "${BOLD}${CYAN}Step 1: Select an Existing Mix from Archive${NC}\n"; read -r -p "Enter mix search query (Episode #, Title, Artist, or ENTER to browse): " m_query; local raw_dirs=("$OUTPUT_DIR" "$PWD" "${OUTPUT_DIR%/*}/CONVERTED_WAV_FILES" "${MIX_ARCHIVE_DIR:-$SCRIPT_DIR/MIX_ARCHIVE}" "${MIX_ARCHIVE_DIR:-$SCRIPT_DIR/MIX_ARCHIVE}/FLAC_CONVERTED_OUTPUTS" "${ICLOUD_PATH:-}" "${DROPBOX_PATH:-}"); local d valid_dirs=() flac_m=() wav_m=(); local -A seen_dirs=() seen_real=(); while IFS= read -r d; do [[ -n "$d" && -d "$d" && -z "${seen_dirs[$d]}" ]] && { valid_dirs+=("$d"); seen_dirs["$d"]=1; }; done < <(printf "%s\n" "${raw_dirs[@]}"; get_all_flac_output_dirs; get_all_wav_archive_dirs; get_all_mix_archive_dirs); if ((${#valid_dirs[@]})); then local pattern="*.flac"; [ -n "$m_query" ] && pattern="*$m_query*.flac"; while IFS= read -r -d '' file; do local rp; rp="$(realpath "$file" 2>/dev/null || echo "$file")"; [[ -z "${seen_real[$rp]}" ]] && { flac_m+=("$file"); seen_real["$rp"]=1; }; done < <(find "${valid_dirs[@]}" -maxdepth 3 -type f -iname "$pattern" -print0 2>/dev/null); pattern="*.wav"; [ -n "$m_query" ] && pattern="*$m_query*.wav"; while IFS= read -r -d '' file; do local rp; rp="$(realpath "$file" 2>/dev/null || echo "$file")"; [[ -z "${seen_real[$rp]}" ]] && { wav_m+=("$file"); seen_real["$rp"]=1; }; done < <(find "${valid_dirs[@]}" -maxdepth 3 -type f -iname "$pattern" -print0 2>/dev/null); fi; local candidate_mixes=("${flac_m[@]}" "${wav_m[@]}"); if ((${#candidate_mixes[@]} == 0)); then echo -e "\n${YELLOW}No audio mixes matching '${m_query}' were found.${NC}"; press_enter; return 0; fi; local selected_mix=""; if ((${#candidate_mixes[@]} == 1)); then selected_mix="${candidate_mixes[0]}"; local ext="${selected_mix##*.}"; echo -e "${GREEN}Found 1 matching mix:${NC} [${ext^^}] ${selected_mix##*/}\n"; else echo -e "${BOLD}${CYAN}Available Mixes (${#candidate_mixes[@]} found, showing top 25):${NC}"; local max_show=25; ((${#candidate_mixes[@]} < max_show)) && max_show=${#candidate_mixes[@]}; for ((i=0; i<max_show; i++)); do local m="${candidate_mixes[$i]}" ext="${candidate_mixes[$i]##*.}"; printf "  %2d) %-7s %s\n" "$((i + 1))" "[${ext^^}]" "${m##*/}"; done; read -r -p $'\n'"Select mix [1-$max_show, or q to cancel]: " sel_idx; if [[ "$sel_idx" =~ ^[0-9]+$ ]] && ((sel_idx >= 1 && sel_idx <= max_show)); then selected_mix="${candidate_mixes[$((sel_idx - 1))]}"; else echo -e "\n${YELLOW}Mix selection cancelled.${NC}"; sleep 1; return 0; fi; fi; local target_tl="${selected_mix%.*}.txt" mix_base="${selected_mix##*/}" mix_stem="${mix_base%.*}"; echo -e "${BOLD}Target Mix:${NC}       ${CYAN}${mix_base}${NC}"; if [ -f "$target_tl" ]; then echo -e "${BOLD}Target Tracklist:${NC} ${YELLOW}${target_tl}${NC} ${RED}(Existing tracklist will be permanently overwritten!)${NC}\n"; else echo -e "${BOLD}Target Tracklist:${NC} ${GREEN}${target_tl}${NC} (New tracklist will be created)\n"; fi; echo -e "${BOLD}${CYAN}Step 2: Select Traktor History File (.nml)${NC}\n"; local py_extract="$SCRIPT_DIR/scripts/extract_traktor_history_range.py"; [ ! -f "$py_extract" ] && py_extract="$SCRIPT_DIR/extract_traktor_history_range.py"; if [ ! -f "$py_extract" ]; then echo -e "${RED}Error: extract_traktor_history_range.py not found!${NC}"; press_enter; return 1; fi; python3 "$py_extract" --list-history; read -r -p "Select History file [1-30] or enter full history filename (or q to cancel): " h_choice; [[ "$h_choice" =~ ^[qQ]$ || -z "$h_choice" ]] && { echo -e "\n${YELLOW}Operation cancelled.${NC}"; sleep 1; return 0; }; local chosen_history=""; if [[ "$h_choice" =~ ^[0-9]+$ ]]; then local raw_json; raw_json=$(python3 "$py_extract" --list-history --json 2>/dev/null || true); chosen_history=$(python3 -c "import json, sys; data = json.loads(sys.argv[1]); idx = int(sys.argv[2]) - 1; print(data[idx]['path'] if 0 <= idx < len(data) else '')" "$raw_json" "$h_choice" 2>/dev/null || true); if [ -z "$chosen_history" ] || [ ! -f "$chosen_history" ]; then echo -e "\n${RED}Invalid selection number: $h_choice${NC}"; press_enter; return 1; fi; else local hist_input="${h_choice#[\'\"]}"; hist_input="${hist_input%[\'\"]}"; hist_input="${hist_input##*/}"; if [[ ! "$hist_input" =~ ^history_[0-9]{4}y[0-9]{2}m[0-9]{2}d_[0-9]{2}h[0-9]{2}m[0-9]{2}s(\.nml)?$ ]] && [[ ! "$hist_input" =~ \.nml$ ]]; then echo -e "\n${BOLD}${RED}❌ Rejection: You must enter the exact, full history file name!${NC}"; echo -e "${YELLOW}Example: history_2026y07m20d_08h01m28s.nml${NC}\n"; press_enter; return 1; fi; chosen_history="$hist_input"; fi; local total_tracks; total_tracks=$(python3 "$py_extract" --count "$chosen_history" 2>/dev/null || echo "0"); if [ "$total_tracks" -le 0 ] 2>/dev/null; then echo -e "\n${BOLD}${RED}❌ Error: Unable to read history file or history file is empty.${NC}"; press_enter; return 1; fi; echo -e "\n${GREEN}✔ History File:${NC} ${chosen_history##*/}  ${DIM}(Contains ${total_tracks} session tracks)${NC}\n"; echo -e "${BOLD}${CYAN}Step 3: Enter Track Range${NC}"; echo -e "${DIM}Specify the 1-indexed track numbers from session (e.g. '95 to 118' or '95-118')${NC}\n"; read -r -p "Enter track range: " range_input; local start_tr="" end_tr=""; if [[ "$range_input" =~ ^[[:space:]]*([0-9]+)[[:space:]]*(to|-)[[:space:]]*([0-9]+)[[:space:]]*$ ]] || [[ "$range_input" =~ ^[[:space:]]*([0-9]+)[[:space:]]+([0-9]+)[[:space:]]*$ ]]; then start_tr="${BASH_REMATCH[1]}"; end_tr="${BASH_REMATCH[3]:-${BASH_REMATCH[2]}}"; else echo -e "\n${BOLD}${RED}❌ Invalid range format: '${range_input}'!${NC}"; echo -e "${YELLOW}Expected format: e.g. 95 to 118 or 95-118${NC}\n"; press_enter; return 1; fi; echo -e "\n${CYAN}Extracting tracks ${start_tr} to ${end_tr} and saving to:${NC} ${target_tl}..."; if ! python3 "$py_extract" --history "$chosen_history" --start "$start_tr" --end "$end_tr" --output "$target_tl" --mix-file "$selected_mix" --mix-title "$mix_stem"; then echo -e "\n${BOLD}${RED}❌ Extraction failed.${NC}"; press_enter; return 1; fi; echo -e "\n${BOLD}${MAGENTA}${S70}\n               EXTRACTED TRACKLIST PREVIEW                            \n${S70}${NC}\n"; cat "$target_tl"; echo -e "\n${BOLD}${BLUE}──────────────────────────────────────────────────────────────────────${NC}"; local edit_choice=""; read -r -p "Would you like to open and edit the extracted tracklist now? [Y/n]: " edit_choice; edit_choice="${edit_choice:-Y}"; if [[ "$edit_choice" =~ ^[yY] ]]; then local ed="${EDITOR:-}"; [ -z "$ed" ] && command -v nano &>/dev/null && ed="nano"; [ -z "$ed" ] && command -v vi &>/dev/null && ed="vi"; if [ -n "$ed" ]; then "$ed" "$target_tl"; elif [ -f "$SCRIPT_DIR/scripts/view_tracklist_console.sh" ]; then bash "$SCRIPT_DIR/scripts/view_tracklist_console.sh" "$target_tl"; else echo -e "${YELLOW}Tracklist saved at: ${target_tl}${NC}"; press_enter; fi; fi
}
manage_cover_converter() {
local script; _find_scr "convert_cover_art.py" || return 1; script="$REPLY"; while true; do clear
echo -e "${BOLD}${MAGENTA}======================================================================\n                   COVER ART CONVERTER & OPTIMIZER                    \n======================================================================${NC}
  1) Optimize to 1MB Podcast (JPG)   5) Batch Convert COVERS/
  2) Convert to WebP (q90)           6) Custom CLI Arguments
  3) Resize Cover Art                7) Return to Main Menu
  4) Custom Byte Target\n"
read -r -p "Enter choice [1-7]: " c; case "$c" in 1|2|3|4) read -r -p "Cover path [default: ./Cover.png]: " img; img="${img:-./Cover.png}"; if [[ ! -f "$img" ]]; then echo -e "\n${RED}Not found: $img${NC}"; press_enter; continue; fi; case "$c" in 1) python3 "$script" -i "$img" --bytes 1MB -f jpg ;; 2) python3 "$script" -i "$img" -f webp -q 90 ;; 3) read -r -p "Preset: 1) 3000x3000 2) 1400x1400 3) 1080x1080 4) 500x500: " r; local res=("1400x1400" "3000x3000" "1400x1400" "1080x1080" "500x500"); python3 "$script" -i "$img" -r "${res[${r:-2}]:-1400x1400}" ;; 4) read -r -p "Target max size [default: 1MB]: " sz; python3 "$script" -i "$img" --bytes "${sz:-1MB}" ;; esac ;; 5) local d="$PWD/COVERS"; [[ ! -d "$d" ]] && d="${MIX_ARCHIVE_DIR:-$SCRIPT_DIR/MIX_ARCHIVE}/COVERS"; [[ -d "$d" ]] && python3 "$script" -d "$d" --bytes 1MB -f jpg || echo -e "\n${YELLOW}COVERS/ not found.${NC}" ;; 6) python3 "$script" -h; read -r -p $'\n'"Custom args: " args; [[ -n "$args" ]] && python3 "$script" $args ;; 7|[qQ]) return 0 ;; *) echo -e "\n${RED}Invalid option!${NC}"; sleep 1; continue ;; esac; press_enter; done
}
find_duplicate_audio_mixes() {
local script; _find_scr "find_duplicate_mixes.py" || return 1; script="$REPLY"; local d scan_dirs=(); while IFS= read -r d; do [[ -n "$d" && -d "$d" ]] && scan_dirs+=("$d"); done < <(get_all_flac_output_dirs; get_all_wav_archive_dirs; printf "%s\n" "$PWD"); while true; do clear; echo -e "${BOLD}${MAGENTA}${S70}\n             DUPLICATE AUDIO FILE DETECTOR & CLEANER                  \n${S70}${NC}\n  Scanning:"; printf "    ${CYAN}%s${NC}\n" "${scan_dirs[@]}"; echo -e "\n  1) Scan & Report (Safe)   3) Delete Duplicates   5) Return\n  2) Quarantine Duplicates  4) Custom Directory Scan\n"; read -r -p "Enter choice [1-5]: " c; case "$c" in 1) python3 "$script" -d "${scan_dirs[@]}" --action report ;; 2) python3 "$script" -d "${scan_dirs[@]}" --action quarantine ;; 3) read -r -p $'\n'"${BOLD}${RED}⚠️ Permanently delete duplicates? [y/N]: ${NC}" yn; [[ "$yn" =~ ^[yY] ]] && python3 "$script" -d "${scan_dirs[@]}" --action delete || echo -e "\n${GREEN}Cancelled.${NC}" ;; 4) read -r -p "Directory to scan: " cd; [[ -d "$cd" ]] && python3 "$script" -d "$cd" --action report || echo -e "\n${RED}Not found: $cd${NC}" ;; 5|[qQ]) return 0 ;; *) echo -e "\n${RED}Invalid option!${NC}"; sleep 1; continue ;; esac; press_enter; done
}
export_mixes_to_path() {
clear; echo -e "${BOLD}${MAGENTA}${S70}\n                 EXPORT & COPY MIXES TO DESTINATION                   \n${S70}${NC}\n  ${BOLD}${CYAN}0)${NC} ${BOLD}${GREEN}Launch MP Mix Archive Cloner (Clone Entire Mix Archive Folders to Full Path)${NC}\n"; read -r -p "Enter destination path (or '0' to launch MP Mix Archive Cloner): " dest_dir; if [[ "$dest_dir" == "0" || "$dest_dir" =~ ^[cC][lL][oO][nN][eE] ]]; then run_sub_script "MP_Mix_Archive_Cloner.sh"; press_enter; return 0; fi; [[ -z "$dest_dir" ]] && { echo -e "\n${YELLOW}Cancelled.${NC}"; sleep 1; return 0; }; dest_dir="${dest_dir/#\~/$HOME}"; dest_dir="${dest_dir//\\//}"; [[ ! "$dest_dir" =~ ^[a-zA-Z]:/$ && "$dest_dir" != "/" ]] && dest_dir="${dest_dir%/}"; if [[ ! -d "$dest_dir" ]]; then read -r -p "Create directory '${dest_dir}'? [Y/n]: " yn; [[ "$yn" =~ ^[nN] ]] && return 0; mkdir -p "$dest_dir" || { echo -e "${RED}Failed!${NC}"; press_enter; return 1; }; fi; local d all_flac_dirs=(); while IFS= read -r d; do [[ -n "$d" && -d "$d" ]] && all_flac_dirs+=("$d"); done < <(get_all_flac_output_dirs); echo -e "\n  1) Complete Package  3) Tracklists/Docs Only  5) Search Keyword\n  2) Audio Files Only  4) Covers & Spek Only    6) Clone Entire Archive Folder (MP_Mix_Archive_Cloner)  7) Cancel\n"; read -r -p "Enter choice [1-7]: " c; shopt -s nullglob; case "$c" in 1) for d in "${all_flac_dirs[@]}"; do rsync -avh --progress "$d"/*.{flac,txt,html,pdf} "$dest_dir/" 2>/dev/null; done; [[ -d "$PWD/COVERS" ]] && rsync -avh "$PWD/COVERS/" "$dest_dir/COVERS/" 2>/dev/null; [[ -d "$PWD/SPEK_OUTPUTS" ]] && rsync -avh "$PWD/SPEK_OUTPUTS/" "$dest_dir/SPEK_OUTPUTS/" 2>/dev/null ;; 2) for d in "${all_flac_dirs[@]}" "$PWD"; do rsync -avh --progress "$d"/*.{flac,wav,mp3} "$dest_dir/" 2>/dev/null; done ;; 3) for d in "${all_flac_dirs[@]}" "$PWD"; do rsync -avh "$d"/*.{txt,html,pdf} "$dest_dir/" 2>/dev/null; done ;; 4) [[ -d "$PWD/COVERS" ]] && rsync -avh "$PWD/COVERS/" "$dest_dir/COVERS/" 2>/dev/null; [[ -d "$PWD/SPEK_OUTPUTS" ]] && rsync -avh "$PWD/SPEK_OUTPUTS/" "$dest_dir/SPEK_OUTPUTS/" 2>/dev/null; [[ -f "$PWD/Cover.png" ]] && cp -v "$PWD/Cover.png" "$dest_dir/" 2>/dev/null ;; 5) read -r -p "Search term: " kw; [[ -n "$kw" ]] && find "${all_flac_dirs[@]}" "$PWD" -maxdepth 2 -type f -iname "*${kw}*" -exec cp -v -t "$dest_dir/" {} + 2>/dev/null ;; 6) shopt -u nullglob; run_sub_script "MP_Mix_Archive_Cloner.sh" --all --dest "$dest_dir"; press_enter; return 0 ;; *) shopt -u nullglob; return 0 ;; esac; shopt -u nullglob; echo -e "\n${BOLD}${GREEN}✓ Export finished.${NC}"; press_enter
}
manage_audio_checksums() {
local script; _find_scr "manage_checksums.sh" || return 1; script="$REPLY"; while true; do clear
echo -e "${BOLD}${MAGENTA}======================================================================\n             AUDIO FILE CHECKSUM CREATION & VERIFICATION              \n======================================================================${NC}
  1) Generate SHA-256 (FLAC_CONVERTED_OUTPUTS)  4) View Manifest
  2) Generate SHA-256 ($PWD)  5) View Logs
  3) Verify Archive Checksums                   6) Return\n"
read -r -p "Enter choice [1-6]: " c; case "$c" in 1) bash "$script" -g -d "$OUTPUT_DIR" ;; 2) bash "$script" -g -d "$PWD" ;; 3) bash "$script" -v ;; 4) local mf="$PWD/checksums.sha256"; [[ ! -f "$mf" ]] && mf="$OUTPUT_DIR/checksums.sha256"; [[ -f "$mf" ]] && head -n 40 "$mf" || echo -e "\n${YELLOW}No manifest found.${NC}" ;; 5) [[ -d "$PWD/VERIFY_LOGS" ]] && ls -lh "$PWD/VERIFY_LOGS" || echo -e "\n${YELLOW}No logs found.${NC}" ;; 6|[qQ]) return 0 ;; *) echo -e "\n${RED}Invalid!${NC}"; sleep 1; continue ;; esac; press_enter; done
}
manage_mix_search_and_import() {
clear 2>/dev/null || true
echo -e "${BOLD}${MAGENTA}======================================================================\n       Search & Import Mixes from Local Storage & Network SMB         \n======================================================================${NC}
  1) Universal Search & Import Wizard
  2) Dedicated Traktor & SOF SMB Share Ingest
  0) Return to Main Menu\n"
read -r -p "Select mode [1-2, 0]: " m; case "$m" in 1) run_sub_script "search_and_import_mixes.sh"; press_enter ;; 2) run_sub_script "import_new_mixes.sh"; press_enter ;; esac
}
manage_installation_and_config() { run_sub_script "manage_installation_config.sh"; }
reboot_system() {
read -r -p $'\n'"${BOLD}${RED}⚠️ Confirm system reboot? [y/N]: ${NC}" yn; [[ ! "$yn" =~ ^[yY] ]] && { echo -e "\n${GREEN}Cancelled.${NC}"; sleep 1; return 0; }; echo -e "\n${BOLD}${RED}Rebooting...${NC}"; case "$OS_TYPE" in macos) osascript -e 'tell app "System Events" to restart' 2>/dev/null || sudo shutdown -r now ;; windows) shutdown.exe /r /t 0 2>/dev/null || shutdown /r /t 0 ;; wsl) cmd.exe /c shutdown /r /t 0 2>/dev/null || wsl.exe --shutdown ;; *) sudo systemctl reboot 2>/dev/null || sudo reboot || sudo shutdown -r now || reboot ;; esac
}
_LAST_VOL_CHECK=0; _CACHED_VOL_STATUS="Active"
get_audio_volume_and_mute() {
local now="${EPOCHSECONDS:-0}"; if [ "${1:-}" != "--force" ] && (( now - _LAST_VOL_CHECK < 15 )) && [ -n "$_CACHED_VOL_STATUS" ]; then echo "$_CACHED_VOL_STATUS"; return 0; fi; _LAST_VOL_CHECK="$now"; local out vol res="Active"; if out=$(wpctl get-volume @DEFAULT_AUDIO_SINK@ 2>/dev/null) && [[ -n "$out" ]]; then vol="${out#*: }"; vol="${vol%% *}"; vol="${vol//./}"; vol=$((10#$vol)); [[ "$out" == *MUTED* ]] && res="Muted (${vol}%)" || res="${vol}%"; elif out=$(pactl get-sink-volume @DEFAULT_SINK@ 2>/dev/null) && [[ "$out" =~ ([0-9]+%) ]]; then vol="${BASH_REMATCH[1]}"; [[ $(pactl get-sink-mute @DEFAULT_SINK@ 2>/dev/null) == *yes* ]] && res="Muted ($vol)" || res="$vol"; elif [[ "$OS_TYPE" = "macos" ]]; then out=$(osascript -e 'get volume settings' 2>/dev/null); [[ "$out" =~ output\ volume:([0-9]+).*output\ muted:(true|false) ]] && {
[[ "${BASH_REMATCH[2]}" = "true" ]] && res="Muted (${BASH_REMATCH[1]}%)" || res="${BASH_REMATCH[1]}%"
}; fi; _CACHED_VOL_STATUS="$res"; echo "$res"
}
toggle_audio_mute() {
echo -e "\n${BOLD}${MAGENTA}=== MASTER AUDIO MUTE / UNMUTE CONTROL ===${NC}\n"; local ok=1; if command -v wpctl &>/dev/null; then wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle 2>/dev/null; elif command -v pactl &>/dev/null; then pactl set-sink-mute @DEFAULT_SINK@ toggle 2>/dev/null; elif command -v amixer &>/dev/null; then amixer -q set Master toggle 2>/dev/null; elif [[ "$OS_TYPE" = "macos" ]]; then osascript -e "set volume output muted not (output muted of (get volume settings))" 2>/dev/null; elif [[ "$OS_TYPE" =~ ^(windows|wsl)$ ]]; then powershell.exe -NoProfile -Command '(New-Object -ComObject WScript.Shell).SendKeys([char]173)' 2>/dev/null; elif [[ "$OS_TYPE" = "freebsd" ]]; then mixer vol.mute=toggle 2>/dev/null || mixer -s vol toggle 2>/dev/null; else ok=0; fi; ((ok)) && echo -e "${GREEN}✓ Toggled.${NC} Status: ${BOLD}${CYAN}$(get_audio_volume_and_mute)${NC}" || echo -e "${YELLOW}Warning: No mixer detected.${NC}"; sleep 1.2
}
_run_tool() {
local target="$1" p rc=0 t_start="${EPOCHSECONDS:-$(date +%s 2>/dev/null || echo 0)}" found=0; shift
track_user_activity "Run Tool: $target" "tool_execution" 0 "pending" "Args: $*"
for p in "$SCRIPT_DIR/scripts" "$SCRIPT_DIR" "$PWD/scripts" "$PWD"; do
    if [ -x "$p/$target" ]; then "$p/$target" "$@"; rc=$?; found=1; break; fi
    if [ -f "$p/$target" ]; then bash "$p/$target" "$@"; rc=$?; found=1; break; fi
    if [ -f "$p/${target%.*}.py" ] && command -v python3 &>/dev/null; then python3 "$p/${target%.*}.py" "$@"; rc=$?; found=1; break; fi
done
if [ "$found" -eq 0 ]; then
    printf '%b\n' "${RED:-}Error: $target not found!${NC:-}"
    read -r -p "Press Enter to continue..."
    rc=1
fi
local t_end="${EPOCHSECONDS:-$(date +%s 2>/dev/null || echo 0)}" dur=$((t_end - t_start))
if [ "$rc" -ne 0 ]; then
    log_mp_error "_run_tool" "Tool '$target' failed with exit code $rc" "Args: $*"
    track_user_activity "Run Tool: $target" "tool_execution" "$dur" "error" "Exit code: $rc"
else
    track_user_activity "Run Tool: $target" "tool_execution" "$dur" "success" "Completed"
fi
return "$rc"
}
manage_mix_scheduler() {
local alarm_bin="" p ac_choice a_time a_daily a_vol a_mus sn_min c_id th_ch wk_ch wk_url nt_ch nt_txt nt_id; for p in "$SCRIPT_DIR/mplanetarians-alarm-clock/alarm.sh" "$SCRIPT_DIR/alarm.sh" "./alarm.sh"; do [ -x "$p" ] && { alarm_bin="$p"; break; }; done
_run_alarm() {
if [ -n "$alarm_bin" ]; then "$alarm_bin" "$@"; else printf '%b\n' "${RED}Error: alarm.sh not found!${NC}"; return 1; fi
}
while true; do clear; local alarm_summary; alarm_summary=$(get_alarm_clock_status_display); printf '%b\n' "${BOLD}${MAGENTA}======================================================================${NC}" "${BOLD}${MAGENTA}       MORNING ALARM CLOCK & DJ MIX PLAYBACK SCHEDULER SUITE          ${NC}" "${BOLD}${MAGENTA}======================================================================${NC}" "${alarm_summary:+${alarm_summary}\n${BOLD}${MAGENTA}----------------------------------------------------------------------${NC}}" "\n${BOLD}Select an operation:${NC}" "  ${BOLD}${BLUE}─── [ MPLANETARIANS ALARM CLOCK (WAKE UP EDITION) ] ───────────${NC}" "  ${BOLD}${CYAN} 1)${NC} Morning Screen & Daily Brief (${GREEN}Animated Clock, Weather, Steam Games${NC})" "  ${BOLD}${CYAN} 2)${NC} Alarm Clock Interactive Menu (${GREEN}Full TUI Alarm Interface${NC})" "  ${BOLD}${CYAN} 3)${NC} Set New Morning Alarm (${GREEN}Time, Daily/Once, Volume, Mix Path${NC})" "  ${BOLD}${CYAN} 4)${NC} List All Saved Alarms & Timers (${GREEN}systemd user timers & status${NC})" "  ${BOLD}${CYAN} 5)${NC} Silence / Stop Ringing Alarm (${GREEN}Move mouse or manual stop${NC})" "  ${BOLD}${CYAN} 6)${NC} Snooze Ringing Alarm (${GREEN}Ramp volume, custom snooze minutes${NC})" "  ${BOLD}${CYAN} 7)${NC} Cancel / Delete Saved Alarms (${GREEN}Cancel single alarm or all${NC})" "  ${BOLD}${CYAN} 8)${NC} Toggle Alarm Clock (${GREEN}Enable / Disable all alarms${NC})" "  ${BOLD}${CYAN} 9)${NC} Change Alarm Theme (${GREEN}Midnight Ink, Warm Brass, Forest Hour, Porcelain${NC})" "  ${BOLD}${CYAN}10)${NC} Configure Wake-Up Action (${GREEN}Browser on right screen / Console / URL${NC})" "  ${BOLD}${CYAN}11)${NC} Manage Morning Notes & Reminders (${GREEN}View / Add / Remove wake notes${NC})" "  ${BOLD}${CYAN}12)${NC} Test Morning Alarm Now (${RED}Loud Playback Test, Mouse Tracking & Steam Prompt${NC})\n" "  ${BOLD}${BLUE}─── [ DJ MIX AUTOMATED PLAYBACK SCHEDULER ] ───────────────────${NC}" "  ${BOLD}${CYAN}13)${NC} Schedule Single Mix / Playlist for Specific Date & Time (${GREEN}schedule_mix_playback.py${NC})\n" "  ${BOLD}${CYAN} 0)${NC} Return to Main Menu\n"; read -r -p "Enter choice [0-13]: " ac_choice; case "$ac_choice" in 1) clear; _run_alarm brief; press_enter ;; 2) _run_alarm menu || press_enter ;; 3) clear; printf '%b\n\n' "${BOLD}${MAGENTA}=== SET NEW MORNING ALARM ===${NC}"; read -r -p "Enter alarm time (e.g. 07:30, 6:45am, 1930): " a_time; if [ -n "$a_time" ]; then read -r -p "Repeat daily? [y/N]: " a_daily; read -r -p "Volume percentage [1-100, default 100]: " a_vol; read -r -p "Specific mix path (leave empty for random archive mix): " a_mus; local set_args=("$a_time"); [[ "$a_daily" =~ ^[Yy] ]] && set_args+=("--daily"); [ -n "$a_vol" ] && set_args+=("--volume" "$a_vol"); [ -n "$a_mus" ] && set_args+=("--music" "$a_mus"); _run_alarm set "${set_args[@]}"; fi; press_enter ;; 4) clear; printf '%b\n\n' "${BOLD}${MAGENTA}=== SAVED ALARMS & TIMERS ===${NC}"; _run_alarm list; press_enter ;; 5) printf '\n%b\n' "${YELLOW}Silencing alarm...${NC}"; _run_alarm stop; press_enter ;; 6) read -r -p "Enter snooze minutes (default 5): " sn_min; _run_alarm snooze "${sn_min:-5}"; press_enter ;; 7) clear; printf '%b\n\n' "${BOLD}${MAGENTA}=== CANCEL SAVED ALARMS ===${NC}"; if _run_alarm list; then echo ""; read -r -p "Enter Alarm ID to cancel (or 'all' to cancel all): " c_id; [ -n "$c_id" ] && _run_alarm cancel "$c_id"
fi; press_enter ;; 8) if [ -n "$alarm_bin" ]; then if [[ "$("$alarm_bin" list 2>/dev/null)" == *[Ee]nabled* ]]; then "$alarm_bin" disable; else "$alarm_bin" enable; fi; fi; sleep 1.2 ;; 9) clear; printf '%b\n' "${BOLD}${MAGENTA}=== CHANGE ALARM CLOCK THEME ===${NC}\n" "  ${BOLD}${CYAN}1)${NC} Midnight Ink (${DIM}navy and silver${NC})" "  ${BOLD}${CYAN}2)${NC} Warm Brass (${DIM}amber lamp-light${NC})" "  ${BOLD}${CYAN}3)${NC} Forest Hour (${DIM}deep green and gold${NC})" "  ${BOLD}${CYAN}4)${NC} Porcelain (${DIM}warm grey and rose${NC})"; read -r -p "Enter choice [1-4]: " th_ch; local themes=("" "midnight-ink" "warm-brass" "forest-hour" "porcelain"); [ -n "${themes[$th_ch]:-}" ] && _run_alarm theme "${themes[$th_ch]}"; sleep 1 ;; 10) clear; printf '%b\n' "${BOLD}${MAGENTA}=== CONFIGURE WAKE-UP ACTION ===${NC}\n\nCurrent action:"; _run_alarm task; printf '\n%b\n' "  ${BOLD}${CYAN}1)${NC} Browser on Display to the Right (Default)" "  ${BOLD}${CYAN}2)${NC} Browser with Custom URL" "  ${BOLD}${CYAN}3)${NC} Dedicated Console Window" "  ${BOLD}${CYAN}4)${NC} Clear / None"; read -r -p "Enter choice [1-4]: " wk_ch; case "$wk_ch" in 1) _run_alarm task browser ;; 2) read -r -p "Enter URL (e.g. https://news.ycombinator.com): " wk_url; _run_alarm task browser "$wk_url" ;; 3) _run_alarm task console ;; 4) _run_alarm task clear ;; esac; sleep 1 ;; 11) clear; printf '%b\n\n' "${BOLD}${MAGENTA}=== MORNING WAKE-UP NOTES ===${NC}"; _run_alarm note list; printf '\n%b\n' "  ${BOLD}${CYAN}1)${NC} Add Note" "  ${BOLD}${CYAN}2)${NC} Remove Note by ID" "  ${BOLD}${CYAN}0)${NC} Done"; read -r -p "Enter choice [0-2]: " nt_ch; case "$nt_ch" in 1) read -r -p "Enter note text: " nt_txt; [ -n "$nt_txt" ] && _run_alarm note add "$nt_txt" ;; 2) read -r -p "Enter note ID to remove: " nt_id; [ -n "$nt_id" ] && _run_alarm note rm "$nt_id" ;; esac; sleep 1 ;; 12) clear; printf '%b\n\n' "${BOLD}${RED}=== TESTING MORNING ALARM (LOUD PLAYBACK & STEAM PROMPT) ===${NC}" "${YELLOW}Starting alarm test. Press Ctrl+C or move mouse to stop.${NC}"; _run_alarm test; press_enter ;; 13) printf '\n%b\n\n' "${BOLD}${BLUE}=== DJ MIX SCHEDULER (PLAYS LOUDLY VIA DEFAULT AUDIO PLAYER) ===${NC}"; _run_tool "schedule_mix_playback.sh" --player "${DEFAULT_AUDIO_PLAYER:-strawberry}"; press_enter ;; 0|[qQ]|[eE][xX][iI][tT]) return 0 ;; *) printf '\n%b\n' "${RED}Invalid option!${NC}"; sleep 1 ;; esac; done
}
get_manager_uptime() {
local now="${EPOCHSECONDS:-${EPOCHSECONDS:-$(printf "%(%s)T" -1)}}"; local start="${MANAGER_START_EPOCH:-$now}"; (( start <= 0 )) && start="$now"; local el=$(( now - start )); (( el < 0 )) && el=0; local m_up="$((el % 60))s"; (( el >= 60 )) && m_up="$(((el % 3600) / 60))m $m_up"; if (( el >= 86400 )); then m_up="$((el / 86400))d $(((el % 86400) / 3600))h $m_up"; elif (( el >= 3600 )); then m_up="$((el / 3600))h $m_up"; fi; local sys_up="N/A"; if [ -r /proc/uptime ]; then local up_val sec; read -r up_val _ < /proc/uptime; sec="${up_val%%.*}"; sys_up="$(((sec % 86400) / 3600))h $(((sec % 3600) / 60))m"; (( sec >= 86400 )) && sys_up="$((sec / 86400))d $sys_up"; elif [ "${OS_TYPE:-}" != "windows" ] && command -v uptime &>/dev/null; then sys_up=$(uptime); sys_up="${sys_up#*up }"; sys_up="${sys_up%%,*}"; fi; local audio_st="Active"; [ "${OS_TYPE:-}" != "windows" ] && audio_st=$(get_audio_volume_and_mute); printf -v _MANAGER_UPTIME_LINE '%b' "  ${BOLD}${CYAN}⏱ MP Manager Uptime:${NC} ${m_up}  ${BOLD}${BLUE}│${NC}  ${BOLD}${CYAN}🖥 System Uptime:${NC} ${sys_up}  ${BOLD}${BLUE}│${NC}  ${BOLD}${CYAN}🔊 Audio:${NC} ${audio_st}"; printf '%s\n' "$_MANAGER_UPTIME_LINE"
}
detect_currently_playing_mix() {
get_mp_audio_player_track_info 2>/dev/null && [ -f "${MP_PLAYER_RAW_PATH:-}" ] && { printf '%s\n' "$MP_PLAYER_RAW_PATH"; return 0; }; get_audacious_track_info 2>/dev/null && [ -f "${AUDACIOUS_RESOLVED_PATH:-}" ] && { printf '%s\n' "$AUDACIOUS_RESOLVED_PATH"; return 0; }; get_strawberry_track_info 2>/dev/null && [ -f "${STRAWBERRY_RESOLVED_PATH:-}" ] && { printf '%s\n' "$STRAWBERRY_RESOLVED_PATH"; return 0; }; get_cliamp_track_info 2>/dev/null && [ -f "${CLIAMP_RESOLVED_PATH:-}" ] && { printf '%s\n' "$CLIAMP_RESOLVED_PATH"; return 0; }; if command -v playerctl &>/dev/null; then local p_st p_url p_path; p_st=$(playerctl status 2>/dev/null); if [[ "${p_st%%$'\n'*}" =~ ^(Playing|Paused)$ ]]; then p_url=$(playerctl metadata xesam:url 2>/dev/null); p_url="${p_url%%$'\n'*}"; if [[ "$p_url" == file://* ]]; then printf -v p_path '%b' "${p_url#file://}"; printf -v p_path '%b' "${p_path//%/\\x}"; [ -f "$p_path" ] && { printf '%s\n' "$p_path"; return 0; }; fi; fi; fi; local pid fd tgt; for pid in $(pgrep -i -f 'audacious|strawberry|vlc|mpv|kodi|cliamp' 2>/dev/null); do for fd in /proc/"$pid"/fd/*; do if [ -e "$fd" ] && tgt=$(readlink "$fd" 2>/dev/null); then case "$tgt" in *.flac|*.wav|*.mp3|*.m4a|*.ogg) [ -f "$tgt" ] && { printf '%s\n' "$tgt"; return 0; } ;; esac; fi; done; done; return 1
}
auto_show_playing_mix_assets() {
local mix_file="$1" player_name="${2:-${DEFAULT_AUDIO_PLAYER:-audacious}}"; [ -f "${mix_file:-}" ] || return 0; local mix_base="${mix_file##*/}"; local found_cover audio_spec audio_out; found_cover=$(find_mix_cover "$mix_file" 2>/dev/null); [ -f "${found_cover:-}" ] && open_cover_art_window "$found_cover" || found_cover=""; [ -n "$found_cover" ] && align_mix_windows_on_screen; if [ "${AUTO_PLAY_YOUTUBE_ON_STARTUP:-false}" = "true" ] && [ -n "${STARTUP_YOUTUBE_URL:-}" ]; then (sleep 0.6; open_video_url "$STARTUP_YOUTUBE_URL" &>/dev/null || true) &
fi; clear; audio_spec=$(get_playing_audio_spec_summary "$mix_file"); audio_out=$(get_active_audio_interface_display); printf '%b\n' "${BOLD}${MAGENTA}===================================================================================${NC}" "${BOLD}${MAGENTA}                 🎶 NOW PLAYING MIX & ASSET DISPLAY 🎶                             ${NC}" "${BOLD}${MAGENTA}===================================================================================${NC}" "\n${BOLD}Now Playing:${NC}       ${BOLD}${GREEN}${mix_base}${NC}" "\n${BOLD}Audio Player:${NC}      ${BOLD}${CYAN}${player_name}${NC}"; [ -n "$audio_spec" ]  && printf '%b\n' "\n${BOLD}Audio Specs:${NC}       ${BOLD}${GREEN}${audio_spec}${NC}"; [ -n "$audio_out" ]   && printf '%b\n' "\n${BOLD}Audio Output:${NC}     ${audio_out#  }"; [ -n "$found_cover" ] && printf '%b\n' "\n${BOLD}Cover Art Opened:${NC}  ${YELLOW}${found_cover##*/}${NC} (Image Viewer Window)"; printf '%b\n' "${BOLD}${MAGENTA}-----------------------------------------------------------------------------------${NC}"; printf '\n%b\n%b\n' "${BOLD}${BLUE}───────────────────────────────────────────────────────────────────────────────────${NC}" "${DIM}Playback assets loaded in separate windows. Press [Enter] to continue to Main Menu...${NC}"; if [ -t 0 ]; then read -r -t 3 < /dev/tty 2>/dev/null || read -r -t 3 || true; fi
}
check_and_show_currently_playing_mix() { return 0; }
open_video_url() {
local url="${1:-}" p="${DEFAULT_VIDEO_PLAYER:-vlc}"; [ -z "$url" ] && return 1; if [[ "$p" =~ ^(vlc|mpv)$ ]] && command -v "$p" &>/dev/null; then "$p" "$url" &>/dev/null & return 0; fi; local fp_list=""; command -v flatpak &>/dev/null && fp_list=$(flatpak list 2>/dev/null); if [ "$p" = "vlc" ] && [[ "$fp_list" == *org.videolan.VLC* ]]; then flatpak run org.videolan.VLC "$url" &>/dev/null & return 0; fi; if [[ "$fp_list" == *com.google.Chrome* ]]; then flatpak run com.google.Chrome "$url" &>/dev/null &
else local b; for b in google-chrome firefox xdg-open open; do command -v "$b" &>/dev/null && { "$b" "$url" &>/dev/null & return 0; }; done; [ "${OS_TYPE:-}" = "windows" ] && cmd.exe /c start "" "$url" &>/dev/null &
fi
}
_LAST_WEATHER_CHECK=0; _CACHED_WEATHER_DISPLAY=""
get_current_weather() {
[[ "${WEATHER_ENABLED:-true}" != "true" || -z "${WEATHER_LOCATION:-}" ]] && return 0; local now="${EPOCHSECONDS:-${EPOCHSECONDS:-$(printf "%(%s)T" -1)}}"; if (( now - _LAST_WEATHER_CHECK < 60 )) && [ -n "$_CACHED_WEATHER_DISPLAY" ]; then printf '%b\n' "$_CACHED_WEATHER_DISPLAY"; return 0; fi; _LAST_WEATHER_CHECK="$now"; local w_sh="$SCRIPT_DIR/scripts/get_weather.sh" w_data; [ -x "$w_sh" ] || w_sh="$PWD/scripts/get_weather.sh"; if [ -x "$w_sh" ]; then w_data=$("$w_sh" get 2>/dev/null); if [ -n "$w_data" ]; then _CACHED_WEATHER_DISPLAY="  ${BOLD}${CYAN}🌤️  Weather:${NC} ${WHITE}${w_data}${NC}  ${DIM}(${WEATHER_LOCATION})${NC}"; elif ! is_internet_connected; then _CACHED_WEATHER_DISPLAY="  ${BOLD}${CYAN}🌤️  Weather:${NC} ${YELLOW}Offline (No Internet Connection)${NC}  ${DIM}(${WEATHER_LOCATION})${NC}"; else return 0; fi; printf '%b\n' "$_CACHED_WEATHER_DISPLAY"; fi
}
_LAST_PLANETS_CHECK=0; _CACHED_PLANETS_DISPLAY=""
get_planets_above_horizon() {
[ "${PLANETS_ENABLED:-true}" != "true" ] && return 0; local now="${EPOCHSECONDS:-${EPOCHSECONDS:-$(printf "%(%s)T" -1)}}"; if (( now - _LAST_PLANETS_CHECK < 120 )) && [ -n "$_CACHED_PLANETS_DISPLAY" ]; then printf '%b\n' "$_CACHED_PLANETS_DISPLAY"; return 0; fi; _LAST_PLANETS_CHECK="$now"; local p_py="$SCRIPT_DIR/scripts/get_planets.py"; [ -f "$p_py" ] || p_py="$PWD/scripts/get_planets.py"; if [ -f "$p_py" ] && command -v python3 &>/dev/null; then _CACHED_PLANETS_DISPLAY=$(python3 "$p_py" --location "${WEATHER_LOCATION:-Swansea, UK}" 2>/dev/null); [ -n "$_CACHED_PLANETS_DISPLAY" ] && printf '%b\n' "$_CACHED_PLANETS_DISPLAY"; fi
}
manage_weather_menu() {
local w_sh="$SCRIPT_DIR/scripts/get_weather.sh"; [ ! -f "$w_sh" ] && w_sh="$PWD/scripts/get_weather.sh"; local p_py="$SCRIPT_DIR/scripts/get_planets.py"; [ ! -f "$p_py" ] && p_py="$PWD/scripts/get_planets.py"; while :; do clear; printf "%b\n" "${BOLD}${MAGENTA}======================================================================${NC}" "${BOLD}${MAGENTA}        METEOROLOGICAL & PLANETARY EPHEMERIS SETTINGS                 ${NC}" "${BOLD}${MAGENTA}======================================================================${NC}\n"; local w_st="DISABLED" p_st="DISABLED"; [ "${WEATHER_ENABLED:-true}" = "true" ] && w_st="ENABLED"; [ "${PLANETS_ENABLED:-true}" = "true" ] && p_st="ENABLED"; local w_badge="${!w_st:+${GREEN}${w_st}${NC}}"; [ "$w_st" = "DISABLED" ] && w_badge="${RED}DISABLED${NC}"; local p_badge="${!p_st:+${GREEN}${p_st}${NC}}"; [ "$p_st" = "DISABLED" ] && p_badge="${RED}DISABLED${NC}"; printf "%b Weather Banner Display:   %b\n" "${BOLD}" "$w_badge"; printf "%b Planets Banner Display:   %b\n" "${BOLD}" "$p_badge"; printf "%b Configured Location:      %b%b%b\n" "${BOLD}" "${CYAN}" "${WEATHER_LOCATION:-Not Set}" "${NC}"; if [ -x "$w_sh" ]; then local cw; cw=$("$w_sh" get 2>/dev/null); [ -n "$cw" ] && printf "%b Current Conditions:       %b%s%b\n" "${BOLD}" "${WHITE}" "$cw" "${NC}"; fi; if [ -f "$p_py" ] && command -v python3 &>/dev/null; then local cp; cp=$(python3 "$p_py" --location "${WEATHER_LOCATION:-Swansea, UK}" 2>/dev/null); [ -n "$cp" ] && printf "%b Planets Above Horizon:    %s\n" "${BOLD}" "${cp#*Planets: }"; fi; printf "%b Config File:              %b%s/config.env%b\n\n" "${BOLD}" "${DIM}" "$SCRIPT_DIR" "${NC}"; printf "%bSelect an option:%b\n" "${BOLD}" "${NC}"; printf "  %b%b 1)%b Toggle Weather Display (%b)\n" "${BOLD}" "${CYAN}" "${NC}" "$w_badge"; printf "  %b%b 2)%b Toggle Planets Above Horizon Display (%b)\n" "${BOLD}" "${CYAN}" "${NC}" "$p_badge"; printf "  %b%b 3)%b Change / Update Observer Location (%b%s%b)\n" "${BOLD}" "${CYAN}" "${NC}" "${BOLD}" "${WEATHER_LOCATION:-Swansea, UK}" "${NC}"; printf "  %b%b 4)%b Force Refresh Weather Now (Fetch live meteorological data)\n" "${BOLD}" "${CYAN}" "${NC}"; printf "  %b%b 5)%b View Full Planetary Ephemeris (All 7 Planets Altitude & Compass Heading)\n" "${BOLD}" "${CYAN}" "${NC}"; printf "  %b%b 6)%b Remove / Clear Location (Disables weather display)\n" "${BOLD}" "${CYAN}" "${NC}"; printf "  %b%b 0)%b Return to Previous Menu\n\n" "${BOLD}" "${CYAN}" "${NC}"; read -r -p "Enter choice [0-6]: " ch; case "$ch" in 1) [ "${WEATHER_ENABLED:-true}" = "true" ] && WEATHER_ENABLED="false" || WEATHER_ENABLED="true"; save_config_setting "WEATHER_ENABLED" "$WEATHER_ENABLED"; echo -e "\n${GREEN}✓ Weather display set to '$WEATHER_ENABLED'!${NC}"; sleep 1 ;; 2) [ "${PLANETS_ENABLED:-true}" = "true" ] && PLANETS_ENABLED="false" || PLANETS_ENABLED="true"; save_config_setting "PLANETS_ENABLED" "$PLANETS_ENABLED"; echo -e "\n${GREEN}✓ Planets display set to '$PLANETS_ENABLED'!${NC}"; sleep 1 ;; 3) echo -e "\nCurrent Location: ${CYAN}${WEATHER_LOCATION:-Swansea, UK}${NC}"; read -r -p "Enter new location: " nl; if [ -n "$nl" ]; then WEATHER_LOCATION="$nl"; WEATHER_ENABLED="true"; save_config_setting "WEATHER_LOCATION" "$nl"; save_config_setting "WEATHER_ENABLED" "true"; [ -x "$w_sh" ] && "$w_sh" clear &>/dev/null; echo -e "\n${GREEN}✓ Observer location updated to '$nl'!${NC}"; sleep 1; fi ;; 4) echo ""; [ -x "$w_sh" ] && "$w_sh" refresh; sleep 1.2 ;; 5) echo ""; [ -f "$p_py" ] && python3 "$p_py" --all --location "${WEATHER_LOCATION:-Swansea, UK}"; read -r -p $'\nPress Enter to return to settings...' ;; 6) WEATHER_LOCATION=""; WEATHER_ENABLED="false"; save_config_setting "WEATHER_LOCATION" ""; save_config_setting "WEATHER_ENABLED" "false"; [ -x "$w_sh" ] && "$w_sh" clear &>/dev/null; echo -e "\n${YELLOW}✓ Observer location cleared.${NC}"; sleep 1.2 ;; 0|[qQ]) return 0 ;; *) echo -e "\n${RED}Invalid choice!${NC}"; sleep 1 ;; esac; done
}
manage_video_dispatcher()          { _run_tool "launch_specific_video.sh" || launch_vlc; }
manage_publishing_schedule()      { _run_tool "publish_calendar_scheduler.sh"; }
manage_playlists_menu()            { _run_tool "manage_playlists.sh"; }
inspect_audio_studio_menu()        { _run_tool "inspect_audio_studio.sh"; }
generate_ppm_cover_menu()          { _run_tool "generate_ppm_cover.sh"; }
manage_sync_video_companion_menu() { _run_tool "sync_video_companion.sh"; }
manage_system_motd_menu()          { _run_tool "update_system_motd.sh"; }
manage_cloud_backup_suite()        { _run_tool "backup_mix_archive.sh"; }
shop_for_new_music_menu() {
for s in "$SCRIPT_DIR/scripts/shop_music.sh" "$PWD/scripts/shop_music.sh"; do [ -x "$s" ] && { "$s"; return; }; [ -f "$s" ] && { bash "$s"; return; }; done; local urls=("https://www.beatport.com" "https://music.apple.com" "https://bandcamp.com"); if command -v flatpak &>/dev/null && flatpak info com.google.Chrome &>/dev/null; then flatpak run com.google.Chrome "${urls[@]}" &>/dev/null &
else for u in "${urls[@]}"; do xdg-open "$u" &>/dev/null & sleep 0.2; done; fi
}
manage_mix_reports_menu() {
    run_sub_script "manage_mp_reporter.sh" "$@"
}
configure_daily_reports_settings() {
while true; do
    clear
    echo -e "${BOLD}${MAGENTA}======================================================================${NC}"
    echo -e "${BOLD}${MAGENTA}          CONFIGURE DAILY MIX REPORTS & AUTOMATED SCHEDULES           ${NC}"
    echo -e "${BOLD}${MAGENTA}======================================================================${NC}\n"
    local d_badge="${RED}DISABLED${NC}"
    [ "${DAILY_REPORTS_ENABLED:-true}" = "true" ] && d_badge="${GREEN}ENABLED${NC}"
    local m_badge="${RED}DISABLED${NC}"
    [ "${MONTHLY_REPORTS_ENABLED:-true}" = "true" ] && m_badge="${GREEN}ENABLED${NC}"
    local y_badge="${RED}DISABLED${NC}"
    [ "${YEARLY_REPORTS_ENABLED:-true}" = "true" ] && y_badge="${GREEN}ENABLED${NC}"

    echo -e "  Daily Reports Status:           ${d_badge}"
    echo -e "  Daily Scheduled Update Time:    ${BOLD}${CYAN}${DAILY_REPORTS_TIME:-10:00}${NC} (24-hour format)"
    echo -e "  Monthly Reports Status:         ${m_badge}"
    echo -e "  Yearly Reports Status:          ${y_badge}"
    echo -e "  Catch-Up Mode:                  ${GREEN}ACTIVE${NC} (Runs on manager start if missed)"
    echo -e "  Configuration File:             ${DIM}${SCRIPT_DIR}/config.env${NC}\n"

    echo -e "${BOLD}Select an option:${NC}"
    echo -e "  ${BOLD}${CYAN}1)${NC} Toggle Daily Reports ON / OFF (${d_badge})"
    echo -e "  ${BOLD}${CYAN}2)${NC} Change Scheduled Daily Update Time (Current: ${BOLD}${DAILY_REPORTS_TIME:-10:00}${NC})"
    echo -e "  ${BOLD}${CYAN}3)${NC} Toggle Monthly Reports ON / OFF (${m_badge})"
    echo -e "  ${BOLD}${CYAN}4)${NC} Toggle Yearly Reports ON / OFF (${y_badge})"
    echo -e "  ${BOLD}${CYAN}5)${NC} View Automated Reporting Engine Status & Diagnostics"
    echo -e "  ${BOLD}${CYAN}0)${NC} Return to Previous Menu\n"
    read -r -p "Enter choice [0-5]: " rep_choice
    case "$rep_choice" in
        1)
            if [ "${DAILY_REPORTS_ENABLED:-true}" = "true" ]; then
                DAILY_REPORTS_ENABLED="false"
            else
                DAILY_REPORTS_ENABLED="true"
            fi
            save_config_setting "DAILY_REPORTS_ENABLED" "$DAILY_REPORTS_ENABLED"
            echo -e "\n${GREEN}✓ Daily Reports set to '${DAILY_REPORTS_ENABLED}' and saved to config.env!${NC}"
            sleep 1
            ;;
        2)
            echo ""
            read -r -p "Enter scheduled update time in 24h HH:MM format [${DAILY_REPORTS_TIME:-10:00}]: " new_time
            if [[ "$new_time" =~ ^([01][0-9]|2[0-3]):[0-5][0-9]$ ]]; then
                DAILY_REPORTS_TIME="$new_time"
                save_config_setting "DAILY_REPORTS_TIME" "$new_time"
                echo -e "\n${GREEN}✓ Daily update time set to '${new_time}'!${NC}"
            elif [ -n "$new_time" ]; then
                echo -e "\n${RED}Invalid format. Please enter HH:MM (e.g. 10:00 or 19:30).${NC}"
            fi
            sleep 1.2
            ;;
        3)
            if [ "${MONTHLY_REPORTS_ENABLED:-true}" = "true" ]; then
                MONTHLY_REPORTS_ENABLED="false"
            else
                MONTHLY_REPORTS_ENABLED="true"
            fi
            save_config_setting "MONTHLY_REPORTS_ENABLED" "$MONTHLY_REPORTS_ENABLED"
            echo -e "\n${GREEN}✓ Monthly Reports set to '${MONTHLY_REPORTS_ENABLED}'!${NC}"
            sleep 1
            ;;
        4)
            if [ "${YEARLY_REPORTS_ENABLED:-true}" = "true" ]; then
                YEARLY_REPORTS_ENABLED="false"
            else
                YEARLY_REPORTS_ENABLED="true"
            fi
            save_config_setting "YEARLY_REPORTS_ENABLED" "$YEARLY_REPORTS_ENABLED"
            echo -e "\n${GREEN}✓ Yearly Reports set to '${YEARLY_REPORTS_ENABLED}'!${NC}"
            sleep 1
            ;;
        5)
            echo ""
            bash "$SCRIPT_DIR/scripts/mp_scheduled_reporter.sh" --status
            echo ""
            press_enter
            ;;
        0|[qQ])
            return 0
            ;;
        *)
            echo -e "\n${RED}Invalid option!${NC}"
            sleep 1
            ;;
    esac
done
}
_CACHED_OS_BADGE=""
get_os_badge() {
[ -n "$_CACHED_OS_BADGE" ] && { echo -e "$_CACHED_OS_BADGE"; return 0; }; local m; m="$UNAME_M" r; r="$(uname -r)"; case "$OS_TYPE" in macos)   _CACHED_OS_BADGE="${BOLD}${CYAN}🍏 macOS:${NC} $(sw_vers -productVersion 2>/dev/null || echo "$r") ($m)" ;; freebsd) _CACHED_OS_BADGE="${BOLD}${RED}😈 FreeBSD:${NC} $r ($m)" ;; windows|wsl) local wv="$r" s; s="$UNAME_S"; [[ "$s" =~ NT-([0-9.]+) ]] && wv="${BASH_REMATCH[1]}"; [ "$OS_TYPE" = "wsl" ] && _CACHED_OS_BADGE="${BOLD}${CYAN}🪟 Windows (WSL2):${NC} $wv" || _CACHED_OS_BADGE="${BOLD}${CYAN}🪟 Windows:${NC} $wv" ;; *) local d="" v=""; if [ -f /etc/os-release ]; then while IFS='=' read -r k val; do val="${val%\"}"; val="${val#\"}"; [ "$k" = "NAME" ] && d="$val"; [ "$k" = "VERSION" ] && v="$val"; done < /etc/os-release; fi; if [ -n "$d" ]; then [[ "${d,,}" =~ linux ]] && _CACHED_OS_BADGE="${BOLD}${CYAN}🐧 OS:${NC} $d $v (${BOLD}$r${NC})" || _CACHED_OS_BADGE="${BOLD}${CYAN}🐧 OS:${NC} $d Linux $v (${BOLD}$r${NC})"; else _CACHED_OS_BADGE="${BOLD}${CYAN}🐧 Kernel:${NC} $r"; fi ;; esac; echo -e "$_CACHED_OS_BADGE"
}
_LAST_OS_UPDATE_CHECK=0; _CACHED_OS_UPDATE_STATUS=""
get_os_update_status() {
local now; printf -v now '%(%s)T' -1 2>/dev/null || now=$(date +%s 2>/dev/null || echo 0); [ $((now - _LAST_OS_UPDATE_CHECK)) -lt 60 ] && [ -n "$_CACHED_OS_UPDATE_STATUS" ] && { echo -e "$_CACHED_OS_UPDATE_STATUS"; return 0; }; local status=""; case "$OS_TYPE" in macos) local count=0 plist="/Library/Preferences/com.apple.SoftwareUpdate.plist"; if [ -f "$plist" ]; then count=$(defaults read "$plist" RecommendedUpdates 2>/dev/null | grep -c "Identifier =" 2>/dev/null || echo 0); [ "$count" -eq 0 ] && count=$(defaults read "$plist" LastUpdatesAvailable 2>/dev/null || echo 0); fi; [[ "$count" =~ ^[1-9] ]] && status="${YELLOW}${count} pending${NC}" || status="${GREEN}Up to date${NC}" ;; windows|wsl) command -v reg.exe &>/dev/null && reg.exe query "HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\WindowsUpdate\\Auto Update\\RebootRequired" &>/dev/null && status="${YELLOW}Restart pending${NC}" || status="${GREEN}Up to date${NC}" ;; freebsd) status="${GREEN}Up to date${NC}" ;; *) if command -v rpm-ostree &>/dev/null && rpm-ostree status 2>/dev/null | grep -E -qi "(staged|upgrade available|staged: yes)"; then status="${YELLOW}1 staged (reboot)${NC}"; elif [ -f /var/run/reboot-required ]; then status="${YELLOW}Reboot required${NC}"; elif [ -f /var/lib/update-notifier/updates-available ]; then local uc; uc=$(awk '/updates can be applied/{print $1}' /var/lib/update-notifier/updates-available 2>/dev/null); [ -n "$uc" ] && [ "$uc" -gt 0 ] && status="${YELLOW}${uc} pending${NC}" || status="${GREEN}Up to date${NC}"; else is_internet_connected && status="${GREEN}Up to date${NC}" || status="${GREEN}Up to date${NC} ${DIM}(Offline)${NC}"; fi ;; esac; _LAST_OS_UPDATE_CHECK="$now"; _CACHED_OS_UPDATE_STATUS="$status"; echo -e "$status"
}
_LAST_CLOUD_CHECK=0; _CACHED_CLOUD_STATUS=""
get_cloud_backup_badge() {
local now; printf -v now '%(%s)T' -1 2>/dev/null || now=$(date +%s 2>/dev/null || echo 0); [ $((now - _LAST_CLOUD_CHECK)) -lt 30 ] && [ -n "$_CACHED_CLOUD_STATUS" ] && { echo -e "$_CACHED_CLOUD_STATUS"; return 0; }; if ! is_internet_connected; then _CACHED_CLOUD_STATUS="${BOLD}${CYAN}☁️  Cloud Backup:${NC} ${BOLD}${YELLOW}Offline (No Internet Connection)${NC}  ${BOLD}${BLUE}│${NC}  ${DIM}Cloud sync paused (Option 9 when online)${NC}"; _LAST_CLOUD_CHECK="$now"; echo -e "$_CACHED_CLOUD_STATUS"; return 0; fi; local sf="$HOME/.config/mix-manager/cloud_backup_state.json" btime=0 bdate="" bprov=""; if [ -f "$sf" ]; then btime=$(grep -o '"timestamp": [0-9]*' "$sf" 2>/dev/null | head -1 | cut -d' ' -f2); bdate=$(grep -o '"date": "[^"]*"' "$sf" 2>/dev/null | head -1 | cut -d'"' -f4); bprov=$(grep -o '"provider": "[^"]*"' "$sf" 2>/dev/null | head -1 | cut -d'"' -f4); fi; if [ -z "$bdate" ]; then local llog; llog=$(ls -t {"$SCRIPT_DIR","${MIX_ARCHIVE_DIR:-}"}/BACKUP_LOGS/backup_*.log 2>/dev/null | head -1); if [ -n "$llog" ] && [ -f "$llog" ]; then btime=$(stat -c %Y "$llog" 2>/dev/null || stat -f %m "$llog" 2>/dev/null || echo 0); printf -v bdate '%(%Y-%m-%d %H:%M)T' "$btime" 2>/dev/null || bdate="Recently"; [[ "$llog" =~ backup_([a-z0-9]+)_ ]] && bprov="${BASH_REMATCH[1]^^}"; fi; fi; [ -z "$bprov" ] && bprov="Google Drive"; if [ -z "$bdate" ] || [ "${btime:-0}" -eq 0 ]; then _CACHED_CLOUD_STATUS="${BOLD}${CYAN}☁️  Cloud Backup:${NC} ${BOLD}${YELLOW}No backup recorded${NC} ${DIM}(Option 9 to sync)${NC}"; _LAST_CLOUD_CHECK="$now"; echo -e "$_CACHED_CLOUD_STATUS"; return 0; fi; local fdirs=(); while IFS= read -r fd; do [ -d "$fd" ] || continue; case "${fd,,}" in *googledrive*|*google-drive*|*rclone*) continue ;; esac; fdirs+=("$fd"); done < <(get_all_flac_output_dirs 2>/dev/null); local pending=0; if [ ${#fdirs[@]} -gt 0 ]; then
pending=$(python3 - "$btime" "$(printf "%s\n" "${fdirs[@]}")" << 'PY' 2>/dev/null || echo 0
import os, sys
try:
    bt, dirs = float(sys.argv[1]), [d for d in sys.argv[2].splitlines() if os.path.isdir(d)]
    print(sum(1 for d in dirs for e in os.scandir(d) if e.name.lower().endswith('.flac') and e.is_file() and e.stat().st_mtime > bt))
except Exception: print(0)
PY
)
fi; [ "$pending" -eq 0 ] && _CACHED_CLOUD_STATUS="${BOLD}${CYAN}☁️  Cloud Backup (${bprov}):${NC} ${BOLD}${GREEN}Up-to-date${NC} ${DIM}(Last: ${bdate})${NC}  ${BOLD}${BLUE}│${NC}  ${BOLD}${GREEN}0 pending${NC}" || _CACHED_CLOUD_STATUS="${BOLD}${CYAN}☁️  Cloud Backup (${bprov}):${NC} ${BOLD}${YELLOW}${pending} mix(es) pending sync${NC}  ${BOLD}${BLUE}│${NC}  ${DIM}Last: ${bdate}${NC}"; _LAST_CLOUD_CHECK="$now"; echo -e "$_CACHED_CLOUD_STATUS"
}
case "$1" in update|--update)            shift; run_sub_script "update_manager.sh" "$@"; exit $? ;; version|--version|-v)       shift; run_sub_script "update_manager.sh" --version "$@"; exit $? ;; --wan2gp-start-4.5|--wan2gp-p45) pgrep -f "python.*wgp\.py" >/dev/null && { echo -e "\n${YELLOW}WAN2GP already running.${NC}"; exit 0; }; launch_wan2gp_terminal "4.5"; exit 0 ;; --wan2gp-start|--wan2gp) pgrep -f "python.*wgp\.py" >/dev/null && { echo -e "\n${YELLOW}WAN2GP already running.${NC}"; exit 0; }; launch_wan2gp_terminal "${2:-4.5}"; exit 0 ;; --wan2gp-stop)              run_sub_script "wan2gp.sh" stop; exit 0 ;; --tts|--wan2gp-tts)         shift; [ "${1:-}" = "25" ] && shift; run_wan2gp_tts_batch "$@"; exit 0 ;; --wan2gp-monitor|--monitor-wan2gp|--output-monitor) shift; run_wan2gp_output_monitor "$@"; exit 0 ;; --audio-monitor|--conversion-monitor|--media-monitor) shift; _mon_py="$SCRIPT_DIR/scripts/MP_Mix_Manager_Audio_File_Output_Monitor.py"; [ ! -f "$_mon_py" ] && _mon_py="$SCRIPT_DIR/MP_Mix_Manager_Audio_File_Output_Monitor.py"; exec python3 "$_mon_py" "$@" ;; --split-flac|--flac-split)  shift; split_flac_audio "$@"; exit 0 ;; --split-video|--split-mp4|--video-split) shift; split_video_clip "$@"; exit 0 ;; --cut-video)                shift; cut_video_clip "$@"; exit 0 ;; --beszel|--beszel-menu)     shift; manage_beszel "$@"; exit 0 ;; --beszel-start|--beszel-start-both) run_sub_script "beszel.sh" start; exit 0 ;; --beszel-hub|--beszel-start-hub)    run_sub_script "beszel.sh" start-hub; exit 0 ;; --beszel-agent|--beszel-start-agent) run_sub_script "beszel.sh" start-agent; exit 0 ;; --beszel-dashboard|--beszel-web)    run_sub_script "beszel.sh" dashboard; exit 0 ;; --beszel-stop)              run_sub_script "beszel.sh" stop; exit 0 ;; --beszel-status)            run_sub_script "beszel.sh" status; exit 0 ;; 57) [ -z "$2" ] && manage_beszel || run_sub_script "beszel.sh" "${2/1/start}"; exit 0 ;; --ollama|--ollama-menu)     shift; manage_ollama "$@"; exit 0 ;; --ollama-serve|--ollama-start|--ollama-bg) run_sub_script "manage_ollama.sh" start; exit 0 ;; --ollama-window|--ollama-term)             run_sub_script "manage_ollama.sh" start-window; exit 0 ;;
--ollama-stop)              run_sub_script "manage_ollama.sh" stop; exit 0 ;; --ollama-restart)           run_sub_script "manage_ollama.sh" restart; exit 0 ;; --ollama-chat)              shift; run_sub_script "manage_ollama.sh" chat "$@"; exit 0 ;; --ollama-voice|--ollama-voice-chat) shift; run_sub_script "manage_ollama.sh" voice "$@"; exit 0 ;; --ollama-audio|--ollama-recordings) run_sub_script "manage_ollama.sh" audio; exit 0 ;; --ollama-logs)              run_sub_script "manage_ollama.sh" logs; exit 0 ;; --ollama-status)            run_sub_script "manage_ollama.sh" status; exit 0 ;; 58) [ -z "$2" ] && manage_ollama || run_sub_script "manage_ollama.sh" "${2/1/start}"; exit 0 ;; --open-webui|--webui|webui|open-webui|--openwebui) shift; run_sub_script "manage_open_webui.sh" "$@"; exit 0 ;; --harmony|--mp-harmony|harmony|mp-harmony|--harmony-agent) shift; run_sub_script "manage_harmony_agent.sh" "$@"; exit 0 ;; --harmony-voice|--voice-talk|voice-talk|--harmony-voice-chat) run_sub_script "manage_harmony_agent.sh" voice; exit 0 ;; --harmony-audio|--harmony-recordings) run_sub_script "manage_harmony_agent.sh" audio; exit 0 ;; --dsh-mobile|--dsh|--dsh-start) run_sub_script "dsh_mobile.sh" start; exit 0 ;; --dsh-bg)                   run_sub_script "dsh_mobile.sh" start-bg; exit 0 ;; --dsh-web|--dsh-browser)    run_sub_script "dsh_mobile.sh" web; exit 0 ;; --dsh-stop)                 run_sub_script "dsh_mobile.sh" stop; exit 0 ;; --dsh-restart)              run_sub_script "dsh_mobile.sh" restart; exit 0 ;; --dsh-logs)                 run_sub_script "dsh_mobile.sh" logs; exit 0 ;; --dsh-status)               run_sub_script "dsh_mobile.sh" status; exit 0 ;; --dsh-menu|59)              [ -z "$2" ] && manage_dsh_mobile || run_sub_script "dsh_mobile.sh" "$2"; exit 0 ;; --daily-report|--report-daily) shift; python3 "$SCRIPT_DIR/scripts/mp_report_generator.py" --kind daily "$@"; exit $? ;; --monthly-report|--report-monthly) shift; python3 "$SCRIPT_DIR/scripts/mp_report_generator.py" --kind monthly "$@"; exit $? ;; --yearly-report|--report-yearly) shift; python3 "$SCRIPT_DIR/scripts/mp_report_generator.py" --kind yearly "$@"; exit $? ;; --report-status|--reporter-status) shift; bash "$SCRIPT_DIR/scripts/mp_scheduled_reporter.sh" --status "$@"; exit $? ;; --daily-email|--email-report|--email-briefing) shift; bash "$SCRIPT_DIR/scripts/mp_email_manager.sh" "$@"; exit $? ;; --error-log|--view-errors|--mp-error) shift; bash "$SCRIPT_DIR/scripts/mp_logging.sh" --tail "$@"; exit $? ;; 26|--reports|--mix-reports|--mp-reporter|--reporter) shift || true; manage_mix_reports_menu "$@"; exit 0 ;; --backup|--cloud-backup|9)  shift || true; run_sub_script "backup_mix_archive.sh" "$@"; exit 0 ;; --alarm*|alarm*|18)         shift || true; _run_tool "alarm.sh" "$@" ;; --congen*|congen*|*kdeconnect*) shift || true; _run_tool "Congen" "$@" ;; 56) case "$2" in 2) launch_wan2gp_terminal "4.5"; exit 0 ;; 3) run_sub_script "wan2gp.sh" stop; exit 0 ;; 25) shift 2; run_wan2gp_tts_batch "$@"; exit 0 ;; esac ;; esac
manage_integrity_and_verification() {
while :; do local opts=("1|Manage Audio Integrity Checksums|(SHA-256 Manifest & Verification)" "2|Verify FLAC Files for Integrity & Corruption|(Verify_FLAC_Files.sh)" "3|Lossless Legitimacy & Spectral Cutoff Inspector|(Detect Fake FLACs / MP3 Transcodes)" "4|Run Non-Destructive Bit-Rot Scrub on All Mix Archives|(scrub_mix_archive.sh)" "5|Automated Background Bit-Rot Scrub Timer|(Systemd User Timer)" "6|View Bit-Rot Scrub History & Logs|(VERIFY_LOGS)" "0|Return to Main Menu|(or Esc / q)"); run_interactive_submenu "AUDIO INTEGRITY, BIT-ROT SCRUB & FLAC VERIFICATION" "" opts 0; case "$REPLY" in 1) manage_audio_checksums ;; 2) echo -e "\n${BOLD}${YELLOW}Starting FLAC Integrity Scan...${NC}\n"; run_sub_script "Verify_FLAC_Files.sh"; press_enter ;; 3) [ -f "$SCRIPT_DIR/scripts/verify_lossless_spectral.py" ] && python3 "$SCRIPT_DIR/scripts/verify_lossless_spectral.py" || echo -e "\n${RED}Error: verify_lossless_spectral.py not found!${NC}"; press_enter ;; 4) echo -e "\n${BOLD}${YELLOW}Starting Non-Destructive Bit-Rot Scrub...${NC}\n"; run_sub_script "scrub_mix_archive.sh"; press_enter ;; 5) echo -e "\n${BOLD}${MAGENTA}--- Automated Background Bit-Rot Scrub Timer (Systemd) ---${NC}"; run_sub_script "scrub_mix_archive.sh" --timer-status; local t_opts=("1|Install & Enable Weekly Scrub Timer|(Sundays 03:00 AM)" "2|Disable & Uninstall Scrub Timer|" "0|Back|(or Esc)"); run_interactive_submenu "Automated Bit-Rot Scrub Timer" "" t_opts 0; [ "$REPLY" = "1" ] && run_sub_script "scrub_mix_archive.sh" --install-timer; [ "$REPLY" = "2" ] && run_sub_script "scrub_mix_archive.sh" --uninstall-timer; press_enter ;; 6) run_sub_script "scrub_mix_archive.sh" --logs; press_enter ;; 0|[qQ]|[eE][xX][iI][tT]|ESC) return 0 ;; *) echo -e "\n${RED}Invalid option!${NC}"; sleep 1 ;; esac; done
}
manage_storage_and_archive_config() {
while true; do local a_disp="${RED}Not Configured${NC} ${DIM}(Root: ${SCRIPT_DIR}/MIX_ARCHIVE)${NC}"; is_mix_archive_configured && a_disp="${GREEN}${MIX_ARCHIVE_DIR}${NC}"; local x_disp="${EXTRA_MIX_ARCHIVE_DIRS:+\n  Extra Archives  : ${CYAN}${EXTRA_MIX_ARCHIVE_DIRS}${NC}}"; local opts=("1|Show Mix Storage Drive Space Remaining|(All Configured Mix Drives)" "2|Show All Attached Drives Space Remaining|(Get_All_Drive_Space.sh)" "3|Refresh Archive Status & File Counts|(Rescan WAVs, FLACs & Tracklists)" "4|Configure Mix Archive Storage Locations|(Option 14: Primary & Multiple Folders)" "5|Clone Entire Mix Archive Folders to New Destination|(MP_Mix_Archive_Cloner)" "0|Return to Main Menu|(or Esc / q)"); run_interactive_submenu "STORAGE MANAGEMENT & ARCHIVE CONFIGURATION" "  Primary Archive : ${a_disp}${x_disp}\n" opts 0; case "$REPLY" in 1) show_mix_drive_space ;; 2) echo -e "\n${BOLD}${YELLOW}Scanning Drive Space Across Attached Storage...${NC}\n"; run_sub_script "Get_All_Drive_Space.sh"; press_enter ;; 3) echo -e "\n${BOLD}${YELLOW}Rescanning Mix Archive Status & File Counts across all drives...${NC}\n"; clear_archive_dir_cache; invalidate_archive_stats_cache; show_stats --force; save_header_cache 2>/dev/null || true; echo -e "\n${GREEN}✓ Archive status, file counts, and cache successfully refreshed.${NC}\n"; press_enter "Press [Enter] to return to Storage Management Menu..." ;; 4|13) configure_mix_archive_folder ;; 5|clone|cloner) run_sub_script "MP_Mix_Archive_Cloner.sh"; press_enter ;; 0|[qQ]|[eE][xX][iI][tT]|ESC) return 0 ;; *) echo -e "\n${RED}Invalid option!${NC}"; sleep 1 ;; esac; done
}
manage_tracklist_suite() {
local f py_exp="$SCRIPT_DIR/scripts/export_chapters.py" py_id="$SCRIPT_DIR/scripts/identify_mix_tracks.py"; while true; do local opts=("1|Tracklist Management Suite|(Browse, Search, View, Export HTML & PDF)" "2|Search for Mix & Auto-Play with Live Tracklist View|(MP Audio Player)" "3|Scan & Generate Missing Tracklists|(Check_Find_Tracklists.sh)" "4|Generate Master Tracklist HTML Index|(Generate_Master_Tracklist.sh)" "5|Launch MusicBrainz Picard Meta Tag Editor|(Auto-install if missing)" "6|Export YouTube & SoundCloud Chapters|(export_chapters.py - Timestamps / CUE / MD)" "7|Auto-Identify Unknown Tracks via Audio Fingerprinting|(identify_mix_tracks.py - AcoustID / Shazam)" "8|Extract Tracklist from Traktor History Files by Range|(Traktor .nml History)" "0|Return to Main Menu|(or Esc / q)"); run_interactive_submenu "TRACKLIST MANAGEMENT, SCANNING & METADATA SUITE" "" opts 0; case "$REPLY" in 1) manage_tracklists ;; 2) search_and_play_mix ;; 3) echo -e "\n${BOLD}${YELLOW}Scanning & Generating Missing Tracklists...${NC}\n"; run_sub_script "Check_Find_Tracklists.sh"; press_enter ;; 4) echo -e "\n${BOLD}${YELLOW}Starting Master Tracklist HTML Generation...${NC}\n"; [ -f "$SCRIPT_DIR/Generate_Master_Tracklist.sh" ] && bash "$SCRIPT_DIR/Generate_Master_Tracklist.sh" || run_sub_script "Generate_Master_Tracklist.sh"; press_enter ;; 5) launch_or_install_picard ;; 6) echo -e "\n${BOLD}${BLUE}=== EXPORT YOUTUBE & SOUNDCLOUD CHAPTERS ===${NC}\n"; read -r -p "Enter path to tracklist .txt or .cue file: " f; f="${f#[\'\"]}"; f="${f%[\'\"]}"; [ -f "$f" ] && python3 "$py_exp" "$f" --format all --clipboard || echo -e "${RED}Error: File not found.${NC}"; press_enter ;; 7) echo -e "\n${BOLD}${BLUE}=== AUTO-IDENTIFY TRACKS VIA AUDIO FINGERPRINTING ===${NC}\n"; read -r -p "Enter path to mix audio file: " f; f="${f#[\'\"]}"; f="${f%[\'\"]}"; [ -f "$f" ] && python3 "$py_id" "$f" || echo -e "${RED}Error: File not found.${NC}"; press_enter ;; 8) extract_tracklist_from_traktor_history ;; 0|[qQ]|[eE][xX][iI][tT]|ESC) return 0 ;; *) echo -e "\n${RED}Invalid option!${NC}"; sleep 1 ;; esac; done
}
generate_archive_folder_playlists_menu() {
ensure_playlists_generated_dirs; local p="$SCRIPT_DIR/scripts/generate_archive_folder_playlists.py"; [ -f "$p" ] || p="$SCRIPT_DIR/generate_archive_folder_playlists.py"; [ -f "$p" ] && python3 "$p" || { echo -e "${RED}Error: generate_archive_folder_playlists.py not found!${NC}"; press_enter; }
}
manage_playlists_and_history() {
local t_ver rb py_rb="$SCRIPT_DIR/scripts/export_rekordbox_playlist.py"; t_ver="$(get_traktor_version_mac 2>/dev/null)"; t_ver="${t_ver//$'\r'/}"; t_ver="${t_ver//$'\n'/}"; while true; do local opts=("1|Custom Mix Playlists Suite|(.m3u / .m3u8 / .xspf - Create, Edit & Launch)" "2|Generate Mix Archive Folder Playlists|(.m3u / .m3u8 / .xspf ➔ PLAYLISTS_GENERATED)" "3|Generate Playlist from History Files on Traktor ${t_ver:-3}|(Key Sorted / Decks Ready)" "4|Listen to Your Top 5 Tracks Right Now|$(get_top_5_status_badge)" "5|Export Playlists / Traktor History to Pioneer Rekordbox XML|(export_rekordbox_playlist.py)" "0|Return to Main Menu|(or Esc / q)"); run_interactive_submenu "CUSTOM PLAYLISTS & TRAKTOR HISTORY SUITE" "" opts 0; case "$REPLY" in 1) manage_playlists_menu ;; 2) generate_archive_folder_playlists_menu ;; 3) generate_traktor_playlist_from_history ;; 4|top5|top-5|top|special) manage_top_5_tracks ;; 5) echo -e "\n${BOLD}${BLUE}=== EXPORT TO PIONEER REKORDBOX XML ===${NC}\n"; read -r -p "Enter path to Traktor .nml, .m3u, or .m3u8 playlist: " rb; rb="${rb#[\'\"]}"; rb="${rb%[\'\"]}"; [ -f "$rb" ] && python3 "$py_rb" "$rb" || echo -e "${RED}Error: Playlist file not found.${NC}"; press_enter ;; 0|[qQ]|[eE][xX][iI][tT]|ESC) return 0 ;; *) echo -e "\n${RED}Invalid option!${NC}"; sleep 1 ;; esac; done
}
_LAST_TOP_5_CHECK=0; _CACHED_TOP_5_BADGE=""
get_top_5_status_badge() {
local now="$EPOCHSECONDS"; [ -z "$now" ] && printf -v now '%(%s)T' -1 2>/dev/null; if (( (now - _LAST_TOP_5_CHECK) < 30 )) && [ -n "$_CACHED_TOP_5_BADGE" ]; then echo -e "$_CACHED_TOP_5_BADGE"; return 0; fi; _LAST_TOP_5_CHECK="$now"; local p="$SCRIPT_DIR/scripts/top_5_tracks_manager.py"; [ -f "$p" ] || p="$SCRIPT_DIR/top_5_tracks_manager.py"; _CACHED_TOP_5_BADGE="$([ -f "$p" ] && python3 "$p" --badge 2>/dev/null || echo -e "${YELLOW}[Unlock Mystery / Ready]${NC}")"; echo -e "$_CACHED_TOP_5_BADGE"
}
manage_top_5_tracks() {
local f; for f in "$SCRIPT_DIR/scripts/top_5_tracks_manager.py" "$SCRIPT_DIR/top_5_tracks_manager.py"; do [ -f "$f" ] && { python3 "$f"; return; }; done; for f in "$SCRIPT_DIR/scripts/manage_top_5_tracks.sh" "$SCRIPT_DIR/manage_top_5_tracks.sh"; do [ -x "$f" ] && { bash "$f"; return; }; done; echo -e "\n${RED}Error: top_5_tracks_manager.py was not found in scripts/!${NC}\n"; press_enter
}
manage_daws_suite() {
local opts=("1|Digital Audio Workstations (DAWs) Menu|(Reaper, Logic Pro, FL Studio, Traktor, Ardour, Bitwig...)" "2|Open Mix WAV/FLAC Audio File in DAW|(Direct Mix Search/Select & Dispatch)" "0|Return to Main Menu|(or Esc / q)"); while true; do run_interactive_submenu "DIGITAL AUDIO WORKSTATIONS (DAWS) SUITE" "" opts 0; case "$REPLY" in 1) manage_daws ;; 2) open_mix_in_daw ;; 0|[qQ]|[eE][xX][iI][tT]|ESC) return 0 ;; *) echo -e "\n${RED}Invalid option!${NC}"; sleep 1 ;; esac; done
}
manage_traktor_s4_midi_menu() {
save_config_setting "TRAKTOR_S4_NOTIFIED" "true"
touch "$HOME/.config/mix-manager/traktor_s4_notified.flag" 2>/dev/null || true
local py_s4="$SCRIPT_DIR/scripts/traktor_s4_midi.py"
[ ! -f "$py_s4" ] && py_s4="$SCRIPT_DIR/traktor_s4_midi.py"
while true; do
local det_badge="${RED}Not Detected / Offline${NC}"
if amidi -l 2>/dev/null | grep -qi "Traktor"; then
det_badge="${GREEN}Detected & Connected (hw:0,0)${NC}"
elif [ -e "/dev/snd/midiC0D0" ] && grep -qi "Traktor" /proc/asound/cards 2>/dev/null; then
det_badge="${GREEN}Detected & Connected (/dev/snd/midiC0D0)${NC}"
fi
local srv_badge="${RED}Disabled / Inactive${NC}" srv_pid=""
local pid_file="$HOME/.config/mix-manager/traktor_s4_midi.pid"
if [ -f "$pid_file" ]; then
srv_pid="$(cat "$pid_file" 2>/dev/null || echo "")"
if [ -n "$srv_pid" ] && kill -0 "$srv_pid" 2>/dev/null; then
srv_badge="${GREEN}Enabled & Active (PID: ${srv_pid})${NC}"
else
rm -f "$pid_file" 2>/dev/null || true
fi
fi
local pl_badge="${DIM}Standby / Offline${NC}"
if [ -f "$HOME/.config/mix-manager/mp_audio_player.sock" ] || [ -f "$HOME/.config/mix-manager/mp_audio_player.port" ]; then
pl_badge="${GREEN}Connected to MP Audio Player${NC}"
fi
local s4_hdr="  • Hardware Unit         : ${BOLD}${WHITE}Native Instruments Traktor Kontrol S4${NC}\n"
s4_hdr+="  • ALSA Hardware Port    : ${CYAN}hw:0,0${NC} ${DIM}(/dev/snd/midiC0D0)${NC}\n"
s4_hdr+="  • Hardware Status       : ${det_badge}\n"
s4_hdr+="  • MIDI Service Daemon   : ${srv_badge}\n"
s4_hdr+="  • Audio Player IPC      : ${pl_badge}\n"
s4_hdr+="  • MIDI Mode Shortcut    : Hold ${BOLD}${YELLOW}SHIFT + BROWSE${NC} (MK1) or ${BOLD}${YELLOW}SHIFT + PREVIEW${NC} (MK2)\n"
s4_hdr+="  • Supported in v0.4.0   : ${BOLD}${GREEN}Traktor Kontrol S4 Exclusively${NC}\n"
local s4_opts=(
"1|Enable Traktor Kontrol S4 MIDI Mapping Support|(Start Background Service & Save Setting)"
"2|Disable Traktor Kontrol S4 MIDI Mapping Support|(Stop Background Service & Save Setting)"
"3|Restart MIDI Controller Service / Rescan hw:0,0|(Re-initialize ALSA Rawmidi Connection)"
"4|Interactive Live MIDI Monitor & Packet Test|(Real-Time Pitch Sliders, Buttons & Encoders)"
"5|View Traktor Kontrol S4 Getting Started User Guide|(Full Hardware Mapping Documentation)"
"6|Open Official Native Instruments PDF Manuals|(Controller Editor & S4 MK2 Guides)"
"0|Return to Previous Menu|(or Esc / q)"
)
run_interactive_submenu "TRAKTOR KONTROL S4 MIDI HARDWARE CONTROL & MAPPING (v0.4.0)" "$s4_hdr" s4_opts 0
local opt="$REPLY"
case "$opt" in
1)
echo -e "\n${BOLD}${CYAN}Starting Traktor Kontrol S4 MIDI Service...${NC}\n"
[ -f "$py_s4" ] && python3 "$py_s4" --start
save_config_setting "MIDI_CONTROL_ENABLED" "true"
save_config_setting "TRAKTOR_S4_NOTIFIED" "true"
play_sound_effect "storage" 2>/dev/null || true
sleep 1.5 ;;
2)
echo -e "\n${BOLD}${YELLOW}Stopping Traktor Kontrol S4 MIDI Service...${NC}\n"
[ -f "$py_s4" ] && python3 "$py_s4" --stop
save_config_setting "MIDI_CONTROL_ENABLED" "false"
sleep 1.5 ;;
3)
echo -e "\n${BOLD}${CYAN}Restarting Traktor Kontrol S4 MIDI Service...${NC}\n"
[ -f "$py_s4" ] && python3 "$py_s4" --restart
sleep 1.5 ;;
4|monitor|test)
echo -e "\n${BOLD}${YELLOW}Launching Interactive Live MIDI Monitor Console...${NC}\n"
[ -f "$py_s4" ] && python3 "$py_s4" --monitor
press_enter ;;
5|guide|help|manual)
clear
if [ -f "$py_s4" ]; then
python3 "$py_s4" --guide | ${PAGER:-less -R} 2>/dev/null || python3 "$py_s4" --guide
elif [ -f "$SCRIPT_DIR/docs/TRAKTOR_KONTROL_S4_USER_GUIDE.md" ]; then
cat "$SCRIPT_DIR/docs/TRAKTOR_KONTROL_S4_USER_GUIDE.md" | ${PAGER:-less -R} 2>/dev/null || cat "$SCRIPT_DIR/docs/TRAKTOR_KONTROL_S4_USER_GUIDE.md"
fi
press_enter ;;
6|pdf|manuals)
echo -e "\n${BOLD}${BLUE}=== OFFICIAL TRAKTOR KONTROL S4 PDF MANUALS ===${NC}\n"
local m1="$SCRIPT_DIR/docs/Controller_Editor_Manual_English.pdf"
local m2="$SCRIPT_DIR/docs/traktor_kontrol_s4_mk2_manual_english.pdf"
echo -e "  ${BOLD}1)${NC} Native Instruments Controller Editor Manual (206 pages):\n     ${CYAN}${m1}${NC}"
echo -e "  ${BOLD}2)${NC} Traktor Kontrol S4 MK2 Hardware & Setup Manual (233 pages):\n     ${CYAN}${m2}${NC}\n"
read -r -p "Select manual to open [1-2, or 0 to cancel]: " m_sel
if [ "$m_sel" = "1" ] && [ -f "$m1" ]; then
(xdg-open "$m1" &>/dev/null &) || echo "Path: $m1"
elif [ "$m_sel" = "2" ] && [ -f "$m2" ]; then
(xdg-open "$m2" &>/dev/null &) || echo "Path: $m2"
fi
sleep 1 ;;
0|[qQ]|ESC) return 0 ;;
*) echo -e "\n${RED}Invalid option!${NC}"; sleep 1 ;;
esac; done
}
manage_studio_hardware_and_volume() {
local opts=("1|Studio Hardware & Software Inspector|(PipeWire, ALSA, DAWs, MIDI Controllers & Surfaces)" "2|Toggle Audio Mute / Unmute & Master Volume Control|(Instant PipeWire/ALSA Mute)" "3|Traktor Kontrol S4 MIDI Hardware Control & Mapping|(Enable/Disable, Live Status, Port hw:0,0, Pitch & Guide)" "0|Return to Main Menu|(or Esc / q)"); while true; do run_interactive_submenu "STUDIO HARDWARE, INTERFACES & VOLUME CONTROL" "" opts 0; case "$REPLY" in 1) inspect_audio_studio_menu ;; 2) toggle_audio_mute ;; 3|s4|midi|kontrol) manage_traktor_s4_midi_menu ;; 0|[qQ]|[eE][xX][iI][tT]|ESC) return 0 ;; *) echo -e "\n${RED}Invalid option!${NC}"; sleep 1 ;; esac; done
}
manage_desktop_shortcuts() {
local opts=("1|Run Any Desktop Shortcut Manually|(Games, Audio, Files, Tools, AI Servers)" "2|Generate Keyboard Shortcut for a Desktop Shortcut|(e.g. Ctrl+Alt+Enter)" "0|Return to Main Menu|(or Esc / q)"); while true; do run_interactive_submenu "RUN ANY DESKTOP SHORTCUTS — Linux / Windows / macOS" "  Launch and automate Desktop Shortcuts (Linux KDE Plasma, Windows .lnk, macOS .app).\n" opts 0; case "$REPLY" in 1) _run_desktop_shortcut_manual ;; 2) _bind_desktop_shortcut_keyboard ;; 0|[qQ]|[eE][xX][iI][tT]|ESC) return 0 ;; *) echo -e "\n${RED}Invalid option!${NC}"; sleep 1 ;; esac; done
}
_dsk_is_windows() {
[[ "${OS_TYPE:-}${OSTYPE:-}" =~ (windows|msys|cygwin|win32) ]]
}
_dsk_have_ps() {
[ -n "$_CACHED_PS" ] || _CACHED_PS="$(command -v powershell.exe || command -v pwsh.exe || command -v pwsh)" 2>/dev/null; [ -n "$_CACHED_PS" ]
}
_dsk_ps() {
_dsk_have_ps || return 127; "$_CACHED_PS" -NoProfile -NonInteractive -ExecutionPolicy Bypass -Command "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $1" 2>/dev/null
}
_dsk_collect_windows() {
shortcut_names=(); shortcut_files=(); shortcut_comments=(); local line; while IFS=$'\t' read -r _n _p _h _t; do [ -n "$_p" ] && { shortcut_names+=("$_n"); shortcut_files+=("$_p"); shortcut_comments+=("$_t"); }
done < <(_dsk_ps '$dirs=@([Environment]::GetFolderPath("Desktop"),[Environment]::GetFolderPath("CommonDesktopDirectory"),[Environment]::GetFolderPath("Programs"),[Environment]::GetFolderPath("CommonPrograms"))|?{$_ -and (Test-Path $_)}|Select -Unique
$sh=New-Object -ComObject WScript.Shell;$s=@{}
gci -LiteralPath $dirs -Recurse -Depth 2 -File -EA 0|?{$_.Extension -in ".lnk",".url"}|sort Name|%{
if($_.BaseName -notmatch "(?i)uninstall" -and !$s[$_.FullName]){
$s[$_.FullName]=1;$t=""
if($_.Extension -eq ".lnk"){try{$t=$sh.CreateShortcut($_.FullName).TargetPath}catch{}}
Write-Output "$($_.BaseName)`t$($_.FullName)`t`t$t"
}}' | tr -d '\r')
}
_run_desktop_shortcut_manual_windows() {
if ! _dsk_have_ps; then echo -e "\n${RED}PowerShell was not found — it is required to launch Windows shortcuts.${NC}"; press_enter; return 0; fi; echo -e "\n${DIM}Scanning Desktop and Start Menu for Windows shortcuts...${NC}"; _dsk_collect_windows; local total=${#shortcut_names[@]}; [ "$total" -eq 0 ] && { echo -e "\n${RED}No Windows shortcuts (.lnk / .url) found.${NC}"; press_enter; return 0; }; while true; do clear; echo -e "${BOLD}${MAGENTA}${S70}==\n   🖥️  RUN ANY DESKTOP SHORTCUT MANUALLY — Windows\n${S70}==${NC}\n${DIM}Select a number to launch the shortcut. Press 0 to go back.${NC}\n"; local idx; for (( idx=0; idx<total; idx++ )); do printf "  ${BOLD}${CYAN}\%3d)${NC} 📌 ${BOLD}\%s${NC}\n" "$((idx+1))" "${shortcut_names[idx]}"; [ -n "${shortcut_comments[idx]}" ] && echo -e "       ${DIM}${shortcut_comments[idx]}${NC}"; done; echo -e "\n  ${BOLD}${CYAN}  0)${NC} Return to Desktop Shortcuts Menu\n"; local choice; read -r -p "Enter shortcut number to launch [0-$total]: " choice; [[ "$choice" =~ ^(0|[qQ])$ ]] && return 0; if ! [[ "$choice" =~ ^[0-9]+$ ]] || (( choice < 1 || choice > total )); then echo -e "\n${RED}Invalid selection.${NC}"; sleep 1; continue; fi; local sel_idx=$((choice-1)); echo -e "\n${BOLD}${YELLOW}▶  Launching: ${GREEN}${shortcut_names[sel_idx]}${NC}\n${DIM}File: ${shortcut_files[sel_idx]}${NC}"; if DSK_LNK="${shortcut_files[sel_idx]}" _dsk_ps 'Start-Process -FilePath $env:DSK_LNK; exit [int](!$?)' >/dev/null; then echo -e "${GREEN}✔  Shortcut launched successfully!${NC}"; else echo -e "${RED}Error: Failed to launch shortcut.${NC}"; fi; echo ""; press_enter; done
}
_bind_desktop_shortcut_keyboard_windows() {
local -a shortcut_names shortcut_files shortcut_comments shortcut_categories shortcut_existing_keys; if ! _dsk_have_ps; then echo -e "\n${RED}PowerShell was not found — it is required to set Windows shortcut keys.${NC}"; press_enter; return 0; fi; echo -e "\n${DIM}Scanning Desktop and Start Menu for Windows shortcuts...${NC}"; _dsk_collect_windows; local -a _n2=() _f2=() _c2=() _k2=(); local i; for (( i=0; i<${#shortcut_files[@]}; i++ )); do case "${shortcut_files[$i]}" in *.lnk|*.LNK) _n2+=("${shortcut_names[$i]}"); _f2+=("${shortcut_files[$i]}"); _c2+=("${shortcut_comments[$i]}"); _k2+=("${shortcut_existing_keys[$i]}") ;; esac; done; shortcut_names=("${_n2[@]}"); shortcut_files=("${_f2[@]}"); shortcut_comments=("${_c2[@]}"); shortcut_existing_keys=("${_k2[@]}"); if [ ${#shortcut_names[@]} -eq 0 ]; then echo -e "\n${RED}No Windows .lnk shortcuts found on the Desktop or in the Start Menu.${NC}"; press_enter; return 0; fi; while true; do clear; echo -e "${BOLD}${MAGENTA}${S70}==${NC}\n${BOLD}${MAGENTA}   ⌨️  GENERATE KEYBOARD SHORTCUT FOR DESKTOP SHORTCUT (Windows)       ${NC}\n${BOLD}${MAGENTA}${S70}==${NC}\n  ${DIM}Select a shortcut and assign a hotkey (stored in the .lnk file).${NC}"; echo ""; local idx _idx_str _badge; for (( idx=0; idx<${#shortcut_names[@]}; idx++ )); do printf -v _idx_str "%3d" "$(( idx + 1 ))"; _badge=""; [ -n "${shortcut_existing_keys[$idx]}" ] && _badge=" ${CYAN}[${shortcut_existing_keys[$idx]}]${NC}"; echo -e "  ${BOLD}${CYAN}${_idx_str})${NC} 📌 ${BOLD}${shortcut_names[$idx]}${NC}${_badge}"; done; echo ""; echo -e "  ${BOLD}${CYAN}  0)${NC} Return to Desktop Shortcuts Menu"; echo ""; local sc_choice; read -r -p "Enter shortcut number to bind [0-${#shortcut_names[@]}]: " sc_choice; if [[ "$sc_choice" == "0" ]] || [[ "$sc_choice" =~ ^[qQ]$ ]]; then return 0; fi; if ! [[ "$sc_choice" =~ ^[0-9]+$ ]] || [ "$sc_choice" -lt 1 ] || [ "$sc_choice" -gt "${#shortcut_names[@]}" ]; then echo -e "\n${RED}Invalid selection.${NC}"; sleep 1.5; continue; fi; local _sel_idx=$(( sc_choice - 1 )); local _sel_name="${shortcut_names[$_sel_idx]}"; local _sel_file="${shortcut_files[$_sel_idx]}"; echo ""; echo -e "  ${BOLD}Selected shortcut:${NC} ${GREEN}${_sel_name}${NC}\n  ${DIM}File: ${_sel_file}${NC}"; [ -n "${shortcut_existing_keys[$_sel_idx]}" ] && echo -e "  ${YELLOW}⚠️  Currently bound to: ${BOLD}${shortcut_existing_keys[$_sel_idx]}${NC}"; echo -e "  ${DIM}Examples: Ctrl+Alt+G   Ctrl+Shift+F5   Ctrl+Alt+1  (Windows always includes Ctrl+Alt)${NC}\n  ${DIM}Enter 'clear' to remove the existing hotkey. The Windows/Meta key is not supported.${NC}"; local new_shortcut; read -r -p "  Keyboard shortcut (or 0 to cancel): " new_shortcut; if [[ "$new_shortcut" == "0" ]] || [[ -z "$new_shortcut" ]]; then continue; fi; local norm_shortcut=""; if [[ "$(echo "$new_shortcut" | tr 'A-Z' 'a-z')" == "clear" ]]; then norm_shortcut=""; else if echo "$new_shortcut" | grep -qiE '(^|\+)[[:space:]]*(meta|win|super)[[:space:]]*(\+|$)'; then echo -e "\n${RED}The Windows/Meta key cannot be used in Windows shortcut hotkeys.${NC}"; press_enter; continue; fi; norm_shortcut="$(echo "$new_shortcut" | tr -d ' ' | sed -E 's/[Cc][Oo][Nn][Tt][Rr][Oo][Ll]/Ctrl/g' | awk -F+ 'BEGIN{OFS="+"}{for(i=1;i<=NF;i++) $i=toupper($i); print}')"; fi; local confirm_bind; read -r -p "  Apply '${norm_shortcut:-<none>}' to ${_sel_name}? [Y/n]: " confirm_bind; [[ "$confirm_bind" =~ ^[Nn]$ ]] && continue; local _result
_result="$(DSK_LNK="$_sel_file" DSK_HK="$norm_shortcut" _dsk_ps '
try{
  $sh=New-Object -ComObject WScript.Shell
  $l=$sh.CreateShortcut($env:DSK_LNK)
  $l.Hotkey=$env:DSK_HK
  $l.Save()
  $sh.CreateShortcut($env:DSK_LNK).Hotkey
}catch{ Write-Output ("ERROR: "+$_.Exception.Message) }')"
if [[ "$_result" == ERROR:* ]] || { [ -n "$norm_shortcut" ] && [ -z "$_result" ]; }; then echo -e "\n${RED}Failed to write hotkey. ${_result}${NC}\n${DIM}Shortcuts in 'All Users' locations may need an Administrator terminal.${NC}"; else echo -e "\n${GREEN}✔  Hotkey set to: ${BOLD}${_result:-<none>}${NC}\n  ${DIM}Windows only honours hotkeys on shortcuts located on the Desktop or in the Start Menu.${NC}"; shortcut_existing_keys[$_sel_idx]="$_result"; fi; press_enter; done
}
_dsk_is_mac() {
[ "${OS_TYPE:-}" = "macos" ] && return 0; [ "$UNAME_S" = "Darwin" ]
}
_dsk_collect_mac() {
shortcut_names=(); shortcut_files=(); shortcut_comments=(); shortcut_categories=(); shortcut_existing_keys=(); local _dir _f _base _key; for _dir in "$HOME/Desktop" "$HOME/Applications" "/Applications" "/Applications/Utilities" "/System/Applications"; do [ -d "$_dir" ] || continue; while IFS= read -r -d '' _f; do _base="$(basename "$_f")"; _base="${_base%.*}"; shortcut_names+=("$_base"); shortcut_files+=("$_f"); shortcut_comments+=("$_f"); shortcut_categories+=(""); _key="$(/usr/libexec/PlistBuddy -c "Print :NSServicesStatus:'(null) - Launch ${_base} - runWorkflowAsService':key_equivalent" "$HOME/Library/Preferences/pbs.plist" 2>/dev/null)"; shortcut_existing_keys+=("$(_dsk_mac_key_display "$_key")"); done < <(find "$_dir" -maxdepth 1 \( -name '*.app' -o -name '*.command' -o -name '*.webloc' \) -print0 2>/dev/null | sort -z); done
}
_dsk_mac_key_display() {
local _k="$1" _out="" _c; [ -n "$_k" ] || return 0; while [ -n "$_k" ]; do _c="${_k:0:1}"; _k="${_k:1}"; case "$_c" in
'@') _out="${_out}Cmd+" ;;
'~') _out="${_out}Option+" ;;
'^') _out="${_out}Ctrl+" ;;
'$') _out="${_out}Shift+" ;; *)   _out="${_out}$(echo "$_c" | tr 'a-z' 'A-Z')" ;; esac; done; echo "$_out"
}
_run_desktop_shortcut_manual_mac() {
local -a shortcut_names shortcut_files shortcut_comments shortcut_categories shortcut_existing_keys; echo -e "\n${DIM}Scanning Desktop and Applications folders...${NC}"; _dsk_collect_mac; if [ ${#shortcut_names[@]} -eq 0 ]; then echo -e "\n${RED}No macOS applications or shortcuts (.app / .command / .webloc) found.${NC}"; press_enter; return 0; fi; while true; do clear; echo -e "${BOLD}${MAGENTA}${S70}==${NC}\n${BOLD}${MAGENTA}   🖥️  RUN ANY DESKTOP SHORTCUT MANUALLY — macOS                       ${NC}\n${BOLD}${MAGENTA}${S70}==${NC}\n  ${DIM}Select a number to launch. Press 0 to go back.${NC}"; echo ""; local idx _idx_str; for (( idx=0; idx<${#shortcut_names[@]}; idx++ )); do printf -v _idx_str "%3d" "$(( idx + 1 ))"; echo -e "  ${BOLD}${CYAN}${_idx_str})${NC} 📌 ${BOLD}${shortcut_names[$idx]}${NC}\n       ${DIM}${shortcut_comments[$idx]}${NC}"; done; echo ""; echo -e "  ${BOLD}${CYAN}  0)${NC} Return to Desktop Shortcuts Menu"; echo ""; local sc_choice; read -r -p "Enter shortcut number to launch [0-${#shortcut_names[@]}]: " sc_choice; if [[ "$sc_choice" == "0" ]] || [[ "$sc_choice" =~ ^[qQ]$ ]]; then return 0; fi; if ! [[ "$sc_choice" =~ ^[0-9]+$ ]] || [ "$sc_choice" -lt 1 ] || [ "$sc_choice" -gt "${#shortcut_names[@]}" ]; then echo -e "\n${RED}Invalid selection — please enter a number between 1 and ${#shortcut_names[@]}.${NC}"; sleep 1.5; continue; fi; local _sel_name="${shortcut_names[$((sc_choice-1))]}"; local _sel_file="${shortcut_files[$((sc_choice-1))]}"; echo ""; echo -e "${BOLD}${YELLOW}▶  Launching: ${GREEN}${_sel_name}${NC}\n   ${DIM}Command: open \"${_sel_file}\"${NC}"; if open "$_sel_file" &>/dev/null; then echo -e "${GREEN}✔  Shortcut launched successfully!${NC}"; else echo -e "${RED}Error: Failed to launch shortcut.${NC}"; fi; echo ""; press_enter; done
}
_bind_desktop_shortcut_keyboard_mac() {
local -a shortcut_names shortcut_files shortcut_comments shortcut_categories shortcut_existing_keys; echo -e "\n${DIM}Scanning Desktop and Applications folders...${NC}"; _dsk_collect_mac; if [ ${#shortcut_names[@]} -eq 0 ]; then echo -e "\n${RED}No macOS applications or shortcuts (.app / .command / .webloc) found.${NC}"; press_enter; return 0; fi; while true; do clear; echo -e "${BOLD}${MAGENTA}${S70}==${NC}\n${BOLD}${MAGENTA}   ⌨️  GENERATE KEYBOARD SHORTCUT FOR DESKTOP SHORTCUT (macOS)         ${NC}\n${BOLD}${MAGENTA}${S70}==${NC}\n  ${DIM}Creates a Quick Action service with a keyboard shortcut.${NC}"; echo ""; local idx _idx_str _badge; for (( idx=0; idx<${#shortcut_names[@]}; idx++ )); do printf -v _idx_str "%3d" "$(( idx + 1 ))"; _badge=""; [ -n "${shortcut_existing_keys[$idx]}" ] && _badge=" ${CYAN}[${shortcut_existing_keys[$idx]}]${NC}"; echo -e "  ${BOLD}${CYAN}${_idx_str})${NC} 📌 ${BOLD}${shortcut_names[$idx]}${NC}${_badge}"; done; echo ""; echo -e "  ${BOLD}${CYAN}  0)${NC} Return to Desktop Shortcuts Menu"; echo ""; local sc_choice; read -r -p "Enter shortcut number to bind [0-${#shortcut_names[@]}]: " sc_choice; if [[ "$sc_choice" == "0" ]] || [[ "$sc_choice" =~ ^[qQ]$ ]]; then return 0; fi; if ! [[ "$sc_choice" =~ ^[0-9]+$ ]] || [ "$sc_choice" -lt 1 ] || [ "$sc_choice" -gt "${#shortcut_names[@]}" ]; then echo -e "\n${RED}Invalid selection.${NC}"; sleep 1.5; continue; fi; local _sel_idx=$(( sc_choice - 1 )); local _sel_name="${shortcut_names[$_sel_idx]}"; local _sel_file="${shortcut_files[$_sel_idx]}"; echo ""; echo -e "  ${BOLD}Selected:${NC} ${GREEN}${_sel_name}${NC}\n  ${DIM}File: ${_sel_file}${NC}\n  ${DIM}Examples: Ctrl+Option+G   Cmd+Shift+F5   Ctrl+Cmd+1  (Alt = Option, Meta = Cmd)${NC}"; local new_shortcut; read -r -p "  Keyboard shortcut (or 0 to cancel): " new_shortcut; if [[ "$new_shortcut" == "0" ]] || [[ -z "$new_shortcut" ]]; then continue; fi; local _mods="" _keytok="" _tok _lc _bad=0; local _old_ifs="$IFS"; IFS='+'; local -a _toks=( $(echo "$new_shortcut" | tr -d ' ') ); IFS="$_old_ifs"; local _n=${#_toks[@]} _i; for (( _i=0; _i<_n; _i++ )); do _tok="${_toks[$_i]}"; _lc="$(echo "$_tok" | tr 'A-Z' 'a-z')"; if [ "$_i" -eq $(( _n - 1 )) ]; then if [ "${#_tok}" -eq 1 ]; then _keytok="$_lc"; else _bad=1; fi; else case "$_lc" in cmd|command|meta|win|super) _mods="${_mods}@" ;; alt|option|opt)             _mods="${_mods}~" ;; ctrl|control)               _mods="${_mods}^" ;; shift)                      _mods="${_mods}\$" ;; *) _bad=1 ;; esac; fi; done; if [ "$_bad" -eq 1 ] || [ -z "$_mods" ] || [ -z "$_keytok" ]; then echo -e "\n${RED}Invalid shortcut. Use modifiers plus a single letter/digit key, e.g. Ctrl+Option+G.${NC}"; press_enter; continue; fi; local _keyeq="${_mods}${_keytok}"; local _display; _display="$(_dsk_mac_key_display "$_keyeq")"; local confirm_bind; read -r -p "  Apply ${_display} to ${_sel_name}? [Y/n]: " confirm_bind; [[ "$confirm_bind" =~ ^[Nn]$ ]] && continue; local _svc_name="Launch ${_sel_name}"; local _wf="$HOME/Library/Services/${_svc_name}.workflow"; local _esc_path; _esc_path="$(printf '%s' "$_sel_file" | sed -e 's/&/\&amp;/g' -e 's/</\&lt;/g' -e 's/>/\&gt;/g' -e "s/'/'\\\\''/g")"; local _esc_name; _esc_name="$(printf '%s' "$_svc_name" | sed -e 's/&/\&amp;/g' -e 's/</\&lt;/g' -e 's/>/\&gt;/g')"; mkdir -p "$_wf/Contents" || { echo -e "${RED}Cannot create ${_wf}${NC}"; press_enter; continue; }
cat > "$_wf/Contents/Info.plist" <<PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>NSServices</key>
	<array>
		<dict>
			<key>NSMenuItem</key>
			<dict>
				<key>default</key>
				<string>${_esc_name}</string>
			</dict>
			<key>NSMessage</key>
			<string>runWorkflowAsService</string>
		</dict>
	</array>
</dict>
</plist>
PLISTEOF
cat > "$_wf/Contents/document.wflow" <<WFEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>AMApplicationBuild</key><string>523</string>
	<key>AMApplicationVersion</key><string>2.10</string>
	<key>AMDocumentVersion</key><string>2</string>
	<key>actions</key>
	<array>
		<dict>
			<key>action</key>
			<dict>
				<key>AMAccepts</key>
				<dict>
					<key>Container</key><string>List</string>
					<key>Optional</key><true/>
					<key>Types</key><array><string>com.apple.cocoa.string</string></array>
				</dict>
				<key>AMActionVersion</key><string>2.0.3</string>
				<key>AMApplication</key><array><string>Automator</string></array>
				<key>AMParameterProperties</key>
				<dict>
					<key>COMMAND_STRING</key><dict/>
					<key>CheckedForUserDefaultShell</key><dict/>
					<key>inputMethod</key><dict/>
					<key>shell</key><dict/>
					<key>source</key><dict/>
				</dict>
				<key>AMProvides</key>
				<dict>
					<key>Container</key><string>List</string>
					<key>Types</key><array><string>com.apple.cocoa.string</string></array>
				</dict>
				<key>ActionBundlePath</key><string>/System/Library/Automator/Run Shell Script.action</string>
				<key>ActionName</key><string>Run Shell Script</string>
				<key>ActionParameters</key>
				<dict>
					<key>COMMAND_STRING</key><string>open '${_esc_path}'</string>
					<key>CheckedForUserDefaultShell</key><true/>
					<key>inputMethod</key><integer>1</integer>
					<key>shell</key><string>/bin/bash</string>
					<key>source</key><string></string>
				</dict>
				<key>BundleIdentifier</key><string>com.apple.RunShellScript</string>
				<key>CFBundleVersion</key><string>2.0.3</string>
				<key>Class Name</key><string>RunShellScriptAction</string>
				<key>InputUUID</key><string>A1B2C3D4-0000-4000-8000-000000000001</string>
				<key>OutputUUID</key><string>A1B2C3D4-0000-4000-8000-000000000002</string>
				<key>UUID</key><string>A1B2C3D4-0000-4000-8000-000000000003</string>
				<key>arguments</key><dict/>
			</dict>
		</dict>
	</array>
	<key>connectors</key><dict/>
	<key>workflowMetaData</key>
	<dict>
		<key>serviceInputTypeIdentifier</key><string>com.apple.Automator.nothing</string>
		<key>serviceOutputTypeIdentifier</key><string>com.apple.Automator.nothing</string>
		<key>serviceProcessesInput</key><integer>0</integer>
		<key>workflowTypeIdentifier</key><string>com.apple.Automator.servicesMenu</string>
	</dict>
</dict>
</plist>
WFEOF
local _pbs_key="(null) - ${_svc_name} - runWorkflowAsService"; if defaults write pbs NSServicesStatus -dict-add "\"${_pbs_key}\"" "{ enabled_context_menu = 0; enabled_services_menu = 1; key_equivalent = \"${_keyeq}\"; presentation_modes = { ContextMenu = 0; ServicesMenu = 1; }; }" 2>/dev/null; then /System/Library/CoreServices/pbs -update &>/dev/null || true; echo -e "\n${GREEN}✔  Quick Action created: ${BOLD}${_wf}${NC}\n${GREEN}✔  Keyboard shortcut set: ${BOLD}${_display}${NC}\n  ${DIM}If it doesn't fire, check System Settings → Keyboard → Keyboard Shortcuts → Services → General,${NC}\n  ${DIM}or log out/in. Service shortcuts only fire inside apps that expose a Services menu.${NC}"; shortcut_existing_keys[$_sel_idx]="$_display"; else echo -e "\n${RED}Failed to register the keyboard shortcut with macOS (defaults write pbs).${NC}"; fi; press_enter; done
}
_run_desktop_shortcut_manual() {
if _dsk_is_windows; then _run_desktop_shortcut_manual_windows; return 0; fi; if _dsk_is_mac; then _run_desktop_shortcut_manual_mac; return 0; fi; local -a desktop_paths=(); local -a search_dirs=("$HOME/Desktop/DESKTOP" "$HOME/Desktop" "$HOME/.local/share/applications"); for _dir in "${search_dirs[@]}"; do if [ -d "$_dir" ]; then while IFS= read -r -d '' _f; do desktop_paths+=("$_f"); done < <(find "$_dir" -maxdepth 1 -name "*.desktop" -print0 2>/dev/null | sort -z); fi; done; if [ ${#desktop_paths[@]} -eq 0 ]; then echo -e "\n${RED}No .desktop shortcuts found in standard locations.${NC}\n${DIM}Searched: ${search_dirs[*]}${NC}"; press_enter; return 0; fi; local -a shortcut_names=(); local -a shortcut_files=(); local -a shortcut_comments=(); local -a shortcut_categories=(); for _f in "${desktop_paths[@]}"; do local _name="" _comment="" _cats="" _type="" _k _v; while IFS='=' read -r _k _v; do case "$_k" in Name) [ -z "$_name" ] && _name="$_v" ;; Comment) [ -z "$_comment" ] && _comment="$_v" ;; Categories) [ -z "$_cats" ] && _cats="$_v" ;; Type) [ -z "$_type" ] && _type="$_v" ;; esac; done < "$_f"; [ -z "$_type" ] || [ "$_type" = "Application" ] || continue; [ -z "$_name" ] && { _name="${_f##*/}"; _name="${_name%.desktop}"; }; shortcut_names+=("$_name"); shortcut_files+=("$_f"); shortcut_comments+=("$_comment"); shortcut_categories+=("$_cats"); done; if [ ${#shortcut_names[@]} -eq 0 ]; then echo -e "\n${RED}No valid Application .desktop shortcuts found.${NC}"; press_enter; return 0; fi
_cat_emoji() {
local cats="$1"; case "$cats" in *Game*)                      echo "🎮" ;; *AudioVideo*|*Audio*|*Music*) echo "🎵" ;; *AI*)                        echo "🤖" ;; *Development*)               echo "🛠️ " ;; *Network*)                   echo "🌐" ;; *System*|*Settings*)         echo "⚙️ " ;; *Graphics*|*Screensaver*)    echo "🎨" ;; *Utility*)                   echo "🔧" ;; *)                           echo "📌" ;; esac
}
while true; do clear; echo -e "${BOLD}${MAGENTA}${S70}==${NC}\n${BOLD}${MAGENTA}   🖥️  RUN ANY DESKTOP SHORTCUT MANUALLY — KDE Plasma (kioclient)     ${NC}\n${BOLD}${MAGENTA}${S70}==${NC}\n  ${DIM}All available Desktop Shortcuts are listed below.${NC}\n  ${DIM}Select a number to launch the shortcut. Press 0 to go back.${NC}"; echo ""; local _i=1; local idx; for (( idx=0; idx<${#shortcut_names[@]}; idx++ )); do local _name="${shortcut_names[$idx]}"; local _comment="${shortcut_comments[$idx]}"; local _cats="${shortcut_categories[$idx]}"; local _emoji; _emoji="$(_cat_emoji "$_cats")"; local _idx_str; printf -v _idx_str "%3d" "$_i"; if [ -n "$_comment" ]; then echo -e "  ${BOLD}${CYAN}${_idx_str})${NC} ${_emoji} ${BOLD}${_name}${NC}\n       ${DIM}${_comment}${NC}"; else echo -e "  ${BOLD}${CYAN}${_idx_str})${NC} ${_emoji} ${BOLD}${_name}${NC}"; fi; _i=$(( _i + 1 )); done; echo ""; echo -e "  ${BOLD}${CYAN}  0)${NC} Return to Desktop Shortcuts Menu"; echo ""; read -r -p "Enter shortcut number to launch [0-$(( ${#shortcut_names[@]} ))]: " sc_choice; if [[ "$sc_choice" == "0" ]] || [[ "$sc_choice" =~ ^[qQ]$ ]]; then return 0; fi; if ! [[ "$sc_choice" =~ ^[0-9]+$ ]] || [ "$sc_choice" -lt 1 ] || [ "$sc_choice" -gt "${#shortcut_names[@]}" ]; then echo -e "\n${RED}Invalid selection — please enter a number between 1 and ${#shortcut_names[@]}.${NC}"; sleep 1.5; continue; fi; local _sel_idx=$(( sc_choice - 1 )); local _sel_name="${shortcut_names[$_sel_idx]}"; local _sel_file="${shortcut_files[$_sel_idx]}"; echo ""; echo -e "${BOLD}${YELLOW}▶  Launching: ${GREEN}${_sel_name}${NC}\n   ${DIM}File: ${_sel_file}${NC}"; local _launcher_type=""; local _launcher_bin=""; if command -v gio &>/dev/null; then _launcher_type="gio"; _launcher_bin="gio"; elif command -v gtk-launch &>/dev/null; then _launcher_type="gtk-launch"; _launcher_bin="gtk-launch"; elif command -v kioclient &>/dev/null; then _launcher_type="kioclient"; _launcher_bin="kioclient"; elif command -v kioclient6 &>/dev/null; then _launcher_type="kioclient"; _launcher_bin="kioclient6"; elif command -v kioclient5 &>/dev/null; then _launcher_type="kioclient"; _launcher_bin="kioclient5"; else _launcher_type="direct"; fi; case "$_launcher_type" in gio) echo -e "   ${DIM}Command: gio launch \"${_sel_file}\"${NC}"; echo ""; gio launch "$_sel_file" &>/dev/null &
disown ;; gtk-launch) local _desktop_base; _desktop_base="$(basename "$_sel_file" .desktop)"; echo -e "   ${DIM}Command: gtk-launch \"${_desktop_base}\"${NC}"; echo ""; gtk-launch "$_desktop_base" &>/dev/null &
disown ;; kioclient) echo -e "   ${DIM}Command: ${_launcher_bin} exec \"${_sel_file}\"${NC}"; echo ""; "$_launcher_bin" exec "$_sel_file" &>/dev/null &
disown ;; direct) local _exec_cmd; _exec_cmd="$(grep -m1 '^Exec=' "$_sel_file" | cut -d= -f2- | sed -E 's/%[uUfFiIck]//g' | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"; if [ -n "$_exec_cmd" ]; then echo -e "   ${DIM}Command: ${_exec_cmd}${NC}"; echo ""; nohup bash -c "$_exec_cmd" >/dev/null 2>&1 &
disown; else echo -e "${RED}Error: Neither gio, gtk-launch, nor kioclient is installed, and could not parse Exec line.${NC}\n${DIM}Install a desktop launcher via: sudo dnf install glib2 kioclient  OR  sudo apt install libglib2.0-bin kio${NC}"; press_enter; continue; fi; ;; esac; echo -e "${GREEN}✔  Shortcut launched successfully!${NC}\n${DIM}The application is opening. When you are done, return here to launch another.${NC}"; echo ""; press_enter; done
}
_bind_desktop_shortcut_keyboard() {
_dsk_is_windows && { _bind_desktop_shortcut_keyboard_windows; return 0; }; _dsk_is_mac && { _bind_desktop_shortcut_keyboard_mac; return 0; }; local -a shortcut_names=() shortcut_files=() shortcut_comments=() shortcut_categories=() shortcut_existing_keys=(); local f line k v name comm cats type key; shopt -s nullglob; local files=("$HOME/Desktop/DESKTOP"/*.desktop "$HOME/Desktop"/*.desktop "$HOME/.local/share/applications"/*.desktop); shopt -u nullglob; for f in "${files[@]}"; do [ -f "$f" ] || continue; name="" comm="" cats="" type="" key=""; while IFS='=' read -r k v || [ -n "$k" ]; do case "$k" in Name)                 [ -z "$name" ] && name="$v" ;; Comment)              [ -z "$comm" ] && comm="$v" ;; Categories)           [ -z "$cats" ] && cats="$v" ;; Type)                 [ -z "$type" ] && type="$v" ;; X-KDE-Shortcuts)      [ -z "$key" ]  && key="$v" ;; esac; done < "$f"; [ -n "$type" ] && [ "$type" != "Application" ] && continue; [ -z "$name" ] && name="${f##*/}" && name="${name%.desktop}"; shortcut_names+=("$name"); shortcut_files+=("$f"); shortcut_comments+=("$comm"); shortcut_categories+=("$cats"); shortcut_existing_keys+=("$key"); done; local total=${#shortcut_names[@]}; if [ "$total" -eq 0 ]; then echo -e "\n${RED}No valid Application .desktop shortcuts found.${NC}"; press_enter; return 0; fi
_cat_emoji_bind() {
case "$1" in *Game*)                       echo "🎮" ;; *AudioVideo*|*Audio*|*Music*) echo "🎵" ;; *AI*)                         echo "🤖" ;; *Development*)                echo "🛠️ " ;; *Network*)                    echo "🌐" ;; *System*|*Settings*)          echo "⚙️ " ;; *Graphics*|*Screensaver*)     echo "🎨" ;; *Utility*)                    echo "🔧" ;; *)                            echo "📌" ;; esac
}
while true; do clear; echo -e "${BOLD}${MAGENTA}${S70}==\n   ⌨️  GENERATE KEYBOARD SHORTCUT FOR DESKTOP SHORTCUT (KDE Plasma)    \n${S70}==${NC}\n  ${DIM}Select a Desktop Shortcut and assign a global keyboard shortcut.\n  The shortcut will be registered in KDE Plasma and fire instantly.${NC}\n"; local i; for (( i=0; i<total; i++ )); do local badge=""; [ -n "${shortcut_existing_keys[i]}" ] && badge=" ${CYAN}[${shortcut_existing_keys[i]}]${NC}"; printf "  ${BOLD}${CYAN}%3d)${NC} %s ${BOLD}%s${NC}%b\n" "$((i + 1))" "$(_cat_emoji_bind "${shortcut_categories[i]}")" "${shortcut_names[i]}" "$badge"; [ -n "${shortcut_comments[i]}" ] && echo -e "       ${DIM}${shortcut_comments[i]}${NC}"; done; echo -e "\n  ${BOLD}${CYAN}  0)${NC} Return to Desktop Shortcuts Menu\n"; read -r -p "Enter shortcut number to bind [0-$total]: " sc_choice; [[ "$sc_choice" =~ ^(0|[qQ])$ ]] && return 0; if ! [[ "$sc_choice" =~ ^[0-9]+$ ]] || [ "$sc_choice" -lt 1 ] || [ "$sc_choice" -gt "$total" ]; then echo -e "\n${RED}Invalid selection.${NC}"; sleep 1; continue; fi; local sel=$(( sc_choice - 1 )); local sel_name="${shortcut_names[sel]}"; local sel_file="${shortcut_files[sel]}"; local sel_comm="${shortcut_comments[sel]}"; local cur_key="${shortcut_existing_keys[sel]}"; clear; echo -e "${BOLD}${MAGENTA}${S70}==\n   ⌨️  ASSIGN KEYBOARD SHORTCUT — ${sel_name}\n${S70}==${NC}\n\n  ${BOLD}Selected shortcut:${NC} ${GREEN}${sel_name}${NC}"; [ -n "$sel_comm" ] && echo -e "  ${DIM}${sel_comm}${NC}"; echo -e "  ${DIM}File: ${sel_file}${NC}\n"; [ -n "$cur_key" ] && echo -e "  ${YELLOW}⚠️  Currently bound to: ${BOLD}${cur_key}${NC}\n  ${DIM}  Entering a new shortcut will replace the existing binding.${NC}\n"; echo -e "  ${BOLD}${CYAN}Enter a keyboard shortcut combination:${NC}\n  ${DIM}  Examples: Ctrl+Alt+G, Meta+Shift+A, Ctrl+Alt+Return\n  Modifiers: Ctrl, Alt, Meta, Shift | Keys: A-Z, F1-F12, Return, Space${NC}\n"; local kglobal_cfg="$HOME/.config/kglobalshortcutsrc"; if [ -f "$kglobal_cfg" ]; then echo -e "  ${BOLD}${CYAN}Known taken shortcuts on your system:${NC}"
awk -F'=' '
                /^[A-Za-z].*=(Ctrl\+Alt\+|Meta\+[A-Z])/ && !/^_k_/ {
                    split($2, a, ",");
                    gsub(/_/, " ", $1);
                    printf "  \033[2m    %-35s → %s\033[0m\n", $1, a[1];
                    if (++count == 8) exit;
                }' "$kglobal_cfg" 2>/dev/null
echo ""; fi; local new_shortcut; read -r -p "  Keyboard shortcut (or 0 to cancel): " new_shortcut; [[ -z "$new_shortcut" || "$new_shortcut" == "0" ]] && continue; local norm_shortcut="${new_shortcut// /}"; local s_low="${norm_shortcut,,}"; norm_shortcut=$(sed -E -e 's/ctrl/Ctrl/gi' -e 's/alt/Alt/gi' -e 's/meta/Meta/gi' -e 's/shift/Shift/gi' -e 's/return/Return/gi' -e 's/space/Space/gi' -e 's/tab/Tab/gi' -e 's/insert/Insert/gi' -e 's/delete/Delete/gi' -e 's/escape/Escape/gi' -e 's/home/Home/gi' -e 's/end/End/gi' <<< "$norm_shortcut"); echo -e "\n  ${BOLD}Confirming shortcut:${NC} ${CYAN}${BOLD}${norm_shortcut}${NC}\n  ${BOLD}For application:${NC}   ${GREEN}${sel_name}${NC}\n"; read -r -p "  Apply this keyboard shortcut? [Y/n]: " confirm_bind; [[ "$confirm_bind" =~ ^[Nn]$ ]] && continue; local target_desktop="$HOME/.local/share/applications/${sel_file##*/}"; local dsk_base="${sel_file##*/}"; local action="${dsk_base%.desktop}"; mkdir -p "$HOME/.local/share/applications"; [ "$sel_file" != "$target_desktop" ] && cp -f "$sel_file" "$target_desktop" 2>/dev/null
awk -v s="$norm_shortcut" '
            !/^X-KDE-(GlobalAccel-CommandShortcut|Shortcuts)=/ { print }
            END {
                print "X-KDE-GlobalAccel-CommandShortcut=true";
                print "X-KDE-Shortcuts=" s;
            }' "$target_desktop" > "${target_desktop}.tmp" && mv -f "${target_desktop}.tmp" "$target_desktop"
if [ -f "$kglobal_cfg" ]; then
awk -v act="$action" -v app="$sel_name" -v sc="$norm_shortcut" '
                BEGIN { in_sec = 0; written = 0 }
                $0 ~ ("^\\[services\\]\\[" act "\\.desktop\\]") { in_sec = 1; next }
                in_sec && /^\[/ { in_sec = 0 }
                !in_sec { print }
                END {
                    printf "\n[services][%s.desktop]\n_k_friendly_name=%s\n%s=%s,%s,Launch %s\n", act, app, act, sc, sc, app;
                }' "$kglobal_cfg" > "${kglobal_cfg}.tmp" && mv -f "${kglobal_cfg}.tmp" "$kglobal_cfg"
else printf "[services][%s.desktop]\n_k_friendly_name=%s\n%s=%s,%s,Launch %s\n\n" "$action" "$sel_name" "$action" "$norm_shortcut" "$norm_shortcut" "$sel_name" >> "$kglobal_cfg"; fi; command -v qdbus &>/dev/null && qdbus org.kde.kglobalaccel /kglobalaccel org.kde.KGlobalAccel.reloadConfig &>/dev/null || true; command -v kbuildsycoca6 &>/dev/null && { kbuildsycoca6 --noincremental &>/dev/null & disown; } || command -v kbuildsycoca5 &>/dev/null && { kbuildsycoca5 --noincremental &>/dev/null & disown; }; clear; echo -e "${BOLD}${MAGENTA}${S70}==\n${GREEN}   ✔  Keyboard Shortcut Successfully Bound!\n${MAGENTA}${S70}==${NC}\n\n  ${BOLD}Application:${NC}       ${GREEN}${BOLD}${sel_name}${NC}\n  ${BOLD}Keyboard Shortcut:${NC} ${CYAN}${BOLD}${norm_shortcut}${NC}\n  ${BOLD}Desktop File:${NC}      ${DIM}${target_desktop}${NC}\n"; press_enter; shortcut_existing_keys[sel]="$norm_shortcut"; done
}
manage_visual_media_suite() {
local opts=("1|Visual, Video & Art Launchers Suite|(MP_Liquid_Visualizer 3D Vulkan, NFT Videos, GIMP, Electric Sheep, GeeXLab)" "2|Launch MP_Liquid_Visualizer — 3D Vulkan Visualizer|(1400x1400 Fixed Borderless • Cosmic Dreamworlds / Orbital Void Reflux)" "3|Select MP_Liquid_Visualizer Preset|(Cosmic Dreamworlds / Orbital Void Reflux)" "4|Cut or Split Video File (.mp4 / .mkv)|(Cut_Video.sh / Split_Video_File.sh)" "5|Convert Cover Art & Resize / Byte Target|(1MB Podcast, WebP/JPG/PNG, Sizes)" "6|View Cover Art by Mix Number|(External Viewer)" "7|Procedural Gradient .PPM Cover Art Generator|(Netpbm P6 Binary, Palettes)" "8|Synchronized Mix-Video Companion Player Daemon|(Auto-play Video on Mix Start, Close on Stop)" "9|Download YouTube Videos & Shorts in 1080p|(Single URL, 1/3/6 Mo, All Videos/Shorts)" "10|Play Startup Loader Video (MP_loader.mp4)|(Test or play startup intro video)" "0|Return to Main Menu|(or Esc / q)"); while true; do run_interactive_submenu "VISUAL MEDIA, COVER ART & COMPANION VIDEO SUITE" "" opts 0; case "$REPLY" in 1) manage_visual_media_launchers ;; 2|z|Z|visualizer|liquid-visualizer) launch_mp_liquid_visualizer ;; 3|preset|presets) manage_mp_liquid_visualizer_presets ;; 4) manage_video_cut_and_split ;; 5) manage_cover_converter ;; 6) view_cover; press_enter ;; 7) generate_ppm_cover_menu ;; 8) manage_sync_video_companion_menu ;; 9) run_sub_script "MP_YouTube_Channel_Downloader.sh"; press_enter ;; 10) display_startup_loader_video 1 ;; 0|[qQ]|[eE][xX][iI][tT]|ESC) return 0 ;; *) echo -e "\n${RED}Invalid option!${NC}"; sleep 1 ;; esac; done
}
manage_promo_and_syndication() {
local opts=("1|Promotional & Publisher Outreach Emails|(Promoters, Publishers, Radio, Labels)" "2|Mix Publishing Schedule & Multi-Platform Syndication|(Apple Podcasts, Spotify, YouTube, SoundCloud, RSS, iCal)" "3|Go Shopping for New Music|(Beatport, Apple Music & Bandcamp Tabs)" "0|Return to Main Menu|(or Esc / q)"); while true; do run_interactive_submenu "PROMOTIONAL OUTREACH, SYNDICATION & SHOPPING" "" opts 0; case "$REPLY" in 1) manage_promo_outreach ;; 2) manage_publishing_schedule ;; 3) shop_for_new_music_menu ;; 0|[qQ]|[eE][xX][iI][tT]|ESC) return 0 ;; *) echo -e "\n${RED}Invalid option!${NC}"; sleep 1 ;; esac; done
}
manage_congen() {
local b; for b in "$SCRIPT_DIR/Congen/Congen" "$SCRIPT_DIR/congen" "./congen"; do if [ -x "$b" ]; then "$b" "$@"; return 0; fi; done; echo -e "\n${RED}Error: Congen executable not found!${NC}"; press_enter
}
manage_network_and_internet() {
local opts=("1|Manage Network Services|(SSH, Samba, FTP - Start, Stop, Restart All)" "2|Congen - KDE Connect Commands Generator & Remote Control|(Mobile Phone Commands)" "3|Block Internet Access|(LAN Only - block-internet)" "4|Restore / Unblock Internet Access|(unblock-internet)" "5|Studio & DJ Booth Mobile Web Companion Server|(Phone & Tablet browser remote on port 8888)" "0|Return to Main Menu|(or Esc / q)"); while true; do run_interactive_submenu "NETWORK SERVICES, CONGEN & INTERNET ACCESS CONTROL" "" opts 0; case "$REPLY" in 1) manage_network_services ;; 2) manage_congen ;; 3) block_internet ;; 4) unblock_internet ;; 5) echo -e "\n${BOLD}${BLUE}=== LAUNCHING STUDIO & DJ BOOTH MOBILE WEB COMPANION ===${NC}\n"; launch_in_terminal "DJ Booth Web Companion" "CURRENT_THEME='$CURRENT_THEME' python3 '$SCRIPT_DIR/scripts/mix_web_companion.py' --theme '$CURRENT_THEME'" "window"; press_enter; ;; 0|[qQ]|[eE][xX][iI][tT]|ESC) return 0 ;; *) echo -e "\n${RED}Invalid option!${NC}"; sleep 1 ;; esac; done
}
_m_loop() {
local title="$1" sub="$2"; shift 2; local -a opts=("$@"); while true; do run_interactive_submenu "$title" "$sub" opts 0; case "$REPLY" in 0|[qQ]|[eE][xX][iI][tT]|ESC) return 0 ;; " ") toggle_mp_audio_player ;; [mM]) launch_mp_audio_player_window ;; [lL]) launch_mp_audio_player_liquid_glass ;; [zZ]) launch_mp_liquid_visualizer ;; K) pkill -9 -f "MP_Audio_Player" 2>/dev/null || true; rm -f "${HOME}/.config/mix-manager/mp_player.pid" "${HOME}/.config/mix-manager/mp_audio_player.port" "${HOME}/.config/mix-manager/mp_audio_player.sock" 2>/dev/null || true; _CACHED_PLAYER_CHECK_TIME=0; _CACHED_PLAYER_ACTIVE_RES=1; MP_PLAYER_RUNNING=0; MP_PLAYER_STATE="stopped" ;; *) local act="${_MENU_ACT[$REPLY]:-}"; if [[ -n "$act" ]]; then eval "$act"; else printf '\n%bInvalid option!%b\n' "${RED:-}" "${NC:-}"; sleep 1; fi; ;; esac; done
}
manage_desktop_and_display() {
local d1="Switch Desktop to Plasma Wayland" d1_i="(HDR Gaming on Hisense & Steam BPM)"; local d2="Switch Desktop to Plasma X11" d2_i="(Standard Workstation)"; local c1="switch_to_wayland" c2="switch_to_x11"; case "$OS_TYPE" in macos) d1="Open macOS Display Settings"; d1_i="(Displays, Arrangement & HDR)"; d2="Open macOS Audio MIDI Setup"; d2_i="(Sample Rates & Output Devices)"; c1='open /System/Library/PreferencePanes/Displays.prefPane 2>/dev/null || open "x-apple.systempreferences:com.apple.Displays-Settings.extension" 2>/dev/null || true'; c2='open -a "Audio MIDI Setup" 2>/dev/null || true' ;; windows|wsl) d1="Open Windows Display Settings"; d1_i="(ms-settings:display - HDR & Scale)"; d2="Open Windows Sound Settings"; d2_i="(control.exe mmsys.cpl)"; c1='cmd.exe /c start ms-settings:display 2>/dev/null || true'; c2='cmd.exe /c start control.exe mmsys.cpl 2>/dev/null || true' ;; esac; local fs_i="(Currently Windowed - switch to Fullscreen)"; (( ${_IS_FULLSCREEN:-0} == 1 )) && fs_i="(Currently Fullscreen - switch to Windowed)"; local -A _MENU_ACT=([1]="$c1" [2]="$c2" [3]="close_all_desktop_apps" [4]="toggle_manager_fullscreen"); _m_loop "DESKTOP DISPLAY SETTINGS & APP CONTROL" "" "1|${d1}|${d1_i}" "2|${d2}|${d2_i}" "3|Close All Desktop Applications|(Keep Manager Open)" "4|Toggle Fullscreen / Windowed Mode|${fs_i}" "0|Return to Main Menu|(or Esc / q)"
}
manage_ai_and_servers() {
local olm="(ollama serve in distrobox, Chat, Models, Logs :11434)"; local wui="(Open Web UI Web Chat AI Harness, Service, Browser :42004)"; [[ "$OS_TYPE" == "windows" ]] && {
olm="(ollama serve on Windows, Chat, Models, Logs :11434)"; wui="(Open Web UI Web Chat AI Harness on Windows, Browser :8080)"
}
local -A _MENU_ACT=([1]="manage_ai_models" [2]="manage_ollama" [3]="manage_open_webui" [open-webui]="manage_open_webui" [openwebui]="manage_open_webui" [webui]="manage_open_webui" [web-chat]="manage_open_webui" [4]="manage_harmony_agent" [harmony]="manage_harmony_agent" [mp-harmony]="manage_harmony_agent" [harmony-agent]="manage_harmony_agent" [ha]="manage_harmony_agent" [5]="manage_dsh_mobile" [6]="manage_wan2gp" [7]="manage_beszel" [8]="run_wan2gp_infinite_talker" [inftlk]="run_wan2gp_infinite_talker" [infinite-talk]="run_wan2gp_infinite_talker" [infinite-talker]="run_wan2gp_infinite_talker" [stephen-hawking]="run_wan2gp_infinite_talker"); _m_loop "AI ASSISTANT & LOCAL LLM SERVERS SUITE" "" "1|Launch AI Assistant / Models|(Claude Opus, Claude Sonnet, GPT-OSS, Gemini, Ollama, DeepSeek)" "2|Manage Ollama Server|${olm}" "3|Manage Open WebUI Server & Web Chat|${wui}" "4|Manage MP Harmony AI Agent|(Autonomous Engineering Engine & Voice Bridge :11435)" "5|Manage DeepSeek Harness Server|(dsh-mobile - Start, Stop, Mobile Web UI :3080)" "6|Manage WAN2GP Server|(Start, Stop, Restart in Profile 2 or 4.5, Update)" "7|Manage Beszel Server & Monitoring Agent|(Start Hub & Agent, Status, Dashboard :8090)" "8|MP Infinite Talker AI Video Suite|(Stephen Hawking Video Generation, Voice Cloning & Batch Suite)" "0|Return to Main Menu|(or Esc / q)"
}
manage_motd_and_tools() {
local -A _MENU_ACT=([1]="manage_system_motd_menu" [2]="burn_iso_to_usb"); _m_loop "MOTD BANNER MANAGER & SYSTEM UTILITIES" "" "1|Dynamic System MOTD Banner Manager|(Last 3 Mixes, Date/Time, Size, Format & Specs)" "2|Burn ISO Image to USB Drive|(dd / diskutil with safety checks)" "0|Return to Main Menu|(or Esc / q)"
}
manage_settings_and_system() {
local rb="systemctl reboot with confirmation"; case "$OS_TYPE" in macos) rb="macOS restart with confirmation" ;; windows|wsl) rb="Windows restart with confirmation" ;; freebsd) rb="FreeBSD restart with confirmation" ;; esac; local -A _MENU_ACT=([1]="manage_themes" [2]="manage_installation_and_config" [3]="configure_daily_reports_settings" [4]="manage_mix_reports_menu" [5]="run_bash_cli" [6]="reboot_system" [7]="configure_liquid_glass_backend"); _m_loop "MANAGER SETTINGS, THEMES & SYSTEM SHELL" "" "1|Manager Themes & Color Palette Switcher|(19 Themes: Dreamworlds, Liquid Glass Skins, Cosmic Supernova...)" "2|Manage Installation & Configuration|(Migrate Path, Backup, Export & Import Config)" "3|Automated Daily Reports & Continuous Telemetry Settings|(Schedule Time, On/Off, Catch-Up)" "4|Daily Mix Reports, Telemetry & Predictive Analytics Suite|(PDF Reports, Multi-Archive Stats, Math Models)" "5|Run Bash CLI Commands|(Interactive Shell & Direct Runner)" "6|Reboot System|(${rb})" "7|Configure Liquid Glass Player Backend|(OpenGL [Default • AMD Radeon/Intel/Older Cards] or Vulkan)" "0|Return to Main Menu|(or Esc / q)"
}
render_main_header() {
local cur_box_w="${1:-}" _hdr_cap; _set_menu_box_width _hdr_cap "${_TERM_COLS:-80}"; [[ -z "$cur_box_w" || "$cur_box_w" -gt "$_hdr_cap" ]] && cur_box_w="$_hdr_cap"; (( cur_box_w < 1 )) && cur_box_w=1;
local inner_w=$(( cur_box_w - 2 )) text_w=$(( cur_box_w - 4 ))
local h_border; printf -v h_border '%*s' "$inner_w" ''; h_border="${h_border// /─}";
local title="MP Mix Archive Manager (v${VERSION#v})";
local pad_left=$(( (text_w - ${#title}) / 2 ))
(( pad_left < 0 )) && pad_left=0
local pad_right=$(( text_w - ${#title} - pad_left ))
(( pad_right < 0 )) && pad_right=0
local sp_left="" sp_right=""
(( pad_left > 0 )) && printf -v sp_left '%*s' "$pad_left" ''
(( pad_right > 0 )) && printf -v sp_right '%*s' "$pad_right" ''
[[ -z "${_CACHED_OS_BADGE:-}" ]] && get_os_badge &>/dev/null;
[[ -z "${_CACHED_PERF_DISPLAY:-}" ]] && get_system_perf_stats >/dev/null;
local net="${GREEN}Online${NC}";
[[ "${_CACHED_INTERNET_STATUS:-online}" == "offline" ]] && net="${YELLOW}Offline (LAN Only)${NC}";
local b_mag="${BOLD}${MAGENTA}" b_blue="${BOLD}${BLUE}" b_cyan="${BOLD}${CYAN}"
local hdr="  ${b_mag}╭${h_border}╮${NC}
  ${b_mag}│${NC} ${sp_left}${b_mag}${title}${NC}${sp_right} ${b_mag}│${NC}
  ${b_mag}╰${h_border}╯${NC}
  ${_CACHED_OS_BADGE:-}  ${b_blue}│${NC}  ${b_cyan}🔄 OS Updates:${NC} ${_CACHED_OS_UPDATE_STATUS:-${DIM}checking...${NC}}  ${b_blue}│${NC}  ${b_cyan}🌐 Network:${NC} ${net}  ${b_blue}│${NC}  ${b_cyan}🐚 Shell:${NC} Bash ${BASH_VERSION%%(*}"
[[ -n "${_CACHED_CLOUD_STATUS:-}" ]]       && hdr+=$'\n  '"${_CACHED_CLOUD_STATUS}"; [[ -n "${_CACHED_PERF_DISPLAY:-}" ]]        && hdr+=$'\n'"${_CACHED_PERF_DISPLAY}"; [[ -n "${_CACHED_AUDIO_IFACE_DISPLAY:-}" ]] && hdr+=$'\n'"${_CACHED_AUDIO_IFACE_DISPLAY}"; if (( _TERM_LINES >= 38 )); then [[ -n "${STARTUP_AUTOPLAY_NOTICE:-}" ]] && hdr+=$'\n  '"${BOLD}${GREEN}${STARTUP_AUTOPLAY_NOTICE}${NC}"; [[ -n "${STARTUP_SPEK_NOTICE:-}" ]]     && hdr+=$'\n  '"${BOLD}${GREEN}${STARTUP_SPEK_NOTICE}${NC}"; if [[ "${WEATHER_ENABLED:-true}" == "true" && -n "${WEATHER_LOCATION:-}" && -n "${_CACHED_WEATHER_DISPLAY:-}" ]]; then hdr+=$'\n'"${_CACHED_WEATHER_DISPLAY}"; fi; if [[ "${PLANETS_ENABLED:-true}" == "true" && -n "${_CACHED_PLANETS_DISPLAY:-}" ]]; then hdr+=$'\n'"${_CACHED_PLANETS_DISPLAY}"; fi; [[ -n "${_CACHED_ALARM_CLOCK_STATUS:-}" ]] && hdr+=$'\n'"${_CACHED_ALARM_CLOCK_STATUS}"; if ! is_mix_archive_configured; then
hdr+=$'\n\n  '"${BOLD}${RED}⚠️  Please be advised you have not configured your Mix Archive Folder, Please use Option 16 or 13 to Configure this now.${NC}
  ${DIM}${YELLOW}(Currently using application root folder: ${SCRIPT_DIR}/MIX_ARCHIVE)${NC}"
fi; local _mf_cnt=0 _mf_f="$HOME/.config/mix-manager/music_folders.json"; [ -f "$_mf_f" ] && _mf_cnt=$(grep -c '"id":' "$_mf_f" 2>/dev/null || echo 0); if [ "${_mf_cnt:-0}" -eq 0 ]; then
hdr+=$'\n\n  '"${BOLD}${YELLOW}⚠️  Please be advised you have 0 MUSIC Folders configured. Please use Option 2 to configure your music library folders now.${NC}
  ${DIM}${YELLOW}(Support for local music libraries, external drives & network SMB shares)${NC}"
fi; local _s4_conn=0; if amidi -l 2>/dev/null | grep -qi "Traktor"; then _s4_conn=1; elif [ -e "/dev/snd/midiC0D0" ] && grep -qi "Traktor" /proc/asound/cards 2>/dev/null; then _s4_conn=1; fi; if [ "$_s4_conn" -eq 1 ] && [ "${TRAKTOR_S4_NOTIFIED:-false}" != "true" ] && [ ! -f "$HOME/.config/mix-manager/traktor_s4_notified.flag" ]; then
hdr+=$'\n\n  '"${BOLD}${GREEN}🎛️  Traktor Kontrol S4 Hardware MIDI Device Detected [hw:0,0]!${NC}
  ${BOLD}${CYAN}Please navigate to Option 19 (Studio Hardware & MIDI) to enable and configure Traktor Kontrol S4 MIDI Device Mapping Controls.${NC}
  ${DIM}${GREEN}(Control player transport, mixer, and pitch sliders directly from your S4 hardware)${NC}"
fi; if [[ -z "${_CACHED_STATS_CORE:-}" ]]; then load_header_cache 2>/dev/null || true
[[ -z "${_CACHED_STATS_CORE:-}" ]] && _CACHED_STATS_CORE="${b_blue}=== CURRENT STATUS & STATISTICS ===${NC}
  ${DIM}⚡ Loading archive statistics in background...${NC}"
fi; hdr+=$'\n\n'"${_CACHED_STATS_CORE}"; [[ -n "${_CACHED_NOW_PLAYING:-}" ]] && hdr+=$'\n'"${_CACHED_NOW_PLAYING}"; hdr+=$'\n'"${BLUE}===================================${NC}"; fi; get_manager_uptime >/dev/null; hdr+=$'\n  '"${_MANAGER_UPTIME_LINE}"; _RENDERED_MAIN_HEADER="$hdr"; printf '%b\n' "$_RENDERED_MAIN_HEADER"
}
run_deferred_startup() {
[ "${STARTUP_AUTOPLAY_EXECUTED:-0}" -eq 1 ] && return 0; STARTUP_AUTOPLAY_EXECUTED=1; ensure_manager_windowed; if [ "${AUTO_PLAY_ON_STARTUP:-true}" = "true" ]; then (execute_startup_autoplay &>/dev/null &); _AUTOPLAY_PID=$!; fi; if ! pgrep -f "MP_Audio_Player_Liquid_Glass" &>/dev/null; then (launch_mp_audio_player_liquid_glass &>/dev/null &); fi; _LAST_HDR_REFRESH_SPAWN="${EPOCHSECONDS:-$(date +%s 2>/dev/null || echo 0)}"; (refresh_header_cache_worker --force &>/dev/null &); if [ -f "$HOME/.config/mix-manager/scheduled_mixes.json" ] && grep -q '"status": "pending"' "$HOME/.config/mix-manager/scheduled_mixes.json" 2>/dev/null; then if [ -f "$SCRIPT_DIR/scripts/schedule_mix_playback.py" ]; then python3 "$SCRIPT_DIR/scripts/schedule_mix_playback.py" --ensure-daemon &>/dev/null &
elif [ -f "$SCRIPT_DIR/scripts/schedule_mix_playback.sh" ]; then "$SCRIPT_DIR/scripts/schedule_mix_playback.sh" --ensure-daemon &>/dev/null &
fi; fi
if [ -f "$SCRIPT_DIR/scripts/mp_scheduled_reporter.sh" ]; then
(bash "$SCRIPT_DIR/scripts/mp_scheduled_reporter.sh" --check-or-run &>/dev/null &)
(bash "$SCRIPT_DIR/scripts/mp_scheduled_reporter.sh" --daemon &>/dev/null &)
fi
if [ "${MIDI_CONTROL_ENABLED:-true}" = "true" ]; then
local _s4_py="$SCRIPT_DIR/scripts/traktor_s4_midi.py"; [ ! -f "$_s4_py" ] && _s4_py="$SCRIPT_DIR/traktor_s4_midi.py"; [ -f "$_s4_py" ] && (python3 "$_s4_py" --start &>/dev/null &)
fi
if [ "${OS_TYPE:-}" = "macos" ] || [ "${UNAME_S:-}" = "Darwin" ] || [[ "${OSTYPE:-}" == darwin* ]]; then
if pgrep -i -f "Traktor" &>/dev/null || (osascript -e 'application "Traktor" is running' 2>/dev/null | grep -qi "true"); then
local _t_mon=""; if [ -x "$SCRIPT_DIR/scripts/traktor_monitor.sh" ]; then _t_mon="$SCRIPT_DIR/scripts/traktor_monitor.sh"; elif [ -x "$SCRIPT_DIR/traktor_monitor.sh" ]; then _t_mon="$SCRIPT_DIR/traktor_monitor.sh"; elif [ -f "$SCRIPT_DIR/scripts/traktor_monitor.py" ]; then _t_mon="python3 \"$SCRIPT_DIR/scripts/traktor_monitor.py\""; elif [ -f "$PWD/scripts/traktor_monitor.py" ]; then _t_mon="python3 \"$PWD/scripts/traktor_monitor.py\""; elif command -v traktor-monitor &>/dev/null; then _t_mon="$(command -v traktor-monitor)"; fi; [ -n "$_t_mon" ] && launch_in_terminal "Traktor Live Monitor" "$_t_mon" "tab" &>/dev/null &
fi; fi
}
is_manager_already_open() {
local disp_sh="$SCRIPT_DIR/scripts/display_loader_video.sh"; [ ! -f "$disp_sh" ] && disp_sh="$PWD/scripts/display_loader_video.sh"; if [ -f "$disp_sh" ]; then source "$disp_sh"; is_manager_already_open "${1:-$$}"; return $?; fi; return 1
}
display_startup_loader_video() {
local disp_sh="$SCRIPT_DIR/scripts/display_loader_video.sh"; [ ! -f "$disp_sh" ] && disp_sh="$PWD/scripts/display_loader_video.sh"; if [ -f "$disp_sh" ]; then source "$disp_sh"; display_startup_loader_video "${1:-0}"; return $?; fi; return 0
}
ensure_liquid_glass_first_run_reward() {
    local rew_py="$SCRIPT_DIR/scripts/liquid_glass_reward.py"
    [ ! -f "$rew_py" ] && rew_py="$PWD/scripts/liquid_glass_reward.py"
    if [ -f "$rew_py" ]; then
        python3 "$rew_py" || true
    fi
}
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
MANAGER_MAIN_PID=$BASHPID
_cleanup_mix_manager_exit() {
    [ "${BASHPID:-$$}" -ne "${MANAGER_MAIN_PID:-$$}" ] && return 0
    exit_mix_manager
}
trap '_cleanup_mix_manager_exit' EXIT INT TERM HUP
display_startup_loader_video 0
ensure_liquid_glass_first_run_reward
_STOP_AUDIO_ON_EXIT=1; while true; do update_mp_bridge_menu "Main Console / Workstation Menu" "true"; update_terminal_geometry 0; _set_menu_box_width box_w "${_TERM_COLS:-80}"; main_header=""; main_opts=("SECTION|SECTION 1: MIX ARCHIVE WORKFLOW & INGESTION|" "0|Run Any Desktop Shortcuts|(Games, Audio, Files, Tools, AI Servers — Linux/Windows/macOS)" "1|Play DJ Mixes (MP Audio Player - Mix Archive Mode)|(Built-in Player, Custom Animated EQ, FLAC/WAV/MP3)" "2|Play Tracks from MUSIC Folders using MP Audio Player|(Music Library • Local Drives & SMB Shares • Add / Remove Folders)" "3|MP Audio Player (Liquid Glass Mode)|(Liquid glass window • OpenGL [Default - All GPUs] or Vulkan • light theme reflections)" "4|Run Mix Conversion|(FLAC, MP3, WAV, or YouTube MP4)" "5|Audio Conversion, EBU R128 Mastering & CUE Sheets|(WAV, MP3, AAC, LUFS, CUE, Splitter)" "6|Retrieve Unconverted WAVs from Archive|(MOVE_NOT_CONVERTED_WAVS.sh)" "7|Search & Import Mixes from Local Drives & SMB|(search_and_import_mixes.sh / import_new_mixes.sh)" "8|Rename a Mix and Associated Assets|(FLAC, Tracklist, Spek)" "9|Find & Remove Duplicate Audio Files / Mixes|(Exact Content & Episode Match)" "10|Export / Copy Mixes to Specified Path|(Audio, Covers, Tracklists, Spek)" "11|Audio Integrity, Bit-Rot Scrub & FLAC Verification|(SHA-256, Bit-Rot Daemon, Fake FLAC)" "12|Cloud & Remote Backup Suite|(Google Drive, iCloud, Dropbox, Custom Folder)" "13|Storage Management & Multiple Mix Archives Setup|(Drive Space, Rescan, Configure Archives)" "SECTION|SECTION 2: STUDIO AUDIO, PLAYBACK, METADATA & VIDEO|" "14|Tracklist Management, Scanning & Metadata Suite|(Browse, Search, Picard, HTML Index)" "15|Audio Players & Retro Playback Suite|(cliamp, Strawberry, VLC, Audacity, Haruna, Winamp...)" "16|Configure Mix Archive Storage Locations|(Primary & Multiple Archives)" "17|Custom Mix Playlists & Traktor History Suite|(.m3u, .m3u8, .xspf, Traktor 3 Playlists)" "18|Digital Audio Workstations (DAWs) & Mix Dispatch|(Reaper, Logic, FL Studio, Ardour, Traktor)" "19|Studio Hardware, Audio Interfaces & Master Volume Control|(PipeWire, ALSA, MIDI, Mute)" "20|Spectrogram Generation & Audio Frequency Analysis|(Single & Multiple Spek, SoX, Praat)" "21|Morning Alarm Clock & DJ Mix Playback Suite|(Steam Games, Wake-Up Mixes, Scheduler)" "22|YouTube Video Suite|(Generate 4K/1080p Videos, Download Videos & Shorts)" "23|Visual Media, Cover Art & Companion Video Suite|(Cut/Split Video, Converters, PPM, Launchers)" "24|Record Video of DJ Mix using GPU Screen Recorder (Linux)|(New Desktop Window)" "25|Listen to Your Top 5 Tracks Right Now (Pre-Selected - Special Option)|${_CACHED_TOP_5_BADGE:-[Ready]}" "SECTION|SECTION 3: SYSTEM, NETWORK, AI & SETTINGS|" "26|Live Session, Stream & Transfer Monitors Suite|(Tracklist, Traktor, Transfers, Uploads, Tasks)" "27|System & Hardware Process Monitors Suite|(btop, nvtop, top)" "28|MP Reporter Suite & Automated Reports Management|(Daily, Weekly, Monthly, Yearly, 12-Month Calendar & Email)" "29|Promotional Outreach, Syndication & Music Shopping|(Emails, RSS/Podcasts, Beatport/Bandcamp)" "30|Network Services, Congen & Internet Control|(SSH, Samba, FTP, Congen KDE Connect, Block Internet)" "31|Desktop Display Settings, Audio Routing & App Control|(Wayland/X11/macOS/Windows, Close Apps)" "32|Universal System Maintenance & Cleanup|(Drive space, OS Updates, Package Clean, Logs)" "33|Monitor System Processes and Bash Commands with System Info|(MP_Monitor_Bash.sh, new Terminal tab)" "34|AI Assistant & Local LLM Servers Suite|(Claude, GPT, Ollama, Open WebUI, MP Harmony, DeepSeek, WAN2GP, Beszel)" "35|Dynamic MOTD Banner Manager & Drive Burner|(Last 3 Mixes, Netpbm, ISO USB Burner)" "36|Manager Settings, Themes, Shell CLI & Reboot|(Themes, Migration, Bash CLI, Reboot)" "SEP|SEP|" "37|Exit Manager|(or q / exit)"); if [ -n "$CLI_INITIAL_ACTION" ]; then run_deferred_startup; choice="$CLI_INITIAL_ACTION"; CLI_INITIAL_ACTION=""; else run_interactive_submenu "" "$main_header" main_opts 0; choice="$REPLY"; fi; case $choice in 1|p|P|play|Play|player|mp_player|mp-player|mpplayer|mp|"Play DJ Mixes (MP Audio Player - Mix Archive Mode)"*|"Play Mix/Audio File (MP Audio Player)"*)
manage_mp_audio_player ;; 2|music|MUSIC|"Play Tracks from MUSIC Folders using MP Audio Player"*|"NEW Feature - Play Tracks from MUSIC Folders using MP Audio Player"*)
manage_music_folders_menu ;; 3|liquid|liquid-glass|glass|"MP Audio Player (Liquid Glass Mode)"*) launch_mp_audio_player_liquid_glass ;; liquid-config|glass-config|liquid-backend|glass-backend) configure_liquid_glass_backend ;; 4|convert|mix-conversion|flac-conversion|"Run Mix Conversion"*)
manage_mix_conversion ;; 5) manage_audio_conversion ;; 6) echo -e "\n${BOLD}${YELLOW}Retrieving unconverted WAV files...${NC}\n"; run_sub_script "MOVE_NOT_CONVERTED_WAVS.sh"; press_enter; ;; 7) manage_mix_search_and_import ;; 8) rename_mix; press_enter ;; 9) find_duplicate_audio_mixes; ;; 10) export_mixes_to_path ;; 11) manage_integrity_and_verification; ;; 12|backup|cloud-backup) manage_cloud_backup_suite ;; 13) play_sound_effect "storage"; manage_storage_and_archive_config ;;
14) manage_tracklist_suite; ;; 15|manage-audio-players|players) manage_audio_players ;; 16|config-archive|archive-dir|archive-folder) play_sound_effect "storage"; configure_mix_archive_folder ;; specs|metadata|inspect) inspect_playing_audio_file; ;; 17) manage_playlists_and_history ;; 18) manage_daws_suite; ;; 19|studio|midi|hardware) manage_studio_hardware_and_volume ;; s4|kontrol|kontrol-s4|traktor-s4|traktor_s4) manage_traktor_s4_midi_menu ;; 20) manage_spek_generation; ;; 21) manage_mix_scheduler ;; 22) generate_youtube_video; ;; 23|manage-visual-media|visual-launchers|video-launchers) manage_visual_media_suite ;; 24|gpu-screen-recorder|record-mix) launch_gpu_screen_recorder; press_enter ;; 25|top5|top-5|top_5|top|mystery|special) manage_top_5_tracks; ;; 26|manage-live-monitors|live-monitors) manage_live_monitors ;; 27|manage-process-monitors|process-monitors) manage_system_process_monitors; ;; 28|reports|daily-reports|report|mp-reporter|reporter) manage_mix_reports_menu ;; 29) manage_promo_and_syndication ;; 30) manage_network_and_internet; ;; 31) manage_desktop_and_display ;; 32) manage_system_maintenance; ;; 33|monitor|mp-monitor|bash-monitor) manage_process_and_bash_monitor ;; 34|ai|ai-servers|ai-suite|ai-models) manage_ai_and_servers; ;; infinite-talk*|inftlk*|stephen-hawking*|infinite-talker*) run_wan2gp_infinite_talker ;; open-webui|openwebui|webui|web-chat) manage_open_webui ;; harmony|mp-harmony|mp_harmony|harmony-agent|ha) manage_harmony_agent; ;; 35) manage_motd_and_tools ;; 36) manage_settings_and_system; ;; ESC) ;; 37|77|[qQ]|[eE][xX][iI][tT]) exit_mix_manager ;; audacious|audacious-launch) launch_audacious; ;; audacity|audacity-launch) launch_audacity ;; strawberry|strawberry-launch) launch_strawberry; ;; vlc|vlc-launch) launch_vlc ;; haruna|haruna-launch) launch_haruna; ;; kodi|kodi-launch) launch_kodi ;; gimp|gimp-launch) launch_gimp; ;; electricsheep|screensaver) launch_electricsheep ;; geexlab|geexlab-launch) launch_geexlab_demos; ;; btop|btop-launch) echo -e "\n${BOLD}${YELLOW}Launching btop Resource Monitor (Press 'q' to exit)...${NC}\n"; sleep 0.5; if command -v btop &>/dev/null; then _sync_btop_theme "$CURRENT_THEME"; btop; else echo -e "${RED}Error: btop command not found!${NC}"; press_enter; fi ;; nvtop|nvtop-launch) echo -e "\n${BOLD}${YELLOW}Launching nvtop GPU Monitor (Press 'q' to exit)...${NC}\n"; sleep 0.5; trap ':' INT; if command -v nvtop &>/dev/null; then nvtop; else echo -e "${RED}Error: nvtop command not found!${NC}"; press_enter; fi; trap 'exit_mix_manager' INT; ;; top|top-launch) echo -e "\n${BOLD}${YELLOW}Launching top Process Monitor (Press 'q' to exit)...${NC}\n"; sleep 0.5; trap ':' INT; if command -v top &>/dev/null; then top; else echo -e "${RED}Error: top command not found!${NC}"; press_enter; fi; trap 'exit_mix_manager' INT ;; split-flac|split_flac) split_flac_audio; press_enter ;; split-video|split_video|split-mp4|split_mp4) split_video_clip; press_enter ;; cut-video|cut_video) cut_video_clip; press_enter ;; beszel|beszel-start|beszel_start|beszel-hub|beszel-agent) manage_beszel; press_enter ;; ollama|ollama-serve|ollama_serve|ollama-start|ollama_start) manage_ollama; press_enter ;; dsh|dsh-mobile|dsh_mobile|dsh-start|dsh_start|dsh-web|dsh_web|deepseek|deepseek-harness) manage_dsh_mobile; press_enter ;; alarm|alarm-clock|alarm_clock|alarm.sh) manage_mix_scheduler; ;; congen|kdeconnect|congen-launch) manage_congen ;; block-internet|--block-internet|block_internet) block_internet; ;; unblock-internet|--unblock-internet|unblock_internet) unblock_internet ;; 0|[Ss]|shortcuts|desktop-shortcuts|ds|kioclient|run-shortcuts|desktop_shortcuts) manage_desktop_shortcuts; ;; " ") toggle_mp_audio_player ;; [mM]) launch_mp_audio_player_window ;; [lL]) launch_mp_audio_player_liquid_glass ;; [zZ]|visualizer|liquid-visualizer|mp-visualizer|mp_liquid_visualizer) launch_mp_liquid_visualizer ;; visualizer-preset|visualizer-presets) manage_mp_liquid_visualizer_presets ;; K) pkill -9 -f "MP_Audio_Player" 2>/dev/null || true; rm -f "${HOME}/.config/mix-manager/mp_player.pid" "${HOME}/.config/mix-manager/mp_audio_player.port" "${HOME}/.config/mix-manager/mp_audio_player.sock" 2>/dev/null || true; _CACHED_PLAYER_CHECK_TIME=0; _CACHED_PLAYER_ACTIVE_RES=1; MP_PLAYER_RUNNING=0; MP_PLAYER_STATE="stopped" ;; *) case "$choice" in ""|A|B|"[A"|"[B"|OA|OB|UP|DOWN|UNKNOWN|SECTION|SEP) ;; *) echo -e "\n${RED}Invalid option! Please enter a number between 0 and 37, or q to exit.${NC}"; sleep 2 ;; esac ;; esac; done
fi
