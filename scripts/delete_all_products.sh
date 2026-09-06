#!/usr/bin/env bash
# Hard-delete ALL products (interactive yes/no).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND="$ROOT/backend"
PY="$BACKEND/.venv/bin/python"
if [[ ! -x "$PY" ]]; then
  echo "Backend venv not found at $PY. Run the Dev Launcher first-time setup." >&2
  exit 1
fi
cd "$BACKEND"
exec "$PY" -m app.scripts.delete_all_products "$@"
