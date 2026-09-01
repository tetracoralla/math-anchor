from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
SPEC = importlib.util.spec_from_file_location(
    "lean_reference_check",
    ROOT / "script" / "lean_reference_check.py",
)
assert SPEC is not None and SPEC.loader is not None
lean_reference = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = lean_reference
SPEC.loader.exec_module(lean_reference)


def _digest(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{sha256(encoded).hexdigest()}"


def _certificate(
    left: str,
    right: str,
    variables: list[str],
    *,
    identity: bool = True,
    normalized_difference: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    statement = {"left": left, "right": right, "variables": variables}
    certificate: dict[str, object] = {
        "format": "math-anchor.polynomial-identity.v1",
        "statement": statement,
        "statementDigest": _digest(statement),
        "identity": identity,
        "normalizedDifference": normalized_difference or [],
    }
    certificate["certificateDigest"] = _digest(certificate)
    return certificate


def test_putnam_bridge_fixture_translates_to_a_bound_lean_theorem() -> None:
    certificate = _certificate(
        "(x + y)**4 + (x**4 + y**4)",
        "2 * (x**2 + x*y + y**2)**2",
        ["x", "y"],
    )

    source = lean_reference.build_lean_source(certificate).decode("utf-8")

    assert "theorem mathAnchorCertificate (v0 v1 : ℚ)" in source
    assert "by\n  ring" in source
    assert certificate["certificateDigest"] in source
    assert "sorry" not in source
    assert "axiom " not in source


def test_rational_coefficients_are_translated_without_float_literals() -> None:
    certificate = _certificate("(x + y)/3", "x/3 + y/3", ["x", "y"])

    source = lean_reference.build_lean_source(certificate).decode("utf-8")

    assert "/ (3 : ℚ)" in source
    assert "0.333" not in source


def test_false_identity_never_reaches_the_kernel() -> None:
    certificate = _certificate(
        "x**2",
        "x",
        ["x"],
        identity=False,
        normalized_difference=[
            {"powers": [2], "coefficient": "1"},
            {"powers": [1], "coefficient": "-1"},
        ],
    )

    with pytest.raises(lean_reference.LeanReferenceError, match="false identity") as error:
        lean_reference.build_lean_source(certificate)

    assert error.value.code == "E_CERTIFICATE"


def test_recomputed_digest_cannot_hide_tampered_coefficients() -> None:
    certificate = deepcopy(_certificate("x**2", "x**2", ["x"]))
    certificate["normalizedDifference"] = [{"powers": [0], "coefficient": "1"}]
    digest_payload = dict(certificate)
    digest_payload.pop("certificateDigest")
    certificate["certificateDigest"] = _digest(digest_payload)

    with pytest.raises(lean_reference.LeanReferenceError, match="coefficients do not match") as error:
        lean_reference.build_lean_source(certificate)

    assert error.value.code == "E_CERTIFICATE"


def test_certificate_variable_names_are_mapped_not_interpolated() -> None:
    certificate = _certificate("theorem + by", "by + theorem", ["theorem", "by"])

    source = lean_reference.build_lean_source(certificate).decode("utf-8")

    theorem_body = source.split("theorem mathAnchorCertificate", 1)[1]
    assert "theorem + by" not in theorem_body
    assert "v0" in theorem_body and "v1" in theorem_body


def test_kernel_output_with_sorry_axiom_is_rejected() -> None:
    with pytest.raises(lean_reference.LeanReferenceError, match="sorryAx") as error:
        lean_reference._validate_kernel_output(
            b"'mathAnchorCertificate' depends on axioms: [sorryAx]"
        )

    assert error.value.code == "E_KERNEL"


@pytest.mark.parametrize(
    "output",
    (
        b"",
        b"kernel accepted",
        b"'mathAnchorCertificate' depends on axioms: []\n" + b"x" * 70_000,
    ),
)
def test_kernel_output_requires_one_complete_axiom_report(output: bytes) -> None:
    with pytest.raises(lean_reference.LeanReferenceError) as error:
        lean_reference._validate_kernel_output(output)

    assert error.value.code == "E_KERNEL"


@pytest.mark.parametrize("timeout", (0, -1, 601, True, 1.5))
def test_reference_rejects_unbounded_timeout_values(timeout: object) -> None:
    certificate = _certificate("x", "x", ["x"])

    with pytest.raises(lean_reference.LeanReferenceError, match="between 1 and 600") as error:
        lean_reference.kernel_check(certificate, timeout_seconds=timeout)  # type: ignore[arg-type]

    assert error.value.code == "E_INPUT"


def test_reference_rejects_an_unavailable_explicit_lake(tmp_path: Path) -> None:
    certificate = _certificate("x", "x", ["x"])

    with pytest.raises(lean_reference.LeanReferenceError, match="Lake executable") as error:
        lean_reference.kernel_check(
            certificate,
            timeout_seconds=10,
            lake=tmp_path / "missing-lake",
        )

    assert error.value.code == "E_TOOLCHAIN"
