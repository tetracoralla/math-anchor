#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLUGIN_RUNTIME_BUNDLE="$ROOT_DIR/plugins/zibetha/runtime/zibetha-runtime"
PLUGIN_RUNTIME="$PLUGIN_RUNTIME_BUNDLE/zibetha-runtime"
APP_BUNDLE="$ROOT_DIR/dist/Zibetha.app"
EXPECTED_ARCH="${ZIBETHA_EXPECTED_ARCH:-$(uname -m)}"

git -C "$ROOT_DIR" check-ignore -q "plugins/zibetha/runtime/"
if [[ -n "$(git -C "$ROOT_DIR" ls-files -- "plugins/zibetha/runtime/**")" ]]; then
  echo "Generated plugin runtime must not be tracked by git." >&2
  exit 1
fi

for required in \
  "$ROOT_DIR/requirements-runtime.lock" \
  "$ROOT_DIR/requirements-dev.lock" \
  "$ROOT_DIR/SECURITY.md" \
  "$ROOT_DIR/.github/workflows/ci.yml" \
  "$PLUGIN_RUNTIME_BUNDLE/THIRD_PARTY_NOTICES.txt" \
  "$PLUGIN_RUNTIME_BUNDLE/sbom.spdx.json"; do
  if [[ ! -s "$required" ]]; then
    echo "Required release material is missing: $required" >&2
    exit 1
  fi
done

"$ROOT_DIR/.venv/bin/python" "$ROOT_DIR/script/runtime_manifest.py" verify \
  --bundle "$PLUGIN_RUNTIME_BUNDLE" \
  --runtime "$PLUGIN_RUNTIME" \
  --lock "$ROOT_DIR/requirements-runtime.lock" \
  --source-root "$ROOT_DIR"

"$ROOT_DIR/.venv/bin/python" "$ROOT_DIR/script/generate_third_party_materials.py" \
  --lock "$ROOT_DIR/requirements-runtime.lock" \
  --project "$ROOT_DIR/pyproject.toml" \
  --bundle "$PLUGIN_RUNTIME_BUNDLE" \
  --runtime "$PLUGIN_RUNTIME" \
  --output-dir "$PLUGIN_RUNTIME_BUNDLE" \
  --verify-existing

"$ROOT_DIR/.venv/bin/python" "$ROOT_DIR/script/generate_third_party_materials.py" \
  --lock "$ROOT_DIR/requirements-dev.lock" \
  --project "$ROOT_DIR/pyproject.toml" \
  --extra dev \
  --validate-only

if ! file -b "$PLUGIN_RUNTIME" | grep -q "$EXPECTED_ARCH"; then
  echo "Packaged runtime does not contain expected architecture $EXPECTED_ARCH." >&2
  exit 1
fi

if [[ "${ZIBETHA_VERIFY_APP_BUNDLE:-0}" == "1" ]]; then
  if [[ ! -d "$APP_BUNDLE" ]]; then
    echo "Expected app bundle is missing: $APP_BUNDLE" >&2
    exit 1
  fi
  APP_BINARY="$APP_BUNDLE/Contents/MacOS/Zibetha"
  if ! file -b "$APP_BINARY" | grep -q "$EXPECTED_ARCH"; then
    echo "Packaged app does not contain expected architecture $EXPECTED_ARCH." >&2
    exit 1
  fi
  /usr/libexec/PlistBuddy -c "Print :CFBundleShortVersionString" "$APP_BUNDLE/Contents/Info.plist" >/dev/null
  /usr/libexec/PlistBuddy -c "Print :CFBundleVersion" "$APP_BUNDLE/Contents/Info.plist" >/dev/null
  APP_RUNTIME_BUNDLE="$APP_BUNDLE/Contents/Resources/Runtime/zibetha-runtime"
  "$ROOT_DIR/.venv/bin/python" "$ROOT_DIR/script/runtime_manifest.py" verify \
    --bundle "$APP_RUNTIME_BUNDLE" \
    --runtime "$APP_RUNTIME_BUNDLE/zibetha-runtime" \
    --lock "$ROOT_DIR/requirements-runtime.lock" \
    --source-root "$ROOT_DIR"
  "$ROOT_DIR/.venv/bin/python" "$ROOT_DIR/script/generate_third_party_materials.py" \
    --lock "$ROOT_DIR/requirements-runtime.lock" \
    --project "$ROOT_DIR/pyproject.toml" \
    --bundle "$APP_RUNTIME_BUNDLE" \
    --runtime "$APP_RUNTIME_BUNDLE/zibetha-runtime" \
    --output-dir "$APP_RUNTIME_BUNDLE" \
    --verify-existing
fi

echo "Release hygiene passed for source distribution and $EXPECTED_ARCH generated artifacts."
