from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys

from jsonschema import Draft202012Validator
import pytest

from math_anchor import cli
from math_anchor.certificate_checker import CertificateValidationError
from math_anchor.errors import CalculatorError
from math_anchor.obligations import (
    OBLIGATION_FEEDBACK_SCHEMA_VERSION,
    OBLIGATION_RECEIPT_SCHEMA_VERSION,
    OBLIGATION_REPLAY_SCHEMA_VERSION,
    OBLIGATION_SET_SCHEMA_VERSION,
    check_obligation_set,
    obligation_feedback_schema,
    obligation_receipt_schema,
    obligation_request_schema,
    replay_obligation_set,
)


ROOT = Path(__file__).resolve().parents[2]


def _request(*obligations: dict[str, object], response_mode: str = "failures_only") -> dict[str, object]:
    return {
        "schemaVersion": OBLIGATION_SET_SCHEMA_VERSION,
        "assumptionSets": [
            {
                "id": "rational-context",
                "assumptions": ["x and y are commuting indeterminates"],
            }
        ],
        "obligations": list(obligations),
        "assurancePolicy": "strongest_available",
        "responseMode": response_mode,
    }


def _polynomial(obligation_id: str, right: str, **extra: object) -> dict[str, object]:
    return {
        "id": obligation_id,
        "kind": "polynomial_identity",
        "claim": {
            "left": "(x + y)^2",
            "right": right,
            "variables": ["x", "y"],
        },
        "assumptionSet": "rational-context",
        **extra,
    }


def _canonical_digest(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{sha256(payload).hexdigest()}"


def test_obligation_schemas_are_valid_and_outputs_validate() -> None:
    for schema in (
        obligation_request_schema(),
        obligation_receipt_schema(),
        obligation_feedback_schema(),
    ):
        Draft202012Validator.check_schema(schema)

    request = _request(_polynomial("identity", "x^2 + 2*x*y + y^2"))
    feedback, receipt = check_obligation_set(request)

    Draft202012Validator(obligation_feedback_schema()).validate(feedback)
    Draft202012Validator(obligation_receipt_schema()).validate(receipt)
    assert feedback["schemaVersion"] == OBLIGATION_FEEDBACK_SCHEMA_VERSION
    assert receipt["schemaVersion"] == OBLIGATION_RECEIPT_SCHEMA_VERSION


def test_failures_only_bundle_distinguishes_falsified_unsupported_and_dependency_unknown() -> None:
    request = _request(
        _polynomial("identity", "x^2 + 2*x*y + y^2"),
        {
            "id": "dimension-error",
            "kind": "dimension_consistency",
            "claim": {
                "left": "distance",
                "right": "speed + time",
                "symbols": {
                    "distance": "meter",
                    "speed": "meter / second",
                    "time": "second",
                },
            },
        },
        {
            "id": "sheaf-step",
            "kind": "sheaf_cohomology_vanishing",
            "claim": {"statement": "H^1(X, O_X) = 0"},
        },
        {
            "id": "dependent-step",
            "kind": "polynomial_identity",
            "claim": {"left": "x", "right": "x", "variables": ["x"]},
            "dependsOn": ["sheaf-step"],
        },
    )

    feedback, receipt = check_obligation_set(request)

    assert feedback["status"] == "attention_required"
    assert feedback["summary"] == {
        "checked": 1,
        "falsified": 1,
        "unknown": 1,
        "unsupported": 1,
        "total": 4,
    }
    assert [entry["id"] for entry in feedback["obligations"]] == [
        "dimension-error",
        "sheaf-step",
        "dependent-step",
    ]
    statuses = {entry["id"]: entry["status"] for entry in receipt["obligations"]}
    assert statuses == {
        "identity": "checked",
        "dimension-error": "falsified",
        "sheaf-step": "unsupported",
        "dependent-step": "unknown",
    }
    dependent = receipt["obligations"][-1]
    assert dependent["blockedBy"] == ["sheaf-step"]
    assert dependent["provider"] is None
    identity = receipt["obligations"][0]
    assert identity["assumptions"]["setId"] == "rational-context"
    assert identity["assumptions"]["interpretation"] == "bound_not_evaluated"
    assert identity["detail"]["checker"]["system"] == (
        "math-anchor-stdlib-polynomial-checker"
    )


def test_success_feedback_is_small_and_omits_checked_details() -> None:
    feedback, receipt = check_obligation_set(
        _request(_polynomial("identity", "x^2 + 2*x*y + y^2"))
    )

    assert feedback["status"] == "checked"
    assert feedback["obligations"] == []
    assert len(json.dumps(feedback, separators=(",", ":")).encode()) < 800
    assert receipt["obligations"][0]["detail"]["identity"] is True
    assert receipt["obligations"][0]["provider"]["resultDigest"].startswith("sha256:")


def test_full_response_retains_checked_obligation_scope_and_limit_disclosures() -> None:
    request = _request(
        {
            "id": "local-J",
            "kind": "local_almost_complex_integrability",
            "claim": {
                "coordinates": ["x", "y"],
                "structure": [["0", "-1"], ["1", "0"]],
            },
        },
        response_mode="full",
    )

    feedback, _receipt = check_obligation_set(request)

    entry = feedback["obligations"][0]
    assert entry["status"] == "checked"
    assert entry["assuranceLevel"] == "exact_symbolic"
    assert entry["scope"] == "local_coordinate_rational_polynomial_almost_complex_check"
    assert "chart_and_global_manifold_obligations_unchecked" in entry["limitations"]
    assert "global_topological_and_analytic_existence" in entry["detail"][
        "uncheckedGlobalObligations"
    ]


@pytest.mark.parametrize(
    "mutation, message",
    [
        (
            lambda value: value["obligations"].append(deepcopy(value["obligations"][0])),
            "obligation ids must be unique",
        ),
        (
            lambda value: value["obligations"][0].update({"dependsOn": ["missing"]}),
            "unknown dependency",
        ),
        (
            lambda value: value["obligations"][0].update({"dependsOn": ["identity"]}),
            "cannot depend on itself",
        ),
        (
            lambda value: value["obligations"][0]["claim"].update({"invented": True}),
            "invalid certificate.polynomial_identity arguments",
        ),
    ],
)
def test_request_preflight_rejects_invalid_graph_and_known_claims(
    mutation: object,
    message: str,
) -> None:
    request = _request(_polynomial("identity", "x^2 + 2*x*y + y^2"))
    mutation(request)  # type: ignore[operator]

    with pytest.raises(CalculatorError, match=message):
        check_obligation_set(request)


def test_request_preflight_rejects_dependency_cycles() -> None:
    request = _request(
        _polynomial("a", "x^2 + 2*x*y + y^2", dependsOn=["b"]),
        _polynomial("b", "x^2 + 2*x*y + y^2", dependsOn=["a"]),
    )

    with pytest.raises(CalculatorError, match="contains a cycle"):
        check_obligation_set(request)


def test_independent_certificate_rejection_cannot_be_promoted_to_checked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def reject(_certificate: object) -> dict[str, object]:
        raise CertificateValidationError("injected certificate corruption")

    monkeypatch.setattr(
        "math_anchor.obligations.verify_polynomial_identity_certificate",
        reject,
    )
    feedback, receipt = check_obligation_set(
        _request(_polynomial("identity", "x^2 + 2*x*y + y^2"))
    )

    assert feedback["status"] == "attention_required"
    entry = receipt["obligations"][0]
    assert entry["status"] == "unknown"
    assert entry["assuranceLevel"] is None
    assert entry["detail"]["reason"] == "certificate_rejected"


@pytest.mark.parametrize(
    "error_code",
    ["E_AST_BLOCK", "E_DOMAIN", "E_INPUT", "E_NAME", "E_SYNTAX", "E_UNIT"],
)
def test_caller_correctable_provider_rejection_is_unsupported(
    monkeypatch: pytest.MonkeyPatch,
    error_code: str,
) -> None:
    def reject(*_args: object, **_kwargs: object) -> dict[str, object]:
        return {
            "status": "error",
            "error": {
                "code": error_code,
                "message": "injected caller-correctable rejection",
                "retryable": False,
            },
        }

    monkeypatch.setattr("math_anchor.obligations.run_operation", reject)
    _feedback, receipt = check_obligation_set(
        _request(_polynomial("identity", "x^2 + 2*x*y + y^2"))
    )

    entry = receipt["obligations"][0]
    assert entry["status"] == "unsupported"
    assert entry["detail"]["reason"] == "provider_rejected_claim"
    assert entry["detail"]["error"]["code"] == error_code


def test_real_invalid_polynomial_syntax_is_unsupported() -> None:
    invalid = _polynomial("invalid", "x+")
    _feedback, receipt = check_obligation_set(_request(invalid))

    entry = receipt["obligations"][0]
    assert entry["status"] == "unsupported"
    assert entry["detail"]["reason"] == "provider_rejected_claim"
    assert entry["detail"]["error"]["code"] == "E_SYNTAX"


def test_known_provider_operation_mismatch_is_inconclusive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def reject(*_args: object, **_kwargs: object) -> dict[str, object]:
        return {
            "status": "error",
            "error": {
                "code": "E_OPERATION",
                "message": "injected provider registry drift",
                "retryable": False,
            },
        }

    monkeypatch.setattr("math_anchor.obligations.run_operation", reject)
    _feedback, receipt = check_obligation_set(
        _request(_polynomial("identity", "x^2 + 2*x*y + y^2"))
    )

    entry = receipt["obligations"][0]
    assert entry["status"] == "unknown"
    assert entry["detail"]["reason"] == "provider_inconclusive"
    assert entry["detail"]["error"]["code"] == "E_OPERATION"


def test_replay_matches_and_detects_runtime_only_drift() -> None:
    request = _request(_polynomial("identity", "x^2 + 2*x*y + y^2"))
    _feedback, receipt = check_obligation_set(request)

    replay, replay_feedback, current = replay_obligation_set(request, receipt)
    assert replay["schemaVersion"] == OBLIGATION_REPLAY_SCHEMA_VERSION
    assert replay["status"] == "matched"
    assert replay["outcomeMatch"] is True
    assert replay_feedback["status"] == "checked"
    assert current["receiptDigest"] == receipt["receiptDigest"]

    prior_runtime = deepcopy(receipt)
    prior_runtime["runtime"]["version"] = "0.4.99"
    digest_payload = dict(prior_runtime)
    digest_payload.pop("receiptDigest")
    prior_runtime["receiptDigest"] = _canonical_digest(digest_payload)
    drift, _feedback, _current = replay_obligation_set(request, prior_runtime)
    assert drift["status"] == "runtime_drift"
    assert drift["outcomeMatch"] is True
    assert drift["runtimeMatch"] is False


def test_replay_rejects_corrupted_receipt_content() -> None:
    request = _request(_polynomial("identity", "x^2 + 2*x*y + y^2"))
    _feedback, receipt = check_obligation_set(request)
    receipt["obligations"][0]["status"] = "falsified"

    with pytest.raises(CalculatorError, match="receipt digest"):
        replay_obligation_set(request, receipt)


def test_cli_shadow_mode_is_silent_on_success_and_writes_new_receipt(tmp_path: Path) -> None:
    request_path = tmp_path / "request.json"
    receipt_path = tmp_path / "receipt.json"
    request_path.write_text(
        json.dumps(_request(_polynomial("identity", "x^2 + 2*x*y + y^2"))),
        encoding="utf-8",
    )
    environment = {**os.environ, "PYTHONPATH": str(ROOT / "src")}

    checked = subprocess.run(
        [
            sys.executable,
            "-m",
            "math_anchor.cli",
            "check-obligations",
            str(request_path),
            "--receipt-output",
            str(receipt_path),
            "--quiet-success",
        ],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert checked.returncode == 0, checked.stderr
    assert checked.stdout == ""
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["summary"]["checked"] == 1

    replayed = subprocess.run(
        [
            sys.executable,
            "-m",
            "math_anchor.cli",
            "replay-obligations",
            str(request_path),
            str(receipt_path),
        ],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert replayed.returncode == 0, replayed.stderr
    assert json.loads(replayed.stdout)["status"] == "matched"

    no_overwrite = subprocess.run(
        [
            sys.executable,
            "-m",
            "math_anchor.cli",
            "check-obligations",
            str(request_path),
            "--receipt-output",
            str(receipt_path),
        ],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert no_overwrite.returncode == 2
    assert json.loads(no_overwrite.stdout)["error"]["code"] == "E_INPUT"


def test_receipt_write_failure_leaves_no_partial_target_or_staging_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "receipt.json"

    def fail_before_publish(_descriptor: int) -> None:
        raise OSError("injected durability failure")

    monkeypatch.setattr(cli.os, "fsync", fail_before_publish)
    with pytest.raises(CalculatorError, match="could not be written"):
        cli._write_new_json(target, {"status": "ok"}, label="receipt output")

    assert not target.exists()
    assert list(tmp_path.iterdir()) == []


def test_receipt_publish_is_no_clobber_and_cleans_its_staging_file(
    tmp_path: Path,
) -> None:
    target = tmp_path / "receipt.json"
    target.write_text('{"existing":true}\n', encoding="utf-8")

    with pytest.raises(CalculatorError, match="refusing to overwrite"):
        cli._write_new_json(target, {"replacement": True}, label="receipt output")

    assert json.loads(target.read_text(encoding="utf-8")) == {"existing": True}
    assert [path.name for path in tmp_path.iterdir()] == ["receipt.json"]


def test_cli_returns_attention_exit_for_falsified_claim(tmp_path: Path) -> None:
    request_path = tmp_path / "request.json"
    request_path.write_text(
        json.dumps(_request(_polynomial("false", "x^2 + y^2"))),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "math_anchor.cli",
            "check-obligations",
            str(request_path),
            "--quiet-success",
        ],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 1
    assert completed.stderr == ""
    assert json.loads(completed.stdout)["status"] == "attention_required"
