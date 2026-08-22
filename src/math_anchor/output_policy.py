from __future__ import annotations

from copy import deepcopy
import json
from typing import Any


DEFAULT_RESULT_MODE = "auto"
DEFAULT_MAX_OUTPUT_BYTES = 64 * 1024
DEFAULT_BATCH_MAX_OUTPUT_BYTES = 128 * 1024
MIN_OUTPUT_BYTES = 1_024
MAX_OUTPUT_BYTES = 1_048_576
RESULT_MODES = ("auto", "exact", "approx", "both")


def apply_output_policy(
    result: dict[str, Any],
    *,
    result_mode: str,
    max_output_bytes: int,
) -> dict[str, Any]:
    selected = deepcopy(result)
    if result.get("status") in {"ok", "uncertain"}:
        if result_mode == "exact":
            _drop_redundant(selected, field="approx", counterpart="exact")
        elif result_mode == "approx":
            _drop_all(selected, field="exact")

    size = _encoded_size(selected)
    if (
        result.get("status") in {"ok", "uncertain"}
        and result_mode == "auto"
        and size > max_output_bytes
    ):
        _drop_redundant(selected, field="approx", counterpart="exact")
        size = _encoded_size(selected)

    if size <= max_output_bytes:
        return selected
    if result.get("status") == "error":
        trimmed = _trim_error_envelope(selected, max_output_bytes)
        if trimmed is not None:
            return trimmed
    return {
        "status": "error",
        "error": {
            "code": "E_OUTPUT_LIMIT",
            "message": (
                f"result requires {size} bytes after applying resultMode={result_mode}; "
                f"increase maxOutputBytes or request a smaller result"
            ),
            "details": {
                "bytes": size,
                "maxOutputBytes": max_output_bytes,
                "resultMode": result_mode,
            },
        },
    }


def _trim_error_envelope(
    selected: dict[str, Any],
    max_output_bytes: int,
) -> dict[str, Any] | None:
    """Shrink an oversized error envelope in place, preserving its code.

    Error messages can embed original exception text (an E_RUNTIME echoing
    long input), so an error envelope can exceed the byte budget. Replacing
    it wholesale with E_OUTPUT_LIMIT hid the real failure behind an unrelated
    "increase maxOutputBytes" instruction. Drop details first, then shorten
    the message, and keep the envelope only once it fits.
    """
    error = selected.get("error")
    if not isinstance(error, dict):
        return None
    error.pop("details", None)
    if _encoded_size(selected) <= max_output_bytes:
        return selected
    message = error.get("message")
    if not isinstance(message, str) or not message:
        return None
    for limit in (512, 256, 128, 64, 32, 16, 8, 0):
        error["message"] = message[:limit] + ("…" if limit else "")
        if _encoded_size(selected) <= max_output_bytes:
            return selected
    return None


def _drop_redundant(value: Any, *, field: str, counterpart: str) -> None:
    if isinstance(value, dict):
        if field in value and counterpart in value and value[counterpart] is not None:
            value[field] = None
        for child in value.values():
            _drop_redundant(child, field=field, counterpart=counterpart)
    elif isinstance(value, list):
        for child in value:
            _drop_redundant(child, field=field, counterpart=counterpart)


def _drop_all(value: Any, *, field: str) -> None:
    if isinstance(value, dict):
        if field in value:
            value[field] = None
        for child in value.values():
            _drop_all(child, field=field)
    elif isinstance(value, list):
        for child in value:
            _drop_all(child, field=field)


def _encoded_size(result: dict[str, Any]) -> int:
    return len(json.dumps(result, ensure_ascii=False, separators=(",", ":")).encode())
