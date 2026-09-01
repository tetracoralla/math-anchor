#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$ROOT_DIR"

"$ROOT_DIR/script/package_runtime.sh"
VERSION="$("$ROOT_DIR/.venv/bin/python" "$ROOT_DIR/script/release_metadata.py" version --root "$ROOT_DIR")"
INSTALL_RESULT="$(codex plugin add math-anchor@openadam --json)"
SERVER_RESULT="$(codex mcp get math-anchor --json)"

INSTALLED_PLUGIN="$(printf '%s' "$INSTALL_RESULT" | "$ROOT_DIR/.venv/bin/python" -c '
import json, sys
from pathlib import Path
value = json.load(sys.stdin)
expected = sys.argv[1]
if value.get("pluginId") != "math-anchor@openadam" or value.get("version") != expected:
    raise SystemExit(f"Codex installed an unexpected Plugin identity: {value}")
installed_path = value.get("installedPath")
if not isinstance(installed_path, str) or not installed_path.strip():
    raise SystemExit(f"Codex did not report the installed Plugin path: {value}")
print(Path(installed_path).expanduser().resolve())
' "$VERSION")"

printf '%s' "$SERVER_RESULT" | \
  "$ROOT_DIR/.venv/bin/python" "$ROOT_DIR/script/check_installed_plugin.py" \
  --source-plugin "$ROOT_DIR/plugins/math-anchor" \
  --installed-plugin "$INSTALLED_PLUGIN" \
  --expected-version "$VERSION" \
  --server-json -
"$ROOT_DIR/.venv/bin/python" "$ROOT_DIR/script/check_mcp.py" \
  --plugin-root "$INSTALLED_PLUGIN"

PROMPT_INPUT="$(codex debug prompt-input 'Use Math Anchor for one reliability-sensitive calculation.')"
printf '%s' "$PROMPT_INPUT" | "$ROOT_DIR/.venv/bin/python" -c '
import json, sys
value = json.load(sys.stdin)
expected = sys.argv[1]
text = "\n".join(
    item.get("content", [{}])[0].get("text", "")
    for item in value
    if isinstance(item, dict) and isinstance(item.get("content"), list) and item.get("content")
)
needle = f"/math-anchor/{expected}/skills/calculate/SKILL.md"
if needle not in text:
    raise SystemExit(f"fresh Codex process did not load the installed Math Anchor Skill at {needle}")
' "$VERSION"

printf 'Math Anchor Plugin %s installed and verified from a fresh Codex process: %s\n' \
  "$VERSION" "$INSTALLED_PLUGIN"
