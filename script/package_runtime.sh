#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PYTHON="$ROOT_DIR/.venv/bin/python"
PLUGIN_RUNTIME_DIR="$ROOT_DIR/plugins/zibetha/runtime"
PLUGIN_RUNTIME_BUNDLE="$PLUGIN_RUNTIME_DIR/zibetha-runtime"
PLUGIN_RUNTIME="$PLUGIN_RUNTIME_BUNDLE/zibetha-runtime"
RUNTIME_LOCK="$ROOT_DIR/requirements-runtime.lock"
BUILD_DIR="$ROOT_DIR/.build/runtime-package"
DIST_DIR="$BUILD_DIR/dist"
WORK_DIR="$BUILD_DIR/work"
SPEC_DIR="$BUILD_DIR/spec"
PYINSTALLER_CONFIG_DIR="$BUILD_DIR/cache"
export PYINSTALLER_CONFIG_DIR

if [[ ! -x "$VENV_PYTHON" ]] || ! "$VENV_PYTHON" -c 'import PyInstaller' >/dev/null 2>&1; then
  "$ROOT_DIR/script/bootstrap.sh"
fi

needs_build=0
if [[ ! -x "$PLUGIN_RUNTIME" ]]; then
  needs_build=1
elif ! "$VENV_PYTHON" "$ROOT_DIR/script/runtime_manifest.py" verify \
  --bundle "$PLUGIN_RUNTIME_BUNDLE" \
  --runtime "$PLUGIN_RUNTIME" \
  --lock "$RUNTIME_LOCK" \
  --source-root "$ROOT_DIR" >/dev/null 2>&1; then
  needs_build=1
elif find "$ROOT_DIR/src/zibetha" "$ROOT_DIR/legal" "$ROOT_DIR/LICENSE" \
  "$ROOT_DIR/pyproject.toml" "$ROOT_DIR/script/package_runtime.sh" \
  "$ROOT_DIR/script/generate_third_party_materials.py" "$ROOT_DIR/script/runtime_manifest.py" \
  "$RUNTIME_LOCK" \
  -type f \
  ! -path '*/__pycache__/*' \
  ! -name '*.pyc' \
  -newer "$PLUGIN_RUNTIME" \
  -print -quit | grep -q .; then
  needs_build=1
fi

if [[ "$needs_build" -eq 0 ]]; then
  exit 0
fi

mkdir -p "$PLUGIN_RUNTIME_DIR" "$DIST_DIR" "$WORK_DIR" "$SPEC_DIR" "$PYINSTALLER_CONFIG_DIR"
"$VENV_PYTHON" -m PyInstaller \
  --noconfirm \
  --clean \
  --onedir \
  --name zibetha-runtime \
  --distpath "$DIST_DIR" \
  --workpath "$WORK_DIR" \
  --specpath "$SPEC_DIR" \
  --collect-data pint \
  --collect-submodules zibetha \
  --exclude-module coverage \
  --exclude-module _pytest \
  --exclude-module iniconfig \
  --exclude-module packaging \
  --exclude-module pluggy \
  --exclude-module py \
  --exclude-module pygments \
  --exclude-module pytest \
  --exclude-module pytest_cov \
  --exclude-module scipy \
  --exclude-module setuptools \
  --exclude-module sympy.testing \
  "$ROOT_DIR/src/zibetha/bundled_runtime.py"

if [[ "$PLUGIN_RUNTIME_BUNDLE" != "$ROOT_DIR/plugins/zibetha/runtime/zibetha-runtime" ]]; then
  echo "Refusing to replace an unexpected plugin runtime: $PLUGIN_RUNTIME_BUNDLE" >&2
  exit 1
fi
if [[ -L "$PLUGIN_RUNTIME_BUNDLE" ]]; then
  echo "Refusing to replace a symbolic-link plugin runtime: $PLUGIN_RUNTIME_BUNDLE" >&2
  exit 1
fi
rm -rf "$PLUGIN_RUNTIME_BUNDLE"
ditto "$DIST_DIR/zibetha-runtime" "$PLUGIN_RUNTIME_BUNDLE"
chmod +x "$PLUGIN_RUNTIME"
"$VENV_PYTHON" "$ROOT_DIR/script/generate_third_party_materials.py" \
  --lock "$RUNTIME_LOCK" \
  --project "$ROOT_DIR/pyproject.toml" \
  --bundle "$PLUGIN_RUNTIME_BUNDLE" \
  --runtime "$PLUGIN_RUNTIME" \
  --output-dir "$PLUGIN_RUNTIME_BUNDLE"
"$VENV_PYTHON" "$ROOT_DIR/script/runtime_manifest.py" write \
  --bundle "$PLUGIN_RUNTIME_BUNDLE" \
  --runtime "$PLUGIN_RUNTIME" \
  --lock "$RUNTIME_LOCK" \
  --source-root "$ROOT_DIR" \
  --version "0.1.0"
"$VENV_PYTHON" "$ROOT_DIR/script/runtime_manifest.py" verify \
  --bundle "$PLUGIN_RUNTIME_BUNDLE" \
  --runtime "$PLUGIN_RUNTIME" \
  --lock "$RUNTIME_LOCK" \
  --source-root "$ROOT_DIR"
