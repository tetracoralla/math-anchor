#!/usr/bin/env python3
"""One-command reuse-benefit smoke. No model. No Host. Not a benefit percentage."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from math_anchor.errors import CalculatorError, error_payload

from research.reuse_benefit_eval.smoke import run_smoke, write_report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the pre-registered no-model reuse-benefit smoke "
            "(B0/B1/B_template/B_codegen/P-pack). Writes a machine-readable "
            "report. Not a benefit percentage and not a pack promotion. "
            "Trustworthiness, behavior, and utility stay separate."
        )
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Write the smoke report JSON to a new file (refuses to overwrite)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        report = run_smoke()
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
