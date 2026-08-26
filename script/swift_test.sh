#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$ROOT_DIR"

source "$ROOT_DIR/script/swift_env.sh"
configure_swift_environment "$ROOT_DIR"

DEVELOPER_ROOT="$(/usr/bin/xcode-select -p)"
TESTING_FRAMEWORK="$(find "$DEVELOPER_ROOT" -type d -name Testing.framework -print -quit 2>/dev/null || true)"
TESTING_INTEROP="$(find "$DEVELOPER_ROOT" -type f -name lib_TestingInterop.dylib -print -quit 2>/dev/null || true)"

if [[ -z "$TESTING_FRAMEWORK" || -z "$TESTING_INTEROP" ]]; then
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
