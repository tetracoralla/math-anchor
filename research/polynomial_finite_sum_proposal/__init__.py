"""A0/A1 proposal: rational-polynomial finite sums via a checked discrete antidifference.

This is a research vertical, not a supported Math Anchor domain module and not
an Agent-extracted method library.
"""

from .coverage import record_coverage
from .runner import run_polynomial_finite_sum
from .telescoping import (
    TELESCOPING_RULE_ID,
    TELESCOPING_RULE_ORIGIN,
    apply_finite_telescoping_sum,
)

__all__ = [
    "TELESCOPING_RULE_ID",
    "TELESCOPING_RULE_ORIGIN",
    "apply_finite_telescoping_sum",
    "record_coverage",
    "run_polynomial_finite_sum",
]
