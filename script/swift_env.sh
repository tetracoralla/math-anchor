#!/usr/bin/env bash

configure_swift_environment() {
  local root_dir="$1"
  local architecture
  local developer_dir
  local candidate
  local selected=""

  architecture="$(uname -m)"
  case "$architecture" in
    arm64|x86_64) ;;
    *)
      echo "Unsupported macOS architecture: $architecture" >&2
      return 1
      ;;
  esac

  export ZIBETHA_SWIFT_TARGET="${ZIBETHA_SWIFT_TARGET:-${architecture}-apple-macosx14.0}"
  export SWIFTPM_MODULECACHE_OVERRIDE="${SWIFTPM_MODULECACHE_OVERRIDE:-$root_dir/.build/ModuleCache}"
  export CLANG_MODULE_CACHE_PATH="${CLANG_MODULE_CACHE_PATH:-$root_dir/.build/ModuleCache}"
  mkdir -p "$SWIFTPM_MODULECACHE_OVERRIDE"

  developer_dir="$(/usr/bin/xcode-select -p 2>/dev/null || true)"
  if [[ -n "${ZIBETHA_SDKROOT:-}" ]]; then
    candidate="$ZIBETHA_SDKROOT"
    if [[ ! -d "$candidate" ]]; then
      echo "Explicit macOS SDK does not exist: $candidate" >&2
      return 1
    fi
    if SDKROOT="$candidate" swiftc \
      -sdk "$candidate" \
      -target "$ZIBETHA_SWIFT_TARGET" \
      -module-cache-path "$CLANG_MODULE_CACHE_PATH" \
      -typecheck "$root_dir/script/SwiftSDKProbe.swift" \
      >/dev/null 2>&1; then
      selected="$candidate"
    else
      echo "Explicit macOS SDK is incompatible with the active Swift compiler: $candidate" >&2
      return 1
    fi
  else
    while IFS= read -r candidate; do
      [[ -n "$candidate" && -d "$candidate" ]] || continue
      if SDKROOT="$candidate" swiftc \
        -sdk "$candidate" \
        -target "$ZIBETHA_SWIFT_TARGET" \
        -module-cache-path "$CLANG_MODULE_CACHE_PATH" \
        -typecheck "$root_dir/script/SwiftSDKProbe.swift" \
        >/dev/null 2>&1; then
        selected="$candidate"
        break
      fi
    done < <(
      {
        xcrun --sdk macosx --show-sdk-path 2>/dev/null || true
        if [[ -n "$developer_dir" && -d "$developer_dir" ]]; then
          find "$developer_dir" -type d -name 'MacOSX*.sdk' -prune 2>/dev/null
        fi
      } | awk 'NF && !seen[$0]++' | sort -Vr
    )
  fi

  if [[ -z "$selected" ]]; then
    echo "No installed macOS SDK is compatible with the active Swift compiler." >&2
    echo "Select a matching Xcode toolchain or set ZIBETHA_SDKROOT." >&2
    return 1
  fi
  export SDKROOT="$selected"
}
