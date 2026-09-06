from __future__ import annotations

from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]


def test_registry_exports_every_domain_operation_once() -> None:
    import importlib
    import pkgutil
    from math_anchor import operation_specs
    from math_anchor.catalog import OPERATIONS, describe_operation

    declared = []
    for module_info in pkgutil.iter_modules(operation_specs.__path__):
        module = importlib.import_module(f"math_anchor.operation_specs.{module_info.name}")
        declared.extend(getattr(module, "SPECS", ()))
    ids = [spec.id for spec in declared]
    assert len(ids) == len(set(ids)), "Duplicate operation IDs would be silently overwritten"
    assert set(ids) == set(OPERATIONS), "Registry order must not silently omit a domain operation"
    for spec in declared:
        assert OPERATIONS[spec.id] is spec
        assert describe_operation(spec.id)["operation"]["inputSchema"] == spec.input_schema


@pytest.mark.parametrize("relative_path", [
    "src/math_anchor/catalog.py",
    "src/math_anchor/contracts.py",
    "src/math_anchor/mcp_server.py",
    "src/math_anchor/cli.py",
    "src/math_anchor/worker_pool.py",
    "src/math_anchor/worker_process.py",
])
def test_transport_and_registry_layers_do_not_import_mathematical_engines(relative_path: str) -> None:
    import ast

    tree = ast.parse((ROOT / relative_path).read_text())
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".")[0])
    assert imports.isdisjoint({"sympy", "numpy", "pint", "mpmath"})


def test_swift_package_separates_core_from_app_and_tests_it() -> None:
    package = (ROOT / "Package.swift").read_text(encoding="utf-8")
    assert '.library(name: "MathAnchorCore", targets: ["MathAnchorCore"])' in package
    assert 'dependencies: ["MathAnchorCore"]' in package
    assert 'name: "MathAnchorCoreTests"' in package
    assert (ROOT / "Sources/MathAnchorCore").is_dir()
    assert 'path: "tests/MathAnchorCoreTests"' in package
    assert (ROOT / "tests/MathAnchorCoreTests").is_dir()


def test_complete_check_runs_the_swift_package_suite() -> None:
    complete_check = (ROOT / "script/check_all.sh").read_text(encoding="utf-8")
    swift_test = (ROOT / "script/swift_test.sh").read_text(encoding="utf-8")
    assert '"$ROOT_DIR/script/swift_test.sh"' in complete_check
    assert "swift test" in swift_test


def test_lean_reference_consumer_is_not_part_of_the_python_package() -> None:
    packaging = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert 'where = ["src"]' in packaging
    assert not (ROOT / "src" / "math_anchor" / "lean_reference_check.py").exists()
