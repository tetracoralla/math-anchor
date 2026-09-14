"""Trust / fail-closed vs fair template smoke.

Research-only. Not a public Capability, not a benefit percentage, and not a
Host/UI/MCP change. The frozen pack is not promoted. Latency is not the
primary claim.

Three judgments stay separate: trustworthiness, behavior, and utility.
"""

from .smoke import run_smoke

__all__ = ["run_smoke"]
