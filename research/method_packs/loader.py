"""Load and validate experimental method-pack JSON. No eval, no code import from the pack."""

from __future__ import annotations

from typing import Any

from math_anchor.certificate_checker import (
    CERTIFICATE_FORMAT,
    CHECKER_SYSTEM,
    CHECKER_VERSION,
)
from math_anchor.errors import CalculatorError

from .format import (
    ALLOWED_NOVELTY,
    DEFAULT_PACK_PATH,
    EXECUTABLE_LIFECYCLES,
    FORBIDDEN_PACK_KEYS,
    KNOWN_PACK_IDS,
    LIFECYCLE_CANDIDATE,
    PACK_ID,
    PARAM_PACK_ID,
    PARAM_REQUIRED_INSTANTIATION_RULE_IDS,
    REQUIRED_INSTANTIATION_RULE_IDS,
    SCHEMA_VERSION,
)


class PackFormatError(CalculatorError):
    """Pack JSON is not a well-formed experimental method pack."""


def load_pack(path: object | None = None) -> dict[str, Any]:
    from pathlib import Path
    import json

    pack_path = Path(path) if path is not None else DEFAULT_PACK_PATH
    try:
        raw = pack_path.read_text(encoding="utf-8")
    except OSError as error:
        raise PackFormatError("E_INPUT", f"cannot read method pack: {error}") from error
    try:
        document = json.loads(raw)
    except json.JSONDecodeError as error:
        raise PackFormatError("E_INPUT", f"method pack is not JSON: {error}") from error
    if not isinstance(document, dict):
        raise PackFormatError("E_INPUT", "method pack must be a JSON object")
    validate_pack(document)
    document["_packPath"] = str(pack_path)
    return document


def validate_pack(document: dict[str, Any]) -> None:
    _forbid_executable_keys(document)
    for key in (
        "schemaVersion",
        "id",
        "version",
        "status",
        "publicPromotion",
        "notAPublicCapability",
        "notAPublicProcedure",
        "provenance",
        "mathSemantics",
        "useInterface",
        "verification",
        "infrastructureUsedNotExtracted",
        "novelty",
        "humanNotePath",
        "costAdoption",
    ):
        if key not in document:
            raise PackFormatError("E_INPUT", f"method pack missing {key}")

    if document["schemaVersion"] != SCHEMA_VERSION:
        raise PackFormatError("E_INPUT", "unsupported experimental method-pack schema")
    if document["id"] not in KNOWN_PACK_IDS:
        raise PackFormatError("E_INPUT", "unexpected method-pack id")
    if document["publicPromotion"] is not False:
        raise PackFormatError("E_INPUT", "experimental pack must not be marked public")
    if document["notAPublicCapability"] is not True or document["notAPublicProcedure"] is not True:
        raise PackFormatError("E_INPUT", "experimental pack must decline Capability/Procedure promotion")
    if document["status"] not in {LIFECYCLE_CANDIDATE, *EXECUTABLE_LIFECYCLES}:
        raise PackFormatError("E_INPUT", f"unknown pack lifecycle status: {document['status']}")

    novelty = document["novelty"]
    if not isinstance(novelty, dict) or novelty.get("status") not in ALLOWED_NOVELTY:
        raise PackFormatError("E_INPUT", "novelty.status must be an honest allowed label")
    if novelty.get("autoClaimed") is True:
        raise PackFormatError("E_INPUT", "novelty must never be auto-claimed")

    verification = document["verification"]
    if not isinstance(verification, dict):
        raise PackFormatError("E_INPUT", "verification must be an object")
    if verification.get("formalKernelChecked") is not False:
        raise PackFormatError("E_INPUT", "pack must not mark formal_kernel_checked")
    if verification.get("obligationKind") != "polynomial_identity":
        raise PackFormatError("E_INPUT", "pack obligationKind must be polynomial_identity")
    if verification.get("checkerId") != CHECKER_SYSTEM:
        raise PackFormatError(
            "E_INPUT",
            "pack checkerId is not the runtime stdlib polynomial checker",
        )
    if verification.get("checkerVersion") != CHECKER_VERSION:
        raise PackFormatError(
            "E_INPUT",
            "pack checkerVersion is not the runtime checker version",
        )
    if verification.get("certificateFormat") != CERTIFICATE_FORMAT:
        raise PackFormatError(
            "E_INPUT",
            "pack certificateFormat is not the runtime certificate format",
        )

    infrastructure = document["infrastructureUsedNotExtracted"]
    if not isinstance(infrastructure, dict) or infrastructure.get("agentExtracted") is not False:
        raise PackFormatError(
            "E_INPUT",
            "telescoping combination rule must remain hand-provided infrastructure",
        )

    provenance = document["provenance"]
    if not isinstance(provenance, dict):
        raise PackFormatError("E_INPUT", "provenance must be an object")
    if provenance.get("hiddenModelReasoningRequired") is not False:
        raise PackFormatError("E_INPUT", "packs must not require hidden model reasoning")
    if not provenance.get("extractionTaskId"):
        raise PackFormatError("E_INPUT", "provenance.extractionTaskId is required")

    semantics = document["mathSemantics"]
    if not isinstance(semantics, dict):
        raise PackFormatError("E_INPUT", "mathSemantics must be an object")
    for key in (
        "problemFamily",
        "statement",
        "variables",
        "necessaryConditions",
        "unsupportedInputs",
    ):
        if key not in semantics:
            raise PackFormatError("E_INPUT", f"mathSemantics missing {key}")

    use = document["useInterface"]
    if not isinstance(use, dict):
        raise PackFormatError("E_INPUT", "useInterface must be an object")
    rules = use.get("instantiationRules")
    if not isinstance(rules, list) or not rules:
        raise PackFormatError("E_INPUT", "useInterface.instantiationRules must be a non-empty list")
    ids = _rule_ids(rules)
    expected_rules = (
        PARAM_REQUIRED_INSTANTIATION_RULE_IDS
        if document["id"] == PARAM_PACK_ID
        else REQUIRED_INSTANTIATION_RULE_IDS
    )
    if tuple(ids) != expected_rules:
        raise PackFormatError(
            "E_INPUT",
            "instantiation rules must be the frozen restricted allow-list; "
            "arbitrary code is not a method-pack rule",
        )
    forbidden = use.get("forbiddenEvaluators")
    if not isinstance(forbidden, list) or "eval" not in forbidden:
        raise PackFormatError("E_INPUT", "useInterface must forbid eval and related evaluators")

    if document["id"] == PARAM_PACK_ID:
        _validate_parametric_payload(document)
    elif "construct_antidifference_sympy_gosper" not in ids:
        raise PackFormatError(
            "E_INPUT",
            "Gosper polynomial pack must keep the construction rule in its allow-list",
        )


def require_executable(pack: dict[str, Any]) -> None:
    status = pack.get("status")
    if status not in EXECUTABLE_LIFECYCLES:
        raise PackFormatError(
            "E_INPUT",
            f"pack status {status!r} is not executable; only "
            "verified-in-declared-scope packs may be applied",
        )


def _rule_ids(rules: list[object]) -> list[str]:
    ids: list[str] = []
    for rule in rules:
        if not isinstance(rule, dict) or not isinstance(rule.get("id"), str):
            raise PackFormatError("E_INPUT", "each instantiation rule must be an object with string id")
        ids.append(rule["id"])
    return ids


def _validate_parametric_payload(document: dict[str, Any]) -> None:
    from .shifted_square import parse_bivariate

    semantics = document["mathSemantics"]
    payload = semantics.get("parametricAntidifference")
    if not isinstance(payload, dict):
        raise PackFormatError(
            "E_INPUT",
            "shifted-square pack must carry mathSemantics.parametricAntidifference",
        )
    source = payload.get("source")
    if not isinstance(source, str) or not source.strip():
        raise PackFormatError(
            "E_INPUT",
            "shifted-square pack must carry a non-empty parametric G(k,c) source",
        )
    if payload.get("notFromGosper") is not True:
        raise PackFormatError(
            "E_INPUT",
            "shifted-square pack must declare the saved G is not reconstructed by Gosper",
        )
    if payload.get("indexVariable") != "k" or payload.get("parameterVariable") != "c":
        raise PackFormatError(
            "E_INPUT",
            "shifted-square pack must store G in variables k and c",
        )
    reconstruction = document["useInterface"].get("reconstructionOnReusePath")
    if reconstruction is not False:
        raise PackFormatError(
            "E_INPUT",
            "shifted-square pack must disable reconstruction on the reuse path",
        )
    try:
        terms = parse_bivariate(source)
    except CalculatorError as error:
        raise PackFormatError("E_INPUT", f"parametric G(k,c) is not a QQ-polynomial: {error}") from error
    if not terms:
        raise PackFormatError("E_INPUT", "parametric G(k,c) must not be the zero polynomial")


def _forbid_executable_keys(value: object) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).lower() in FORBIDDEN_PACK_KEYS:
                raise PackFormatError(
                    "E_INPUT",
                    f"method pack must not contain executable key {key!r}",
                )
            _forbid_executable_keys(child)
    elif isinstance(value, list):
        for child in value:
            _forbid_executable_keys(child)
