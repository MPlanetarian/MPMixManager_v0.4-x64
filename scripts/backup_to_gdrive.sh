#!/usr/bin/env bash
# MP_Mix_Manager_v0.3 - Google Drive Backup Runner

SCRIPT_DIR="$(dirname "${BASH_SOURCE[0]}")"
BACKUP_SUITE="$SCRIPT_DIR/scripts/backup_mix_archive.sh"

exec "$BACKUP_SUITE" --provider=gdrive --all "$@" || { echo "Error: backup_mix_archive.sh not found."; exit 1; }