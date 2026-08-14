#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-run}"
APP_NAME="Zibetha"
BUNDLE_ID="com.openadam.zibetha"
MIN_SYSTEM_VERSION="14.0"
APP_VERSION="${ZIBETHA_APP_VERSION:-0.1.0}"
BUILD_NUMBER="${ZIBETHA_BUILD_NUMBER:-1}"
BUILD_CONFIGURATION="${ZIBETHA_BUILD_CONFIGURATION:-debug}"

if [[ "$BUILD_CONFIGURATION" != "debug" && "$BUILD_CONFIGURATION" != "release" ]]; then
  echo "ZIBETHA_BUILD_CONFIGURATION must be debug or release." >&2
  exit 2
fi
if [[ ! "$APP_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+([.-][A-Za-z0-9]+)*$ ]]; then
  echo "ZIBETHA_APP_VERSION must be a semantic version." >&2
  exit 2
fi
if [[ ! "$BUILD_NUMBER" =~ ^[1-9][0-9]*$ ]]; then
  echo "ZIBETHA_BUILD_NUMBER must be a positive integer." >&2
  exit 2
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/script/swift_env.sh"
configure_swift_environment "$ROOT_DIR"
DIST_DIR="$ROOT_DIR/dist"
APP_BUNDLE="$DIST_DIR/$APP_NAME.app"
EXPECTED_BUNDLE="$ROOT_DIR/dist/Zibetha.app"
APP_CONTENTS="$APP_BUNDLE/Contents"
APP_MACOS="$APP_CONTENTS/MacOS"
APP_BINARY="$APP_MACOS/$APP_NAME"
INFO_PLIST="$APP_CONTENTS/Info.plist"
APP_RESOURCES="$APP_CONTENTS/Resources"
APP_RUNTIME_DIR="$APP_RESOURCES/Runtime"
APP_RUNTIME_BUNDLE="$APP_RUNTIME_DIR/zibetha-runtime"
APP_RUNTIME="$APP_RUNTIME_BUNDLE/zibetha-runtime"
APP_ICON="$APP_RESOURCES/AppIcon.icns"

if [[ ! -x "$ROOT_DIR/.venv/bin/zibetha" ]]; then
  "$ROOT_DIR/script/bootstrap.sh"
fi
"$ROOT_DIR/script/package_runtime.sh"

swift build --package-path "$ROOT_DIR" --configuration "$BUILD_CONFIGURATION"
BUILD_BINARY="$(swift build --package-path "$ROOT_DIR" --configuration "$BUILD_CONFIGURATION" --show-bin-path)/$APP_NAME"

if [[ "$APP_BUNDLE" != "$EXPECTED_BUNDLE" || -z "$APP_BUNDLE" ]]; then
  echo "Refusing to replace unexpected app bundle: $APP_BUNDLE" >&2
  exit 1
fi

rm -rf "$APP_BUNDLE"
mkdir -p "$APP_MACOS" "$APP_RUNTIME_DIR"
cp "$BUILD_BINARY" "$APP_BINARY"
chmod +x "$APP_BINARY"
ditto "$ROOT_DIR/plugins/zibetha/runtime/zibetha-runtime" "$APP_RUNTIME_BUNDLE"
chmod +x "$APP_RUNTIME"
bash "$ROOT_DIR/script/build_app_icon.sh" "$APP_ICON"

cat >"$INFO_PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleExecutable</key><string>$APP_NAME</string>
  <key>CFBundleIdentifier</key><string>$BUNDLE_ID</string>
  <key>CFBundleName</key><string>Zibetha</string>
  <key>CFBundleDisplayName</key><string>Zibetha</string>
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

open_app() {
  pkill -x "$APP_NAME" >/dev/null 2>&1 || true
  /usr/bin/open -n "$APP_BUNDLE"
}

case "$MODE" in
  run)
    open_app
    ;;
  --debug|debug)
    pkill -x "$APP_NAME" >/dev/null 2>&1 || true
    lldb -- "$APP_BINARY"
    ;;
  --logs|logs)
    open_app
    /usr/bin/log stream --info --style compact --predicate "process == \"$APP_NAME\""
    ;;
  --telemetry|telemetry)
    open_app
    /usr/bin/log stream --info --style compact --predicate "subsystem == \"$BUNDLE_ID\""
    ;;
  --verify|verify)
    open_app
    sleep 1
    pgrep -x "$APP_NAME" >/dev/null
    ;;
  --package|package)
    ;;
  *)
    echo "usage: $0 [run|--debug|--logs|--telemetry|--verify|--package]" >&2
    exit 2
    ;;
esac
