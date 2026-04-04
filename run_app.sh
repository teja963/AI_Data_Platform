#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEFAULT_VENV="$ROOT_DIR/../myenv"

if [[ -n "${VIRTUAL_ENV:-}" && -x "$VIRTUAL_ENV/bin/python" ]]; then
  PYTHON_BIN="$VIRTUAL_ENV/bin/python"
elif [[ -x "$DEFAULT_VENV/bin/python" ]]; then
  PYTHON_BIN="$DEFAULT_VENV/bin/python"
else
  echo "No virtual environment Python found. Activate your venv or create ../myenv first." >&2
  exit 1
fi

exec "$PYTHON_BIN" -m streamlit run "$ROOT_DIR/app.py" --server.runOnSave true --server.fileWatcherType watchdog
