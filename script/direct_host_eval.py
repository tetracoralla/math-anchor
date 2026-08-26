#!/usr/bin/env python3
"""Validate or run Math Anchor's zero-model direct-host cold smoke."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any, Iterator


ROOT = Path(__file__).resolve().parent.parent
SUITE_PATH = ROOT / "evals" / "direct" / "coding-agent-profile.v0.1.json"
PLAN_PATH = ROOT / "evals" / "direct" / "math-anchor-cold-smoke.v0.1.json"
DRIVER_PATH = ROOT / "script" / "direct_eval_driver.py"
DEFAULT_EVALUATOR_ROOT = ROOT.parent / "agent-tool-evals"
DEFAULT_OUTPUT_DIR = ROOT / "build" / "direct-evals"
ROOT_PLACEHOLDER = "/MATH_ANCHOR_ROOT"
DRIVER_PLACEHOLDER = "/MATH_ANCHOR_DIRECT_DRIVER"


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SystemExit(f"unable to read {path}: {error}") from error
    if not isinstance(value, dict):
        raise SystemExit(f"expected one JSON object in {path}")
    return value


def _evaluator_root(argument: str | None) -> Path:
    configured = argument or os.environ.get("AGENT_TOOL_EVALS_ROOT")
    return Path(configured).expanduser().resolve() if configured else DEFAULT_EVALUATOR_ROOT.resolve()


def _environment() -> dict[str, str]:
    virtual_bin = ROOT / ".venv" / "bin"
    if not (virtual_bin / "python").is_file():
        raise SystemExit(f"Math Anchor virtual environment is unavailable: {virtual_bin}")
    return {**os.environ, "PATH": f"{virtual_bin}{os.pathsep}{os.environ.get('PATH', '')}"}


def _cli(root: Path) -> Path:
    cli = root / "src" / "cli.mjs"
    if not cli.is_file() or shutil.which("node") is None:
        raise SystemExit(f"agent-tool-evals is unavailable at {root}")
    if not DRIVER_PATH.is_file() or not os.access(DRIVER_PATH, os.X_OK):
        raise SystemExit(f"direct Math Anchor driver is unavailable or not executable: {DRIVER_PATH}")
    return cli


def _run(command: list[str], *, cwd: Path, environment: dict[str, str]) -> None:
    completed = subprocess.run(command, cwd=cwd, env=environment, check=False)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


@contextmanager
def _prepared_plan(plan: dict[str, Any]) -> Iterator[Path]:
    prepared = json.loads(json.dumps(plan))
    driver = prepared.get("driver")
    if not isinstance(driver, dict):
        raise SystemExit("direct plan has no driver")
    if driver.get("root") != ROOT_PLACEHOLDER or driver.get("command") != DRIVER_PLACEHOLDER:
        raise SystemExit("direct plan driver placeholders are missing or already resolved")
    driver["root"] = str(ROOT)
    driver["command"] = str(DRIVER_PATH)
    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(
        prefix=f"{PLAN_PATH.stem}-",
        suffix=".json",
        dir=DEFAULT_OUTPUT_DIR,
    )
    os.close(descriptor)
    temporary = Path(name)
    try:
        temporary.write_text(json.dumps(prepared, indent=2) + "\n", encoding="utf-8")
        yield temporary
    finally:
        temporary.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("validate", "run"))
    parser.add_argument("--evaluator-root")
    parser.add_argument("--output", help="new report path; defaults under build/direct-evals")
    arguments = parser.parse_args()
    if arguments.action == "validate" and arguments.output is not None:
        parser.error("--output applies only to the run action")

    suite = _load(SUITE_PATH)
    plan = _load(PLAN_PATH)
    evaluator_root = _evaluator_root(arguments.evaluator_root)
    cli = _cli(evaluator_root)
    environment = _environment()
    planned = len(suite.get("tasks", [])) * int(plan.get("repeats", 0))

    with _prepared_plan(plan) as prepared_plan:
        _run(
            [
                "node", str(cli), "direct-validate",
                "--suite", str(SUITE_PATH), "--plan", str(prepared_plan),
            ],
            cwd=evaluator_root,
            environment=environment,
        )
        print(f"validated direct-host cold smoke: {planned} zero-model invocations")
        if arguments.action == "validate":
            return 0

        if arguments.output:
            output = Path(arguments.output).expanduser().resolve()
        else:
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            output = DEFAULT_OUTPUT_DIR / f"{plan['id']}-{stamp}.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        if output.exists() or output.is_symlink():
            raise SystemExit(f"refusing to overwrite existing report: {output}")
        _run(
            [
                "node", str(cli), "direct-run",
                "--suite", str(SUITE_PATH), "--plan", str(prepared_plan),
                "--output", str(output),
            ],
            cwd=evaluator_root,
            environment=environment,
        )
        print(f"report: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
