sed -i 's/"3|Launch Native Terminal Audio Player|(Standard TTY UI)"/"3|Launch MP Audio Player (Liquid Glass Mode)|(launch-liquid-glass)"/' Mix_Archive_Manager.sh
sed -i 's/3) manage_mp_audio_player ;;/\&3) launch_mp_audio_player_liquid_glass >\/dev\/null 2>\&1 ;;/' Mix_Archive_Manager.sh
