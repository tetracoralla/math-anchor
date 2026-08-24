#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="${MATH_ANCHOR_APP_VERSION:?Set MATH_ANCHOR_APP_VERSION to the release version.}"
BUILD_NUMBER="${MATH_ANCHOR_BUILD_NUMBER:?Set MATH_ANCHOR_BUILD_NUMBER to a positive release build number.}"
SIGNING_IDENTITY="${MATH_ANCHOR_CODESIGN_IDENTITY:?Set MATH_ANCHOR_CODESIGN_IDENTITY to a Developer ID Application identity.}"
NOTARY_PROFILE="${MATH_ANCHOR_NOTARY_PROFILE:?Set MATH_ANCHOR_NOTARY_PROFILE to a configured notarytool keychain profile.}"
NOTARY_KEYCHAIN="${MATH_ANCHOR_NOTARY_KEYCHAIN:-}"
EXPECTED_ARCH="${MATH_ANCHOR_EXPECTED_ARCH:-$(uname -m)}"
APP_BUNDLE="$ROOT_DIR/dist/Math Anchor.app"
ARCHIVE="$ROOT_DIR/dist/Math-Anchor-$VERSION-$EXPECTED_ARCH.zip"
NOTARY_ARCHIVE="$ROOT_DIR/dist/.Math-Anchor-$VERSION-$EXPECTED_ARCH-notary.zip"
CHECKSUM="$ARCHIVE.sha256"
SBOM="$ROOT_DIR/dist/Math-Anchor-$VERSION-$EXPECTED_ARCH.spdx.json"
SBOM_CHECKSUM="$SBOM.sha256"
APP_RUNTIME_BUNDLE="$APP_BUNDLE/Contents/Resources/Runtime/math-anchor-runtime"
APP_RUNTIME="$APP_RUNTIME_BUNDLE/math-anchor-runtime"

if [[ "$EXPECTED_ARCH" != "$(uname -m)" ]]; then
  echo "Release host architecture $(uname -m) does not match expected $EXPECTED_ARCH." >&2
  exit 1
fi

MATH_ANCHOR_APP_VERSION="$VERSION" "$ROOT_DIR/script/check_release_source.sh"

source "$ROOT_DIR/script/python_env.sh"
if ! resolve_math_anchor_python "to validate release output paths"; then
  exit 1
fi
"$RESOLVED_MATH_ANCHOR_PYTHON" "$ROOT_DIR/script/validate_repo_paths.py" \
  --root "$ROOT_DIR" \
  "$ROOT_DIR/dist" \
  "$APP_BUNDLE" \
  "$ARCHIVE" \
  "$NOTARY_ARCHIVE" \
  "$CHECKSUM" \
  "$SBOM" \
  "$SBOM_CHECKSUM"

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

# Signing changes every nested Mach-O hash. Refresh the embedded SBOM and
# manifest after nested signing, then seal those final resources with the
# outer app signature. A pre-sign manifest must never travel in a signed app.
"$ROOT_DIR/.venv/bin/python" "$ROOT_DIR/script/generate_third_party_materials.py" \
  --lock "$ROOT_DIR/requirements-runtime.lock" \
  --project "$ROOT_DIR/pyproject.toml" \
  --bundle "$APP_RUNTIME_BUNDLE" \
  --runtime "$APP_RUNTIME" \
  --output-dir "$APP_RUNTIME_BUNDLE"
"$ROOT_DIR/.venv/bin/python" "$ROOT_DIR/script/runtime_manifest.py" write \
  --bundle "$APP_RUNTIME_BUNDLE" \
  --runtime "$APP_RUNTIME" \
  --lock "$ROOT_DIR/requirements-runtime.lock" \
  --source-root "$ROOT_DIR" \
  --version "$VERSION"
"$ROOT_DIR/.venv/bin/python" "$ROOT_DIR/script/runtime_manifest.py" verify \
  --bundle "$APP_RUNTIME_BUNDLE" \
  --runtime "$APP_RUNTIME" \
  --lock "$ROOT_DIR/requirements-runtime.lock" \
  --source-root "$ROOT_DIR" \
  --version "$VERSION"
"$ROOT_DIR/.venv/bin/python" "$ROOT_DIR/script/generate_third_party_materials.py" \
  --lock "$ROOT_DIR/requirements-runtime.lock" \
  --project "$ROOT_DIR/pyproject.toml" \
  --bundle "$APP_RUNTIME_BUNDLE" \
  --runtime "$APP_RUNTIME" \
  --output-dir "$APP_RUNTIME_BUNDLE" \
  --verify-existing

codesign --force --timestamp --options runtime --sign "$SIGNING_IDENTITY" "$APP_BUNDLE"
codesign --verify --deep --strict --verbose=2 "$APP_BUNDLE"

rm -f "$NOTARY_ARCHIVE" "$ARCHIVE" "$CHECKSUM" "$SBOM" "$SBOM_CHECKSUM"
ditto -c -k --keepParent "$APP_BUNDLE" "$NOTARY_ARCHIVE"
NOTARY_ARGUMENTS=(--keychain-profile "$NOTARY_PROFILE" --wait)
if [[ -n "$NOTARY_KEYCHAIN" ]]; then
  NOTARY_ARGUMENTS+=(--keychain "$NOTARY_KEYCHAIN")
fi
xcrun notarytool submit "$NOTARY_ARCHIVE" "${NOTARY_ARGUMENTS[@]}"
xcrun stapler staple "$APP_BUNDLE"
xcrun stapler validate "$APP_BUNDLE"
spctl --assess --type execute --verbose=2 "$APP_BUNDLE"
ditto -c -k --keepParent "$APP_BUNDLE" "$ARCHIVE"
cp "$APP_RUNTIME_BUNDLE/sbom.spdx.json" "$SBOM"
(
  cd "$ROOT_DIR/dist"
  shasum -a 256 "${ARCHIVE##*/}" > "${CHECKSUM##*/}"
  shasum -a 256 "${SBOM##*/}" > "${SBOM_CHECKSUM##*/}"
)
rm -f "$NOTARY_ARCHIVE"
printf '%s\n%s\n%s\n%s\n' "$ARCHIVE" "$CHECKSUM" "$SBOM" "$SBOM_CHECKSUM"
