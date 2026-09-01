#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
TASK_UID=$(id -u)
STATE_DIR="${MATH_ANCHOR_LEAN_STATE_DIR:-/private/tmp/math-anchor-lean-reference-$TASK_UID}"
ELAN_HOME_DIR="$STATE_DIR/elan-home"
INSTALLER_DIR="$STATE_DIR/installer"
DOWNLOAD_DIR="$STATE_DIR/downloads"
ELAN_VERSION="4.2.4"
TOOLCHAIN="leanprover/lean4:v4.33.1"
PROJECT_SOURCE="$ROOT/integrations/lean-reference"
PROJECT_DIR="$STATE_DIR/project"

OS=$(uname -s)
ARCH=$(uname -m)
case "$OS:$ARCH" in
  Darwin:arm64)
    TARGET="aarch64-apple-darwin"
    EXPECTED_SHA256="7ad829861392c718dfebde3a83b5c8508df47be02af68894b094b0b3952616e5"
    ;;
  Darwin:x86_64)
    TARGET="x86_64-apple-darwin"
    EXPECTED_SHA256="8a340b309d8ed2e96f930761fa223b3af57a38f5d253b53ac90293c9516f8cd4"
    ;;
  Linux:aarch64|Linux:arm64)
    TARGET="aarch64-unknown-linux-gnu"
    EXPECTED_SHA256="05febd124d84ebf994b2e7479922a5650b1e950c17ae3bd1ddd776b65bb72bf9"
    ;;
  Linux:x86_64)
    TARGET="x86_64-unknown-linux-gnu"
    EXPECTED_SHA256="42b94d4244e8353142c456ec0e4ca6528fd898a6c604d4059f494e706e431f63"
    ;;
  *)
    echo "unsupported Lean reference platform: $OS $ARCH" >&2
    exit 2
    ;;
esac

mkdir -p "$DOWNLOAD_DIR" "$INSTALLER_DIR" "$ELAN_HOME_DIR" "$PROJECT_DIR"
cp "$PROJECT_SOURCE/lean-toolchain" "$PROJECT_DIR/lean-toolchain"
cp "$PROJECT_SOURCE/lakefile.toml" "$PROJECT_DIR/lakefile.toml"
cp "$PROJECT_SOURCE/MathAnchorLeanReference.lean" "$PROJECT_DIR/MathAnchorLeanReference.lean"
if [ -f "$PROJECT_SOURCE/lake-manifest.json" ]; then
  cp "$PROJECT_SOURCE/lake-manifest.json" "$PROJECT_DIR/lake-manifest.json"
fi
ARCHIVE="$DOWNLOAD_DIR/elan-$TARGET.tar.gz"
URL="https://github.com/leanprover/elan/releases/download/v$ELAN_VERSION/elan-$TARGET.tar.gz"

if [ ! -f "$ARCHIVE" ]; then
  curl --fail --location --silent --show-error --output "$ARCHIVE" "$URL"
fi

ACTUAL_SHA256=$(python3 - "$ARCHIVE" <<'PY'
from hashlib import sha256
from pathlib import Path
import sys

digest = sha256()
with Path(sys.argv[1]).open("rb") as handle:
    for chunk in iter(lambda: handle.read(1024 * 1024), b""):
        digest.update(chunk)
print(digest.hexdigest())
PY
)
if [ "$ACTUAL_SHA256" != "$EXPECTED_SHA256" ]; then
  echo "elan archive checksum mismatch" >&2
  exit 2
fi

if [ ! -x "$ELAN_HOME_DIR/bin/elan" ]; then
  tar -xzf "$ARCHIVE" -C "$INSTALLER_DIR"
  ELAN_HOME="$ELAN_HOME_DIR" "$INSTALLER_DIR/elan-init" \
    -y --no-modify-path --default-toolchain none
fi

ELAN="$ELAN_HOME_DIR/bin/elan"
ELAN_HOME="$ELAN_HOME_DIR" "$ELAN" toolchain install "$TOOLCHAIN"
(
  cd "$PROJECT_DIR"
  MATHLIB_NO_CACHE_ON_UPDATE=1 ELAN_HOME="$ELAN_HOME_DIR" \
    "$ELAN" run "$TOOLCHAIN" lake update
  ELAN_HOME="$ELAN_HOME_DIR" "$ELAN" run "$TOOLCHAIN" lake \
    exe cache get Mathlib.Tactic.Ring
  ELAN_HOME="$ELAN_HOME_DIR" "$ELAN" run "$TOOLCHAIN" lake build
)

ELAN_HOME="$ELAN_HOME_DIR" "$ELAN" run "$TOOLCHAIN" lean --version
