"""Load and validate the human-authored natural_tasks pack for live plans.

Agent-facing prompts stay separate from controller-only oracle notes.
Missing or invalid pack paths fail closed (no silent skip).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from math_anchor.errors import CalculatorError

NATURAL_TASKS_KIND = "math-anchor.research.ai-for-math-shadow-verifier-natural-tasks.v0"
REQUIRED_TASK_FIELDS = ("id", "title", "domain", "prompt", "oracleNotes")
REQUIRED_ORACLE_FLAGS = ("outsideAgentView", "controllerOnly")


def _fail(message: str, *, details: dict[str, Any] | None = None) -> None:
    raise CalculatorError("E_INPUT", message, details or {})


def load_natural_tasks_pack(path: str | Path) -> dict[str, Any]:
    """Load index.json + task files; return agent-view / controller-oracle split."""

    pack_dir = Path(path)
    if not pack_dir.exists():
        _fail(
            f"natural-tasks pack path does not exist: {pack_dir}",
            details={"path": str(pack_dir)},
        )
    if not pack_dir.is_dir():
        _fail(
            f"natural-tasks pack path is not a directory: {pack_dir}",
            details={"path": str(pack_dir)},
        )
    index_path = pack_dir / "index.json"
    if not index_path.is_file():
        _fail(
            f"natural-tasks pack missing index.json: {index_path}",
            details={"path": str(pack_dir)},
        )
    try:
        index = json.loads(index_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        _fail(
            f"natural-tasks index.json is not valid JSON: {error}",
            details={"path": str(index_path)},
        )
    if not isinstance(index, dict):
        _fail("natural-tasks index.json must be an object", details={"path": str(index_path)})
    if index.get("kind") != NATURAL_TASKS_KIND:
        _fail(
            f"unexpected natural-tasks kind: {index.get('kind')!r}",
            details={"expected": NATURAL_TASKS_KIND, "path": str(index_path)},
        )
    if index.get("liveScores") is not None:
        _fail(
            "natural-tasks pack must keep liveScores null (no invented live scores)",
            details={"path": str(index_path)},
        )
    if index.get("epoch2Complete") is not False:
        _fail(
            "natural-tasks pack must mark epoch2Complete=false",
            details={"path": str(index_path)},
        )
    task_names = index.get("tasks")
    if not isinstance(task_names, list) or not task_names:
        _fail(
            "natural-tasks index.json must declare a non-empty tasks list",
            details={"path": str(index_path)},
        )

    agent_view: list[dict[str, Any]] = []
    controller_oracle: dict[str, Any] = {}
    loaded_ids: list[str] = []
    for name in task_names:
        if not isinstance(name, str) or not name.endswith(".json"):
            _fail(
                f"natural-tasks entry must be a .json filename: {name!r}",
                details={"path": str(pack_dir)},
            )
        task_path = pack_dir / name
        if not task_path.is_file():
            _fail(
                f"natural-tasks file missing: {task_path}",
                details={"path": str(pack_dir), "taskFile": name},
            )
        try:
            task = json.loads(task_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            _fail(
                f"natural-tasks file is not valid JSON ({name}): {error}",
                details={"path": str(task_path)},
            )
        if not isinstance(task, dict):
            _fail(f"natural-tasks file must be an object: {name}")
        for field in REQUIRED_TASK_FIELDS:
            if field not in task:
                _fail(
                    f"natural-tasks file {name} missing required field {field!r}",
                    details={"path": str(task_path)},
                )
        prompt = task.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            _fail(f"natural-tasks file {name} must have a non-empty prompt string")
        notes = task.get("oracleNotes")
        if not isinstance(notes, dict):
            _fail(f"natural-tasks file {name} oracleNotes must be an object")
        for flag in REQUIRED_ORACLE_FLAGS:
            if notes.get(flag) is not True:
                _fail(
                    f"natural-tasks file {name} oracleNotes.{flag} must be true "
                    "(controller-only / outside agent view)",
                    details={"path": str(task_path)},
                )
        if notes.get("liveScore") is not None:
            _fail(
                f"natural-tasks file {name} oracleNotes.liveScore must be null",
                details={"path": str(task_path)},
            )
        task_id = str(task["id"])
        if task_id in controller_oracle:
            _fail(f"duplicate natural-tasks id: {task_id}")
        loaded_ids.append(task_id)
        agent_view.append(
            {
                "task": task_id,
                "title": task.get("title"),
                "domain": task.get("domain"),
                "prompt": prompt,
                "sourceFile": name,
                "agentView": True,
            }
        )
        controller_oracle[task_id] = {
            "task": task_id,
            "sourceFile": name,
            "silentWrongRisk": task.get("silentWrongRisk"),
            "oracleNotes": notes,
            "outsideAgentView": True,
            "controllerOnly": True,
        }

    return {
        "kind": NATURAL_TASKS_KIND,
        "path": str(pack_dir),
        "index": {
            "title": index.get("title"),
            "researchStatus": index.get("researchStatus"),
            "liveScores": None,
            "epoch2Complete": False,
            "doNotStartH1": bool(index.get("doNotStartH1", True)),
            "taskFiles": list(task_names),
            "honesty": index.get("honesty") or {},
        },
        "taskIds": loaded_ids,
        "agentView": {
            "note": (
                "Natural-task prompts for a later live B0/B1 Agent. "
                "Do not attach controllerOracle fields to the Agent prompt."
            ),
            "prompts": agent_view,
        },
        "controllerOracle": {
            "note": "Controller-owned oracle notes; outside agent view.",
            "outsideAgentView": True,
            "controllerOnly": True,
            "byTask": controller_oracle,
        },
        "honesty": {
            "loadedAndValidated": True,
            "noLiveScores": True,
            "oracleOutsideAgentView": True,
            "epoch2StillIncomplete": True,
        },
    }
