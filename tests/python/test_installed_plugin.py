from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import shutil
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "math_anchor_check_installed_plugin",
    ROOT / "script" / "check_installed_plugin.py",
)
assert SPEC is not None and SPEC.loader is not None
installed_plugin = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = installed_plugin
SPEC.loader.exec_module(installed_plugin)


def write_plugin(root: Path, version: str, payload: str = "runtime") -> None:
    (root / ".codex-plugin").mkdir(parents=True)
    (root / "runtime" / "math-anchor-runtime").mkdir(parents=True)
    (root / "skills" / "calculate").mkdir(parents=True)
    (root / ".codex-plugin" / "plugin.json").write_text(
        json.dumps({"name": "math-anchor", "version": version}), encoding="utf-8"
    )
    (root / ".mcp.json").write_text(
        json.dumps(
            {
                "mcpServers": {
                    "math-anchor": {
                        "command": "runtime/math-anchor-runtime/math-anchor-runtime",
                        "args": ["mcp"],
                        "cwd": ".",
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    runtime = root / "runtime" / "math-anchor-runtime" / "math-anchor-runtime"
    runtime.write_text(payload, encoding="utf-8")
    runtime.chmod(0o755)
    (root / installed_plugin.RUNTIME_MANIFEST).write_text(
        json.dumps({"productVersion": version}), encoding="utf-8"
    )
    (root / "skills" / "calculate" / "SKILL.md").write_text("skill", encoding="utf-8")


def test_installed_plugin_requires_identical_versioned_bytes(tmp_path: Path) -> None:
    source = tmp_path / "source"
    installed = tmp_path / "installed"
    write_plugin(source, "0.4.0")
    shutil.copytree(source, installed)

    installed_plugin.validate(source, installed, "0.4.0")


def test_installed_plugin_rejects_same_version_content_drift(tmp_path: Path) -> None:
    source = tmp_path / "source"
    installed = tmp_path / "installed"
    write_plugin(source, "0.4.0")
    shutil.copytree(source, installed)
    (installed / "skills" / "calculate" / "SKILL.md").write_text(
        "stale skill", encoding="utf-8"
    )

    with pytest.raises(SystemExit, match="installed bytes differ"):
        installed_plugin.validate(source, installed, "0.4.0")


def test_installed_plugin_rejects_version_drift(tmp_path: Path) -> None:
    source = tmp_path / "source"
    installed = tmp_path / "installed"
    write_plugin(source, "0.3.0")
    shutil.copytree(source, installed)

    with pytest.raises(SystemExit, match="manifest version mismatch"):
        installed_plugin.validate(source, installed, "0.4.0")
