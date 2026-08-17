from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "math_anchor_release_materials",
    ROOT / "script" / "generate_third_party_materials.py",
)
assert SPEC is not None and SPEC.loader is not None
release_materials = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = release_materials
SPEC.loader.exec_module(release_materials)


def test_runtime_and_development_locks_include_extra_dependency_closure() -> None:
    runtime_lock = release_materials.locked_packages(ROOT / "requirements-runtime.lock")
    runtime_closure = release_materials.validate_dependency_closure(
        ROOT / "pyproject.toml", runtime_lock
    )
    assert {"cryptography", "cffi", "pycparser"} <= set(runtime_closure)

    development_lock = release_materials.locked_packages(ROOT / "requirements-dev.lock")
    development_closure = release_materials.validate_dependency_closure(
        ROOT / "pyproject.toml",
        development_lock,
        project_extras=("dev",),
    )
    assert set(runtime_closure) < set(development_closure)


def test_dependency_closure_rejects_a_lock_that_drops_an_extra_dependency() -> None:
    runtime_lock = release_materials.locked_packages(ROOT / "requirements-runtime.lock")
    incomplete = [item for item in runtime_lock if item[0] != "cryptography"]

    with pytest.raises(SystemExit, match=r"missing=\['cryptography'\]"):
        release_materials.validate_dependency_closure(
            ROOT / "pyproject.toml", incomplete
        )


def test_dependency_lock_requires_a_sha256_hash_for_every_package(
    tmp_path: Path,
) -> None:
    unhashed = tmp_path / "unhashed.lock"
    unhashed.write_text("example==1.0\n", encoding="utf-8")

    with pytest.raises(SystemExit, match="missing or invalid sha256 hashes"):
        release_materials.locked_packages(unhashed)


def test_legacy_ambiguous_license_is_not_emitted_as_invalid_spdx() -> None:
    installed = SimpleNamespace(
        metadata={"License-Expression": None, "License": "BSD"}
    )

    assert release_materials.declared_license(installed) == "NOASSERTION"


def test_native_inventory_maps_every_standalone_library(tmp_path: Path) -> None:
    internal = tmp_path / "_internal"
    internal.mkdir()
    (internal / "libcrypto.3.dylib").write_bytes(b"OpenSSL 3.6.3 9 Jun 2026")
    (internal / "libssl.3.dylib").write_bytes(b"OpenSSL 3.6.3 9 Jun 2026")
    (internal / "liblzma.5.dylib").write_bytes(b"liblzma 5.8.3")
    (internal / "libmpdec.4.dylib").write_bytes(b"mpdecimal 4.0.1")

    components = release_materials.native_components(tmp_path, ROOT)

    assert {
        (component.name, component.version, component.license_declared)
        for component in components
    } == {
        ("OpenSSL", "3.6.3", "Apache-2.0"),
        ("XZ Utils liblzma", "5.8.3", "0BSD"),
        ("mpdecimal", "4.0.1", "BSD-2-Clause"),
    }


def test_native_inventory_rejects_an_unmapped_library(tmp_path: Path) -> None:
    (tmp_path / "libunknown.1.dylib").write_bytes(b"unknown")

    with pytest.raises(SystemExit, match="no owned license mapping"):
        release_materials.native_components(tmp_path, ROOT)
