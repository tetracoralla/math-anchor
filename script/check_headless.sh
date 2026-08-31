#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$ROOT_DIR"

"$ROOT_DIR/script/check_source_layout.sh" --development
"$ROOT_DIR/script/bootstrap.sh"
"$ROOT_DIR/.venv/bin/python" -m pytest
"$ROOT_DIR/.venv/bin/python" "$ROOT_DIR/script/check_source_safety.py"
"$ROOT_DIR/.venv/bin/python" "$ROOT_DIR/script/check_mcp.py" --source-runtime
"$ROOT_DIR/.venv/bin/python" "$ROOT_DIR/script/load_check.py" --calls 1000
"$ROOT_DIR/.venv/bin/python" "$ROOT_DIR/script/build_python_dist.py" build
"$ROOT_DIR/.venv/bin/python" "$ROOT_DIR/script/build_python_dist.py" verify

echo "Headless runtime checks passed."
