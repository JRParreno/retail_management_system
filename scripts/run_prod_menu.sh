#!/usr/bin/env bash
# Ubuntu production ops menu (start/stop/deploy/logs)
#
# Run from repo root OR from this scripts/ folder:
#   ./scripts/run_prod_menu.sh
#   cd scripts && bash run_prod_menu.sh
#
# If ./run_prod_menu.sh says "Permission denied", use bash instead:
#   bash run_prod_menu.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
MENU="$ROOT/scripts/prod_menu.py"

cd "$ROOT"

if [[ ! -f "$MENU" ]]; then
  echo "Cannot find $MENU (expected repo root: $ROOT)" >&2
  exit 1
fi

if command -v python3 >/dev/null 2>&1; then
  exec python3 "$MENU" "$@"
fi
if command -v python >/dev/null 2>&1; then
  exec python "$MENU" "$@"
fi

echo "Python 3 not found." >&2
exit 1
