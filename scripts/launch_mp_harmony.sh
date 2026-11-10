#!/usr/bin/env bash
# Open the MP Harmony AI Assistant from MP Mix Manager.
# Ollama must already be answering. This script does not start it.
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
    local answer=""
    printf '%b' "${BOLD}Install ${HARMONY_MODEL} now? [y/N] ${NC}"
    if [ -r /dev/tty ]; then
        read -r answer </dev/tty || answer=""
    else
        read -r answer || answer=""
    fi
    case "$answer" in
        y|Y|yes|YES|Yes) return 0 ;;
        *) return 1 ;;
    esac
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

harmony_main() {
    printf '\033[0m\033[?25h'
    if ! harmony_ollama_is_running; then
        harmony_say ""
        harmony_say "${RED}${BOLD}Ollama is not running, so MP Harmony was not started.${NC}"
        harmony_say ""
        harmony_say "The assistant needs the Ollama service answering at ${OLLAMA_API_URL}."
        harmony_say "Start Ollama, then choose ${BOLD}AI${NC} again or press ${BOLD}Shift+A${NC}."
        harmony_say "This option does not start Ollama for you."
        harmony_say ""
        harmony_wait_enter
        return 2
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
