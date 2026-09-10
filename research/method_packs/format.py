"""Experimental method-pack format constants (not a public Capability schema)."""

from __future__ import annotations

from pathlib import Path


SCHEMA_VERSION = "math-anchor.research.experimental-method-pack.v0"
PACK_ID = "math-anchor.research.method-pack.polynomial-antidifference-gosper.v0"
PACK_VERSION = "0.1.0-experimental"
APPLICATION_KIND = "math-anchor.research.experimental-method-pack-application.v0"

LIFECYCLE_CANDIDATE = "candidate"
LIFECYCLE_VERIFIED = "verified-in-declared-scope"
LIFECYCLE_CROSS_TASK = "cross-task-use-evidence"
EXECUTABLE_LIFECYCLES = frozenset({LIFECYCLE_VERIFIED, LIFECYCLE_CROSS_TASK})

NOVELTY_KNOWN_ADAPTATION = "known-method-adaptation"
NOVELTY_REDISCOVERY = "rediscovery"
NOVELTY_UNPROVEN_NEW = "unproven-new"
ALLOWED_NOVELTY = frozenset(
    {NOVELTY_KNOWN_ADAPTATION, NOVELTY_REDISCOVERY, NOVELTY_UNPROVEN_NEW}
)

EXTRACTION_TASK_ID = "T1"
HELD_OUT_SECOND_TASK_ID = "A2-second-sum-k-cubed-1-to-20"

REQUIRED_INSTANTIATION_RULE_IDS = (
    "parse_summand_safe_expression",
    "require_univariate_qq_polynomial_constant_denominators",
    "construct_antidifference_sympy_gosper",
    "emit_polynomial_identity_obligation",
    "evaluate_endpoints_independent_parser",
    "apply_infrastructure_telescoping_rule",
)

FORBIDDEN_PACK_KEYS = frozenset(
    {
        "eval",
        "exec",
        "python",
        "code",
        "callable",
        "import",
        "__import__",
        "sympify",
        "parse_expr",
    }
)

PACKS_ROOT = Path(__file__).resolve().parent
DEFAULT_PACK_DIR = PACKS_ROOT / "polynomial_antidifference_gosper.v0"
DEFAULT_PACK_PATH = DEFAULT_PACK_DIR / "pack.json"
REPO_ROOT = PACKS_ROOT.parents[1]
