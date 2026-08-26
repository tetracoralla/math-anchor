from __future__ import annotations

import re
from typing import Any

from .errors import CalculatorError
from .models import OperationSpec
from .operation_specs import ALL_SPECS


MAX_SEARCH_QUERY_LENGTH = 256
MAX_CATEGORY_LENGTH = 64
MAX_OPERATION_ID_LENGTH = 128
_CJK_RUN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]+")


def _search_tokens(normalized_query: str) -> set[str]:
    tokens = set(re.findall(r"[a-z0-9]+", normalized_query))
    for run in _CJK_RUN.findall(normalized_query):
        if len(run) == 1:
            tokens.add(run)
        else:
            tokens.update(run[index : index + 2] for index in range(len(run) - 1))
    return tokens


OPERATIONS = {spec.id: spec for spec in ALL_SPECS}


def search_operations(query: str = "", category: str | None = None) -> dict[str, Any]:
    if not isinstance(query, str):
        raise CalculatorError("E_INPUT", "query must be a string")
    if len(query) > MAX_SEARCH_QUERY_LENGTH:
        raise CalculatorError(
            "E_LIMIT",
            f"query must contain at most {MAX_SEARCH_QUERY_LENGTH} characters",
        )
    if category is not None and not isinstance(category, str):
        raise CalculatorError("E_INPUT", "category must be a string or null")
    if category is not None and len(category) > MAX_CATEGORY_LENGTH:
        raise CalculatorError(
            "E_LIMIT",
            f"category must contain at most {MAX_CATEGORY_LENGTH} characters",
        )
    normalized_query = query.strip().lower()
    tokens = _search_tokens(normalized_query)
    candidates = [spec for spec in ALL_SPECS if category is None or spec.category == category]
    if normalized_query:
        scored: list[tuple[int, OperationSpec]] = []
        for spec in candidates:
            haystack = " ".join((spec.id, spec.category, spec.summary, spec.description, *spec.keywords)).lower()
            alias_score = sum(
                4
                for keyword in spec.keywords
                if keyword.lower() in normalized_query or normalized_query in keyword.lower()
            )
            score = (
                (4 if normalized_query in haystack else 0)
                + alias_score
                + sum(1 for token in tokens if token in haystack)
            )
            if score:
                scored.append((score, spec))
        candidates = [spec for _, spec in sorted(scored, key=lambda item: (-item[0], item[1].id))]
    return {
        "status": "ok",
        "query": query,
        "category": category,
        "operations": [spec.compact() for spec in candidates],
        "count": len(candidates),
    }


def describe_operation(operation: str) -> dict[str, Any]:
    if not isinstance(operation, str) or not operation:
        raise CalculatorError("E_INPUT", "operation must be a non-empty string")
    if len(operation) > MAX_OPERATION_ID_LENGTH:
        raise CalculatorError(
            "E_LIMIT",
            f"operation must contain at most {MAX_OPERATION_ID_LENGTH} characters",
        )
    spec = OPERATIONS.get(operation)
    if spec is None:
        raise CalculatorError(
            "E_OPERATION",
            "unknown operation id",
            {"available": sorted(OPERATIONS)},
        )
    return {"status": "ok", "operation": spec.describe()}


def operation_schemas() -> list[tuple[str, dict[str, Any]]]:
    return [(spec.id, spec.input_schema) for spec in ALL_SPECS]
