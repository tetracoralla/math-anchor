#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="$ROOT_DIR/.venv"

PYTHON=""
for candidate in "${MATH_ANCHOR_PYTHON:-}" python3 python3.13 python3.12 python3.11; do
  [[ -n "$candidate" ]] || continue
  if [[ -x "$candidate" ]]; then
    candidate_path="$candidate"
  elif command -v "$candidate" >/dev/null 2>&1; then
    candidate_path="$(command -v "$candidate")"
  else
    continue
  fi
  if "$candidate_path" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)'; then
    PYTHON="$candidate_path"
    break
  fi
done

if [[ -z "$PYTHON" ]]; then
  echo "Python 3.11 or newer is required." >&2
  exit 1
fi

if [[ -L "$VENV_DIR" && -d "$VENV_DIR" ]]; then
  echo "The repository virtualenv must not be a symbolic link to an existing environment: $VENV_DIR" >&2
  exit 1
fi

if [[ ! -x "$VENV_DIR/bin/python" ]]; then
  "$PYTHON" -m venv "$VENV_DIR"
elif ! "$VENV_DIR/bin/python" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)'; then
  echo "The existing .venv uses Python older than 3.11. Recreate it with script/bootstrap.sh." >&2
  exit 1
fi

"$VENV_DIR/bin/python" -m pip install \
  --disable-pip-version-check \
  --timeout 60 \
  --retries 8 \
  --require-hashes \
  --requirement "$ROOT_DIR/requirements-dev.lock"
"$VENV_DIR/bin/python" -m pip install \
  --disable-pip-version-check \
  --no-build-isolation \
  --no-deps \
  -e "$ROOT_DIR"
