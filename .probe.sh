#!/bin/bash
SRC=/x/MP_Mix_Manager_v0.3/Mix_Archive_Manager.sh
BOLD="";MAGENTA="";CYAN="";BLUE="";DIM="";NC="";YELLOW="";GREEN="";RED=""
SCRIPT_DIR=/x/MP_Mix_Manager_v0.3
get_mp_audio_player_track_info(){ return 1; }
shopt -s checkwinsize
_TERM_LINES=""; _TERM_COLS=""; _TERM_RESIZED=1
trap '_TERM_RESIZED=1' WINCH
eval "$(sed -n '121,140p' $SRC)"
eval "$(sed -n '302,1027p' $SRC)"
opts=("1|First|(a)" "2|Second|(b)" "3|Third|(c)" "0|Exit|(z)")
run_interactive_submenu "TEST MENU" "" opts 0
echo "REPLY1=$REPLY" > /x/MP_Mix_Manager_v0.3/.conout.txt
run_interactive_submenu "TEST MENU" "" opts 0
echo "REPLY2=$REPLY" >> /x/MP_Mix_Manager_v0.3/.conout.txt
sleep 5
