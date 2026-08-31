from __future__ import annotations

from functools import lru_cache
import importlib
import platform
from typing import Any

from . import __version__
from .models import ASSURANCE_CONTRACT_VERSION, OperationSpec


@lru_cache(maxsize=None)
def _backend_version(name: str) -> str:
    if name == "python":
        return platform.python_version()
    module = importlib.import_module(name)
    value = getattr(module, "__version__", None)
    return str(value) if value is not None else "unknown"


def _backend_names(spec: OperationSpec, result: dict[str, Any]) -> tuple[str, ...]:
    selected = result.pop("_usedBackends", None)
    if selected is None:
        return spec.backends
    if (
        not isinstance(selected, (list, tuple))
        or not selected
        or any(not isinstance(name, str) or name not in spec.backends for name in selected)
    ):
        raise ValueError(f"operation {spec.id} reported invalid execution backends")
    # Keep first-use order while preventing duplicate provenance entries.
    return tuple(dict.fromkeys(selected))


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
    annotated["assuranceContractVersion"] = ASSURANCE_CONTRACT_VERSION
    annotated["assurance"] = assurance
    annotated["claim"] = str(annotated.get("kind", spec.id))
    annotated["scope"] = spec.assurance_scope
    annotated.setdefault("assumptions", [])
    annotated["provenance"] = {
        # The runtime identity supplies the package namespace. Keeping the
        # operation module plus callable is unambiguous inside Math Anchor and
        # avoids paying for the same package prefix on every Agent result.
        "entrypoint": f"{spec.handler.__module__.rsplit('.', 1)[-1]}.{spec.handler.__name__}",
        "runtime": {"name": "math-anchor", "version": __version__},
        "backends": [
            {"name": name, "version": _backend_version(name)}
            for name in _backend_names(spec, annotated)
        ],
    }
    annotated.setdefault("certificate", None)
    annotated.setdefault("checkedBy", None)
    if assurance == "certified" and annotated.get("certificate") is None:
        raise ValueError(f"certified operation {spec.id} returned no certificate")
    if assurance == "kernel_checked" and annotated.get("checkedBy") is None:
        raise ValueError(f"kernel-checked operation {spec.id} returned no checker identity")
    return annotated
