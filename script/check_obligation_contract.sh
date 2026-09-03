#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$ROOT_DIR"

"$ROOT_DIR/script/check_source_layout.sh" --development
"$ROOT_DIR/script/bootstrap.sh"
"$ROOT_DIR/.venv/bin/python" "$ROOT_DIR/script/check_obligations.py"
