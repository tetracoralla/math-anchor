from __future__ import annotations

from dataclasses import dataclass
from typing import Any


_RETRYABLE_CODES = {"E_OVERLOADED", "E_RUNTIME", "E_UNAVAILABLE"}
_INPUT_CODES = {
    "E_AST_BLOCK",
    "E_DOMAIN",
    "E_INPUT",
    "E_LIMIT",
    "E_NAME",
    "E_OPERATION",
    "E_UNIT",
}


def error_payload(
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
    *,
    phase: str | None = None,
    retry_after_ms: int | None = None,
    suggested_action: str | None = None,
) -> dict[str, Any]:
    """Create the stable machine-actionable error contract.

    Messages remain useful to humans, but callers can branch on retryability,
    phase, delay, and suggested action without parsing English.
    """
    resolved_phase = phase or (
        str(details.get("phase"))
        if details is not None and isinstance(details.get("phase"), str)
        else _default_phase(code)
    )
    payload: dict[str, Any] = {
        "code": code,
        "message": message,
        "retryable": code in _RETRYABLE_CODES,
        "phase": resolved_phase,
        "suggestedAction": suggested_action or _default_action(code, resolved_phase),
    }
    if retry_after_ms is not None:
        payload["retryAfterMs"] = max(1, int(retry_after_ms))
    if details:
        payload["details"] = details
    return payload


def _default_phase(code: str) -> str:
    if code in _INPUT_CODES:
        return "input"
    if code == "E_OUTPUT_LIMIT":
        return "output"
    if code == "E_CANCELLED":
        return "cancellation"
    if code == "E_MEMORY":
        return "execution"
    if code == "E_TIMEOUT":
        return "execution"
    if code in {"E_OVERLOADED", "E_UNAVAILABLE"}:
        return "admission"
    return "execution"


def _default_action(code: str, phase: str) -> str:
    if code == "E_OPERATION":
        return "search_operation"
    if code in _INPUT_CODES:
        return "correct_input"
    if code in {"E_OUTPUT_LIMIT", "E_MEMORY"}:
        return "reduce_request"
    if code == "E_TIMEOUT":
        return "split_or_reduce"
    if code in _RETRYABLE_CODES:
        return "retry"
    if code == "E_CANCELLED" or phase == "cancellation":
        return "stop"
    return "stop"


@dataclass
class CalculatorError(Exception):
    code: str
    message: str
    details: dict[str, Any] | None = None

    def __str__(self) -> str:
        return self.message

    def as_dict(self) -> dict[str, Any]:
        return error_payload(self.code, self.message, self.details)


def require(condition: bool, code: str, message: str) -> None:
    if not condition:
        raise CalculatorError(code, message)
