#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/script/swift_env.sh"
configure_swift_environment "$ROOT_DIR"

if [[ ! -x "$ROOT_DIR/.venv/bin/python" ]]; then
  "$ROOT_DIR/script/bootstrap.sh"
fi

"$ROOT_DIR/script/package_runtime.sh"

ZIBETHA_VERIFY_PACKAGED_RUNTIME=1 "$ROOT_DIR/.venv/bin/python" -m pytest
"$ROOT_DIR/.venv/bin/python" "$ROOT_DIR/script/check_source_safety.py"
"$ROOT_DIR/script/check_swift_store.sh"
swift build --package-path "$ROOT_DIR"
"$ROOT_DIR/.venv/bin/python" "$ROOT_DIR/script/check_mcp.py"
"$ROOT_DIR/.venv/bin/python" "$ROOT_DIR/script/check_plugin.py"
"$ROOT_DIR/script/check_release_hygiene.sh"
