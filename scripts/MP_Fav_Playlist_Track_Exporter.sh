#!/usr/bin/env bash
# ==============================================================================
# MP_Mix_Manager - MP Fav Playlist Track Exporter
#
# Exports the MP Audio Player Favorites playlist to a local folder or an SMB
# share, writes an MP Mix Manager tracklist plus an m3u8 playlist, and can
# create a matching Traktor playlist from a Traktor History file.
#
# The work is done by MP_Fav_Playlist_Track_Exporter.py next to this script.
# ==============================================================================

set -o pipefail 2>/dev/null || true

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
PY_EXPORTER="$SCRIPT_DIR/MP_Fav_Playlist_Track_Exporter.py"

if [ ! -f "$PY_EXPORTER" ]; then
    for dir in "$SCRIPT_DIR" "$PWD/scripts" "$PWD"; do
        if [ -f "$dir/MP_Fav_Playlist_Track_Exporter.py" ]; then
            PY_EXPORTER="$dir/MP_Fav_Playlist_Track_Exporter.py"
            break
        fi
    done
fi

if [ ! -f "$PY_EXPORTER" ]; then
    echo "Error: MP_Fav_Playlist_Track_Exporter.py was not found in $SCRIPT_DIR." >&2
    exit 1
fi

PYTHON_CMD=""
for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then
        PYTHON_CMD="$candidate"
        break
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    for candidate in /usr/bin/python3 /usr/local/bin/python3 /opt/homebrew/bin/python3; do
        if [ -x "$candidate" ]; then
            PYTHON_CMD="$candidate"
            break
        fi
    done
fi

if [ -z "$PYTHON_CMD" ]; then
    echo "Error: python3 is required by MP_Fav_Playlist_Track_Exporter.sh." >&2
    exit 1
fi

exec "$PYTHON_CMD" "$PY_EXPORTER" "$@"
