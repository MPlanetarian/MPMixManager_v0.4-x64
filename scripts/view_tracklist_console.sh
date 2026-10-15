    #!/bin/bash

    # ANSI Color Palette
    BOLD='\033[1m'
    DIM='\033[2m'
    ITALIC='\033[3m'
    UNDERLINE='\033[4m'
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[0;33m'
    BLUE='\033[0;34m'
    MAGENTA='\033[0;35m'
    CYAN='\033[0;36m'
    WHITE='\033[1;37m'
    NC='\033[0m'

    TARGET_FILE="$1"

    if [ -z "$TARGET_FILE" ] || [ ! -f "$TARGET_FILE" ]; then
        clear
        echo -e "${RED}Error: Tracklist file not provided or does not exist!${NC}"
        echo -e "${DIM}Usage: $0 <path-to-tracklist.txt>${NC}"
        echo ""
        read -r -p "Press [Enter] to exit..."
        exit 1
    fi

    HOST_DESC="Linux"
    if [ -f /etc/os-release ]; then
        HOST_DESC=$(grep -E '^PRETTY_NAME=' /etc/os-release | cut -d= -f2 | tr -d '"')
    elif [ "$(uname -s)" = "Darwin" ]; then
        HOST_DESC="macOS $(sw_vers -productVersion 2>/dev/null)"
    elif [ "$(uname -s)" = "FreeBSD" ]; then
        HOST_DESC="FreeBSD $(uname -r)"
    fi

    copy_tracklist_clipboard() {
        local text
        text=$(<"$TARGET_FILE")
        for cmd in wl-copy xclip pbcopy clip.exe; do
            if command -v "$cmd" >/dev/null 2>&1; then
                printf "%s" "$text" | "$cmd" 2>/dev/null
                return 0
            fi
        done
        return 1
    }

    render_tracklist() {
        clear
        local filename=$(basename "$TARGET_FILE")
        local total_lines=$(wc -l < "$TARGET_FILE" 2>/dev/null || echo "0")
        local filesize=$(ls -lh "$TARGET_FILE" 2>/dev/null | awk '{print $5}')

        echo -e "${BOLD}${MAGENTA}========================================================================================${NC}"
        echo -e "${BOLD}${CYAN}            🎶 STREAM OF FREQUENCY • DEDICATED CONSOLE TRACKLIST VIEWER 🎶              ${NC}"
        echo -e "${BOLD}${MAGENTA}========================================================================================${NC}"
        echo -e "  • ${BOLD}File:${NC}        ${GREEN}${filename}${NC} ${DIM}(${filesize}, ${total_lines} lines)${NC}"
        echo -e "  • ${BOLD}Location:${NC}    ${DIM}$(dirname "$TARGET_FILE")${NC}"
        echo -e "  • ${BOLD}Platform:${NC}    ${YELLOW}${HOST_DESC}${NC} ${DIM}(Borderless Console Mode)${NC}"
        echo -e "${BOLD}${MAGENTA}────────────────────────────────────────────────────────────────────────────────────────${NC}\n"

        local in_tracklist=0
        local track_count=0

        while IFS= read -r line || [ -n "$line" ]; do
            if [[ "$line" =~ ^={10,}$ || "$line" =~ ^-{10,}$ ]]; then
                echo -e "${DIM}${line}${NC}"
            elif [[ "$line" =~ (RELEASE\ INFO|TRACKLIST|SOURCE\ MANIFEST|SOURCE\ FILES) ]]; then
                echo -e "${BOLD}${YELLOW}${line}${NC}"
            elif [[ "$line" =~ ^([A-Za-z0-9\ ]+):([[:space:]]+)(.*)$ ]]; then
                local key="${BASH_REMATCH[1]}"
                local val="${BASH_REMATCH[3]}"
                echo -e "  ${BOLD}${BLUE}${key}:${NC} ${WHITE}${val}${NC}"
            elif [[ "$line" =~ ^([0-9]{1,3})[\.\)][[:space:]]+(.*)$ ]]; then
                local num="${BASH_REMATCH[1]}"
                local rest="${BASH_REMATCH[2]}"
                ((track_count++))
                if [[ "$rest" =~ ^([^-]+)[[:space:]]-[[:space:]](.+)$ ]]; then
                    local artist="${BASH_REMATCH[1]}"
                    local title="${BASH_REMATCH[2]}"
                    if [[ "$title" =~ (.*)(\([^\)]+\))(.*) ]]; then
                        local tmain="${BASH_REMATCH[1]}"
                        local remix="${BASH_REMATCH[2]}"
                        local tend="${BASH_REMATCH[3]}"
                        printf "  ${BOLD}${CYAN}%02d.${NC} ${WHITE}%s${NC} - ${GREEN}%s${NC}${YELLOW}%s${NC}%s\n" "$((10#$num))" "$artist" "$tmain" "$remix" "$tend"
                    else
                        printf "  ${BOLD}${CYAN}%02d.${NC} ${WHITE}%s${NC} - ${GREEN}%s${NC}\n" "$((10#$num))" "$artist" "$title"
                    fi
                else
                    printf "  ${BOLD}${CYAN}%02d.${NC} ${WHITE}%s${NC}\n" "$((10#$num))" "$rest"
                fi
            elif [ -z "$line" ]; then
                echo ""
            else
                echo -e "  ${WHITE}${line}${NC}"
            fi
        done < "$TARGET_FILE"

        echo ""
        echo -e "${BOLD}${MAGENTA}========================================================================================${NC}"
        if [ "$track_count" -gt 0 ]; then
            echo -e "  ${BOLD}${GREEN}✓ Total Tracks Parsed:${NC} ${BOLD}${WHITE}${track_count}${NC}"
        fi
        echo -e "  ${BOLD}${CYAN}[Q]${NC} Close Window    ${BOLD}${CYAN}[C]${NC} Copy to Clipboard    ${BOLD}${CYAN}[S]${NC} Full Scroll Mode (less)    ${BOLD}${CYAN}[R]${NC} Reload"
        echo -e "${BOLD}${MAGENTA}========================================================================================${NC}"
    }

    render_tracklist

    while true; do
        if [ -t 0 ]; then
            read -r -s -n 1 key
        else
            sleep 3600
            exit 0
        fi

        case "$key" in
            [qQ]|$'\e')
                exit 0
                ;;
            [cC])
                if copy_tracklist_clipboard; then
                    render_tracklist
                    echo -e "\n  ${BOLD}${GREEN}✓ Tracklist copied to system clipboard!${NC}"
                else
                    echo -e "\n  ${YELLOW}Notice: No clipboard utility found.${NC}"
                fi
                ;;
            [rR])
                render_tracklist
                echo -e "\n  ${BOLD}${CYAN}✓ Tracklist reloaded from disk.${NC}"
                ;;
            [sS])
                if command -v less >/dev/null 2>&1; then
                    less -RFX "$TARGET_FILE"
                    render_tracklist
                fi
                ;;
            [eE])
                for editor in kwrite kate xdg-open; do
                    if command -v "$editor" >/dev/null 2>&1; then
                        "$editor" "$TARGET_FILE" >/dev/null 2>&1 &
                        break
                    fi
                done
                ;;
        esac
    done