#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="${ZIBETHA_APP_VERSION:?Set ZIBETHA_APP_VERSION to the release version.}"
BUILD_NUMBER="${ZIBETHA_BUILD_NUMBER:?Set ZIBETHA_BUILD_NUMBER to a positive release build number.}"
SIGNING_IDENTITY="${ZIBETHA_CODESIGN_IDENTITY:?Set ZIBETHA_CODESIGN_IDENTITY to a Developer ID Application identity.}"
NOTARY_PROFILE="${ZIBETHA_NOTARY_PROFILE:?Set ZIBETHA_NOTARY_PROFILE to a configured notarytool keychain profile.}"
EXPECTED_ARCH="${ZIBETHA_EXPECTED_ARCH:-$(uname -m)}"
APP_BUNDLE="$ROOT_DIR/dist/Zibetha.app"
ARCHIVE="$ROOT_DIR/dist/Zibetha-$VERSION-$EXPECTED_ARCH.zip"
NOTARY_ARCHIVE="$ROOT_DIR/dist/.Zibetha-$VERSION-$EXPECTED_ARCH-notary.zip"

if [[ "$EXPECTED_ARCH" != "$(uname -m)" ]]; then
  echo "Release host architecture $(uname -m) does not match expected $EXPECTED_ARCH." >&2
  exit 1
fi

ZIBETHA_BUILD_CONFIGURATION=release \
ZIBETHA_APP_VERSION="$VERSION" \
ZIBETHA_BUILD_NUMBER="$BUILD_NUMBER" \
  "$ROOT_DIR/script/build_and_run.sh" package
ZIBETHA_EXPECTED_ARCH="$EXPECTED_ARCH" ZIBETHA_VERIFY_APP_BUNDLE=1 \
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
