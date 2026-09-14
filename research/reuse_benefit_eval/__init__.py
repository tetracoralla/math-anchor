"""Equal-budget reuse-benefit smoke with strong CAS baselines.

Research-only. Not a public Capability, not a benefit percentage, and not a
Host/UI/MCP change. The frozen pack is not promoted.

Three judgments stay separate: trustworthiness, behavior, and utility.
"""

from .smoke import run_smoke

__all__ = ["run_smoke"]
