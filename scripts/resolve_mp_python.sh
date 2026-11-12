#!/usr/bin/env bash
# Resolve a Python 3 that can run MP Audio Player.
# Windows Store aliases in WindowsApps print "Python was not found" and exit.
# env and nohup do not see a python3() shell function, so callers must use
# the absolute path from mp_python_bin.

_mp_python_is_stub() {
    case "$1" in
        *[Ww]indows[Aa]pps*) return 0 ;;
    esac
    return 1
}

_mp_python_works() {
    local bin="$1"
    [ -n "$bin" ] || return 1
    _mp_python_is_stub "$bin" && return 1
    if [ ! -f "$bin" ] && [ ! -x "$bin" ]; then
        return 1
    fi
    "$bin" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 8) else 1)" >/dev/null 2>&1
}

# True when the interpreter imports every module named on the command line.
# A missing PyGObject is the usual reason a shortcut dies: Homebrew ships a
# python3 without "gi", and having it first on PATH used to shadow the system
# interpreter, so every MP desktop shortcut exited with "No module named 'gi'".
_mp_python_can_import() {
    local bin="$1"
    shift
    _mp_python_works "$bin" || return 1
    "$bin" - "$@" >/dev/null 2>&1 <<'PY'
import importlib, sys
for name in sys.argv[1:]:
    importlib.import_module(name)
PY
}

# Every interpreter worth trying, best first. System interpreters come before
# PATH ones so a feature-poor Homebrew/conda python cannot hide a working
# PyGObject install.
_mp_python_candidates() {
    local item
    [ -n "${MP_PYTHON:-}" ] && printf '%s\n' "$MP_PYTHON"
    if [ -n "${MP_PYTHON_CANDIDATES:-}" ]; then
        local raw="${MP_PYTHON_CANDIDATES//;/$'\n'}"
        while IFS= read -r item || [ -n "$item" ]; do
            item="${item#"${item%%[![:space:]]*}"}"
            item="${item%"${item##*[![:space:]]}"}"
            [ -n "$item" ] && printf '%s\n' "$item"
        done <<< "$raw"
    fi
    if [ -n "${SCRIPT_DIR:-}" ]; then
        printf '%s\n' \
            "${SCRIPT_DIR}/venv/bin/python3" \
            "${SCRIPT_DIR}/venv/bin/python" \
            "${SCRIPT_DIR}/.venv/bin/python3" \
            "${SCRIPT_DIR}/.venv/bin/python"
    fi
    printf '%s\n' \
        "${HOME}/.local/share/mp-mix-manager/python-env/bin/python3" \
        "${HOME}/.local/share/mp-mix-manager/python-env/bin/python" \
        "/usr/bin/python3" \
        "/usr/bin/python" \
        "/usr/local/bin/python3" \
        "/usr/local/bin/python"
    for item in python3 python; do
        item="$(type -p "$item" 2>/dev/null || true)"
        [ -n "$item" ] && printf '%s\n' "$item"
    done
    printf '%s\n' \
        "/opt/homebrew/bin/python3" \
        "/home/linuxbrew/.linuxbrew/bin/python3"
}

_mp_python_use() {
    MP_PYTHON="$1"
    export MP_PYTHON
    _mp_install_python3_shim
}

# Print the first interpreter that can import the named modules. Returns
# non-zero when none qualifies so callers can fall back.
mp_python_with_modules() {
    local bin
    [ "$#" -gt 0 ] || return 1
    local seen=" "
    while IFS= read -r bin; do
        [ -n "$bin" ] || continue
        case "$seen" in
            *" ${bin} "*) continue ;;
        esac
        seen="${seen}${bin} "
        if _mp_python_can_import "$bin" "$@"; then
            _mp_python_use "$bin"
            printf '%s\n' "$bin"
            return 0
        fi
    done <<EOF
$(_mp_python_candidates)
EOF
    return 1
}

# The Liquid Glass window needs PyGObject (Gtk 3, GdkX11, Vte) and numpy.
# soundfile stays optional: MP_Audio_Player.py imports it in a try/except.
# Windows does not use GTK, so it keeps the plain resolver.
mp_gui_python_bin() {
    local bin
    case "$(uname -s 2>/dev/null)" in
        MINGW*|MSYS*|CYGWIN*) mp_python_bin; return $? ;;
    esac
    if bin="$(mp_python_with_modules gi numpy 2>/dev/null)" && [ -n "$bin" ]; then
        printf '%s\n' "$bin"
        return 0
    fi
    mp_python_bin
    return $?
}

# The standalone visualizer only needs numpy and OpenGL.
mp_visualizer_python_bin() {
    local bin
    case "$(uname -s 2>/dev/null)" in
        MINGW*|MSYS*|CYGWIN*) mp_python_bin; return $? ;;
    esac
    if bin="$(mp_python_with_modules numpy OpenGL 2>/dev/null)" && [ -n "$bin" ]; then
        printf '%s\n' "$bin"
        return 0
    fi
    mp_python_bin
    return $?
}

_mp_install_python3_shim() {
    [ -n "${MP_PYTHON:-}" ] || return 0
    python3() { "$MP_PYTHON" "$@"; }
    export -f python3 2>/dev/null || true
    local py_dir
    py_dir="$(dirname "$MP_PYTHON")"
    case ":${PATH:-}:" in
        *":${py_dir}:"*) ;;
        *) PATH="${py_dir}:${PATH:-}"; export PATH ;;
    esac
}

# Print the interpreter path. Falls back to the name python3.
mp_python_bin() {
    if [ -n "${MP_PYTHON:-}" ] && _mp_python_works "$MP_PYTHON"; then
        printf '%s\n' "$MP_PYTHON"
        return 0
    fi
    local resolved
    resolved="$(resolve_mp_python 2>/dev/null || true)"
    if [ -n "$resolved" ]; then
        printf '%s\n' "$resolved"
        return 0
    fi
    printf '%s\n' "python3"
    return 1
}

resolve_mp_python() {
    local cand resolved user_name pyver item raw path_py found
    user_name="${USERNAME:-${USER:-}}"
    local -a cands=()

    if [ -n "${MP_PYTHON_CANDIDATES:-}" ]; then
        raw="${MP_PYTHON_CANDIDATES//;/$'\n'}"
        while IFS= read -r item || [ -n "$item" ]; do
            item="${item#"${item%%[![:space:]]*}"}"
            item="${item%"${item##*[![:space:]]}"}"
            [ -n "$item" ] && cands+=("$item")
        done <<< "$raw"
    fi

    if [ -n "${SCRIPT_DIR:-}" ]; then
        cands+=(
            "${SCRIPT_DIR}/venv/Scripts/python.exe"
            "${SCRIPT_DIR}/venv/bin/python3"
            "${SCRIPT_DIR}/venv/bin/python"
        )
    fi

    for pyver in 313 312 311 310; do
        cands+=(
            "/c/Users/${user_name}/AppData/Local/Programs/Python/Python${pyver}/python.exe"
            "/c/Program Files/Python${pyver}/python.exe"
            "C:/Users/${user_name}/AppData/Local/Programs/Python/Python${pyver}/python.exe"
            "C:/Program Files/Python${pyver}/python.exe"
        )
    done
    cands+=(
        "/c/ProgramData/anaconda3/python.exe"
        "C:/ProgramData/anaconda3/python.exe"
        "/c/Users/${user_name}/anaconda3/python.exe"
        "C:/Users/${user_name}/anaconda3/python.exe"
        "/c/Users/${user_name}/miniconda3/python.exe"
        "C:/Users/${user_name}/miniconda3/python.exe"
        "/c/ProgramData/miniconda3/python.exe"
        "C:/ProgramData/miniconda3/python.exe"
    )

    for cand in "${cands[@]}"; do
        [ -n "$cand" ] || continue
        if _mp_python_works "$cand"; then
            MP_PYTHON="$cand"
            export MP_PYTHON
            _mp_install_python3_shim
            printf '%s\n' "$MP_PYTHON"
            return 0
        fi
    done

    if command -v py >/dev/null 2>&1; then
        resolved="$(py -3 -c "import sys; print(sys.executable)" 2>/dev/null || true)"
        resolved="${resolved//$'\r'/}"
        if _mp_python_works "$resolved"; then
            MP_PYTHON="$resolved"
            export MP_PYTHON
            _mp_install_python3_shim
            printf '%s\n' "$MP_PYTHON"
            return 0
        fi
    fi

    for path_py in python3 python; do
        found="$(type -p "$path_py" 2>/dev/null || true)"
        if _mp_python_works "$found"; then
            MP_PYTHON="$found"
            export MP_PYTHON
            _mp_install_python3_shim
            printf '%s\n' "$MP_PYTHON"
            return 0
        fi
    done
    return 1
}
