#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
PLUGIN_RUNTIME_BUNDLE="$ROOT_DIR/plugins/math-anchor/runtime/math-anchor-runtime"
PLUGIN_RUNTIME="$PLUGIN_RUNTIME_BUNDLE/math-anchor-runtime"
APP_BUNDLE="$ROOT_DIR/dist/Math Anchor.app"
EXPECTED_ARCH="${MATH_ANCHOR_EXPECTED_ARCH:-$(uname -m)}"

"$ROOT_DIR/script/check_source_layout.sh" --development

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

PROJECT_VERSION="$(
  "$ROOT_DIR/.venv/bin/python" "$ROOT_DIR/script/release_metadata.py" version \
    --root "$ROOT_DIR"
)"
METADATA_ARGUMENTS=(
  check
  --root "$ROOT_DIR"
  --runtime-bundle "$PLUGIN_RUNTIME_BUNDLE"
)
if [[ -n "${MATH_ANCHOR_APP_VERSION:-}" ]]; then
  METADATA_ARGUMENTS+=(--expected-version "$MATH_ANCHOR_APP_VERSION")
fi
"$ROOT_DIR/.venv/bin/python" "$ROOT_DIR/script/release_metadata.py" \
  "${METADATA_ARGUMENTS[@]}"

"$ROOT_DIR/.venv/bin/python" "$ROOT_DIR/script/runtime_manifest.py" verify \
  --bundle "$PLUGIN_RUNTIME_BUNDLE" \
  --runtime "$PLUGIN_RUNTIME" \
  --lock "$ROOT_DIR/requirements-runtime.lock" \
  --source-root "$ROOT_DIR" \
  --version "$PROJECT_VERSION"

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

if [[ "${MATH_ANCHOR_VERIFY_APP_BUNDLE:-0}" == "1" ]]; then
  if [[ ! -d "$APP_BUNDLE" ]]; then
    echo "Expected app bundle is missing: $APP_BUNDLE" >&2
    exit 1
  fi
  APP_BINARY="$APP_BUNDLE/Contents/MacOS/MathAnchor"
  if ! file -b "$APP_BINARY" | grep -q "$EXPECTED_ARCH"; then
    echo "Packaged app does not contain expected architecture $EXPECTED_ARCH." >&2
    exit 1
  fi
  APP_RUNTIME_BUNDLE="$APP_BUNDLE/Contents/Resources/Runtime/math-anchor-runtime"
  APP_METADATA_ARGUMENTS=(
    check
    --root "$ROOT_DIR"
    --runtime-bundle "$PLUGIN_RUNTIME_BUNDLE"
    --app-bundle "$APP_BUNDLE"
  )
  if [[ -n "${MATH_ANCHOR_APP_VERSION:-}" ]]; then
    APP_METADATA_ARGUMENTS+=(--expected-version "$MATH_ANCHOR_APP_VERSION")
  fi
  if [[ -n "${MATH_ANCHOR_BUILD_NUMBER:-}" ]]; then
    APP_METADATA_ARGUMENTS+=(--expected-build "$MATH_ANCHOR_BUILD_NUMBER")
  fi
  "$ROOT_DIR/.venv/bin/python" "$ROOT_DIR/script/release_metadata.py" \
    "${APP_METADATA_ARGUMENTS[@]}"
  "$ROOT_DIR/.venv/bin/python" "$ROOT_DIR/script/runtime_manifest.py" verify \
    --bundle "$APP_RUNTIME_BUNDLE" \
    --runtime "$APP_RUNTIME_BUNDLE/math-anchor-runtime" \
    --lock "$ROOT_DIR/requirements-runtime.lock" \
    --source-root "$ROOT_DIR" \
    --version "$PROJECT_VERSION"
  "$ROOT_DIR/.venv/bin/python" "$ROOT_DIR/script/generate_third_party_materials.py" \
    --lock "$ROOT_DIR/requirements-runtime.lock" \
    --project "$ROOT_DIR/pyproject.toml" \
    --bundle "$APP_RUNTIME_BUNDLE" \
    --runtime "$APP_RUNTIME_BUNDLE/math-anchor-runtime" \
    --output-dir "$APP_RUNTIME_BUNDLE" \
    --verify-existing
fi

echo "Release hygiene passed for source distribution and $EXPECTED_ARCH generated artifacts."
