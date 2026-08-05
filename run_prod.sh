#!/usr/bin/env bash
# Ubuntu / Linux production deploy / restart
set -euo pipefail
cd "$(dirname "$0")"
if command -v python3 >/dev/null 2>&1; then
  exec python3 scripts/prod_deploy.py "$@"
fi
if command -v python >/dev/null 2>&1; then
  exec python scripts/prod_deploy.py "$@"
fi
echo "Python 3 not found. Install Python 3 and try again." >&2
exit 1
