#!/usr/bin/env bash
# Create the persistent macOS Python environment used by MP Liquid Player.
set -euo pipefail

if [ "$(uname -s 2>/dev/null || true)" != "Darwin" ]; then
    command -v python3
    exit 0
fi

ENV_DIR="$HOME/.local/share/mp-mix-manager/python-env"
LOCK_DIR="$HOME/.local/share/mp-mix-manager/python-env.lock"
mkdir -p "$(dirname "$ENV_DIR")"

_tries=0
until mkdir "$LOCK_DIR" 2>/dev/null; do
    _tries=$((_tries + 1))
    if [ "$_tries" -ge 120 ]; then
        echo "Error: timed out waiting for MP Mix Manager Python setup." >&2
        exit 1
    fi
    sleep 0.25
done
trap 'rmdir "$LOCK_DIR" 2>/dev/null || true' EXIT

PYTHON=""
for _candidate in "${MP_PYTHON:-}" /opt/homebrew/bin/python3 /usr/local/bin/python3; do
    if [ -n "$_candidate" ] && [ -x "$_candidate" ]; then
        PYTHON="$_candidate"
        break
    fi
done
if [ -z "$PYTHON" ]; then
    PYTHON="$(command -v python3 || true)"
fi
if [ -z "$PYTHON" ] || [ ! -x "$PYTHON" ]; then
    echo "Error: Python 3 is required to prepare MP Mix Manager." >&2
    exit 1
fi

ENV_PY="$ENV_DIR/bin/python"
if [ ! -x "$ENV_PY" ] || ! "$ENV_PY" -c 'import sys; assert sys.version_info >= (3, 9)' >/dev/null 2>&1; then
    "$PYTHON" -m venv --system-site-packages "$ENV_DIR"
fi

if ! "$ENV_PY" -c 'import sounddevice' >/dev/null 2>&1; then
    "$ENV_PY" -m pip install --disable-pip-version-check sounddevice >&2
fi
if ! "$ENV_PY" -c 'import sounddevice' >/dev/null 2>&1; then
    echo "Error: could not install sounddevice in $ENV_DIR." >&2
    exit 1
fi

printf '%s\n' "$ENV_PY"
