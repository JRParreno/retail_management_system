#!/usr/bin/env bash
# Postgres backup / restore helper (see scripts/db_backup.py)
#
# Run from repo root OR scripts/:
#   ./scripts/run_db_backup.sh install-cron
#   bash scripts/run_db_backup.sh install-cron
#
# If ./ says "Permission denied", use bash (or: chmod +x scripts/run_db_backup.sh)
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

if command -v python3 >/dev/null 2>&1; then
  exec python3 "$ROOT/scripts/db_backup.py" "$@"
fi
if command -v python >/dev/null 2>&1; then
  exec python "$ROOT/scripts/db_backup.py" "$@"
fi

echo "Python 3 not found." >&2
exit 1
