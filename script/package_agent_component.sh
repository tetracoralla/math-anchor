#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$ROOT_DIR"

if [[ -z "${OPENADAM_COMPONENT_STAGE:-}" ]]; then
  echo "OPENADAM_COMPONENT_STAGE is required." >&2
  exit 2
fi
case "$OPENADAM_COMPONENT_STAGE" in
  /*) ;;
  *)
    echo "OPENADAM_COMPONENT_STAGE must be an absolute path." >&2
    exit 2
    ;;
esac
if [[ ! -d "$OPENADAM_COMPONENT_STAGE" ]] || [[ -L "$OPENADAM_COMPONENT_STAGE" ]]; then
  echo "OPENADAM_COMPONENT_STAGE must be an existing real directory." >&2
  exit 2
fi
if find "$OPENADAM_COMPONENT_STAGE" -mindepth 1 -print -quit | grep -q .; then
  echo "OPENADAM_COMPONENT_STAGE must be empty." >&2
  exit 2
fi

"$ROOT_DIR/script/package_runtime.sh"
"$ROOT_DIR/.venv/bin/python" "$ROOT_DIR/script/check_plugin.py"
PROJECT_VERSION="$("$ROOT_DIR/.venv/bin/python" "$ROOT_DIR/script/release_metadata.py" version --root "$ROOT_DIR")"
HOST_PLUGIN_VERSION="$("$ROOT_DIR/.venv/bin/python" -c \
  'import json, pathlib, sys; print(json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))["version"])' \
  "$ROOT_DIR/integrations/agent-host/plugin.json")"
if [[ "$HOST_PLUGIN_VERSION" != "$PROJECT_VERSION" ]]; then
  echo "Agent Host plugin version $HOST_PLUGIN_VERSION does not match project version $PROJECT_VERSION." >&2
  exit 1
fi

MARKETPLACE_STAGE="$OPENADAM_COMPONENT_STAGE/marketplace"
mkdir -p "$MARKETPLACE_STAGE/.agents/plugins" "$MARKETPLACE_STAGE/plugins"
cp "$ROOT_DIR/integrations/agent-host/marketplace.json" "$MARKETPLACE_STAGE/.agents/plugins/marketplace.json"
cp -R "$ROOT_DIR/plugins/math-anchor" "$MARKETPLACE_STAGE/plugins/math-anchor-obligation-runtime"
cp "$ROOT_DIR/integrations/agent-host/plugin.json" \
  "$MARKETPLACE_STAGE/plugins/math-anchor-obligation-runtime/.codex-plugin/plugin.json"

if find "$OPENADAM_COMPONENT_STAGE" -type l -print -quit | grep -q .; then
  echo "The staged component must not contain symbolic links." >&2
  exit 1
fi
