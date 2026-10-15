#!/usr/bin/env bash

# OS Platform Detection
OS_TYPE="linux"
case "$(uname -s)" in
    CYGWIN*|MINGW*|MSYS*) OS_TYPE="windows" ;;
    Darwin*)               OS_TYPE="macos" ;;
    *)                    OS_TYPE="linux" ;;
esac

NC='\033[0m'
BOLD='\033[1m'
GREEN='\033[38;2;0;229;255m'
YELLOW='\033[38;2;255;170;0m'
RED='\033[38;2;237;37;78m'
CYAN='\033[38;2;0;193;228m'
MAGENTA='\033[38;2;247;37;133m'
DIM='\033[2m'

press_enter() {
    echo ""
    read -r -p "Press [Enter] to return to the Open WebUI menu..."
}

find_webui_port_and_pids() {
    WEBUI_PORT=8080
    WEBUI_RUNNING=false
    WEBUI_PIDS=""

    for p in 8080 42004; do
        if curl -s -I --connect-timeout 0.75 "http://127.0.0.1:${p}/" 2>/dev/null | grep -qi "HTTP/" || \
           curl -s -I --connect-timeout 0.75 "http://localhost:${p}/" 2>/dev/null | grep -qi "HTTP/"; then
            WEBUI_RUNNING=true
            WEBUI_PORT=$p
            break
        fi
    done

    if [ "$OS_TYPE" = "windows" ]; then
        if command -v netstat.exe >/dev/null 2>&1; then
            WEBUI_PIDS=$(netstat.exe -ano 2>/dev/null | tr -d '\r' | awk -v port=":${WEBUI_PORT}" '$2 ~ port && $4 == "LISTENING" {print $5}' | sort -u | tr '\n' ' ')
            [ -n "$WEBUI_PIDS" ] && WEBUI_RUNNING=true
        fi
    else
        if pgrep -f "open-webui" >/dev/null 2>&1; then
            WEBUI_PIDS=$(pgrep -f "open-webui" 2>/dev/null | tr '\n' ' ')
            WEBUI_RUNNING=true
        fi
    fi
}

start_open_webui() {
    find_webui_port_and_pids
    if [ "$WEBUI_RUNNING" = "true" ]; then
        echo -e "\n${YELLOW}Open WebUI is already running on http://localhost:${WEBUI_PORT}${NC}"
        press_enter
        return 0
    fi

    echo -e "\n${GREEN}Starting Open WebUI Server...${NC}"
    if [ "$OS_TYPE" = "windows" ]; then
        local bat_cand=(
            "$PWD/start_openwebui.bat"
            "B:/MIX_ARCHIVE/start_openwebui.bat"
            "X:/OPENWEBUI/start_openwebui.bat"
            "$SCRIPT_DIR/start_openwebui.bat"
            "$USERPROFILE/Desktop/start_openwebui.bat"
            "$USERPROFILE/Desktop/start_openwebui.bat.lnk"
        )
        local bat_found=""
        for b in "${bat_cand[@]}"; do
            if [ -f "$b" ]; then bat_found="$b"; break; fi
        done

        if [ -n "$bat_found" ]; then
            local win_bat
            win_bat="$(cygpath -w "$bat_found" 2>/dev/null || echo "$bat_found")"
            MSYS_NO_PATHCONV=1 cmd.exe /c start "" "$win_bat"
        else
            # Explicit subshell invocation without dropping to an empty B:\ prompt
            MSYS_NO_PATHCONV=1 cmd.exe /c start "Open WebUI Launcher" cmd.exe /c \
              "call C:\ProgramData\anaconda3\condabin\conda.bat activate X:\OPENWEBUI\env && set DATA_DIR=X:\OPENWEBUI\data && set OLLAMA_BASE_URL=http://127.0.0.1:11434 && echo Starting Open WebUI... && open-webui serve"
        fi
    else
        if systemctl --user list-unit-files 2>/dev/null | grep -q open-webui; then
            systemctl --user start open-webui.service
        else
            nohup open-webui serve >/dev/null 2>&1 &
        fi
    fi

    echo -e "${GREEN}✓ Launch command dispatched. Probing server on port 8080...${NC}"
    for ((i=1; i<=15; i++)); do
        sleep 1
        find_webui_port_and_pids
        if [ "$WEBUI_RUNNING" = "true" ]; then
            echo -e "${GREEN}✓ Server online on http://localhost:${WEBUI_PORT}!${NC}"
            break
        fi
    done
    press_enter
}

stop_open_webui() {
    find_webui_port_and_pids
    if [ "$WEBUI_RUNNING" = "false" ]; then
        echo -e "\n${YELLOW}Open WebUI is not running.${NC}"
        press_enter
        return 0
    fi

    echo -e "\n${YELLOW}Stopping Open WebUI Server...${NC}"
    if [ "$OS_TYPE" = "windows" ]; then
        if [ -n "$WEBUI_PIDS" ]; then
            for pid in $WEBUI_PIDS; do
                taskkill.exe //F //T //PID "$pid" 2>/dev/null || true
            done
        fi
        taskkill.exe //F //FI "WINDOWTITLE eq Open WebUI Launcher*" 2>/dev/null || true
    else
        if systemctl --user is-active --quiet open-webui.service 2>/dev/null; then
            systemctl --user stop open-webui.service
        else
            pkill -f "open-webui serve" 2>/dev/null || true
        fi
    fi
    sleep 1
    echo -e "${GREEN}✓ Open WebUI stopped.${NC}"
    press_enter
}

open_webui_browser() {
    find_webui_port_and_pids
    local target_url="http://localhost:${WEBUI_PORT}"
    echo -e "\n${CYAN}Opening ${target_url} in default web browser...${NC}"
    if [ "$OS_TYPE" = "windows" ]; then
        MSYS_NO_PATHCONV=1 cmd.exe /c start "" "$target_url"
    elif [ "$OS_TYPE" = "macos" ]; then
        open "$target_url"
    else
        xdg-open "$target_url" >/dev/null 2>&1 &
    fi
}

view_webui_logs() {
    echo -e "\n${BOLD}${BLUE}=== OPEN WEBUI RECENT LOGS ===${NC}\n"
    if [ "$OS_TYPE" = "windows" ]; then
        local log_shown=0
        for l in "X:/OPENWEBUI/data/webui.log" "X:/OPENWEBUI/data/logs/open-webui.log"; do
            if [ -f "$l" ]; then
                tail -n 40 "$l"
                log_shown=1
                break
            fi
        done
        if [ "$log_shown" -eq 0 ]; then
            echo -e "${YELLOW}Open WebUI logs output directly to the dedicated launcher console window.${NC}"
            echo -e "Check the '${BOLD}Open WebUI Launcher${NC}' window on your Windows taskbar."
        fi
    else
        journalctl --user -u open-webui.service -n 50 --no-pager 2>/dev/null || true
    fi
    press_enter
}

update_open_webui() {
    echo -e "\n${BOLD}${MAGENTA}=== UPDATE OPEN WEBUI ===${NC}\n"
    if [ "$OS_TYPE" = "windows" ]; then
        echo -e "${CYAN}Checking for Open WebUI updates in X:\\\\OPENWEBUI\\\\env...${NC}\n"
        if [ -f "C:/ProgramData/anaconda3/Scripts/conda.exe" ]; then
            "C:/ProgramData/anaconda3/Scripts/conda.exe" run -p "X:/OPENWEBUI/env" python -m pip install --upgrade open-webui
        else
            MSYS_NO_PATHCONV=1 cmd.exe /c "C:\ProgramData\anaconda3\condabin\conda.bat activate X:\OPENWEBUI\env && python -m pip install --upgrade open-webui"
        fi
    else
        local exec_line=""
        if systemctl --user list-unit-files 2>/dev/null | grep -q "open-webui.service"; then
            exec_line=$(systemctl --user show -p ExecStart --value open-webui.service 2>/dev/null)
        fi

        local venv_py=""
        if echo "$exec_line" | grep -q "path="; then
            local exec_path
            exec_path=$(echo "$exec_line" | sed -n 's/.*path=\([^ ;]*\).*/\1/p')
            if [ -f "$(dirname "$exec_path")/python" ]; then
                venv_py="$(dirname "$exec_path")/python"
            fi
        fi

        if [ -z "$venv_py" ] && [ -x "$HOME/pinokio/api/open-webui/app/env/bin/python" ]; then
            venv_py="$HOME/pinokio/api/open-webui/app/env/bin/python"
        fi

        local uv_bin
        uv_bin=$(command -v uv 2>/dev/null || echo "$HOME/.local/bin/uv")

        if [ -n "$venv_py" ] && [ -x "$uv_bin" ]; then
            echo -e "${CYAN}Updating Open WebUI virtual environment with uv...${NC}\n"
            "$uv_bin" pip install --upgrade open-webui --python "$venv_py"
        elif [ -n "$venv_py" ]; then
            echo -e "${CYAN}Updating Open WebUI virtual environment...${NC}\n"
            "$venv_py" -m pip install --upgrade open-webui 2>/dev/null || pip install --upgrade open-webui
        elif command -v podman >/dev/null 2>&1; then
            echo -e "${CYAN}Pulling latest Open WebUI image (ghcr.io/open-webui/open-webui:main)...${NC}\n"
            podman pull ghcr.io/open-webui/open-webui:main
        else
            pip install --upgrade open-webui
        fi

        if systemctl --user list-unit-files 2>/dev/null | grep -q "open-webui.service"; then
            echo -e "\n${CYAN}Restarting open-webui.service to pick up updates...${NC}\n"
            systemctl --user restart open-webui.service
        fi

        echo -e "\n${GREEN}✓ Open WebUI update process completed.${NC}"
    fi
    press_enter
}

while true; do
    find_webui_port_and_pids
    clear
    echo -e "${BOLD}${MAGENTA}==================================================${NC}"
    echo -e "${BOLD}${MAGENTA}             OPEN WEBUI SERVER MANAGER            ${NC}"
    echo -e "${BOLD}${MAGENTA}==================================================${NC}"
if [ "$WEBUI_RUNNING" = "true" ]; then
        pid_str=""
        [ -n "$WEBUI_PIDS" ] && pid_str=" (PID: ${WEBUI_PIDS% })"
        echo -e "  Server Status:  ${BOLD}${GREEN}● RUNNING${NC} on http://localhost:${WEBUI_PORT}${pid_str}"
    else
        echo -e "  Server Status:  ${BOLD}${RED}○ STOPPED${NC}"
    fi
    echo -e "  Data Directory: ${CYAN}X:\OPENWEBUI\data${NC}"
    echo -e "  Ollama URL:     ${CYAN}http://127.0.0.1:11434${NC}"
    echo ""
    echo -e "${BOLD}Select an Open WebUI Operation:${NC}"
    echo -e "  ${BOLD}${CYAN}1)${NC} Open in Web Browser (${GREEN}http://localhost:${WEBUI_PORT}${NC})"
    echo -e "  ${BOLD}${CYAN}2)${NC} Start Server (${GREEN}start_openwebui.bat / conda env${NC})"
    echo -e "  ${BOLD}${CYAN}3)${NC} Stop Server (${RED}taskkill / stop${NC})"
    echo -e "  ${BOLD}${CYAN}4)${NC} Restart Server"
    echo -e "  ${BOLD}${CYAN}5)${NC} View Server Logs / Console Output"
    echo -e "  ${BOLD}${CYAN}6)${NC} Check / Install Open WebUI Updates"
    echo -e "  ${BOLD}${CYAN}0)${NC} Return to Main Menu"
    echo ""
    read -r -p "Enter choice [0-6]: " ow_opt

case "$ow_opt" in
        1) open_webui_browser ;;
        2) start_open_webui ;;
        3) stop_open_webui ;;
        4)
            stop_open_webui
            sleep 1
            start_open_webui
            ;;
        5) view_webui_logs ;;
        6) update_open_webui ;;
        0|[qQ]|"") break ;;
        *)
            echo -e "\n${RED}Invalid option!${NC}"
            sleep 1
            ;;
    esac
done