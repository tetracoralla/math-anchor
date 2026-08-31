from __future__ import annotations

from functools import lru_cache
import importlib
import platform
from typing import Any

from . import __version__
from .models import OperationSpec


_MODULE_BACKENDS = {
    "algebra": ("sympy",),
    "calculus": ("sympy",),
    "combinatorics": ("sympy",),
    "data": ("pint",),
    "dimension": ("sympy", "pint"),
    "expression": ("sympy",),
    "finance": ("python",),
    "floating": ("python",),
    "inference": ("numpy", "mpmath"),
    "linear_algebra": ("numpy", "sympy"),
    "matrix": ("numpy", "sympy"),
    "measurement": ("sympy",),
    "number_theory": ("sympy",),
    "numerical": ("mpmath", "sympy"),
    "optimization": ("mpmath", "sympy"),
    "probability": ("mpmath",),
    "programmer": ("python",),
    "quantity": ("pint", "sympy"),
    "rounding": ("python",),
    "units": ("pint",),
    "verification": ("sympy",),
}


@lru_cache(maxsize=None)
def _backend_version(name: str) -> str:
    if name == "python":
        return platform.python_version()
    module = importlib.import_module(name)
    value = getattr(module, "__version__", None)
    return str(value) if value is not None else "unknown"


def _backend_names(spec: OperationSpec) -> tuple[str, ...]:
    if spec.backends:
        return spec.backends
    module_name = spec.handler.__module__.rsplit(".", 1)[-1]
    return _MODULE_BACKENDS.get(module_name, ("python",))


def _result_assurance(spec: OperationSpec, result: dict[str, Any]) -> str:
    # A bounded probe that found neither a proof nor a counterexample is useful
    # exploration, not a deterministic mathematical conclusion.
    if spec.id == "expression.equivalent" and result.get("proven") is False:
        return "heuristic"
    return spec.assurance


def apply_research_contract(spec: OperationSpec, result: dict[str, Any]) -> dict[str, Any]:
    """Attach the compact assurance envelope before result validation.

    The envelope describes the operation's actual claim boundary. It does not
    promote generated records into proof: certified results must also carry a
    certificate, and kernel_checked results require a non-null checkedBy value.
    """

    status = result.get("status")
    if status not in {"ok", "uncertain"}:
        return result
    annotated = dict(result)
    assurance = _result_assurance(spec, annotated)
    # Assurance, claim boundary, and runtime provenance are registry/runtime
    # facts. A handler must not be able to promote its own output by returning
    # stronger labels or a broader scope.
    annotated["assurance"] = assurance
    annotated["claim"] = str(annotated.get("kind", spec.id))
    annotated["scope"] = spec.assurance_scope
    annotated.setdefault("assumptions", [])
    annotated["provenance"] = {
        "runtime": {"name": "math-anchor", "version": __version__},
        "backends": [
            {"name": name, "version": _backend_version(name)}
            for name in _backend_names(spec)
        ],
    }
    annotated.setdefault("certificate", None)
    annotated.setdefault("checkedBy", None)
    if assurance == "certified" and annotated.get("certificate") is None:
        raise ValueError(f"certified operation {spec.id} returned no certificate")
    if assurance == "kernel_checked" and annotated.get("checkedBy") is None:
        raise ValueError(f"kernel-checked operation {spec.id} returned no checker identity")
    return annotated
