from __future__ import annotations

from typing import Any

from .errors import error_payload


def _error(
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
    *,
    phase: str | None = None,
    retry_after_ms: int | None = None,
    suggested_action: str | None = None,
) -> dict[str, Any]:
    return {
        "status": "error",
        "error": error_payload(
            code,
            message,
            details,
            phase=phase,
            retry_after_ms=retry_after_ms,
            suggested_action=suggested_action,
        ),
    }
