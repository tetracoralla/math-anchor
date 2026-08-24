#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
VENV_DIR="$ROOT_DIR/.venv"
PATH_VALIDATOR="$ROOT_DIR/script/validate_repo_paths.py"

source "$ROOT_DIR/script/python_env.sh"
if ! resolve_math_anchor_python "to bootstrap Math Anchor"; then
  exit 1
fi
PYTHON="$RESOLVED_MATH_ANCHOR_PYTHON"

# Validate before creating the virtualenv or running pip. This rejects both
# existing and dangling symlinks, including any linked ancestor.
"$PYTHON" "$PATH_VALIDATOR" --root "$ROOT_DIR" "$VENV_DIR"

if [[ ! -x "$VENV_DIR/bin/python" ]]; then
  "$PYTHON" -m venv "$VENV_DIR"
elif ! "$VENV_DIR/bin/python" -c 'import encodings, sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' >/dev/null 2>&1; then
  echo "Rebuilding the unusable or outdated generated .venv with $PYTHON." >&2
  "$PYTHON" -m venv --clear "$VENV_DIR"
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
