#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
GENERATED_OUTPUT_RELATIVES=(
  ".venv/"
  "plugins/math-anchor/runtime/"
  ".build/"
  ".swiftpm/"
  "build/"
  "dist/"
)
GENERATED_OUTPUT_DIRS=(
  "$ROOT_DIR/.venv"
  "$ROOT_DIR/plugins/math-anchor/runtime"
  "$ROOT_DIR/.build"
  "$ROOT_DIR/.swiftpm"
  "$ROOT_DIR/build"
  "$ROOT_DIR/dist"
)
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
# Never execute an interpreter from this repository before its generated paths
# have been validated. In particular, .venv may itself be an unsafe symlink.
if ! resolve_math_anchor_python "to validate source paths" "$ROOT_DIR"; then
  exit 1
fi
PATH_VALIDATION_PYTHON="$RESOLVED_MATH_ANCHOR_PYTHON"

"$PATH_VALIDATION_PYTHON" "$PATH_VALIDATOR" --root "$ROOT_DIR" \
  "${GENERATED_OUTPUT_DIRS[@]}"

if [[ -e "$ROOT_DIR/.git" ]]; then
  for relative in "${GENERATED_OUTPUT_RELATIVES[@]}"; do
    if [[ -n "$(git -C "$ROOT_DIR" ls-files -- "${relative%/}")" ]]; then
      echo "Generated output must not be tracked by git: $relative" >&2
      exit 1
    fi
    if ! git -C "$ROOT_DIR" check-ignore -q "$relative"; then
      echo "Generated output must be ignored by git: $relative" >&2
      exit 1
    fi
  done
  echo "Source layout passed for the Git checkout."
  exit 0
fi

for index in "${!GENERATED_OUTPUT_RELATIVES[@]}"; do
  relative="${GENERATED_OUTPUT_RELATIVES[$index]}"
  output_dir="${GENERATED_OUTPUT_DIRS[$index]}"
  if [[ ! -f "$GITIGNORE" ]] || ! grep -Fqx "$relative" "$GITIGNORE"; then
    echo "Source archive must retain the generated-output exclusion in .gitignore: $relative" >&2
    exit 1
  fi
  if [[ -e "$output_dir" && ! -d "$output_dir" ]]; then
    echo "Generated output path must be a directory: $output_dir" >&2
    exit 1
  fi
  if [[ "$MODE" == "--archive-clean" && -d "$output_dir" ]]; then
    FIRST_ARCHIVED_ENTRY="$(find "$output_dir" -mindepth 1 -maxdepth 1 -print -quit)"
    if [[ -n "$FIRST_ARCHIVED_ENTRY" ]]; then
      echo "Source archive must not contain generated output: $FIRST_ARCHIVED_ENTRY" >&2
      exit 1
    fi
  fi
done

if [[ "$MODE" == "--archive-clean" ]]; then
  echo "Original metadata-free source archive is clean."
else
  echo "Repeatable source layout passed for the metadata-free development tree."
fi
