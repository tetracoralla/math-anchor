#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$ROOT_DIR"

source "$ROOT_DIR/script/swift_env.sh"
configure_swift_environment "$ROOT_DIR"

DEVELOPER_ROOT="${DEVELOPER_DIR:-$(/usr/bin/xcode-select -p)}"
# Xcode contains testing frameworks for every platform. Taking the first
# filesystem match can silently import tvOS/iOS modules into a macOS test.
TESTING_ROOT="$DEVELOPER_ROOT/Platforms/MacOSX.platform/Developer"
if [[ ! -d "$TESTING_ROOT" ]]; then
  TESTING_ROOT="$DEVELOPER_ROOT"
fi
TESTING_FRAMEWORK="$TESTING_ROOT/Library/Frameworks/Testing.framework"
TESTING_INTEROP="$TESTING_ROOT/usr/lib/lib_TestingInterop.dylib"

if [[ ! -d "$TESTING_FRAMEWORK" || ! -f "$TESTING_INTEROP" ]]; then
  swift test --package-path "$ROOT_DIR" "$@"
  exit 0
fi

FRAMEWORKS_DIR="$(dirname "$TESTING_FRAMEWORK")"
INTEROP_DIR="$(dirname "$TESTING_INTEROP")"

DYLD_FRAMEWORK_PATH="$FRAMEWORKS_DIR${DYLD_FRAMEWORK_PATH:+:$DYLD_FRAMEWORK_PATH}" \
DYLD_LIBRARY_PATH="$INTEROP_DIR${DYLD_LIBRARY_PATH:+:$DYLD_LIBRARY_PATH}" \
swift test \
  --package-path "$ROOT_DIR" \
  -Xswiftc -F \
  -Xswiftc "$FRAMEWORKS_DIR" \
  -Xlinker "-F$FRAMEWORKS_DIR" \
  -Xlinker -rpath \
  -Xlinker "$FRAMEWORKS_DIR" \
  -Xlinker -rpath \
  -Xlinker "$INTEROP_DIR" \
  "$@"
