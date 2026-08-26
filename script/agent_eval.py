#!/usr/bin/env python3
"""Validate or run Math Anchor's paired Coding Agent evaluations.

The provider-neutral runner lives in the sibling ``agent-tool-evals``
workspace.  This wrapper keeps Math Anchor's task suites and exact planned
model-call count local to the product, refuses accidental model runs, and
writes reports only under the gitignored ``build/agent-evals`` directory.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any

from release_metadata import canonical_version


ROOT = Path(__file__).resolve().parent.parent
EVAL_DIR = ROOT / "evals" / "agent"
DEFAULT_EVALUATOR_ROOT = ROOT.parent / "agent-tool-evals"
DEFAULT_OUTPUT_DIR = ROOT / "build" / "agent-evals"
POLICY_PATH = EVAL_DIR / "coding-agent-policy.md"
POLICY_PLACEHOLDER = "${MATH_ANCHOR_CODING_AGENT_POLICY}"
ISOLATED_CODEX_HOME_PLACEHOLDER = "${MATH_ANCHOR_ISOLATED_CODEX_HOME}"
TARGET_PLUGIN_ID = "math-anchor@openadam"
TARGET_PLUGIN_VERSION = canonical_version(ROOT)

MODES = {
    "smoke": (
        EVAL_DIR / "routing-smoke.v0.1.json",
        EVAL_DIR / "codex-luna-routing-smoke.v0.1.json",
    ),
    "policy-smoke": (
        EVAL_DIR / "routing-smoke.v0.1.json",
        EVAL_DIR / "codex-luna-policy-routing-smoke.v0.1.json",
    ),
    "installed-smoke": (
        EVAL_DIR / "routing-smoke.v0.1.json",
        EVAL_DIR / "codex-luna-installed-plugin-routing-smoke.v0.1.json",
    ),
    "utility": (
        EVAL_DIR / "coding-agent-utility.v0.1.json",
        EVAL_DIR / "codex-luna-utility.v0.1.json",
    ),
    "policy-utility": (
        EVAL_DIR / "coding-agent-utility.v0.1.json",
        EVAL_DIR / "codex-luna-policy-utility.v0.1.json",
    ),
}


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SystemExit(f"unable to read {path}: {error}") from error
    if not isinstance(value, dict):
        raise SystemExit(f"expected one JSON object in {path}")
    return value


def _planned_runs(suite: dict[str, Any], experiment: dict[str, Any]) -> int:
    tasks = suite.get("tasks")
    repeats = experiment.get("repeats")
    conditions = experiment.get("conditions")
    if not isinstance(tasks, list) or not isinstance(repeats, int) or not isinstance(conditions, dict):
        raise SystemExit("suite or experiment is missing tasks, repeats, or conditions")
    return len(tasks) * repeats * len(conditions)


def _evaluator_root(argument: str | None) -> Path:
    configured = argument or os.environ.get("AGENT_TOOL_EVALS_ROOT")
    return Path(configured).expanduser().resolve() if configured else DEFAULT_EVALUATOR_ROOT.resolve()


def _validate_evaluator(root: Path) -> Path:
    cli = root / "src" / "cli.mjs"
    package = root / "package.json"
    if not cli.is_file() or not package.is_file():
        raise SystemExit(
            f"agent-tool-evals is unavailable at {root}; pass --evaluator-root or set AGENT_TOOL_EVALS_ROOT"
        )
    if shutil.which("node") is None:
        raise SystemExit("node is required to run agent-tool-evals")
    return cli


def _validate_codex_harness(experiment: dict[str, Any]) -> None:
    """Reject a stale declared CLI identity before any model-backed run."""

    arguments = experiment.get("driver", {}).get("args")
    if not isinstance(arguments, list):
        raise SystemExit("experiment driver arguments are unavailable")
    codex_argument = "codex"
    if "--codex" in arguments:
        index = arguments.index("--codex") + 1
        if index >= len(arguments) or not isinstance(arguments[index], str):
            raise SystemExit("experiment --codex argument is malformed")
        codex_argument = arguments[index]
    codex = shutil.which(codex_argument)
    if codex is None:
        raise SystemExit(f"Codex CLI is unavailable: {codex_argument}")
    try:
        completed = subprocess.run(
            [codex, "--version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise SystemExit(f"unable to observe Codex harness version: {error}") from error
    match = re.fullmatch(r"codex-cli\s+(\S+)\s*", completed.stdout)
    if completed.returncode != 0 or match is None:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise SystemExit(f"unable to observe Codex harness version: {detail}")
    observed = {"id": "codex-cli", "version": match.group(1)}
    if experiment.get("harness") != observed:
        raise SystemExit(
            "declared Codex harness does not match the installed CLI: "
            f"declared {experiment.get('harness')!r}, observed {observed!r}; "
            "update the versioned experiment before authorizing model runs"
        )


def _run(command: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> None:
    completed = subprocess.run(command, cwd=cwd, env=env, check=False)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


def _capture_json(command: list[str], *, cwd: Path, env: dict[str, str]) -> dict[str, Any]:
    value = _capture_json_value(command, cwd=cwd, env=env)
    if not isinstance(value, dict):
        raise SystemExit("isolated Plugin setup returned a non-object JSON value")
    return value


def _capture_json_value(
    command: list[str], *, cwd: Path, env: dict[str, str]
) -> Any:
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise SystemExit(f"isolated Plugin setup failed: {detail}")
    try:
        value = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise SystemExit(f"isolated Plugin setup returned invalid JSON: {error}") from error
    return value


@contextmanager
def _temporary_environment(updates: dict[str, str]):
    previous = {key: os.environ.get(key) for key in updates}
    os.environ.update(updates)
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


@contextmanager
def _isolated_codex_home(enabled: bool):
    """Install only Math Anchor into a disposable Codex home for one paired run."""

    if not enabled:
        yield None
        return
    codex = shutil.which("codex")
    if codex is None:
        raise SystemExit("codex is required for the installed Plugin evaluation")
    source_codex_root = Path(
        os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))
    ).expanduser().resolve()
    auth_source = source_codex_root / "auth.json"
    if not auth_source.is_file():
        raise SystemExit(f"Codex authentication is unavailable: {auth_source}")
    with tempfile.TemporaryDirectory(prefix="math-anchor-agent-eval-codex-") as directory:
        isolated_root = Path(directory).resolve()
        (isolated_root / "auth.json").symlink_to(auth_source.resolve())
        isolated_environment = {
            **os.environ,
            "CODEX_HOME": str(isolated_root),
            # CODEX_HOME isolates Codex configuration and Plugins, while HOME
            # also prevents unrelated ~/.agents/skills from contaminating the
            # evaluated prompt surface.
            "HOME": str(isolated_root),
        }
        _capture_json(
            [codex, "plugin", "marketplace", "add", str(ROOT), "--json"],
            cwd=ROOT,
            env=isolated_environment,
        )
        installed = _capture_json(
            [codex, "plugin", "add", TARGET_PLUGIN_ID, "--json"],
            cwd=ROOT,
            env=isolated_environment,
        )
        if installed.get("pluginId") != TARGET_PLUGIN_ID or installed.get("version") != TARGET_PLUGIN_VERSION:
            raise SystemExit("isolated Plugin installation did not resolve the declared Math Anchor version")
        inventory = _capture_json(
            [codex, "plugin", "list", "--json"],
            cwd=ROOT,
            env=isolated_environment,
        )
        enabled_plugins = [
            item
            for item in inventory.get("installed", [])
            if isinstance(item, dict) and item.get("installed") is True and item.get("enabled") is True
        ]
        if len(enabled_plugins) != 1 or enabled_plugins[0].get("pluginId") != TARGET_PLUGIN_ID:
            raise SystemExit("isolated Codex home must contain exactly the enabled Math Anchor Plugin")
        server = _capture_json(
            [codex, "mcp", "get", "math-anchor", "--json"],
            cwd=ROOT,
            env=isolated_environment,
        )
        if server.get("name") != "math-anchor" or server.get("enabled") is not True:
            raise SystemExit("isolated Math Anchor MCP server is unavailable after installation")
        transport = server.get("transport")
        if not isinstance(transport, dict):
            raise SystemExit("isolated Math Anchor MCP transport is unavailable")
        command = transport.get("command")
        server_arguments = transport.get("args")
        server_cwd = transport.get("cwd")
        if not isinstance(command, str) or not isinstance(server_cwd, str) or not isinstance(server_arguments, list):
            raise SystemExit("isolated Math Anchor MCP transport is malformed")
        if not all(isinstance(value, str) for value in server_arguments):
            raise SystemExit("isolated Math Anchor MCP arguments are malformed")
        for expected_enabled in (False, True):
            serialized_arguments = ",".join(json.dumps(value) for value in server_arguments)
            override = (
                "mcp_servers.math-anchor={"
                f"command={json.dumps(command)},"
                f"args=[{serialized_arguments}],"
                f"cwd={json.dumps(server_cwd)},"
                f"enabled={str(expected_enabled).lower()}"
                "}"
            )
            observed = _capture_json(
                [
                    codex,
                    "--disable", "shell_tool",
                    "--disable", "unified_exec",
                    "--config", override,
                    "mcp", "get", "math-anchor", "--json",
                ],
                cwd=ROOT,
                env=isolated_environment,
            )
            if observed.get("enabled") is not expected_enabled:
                raise SystemExit(
                    f"isolated Math Anchor MCP preflight did not observe enabled={expected_enabled}"
                )
        prompt_input = _capture_json_value(
            [
                codex,
                "--enable", "plugins",
                "--disable", "shell_tool",
                "--disable", "unified_exec",
                "debug", "prompt-input",
                "Use Math Anchor for one reliability-sensitive calculation.",
            ],
            cwd=ROOT,
            env=isolated_environment,
        )
        if not isinstance(prompt_input, list):
            raise SystemExit("isolated Codex prompt-input probe returned a non-list value")
        prompt_text = "\n".join(
            content.get("text", "")
            for item in prompt_input
            if isinstance(item, dict)
            for content in item.get("content", [])
            if isinstance(content, dict) and isinstance(content.get("text"), str)
        )
        expected_skill = (
            isolated_root
            / "plugins"
            / "cache"
            / "openadam"
            / "math-anchor"
            / TARGET_PLUGIN_VERSION
            / "skills"
            / "calculate"
            / "SKILL.md"
        )
        ambient_skill_root = Path.home().resolve() / ".agents" / "skills"
        if str(expected_skill) not in prompt_text:
            raise SystemExit("isolated Codex prompt does not expose the installed Math Anchor Skill")
        if str(ambient_skill_root) in prompt_text:
            raise SystemExit("isolated Codex prompt still exposes ambient user Skills")
        print(f"prepared isolated {TARGET_PLUGIN_ID} version {TARGET_PLUGIN_VERSION}")
        with _temporary_environment({"HOME": str(isolated_root)}):
            yield isolated_root


@contextmanager
def _prepared_experiment(
    path: Path,
    experiment: dict[str, Any],
    *,
    prepare_installed_plugin: bool,
):
    """Resolve product-owned policy and isolated Plugin coordinates safely."""

    arguments = experiment.get("driver", {}).get("args")
    if not isinstance(arguments, list):
        yield path
        return
    needs_isolated_home = ISOLATED_CODEX_HOME_PLACEHOLDER in arguments
    with _isolated_codex_home(needs_isolated_home and prepare_installed_plugin) as isolated_root:
        replacements: dict[str, str] = {}
        if POLICY_PLACEHOLDER in arguments:
            if not POLICY_PATH.is_file():
                raise SystemExit(f"Coding Agent policy is unavailable: {POLICY_PATH}")
            replacements[POLICY_PLACEHOLDER] = str(POLICY_PATH.resolve())
        if isolated_root is not None:
            replacements[ISOLATED_CODEX_HOME_PLACEHOLDER] = str(isolated_root)
        if not replacements:
            yield path
            return
        prepared = json.loads(json.dumps(experiment))
        prepared_arguments = prepared["driver"]["args"]
        for placeholder, replacement in replacements.items():
            prepared_arguments[prepared_arguments.index(placeholder)] = replacement
        DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f"{path.stem}-",
            suffix=".json",
            dir=DEFAULT_OUTPUT_DIR,
        )
        os.close(descriptor)
        temporary_path = Path(temporary_name)
        try:
            temporary_path.write_text(json.dumps(prepared, indent=2) + "\n", encoding="utf-8")
            yield temporary_path
        finally:
            temporary_path.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("validate", "preflight", "run"))
    parser.add_argument("--mode", choices=tuple(MODES), required=True)
    parser.add_argument("--evaluator-root")
    parser.add_argument("--output", help="new report path; defaults under build/agent-evals")
    parser.add_argument(
        "--confirm-model-runs",
        type=int,
        help="required for run; must exactly match task count × repeats × two conditions",
    )
    arguments = parser.parse_args()

    suite_path, experiment_path = MODES[arguments.mode]
    suite = _load_json(suite_path)
    experiment = _load_json(experiment_path)
    planned = _planned_runs(suite, experiment)
    evaluator_root = _evaluator_root(arguments.evaluator_root)
    cli = _validate_evaluator(evaluator_root)

    if arguments.action in {"validate", "preflight"}:
        if arguments.confirm_model_runs is not None or arguments.output is not None:
            parser.error("--confirm-model-runs and --output apply only to the run action")
        if arguments.action == "preflight" and arguments.mode != "installed-smoke":
            parser.error("preflight currently applies only to --mode installed-smoke")
    elif arguments.confirm_model_runs != planned:
        parser.error(
            f"run requires --confirm-model-runs {planned}; received {arguments.confirm_model_runs!r}"
        )

    if arguments.action in {"preflight", "run"}:
        _validate_codex_harness(experiment)

    with _prepared_experiment(
        experiment_path,
        experiment,
        prepare_installed_plugin=arguments.action in {"preflight", "run"},
    ) as prepared_experiment:
        validate = [
            "node",
            str(cli),
            "validate",
            "--suite",
            str(suite_path),
            "--experiment",
            str(prepared_experiment),
        ]
        _run(validate, cwd=evaluator_root)
        print(f"validated {arguments.mode}: {len(suite['tasks'])} tasks, {planned} planned model runs")
        if arguments.action in {"validate", "preflight"}:
            if arguments.action == "preflight":
                print("installed Plugin preflight passed without model calls")
            return 0

        if arguments.output:
            output = Path(arguments.output).expanduser().resolve()
        else:
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            output = DEFAULT_OUTPUT_DIR / f"{experiment['id']}-{stamp}.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        if output.exists() or output.is_symlink():
            raise SystemExit(f"refusing to overwrite existing report: {output}")

        command = [
            "node",
            str(cli),
            "run",
            "--suite",
            str(suite_path),
            "--experiment",
            str(prepared_experiment),
            "--output",
            str(output),
        ]
        _run(command, cwd=evaluator_root)
        print(f"report: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
