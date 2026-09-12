"""Experimental method-pack research namespace (A2).

Not a public Capability or Procedure, not a supported domain module, and not a
fifth MCP tool. Packs are JSON documents with a restricted apply path.
"""

from .apply import apply_method_pack
from .format import (
    LIFECYCLE_CANDIDATE,
    LIFECYCLE_CROSS_TASK,
    LIFECYCLE_VERIFIED,
    NOVELTY_KNOWN_ADAPTATION,
    PACK_ID,
)
from .loader import load_pack

__all__ = [
    "LIFECYCLE_CANDIDATE",
    "LIFECYCLE_CROSS_TASK",
    "LIFECYCLE_VERIFIED",
    "NOVELTY_KNOWN_ADAPTATION",
    "PACK_ID",
    "apply_method_pack",
    "load_pack",
]
