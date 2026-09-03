from __future__ import annotations

from copy import deepcopy
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from .errors import CalculatorError
from .output_policy import (
    DEFAULT_BATCH_MAX_OUTPUT_BYTES,
    DEFAULT_MAX_OUTPUT_BYTES,
    MAX_OUTPUT_BYTES,
    MIN_OUTPUT_BYTES,
)
from .result_contracts import RUN_RESULT_SCHEMA
from .result_contracts.shared import (
    ERROR_RESULT_SCHEMA,
    _LIMIT_PROPERTIES,
    _LIMIT_VALIDATORS,
    _MAX_VALIDATION_MESSAGE_BYTES,
    _TEXT_MATRIX,
    _TEXT_MATRIX_DEFINITION,
    _TEXT_OR_NULL,
    _TEXT_OR_NULL_DEFINITION,
)


def _validator_for_variant(schema: dict[str, Any]) -> Draft202012Validator:
    return Draft202012Validator(
        {**schema, "$defs": RUN_RESULT_SCHEMA["$defs"]}
    )


_RUN_RESULT_VALIDATOR = Draft202012Validator(RUN_RESULT_SCHEMA)
_ERROR_RESULT_VALIDATOR = _validator_for_variant(ERROR_RESULT_SCHEMA)
_RESULT_VALIDATORS_BY_KIND: dict[
    str,
    tuple[tuple[dict[str, Any], Draft202012Validator], ...],
] = {}
for _variant in RUN_RESULT_SCHEMA["oneOf"]:
    _kind = _variant.get("properties", {}).get("kind", {}).get("const")
    if isinstance(_kind, str):
        _RESULT_VALIDATORS_BY_KIND[_kind] = (
            *_RESULT_VALIDATORS_BY_KIND.get(_kind, ()),
            (_variant, _validator_for_variant(_variant)),
        )


# Keep the complete per-kind schema above as the runtime validation authority.
# Advertising that entire union on every tool listing made Agents pay for more
# than 20 KB of result detail before making an ordinary call. The live tool
# therefore publishes the stable common envelope and dominant scalar/matrix fields;
# operation-specific output remains structured and is still validated against
# RUN_RESULT_SCHEMA before it crosses the execution boundary.
RUN_TOOL_OUTPUT_SCHEMA = {
    "type": "object",
    "additionalProperties": True,
    "properties": {
        "status": {"enum": ["ok", "uncertain", "error"]},
        "operation": {"type": "string"},
        "kind": {"type": "string"},
        "exact": {"oneOf": [_TEXT_OR_NULL, _TEXT_MATRIX]},
        "approx": {"oneOf": [_TEXT_OR_NULL, _TEXT_MATRIX]},
        "precision": {"type": "integer", "minimum": 2},
        "unit": _TEXT_OR_NULL,
        "warnings": {"type": "array", "items": {"type": "string"}},
        "assuranceContractVersion": {"type": "string"},
        "assurance": {
            "enum": ["heuristic", "deterministic", "diagnostic", "certified", "kernel_checked"]
        },
        "claim": {"type": "string"},
        "scope": {"type": "string"},
        "assumptions": {"type": "array"},
        # The complete per-kind contract below remains strict. Keep this
        # always-listed projection shallow so ordinary callers do not pay the
        # certificate/provenance schema on every unrelated calculation.
        "provenance": {"type": "object"},
        "certificate": {"type": ["object", "null"]},
        "checkedBy": {"type": ["object", "null"]},
        "error": ERROR_RESULT_SCHEMA["properties"]["error"],
    },
    "required": ["status"],
    "$defs": {
        "textOrNull": deepcopy(_TEXT_OR_NULL_DEFINITION),
        "textMatrix": deepcopy(_TEXT_MATRIX_DEFINITION),
    },
}


_INDEXED_RESULT_SCHEMA = {
    "type": "object",
    "additionalProperties": True,
    "properties": {
        "index": {"type": "integer", "minimum": 0},
        "status": {"type": "string"},
    },
    "required": ["index", "status"],
}

_BATCH_OK_RESULT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "status": {"enum": ["ok", "partial"]},
        "count": {"type": "integer", "minimum": 1, "maximum": 32},
        "results": {
            "type": "array",
            "minItems": 1,
            "maxItems": 32,
            "items": _INDEXED_RESULT_SCHEMA,
        },
    },
    "required": ["status", "count", "results"],
}

BATCH_RESULT_SCHEMA = {
    "type": "object",
    "additionalProperties": True,
    "properties": {"status": {"type": "string"}},
    "required": ["status"],
}


def validate_operation_arguments(operation: str, schema: dict[str, Any], arguments: dict[str, Any]) -> None:
    schema = _select_discriminated_schema(schema, arguments)
    errors = sorted(
        Draft202012Validator(schema).iter_errors(arguments),
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    )
    if not errors:
        return
    error = errors[0]
    path = ".".join(str(part) for part in error.absolute_path) or "arguments"
    code = "E_LIMIT" if error.validator in _LIMIT_VALIDATORS else "E_INPUT"
    message = error.message
    if len(message.encode("utf-8")) > _MAX_VALIDATION_MESSAGE_BYTES:
        message = f"value does not satisfy {error.validator}"
    raise CalculatorError(
        code,
        f"invalid {operation} arguments at {path}: {message}",
        {"path": list(error.absolute_path), "rule": error.validator},
    )


def _select_discriminated_schema(schema: dict[str, Any], instance: dict[str, Any]) -> dict[str, Any]:
    variants = schema.get("oneOf")
    action = instance.get("action")
    if not isinstance(variants, list) or not isinstance(action, str):
        return schema
    matching = []
    for variant in variants:
        action_schema = variant.get("properties", {}).get("action", {})
        if action_schema.get("const") == action or action in action_schema.get("enum", []):
            matching.append(variant)
    return matching[0] if len(matching) == 1 else schema


def validate_result(result: dict[str, Any]) -> None:
    validator = _result_validator(result)
    try:
        validator.validate(result)
    except ValidationError as error:
        path = ".".join(str(part) for part in error.absolute_path) or "result"
        raise CalculatorError(
            "E_RUNTIME",
            f"operation returned a result outside the public contract at {path}",
        ) from error


def _result_validator(result: dict[str, Any]) -> Draft202012Validator:
    if result.get("status") == "error":
        return _ERROR_RESULT_VALIDATOR
    kind = result.get("kind")
    if not isinstance(kind, str):
        return _RUN_RESULT_VALIDATOR
    candidates = _RESULT_VALIDATORS_BY_KIND.get(kind, ())
    if len(candidates) == 1:
        return candidates[0][1]
    if candidates:
        action = result.get("action")
        if isinstance(action, str):
            matching = [
                validator
                for variant, validator in candidates
                if (
                    variant.get("properties", {}).get("action", {}).get("const") == action
                    or action
                    in variant.get("properties", {}).get("action", {}).get("enum", [])
                )
            ]
            if len(matching) == 1:
                return matching[0]
    # Unknown or ambiguous discriminators still traverse the complete public
    # union so the optimization cannot weaken contract rejection.
    return _RUN_RESULT_VALIDATOR


def run_tool_parameters(operation_schemas: list[tuple[str, dict[str, Any]]]) -> dict[str, Any]:
    """Return the always-listed, Codex-host-safe execution envelope.

    Current Codex hosts compact input schemas larger than roughly 5 KB. The
    complete per-operation tagged union crosses that boundary and loses its argument surface
    before the model sees it. Keep the stable operation IDs and execution
    limits fully typed here; ``math.describe`` publishes the exact closed
    argument schema for one selected operation, and runtime validation still
    consumes the same registry schema before execution.
    """

    operation_ids = [operation for operation, _ in operation_schemas]
    return {
        "title": "math_runArguments",
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "operation": {
                "type": "string",
                "enum": operation_ids,
                "description": "Stable operation ID. Use math.describe once if its exact arguments are unfamiliar.",
            },
            "arguments": {
                "type": "object",
                "description": (
                    "Operation-specific object. Unknown fields are rejected by the selected registry contract before execution. "
                    "For integer.machine_arithmetic, inputMode is exactly value or bits and overflowBehavior is exactly "
                    "checked, wrapping, or saturating; do not invent synonyms such as decimal or wrap."
                ),
            },
            **deepcopy(_LIMIT_PROPERTIES),
        },
        "required": ["operation", "arguments"],
    }


def describe_tool_parameters(operation_schemas: list[tuple[str, dict[str, Any]]]) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "operation": {
                "type": "string",
                "minLength": 1,
                "maxLength": 128,
                "description": "Operation ID returned by math.search or listed by math.run.",
            }
        },
        "required": ["operation"],
    }


def batch_item_parameters() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        # The per-item limits are the same knob values math.run advertises;
        # publishing them keeps the per-item output budget discoverable
        # instead of failing with an undocumented default.
        "properties": {
            "operation": {"type": "string", "minLength": 1},
            "arguments": {"type": "object"},
            **deepcopy(_LIMIT_PROPERTIES),
        },
        "required": ["operation", "arguments"],
    }


def batch_tool_parameters() -> dict[str, Any]:
    return {
        "title": "math_batchArguments",
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "items": {
                "type": "array",
                "minItems": 1,
                "maxItems": 32,
                "items": batch_item_parameters(),
            },
            "timeoutMs": {
                "type": "integer",
                "minimum": 100,
                "maximum": 30_000,
                "default": 30_000,
                "description": "Cumulative deadline for the complete batch, including queued items.",
            },
            "maxOutputBytes": {
                "type": "integer",
                "minimum": MIN_OUTPUT_BYTES,
                "maximum": MAX_OUTPUT_BYTES,
                "default": DEFAULT_BATCH_MAX_OUTPUT_BYTES,
                "description": "Strict UTF-8 byte budget for the complete ordered batch result.",
            },
        },
        "required": ["items"],
    }
