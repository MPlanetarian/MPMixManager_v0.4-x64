#!/usr/bin/env bash
# ==============================================================================
# MP_Mix_Manager_v0.3 - Mix Archive Folder Playlists Generator Launcher
# ==============================================================================
SCRIPT_DIR="$(dirname "$(dirname "${BASH_SOURCE[0]}")")"
PY_SCRIPT="$SCRIPT_DIR/scripts/generate_archive_folder_playlists.py"
exec python3 "$PY_SCRIPT" "$@"