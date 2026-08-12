#!/usr/bin/env bash
# Ubuntu production Nginx setup (by IP, no domain required)
# Usage: sudo ./scripts/run_ubuntu_https.sh --yes
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
SCRIPT="$ROOT/scripts/run_ubuntu_https.sh"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Re-running with sudo…"
  exec sudo -E "$SCRIPT" "$@"
fi

if command -v python3 >/dev/null 2>&1; then
  exec python3 scripts/ubuntu_https_setup.py "$@"
fi
if command -v python >/dev/null 2>&1; then
  exec python scripts/ubuntu_https_setup.py "$@"
fi

echo "Python 3 not found." >&2
exit 1
