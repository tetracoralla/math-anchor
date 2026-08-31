#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
LEAN_VERSION="4.33.1"
SYSTEM_NAME="$(uname -s)"
MACHINE_NAME="$(uname -m)"
TOOLCHAIN_ROOT="$ROOT_DIR/.build/lean-toolchain"
ARCHIVE_DIR="$TOOLCHAIN_ROOT/downloads"

if [[ "$SYSTEM_NAME" != "Darwin" ]]; then
  echo "The pinned Lean bridge bootstrap currently supports macOS only." >&2
  exit 1
fi

case "$MACHINE_NAME" in
  arm64)
    ARCHIVE_NAME="lean-$LEAN_VERSION-darwin_aarch64.tar.zst"
    ARCHIVE_SHA256="88c45aad985b5d2a8d925fe10bd1296bd35f66f408480ab182d3facccd065a9d"
    TOOLCHAIN_NAME="lean-$LEAN_VERSION-darwin_aarch64"
    ;;
  x86_64)
    ARCHIVE_NAME="lean-$LEAN_VERSION-darwin.tar.zst"
    ARCHIVE_SHA256="93c475c1600360df35471bf6ed1c7fe118d7fb42be6915ead67724f7ad58dfaf"
    TOOLCHAIN_NAME="lean-$LEAN_VERSION-darwin"
    ;;
  *)
    echo "Unsupported macOS architecture for the Lean bridge: $MACHINE_NAME" >&2
    exit 1
    ;;
esac

TOOLCHAIN_DIR="$TOOLCHAIN_ROOT/$TOOLCHAIN_NAME"
LAKE="$TOOLCHAIN_DIR/bin/lake"
if [[ ! -x "$LAKE" ]]; then
  mkdir -p "$ARCHIVE_DIR" "$TOOLCHAIN_ROOT"
  ARCHIVE="$ARCHIVE_DIR/$ARCHIVE_NAME"
  if [[ ! -f "$ARCHIVE" ]]; then
    curl --fail --location --show-error \
      "https://github.com/leanprover/lean4/releases/download/v$LEAN_VERSION/$ARCHIVE_NAME" \
      --output "$ARCHIVE"
  fi
  ACTUAL_SHA256="$(shasum -a 256 "$ARCHIVE" | awk '{print $1}')"
  if [[ "$ACTUAL_SHA256" != "$ARCHIVE_SHA256" ]]; then
    echo "Lean archive digest mismatch: expected $ARCHIVE_SHA256, found $ACTUAL_SHA256" >&2
    exit 1
  fi
  tar --extract --file "$ARCHIVE" --directory "$TOOLCHAIN_ROOT"
fi

if [[ ! -x "$LAKE" ]]; then
  echo "Pinned Lake executable is unavailable after extraction: $LAKE" >&2
  exit 1
fi

export PATH="$TOOLCHAIN_DIR/bin:$PATH"
(
  cd "$ROOT_DIR/integrations/lean"
  "$LAKE" update
  "$LAKE" exe cache get
  "$LAKE" build
)

printf '%s\n' "$LAKE"
