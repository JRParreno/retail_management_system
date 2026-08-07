#!/usr/bin/env bash
# Ubuntu / Linux / macOS launcher for MotoShop RMS menu
set -euo pipefail
cd "$(dirname "$0")"

# Prefer Node 20+ from nvm (Tailwind 4 / Next 15 need it)
export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
if [ -s "$NVM_DIR/nvm.sh" ]; then
  # shellcheck disable=SC1091
  . "$NVM_DIR/nvm.sh"
  nvm use 20 >/dev/null 2>&1 || true
fi

if command -v python3 >/dev/null 2>&1; then
  exec python3 scripts/dev_menu.py "$@"
elif command -v python >/dev/null 2>&1; then
  exec python scripts/dev_menu.py "$@"
else
  echo "Python 3 not found. Install with: sudo apt install python3 python3-venv"
  exit 1
fi
