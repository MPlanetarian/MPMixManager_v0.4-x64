#!/usr/bin/env bash
# Open the MP Harmony AI Assistant from MP Mix Manager.
# If Ollama is not answering, offer to start it: a systemd user service,
# a distrobox/podman container (the container name is asked for), or a
# plain `ollama serve`. Declining returns straight to the manager.
# The model is the local tag gpt-oss-pinned:latest (OpenAI gpt-oss-20b).
# Shift+A on an empty assistant line returns to the manager.

if [ "${MP_HARMONY_LIB:-0}" = "1" ]; then
    set +e
else
    set -euo pipefail
fi

HARMONY_MODEL="${HARMONY_MODEL:-gpt-oss-pinned:latest}"
HARMONY_PARENT_MODEL="${HARMONY_PARENT_MODEL:-gpt-oss:20b}"
OLLAMA_API_URL="${OLLAMA_API_URL:-http://127.0.0.1:11434}"
OLLAMA_API_URL="${OLLAMA_API_URL%/}"

OLLAMA_SERVICE="${OLLAMA_SERVICE:-ollama.service}"
OLLAMA_CONTAINER_DEFAULT="${OLLAMA_CONTAINER_DEFAULT:-ollama-container}"
OLLAMA_CONTAINER="${OLLAMA_CONTAINER:-}"
OLLAMA_START_TIMEOUT="${OLLAMA_START_TIMEOUT:-60}"
OLLAMA_CONTAINER_LOG="${OLLAMA_CONTAINER_LOG:-${TMPDIR:-/tmp}/mp-harmony-ollama-serve.log}"

RED=$'\033[0;31m'
GREEN=$'\033[0;32m'
YELLOW=$'\033[0;33m'
CYAN=$'\033[0;36m'
BOLD=$'\033[1m'
NC=$'\033[0m'

harmony_say() {
    printf '%b\n' "$*"
}

harmony_wait_enter() {
    [ "${MP_HARMONY_NO_PAUSE:-0}" = "1" ] && return 0
    local _tty=/dev/tty
    [ -r "$_tty" ] || _tty=/dev/stdin
    printf '%b' "${BOLD}Press Enter to return to MP Mix Manager.${NC} "
    read -r _ </dev/tty 2>/dev/null || read -r _ || true
}

harmony_ollama_is_running() {
    if [ "${MP_HARMONY_FORCE_DOWN:-0}" = "1" ]; then
        return 1
    fi
    if [ "${MP_HARMONY_FORCE_UP:-0}" = "1" ]; then
        return 0
    fi
    local body=""
    body="$(curl -sf --connect-timeout 2 --max-time 4 "${OLLAMA_API_URL}/" 2>/dev/null || true)"
    if printf '%s' "$body" | grep -qi "Ollama is running"; then
        return 0
    fi
    return 1
}

harmony_ask() {
    # harmony_ask "prompt" [default] -> stores the answer in HARMONY_ANSWER.
    local prompt="$1" default="${2:-}"
    HARMONY_ANSWER=""
    if [ "${MP_HARMONY_ASSUME_YES:-0}" = "1" ]; then
        HARMONY_ANSWER="${default:-y}"
        return 0
    fi
    if [ "${MP_HARMONY_ASSUME_NO:-0}" = "1" ]; then
        return 0
    fi
    printf '%b' "$prompt"
    if [ -r /dev/tty ]; then
        read -r HARMONY_ANSWER </dev/tty || HARMONY_ANSWER=""
    else
        read -r HARMONY_ANSWER || HARMONY_ANSWER=""
    fi
    [ -z "$HARMONY_ANSWER" ] && HARMONY_ANSWER="$default"
    return 0
}

harmony_confirm_yes() {
    # harmony_confirm_yes "prompt" [default] -> success when the user answers yes.
    harmony_ask "$@"
    case "$HARMONY_ANSWER" in
        y|Y|yes|YES|Yes) return 0 ;;
        *) return 1 ;;
    esac
}

harmony_wait_for_ollama() {
    local deadline=$((SECONDS + OLLAMA_START_TIMEOUT))
    while [ "$SECONDS" -lt "$deadline" ]; do
        if harmony_ollama_is_running; then
            return 0
        fi
        sleep 1
    done
    return 1
}

harmony_systemd_service_exists() {
    command -v systemctl >/dev/null 2>&1 || return 1
    systemctl --user list-unit-files "$OLLAMA_SERVICE" >/dev/null 2>&1 || return 1
    systemctl --user list-unit-files "$OLLAMA_SERVICE" 2>/dev/null | grep -q "^${OLLAMA_SERVICE}"
}

harmony_podman_container_exists() {
    local name="$1"
    [ -n "$name" ] || return 1
    command -v podman >/dev/null 2>&1 || return 1
    podman container exists "$name" >/dev/null 2>&1
}

harmony_container_is_running() {
    local name="$1"
    [ -n "$name" ] || return 1
    command -v podman >/dev/null 2>&1 || return 1
    [ "$(podman inspect -f '{{.State.Running}}' "$name" 2>/dev/null || true)" = "true" ]
}

harmony_start_systemd_service() {
    harmony_say "${BOLD}Starting ${OLLAMA_SERVICE} with systemctl --user...${NC}"
    if systemctl --user start "$OLLAMA_SERVICE" >/dev/null 2>&1; then
        harmony_wait_for_ollama && return 0
        harmony_say "${YELLOW}${OLLAMA_SERVICE} started, but Ollama is not answering yet.${NC}"
        return 1
    fi
    harmony_say "${RED}systemctl --user could not start ${OLLAMA_SERVICE}.${NC}"
    return 1
}

harmony_start_container() {
    local name="$1"
    [ -n "$name" ] || return 1
    command -v distrobox >/dev/null 2>&1 || {
        harmony_say "${RED}distrobox is not installed, so ${name} cannot be entered.${NC}"
        return 1
    }
    if ! harmony_podman_container_exists "$name"; then
        harmony_say "${RED}No podman container named ${name} exists on this machine.${NC}"
        return 1
    fi
    harmony_say "${BOLD}Starting Ollama inside the ${name} container...${NC}"
    if ! harmony_container_is_running "$name"; then
        harmony_say "  Waking the container first."
        podman start "$name" >/dev/null 2>&1 || true
    fi
    : >"$OLLAMA_CONTAINER_LOG" 2>/dev/null || true
    nohup distrobox enter --no-workdir -T "$name" -- env \
        OLLAMA_HOST="0.0.0.0:${OLLAMA_API_URL##*:}" \
        OLLAMA_ORIGINS="*" \
        ollama serve >"$OLLAMA_CONTAINER_LOG" 2>&1 &
    if harmony_wait_for_ollama; then
        return 0
    fi
    harmony_say "${YELLOW}Ollama did not answer from ${name} within ${OLLAMA_START_TIMEOUT}s.${NC}"
    harmony_say "  Log: ${OLLAMA_CONTAINER_LOG}"
    return 1
}

harmony_start_local_serve() {
    command -v ollama >/dev/null 2>&1 || {
        harmony_say "${RED}No ollama binary was found on this machine.${NC}"
        return 1
    }
    harmony_say "${BOLD}Starting ollama serve in the background...${NC}"
    : >"$OLLAMA_CONTAINER_LOG" 2>/dev/null || true
    nohup ollama serve >"$OLLAMA_CONTAINER_LOG" 2>&1 &
    if harmony_wait_for_ollama; then
        return 0
    fi
    harmony_say "${YELLOW}ollama serve did not answer within ${OLLAMA_START_TIMEOUT}s.${NC}"
    harmony_say "  Log: ${OLLAMA_CONTAINER_LOG}"
    return 1
}

harmony_choose_container() {
    # Sets HARMONY_CONTAINER. Asks for the name unless OLLAMA_CONTAINER is set.
    local candidate="${OLLAMA_CONTAINER:-$OLLAMA_CONTAINER_DEFAULT}"
    HARMONY_CONTAINER="$candidate"
    if [ "${MP_HARMONY_NO_PROMPT:-0}" = "1" ] || [ -n "${OLLAMA_CONTAINER:-}" ]; then
        return 0
    fi
    # Offer a detected container as the default name.
    local running=""
    if command -v podman >/dev/null 2>&1; then
        running="$(podman ps -a --format '{{.Names}}' 2>/dev/null | grep -i ollama | head -n 1 || true)"
        [ -n "$running" ] && candidate="$running"
    fi
    harmony_say ""
    harmony_say "Ollama can run inside a distrobox or podman container."
    harmony_say "Enter the container name so the manager can start it from there."
    harmony_say "  Press Enter for: ${BOLD}${candidate}${NC}"
    harmony_ask "${BOLD}Container name: ${NC}" "$candidate"
    [ -n "$HARMONY_ANSWER" ] && HARMONY_CONTAINER="$HARMONY_ANSWER"
    return 0
}

harmony_model_installed() {
    if [ "${MP_HARMONY_FORCE_MODEL:-}" = "1" ]; then
        return 0
    fi
    if [ "${MP_HARMONY_FORCE_MODEL:-}" = "0" ]; then
        return 1
    fi
    local tags=""
    tags="$(curl -sf --connect-timeout 3 --max-time 8 "${OLLAMA_API_URL}/api/tags" 2>/dev/null || true)"
    if printf '%s' "$tags" | grep -F "\"name\":\"${HARMONY_MODEL}\"" >/dev/null 2>&1; then
        return 0
    fi
    return 1
}

harmony_describe_install() {
    cat <<EOF
${BOLD}${CYAN}Ollama is running, but ${HARMONY_MODEL} is not installed.${NC}

${BOLD}You would be installing this Ollama model tag:${NC}
  ${BOLD}${HARMONY_MODEL}${NC}
  About 14 GB on disk.

${BOLD}What the model is${NC}
  OpenAI gpt-oss-20b, the open-weight reasoning model.
  20.9 billion parameters, about 3.6 billion active per token.
  Mixture-of-experts, MXFP4 weights, GGUF, Apache License 2.0.
  It speaks the OpenAI Harmony format: analysis, commentary, and
  final channels. MP Harmony cannot drive a normal chat model.
  Text in, text out. Knowledge cutoff June 2024.
  Context window up to 131,072 tokens.
  Reasoning effort can be low, medium, or high. This assistant
  uses medium unless you change it.
  The official Ollama parent is ${HARMONY_PARENT_MODEL}
  (the same weights and the same license).
  If the registry has no tag named ${HARMONY_MODEL}, the installer
  pulls ${HARMONY_PARENT_MODEL} and copies it to ${HARMONY_MODEL}.

${BOLD}What it is used for in MP Mix Manager${NC}
  This is the local brain of the MP Harmony AI Assistant.
  It runs on the Ollama server already listening at ${OLLAMA_API_URL}.
  Your prompts stay on this machine. This is not a cloud chat tab.

${BOLD}What you get with the AI Assistant${NC}
  - Chat in this window. Shift+A on an empty line returns to the manager.
  - Read, write, and patch files, with a backup and a syntax check
    for Python, Bash, and JSON.
  - Shell commands and background jobs, with approval when that mode is on.
  - DJ tools: search the mix archive, read tracklists and cue sheets,
    find a track across mixes, and play, pause, or stop in MP Audio Player.
  - Archive totals: counts, size, and the newest mixes.
  - Web HUD at http://127.0.0.1:11435/ for CPU, memory, GPU, diffs, and jobs.
  - A speech archive and the local voice bridge.
  - An OpenAI-compatible API on port 11435 for Open WebUI.
  - Saved agent memory, git checkpoints, and web search.

EOF
}

harmony_confirm_install() {
    if [ "${MP_HARMONY_ASSUME_YES:-0}" = "1" ]; then
        return 0
    fi
    if [ "${MP_HARMONY_ASSUME_NO:-0}" = "1" ]; then
        return 1
    fi
    harmony_confirm_yes "${BOLD}Install ${HARMONY_MODEL} now? [y/N] ${NC}"
}

harmony_api_python() {
    python3 - "$@" <<'PY'
import json
import sys
import urllib.error
import urllib.request

base = sys.argv[1].rstrip("/")
action = sys.argv[2]


def post(path, payload, timeout, stream=False):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        base + path,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        print(body.strip() or f"HTTP {exc.code}", file=sys.stderr)
        return exc.code
    if not stream:
        body = resp.read().decode("utf-8", "replace")
        if body.strip():
            print(body.strip())
        return 0
    failed = False
    for raw in resp:
        line = raw.decode("utf-8", "replace").strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            print(line, flush=True)
            continue
        if obj.get("error"):
            print(obj["error"], file=sys.stderr, flush=True)
            failed = True
            continue
        status = obj.get("status") or ""
        total = obj.get("total") or 0
        done = obj.get("completed") or 0
        if total and done:
            pct = int(done * 100 / total)
            print(f"{status} {pct}%", flush=True)
        elif status:
            print(status, flush=True)
    return 1 if failed else 0


if action == "pull":
    name = sys.argv[3]
    code = post("/api/pull", {"name": name, "stream": True}, 7200, stream=True)
    sys.exit(code)
if action == "copy":
    source, dest = sys.argv[3], sys.argv[4]
    code = post("/api/copy", {"source": source, "destination": dest}, 120, stream=False)
    sys.exit(0 if code == 0 else 1)
if action == "load":
    name = sys.argv[3]
    payload = {
        "model": name,
        "prompt": ".",
        "stream": False,
        "keep_alive": "30m",
        "options": {"num_predict": 1},
    }
    code = post("/api/generate", payload, 600, stream=False)
    sys.exit(0 if code == 0 else 1)
print(f"unknown action {action}", file=sys.stderr)
sys.exit(2)
PY
}

harmony_install_model() {
    if [ "${MP_HARMONY_SKIP_INSTALL:-0}" = "1" ]; then
        harmony_say "${YELLOW}Install skipped.${NC}"
        return 1
    fi
    harmony_say "${BOLD}Pulling ${HARMONY_MODEL} from Ollama...${NC}"
    if harmony_api_python "$OLLAMA_API_URL" pull "$HARMONY_MODEL"; then
        return 0
    fi
    harmony_say "${YELLOW}${HARMONY_MODEL} is not on the Ollama registry.${NC}"
    harmony_say "${BOLD}Pulling the official parent ${HARMONY_PARENT_MODEL}, then copying it to ${HARMONY_MODEL}.${NC}"
    if ! harmony_api_python "$OLLAMA_API_URL" pull "$HARMONY_PARENT_MODEL"; then
        harmony_say "${RED}The download of ${HARMONY_PARENT_MODEL} failed. ${HARMONY_MODEL} was not installed.${NC}"
        return 1
    fi
    if ! harmony_api_python "$OLLAMA_API_URL" copy "$HARMONY_PARENT_MODEL" "$HARMONY_MODEL"; then
        harmony_say "${RED}Could not copy ${HARMONY_PARENT_MODEL} to ${HARMONY_MODEL}.${NC}"
        return 1
    fi
    return 0
}

harmony_load_model() {
    if [ "${MP_HARMONY_SKIP_LOAD:-0}" = "1" ]; then
        harmony_say "${GREEN}${HARMONY_MODEL} is installed. Load skipped.${NC}"
        return 0
    fi
    harmony_say "${BOLD}Loading ${HARMONY_MODEL} into Ollama memory.${NC}"
    harmony_say "  A 20.9B model can take a few minutes."
    if ! harmony_api_python "$OLLAMA_API_URL" load "$HARMONY_MODEL"; then
        harmony_say "${RED}Ollama did not load ${HARMONY_MODEL}. MP Harmony was not started.${NC}"
        return 1
    fi
    harmony_say "${GREEN}${HARMONY_MODEL} is loaded.${NC}"
    return 0
}

harmony_resolve_script() {
    local dir="${HARMONY_DIR:-/var/home/mplanetarian/OpenAI/MP_Harmony_Agent}"
    if [ ! -d "$dir" ] && [ -d "${HOME}/OpenAI/MP_Harmony_Agent" ]; then
        dir="${HOME}/OpenAI/MP_Harmony_Agent"
    elif [ ! -d "$dir" ] && [ -d "${HOME}/OpenAI/Harmony_Agent" ]; then
        dir="${HOME}/OpenAI/Harmony_Agent"
    fi
    HARMONY_DIR="$dir"
    HARMONY_SCRIPT="${HARMONY_DIR}/MP_Harmony_Agent.py"
    if [ ! -f "$HARMONY_SCRIPT" ] && [ -f "${HARMONY_DIR}/HA.py" ]; then
        HARMONY_SCRIPT="${HARMONY_DIR}/HA.py"
    fi
}

harmony_launch_agent() {
    if [ "${MP_HARMONY_SKIP_AGENT:-0}" = "1" ]; then
        harmony_say "${GREEN}Agent launch skipped.${NC}"
        return 0
    fi
    harmony_resolve_script
    if [ ! -f "${HARMONY_SCRIPT:-}" ]; then
        harmony_say "${RED}MP_Harmony_Agent.py was not found in ${HARMONY_DIR:-the Harmony directory}.${NC}"
        return 1
    fi
    harmony_say ""
    harmony_say "${BOLD}${CYAN}MP Harmony AI Assistant${NC}"
    harmony_say "  Model: ${HARMONY_MODEL}"
    harmony_say "  ${YELLOW}Shift+A on an empty line returns to MP Mix Manager.${NC}"
    harmony_say ""
    (
        cd "$HARMONY_DIR" || exit 1
        MP_MIX_MANAGER_SHIFT_A=1 \
            HARMONY_MODEL="$HARMONY_MODEL" \
            python3 "$HARMONY_SCRIPT" "$HARMONY_MODEL"
    )
}

harmony_offer_start_ollama() {
    # Returns 0 when Ollama is answering, 2 when the user declines.
    harmony_say ""
    harmony_say "${RED}${BOLD}Ollama is not running, so MP Harmony was not started.${NC}"
    harmony_say ""
    harmony_say "The assistant needs the Ollama service answering at ${OLLAMA_API_URL}."

    local how="serve" name=""
    local has_container_tool=0
    if command -v distrobox >/dev/null 2>&1 && command -v podman >/dev/null 2>&1; then
        has_container_tool=1
    elif harmony_systemd_service_exists; then
        harmony_say ""
        harmony_say "A systemd user service is installed: ${BOLD}${OLLAMA_SERVICE}${NC}"
    fi

    harmony_say ""
    if ! harmony_confirm_yes "${BOLD}Start Ollama now? [y/N] ${NC}"; then
        harmony_say "${YELLOW}Ollama was not started. Returning to MP Mix Manager.${NC}"
        return 2
    fi

    local started=1
    if [ "$has_container_tool" -eq 1 ]; then
        how="container"
        harmony_choose_container
        name="$HARMONY_CONTAINER"
        harmony_start_container "$name" && started=0
        if [ "$started" -ne 0 ] && harmony_systemd_service_exists; then
            harmony_start_systemd_service && started=0
        fi
    elif harmony_systemd_service_exists; then
        how="systemd"
        harmony_start_systemd_service && started=0
    fi
    if [ "$started" -ne 0 ]; then
        harmony_start_local_serve && started=0
    fi
    if [ "$started" -ne 0 ]; then
        harmony_say ""
        harmony_say "${RED}Ollama could not be started, so MP Harmony was not started.${NC}"
        harmony_say "Start Ollama yourself, then choose ${BOLD}AI${NC} again or press ${BOLD}Shift+A${NC}."
        harmony_wait_enter
        return 2
    fi

    harmony_say ""
    harmony_say "${GREEN}Ollama is answering at ${OLLAMA_API_URL}.${NC}"
    return 0
}

harmony_main() {
    printf '\033[0m\033[?25h'
    if ! harmony_ollama_is_running; then
        local start_rc=0
        harmony_offer_start_ollama || start_rc=$?
        if [ "$start_rc" -ne 0 ]; then
            return "$start_rc"
        fi
    fi

    if ! harmony_model_installed; then
        harmony_say ""
        harmony_describe_install
        if ! harmony_confirm_install; then
            harmony_say "${YELLOW}${HARMONY_MODEL} was not installed. MP Harmony was not started.${NC}"
            harmony_wait_enter
            return 3
        fi
        if ! harmony_install_model; then
            harmony_wait_enter
            return 4
        fi
        if ! harmony_model_installed; then
            harmony_say "${RED}${HARMONY_MODEL} is still not in Ollama after the install.${NC}"
            harmony_wait_enter
            return 4
        fi
    else
        harmony_say ""
        harmony_say "${GREEN}Ollama is running.${NC}"
        harmony_say "${GREEN}${HARMONY_MODEL} is installed.${NC}"
    fi

    if ! harmony_load_model; then
        harmony_wait_enter
        return 5
    fi
    harmony_launch_agent
}

if [ "${MP_HARMONY_LIB:-0}" != "1" ]; then
    harmony_main "$@"
fi
