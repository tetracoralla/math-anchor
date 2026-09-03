---
name: calculate
description: "Use Math Anchor for reliability-sensitive mathematics. MUST load and use it for fixed-width arithmetic, bit/IEEE-754 facts, and large exact combinatorial counts. Also use it for exact or high-precision work, explicit conventions, verification, calculus, linear algebra, finance, probability, statistics, uncertainty, units, and dimensions. Call a known operation with math.run; skip only trivial low-risk arithmetic."
---

# Calculate

## Decide and route

- Do not load it for trivial, low-risk arithmetic the model can immediately
  verify.
- Treat fixed-width wrapping/saturating arithmetic as mandatory; do not classify them as trivial arithmetic.
- Always use it for fixed-width or IEEE-754 facts, exact/high-precision or
  symbolic work, matrices, units, statistics, probability, finance,
  verification, repeated calculations, or consequential results.
- Ask for a missing assumption when it changes the problem; a call must not
  hide ambiguity.
- The four tools are registered. Never call `list_mcp_resources`, inspect
  source, or use a shell to find them. Use `math.run` for a known operation;
  otherwise search, then describe only if needed.
- For an obligation DAG, failures-only checkpoint, or receipt replay, do not
  search the MCP catalog. When this installed Skill contains the Host-generated
  `scripts/math-anchor` launcher, invoke it relative to this Skill directory
  with `check-obligations` or `replay-obligations`; retain receipts outside
  model context. Never substitute an ambient command or source checkout. If
  the launcher is absent, report that this carrier has no obligation checkpoint.
- Every run uses the outer envelope `{operation, arguments}`. Put all
  operation-specific fields inside `arguments`; never flatten them beside
  `operation`.

Call these fully known routes directly; never search or
describe these shapes first:

- Fixed-width arithmetic: `{"operation":"integer.machine_arithmetic","arguments":{"action":"add","left":"255","right":"2","bitWidth":8,"signedness":"unsigned","inputMode":"value","overflowBehavior":"wrapping"}}`
- Exact combinations/permutations: `{"operation":"combinatorics.count","arguments":{"action":"binomial","n":52,"k":5}}`
- Checkable polynomial identity: `{"operation":"certificate.polynomial_identity","arguments":{"left":"(x+1)^2","right":"x^2+2*x+1","variables":["x"]}}`

## Execute economically

- Use one `math.run`, `math.batch` for 2–32 independent ordered calculations,
  or `function.sample` for one expression at many points. Batch is not a
  dependency graph.
- For bulky output, select `resultMode` and raise `maxOutputBytes` only when useful.
- Control digits with `arguments.precision`; `precision` is not a top-level `math.run` field.
  It counts significant digits. Exact fields stay exact. For decimal places,
  include integer digits plus at least two guard digits in the first call and
  round once for presentation.
- Supply answer-changing variables, bounds, units, conventions, and tolerances.

Load a reference only when needed. A fully specified
`integer.machine_arithmetic` call needs no reference.

- [machine-semantics.md](references/machine-semantics.md) for representation or
  bit operations, IEEE-754, rounding, integer division, or a missing machine
  convention.
- [scientific-math.md](references/scientific-math.md) for symbolic, calculus,
  numerical, matrix, geometry, and verification work.
- [statistics-units-dimensions.md](references/statistics-units-dimensions.md)
  for probability, statistics, uncertainty, quantities, dimensions, and
  finance. Use `dimension.check` for symbolic formula consistency and
  `dimension.pi_groups` for a Buckingham Pi basis; preserve
  `scope: dimensional_consistency_only`.
- [result-error-policy.md](references/result-error-policy.md) for result
  presentation, errors, retries, limits, uncertainty, and consequential use.

## Present and check

- Prefer `exact`; include `approx` only when useful and never call it exact.
  Preserve interpretation-changing precision, units, assumptions, warnings,
  uncertainty, residuals, bounds, stability, branches, and omission risk.
- Preserve `assuranceContractVersion`, `assurance`, `scope`, `provenance`,
  `certificate`, and `checkedBy`. `certified` exposes a bounded artifact;
  `checkedBy: null` means no checker/kernel accepted it. Lean is a separate
  CLI lane, not another MCP tool.
- Explain useful mathematical setup, not engine or protocol internals.
- Stop after the first successful call for an ordinary calculation. Repeating
  identical input is not independent validation.
- A successful tool response proves that the declared operation ran; it does
  not prove that the user's problem was translated correctly.
- For consequential results, check the cheapest relevant invariant: dimensions,
  sign/magnitude, support, residual/condition, sample size/method, or timing.
  Correct the declared input/operation once on conflict; if it remains, report
  that validation failed.
- Answer conceptual questions without tools when no calculation is needed.
  Math Anchor supports high-consequence decisions; it is not their sole authority.
