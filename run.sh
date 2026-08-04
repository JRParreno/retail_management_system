#!/usr/bin/env bash
# Ubuntu / Linux / macOS launcher for MotoShop RMS menu
set -euo pipefail
cd "$(dirname "$0")"
if command -v python3 >/dev/null 2>&1; then
  exec python3 scripts/dev_menu.py "$@"
elif command -v python >/dev/null 2>&1; then
  exec python scripts/dev_menu.py "$@"
else
  echo "Python 3 not found. Install with: sudo apt install python3 python3-venv"
  exit 1
fi
