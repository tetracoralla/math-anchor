from __future__ import annotations

import importlib
import threading
from typing import Any, Callable


class LazyOperationHandler:
    """Resolve one operation callable only when the operation is executed.

    Operation metadata and schemas must be cheap to import because every CLI,
    MCP, and direct-host process needs them before it knows which mathematical
    engine the request will use.  The public callable identity is available
    without importing that engine so provenance stays deterministic.
    """

    def __init__(self, module: str, name: str) -> None:
        self.__module__ = module
        self.__name__ = name
        self._callable: Callable[[dict[str, Any]], dict[str, Any]] | None = None
        self._lock = threading.Lock()

    def _resolve(self) -> Callable[[dict[str, Any]], dict[str, Any]]:
        callable_ = self._callable
        if callable_ is not None:
            return callable_
        with self._lock:
            callable_ = self._callable
            if callable_ is None:
                module = importlib.import_module(self.__module__)
                candidate = getattr(module, self.__name__, None)
                if not callable(candidate):
                    raise RuntimeError(
                        f"operation handler is unavailable: {self.__module__}.{self.__name__}"
                    )
                callable_ = candidate
                self._callable = callable_
        return callable_

    def __call__(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return self._resolve()(arguments)


class LazyOperationModule:
    """Provide stable lazy handler attributes for one operations module."""

    def __init__(self, name: str) -> None:
        self._module = f"math_anchor.operations.{name}"
        self._handlers: dict[str, LazyOperationHandler] = {}

    def __getattr__(self, name: str) -> LazyOperationHandler:
        if name.startswith("_"):
            raise AttributeError(name)
        handler = self._handlers.get(name)
        if handler is None:
            handler = LazyOperationHandler(self._module, name)
            self._handlers[name] = handler
        return handler
