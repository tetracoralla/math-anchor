#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
MODE="${1:-run}"
APP_DISPLAY_NAME="Math Anchor"
APP_EXECUTABLE="MathAnchor"
PRODUCTION_BUNDLE_ID="com.openadam.mathanchor"
DEVELOPMENT_BUNDLE_ID="com.openadam.mathanchor.development"
MIN_SYSTEM_VERSION="14.0"
APP_VERSION_OVERRIDE="${MATH_ANCHOR_APP_VERSION:-}"
BUILD_NUMBER="${MATH_ANCHOR_BUILD_NUMBER:-1}"
BUILD_CONFIGURATION="${MATH_ANCHOR_BUILD_CONFIGURATION:-debug}"

if [[ "$BUILD_CONFIGURATION" != "debug" && "$BUILD_CONFIGURATION" != "release" ]]; then
  echo "MATH_ANCHOR_BUILD_CONFIGURATION must be debug or release." >&2
  exit 2
fi
BUNDLE_ID="$PRODUCTION_BUNDLE_ID"
if [[ "$BUILD_CONFIGURATION" == "debug" ]]; then
  BUNDLE_ID="$DEVELOPMENT_BUNDLE_ID"
fi
if [[ ! "$BUILD_NUMBER" =~ ^[1-9][0-9]*$ ]]; then
  echo "MATH_ANCHOR_BUILD_NUMBER must be a positive integer." >&2
  exit 2
fi

DIST_DIR="$ROOT_DIR/dist"
APP_BUNDLE="$DIST_DIR/$APP_DISPLAY_NAME.app"
EXPECTED_BUNDLE="$ROOT_DIR/dist/Math Anchor.app"
APP_CONTENTS="$APP_BUNDLE/Contents"
APP_MACOS="$APP_CONTENTS/MacOS"
APP_BINARY="$APP_MACOS/$APP_EXECUTABLE"
INFO_PLIST="$APP_CONTENTS/Info.plist"
APP_RESOURCES="$APP_CONTENTS/Resources"
APP_RUNTIME_DIR="$APP_RESOURCES/Runtime"
APP_RUNTIME_BUNDLE="$APP_RUNTIME_DIR/math-anchor-runtime"
APP_RUNTIME="$APP_RUNTIME_BUNDLE/math-anchor-runtime"
APP_ICON="$APP_RESOURCES/AppIcon.icns"
PATH_VALIDATOR="$ROOT_DIR/script/validate_repo_paths.py"
PROCESS_CONTROL="$ROOT_DIR/script/app_processes.sh"
APP_RUNTIME_CHECK="$ROOT_DIR/script/check_app_bundle_runtime.py"

# This must run before the Swift module-cache creation, bootstrap, or any
# rm -rf / mkdir -p / ditto on the app bundle subtree.
"$ROOT_DIR/script/check_source_layout.sh" --development
source "$ROOT_DIR/script/python_env.sh"
if ! resolve_math_anchor_python "to validate app bundle paths"; then
  exit 1
fi
PATH_VALIDATION_PYTHON="$RESOLVED_MATH_ANCHOR_PYTHON"
"$PATH_VALIDATION_PYTHON" "$PATH_VALIDATOR" --root "$ROOT_DIR" \
  "$DIST_DIR" \
  "$APP_BUNDLE" \
  "$APP_CONTENTS" \
  "$APP_MACOS" \
  "$APP_RESOURCES" \
  "$APP_RUNTIME_DIR" \
  "$APP_RUNTIME_BUNDLE" \
  "$APP_RUNTIME"
CANONICAL_VERSION="$(
  "$PATH_VALIDATION_PYTHON" "$ROOT_DIR/script/release_metadata.py" version \
    --root "$ROOT_DIR"
)"
APP_VERSION="${APP_VERSION_OVERRIDE:-$CANONICAL_VERSION}"
if [[ "$APP_VERSION" != "$CANONICAL_VERSION" ]]; then
  echo "MATH_ANCHOR_APP_VERSION $APP_VERSION does not match canonical project version $CANONICAL_VERSION." >&2
  exit 2
fi

source "$ROOT_DIR/script/swift_env.sh"
configure_swift_environment "$ROOT_DIR"

"$ROOT_DIR/script/package_runtime.sh"

swift build --package-path "$ROOT_DIR" --configuration "$BUILD_CONFIGURATION"
BUILD_BINARY="$(swift build --package-path "$ROOT_DIR" --configuration "$BUILD_CONFIGURATION" --show-bin-path)/$APP_EXECUTABLE"

if [[ "$APP_BUNDLE" != "$EXPECTED_BUNDLE" || -z "$APP_BUNDLE" ]]; then
  echo "Refusing to replace unexpected app bundle: $APP_BUNDLE" >&2
  exit 1
fi

rm -rf "$APP_BUNDLE"
mkdir -p "$APP_MACOS" "$APP_RUNTIME_DIR"
cp "$BUILD_BINARY" "$APP_BINARY"
chmod +x "$APP_BINARY"
ditto "$ROOT_DIR/plugins/math-anchor/runtime/math-anchor-runtime" "$APP_RUNTIME_BUNDLE"
chmod +x "$APP_RUNTIME"
bash "$ROOT_DIR/script/build_app_icon.sh" "$APP_ICON"

cat >"$INFO_PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleExecutable</key><string>$APP_EXECUTABLE</string>
  <key>CFBundleIdentifier</key><string>$BUNDLE_ID</string>
  <key>CFBundleName</key><string>$APP_DISPLAY_NAME</string>
  <key>CFBundleDisplayName</key><string>$APP_DISPLAY_NAME</string>
  <key>CFBundleShortVersionString</key><string>$APP_VERSION</string>
  <key>CFBundleVersion</key><string>$BUILD_NUMBER</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleIconFile</key><string>AppIcon</string>
  <key>LSMinimumSystemVersion</key><string>$MIN_SYSTEM_VERSION</string>
  <key>NSHighResolutionCapable</key><true/>
  <key>NSPrincipalClass</key><string>NSApplication</string>
</dict>
</plist>
PLIST

"$PATH_VALIDATION_PYTHON" "$APP_RUNTIME_CHECK" --runtime "$APP_RUNTIME"

open_app() {
  "$PROCESS_CONTROL" stop "$APP_EXECUTABLE" "$APP_BINARY"
  /usr/bin/open -n "$APP_BUNDLE"
}

wait_for_app() {
  for _ in {1..40}; do
    if "$PROCESS_CONTROL" check "$APP_EXECUTABLE" "$APP_BINARY"; then
      return 0
    fi
    sleep 0.05
  done
  echo "Local Math Anchor app did not start from $APP_BINARY." >&2
  return 1
}

case "$MODE" in
  run)
    open_app
    ;;
  --debug|debug)
    "$PROCESS_CONTROL" stop "$APP_EXECUTABLE" "$APP_BINARY" "$BUILD_BINARY"
    lldb -- "$APP_BINARY"
    ;;
  --logs|logs)
    open_app
    /usr/bin/log stream --info --style compact --predicate "process == \"$APP_EXECUTABLE\""
    ;;
  --telemetry|telemetry)
    open_app
    /usr/bin/log stream --info --style compact --predicate "subsystem == \"$BUNDLE_ID\""
    ;;
  --verify|verify)
    open_app
    wait_for_app
    ;;
  --package|package)
    ;;
  *)
    echo "usage: $0 [run|--debug|--logs|--telemetry|--verify|--package]" >&2
    exit 2
    ;;
esac
