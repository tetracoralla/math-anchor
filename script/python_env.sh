#!/usr/bin/env bash

# Resolves a Python 3.11+ interpreter for repository tooling that must run
# before the development virtualenv exists. Sets RESOLVED_MATH_ANCHOR_PYTHON.
resolve_math_anchor_python() {
  local context="${1:-required}"
  local rejected_root="${2:-}"
  local candidate
  local candidate_lexical_path
  local candidate_path
  local candidate_resolved_path

  RESOLVED_MATH_ANCHOR_PYTHON=""
  for candidate in "${MATH_ANCHOR_PYTHON:-}" python3 python3.13 python3.12 python3.11; do
    [[ -n "$candidate" ]] || continue
    if [[ "$candidate" == */* ]]; then
      [[ -x "$candidate" ]] || continue
      candidate_path="$candidate"
    else
      command -v "$candidate" >/dev/null 2>&1 || continue
      candidate_path="$(command -v "$candidate")"
    fi
    candidate_resolved_path="$candidate_path"
    if [[ -L "$candidate_path" ]]; then
      candidate_resolved_path="$(
        "$candidate_path" -c 'import os, sys; print(os.path.realpath(sys.executable))' 2>/dev/null
      )" || continue
      [[ -x "$candidate_resolved_path" ]] || continue
    fi
    if [[ -n "$rejected_root" ]]; then
      if [[ "$candidate_path" == /* ]]; then
        candidate_lexical_path="$candidate_path"
      else
        candidate_lexical_path="$(pwd -P)/$candidate_path"
      fi
      case "$candidate_lexical_path" in
        "$rejected_root" | "$rejected_root"/*) continue ;;
      esac
      case "$candidate_resolved_path" in
        "$rejected_root" | "$rejected_root"/*) continue ;;
      esac
    fi
    if "$candidate_resolved_path" -c 'import encodings, sys, venv; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' >/dev/null 2>&1; then
      RESOLVED_MATH_ANCHOR_PYTHON="$candidate_resolved_path"
      return 0
    fi
  done
  echo "Python 3.11 or newer is required $context." >&2
  return 1
}
