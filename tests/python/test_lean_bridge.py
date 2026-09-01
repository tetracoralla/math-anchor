from __future__ import annotations

from pathlib import Path

import pytest

from math_anchor.certificate_checker import CertificateValidationError
from math_anchor.errors import CalculatorError
from math_anchor.lean_bridge import (
    LEAN_TOOLCHAIN,
    MATHLIB_REVISION,
    MAX_KERNEL_OUTPUT_BYTES,
    _run,
    _validate_kernel_output,
    build_lean_artifact,
    verify_polynomial_identity_with_lean,
)
from math_anchor.runtime import execute_direct


def _certificate(*, identity: bool = True) -> dict:
    result = execute_direct(
        "certificate.polynomial_identity",
        {
            "left": "(x + y)^2" if identity else "x^2",
            "right": "x^2 + 2*x*y + y^2" if identity else "x",
            "variables": ["x", "y"],
        },
    )
    return result["certificate"]


def _fake_project(path: Path) -> Path:
    path.mkdir()
    (path / "lakefile.toml").write_text(
        'name = "test"\n[[require]]\nname = "mathlib"\n'
        f'rev = "{MATHLIB_REVISION}"\n',
        encoding="utf-8",
    )
    (path / "lean-toolchain").write_text(f"{LEAN_TOOLCHAIN}\n", encoding="utf-8")
    (path / "lake-manifest.json").write_text(
        '{"packages":[{"name":"mathlib","rev":"' + MATHLIB_REVISION + '"}]}\n',
        encoding="utf-8",
    )
    return path


def _fake_lake(
    path: Path,
    *,
    accept: bool = True,
    version: str = "4.33.1, aarch64-apple-darwin",
    kernel_output: str = "'certificate' depends on axioms: []",
) -> Path:
    path.write_text(
        "#!/bin/sh\n"
        "if [ \"$3\" = \"--version\" ]; then\n"
        f"  echo 'Lean (version {version})'\n"
        "  exit 0\n"
        "fi\n"
        + (
            f"echo \"{kernel_output}\"\nexit 0\n"
            if accept
            else "echo 'kernel rejection' >&2\nexit 1\n"
        ),
        encoding="utf-8",
    )
    path.chmod(0o755)
    return path


def test_lean_artifact_uses_generated_identifiers_and_exact_rational_theorem() -> None:
    source, metadata = build_lean_artifact(_certificate())

    assert "import Mathlib.Tactic.Ring" in source
    assert "(v0 v1 : ℚ)" in source
    assert "((v0 + v1) ^ 2)" in source
    assert "by\n  ring" in source
    assert "#print axioms" in source
    assert metadata["variableMap"] == {"x": "v0", "y": "v1"}
    assert metadata["theorem"].startswith("certificate_")


def test_lean_artifact_types_every_literal_as_rational() -> None:
    result = execute_direct(
        "certificate.polynomial_identity",
        {"left": "1 / 2 + 1 / 2", "right": "1", "variables": ["unused"]},
    )

    source, _ = build_lean_artifact(result["certificate"])

    assert "((1 : ℚ) / (2 : ℚ))" in source
    assert "= (1 : ℚ)" in source


def test_lean_bridge_rejects_a_valid_nonidentity_certificate() -> None:
    with pytest.raises(CertificateValidationError, match="identity classification is true"):
        build_lean_artifact(_certificate(identity=False))


def test_lean_bridge_records_the_real_checker_version_and_artifact_digest(
    tmp_path: Path,
) -> None:
    project = _fake_project(tmp_path / "lean-project")
    lake = _fake_lake(tmp_path / "lake")
    artifact = tmp_path / "out" / "Certificate.lean"

    result = verify_polynomial_identity_with_lean(
        _certificate(),
        lake=lake,
        project_root=project,
        artifact_output=artifact,
    )

    assert result["assurance"] == "kernel_checked"
    assert result["checkedBy"]["system"] == "Lean"
    assert result["checkedBy"]["version"] == (
        f"4.33.1, aarch64-apple-darwin+mathlib@{MATHLIB_REVISION}"
    )
    assert result["checkedBy"]["artifactDigest"] == result["artifactDigest"]
    assert artifact.read_text(encoding="utf-8").startswith("import Mathlib.Tactic.Ring")


def test_lean_bridge_reports_kernel_rejection_without_promoting_the_result(
    tmp_path: Path,
) -> None:
    project = _fake_project(tmp_path / "lean-project")
    lake = _fake_lake(tmp_path / "lake", accept=False)

    with pytest.raises(CalculatorError) as raised:
        verify_polynomial_identity_with_lean(
            _certificate(),
            lake=lake,
            project_root=project,
        )

    assert raised.value.code == "E_KERNEL"
    assert "kernel rejection" in raised.value.message


def test_lean_bridge_rejects_unpinned_project_and_checker_versions(tmp_path: Path) -> None:
    project = _fake_project(tmp_path / "lean-project")
    (project / "lean-toolchain").write_text("leanprover/lean4:v4.32.0\n", encoding="utf-8")
    lake = _fake_lake(tmp_path / "lake")

    with pytest.raises(CalculatorError, match="does not match the pinned") as project_error:
        verify_polynomial_identity_with_lean(
            _certificate(), lake=lake, project_root=project
        )
    assert project_error.value.code == "E_INPUT"

    (project / "lean-toolchain").write_text(f"{LEAN_TOOLCHAIN}\n", encoding="utf-8")
    stale_lake = _fake_lake(tmp_path / "stale-lake", version="4.32.0")
    with pytest.raises(CalculatorError, match="Lean version mismatch") as version_error:
        verify_polynomial_identity_with_lean(
            _certificate(), lake=stale_lake, project_root=project
        )
    assert version_error.value.code == "E_UNAVAILABLE"


def test_lean_bridge_rejects_sorry_axioms_and_missing_axiom_readback(tmp_path: Path) -> None:
    project = _fake_project(tmp_path / "lean-project")
    for name, output, message in (
        ("sorry-lake", "'certificate' depends on axioms: [sorryAx]", "sorryAx"),
        ("silent-lake", "kernel accepted", "did not report"),
    ):
        lake = _fake_lake(tmp_path / name, kernel_output=output)
        with pytest.raises(CalculatorError, match=message) as raised:
            verify_polynomial_identity_with_lean(
                _certificate(), lake=lake, project_root=project
            )
        assert raised.value.code == "E_KERNEL"


def test_lean_subprocess_output_is_bounded(tmp_path: Path) -> None:
    noisy = tmp_path / "noisy"
    noisy.write_text(
        "#!/bin/sh\npython3 - <<'PY'\nprint('x' * 100000)\nPY\n",
        encoding="utf-8",
    )
    noisy.chmod(0o755)

    completed = _run([str(noisy)], cwd=tmp_path, timeout=10)

    assert completed.returncode == 0
    assert len(completed.stdout.encode("utf-8")) <= MAX_KERNEL_OUTPUT_BYTES + 20
    assert completed.stdout.endswith("...<truncated>")


def test_lean_bridge_rejects_truncated_axiom_output() -> None:
    with pytest.raises(CalculatorError, match="exceeded the supported limit") as raised:
        _validate_kernel_output("'certificate' depends on axioms: []\n...<truncated>")

    assert raised.value.code == "E_KERNEL"


@pytest.mark.parametrize("timeout", (0, -1, 601, True, 1.5))
def test_lean_bridge_rejects_unbounded_timeout_values(tmp_path: Path, timeout: object) -> None:
    with pytest.raises(CalculatorError, match="timeout must be an integer") as raised:
        verify_polynomial_identity_with_lean(
            _certificate(),
            lake=tmp_path / "missing-lake",
            project_root=tmp_path / "missing-project",
            timeout=timeout,  # type: ignore[arg-type]
        )

    assert raised.value.code == "E_INPUT"
