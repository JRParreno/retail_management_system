#!/usr/bin/env bash
# Ubuntu production ops menu (start/stop/deploy/logs)
# Usage: ./scripts/run_prod_menu.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if command -v python3 >/dev/null 2>&1; then
  exec python3 scripts/prod_menu.py "$@"
fi
if command -v python >/dev/null 2>&1; then
  exec python scripts/prod_menu.py "$@"
fi

echo "Python 3 not found." >&2
exit 1
