#!/usr/bin/env bash
# Postgres backup / restore helper (see scripts/db_backup.py)
set -euo pipefail
cd "$(dirname "$0")"

if command -v python3 >/dev/null 2>&1; then
  exec python3 scripts/db_backup.py "$@"
fi
if command -v python >/dev/null 2>&1; then
  exec python scripts/db_backup.py "$@"
fi

echo "Python 3 not found." >&2
exit 1
