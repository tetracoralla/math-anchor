#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$ROOT_DIR"

./script/bootstrap.sh >/dev/null
LAKE="$(./script/bootstrap_lean.sh | tail -n 1)"
CERTIFICATE="$ROOT_DIR/.build/lean-bridge/certificate.json"
ARTIFACT="$ROOT_DIR/.build/lean-bridge/Certificate.lean"
mkdir -p "$(dirname "$CERTIFICATE")"

PYTHONPATH="$ROOT_DIR/src" "$ROOT_DIR/.venv/bin/python" -c '
import json, sys
from math_anchor.runtime import execute_direct
result = execute_direct(
    "certificate.polynomial_identity",
    {"left": "(x + y)^2", "right": "x^2 + 2*x*y + y^2", "variables": ["x", "y"]},
)
json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
sys.stdout.write("\n")
' > "$CERTIFICATE"

PYTHONPATH="$ROOT_DIR/src" "$ROOT_DIR/.venv/bin/python" -m math_anchor.cli \
  verify-certificate-lean "$CERTIFICATE" \
  --lake "$LAKE" \
  --project "$ROOT_DIR/integrations/lean" \
  --artifact-output "$ARTIFACT"
