from __future__ import annotations

from pathlib import Path

import pytest

from math_anchor.certificate_checker import CertificateValidationError
from math_anchor.errors import CalculatorError
from math_anchor.lean_bridge import (
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


def _fake_lake(path: Path, *, accept: bool = True) -> Path:
    path.write_text(
        "#!/bin/sh\n"
        "if [ \"$3\" = \"--version\" ]; then\n"
        "  echo 'Lean (version 4.33.1, aarch64-apple-darwin)'\n"
        "  exit 0\n"
        "fi\n"
        + ("exit 0\n" if accept else "echo 'kernel rejection' >&2\nexit 1\n"),
        encoding="utf-8",
    )
    path.chmod(0o755)
    return path


def test_lean_artifact_uses_generated_identifiers_and_exact_rational_theorem() -> None:
    source, metadata = build_lean_artifact(_certificate())

    assert "import Mathlib.Tactic" in source
    assert "(v0 v1 : ℚ)" in source
    assert "((v0 + v1) ^ 2)" in source
    assert "by\n  ring" in source
    assert metadata["variableMap"] == {"x": "v0", "y": "v1"}
    assert metadata["theorem"].startswith("certificate_")


def test_lean_bridge_rejects_a_valid_nonidentity_certificate() -> None:
    with pytest.raises(CertificateValidationError, match="identity classification is true"):
        build_lean_artifact(_certificate(identity=False))


def test_lean_bridge_records_the_real_checker_version_and_artifact_digest(
    tmp_path: Path,
) -> None:
    project = tmp_path / "lean-project"
    project.mkdir()
    (project / "lakefile.toml").write_text('name = "test"\n', encoding="utf-8")
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
    assert result["checkedBy"]["version"] == "4.33.1, aarch64-apple-darwin"
    assert result["checkedBy"]["artifactDigest"] == result["artifactDigest"]
    assert artifact.read_text(encoding="utf-8").startswith("import Mathlib.Tactic")


def test_lean_bridge_reports_kernel_rejection_without_promoting_the_result(
    tmp_path: Path,
) -> None:
    project = tmp_path / "lean-project"
    project.mkdir()
    (project / "lakefile.toml").write_text('name = "test"\n', encoding="utf-8")
    lake = _fake_lake(tmp_path / "lake", accept=False)

    with pytest.raises(CalculatorError) as raised:
        verify_polynomial_identity_with_lean(
            _certificate(),
            lake=lake,
            project_root=project,
        )

    assert raised.value.code == "E_KERNEL"
    assert "kernel rejection" in raised.value.message
