from __future__ import annotations

from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]


def _line_count(relative_path: str) -> int:
    return len((ROOT / relative_path).read_text(encoding="utf-8").splitlines())


@pytest.mark.parametrize(
    ("relative_path", "maximum"),
    (
        ("src/math_anchor/catalog.py", 150),
        ("src/math_anchor/contracts.py", 300),
        ("src/math_anchor/sandbox.py", 500),
        ("src/math_anchor/worker_process.py", 450),
        ("src/math_anchor/worker_pool.py", 350),
    ),
)
def test_architecture_facades_stay_bounded(relative_path: str, maximum: int) -> None:
    assert _line_count(relative_path) <= maximum


@pytest.mark.parametrize(
    "directory",
    ("src/math_anchor/operation_specs", "src/math_anchor/result_contracts"),
)
def test_domain_modules_stay_reviewable(directory: str) -> None:
    modules = sorted((ROOT / directory).glob("*.py"))
    assert modules
    oversized = {
        module.relative_to(ROOT).as_posix(): len(
            module.read_text(encoding="utf-8").splitlines()
        )
        for module in modules
        if len(module.read_text(encoding="utf-8").splitlines()) > 400
    }
    assert oversized == {}


def test_swift_package_separates_core_from_app_and_tests_it() -> None:
    package = (ROOT / "Package.swift").read_text(encoding="utf-8")
    assert '.library(name: "MathAnchorCore", targets: ["MathAnchorCore"])' in package
    assert 'dependencies: ["MathAnchorCore"]' in package
    assert 'name: "MathAnchorCoreTests"' in package
    assert (ROOT / "Sources/MathAnchorCore").is_dir()
    assert (ROOT / "Tests/MathAnchorCoreTests").is_dir()


def test_complete_check_runs_the_swift_package_suite() -> None:
    complete_check = (ROOT / "script/check_all.sh").read_text(encoding="utf-8")
    swift_test = (ROOT / "script/swift_test.sh").read_text(encoding="utf-8")
    assert '"$ROOT_DIR/script/swift_test.sh"' in complete_check
    assert "swift test" in swift_test


def test_lean_reference_consumer_is_not_part_of_the_python_package() -> None:
    packaging = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert 'where = ["src"]' in packaging
    assert not (ROOT / "src" / "math_anchor" / "lean_reference_check.py").exists()
