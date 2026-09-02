#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
from typing import Any


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Probe the packaged Math Anchor app runtime."
    )
    parser.add_argument("--runtime", type=Path, required=True)
    return parser


def _require_object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SystemExit(f"{label} must be a JSON object")
    return value


def _validated_runtime(path: Path) -> Path:
    lexical_path = path.expanduser().absolute()
    for component in (lexical_path, *lexical_path.parents):
        if component.is_symlink():
            raise SystemExit(
                f"packaged app runtime has a symbolic-link component: {component}"
            )
    try:
        runtime = lexical_path.resolve(strict=True)
    except OSError as error:
        raise SystemExit("packaged app runtime is unavailable") from error
    if not runtime.is_file() or not os.access(runtime, os.X_OK):
        raise SystemExit("packaged app runtime must be one regular executable file")
    return runtime


def main() -> None:
    arguments = _parser().parse_args()
    runtime = _validated_runtime(arguments.runtime)

    requests = [
        {
            "id": "expression",
            "operation": "expression.evaluate",
            "expression": "sqrt(2)",
            "precision": 40,
        },
        {
            "id": "unit",
            "operation": "units.convert",
            "value": "72",
            "fromUnit": "watt",
            "toUnit": "kilowatt",
            "precision": 12,
        },
        {
            "id": "blocked",
            "operation": "expression.evaluate",
            "expression": '__import__("os")',
            "precision": 16,
        },
    ]
    payload = "".join(
        json.dumps(request, separators=(",", ":")) + "\n" for request in requests
    )
    try:
        completed = subprocess.run(
            [str(runtime), "app"],
            input=payload,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise SystemExit("packaged app runtime probe exceeded 10 seconds") from error
    if completed.returncode != 0:
        raise SystemExit(
            f"packaged app runtime exited {completed.returncode}: "
            f"{completed.stderr[:512]}"
        )
    if len(completed.stdout.encode("utf-8")) > 64 * 1024:
        raise SystemExit("packaged app runtime probe exceeded 64 KiB")
    try:
        responses = [json.loads(line) for line in completed.stdout.splitlines()]
    except json.JSONDecodeError as error:
        raise SystemExit("packaged app runtime returned invalid JSON") from error
    if len(responses) != 4:
        raise SystemExit("packaged app runtime returned an unexpected response count")

    ready = _require_object(responses[0], "ready response")
    expression = _require_object(responses[1], "expression response")
    unit = _require_object(responses[2], "unit response")
    blocked = _require_object(responses[3], "blocked-input response")
    if ready != {"status": "ready"}:
        raise SystemExit("packaged app runtime did not become ready")
    if not (
        expression.get("id") == "expression"
        and expression.get("status") == "ok"
        and expression.get("exact") == "sqrt(2)"
        and isinstance(expression.get("approx"), str)
        and expression["approx"].startswith("1.41421356237")
    ):
        raise SystemExit("packaged app runtime expression probe failed")
    if not (
        unit.get("id") == "unit"
        and unit.get("status") == "ok"
        and unit.get("exact") == "9/125"
        and unit.get("unit") == "kW"
    ):
        raise SystemExit("packaged app runtime unit probe failed")
    error = blocked.get("error")
    if not (
        blocked.get("id") == "blocked"
        and blocked.get("status") == "error"
        and isinstance(error, dict)
        and error.get("code") == "E_NAME"
    ):
        raise SystemExit("packaged app runtime unsafe-input probe failed")
    print("Packaged app runtime checks passed.")


if __name__ == "__main__":
    main()
