"""Hand-provided finite telescoping combination rule.

This module is research-proposal infrastructure. It is not an Agent-extracted
method, not a new obligation kind, and not a CAS wrapper. The only arithmetic
it performs is subtraction of two already-evaluated rational values after the
caller has established the discrete difference identity and integer bounds.
"""

from __future__ import annotations

from fractions import Fraction


TELESCOPING_RULE_ID = "math-anchor.research.discrete-telescoping-combination.v0"
TELESCOPING_RULE_ORIGIN = "hand-provided-infrastructure"
TELESCOPING_RULE_STATEMENT = (
    "If G(k+1) - G(k) = p(k) as polynomials in k over the rationals, and a, b "
    "are integers with b >= a - 1, then the inclusive sum from k = a to k = b "
    "of p(k) equals G(b+1) - G(a). The empty-sum case b = a - 1 is 0. Bounds "
    "with b < a - 1 are unsupported; this rule does not interpret them as a "
    "negative reversed sum."
)


class TelescopingRuleError(ValueError):
    """Fail-closed combination-rule rejection."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _require_int(name: str, value: object) -> int:
    if isinstance(value, bool) or type(value) is not int:
        raise TelescopingRuleError(
            "E_DOMAIN",
            f"{name} must be an integer; boolean and non-integer values are unsupported",
        )
    return value


def apply_finite_telescoping_sum(
    *,
    difference_identity_checked: bool,
    lower: object,
    upper: object,
    g_at_upper_plus_one: Fraction,
    g_at_lower: Fraction,
) -> Fraction:
    """Combine a checked difference identity with integer bounds.

    Preconditions the caller must establish elsewhere:
    - G(k+1) - G(k) = p(k) as a rational-coefficient polynomial identity;
    - g_at_upper_plus_one is G(upper + 1) and g_at_lower is G(lower).
    """

    if difference_identity_checked is not True:
        raise TelescopingRuleError(
            "E_INPUT",
            "telescoping combination requires a checked difference identity",
        )
    if not isinstance(g_at_upper_plus_one, Fraction) or not isinstance(g_at_lower, Fraction):
        raise TelescopingRuleError(
            "E_INPUT",
            "telescoping combination requires exact rational endpoint values",
        )
    start = _require_int("lower", lower)
    stop = _require_int("upper", upper)
    if stop < start - 1:
        raise TelescopingRuleError(
            "E_DOMAIN",
            "reversed bounds with upper < lower - 1 are unsupported; "
            "the combination rule does not treat them as a negative sum",
        )
    return g_at_upper_plus_one - g_at_lower


def rule_metadata() -> dict[str, object]:
    return {
        "id": TELESCOPING_RULE_ID,
        "origin": TELESCOPING_RULE_ORIGIN,
        "agentExtracted": False,
        "statement": TELESCOPING_RULE_STATEMENT,
        "emptySumConvention": "upper == lower - 1 yields 0",
        "inclusiveBounds": True,
        "reversedBounds": "unsupported when upper < lower - 1",
    }
