from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


OperationHandler = Callable[[dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class OperationSpec:
    id: str
    category: str
    summary: str
    description: str
    input_schema: dict[str, Any]
    examples: tuple[dict[str, Any], ...]
    handler: OperationHandler
    keywords: tuple[str, ...] = ()

    def compact(self) -> dict[str, str]:
        return {
            "id": self.id,
            "category": self.category,
            "summary": self.summary,
        }

    def describe(self) -> dict[str, Any]:
        return {
            **self.compact(),
            "description": self.description,
            "inputSchema": self.input_schema,
            "examples": list(self.examples),
        }

