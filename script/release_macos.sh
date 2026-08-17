#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="${MATH_ANCHOR_APP_VERSION:?Set MATH_ANCHOR_APP_VERSION to the release version.}"
BUILD_NUMBER="${MATH_ANCHOR_BUILD_NUMBER:?Set MATH_ANCHOR_BUILD_NUMBER to a positive release build number.}"
SIGNING_IDENTITY="${MATH_ANCHOR_CODESIGN_IDENTITY:?Set MATH_ANCHOR_CODESIGN_IDENTITY to a Developer ID Application identity.}"
NOTARY_PROFILE="${MATH_ANCHOR_NOTARY_PROFILE:?Set MATH_ANCHOR_NOTARY_PROFILE to a configured notarytool keychain profile.}"
EXPECTED_ARCH="${MATH_ANCHOR_EXPECTED_ARCH:-$(uname -m)}"
APP_BUNDLE="$ROOT_DIR/dist/Math Anchor.app"
ARCHIVE="$ROOT_DIR/dist/Math-Anchor-$VERSION-$EXPECTED_ARCH.zip"
NOTARY_ARCHIVE="$ROOT_DIR/dist/.Math-Anchor-$VERSION-$EXPECTED_ARCH-notary.zip"

if [[ "$EXPECTED_ARCH" != "$(uname -m)" ]]; then
  echo "Release host architecture $(uname -m) does not match expected $EXPECTED_ARCH." >&2
  exit 1
fi

MATH_ANCHOR_APP_VERSION="$VERSION" "$ROOT_DIR/script/check_release_source.sh"

MATH_ANCHOR_BUILD_CONFIGURATION=release \
MATH_ANCHOR_APP_VERSION="$VERSION" \
MATH_ANCHOR_BUILD_NUMBER="$BUILD_NUMBER" \
  "$ROOT_DIR/script/build_and_run.sh" package
MATH_ANCHOR_APP_VERSION="$VERSION" \
MATH_ANCHOR_BUILD_NUMBER="$BUILD_NUMBER" \
MATH_ANCHOR_EXPECTED_ARCH="$EXPECTED_ARCH" \
MATH_ANCHOR_VERIFY_APP_BUNDLE=1 \
  "$ROOT_DIR/script/check_release_hygiene.sh"

while IFS= read -r -d '' candidate; do
  if file -b "$candidate" | grep -q "Mach-O"; then
    codesign --force --timestamp --options runtime --sign "$SIGNING_IDENTITY" "$candidate"
  fi
done < <(find "$APP_BUNDLE/Contents" -type f -print0)
codesign --force --timestamp --options runtime --sign "$SIGNING_IDENTITY" "$APP_BUNDLE"
codesign --verify --deep --strict --verbose=2 "$APP_BUNDLE"

rm -f "$NOTARY_ARCHIVE" "$ARCHIVE"
ditto -c -k --keepParent "$APP_BUNDLE" "$NOTARY_ARCHIVE"
xcrun notarytool submit "$NOTARY_ARCHIVE" --keychain-profile "$NOTARY_PROFILE" --wait
xcrun stapler staple "$APP_BUNDLE"
xcrun stapler validate "$APP_BUNDLE"
spctl --assess --type execute --verbose=2 "$APP_BUNDLE"
ditto -c -k --keepParent "$APP_BUNDLE" "$ARCHIVE"
rm -f "$NOTARY_ARCHIVE"
echo "$ARCHIVE"
