#!/usr/bin/env bash
# Ubuntu production ops menu (start/stop/deploy/logs)
set -euo pipefail
cd "$(dirname "$0")"

if command -v python3 >/dev/null 2>&1; then
  exec python3 scripts/prod_menu.py "$@"
fi
if command -v python >/dev/null 2>&1; then
  exec python scripts/prod_menu.py "$@"
fi

echo "Python 3 not found." >&2
exit 1
