#!/usr/bin/env bash
# ==============================================================================
# MP_Mix_Manager_v0.3 - Go Shopping for New Music & High-Res Tracks
# Opens Beatport, Apple Music, and Bandcamp in browser tabs.
# ==============================================================================

BOLD='\033[1m'
CYAN='\033[0;36m'
GREEN='\033[0;32m'
NC='\033[0m'

URLS=("https://www.beatport.com" "https://music.apple.com" "https://bandcamp.com")

open_urls() {
    local urls=("$@")
    if [ ${#urls[@]} -eq 0 ]; then
        urls=("${URLS[@]}")
    fi

    echo -e "${CYAN}Opening music platforms in your web browser...${NC}"
    for u in "${urls[@]}"; do
        echo -e "  • ${WHITE}${u}${NC}"
    done

    case "$(uname -s)" in
        Darwin)
            open "${urls[@]}" >/dev/null 2>&1 &
            ;;
        Linux|*microsoft*|*MINGW*|*CYGWIN*)
            if command -v flatpak >/dev/null 2>&1 && flatpak list 2>/dev/null | grep -q "com.google.Chrome"; then
                flatpak run com.google.Chrome "${urls[@]}" >/dev/null 2>&1 &
            elif command -v google-chrome >/dev/null 2>&1; then
                google-chrome "${urls[@]}" >/dev/null 2>&1 &
            elif command -v firefox >/dev/null 2>&1; then
                firefox "${urls[@]}" >/dev/null 2>&1 &
            elif command -v chromium >/dev/null 2>&1; then
                chromium "${urls[@]}" >/dev/null 2>&1 &
            elif command -v brave-browser >/dev/null 2>&1; then
                brave-browser "${urls[@]}" >/dev/null 2>&1 &
            else
                for u in "${urls[@]}"; do
                    xdg-open "$u" >/dev/null 2>&1 &
                done
            fi
            ;;
    esac
}

case "${1:-}" in
    --all)
        open_urls
        ;;
    --beatport)
        open_urls "${URLS[0]}"
        ;;
    --apple)
        open_urls "${URLS[1]}"
        ;;
    --bandcamp)
        open_urls "${URLS[2]}"
        ;;
    *)
        echo -e "${BOLD}${MAGENTA}======================================================================${NC}"
        echo -e "${BOLD}${MAGENTA}               🛒 GO SHOPPING FOR NEW MUSIC & TRACKS                  ${NC}"
        echo -e "${BOLD}${MAGENTA}======================================================================${NC}\n"
        echo -e "  Quick-launch curated electronic music stores in your web browser:\n"
        echo -e "  ${BOLD}${CYAN} 1)${NC} ${BOLD}Open All 3 Stores in Browser Tabs${NC} (${GREEN}Beatport + Apple Music + Bandcamp${NC})"
        echo -e "  ${BOLD}${CYAN} 2)${NC} ${BOLD}Beatport${NC} (${DIM}https://www.beatport.com${NC})"
        echo -e "  ${BOLD}${CYAN} 3)${NC} ${BOLD}Apple Music${NC} (${DIM}https://music.apple.com${NC})"
        echo -e "  ${BOLD}${CYAN} 4)${NC} ${BOLD}Bandcamp${NC} (${DIM}https://bandcamp.com${NC})"
        echo -e "  ${BOLD}${CYAN} 0)${NC} Return to Main Menu\n"
        read -r -p "Enter choice [1-4, or 0 to return]: " choice

        case "$choice" in
            1|"")
                open_urls
                ;;
            2)
                open_urls "${URLS[0]}"
                ;;
            3)
                open_urls "${URLS[1]}"
                ;;
            4)
                open_urls "${URLS[2]}"
                ;;
            0|[qQ])
                ;;
            *)
                echo -e "\n${RED}Invalid choice.${NC}"
                ;;
        esac
        ;;
esac