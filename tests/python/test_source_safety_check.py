from __future__ import annotations

import importlib.util
from pathlib import Path


def test_source_safety_check_descends_into_operation_packages(tmp_path: Path) -> None:
    script_path = Path(__file__).parents[2] / "script" / "check_source_safety.py"
    spec = importlib.util.spec_from_file_location("check_source_safety", script_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    runtime = tmp_path / "runtime"
    nested = runtime / "operations"
    nested.mkdir(parents=True)
    (nested / "unsafe.py").write_text("result = eval(source)\n")

    violations = module.find_forbidden_calls(runtime)
    assert violations == ["operations/unsafe.py:1: result = eval(source)"]
