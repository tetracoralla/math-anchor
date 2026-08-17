from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from .catalog import describe_operation, search_operations
from .errors import CalculatorError
from .output_policy import DEFAULT_MAX_OUTPUT_BYTES
from .sandbox import run_batch, run_operation


class StructuredArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise CalculatorError("E_INPUT", message)


def _json_object(raw: str) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as error:
        raise argparse.ArgumentTypeError(f"invalid JSON: {error}") from error
    if not isinstance(value, dict):
        raise argparse.ArgumentTypeError("arguments JSON must be an object")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = StructuredArgumentParser(prog="math-anchor")
    subparsers = parser.add_subparsers(dest="command", required=True)

    search = subparsers.add_parser("search", help="Search the operation catalog")
    search.add_argument("query", nargs="?", default="")
    search.add_argument("--category")

    describe = subparsers.add_parser("describe", help="Describe one operation")
    describe.add_argument("operation")

    run = subparsers.add_parser("run", help="Run one isolated operation")
    run.add_argument("operation")
    run.add_argument("arguments", type=_json_object)
    run.add_argument("--timeout-ms", type=int, default=10_000)
    run.add_argument("--memory-mb", type=int, default=2048)
    run.add_argument("--result-mode", choices=("auto", "exact", "approx", "both"), default="auto")
    run.add_argument("--max-output-bytes", type=int, default=DEFAULT_MAX_OUTPUT_BYTES)

    batch = subparsers.add_parser("batch", help="Run an array of isolated operations")
    batch.add_argument("items", help="JSON array or - to read JSON from stdin")
    return parser


def _batch_items(raw: str) -> list[dict[str, Any]]:
    source = sys.stdin.read() if raw == "-" else raw
    value = json.loads(source)
    if not isinstance(value, list):
        raise CalculatorError("E_INPUT", "batch input must be an array")
    return value


def main() -> None:
    parser = build_parser()
    try:
        arguments = parser.parse_args()
        if arguments.command == "search":
            result = search_operations(arguments.query, arguments.category)
        elif arguments.command == "describe":
            result = describe_operation(arguments.operation)
        elif arguments.command == "run":
            result = run_operation(
                arguments.operation,
                arguments.arguments,
                timeout_ms=arguments.timeout_ms,
                memory_mb=arguments.memory_mb,
                result_mode=arguments.result_mode,
                max_output_bytes=arguments.max_output_bytes,
            )
        else:
            result = run_batch(_batch_items(arguments.items))
    except CalculatorError as error:
        result = {"status": "error", "error": error.as_dict()}
    except json.JSONDecodeError as error:
        result = {"status": "error", "error": {"code": "E_INPUT", "message": f"invalid JSON: {error}"}}
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    if result.get("status") == "error":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
