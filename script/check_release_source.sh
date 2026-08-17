#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
VERSION="${MATH_ANCHOR_APP_VERSION:?Set MATH_ANCHOR_APP_VERSION to the release version.}"

source "$ROOT_DIR/script/python_env.sh"
if ! resolve_math_anchor_python "to validate release source metadata"; then
  exit 1
fi
CANONICAL_VERSION="$(
  "$RESOLVED_MATH_ANCHOR_PYTHON" "$ROOT_DIR/script/release_metadata.py" version \
    --root "$ROOT_DIR"
)"
if [[ "$VERSION" != "$CANONICAL_VERSION" ]]; then
  echo "Release version $VERSION does not match canonical project version $CANONICAL_VERSION." >&2
  exit 1
fi

if ! git -C "$ROOT_DIR" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Signed releases require a Git checkout at an exact annotated source tag." >&2
  exit 1
fi
if [[ -n "$(git -C "$ROOT_DIR" status --porcelain --untracked-files=all)" ]]; then
  echo "Signed releases require a clean Git worktree and index." >&2
  exit 1
fi

TAG_NAME="v$VERSION"
if ! TAG_TYPE="$(git -C "$ROOT_DIR" cat-file -t "refs/tags/$TAG_NAME" 2>/dev/null)"; then
  echo "Signed releases require the annotated tag $TAG_NAME at HEAD." >&2
  exit 1
fi
if [[ "$TAG_TYPE" != "tag" ]]; then
  echo "Signed releases require $TAG_NAME to be an annotated tag." >&2
  exit 1
fi
if ! TAG_COMMIT="$(git -C "$ROOT_DIR" rev-parse "refs/tags/$TAG_NAME^{commit}" 2>/dev/null)"; then
  echo "Could not resolve release tag $TAG_NAME." >&2
  exit 1
fi
HEAD_COMMIT="$(git -C "$ROOT_DIR" rev-parse HEAD)"
if [[ "$TAG_COMMIT" != "$HEAD_COMMIT" ]]; then
  echo "Release tag $TAG_NAME does not point to HEAD $HEAD_COMMIT." >&2
  exit 1
fi

printf 'Release source is clean and bound to %s at %s.\n' "$TAG_NAME" "$HEAD_COMMIT"
