from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class CalculatorError(Exception):
    code: str
    message: str
    details: dict[str, Any] | None = None

    def __str__(self) -> str:
        return self.message

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.details:
            payload["details"] = self.details
        return payload


def require(condition: bool, code: str, message: str) -> None:
    if not condition:
        raise CalculatorError(code, message)

