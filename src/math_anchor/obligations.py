from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
import time
from typing import Any

from jsonschema import Draft202012Validator

from . import __version__
from .catalog import OPERATIONS
from .certificate_checker import (
    CertificateValidationError,
    verify_polynomial_identity_certificate,
)
from .contracts import validate_operation_arguments
from .errors import CalculatorError
from .output_policy import MAX_OUTPUT_BYTES, MIN_OUTPUT_BYTES
from .sandbox import run_batch, run_operation
from .transport_budget import TransportBudgetError, encode_json_line


OBLIGATION_SET_SCHEMA_VERSION = "math-anchor.obligation-set.v0.1"
OBLIGATION_RECEIPT_SCHEMA_VERSION = "math-anchor.obligation-receipt.v0.1"
OBLIGATION_FEEDBACK_SCHEMA_VERSION = "math-anchor.obligation-feedback.v0.1"
OBLIGATION_REPLAY_SCHEMA_VERSION = "math-anchor.obligation-replay.v0.1"
MAX_OBLIGATION_REQUEST_BYTES = 1_048_576
MAX_OBLIGATION_REQUEST_NODES = 50_000
MAX_OBLIGATION_REQUEST_DEPTH = 32
MAX_RECEIPT_BYTES = 1_048_576
DEFAULT_TIMEOUT_MS = 10_000
DEFAULT_MEMORY_MB = 2_048
DEFAULT_PROVIDER_OUTPUT_BYTES = 64 * 1_024
DEFAULT_FEEDBACK_BYTES = 64 * 1_024
STATUS_VALUES = ("checked", "falsified", "unknown", "unsupported")
ASSURANCE_VALUES = (
    "formal_kernel_checked",
    "exact_symbolic",
    "rigorous_interval",
    "numerical",
    "heuristic",
)
_IDENTIFIER = r"^[A-Za-z][A-Za-z0-9._-]{0,63}$"
_KIND = r"^[a-z][a-z0-9._-]{0,63}$"
_DIGEST = r"^sha256:[0-9a-f]{64}$"
_KNOWN_PROVIDERS = {
    "polynomial_identity": "certificate.polynomial_identity",
    "expression_equivalence": "expression.equivalent",
    "dimension_consistency": "dimension.check",
    "local_almost_complex_integrability": "geometry.almost_complex.local_check",
}
_UNSUPPORTED_PROVIDER_ERRORS = {
    "E_AST_BLOCK",
    "E_DOMAIN",
    "E_INPUT",
    "E_NAME",
    "E_SYNTAX",
    "E_UNIT",
}


def _closed_object(
    properties: dict[str, Any],
    required: tuple[str, ...] = (),
) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
        "required": list(required),
    }


_ASSUMPTION_SET_SCHEMA = _closed_object(
    {
        "id": {"type": "string", "pattern": _IDENTIFIER},
        "assumptions": {
            "type": "array",
            "minItems": 1,
            "maxItems": 32,
            "uniqueItems": True,
            "items": {"type": "string", "minLength": 1, "maxLength": 512},
        },
    },
    ("id", "assumptions"),
)
_OBLIGATION_SCHEMA = _closed_object(
    {
        "id": {"type": "string", "pattern": _IDENTIFIER},
        "kind": {"type": "string", "pattern": _KIND},
        "claim": {
            "type": "object",
            "maxProperties": 32,
            "description": (
                "A bounded provider-native claim. Registered kinds are checked against their exact "
                "operation contract; unknown kinds return unsupported without interpreting this object."
            ),
        },
        "assumptionSet": {
            "oneOf": [
                {"type": "string", "pattern": _IDENTIFIER},
                {"type": "null"},
            ],
            "default": None,
        },
        "dependsOn": {
            "type": "array",
            "maxItems": 16,
            "uniqueItems": True,
            "items": {"type": "string", "pattern": _IDENTIFIER},
            "default": [],
        },
    },
    ("id", "kind", "claim"),
)
_LIMITS_SCHEMA = _closed_object(
    {
        "timeoutMs": {
            "type": "integer",
            "minimum": 100,
            "maximum": 30_000,
            "default": DEFAULT_TIMEOUT_MS,
        },
        "memoryMb": {
            "type": "integer",
            "minimum": 256,
            "maximum": 4_096,
            "default": DEFAULT_MEMORY_MB,
        },
        "providerOutputBytes": {
            "type": "integer",
            "minimum": MIN_OUTPUT_BYTES,
            "maximum": MAX_OUTPUT_BYTES,
            "default": DEFAULT_PROVIDER_OUTPUT_BYTES,
        },
        "feedbackBytes": {
            "type": "integer",
            "minimum": MIN_OUTPUT_BYTES,
            "maximum": MAX_OUTPUT_BYTES,
            "default": DEFAULT_FEEDBACK_BYTES,
        },
    }
)
_OBLIGATION_REQUEST_SCHEMA = _closed_object(
    {
        "schemaVersion": {"const": OBLIGATION_SET_SCHEMA_VERSION},
        "assumptionSets": {
            "type": "array",
            "maxItems": 16,
            "items": _ASSUMPTION_SET_SCHEMA,
            "default": [],
        },
        "obligations": {
            "type": "array",
            "minItems": 1,
            "maxItems": 32,
            "items": _OBLIGATION_SCHEMA,
        },
        "assurancePolicy": {
            "const": "strongest_available",
            "default": "strongest_available",
        },
        "responseMode": {
            "enum": ["failures_only", "full"],
            "default": "failures_only",
        },
        "limits": _LIMITS_SCHEMA,
    },
    ("schemaVersion", "obligations"),
)

_ASSUMPTION_REFERENCE_SCHEMA = _closed_object(
    {
        "setId": {
            "oneOf": [
                {"type": "string", "pattern": _IDENTIFIER},
                {"type": "null"},
            ]
        },
        "digest": {"type": "string", "pattern": _DIGEST},
        "count": {"type": "integer", "minimum": 0, "maximum": 32},
        "interpretation": {"const": "bound_not_evaluated"},
    },
    ("setId", "digest", "count", "interpretation"),
)
_PROVIDER_SCHEMA = {
    "oneOf": [
        {"type": "null"},
        _closed_object(
            {
                "operation": {"type": "string", "minLength": 1, "maxLength": 128},
                "resultDigest": {"type": "string", "pattern": _DIGEST},
                "runtime": {
                    "oneOf": [
                        {"type": "null"},
                        _closed_object(
                            {
                                "name": {"const": "math-anchor"},
                                "version": {"type": "string", "minLength": 1, "maxLength": 64},
                            },
                            ("name", "version"),
                        ),
                    ]
                },
                "backends": {
                    "type": "array",
                    "maxItems": 8,
                    "items": _closed_object(
                        {
                            "name": {"type": "string", "minLength": 1, "maxLength": 64},
                            "version": {"type": "string", "minLength": 1, "maxLength": 64},
                        },
                        ("name", "version"),
                    ),
                },
            },
            ("operation", "resultDigest", "runtime", "backends"),
        ),
    ]
}
_RECEIPT_ENTRY_SCHEMA = _closed_object(
    {
        "id": {"type": "string", "pattern": _IDENTIFIER},
        "kind": {"type": "string", "pattern": _KIND},
        "status": {"enum": list(STATUS_VALUES)},
        "assuranceLevel": {
            "oneOf": [{"enum": list(ASSURANCE_VALUES)}, {"type": "null"}]
        },
        "scope": {"type": "string", "minLength": 1, "maxLength": 160},
        "claimDigest": {"type": "string", "pattern": _DIGEST},
        "assumptions": _ASSUMPTION_REFERENCE_SCHEMA,
        "dependsOn": {
            "type": "array",
            "maxItems": 16,
            "uniqueItems": True,
            "items": {"type": "string", "pattern": _IDENTIFIER},
        },
        "blockedBy": {
            "type": "array",
            "maxItems": 16,
            "uniqueItems": True,
            "items": {"type": "string", "pattern": _IDENTIFIER},
        },
        "provider": _PROVIDER_SCHEMA,
        "detail": {"type": "object", "maxProperties": 32},
        "detailDigest": {"type": "string", "pattern": _DIGEST},
        "detailOmitted": {"type": "boolean"},
        "limitations": {
            "type": "array",
            "maxItems": 16,
            "uniqueItems": True,
            "items": {"type": "string", "minLength": 1, "maxLength": 128},
        },
    },
    (
        "id",
        "kind",
        "status",
        "assuranceLevel",
        "scope",
        "claimDigest",
        "assumptions",
        "dependsOn",
        "blockedBy",
        "provider",
        "detail",
        "detailDigest",
        "detailOmitted",
        "limitations",
    ),
)
_SUMMARY_SCHEMA = _closed_object(
    {
        status: {"type": "integer", "minimum": 0, "maximum": 32}
        for status in STATUS_VALUES
    }
    | {"total": {"type": "integer", "minimum": 1, "maximum": 32}},
    (*STATUS_VALUES, "total"),
)
_OBLIGATION_RECEIPT_SCHEMA = _closed_object(
    {
        "schemaVersion": {"const": OBLIGATION_RECEIPT_SCHEMA_VERSION},
        "requestSchemaVersion": {"const": OBLIGATION_SET_SCHEMA_VERSION},
        "requestDigest": {"type": "string", "pattern": _DIGEST},
        "runtime": _closed_object(
            {
                "name": {"const": "math-anchor"},
                "version": {"type": "string", "minLength": 1, "maxLength": 64},
            },
            ("name", "version"),
        ),
        "assurancePolicy": {"const": "strongest_available"},
        "summary": _SUMMARY_SCHEMA,
        "obligations": {
            "type": "array",
            "minItems": 1,
            "maxItems": 32,
            "items": _RECEIPT_ENTRY_SCHEMA,
        },
        "outcomeDigest": {"type": "string", "pattern": _DIGEST},
        "receiptDigest": {"type": "string", "pattern": _DIGEST},
    },
    (
        "schemaVersion",
        "requestSchemaVersion",
        "requestDigest",
        "runtime",
        "assurancePolicy",
        "summary",
        "obligations",
        "outcomeDigest",
        "receiptDigest",
    ),
)
_OBLIGATION_FEEDBACK_SCHEMA = _closed_object(
    {
        "schemaVersion": {"const": OBLIGATION_FEEDBACK_SCHEMA_VERSION},
        "status": {"enum": ["checked", "attention_required"]},
        "responseMode": {"enum": ["failures_only", "full"]},
        "requestDigest": {"type": "string", "pattern": _DIGEST},
        "receiptDigest": {"type": "string", "pattern": _DIGEST},
        "outcomeDigest": {"type": "string", "pattern": _DIGEST},
        "summary": _SUMMARY_SCHEMA,
        "obligations": {
            "type": "array",
            "maxItems": 32,
            "items": _RECEIPT_ENTRY_SCHEMA,
        },
    },
    (
        "schemaVersion",
        "status",
        "responseMode",
        "requestDigest",
        "receiptDigest",
        "outcomeDigest",
        "summary",
        "obligations",
    ),
)

_REQUEST_VALIDATOR = Draft202012Validator(_OBLIGATION_REQUEST_SCHEMA)
_RECEIPT_VALIDATOR = Draft202012Validator(_OBLIGATION_RECEIPT_SCHEMA)
_FEEDBACK_VALIDATOR = Draft202012Validator(_OBLIGATION_FEEDBACK_SCHEMA)


def obligation_request_schema() -> dict[str, Any]:
    return deepcopy(_OBLIGATION_REQUEST_SCHEMA)


def obligation_receipt_schema() -> dict[str, Any]:
    return deepcopy(_OBLIGATION_RECEIPT_SCHEMA)


def obligation_feedback_schema() -> dict[str, Any]:
    return deepcopy(_OBLIGATION_FEEDBACK_SCHEMA)


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _digest(value: Any) -> str:
    return f"sha256:{sha256(_canonical_json(value)).hexdigest()}"


def _validate_document(
    validator: Draft202012Validator,
    value: Any,
    label: str,
) -> None:
    errors = sorted(
        validator.iter_errors(value),
        key=lambda item: (tuple(str(part) for part in item.absolute_path), item.message),
    )
    if not errors:
        return
    error = errors[0]
    path = ".".join(str(part) for part in error.absolute_path) or "$"
    raise CalculatorError("E_INPUT", f"{label} {path}: {error.message}")


def _bounded_request(value: Any) -> None:
    try:
        encode_json_line(
            value,
            max_bytes=MAX_OBLIGATION_REQUEST_BYTES,
            max_nodes=MAX_OBLIGATION_REQUEST_NODES,
            max_depth=MAX_OBLIGATION_REQUEST_DEPTH,
        )
    except TransportBudgetError as error:
        raise CalculatorError("E_LIMIT", str(error), {"rule": error.rule}) from error
    except (TypeError, ValueError, OverflowError, RecursionError) as error:
        raise CalculatorError("E_INPUT", f"obligation request must be bounded JSON: {error}") from error


def _bounded_receipt(value: Any) -> None:
    try:
        encode_json_line(
            value,
            max_bytes=MAX_RECEIPT_BYTES,
            max_nodes=MAX_OBLIGATION_REQUEST_NODES,
            max_depth=MAX_OBLIGATION_REQUEST_DEPTH,
        )
    except TransportBudgetError as error:
        raise CalculatorError("E_LIMIT", str(error), {"rule": error.rule}) from error
    except (TypeError, ValueError, OverflowError, RecursionError) as error:
        raise CalculatorError("E_INPUT", f"obligation receipt must be bounded JSON: {error}") from error


def _validate_request(request: Any) -> dict[str, Any]:
    _bounded_request(request)
    _validate_document(_REQUEST_VALIDATOR, request, "obligation request")
    assert isinstance(request, dict)
    assumption_sets = request.get("assumptionSets", [])
    assumption_ids = [entry["id"] for entry in assumption_sets]
    if len(assumption_ids) != len(set(assumption_ids)):
        raise CalculatorError("E_INPUT", "assumption-set ids must be unique")
    obligations = request["obligations"]
    obligation_ids = [entry["id"] for entry in obligations]
    if len(obligation_ids) != len(set(obligation_ids)):
        raise CalculatorError("E_INPUT", "obligation ids must be unique")
    known_obligation_ids = set(obligation_ids)
    known_assumption_ids = set(assumption_ids)
    for obligation in obligations:
        assumption_set = obligation.get("assumptionSet")
        if assumption_set is not None and assumption_set not in known_assumption_ids:
            raise CalculatorError(
                "E_INPUT",
                f"obligation {obligation['id']} references an unknown assumption set",
            )
        dependencies = obligation.get("dependsOn", [])
        if obligation["id"] in dependencies:
            raise CalculatorError(
                "E_INPUT",
                f"obligation {obligation['id']} cannot depend on itself",
            )
        unknown = [item for item in dependencies if item not in known_obligation_ids]
        if unknown:
            raise CalculatorError(
                "E_INPUT",
                f"obligation {obligation['id']} references an unknown dependency",
            )
        operation = _KNOWN_PROVIDERS.get(obligation["kind"])
        if operation is not None:
            spec = OPERATIONS.get(operation)
            if spec is None:
                raise CalculatorError(
                    "E_OPERATION",
                    f"registered obligation provider is unavailable: {operation}",
                )
            validate_operation_arguments(operation, spec.input_schema, obligation["claim"])
    _dependency_layers(obligations)
    return request


def _dependency_layers(obligations: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    by_id = {entry["id"]: entry for entry in obligations}
    pending = set(by_id)
    completed: set[str] = set()
    layers: list[list[dict[str, Any]]] = []
    while pending:
        layer = [
            entry
            for entry in obligations
            if entry["id"] in pending
            and set(entry.get("dependsOn", [])) <= completed
        ]
        if not layer:
            raise CalculatorError("E_INPUT", "obligation dependency graph contains a cycle")
        layers.append(layer)
        ids = {entry["id"] for entry in layer}
        pending -= ids
        completed |= ids
    return layers


def _assumption_reference(
    obligation: dict[str, Any],
    assumption_sets: dict[str, list[str]],
) -> dict[str, Any]:
    set_id = obligation.get("assumptionSet")
    assumptions = [] if set_id is None else assumption_sets[set_id]
    return {
        "setId": set_id,
        "digest": _digest(assumptions),
        "count": len(assumptions),
        "interpretation": "bound_not_evaluated",
    }


def _entry(
    obligation: dict[str, Any],
    assumption_sets: dict[str, list[str]],
    *,
    status: str,
    assurance_level: str | None,
    scope: str,
    provider: dict[str, Any] | None,
    detail: dict[str, Any],
    blocked_by: list[str] | None = None,
    limitations: list[str] | None = None,
) -> dict[str, Any]:
    detail_digest = _digest(detail)
    return {
        "id": obligation["id"],
        "kind": obligation["kind"],
        "status": status,
        "assuranceLevel": assurance_level,
        "scope": scope,
        "claimDigest": _digest(obligation["claim"]),
        "assumptions": _assumption_reference(obligation, assumption_sets),
        "dependsOn": list(obligation.get("dependsOn", [])),
        "blockedBy": blocked_by or [],
        "provider": provider,
        "detail": detail,
        "detailDigest": detail_digest,
        "detailOmitted": False,
        "limitations": list(dict.fromkeys(limitations or [])),
    }


def _provider(raw_result: dict[str, Any], operation: str) -> dict[str, Any]:
    provenance = raw_result.get("provenance")
    runtime = provenance.get("runtime") if isinstance(provenance, dict) else None
    backends = provenance.get("backends") if isinstance(provenance, dict) else []
    if not isinstance(runtime, dict):
        runtime = None
    if not isinstance(backends, list):
        backends = []
    return {
        "operation": operation,
        "resultDigest": _digest(raw_result),
        "runtime": runtime,
        "backends": backends,
    }


def _assurance_level(raw_result: dict[str, Any]) -> str | None:
    level = raw_result.get("assurance")
    return {
        "kernel_checked": "formal_kernel_checked",
        "certified": "exact_symbolic",
        "deterministic": "exact_symbolic",
        "diagnostic": "numerical",
        "heuristic": "heuristic",
    }.get(level)


def _error_entry(
    obligation: dict[str, Any],
    assumption_sets: dict[str, list[str]],
    operation: str,
    raw_result: dict[str, Any],
) -> dict[str, Any]:
    error = raw_result.get("error")
    error = error if isinstance(error, dict) else {"code": "E_RUNTIME"}
    code = str(error.get("code", "E_RUNTIME"))
    status = "unsupported" if code in _UNSUPPORTED_PROVIDER_ERRORS else "unknown"
    scope = OPERATIONS[operation].assurance_scope
    detail = {
        "reason": "provider_rejected_claim" if status == "unsupported" else "provider_inconclusive",
        "error": {
            key: error[key]
            for key in ("code", "message", "retryable", "phase", "suggestedAction", "retryAfterMs")
            if key in error
        },
    }
    return _entry(
        obligation,
        assumption_sets,
        status=status,
        assurance_level=None,
        scope=scope,
        provider=_provider(raw_result, operation),
        detail=detail,
        limitations=["provider_did_not_establish_the_claim"],
    )


def _polynomial_entry(
    obligation: dict[str, Any],
    assumption_sets: dict[str, list[str]],
    raw_result: dict[str, Any],
) -> dict[str, Any]:
    certificate = raw_result.get("certificate")
    try:
        check = verify_polynomial_identity_certificate(certificate)
    except CertificateValidationError as error:
        detail = {"reason": "certificate_rejected", "message": str(error)}
        return _entry(
            obligation,
            assumption_sets,
            status="unknown",
            assurance_level=None,
            scope="polynomial_identity_over_rationals",
            provider=_provider(raw_result, "certificate.polynomial_identity"),
            detail=detail,
            limitations=["independent_checker_rejected_provider_output"],
        )
    terms = certificate["normalizedDifference"]
    detail = {
        "identity": check["identity"],
        "statementDigest": certificate["statementDigest"],
        "certificateDigest": check["certificateDigest"],
        "differenceTermCount": len(terms),
        "firstDifferenceTerm": terms[0] if terms else None,
        "checker": check["checker"],
    }
    return _entry(
        obligation,
        assumption_sets,
        status="checked" if check["identity"] else "falsified",
        assurance_level="exact_symbolic",
        scope="polynomial_identity_over_rationals",
        provider=_provider(raw_result, "certificate.polynomial_identity"),
        detail=detail,
        limitations=["natural_language_to_claim_translation_unchecked"],
    )


def _equivalence_entry(
    obligation: dict[str, Any],
    assumption_sets: dict[str, list[str]],
    raw_result: dict[str, Any],
) -> dict[str, Any]:
    equivalence = raw_result.get("equivalence")
    proven = raw_result.get("proven") is True
    if proven and equivalence == "equivalent":
        status = "checked"
    elif proven and equivalence == "not_equivalent":
        status = "falsified"
    else:
        status = "unknown"
    detail = {
        "equivalence": equivalence,
        "proven": proven,
        "definedness": raw_result.get("definedness"),
        "difference": raw_result.get("difference"),
        "counterexample": raw_result.get("counterexample"),
    }
    limitations = ["natural_language_to_claim_translation_unchecked"]
    if status == "unknown":
        limitations.append("symbolic_and_bounded_probe_result_inconclusive")
    return _entry(
        obligation,
        assumption_sets,
        status=status,
        assurance_level=_assurance_level(raw_result),
        scope=str(raw_result.get("scope", "declared_domain_and_definedness_policy")),
        provider=_provider(raw_result, "expression.equivalent"),
        detail=detail,
        limitations=limitations,
    )


def _dimension_entry(
    obligation: dict[str, Any],
    assumption_sets: dict[str, list[str]],
    raw_result: dict[str, Any],
) -> dict[str, Any]:
    consistent = raw_result.get("dimensionallyConsistent") is True
    detail = {
        "dimensionallyConsistent": consistent,
        "leftDimension": raw_result.get("leftDimension"),
        "rightDimension": raw_result.get("rightDimension"),
        "issues": raw_result.get("issues", []),
    }
    return _entry(
        obligation,
        assumption_sets,
        status="checked" if consistent else "falsified",
        assurance_level="exact_symbolic",
        scope="dimensional_consistency_only",
        provider=_provider(raw_result, "dimension.check"),
        detail=detail,
        limitations=[
            "formula_correctness_and_coefficients_unchecked",
            "natural_language_to_claim_translation_unchecked",
        ],
    )


def _geometry_entry(
    obligation: dict[str, Any],
    assumption_sets: dict[str, list[str]],
    raw_result: dict[str, Any],
) -> dict[str, Any]:
    square = raw_result.get("square")
    nijenhuis = raw_result.get("nijenhuis")
    satisfied = (
        isinstance(square, dict)
        and square.get("satisfied") is True
        and isinstance(nijenhuis, dict)
        and nijenhuis.get("vanished") is True
    )
    detail = {
        "localConclusion": raw_result.get("localConclusion"),
        "square": square,
        "nijenhuis": nijenhuis,
        "uncheckedGlobalObligations": raw_result.get("uncheckedGlobalObligations", []),
    }
    return _entry(
        obligation,
        assumption_sets,
        status="checked" if satisfied else "falsified",
        assurance_level="exact_symbolic",
        scope="local_coordinate_rational_polynomial_almost_complex_check",
        provider=_provider(raw_result, "geometry.almost_complex.local_check"),
        detail=detail,
        limitations=[
            "chart_and_global_manifold_obligations_unchecked",
            "natural_language_to_claim_translation_unchecked",
        ],
    )


def _map_provider_result(
    obligation: dict[str, Any],
    assumption_sets: dict[str, list[str]],
    raw_result: dict[str, Any],
) -> dict[str, Any]:
    operation = _KNOWN_PROVIDERS[obligation["kind"]]
    if raw_result.get("status") != "ok":
        return _error_entry(obligation, assumption_sets, operation, raw_result)
    if obligation["kind"] == "polynomial_identity":
        return _polynomial_entry(obligation, assumption_sets, raw_result)
    if obligation["kind"] == "expression_equivalence":
        return _equivalence_entry(obligation, assumption_sets, raw_result)
    if obligation["kind"] == "dimension_consistency":
        return _dimension_entry(obligation, assumption_sets, raw_result)
    return _geometry_entry(obligation, assumption_sets, raw_result)


def _unsupported_entry(
    obligation: dict[str, Any],
    assumption_sets: dict[str, list[str]],
) -> dict[str, Any]:
    return _entry(
        obligation,
        assumption_sets,
        status="unsupported",
        assurance_level=None,
        scope="unregistered_obligation_kind",
        provider=None,
        detail={
            "reason": "no_registered_obligation_provider",
            "supportedKinds": sorted(_KNOWN_PROVIDERS),
        },
        limitations=["claim_not_interpreted_or_executed"],
    )


def _blocked_entry(
    obligation: dict[str, Any],
    assumption_sets: dict[str, list[str]],
    blocked_by: list[str],
) -> dict[str, Any]:
    return _entry(
        obligation,
        assumption_sets,
        status="unknown",
        assurance_level=None,
        scope="dependency_gated_obligation",
        provider=None,
        detail={"reason": "dependency_not_checked", "blockedBy": blocked_by},
        blocked_by=blocked_by,
        limitations=["provider_not_executed"],
    )


def _deadline_entry(
    obligation: dict[str, Any],
    assumption_sets: dict[str, list[str]],
) -> dict[str, Any]:
    operation = _KNOWN_PROVIDERS[obligation["kind"]]
    raw_result = {
        "status": "error",
        "error": {
            "code": "E_TIMEOUT",
            "message": "obligation set exhausted its cumulative deadline",
            "retryable": True,
            "phase": "obligation_set",
            "suggestedAction": "Retry with a smaller set or a larger timeoutMs budget.",
        },
    }
    return _error_entry(obligation, assumption_sets, operation, raw_result)


def _summary(entries: list[dict[str, Any]]) -> dict[str, int]:
    counts = {status: 0 for status in STATUS_VALUES}
    for entry in entries:
        counts[entry["status"]] += 1
    return {**counts, "total": len(entries)}


def _outcome_payload(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "id": entry["id"],
            "kind": entry["kind"],
            "status": entry["status"],
            "assuranceLevel": entry["assuranceLevel"],
            "scope": entry["scope"],
            "claimDigest": entry["claimDigest"],
            "assumptionsDigest": entry["assumptions"]["digest"],
            "blockedBy": entry["blockedBy"],
            "detailDigest": entry["detailDigest"],
        }
        for entry in entries
    ]


def _validate_receipt_integrity(receipt: dict[str, Any]) -> None:
    digest_payload = dict(receipt)
    supplied_receipt_digest = digest_payload.pop("receiptDigest")
    if supplied_receipt_digest != _digest(digest_payload):
        raise CalculatorError("E_RECEIPT", "previous receipt digest does not match its content")
    entries = receipt["obligations"]
    if receipt["summary"] != _summary(entries):
        raise CalculatorError("E_RECEIPT", "previous receipt summary does not match its obligations")
    if receipt["outcomeDigest"] != _digest(_outcome_payload(entries)):
        raise CalculatorError("E_RECEIPT", "previous outcome digest does not match its obligations")
    for entry in entries:
        if entry["detailOmitted"]:
            raise CalculatorError("E_RECEIPT", "previous full receipt omits obligation detail")
        if entry["detailDigest"] != _digest(entry["detail"]):
            raise CalculatorError(
                "E_RECEIPT",
                f"previous receipt detail digest does not match obligation {entry['id']}",
            )


def _feedback_entry(entry: dict[str, Any]) -> dict[str, Any]:
    return deepcopy(entry)


def _fit_feedback(feedback: dict[str, Any], maximum: int) -> dict[str, Any]:
    if len(_canonical_json(feedback)) <= maximum:
        return feedback
    compact = deepcopy(feedback)
    for entry in compact["obligations"]:
        entry["detail"] = {"digest": entry["detailDigest"]}
        entry["detailOmitted"] = True
    if len(_canonical_json(compact)) <= maximum:
        return compact
    raise CalculatorError(
        "E_OUTPUT_LIMIT",
        "obligation feedback exceeds feedbackBytes even after detail omission",
        {"feedbackBytes": maximum, "obligationCount": len(compact["obligations"])},
    )


def check_obligation_set(request: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Check one bounded obligation DAG and return compact feedback plus a full receipt.

    Caller-authored assumptions are hash-bound but deliberately not interpreted.
    Dependencies gate execution; they do not substitute one provider result into
    another claim. The request therefore remains deterministic and replayable.
    """

    request = _validate_request(request)
    assumption_sets = {
        entry["id"]: list(entry["assumptions"])
        for entry in request.get("assumptionSets", [])
    }
    limits = request.get("limits", {})
    timeout_ms = limits.get("timeoutMs", DEFAULT_TIMEOUT_MS)
    memory_mb = limits.get("memoryMb", DEFAULT_MEMORY_MB)
    provider_output_bytes = limits.get(
        "providerOutputBytes", DEFAULT_PROVIDER_OUTPUT_BYTES
    )
    feedback_bytes = limits.get("feedbackBytes", DEFAULT_FEEDBACK_BYTES)
    deadline = time.monotonic() + timeout_ms / 1000
    entries_by_id: dict[str, dict[str, Any]] = {}

    for layer in _dependency_layers(request["obligations"]):
        runnable: list[dict[str, Any]] = []
        for obligation in layer:
            blocked_by = [
                dependency
                for dependency in obligation.get("dependsOn", [])
                if entries_by_id[dependency]["status"] != "checked"
            ]
            if blocked_by:
                entries_by_id[obligation["id"]] = _blocked_entry(
                    obligation, assumption_sets, blocked_by
                )
            elif obligation["kind"] not in _KNOWN_PROVIDERS:
                entries_by_id[obligation["id"]] = _unsupported_entry(
                    obligation, assumption_sets
                )
            else:
                runnable.append(obligation)

        if not runnable:
            continue
        remaining_ms = int((deadline - time.monotonic()) * 1000)
        if remaining_ms < 100:
            for obligation in runnable:
                entries_by_id[obligation["id"]] = _deadline_entry(
                    obligation, assumption_sets
                )
            continue
        items = [
            {
                "operation": _KNOWN_PROVIDERS[obligation["kind"]],
                "arguments": obligation["claim"],
                "timeoutMs": remaining_ms,
                "memoryMb": memory_mb,
                "resultMode": "auto",
                "maxOutputBytes": provider_output_bytes,
            }
            for obligation in runnable
        ]
        if len(items) == 1:
            raw_results = [
                run_operation(
                    items[0]["operation"],
                    items[0]["arguments"],
                    timeout_ms=items[0]["timeoutMs"],
                    memory_mb=items[0]["memoryMb"],
                    result_mode=items[0]["resultMode"],
                    max_output_bytes=items[0]["maxOutputBytes"],
                    _request_class="batch",
                )
            ]
        else:
            batch_result = run_batch(
                items,
                timeout_ms=remaining_ms,
                max_output_bytes=MAX_OUTPUT_BYTES,
            )
            raw_results = batch_result.get("results")
            if not isinstance(raw_results, list) or len(raw_results) != len(runnable):
                raw_results = [batch_result for _ in runnable]
        for obligation, raw_result in zip(runnable, raw_results, strict=True):
            if not isinstance(raw_result, dict):
                raw_result = {
                    "status": "error",
                    "error": {
                        "code": "E_RUNTIME",
                        "message": "obligation provider returned an invalid envelope",
                    },
                }
            raw_result = {key: value for key, value in raw_result.items() if key != "index"}
            entries_by_id[obligation["id"]] = _map_provider_result(
                obligation, assumption_sets, raw_result
            )

    entries = [entries_by_id[item["id"]] for item in request["obligations"]]
    summary = _summary(entries)
    receipt: dict[str, Any] = {
        "schemaVersion": OBLIGATION_RECEIPT_SCHEMA_VERSION,
        "requestSchemaVersion": OBLIGATION_SET_SCHEMA_VERSION,
        "requestDigest": _digest(request),
        "runtime": {"name": "math-anchor", "version": __version__},
        "assurancePolicy": request.get("assurancePolicy", "strongest_available"),
        "summary": summary,
        "obligations": entries,
        "outcomeDigest": _digest(_outcome_payload(entries)),
    }
    receipt["receiptDigest"] = _digest(receipt)
    if len(_canonical_json(receipt)) > MAX_RECEIPT_BYTES:
        raise CalculatorError(
            "E_OUTPUT_LIMIT",
            f"obligation receipt exceeds the {MAX_RECEIPT_BYTES}-byte artifact limit",
        )
    _validate_document(_RECEIPT_VALIDATOR, receipt, "obligation receipt")

    response_mode = request.get("responseMode", "failures_only")
    selected = entries if response_mode == "full" else [
        entry for entry in entries if entry["status"] != "checked"
    ]
    feedback = {
        "schemaVersion": OBLIGATION_FEEDBACK_SCHEMA_VERSION,
        "status": "checked" if summary["checked"] == summary["total"] else "attention_required",
        "responseMode": response_mode,
        "requestDigest": receipt["requestDigest"],
        "receiptDigest": receipt["receiptDigest"],
        "outcomeDigest": receipt["outcomeDigest"],
        "summary": summary,
        "obligations": [_feedback_entry(entry) for entry in selected],
    }
    feedback = _fit_feedback(feedback, feedback_bytes)
    _validate_document(_FEEDBACK_VALIDATOR, feedback, "obligation feedback")
    return feedback, receipt


def replay_obligation_set(
    request: dict[str, Any],
    previous_receipt: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Re-run a request and classify exact, runtime-only, or outcome drift."""

    _bounded_receipt(previous_receipt)
    _validate_document(_RECEIPT_VALIDATOR, previous_receipt, "previous receipt")
    _validate_receipt_integrity(previous_receipt)
    request = _validate_request(request)
    if previous_receipt["requestDigest"] != _digest(request):
        raise CalculatorError(
            "E_INPUT",
            "previous receipt is bound to a different obligation request",
        )
    feedback, current_receipt = check_obligation_set(request)
    outcome_match = (
        previous_receipt["outcomeDigest"] == current_receipt["outcomeDigest"]
    )
    receipt_match = (
        previous_receipt["receiptDigest"] == current_receipt["receiptDigest"]
    )
    if receipt_match:
        status = "matched"
    elif outcome_match:
        status = "runtime_drift"
    else:
        status = "outcome_drift"
    replay = {
        "schemaVersion": OBLIGATION_REPLAY_SCHEMA_VERSION,
        "status": status,
        "requestDigest": current_receipt["requestDigest"],
        "previousReceiptDigest": previous_receipt["receiptDigest"],
        "currentReceiptDigest": current_receipt["receiptDigest"],
        "previousOutcomeDigest": previous_receipt["outcomeDigest"],
        "currentOutcomeDigest": current_receipt["outcomeDigest"],
        "outcomeMatch": outcome_match,
        "runtimeMatch": previous_receipt["runtime"] == current_receipt["runtime"],
    }
    return replay, feedback, current_receipt
