#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$ROOT_DIR"
VENV_PYTHON="$ROOT_DIR/.venv/bin/python"
PLUGIN_RUNTIME_DIR="$ROOT_DIR/plugins/math-anchor/runtime"
PLUGIN_RUNTIME_BUNDLE="$PLUGIN_RUNTIME_DIR/math-anchor-runtime"
PLUGIN_RUNTIME="$PLUGIN_RUNTIME_BUNDLE/math-anchor-runtime"
PROJECT_LICENSE="$ROOT_DIR/LICENSE"
PROJECT_NOTICE="$ROOT_DIR/NOTICE"
BUNDLED_LICENSE="$PLUGIN_RUNTIME_BUNDLE/LICENSE"
BUNDLED_NOTICE="$PLUGIN_RUNTIME_BUNDLE/NOTICE"
PYTHON_RUNTIME_LOADER="$PLUGIN_RUNTIME_BUNDLE/_internal/Python"
PYTHON_RUNTIME_LOADER_MATERIALIZED="$PLUGIN_RUNTIME_BUNDLE/_internal/Python.materialized"
PYTHON_FRAMEWORK="$PLUGIN_RUNTIME_BUNDLE/_internal/Python.framework"
RUNTIME_LOCK="$ROOT_DIR/requirements-runtime.lock"
BUILD_DIR="$ROOT_DIR/.build/runtime-package"
DIST_DIR="$BUILD_DIR/dist"
WORK_DIR="$BUILD_DIR/work"
SPEC_DIR="$BUILD_DIR/spec"
PYINSTALLER_CONFIG_DIR="$BUILD_DIR/cache"
DIST_RUNTIME_BUNDLE="$DIST_DIR/math-anchor-runtime"
WORK_RUNTIME_DIR="$WORK_DIR/math-anchor-runtime"
SPEC_FILE="$SPEC_DIR/math-anchor-runtime.spec"
PATH_VALIDATOR="$ROOT_DIR/script/validate_repo_paths.py"
export PYINSTALLER_CONFIG_DIR

source "$ROOT_DIR/script/python_env.sh"
if ! resolve_math_anchor_python "to validate packaging paths"; then
  exit 1
fi
PATH_VALIDATION_PYTHON="$RESOLVED_MATH_ANCHOR_PYTHON"

validate_write_paths() {
  "$PATH_VALIDATION_PYTHON" "$PATH_VALIDATOR" --root "$ROOT_DIR" \
    "$ROOT_DIR/.venv" \
    "$BUILD_DIR" \
    "$DIST_DIR" \
    "$WORK_DIR" \
    "$SPEC_DIR" \
    "$PYINSTALLER_CONFIG_DIR" \
    "$DIST_RUNTIME_BUNDLE" \
    "$WORK_RUNTIME_DIR" \
    "$SPEC_FILE" \
    "$PLUGIN_RUNTIME_DIR" \
    "$PLUGIN_RUNTIME_BUNDLE" \
    "$PLUGIN_RUNTIME" \
    "$BUNDLED_LICENSE" \
    "$BUNDLED_NOTICE" \
    "$PYTHON_RUNTIME_LOADER_MATERIALIZED"
}

# This must run before bootstrap, directory creation, or any generated-path read.
validate_write_paths

# Reinstall the project before inspecting or building generated runtime
# artifacts. A copied/File Provider virtualenv is not relocatable, and Python
# may ignore editable-install .pth metadata carrying the macOS hidden flag.
# The locked dependency install is idempotent; the project wheel copy makes
# this entrypoint self-healing after a repository move and current after edits.
"$ROOT_DIR/script/bootstrap.sh"
PROJECT_VERSION="$(
  "$VENV_PYTHON" "$ROOT_DIR/script/release_metadata.py" version --root "$ROOT_DIR"
)"
PYTHON_FRAMEWORK_VERSION="$(
  "$VENV_PYTHON" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")'
)"

needs_build=0
if [[ ! -x "$PLUGIN_RUNTIME" ]]; then
  needs_build=1
elif ! "$VENV_PYTHON" "$ROOT_DIR/script/runtime_manifest.py" verify \
  --bundle "$PLUGIN_RUNTIME_BUNDLE" \
  --runtime "$PLUGIN_RUNTIME" \
  --lock "$RUNTIME_LOCK" \
  --source-root "$ROOT_DIR" \
  --version "$PROJECT_VERSION" >/dev/null 2>&1; then
  needs_build=1
elif find "$ROOT_DIR/src/math_anchor" "$ROOT_DIR/legal" "$PROJECT_LICENSE" "$PROJECT_NOTICE" \
  "$ROOT_DIR/pyproject.toml" "$ROOT_DIR/script/package_runtime.sh" \
  "$ROOT_DIR/script/generate_third_party_materials.py" "$ROOT_DIR/script/release_metadata.py" \
  "$ROOT_DIR/script/runtime_manifest.py" \
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

mkdir -p "$DIST_DIR" "$WORK_DIR" "$SPEC_DIR" "$PYINSTALLER_CONFIG_DIR"
"$VENV_PYTHON" -m PyInstaller \
  --noconfirm \
  --clean \
  --onedir \
  --name math-anchor-runtime \
  --distpath "$DIST_DIR" \
  --workpath "$WORK_DIR" \
  --specpath "$SPEC_DIR" \
  --collect-data pint \
  --collect-submodules math_anchor \
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
  "$ROOT_DIR/src/math_anchor/bundled_runtime.py"

validate_write_paths
mkdir -p "$PLUGIN_RUNTIME_DIR"
validate_write_paths
rm -rf "$PLUGIN_RUNTIME_BUNDLE"
ditto "$DIST_RUNTIME_BUNDLE" "$PLUGIN_RUNTIME_BUNDLE"
chmod +x "$PLUGIN_RUNTIME"
if [[ -L "$PYTHON_RUNTIME_LOADER" ]]; then
  cp -pL "$PYTHON_RUNTIME_LOADER" "$PYTHON_RUNTIME_LOADER_MATERIALIZED"
  if [[ ! -f "$PYTHON_RUNTIME_LOADER_MATERIALIZED" ]] || [[ -L "$PYTHON_RUNTIME_LOADER_MATERIALIZED" ]]; then
    echo "Failed to materialize the packaged Python loader." >&2
    exit 1
  fi
  mv -f "$PYTHON_RUNTIME_LOADER_MATERIALIZED" "$PYTHON_RUNTIME_LOADER"
fi
python_loader_count=0
if [[ -e "$PYTHON_RUNTIME_LOADER" ]]; then
  if [[ ! -f "$PYTHON_RUNTIME_LOADER" ]] || [[ -L "$PYTHON_RUNTIME_LOADER" ]]; then
    echo "The packaged Python loader must be a regular file for Codex installation." >&2
    exit 1
  fi
  python_loader_count=$((python_loader_count + 1))
fi
while IFS= read -r -d '' python_dylib; do
  if [[ ! -f "$python_dylib" ]] || [[ -L "$python_dylib" ]]; then
    echo "The packaged Python shared library must be a regular file: $python_dylib" >&2
    exit 1
  fi
  python_loader_count=$((python_loader_count + 1))
done < <(find "$PLUGIN_RUNTIME_BUNDLE/_internal" -type f -name 'libpython*.dylib' -print0)
if [[ "$python_loader_count" -eq 0 ]]; then
  echo "The packaged runtime does not contain a supported Python loader." >&2
  exit 1
fi

# Codex's Plugin copier intentionally omits symbolic links. Homebrew Python
# frameworks include three nonessential convenience aliases, so remove only
# those known aliases after materializing the loader above and fail closed if
# PyInstaller introduces any other link that could make the installed copy
# differ from the verified bundle.
remove_framework_alias() {
  local alias_path="$1"
  local expected_target="$2"
  local actual_target
  if [[ ! -L "$alias_path" ]]; then
    return
  fi
  actual_target="$(readlink "$alias_path")"
  if [[ "$actual_target" != "$expected_target" ]]; then
    echo "Unexpected Python framework alias target: $alias_path -> $actual_target" >&2
    exit 1
  fi
  rm "$alias_path"
}
remove_framework_alias "$PYTHON_FRAMEWORK/Python" "Versions/Current/Python"
remove_framework_alias "$PYTHON_FRAMEWORK/Resources" "Versions/Current/Resources"
remove_framework_alias "$PYTHON_FRAMEWORK/Versions/Current" "$PYTHON_FRAMEWORK_VERSION"
remaining_symlink="$(find "$PLUGIN_RUNTIME_BUNDLE" -type l -print -quit)"
if [[ -n "$remaining_symlink" ]]; then
  echo "Packaged runtime contains a symbolic link that Codex installation would omit: $remaining_symlink" >&2
  exit 1
fi

cp "$PROJECT_LICENSE" "$BUNDLED_LICENSE"
cp "$PROJECT_NOTICE" "$BUNDLED_NOTICE"
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
  --version "$PROJECT_VERSION"
"$VENV_PYTHON" "$ROOT_DIR/script/runtime_manifest.py" verify \
  --bundle "$PLUGIN_RUNTIME_BUNDLE" \
  --runtime "$PLUGIN_RUNTIME" \
  --lock "$RUNTIME_LOCK" \
  --source-root "$ROOT_DIR" \
  --version "$PROJECT_VERSION"
