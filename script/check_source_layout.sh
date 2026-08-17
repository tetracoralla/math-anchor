#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
GENERATED_RUNTIME_RELATIVE="plugins/math-anchor/runtime/"
GENERATED_RUNTIME_DIR="$ROOT_DIR/${GENERATED_RUNTIME_RELATIVE%/}"
GITIGNORE="$ROOT_DIR/.gitignore"
PATH_VALIDATOR="$ROOT_DIR/script/validate_repo_paths.py"

MODE="${1:---development}"
if [[ "$#" -gt 1 ]]; then
  echo "Usage: $0 [--development|--archive-clean]" >&2
  exit 2
fi
case "$MODE" in
  --development | --archive-clean) ;;
  *)
    echo "Usage: $0 [--development|--archive-clean]" >&2
    exit 2
    ;;
esac

source "$ROOT_DIR/script/python_env.sh"
if ! resolve_math_anchor_python "to validate source paths"; then
  exit 1
fi
PATH_VALIDATION_PYTHON="$RESOLVED_MATH_ANCHOR_PYTHON"

"$PATH_VALIDATION_PYTHON" "$PATH_VALIDATOR" --root "$ROOT_DIR" "$GENERATED_RUNTIME_DIR"

if [[ -e "$ROOT_DIR/.git" ]]; then
  if [[ -n "$(git -C "$ROOT_DIR" ls-files -- "${GENERATED_RUNTIME_RELATIVE}**")" ]]; then
    echo "Generated plugin runtime must not be tracked by git." >&2
    exit 1
  fi
  if ! git -C "$ROOT_DIR" check-ignore -q "$GENERATED_RUNTIME_RELATIVE"; then
    echo "Generated plugin runtime must be ignored by git: $GENERATED_RUNTIME_RELATIVE" >&2
    exit 1
  fi
  echo "Source layout passed for the Git checkout."
  exit 0
fi

if [[ ! -f "$GITIGNORE" ]] || ! grep -Fqx "$GENERATED_RUNTIME_RELATIVE" "$GITIGNORE"; then
  echo "Source archive must retain the generated-runtime exclusion in .gitignore." >&2
  exit 1
fi

if [[ -e "$GENERATED_RUNTIME_DIR" && ! -d "$GENERATED_RUNTIME_DIR" ]]; then
  echo "Generated plugin runtime path must be a directory: $GENERATED_RUNTIME_DIR" >&2
  exit 1
fi

if [[ "$MODE" == "--archive-clean" && -d "$GENERATED_RUNTIME_DIR" ]]; then
  FIRST_ARCHIVED_ENTRY="$(find "$GENERATED_RUNTIME_DIR" -mindepth 1 -maxdepth 1 -print -quit)"
  if [[ -n "$FIRST_ARCHIVED_ENTRY" ]]; then
    echo "Source archive must not contain a generated plugin runtime: $FIRST_ARCHIVED_ENTRY" >&2
    exit 1
  fi
fi

if [[ "$MODE" == "--archive-clean" ]]; then
  echo "Original metadata-free source archive is clean."
else
  echo "Repeatable source layout passed for the metadata-free development tree."
fi
