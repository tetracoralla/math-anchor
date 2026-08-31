from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


OperationHandler = Callable[[dict[str, Any]], dict[str, Any]]
ASSURANCE_LEVELS = (
    "heuristic",
    "deterministic",
    "diagnostic",
    "certified",
    "kernel_checked",
)
ASSURANCE_CONTRACT_VERSION = "1.0"


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
    assurance: str = "deterministic"
    assurance_scope: str = "declared_operation_result"
    backends: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.assurance not in ASSURANCE_LEVELS:
            raise ValueError(f"unsupported assurance level for {self.id}: {self.assurance}")
        if not self.assurance_scope or len(self.assurance_scope) > 128:
            raise ValueError(f"invalid assurance scope for {self.id}")
        if not self.backends or any(not backend or len(backend) > 64 for backend in self.backends):
            raise ValueError(f"invalid backend identity for {self.id}")

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
            "assurance": {
                "level": self.assurance,
                "scope": self.assurance_scope,
                "certificateAvailable": self.assurance in {"certified", "kernel_checked"},
            },
        }
