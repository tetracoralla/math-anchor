from __future__ import annotations

import json
from typing import Any


MAX_REQUEST_BYTES = 8 * 1024 * 1024
MAX_REQUEST_NODES = 250_000
MAX_REQUEST_DEPTH = 64
MAX_BATCH_REQUEST_BYTES = 16 * 1024 * 1024
MAX_BATCH_REQUEST_NODES = 500_000


class TransportBudgetError(ValueError):
    def __init__(self, message: str, *, rule: str) -> None:
        super().__init__(message)
        self.rule = rule


def encode_json_line(
    value: Any,
    *,
    max_bytes: int = MAX_REQUEST_BYTES,
    max_nodes: int = MAX_REQUEST_NODES,
    max_depth: int = MAX_REQUEST_DEPTH,
) -> str:
    _validate_shape(
        value,
        max_bytes=max_bytes,
        max_nodes=max_nodes,
        max_depth=max_depth,
    )
    encoder = json.JSONEncoder(ensure_ascii=False, separators=(",", ":"))
    chunks: list[str] = []
    encoded_bytes = 1  # newline
    for chunk in encoder.iterencode(value):
        encoded_bytes += len(chunk.encode("utf-8"))
        if encoded_bytes > max_bytes:
            raise TransportBudgetError(
                f"request exceeds the cumulative {max_bytes}-byte transport limit",
                rule="maxRequestBytes",
            )
        chunks.append(chunk)
    return "".join(chunks) + "\n"


def _validate_shape(
    value: Any,
    *,
    max_bytes: int,
    max_nodes: int,
    max_depth: int,
) -> None:
    nodes = 0
    text_bytes = 0
    active_containers: set[int] = set()
    stack: list[tuple[Any, int, bool]] = [(value, 0, False)]
    while stack:
        current, depth, exiting = stack.pop()
        if exiting:
            active_containers.remove(id(current))
            continue
        nodes += 1
        if nodes > max_nodes:
            raise TransportBudgetError(
                f"request exceeds the cumulative {max_nodes}-node transport limit",
                rule="maxRequestNodes",
            )
        if depth > max_depth:
            raise TransportBudgetError(
                f"request exceeds the cumulative depth limit of {max_depth}",
                rule="maxRequestDepth",
            )
        if isinstance(current, str):
            text_bytes += len(current.encode("utf-8"))
            if text_bytes > max_bytes:
                raise TransportBudgetError(
                    f"request text exceeds the cumulative {max_bytes}-byte transport limit",
                    rule="maxRequestBytes",
                )
            continue
        if isinstance(current, dict):
            identity = id(current)
            if identity in active_containers:
                raise ValueError("circular reference in request")
            active_containers.add(identity)
            stack.append((current, depth, True))
            for key, child in current.items():
                if not isinstance(key, str):
                    raise TypeError("request object keys must be strings")
                stack.append((child, depth + 1, False))
                stack.append((key, depth + 1, False))
            continue
        if isinstance(current, (list, tuple)):
            identity = id(current)
            if identity in active_containers:
                raise ValueError("circular reference in request")
            active_containers.add(identity)
            stack.append((current, depth, True))
            for child in reversed(current):
                stack.append((child, depth + 1, False))
            continue
        if current is None or isinstance(current, (bool, int, float)):
            continue
        raise TypeError(f"request contains a non-JSON value: {type(current).__name__}")
