"""Structural probes that reuse obligation runtime, certificate binding, and CLI shadow mode.

Not timed comparison cells. Binding probes are the #16-style fail-closed
hooks: a valid certificate for a different statement must not check this
claim. CLI probes exercise product `--quiet-success` / failures_only.
"""

from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

from math_anchor.obligations import (
    OBLIGATION_SET_SCHEMA_VERSION,
    check_obligation_set,
)
from math_anchor.sandbox import run_operation


ROOT = Path(__file__).resolve().parents[2]
CORE_SUITE = ROOT / "evals" / "obligations" / "core.v0.1.json"
SUITE_VERSION = "math-anchor.obligation-conformance-suite.v0.1"


class _SwapRunOperation:
    def __init__(self, replacement):  # type: ignore[no-untyped-def]
        self.replacement = replacement
        self._original = None

    def __enter__(self):  # type: ignore[no-untyped-def]
        import math_anchor.obligations as obligations_mod

        self._original = obligations_mod.run_operation
        obligations_mod.run_operation = self.replacement
        return obligations_mod

    def __exit__(self, exc_type, exc, tb) -> bool:  # type: ignore[no-untyped-def]
        import math_anchor.obligations as obligations_mod

        obligations_mod.run_operation = self._original
        return False


def core_conformance_probe() -> dict[str, Any]:
    suite = json.loads(CORE_SUITE.read_text(encoding="utf-8"))
    if suite.get("schemaVersion") != SUITE_VERSION:
        return {
            "ok": False,
            "reason": "obligation conformance suite version mismatch",
            "suite": str(CORE_SUITE.relative_to(ROOT)),
        }
    feedback, receipt = check_obligation_set(suite["request"])
    observed = [
        {key: entry[key] for key in ("id", "status", "assuranceLevel", "scope")}
        for entry in receipt["obligations"]
    ]
    matched = observed == suite.get("expected")
    failures_request = deepcopy(suite["request"])
    failures_request["responseMode"] = "failures_only"
    failures_feedback, failures_receipt = check_obligation_set(failures_request)
    checked_ids = {
        entry["id"]
        for entry in failures_receipt["obligations"]
        if entry["status"] == "checked"
    }
    returned_ids = {entry["id"] for entry in failures_feedback["obligations"]}
    leaked_checked = bool(checked_ids & returned_ids)
    statuses = {entry["id"]: entry["status"] for entry in receipt["obligations"]}
    return {
        "ok": matched and not leaked_checked,
        "suite": str(CORE_SUITE.relative_to(ROOT)),
        "matchedExpected": matched,
        "failuresOnlyLeakedChecked": leaked_checked,
        "statuses": statuses,
        "exercisedChecked": "checked" in statuses.values(),
        "exercisedFalsified": "falsified" in statuses.values(),
        "exercisedUnsupported": "unsupported" in statuses.values(),
        "exercisedDependencyBlocked": "unknown" in statuses.values(),
        "feedbackStatus": feedback.get("status"),
        "receiptDigest": receipt.get("receiptDigest"),
        "note": (
            "evals/obligations/core.v0.1.json is the existing conformance "
            "corpus. This probe does not replace it."
        ),
    }


def _binding_probe(
    *,
    name: str,
    corruption_kind: str,
    producer_claim: dict[str, Any],
    caller_claim: dict[str, Any],
) -> dict[str, Any]:
    producer = run_operation("certificate.polynomial_identity", producer_claim)
    if producer.get("status") != "ok":
        return {
            "ok": False,
            "name": name,
            "corruptionKind": corruption_kind,
            "reason": "producer_did_not_return_ok",
            "producerStatus": producer.get("status"),
        }
    request = {
        "schemaVersion": OBLIGATION_SET_SCHEMA_VERSION,
        "obligations": [
            {
                "id": name,
                "kind": "polynomial_identity",
                "claim": caller_claim,
            }
        ],
        "responseMode": "failures_only",
    }
    with _SwapRunOperation(lambda *args, **kwargs: producer):
        feedback, receipt = check_obligation_set(request)
    entry = receipt["obligations"][0]
    detail = entry.get("detail") if isinstance(entry.get("detail"), dict) else {}
    rejected = (
        entry.get("status") == "unknown" and detail.get("reason") == "certificate_rejected"
    )
    return {
        "ok": rejected,
        "name": name,
        "corruptionKind": corruption_kind,
        "failClosed": rejected,
        "checked": entry.get("status") == "checked",
        "status": entry.get("status"),
        "reason": detail.get("reason"),
        "message": detail.get("message"),
        "feedbackStatus": feedback.get("status"),
        "producerStatement": (producer.get("certificate") or {}).get("statement"),
        "callerClaim": caller_claim,
        "hook": "math_anchor.obligations._polynomial_entry claim-binding",
        "independentChecker": "math-anchor-stdlib-polynomial-checker",
        "note": (
            "Valid producer certificate for a different statement cannot check "
            "this obligation. Producer vs checker: the stdlib checker is "
            "independent of SymPy; the obligation runtime still uses the "
            "certificate.polynomial_identity producer for the success path."
        ),
    }


def wrong_witness_probe() -> dict[str, Any]:
    return _binding_probe(
        name="wrong-witness",
        corruption_kind="wrong_witness",
        producer_claim={"left": "x", "right": "x", "variables": ["x", "y"]},
        caller_claim={
            "left": "(x + y)^2",
            "right": "x^2 + 2*x*y + y^2",
            "variables": ["x", "y"],
        },
    )


def stale_swapped_probe() -> dict[str, Any]:
    return _binding_probe(
        name="stale-swapped-result",
        corruption_kind="stale_swapped_result",
        producer_claim={
            "left": "(x + y)^2",
            "right": "x^2 + 2*x*y + y^2",
            "variables": ["x", "y"],
        },
        caller_claim={
            "left": "(x - y)^2",
            "right": "x^2 - 2*x*y + y^2",
            "variables": ["x", "y"],
        },
    )


def _cli_env() -> dict[str, str]:
    environment = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    return environment


def cli_quiet_success_probe(tmp_dir: Path) -> dict[str, Any]:
    request_path = tmp_dir / "quiet-success-request.json"
    receipt_path = tmp_dir / "quiet-success-receipt.json"
    request = {
        "schemaVersion": OBLIGATION_SET_SCHEMA_VERSION,
        "obligations": [
            {
                "id": "identity",
                "kind": "polynomial_identity",
                "claim": {
                    "left": "(x + y)^2",
                    "right": "x^2 + 2*x*y + y^2",
                    "variables": ["x", "y"],
                },
            }
        ],
        "responseMode": "failures_only",
    }
    request_path.write_text(json.dumps(request), encoding="utf-8")
    completed = subprocess.run(
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
        env=_cli_env(),
        capture_output=True,
        text=True,
        check=False,
    )
    stdout_empty = completed.stdout == ""
    receipt_exists = receipt_path.is_file()
    receipt = json.loads(receipt_path.read_text(encoding="utf-8")) if receipt_exists else {}
    return {
        "ok": completed.returncode == 0 and stdout_empty and receipt_exists,
        "exitCode": completed.returncode,
        "stdoutBytes": len(completed.stdout.encode("utf-8")),
        "stdoutEmpty": stdout_empty,
        "receiptExists": receipt_exists,
        "receiptOutsideModelContext": receipt_exists,
        "receiptChecked": (receipt.get("summary") or {}).get("checked"),
        "hook": "math-anchor check-obligations --quiet-success --receipt-output",
        "note": (
            "Product CLI shadow path: successful receipt is a local file; "
            "model-context stdout is empty. Silence is not proof of use."
        ),
    }


def cli_failures_only_on_fail_probe(tmp_dir: Path) -> dict[str, Any]:
    request_path = tmp_dir / "sign-flip-request.json"
    request = {
        "schemaVersion": OBLIGATION_SET_SCHEMA_VERSION,
        "obligations": [
            {
                "id": "sign-flip",
                "kind": "polynomial_identity",
                "claim": {
                    "left": "(x + y)^2",
                    "right": "x^2 - 2*x*y + y^2",
                    "variables": ["x", "y"],
                },
            }
        ],
        "responseMode": "failures_only",
    }
    request_path.write_text(json.dumps(request), encoding="utf-8")
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
        env=_cli_env(),
        capture_output=True,
        text=True,
        check=False,
    )
    payload: dict[str, Any]
    try:
        payload = json.loads(completed.stdout) if completed.stdout else {}
    except json.JSONDecodeError:
        payload = {}
    obligation_ids = [
        entry.get("id")
        for entry in payload.get("obligations") or []
        if isinstance(entry, dict)
    ]
    return {
        "ok": (
            completed.returncode == 1
            and payload.get("status") == "attention_required"
            and payload.get("responseMode") == "failures_only"
            and obligation_ids == ["sign-flip"]
        ),
        "exitCode": completed.returncode,
        "feedbackStatus": payload.get("status"),
        "responseMode": payload.get("responseMode"),
        "obligationIds": obligation_ids,
        "stdoutBytes": len(completed.stdout.encode("utf-8")),
        "hook": "math-anchor check-obligations --quiet-success (failure path)",
        "note": (
            "--quiet-success suppresses stdout only on exit 0. Falsified "
            "claims still return failures_only feedback."
        ),
    }



def _seeded_obligation_probe(
    *,
    name: str,
    corruption_kind: str,
    request: dict[str, Any],
    primary_id: str,
    expected_status: str,
    g1_supported: bool,
) -> dict[str, Any]:
    feedback, receipt = check_obligation_set(request)
    entry = next(
        (item for item in receipt["obligations"] if item.get("id") == primary_id),
        None,
    )
    if entry is None:
        return {
            "ok": False,
            "name": name,
            "corruptionKind": corruption_kind,
            "g1SupportedSeededError": g1_supported,
            "reason": "primary_obligation_missing",
        }
    detail = entry.get("detail") if isinstance(entry.get("detail"), dict) else {}
    matched = entry.get("status") == expected_status
    return {
        "ok": matched,
        "name": name,
        "corruptionKind": corruption_kind,
        "g1SupportedSeededError": g1_supported,
        "primaryObligationId": primary_id,
        "status": entry.get("status"),
        "expectedStatus": expected_status,
        "reason": detail.get("reason"),
        "feedbackStatus": feedback.get("status"),
        "hook": "math_anchor.obligations.check_obligation_set",
        "note": (
            "Expanded adversarial corpus probe. Reuses the existing obligation "
            "runtime; not a second stack."
        ),
    }


def rounding_sneak_probe() -> dict[str, Any]:
    return _seeded_obligation_probe(
        name="rounding-sneak",
        corruption_kind="rounding_sneak",
        primary_id="rounded-third",
        expected_status="falsified",
        g1_supported=True,
        request={
            "schemaVersion": OBLIGATION_SET_SCHEMA_VERSION,
            "obligations": [
                {
                    "id": "rounded-third",
                    "kind": "expression_equivalence",
                    "claim": {
                        "left": "1/3",
                        "right": "0.333333",
                        "variables": [],
                        "domain": "real",
                        "definednessPolicy": "strict",
                    },
                }
            ],
            "responseMode": "failures_only",
        },
    )


def unit_scale_mismatch_probe() -> dict[str, Any]:
    return _seeded_obligation_probe(
        name="unit-scale-mismatch",
        corruption_kind="unit_scale_mismatch",
        primary_id="pressure-area-meter",
        expected_status="falsified",
        g1_supported=True,
        request={
            "schemaVersion": OBLIGATION_SET_SCHEMA_VERSION,
            "obligations": [
                {
                    "id": "pressure-area-meter",
                    "kind": "dimension_consistency",
                    "claim": {
                        "left": "pressure",
                        "right": "force / area",
                        "symbols": {
                            "pressure": "pascal",
                            "force": "newton",
                            "area": "meter",
                        },
                    },
                }
            ],
            "responseMode": "failures_only",
        },
    )


def assumption_swap_probe() -> dict[str, Any]:
    return _seeded_obligation_probe(
        name="assumption-swapped",
        corruption_kind="assumption_swap",
        primary_id="sqrt-square-all-reals",
        expected_status="falsified",
        g1_supported=True,
        request={
            "schemaVersion": OBLIGATION_SET_SCHEMA_VERSION,
            "obligations": [
                {
                    "id": "sqrt-square-all-reals",
                    "kind": "expression_equivalence",
                    "claim": {
                        "left": "sqrt(x)^2",
                        "right": "x",
                        "variables": ["x"],
                        "domain": "real",
                        "definednessPolicy": "strict",
                    },
                }
            ],
            "responseMode": "failures_only",
        },
    )


def step_n_legal_wrong_probe() -> dict[str, Any]:
    return _seeded_obligation_probe(
        name="step-n-legal-wrong-value",
        corruption_kind="step_n_legal_wrong_value",
        primary_id="step-2-wrong-for-claim",
        expected_status="falsified",
        g1_supported=True,
        request={
            "schemaVersion": OBLIGATION_SET_SCHEMA_VERSION,
            "obligations": [
                {
                    "id": "step-1-legal",
                    "kind": "polynomial_identity",
                    "claim": {
                        "left": "(x + y)*(x - y)",
                        "right": "x^2 - y^2",
                        "variables": ["x", "y"],
                    },
                },
                {
                    "id": "step-2-wrong-for-claim",
                    "kind": "polynomial_identity",
                    "claim": {
                        "left": "(x + y)^2",
                        "right": "x^2 - y^2",
                        "variables": ["x", "y"],
                    },
                    "dependsOn": ["step-1-legal"],
                },
            ],
            "responseMode": "failures_only",
        },
    )


def run_structural_probes(tmp_dir: Path) -> dict[str, Any]:
    tmp_dir.mkdir(parents=True, exist_ok=True)
    core = core_conformance_probe()
    wrong = wrong_witness_probe()
    stale = stale_swapped_probe()
    quiet = cli_quiet_success_probe(tmp_dir)
    failure = cli_failures_only_on_fail_probe(tmp_dir)
    rounding = rounding_sneak_probe()
    unit = unit_scale_mismatch_probe()
    assumption = assumption_swap_probe()
    step_n = step_n_legal_wrong_probe()
    probes = (
        core,
        wrong,
        stale,
        quiet,
        failure,
        rounding,
        unit,
        assumption,
        step_n,
    )
    ok = all(probe.get("ok") is True for probe in probes)
    return {
        "ok": ok,
        "coreConformance": core,
        "wrongWitness": wrong,
        "staleSwappedResult": stale,
        "cliQuietSuccess": quiet,
        "cliFailuresOnlyOnFail": failure,
        "roundingSneak": rounding,
        "unitScaleMismatch": unit,
        "assumptionSwap": assumption,
        "stepNLegalWrong": step_n,
    }
