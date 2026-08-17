#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE_SVG="$ROOT_DIR/Resources/AppIcon.svg"
OUTPUT_ICNS="${1:?usage: build_app_icon.sh <output.icns>}"

if [[ ! -f "$SOURCE_SVG" ]]; then
  echo "Missing app icon source: $SOURCE_SVG" >&2
  exit 1
fi

ICON_WORK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/math-anchor-icon.XXXXXX")"
if [[ -z "$ICON_WORK_DIR" || ! -d "$ICON_WORK_DIR" || -L "$ICON_WORK_DIR" ]]; then
  echo "Unable to create a safe icon work directory." >&2
  exit 1
fi

cleanup() {
  if [[ -n "$ICON_WORK_DIR" && -d "$ICON_WORK_DIR" && ! -L "$ICON_WORK_DIR" ]]; then
    find "$ICON_WORK_DIR" -type f -delete
    find "$ICON_WORK_DIR" -depth -type d -exec rmdir {} \; 2>/dev/null || true
  fi
}
trap cleanup EXIT

ICONSET_DIR="$ICON_WORK_DIR/AppIcon.iconset"
mkdir -p "$ICONSET_DIR"

/usr/bin/qlmanage -t -s 1024 -o "$ICON_WORK_DIR" "$SOURCE_SVG" >/dev/null 2>&1
RENDERED_PNG="$ICON_WORK_DIR/AppIcon.svg.png"
if [[ ! -f "$RENDERED_PNG" ]]; then
  echo "App icon rendering failed." >&2
  exit 1
fi

render_size() {
  local pixels="$1"
  local name="$2"
  /usr/bin/sips -z "$pixels" "$pixels" "$RENDERED_PNG" --out "$ICONSET_DIR/$name" >/dev/null
}

render_size 16 icon_16x16.png
render_size 32 icon_16x16@2x.png
render_size 32 icon_32x32.png
render_size 64 icon_32x32@2x.png
render_size 128 icon_128x128.png
render_size 256 icon_128x128@2x.png
render_size 256 icon_256x256.png
render_size 512 icon_256x256@2x.png
render_size 512 icon_512x512.png
render_size 1024 icon_512x512@2x.png

mkdir -p "$(dirname "$OUTPUT_ICNS")"
/usr/bin/iconutil -c icns "$ICONSET_DIR" -o "$OUTPUT_ICNS"
