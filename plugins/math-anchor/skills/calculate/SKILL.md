---
name: calculate
description: "Use Math Anchor for reliability-sensitive mathematics. MUST load and use it for fixed-width wrapping/saturating arithmetic, bit operations and fields, IEEE-754 representation, and large exact combinatorial counts; never answer those from mental arithmetic. Also use it for exact or high-precision evaluation, explicit rounding/division conventions, verification, calculus, linear algebra, finance, probability, statistics, measurement uncertainty, units, and dimensional analysis. For a known operation call math.run directly with {operation, arguments}. Skip only genuinely trivial low-risk arithmetic."
---

# Calculate

Translate the request into explicit mathematics and use Math Anchor when
deterministic execution materially improves reliability.

## Decide and route

- Do not load it for trivial, low-risk arithmetic the model can immediately
  verify.
- Always use it for fixed-width wrapping/saturating arithmetic, bit fields, or
  IEEE-754 facts; do not classify them as trivial arithmetic because the
  visible numbers are small.
- Also use it for exact/high-precision output, symbolic work, matrices, units,
  statistics, probability, finance, verification, repeated calculations,
  standard scientific algorithms, or consequential results.
- Ask for a missing assumption when it changes the problem; a call must not
  hide ambiguity.
- The four tools are registered. Never call `list_mcp_resources`, inspect
  source, or use a shell to find them. Call known operations with `math.run`. Otherwise use
  `math.search`, then `math.describe` once only if the selected schema is still
  needed.
- Every run uses the outer envelope `{operation, arguments}`. Put all
  operation-specific fields inside `arguments`; never flatten them beside
  `operation`.

Three common routes are fully known. Call `math.run` directly; never search or
describe these shapes first:

- Fixed-width arithmetic: `{"operation":"integer.machine_arithmetic","arguments":{"action":"add","left":"255","right":"2","bitWidth":8,"signedness":"unsigned","inputMode":"value","overflowBehavior":"wrapping"}}`
- Exact combinations/permutations: `{"operation":"combinatorics.count","arguments":{"action":"binomial","n":52,"k":5}}`
- Checkable polynomial identity: `{"operation":"certificate.polynomial_identity","arguments":{"left":"(x+1)^2","right":"x^2+2*x+1","variables":["x"]}}`

## Execute economically

- Use one `math.run`, `math.batch` for 2–32 independent ordered calculations,
  or `function.sample` for one expression at many points. Batch is not a
  dependency graph.
- For bulky output, request only the needed `resultMode` (`exact` or `approx`)
  and raise `maxOutputBytes` only when useful.
- Control digits with `arguments.precision`; `precision` is not a top-level `math.run` field.
  It counts significant digits. Exact fields stay exact. For decimal places,
  include integer digits plus at least two guard digits in the first call and
  round once for presentation.
- Supply variables, bounds, units, conventions, brackets, data, and tolerances
  explicitly. Never invent an answer-changing assumption.

Load a reference only when the request needs policy not already explicit in the
known route above. When action, operands, bit width, signedness, input mode, and
overflow behavior are all stated, call `integer.machine_arithmetic` directly
without loading another file.

- [machine-semantics.md](references/machine-semantics.md) for representation or
  bit operations, IEEE-754, rounding, integer division, or a missing machine
  convention.
- [scientific-math.md](references/scientific-math.md) for symbolic work,
  calculus, numerical methods, matrices, linear algebra, and verification.
- [statistics-units-dimensions.md](references/statistics-units-dimensions.md)
  for probability, statistics, uncertainty, quantities, dimensions, and
  finance. Use `dimension.check` for symbolic formula consistency and
  `dimension.pi_groups` for a Buckingham Pi basis; preserve
  `scope: dimensional_consistency_only`.
- [result-error-policy.md](references/result-error-policy.md) for result
  presentation, errors, retries, limits, uncertainty, and consequential use.

## Present and check

- Prefer `exact` for symbolic answers; include `approx` only when useful and
  never call it exact. Preserve interpretation-changing precision, units,
  assumptions, warnings, uncertainty, residuals, bounds, stability, branches,
  and omission risk.
- Preserve `assuranceContractVersion`, `assurance`, `scope`, `provenance`,
  `certificate`, and `checkedBy`. `certified` exposes a bounded artifact;
  `checkedBy: null` means no checker/kernel accepted it. Lean is a separate
  CLI lane, not another MCP tool.
- Briefly explain useful mathematical setup, not engine/protocol internals.
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
