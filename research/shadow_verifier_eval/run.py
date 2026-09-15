#!/usr/bin/env python3
"""One-command shadow-verifier scaffold. B2/B3 deterministic. B0/B1 deferred.

Not a benefit percentage, not a pack promotion, not Epoch 2 completion.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from math_anchor.errors import CalculatorError, error_payload

from research.shadow_verifier_eval.smoke import run_smoke, write_report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the pre-registered shadow-verifier scaffold (B2/B3 deterministic "
            "obligation runtime; B0/B1 model_arms=deferred). Writes a "
            "machine-readable report. Not a benefit percentage, not a pack "
            "promotion, and not Epoch 2 completion."
        )
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Write the smoke report JSON to a new file (refuses to overwrite)",
    )
    parser.add_argument(
        "--receipt-dir",
        type=Path,
        help="Write B2/B3 full receipts to this directory (refuses to overwrite files)",
    )
    parser.add_argument(
        "--include-model-arms",
        action="store_true",
        help=(
            "Rejected in this scaffold. Live B0/B1 require a later runner and "
            "--confirm-model-runs N. See docs/research/ai-for-math/shadow-verifier.md."
        ),
    )
    parser.add_argument(
        "--confirm-model-runs",
        type=int,
        default=None,
        help="Reserved for a later live four-arm run. This scaffold does not call a model.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    if arguments.confirm_model_runs is not None and not arguments.include_model_arms:
        payload = {
            "status": "error",
            "error": error_payload(
                "E_INPUT",
                "--confirm-model-runs is only meaningful with --include-model-arms, "
                "which this scaffold rejects (model_arms=deferred)",
            ),
        }
        sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        return 2
    try:
        report = run_smoke(
            receipt_dir=arguments.receipt_dir,
            include_model_arms=arguments.include_model_arms,
        )
        encoded = json.dumps(report, ensure_ascii=False, indent=2)
        sys.stdout.write(encoded + "\n")
        if arguments.output is not None:
            write_report(arguments.output, report)
    except CalculatorError as error:
        payload = {"status": "error", "error": error_payload(error.code, error.message)}
        sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        return 2
    if report["decision"].get("promote"):
        return 2
    if report["decision"].get("targetedFix"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
