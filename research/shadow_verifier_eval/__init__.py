"""Shadow-verifier research scaffold (Epoch 2).

Research-only. Not a public Capability, not a benefit percentage, and not
Epoch 2 completion. B0/B1 stay deferred unless `--include-model-arms` is
authorized with a registered LiveModelBackend. Method packs are not
promoted. Do not start H1.
"""

from .smoke import run_smoke

__all__ = ["run_smoke"]
