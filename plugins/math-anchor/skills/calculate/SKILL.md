---
name: calculate
description: "Use Math Anchor for reliability-sensitive mathematics. MUST load and use it for fixed-width wrapping/saturating arithmetic, bit operations and fields, IEEE-754 representation, and large exact combinatorial counts; never answer those from mental arithmetic. Also use it for exact or high-precision evaluation, explicit rounding/division conventions, verification, calculus, linear algebra, finance, probability, statistics, measurement uncertainty, units, and dimensional analysis. For a known operation call math.run directly with {operation, arguments}. Skip only genuinely trivial low-risk arithmetic."
---

# Calculate

Translate the user's request into explicit mathematics, then use Math Anchor
when deterministic execution materially improves reliability.

## Decide and route

- Do not load it for trivial, low-risk arithmetic the model can immediately
  verify.
- Always use it for fixed-width or IEEE-754 facts; do not classify them as trivial arithmetic
  merely because the visible numbers are small.
- Call Math Anchor for machine semantics, exact or high-precision output,
  symbolic work, matrices, units, statistics, probability, finance,
  verification, repeated calculations, standard scientific algorithms, or a
  result that affects a consequential next step.
- Ask for a missing assumption when it changes the mathematical problem. Do
  not use a call to hide ambiguity.
- The four tools are already registered. Never call `list_mcp_resources`,
  inspect source, or use a shell to discover them.
- For a known request, call `math.run` directly. Use `math.search` only when
  the operation is genuinely unfamiliar or ambiguous, then `math.describe`
  once for the selected unfamiliar operation if its exact argument contract is
  still needed.
- Every run uses the outer envelope `{operation, arguments}`. Put all
  operation-specific fields inside `arguments`; never flatten them beside
  `operation`.

Three common routes are fully known. Call `math.run` directly; never search or
describe these shapes first:

- Fixed-width arithmetic: `{"operation":"integer.machine_arithmetic","arguments":{"action":"add","left":"255","right":"2","bitWidth":8,"signedness":"unsigned","inputMode":"value","overflowBehavior":"wrapping"}}`
- Exact combinations/permutations: `{"operation":"combinatorics.count","arguments":{"action":"binomial","n":52,"k":5}}`
- Checkable polynomial identity: `{"operation":"certificate.polynomial_identity","arguments":{"left":"(x+1)^2","right":"x^2+2*x+1","variables":["x"]}}`

## Execute economically

- Use `math.run` for one calculation and `math.batch` for 2–32 independent
  calculations. Batch preserves input order and does not form a dependency
  graph.
- Use `function.sample` for one expression at many points instead of repeated
  single-point calls.
- Use `resultMode: "exact"` or `resultMode: "approx"` for bulky output when
  one representation is sufficient. Raise `maxOutputBytes` only when the added
  content is useful.
- Control digits with `arguments.precision`; `precision` is not a top-level `math.run` field.
  It counts significant digits, not decimal places. Exact
  fields remain exact. For requested decimal places, allow integer digits plus
  at least two guard digits in the first call and round once for presentation.
- Supply all material assumptions explicitly: variables, bounds, units,
  conventions, brackets, data, and tolerances. Do not invent one that changes
  the answer.

Load only the relevant reference when the request needs its policy:

- [machine-semantics.md](references/machine-semantics.md) for fixed-width,
  bits, IEEE-754, rounding, and integer division.
- [scientific-math.md](references/scientific-math.md) for symbolic work,
  calculus, numerical methods, matrices, linear algebra, and verification.
- [statistics-units-dimensions.md](references/statistics-units-dimensions.md)
  for probability, statistics, uncertainty, quantities, dimensional analysis,
  and finance. Use `dimension.check` for symbolic formula consistency and
  `dimension.pi_groups` for a Buckingham Pi basis; preserve
  `scope: dimensional_consistency_only`.
- [result-error-policy.md](references/result-error-policy.md) for result
  presentation, errors, retries, limits, uncertainty, and consequential use.

## Present and check

- Prefer `exact` for symbolic answers. Include `approx` when useful or
  requested, and never describe it as exact.
- Preserve precision, units, conventions, assumptions, warnings, uncertainty,
  residuals, error bounds, stability diagnostics, branches, and omission risk
  when they affect interpretation.
- Preserve `assuranceContractVersion`, `assurance`, `scope`, `provenance`,
  `certificate`, and `checkedBy`. `certified` means a bounded artifact is
  available; `checkedBy: null` means no checker or proof kernel has accepted
  it in this call. The optional Lean bridge is a separate CLI lane, not another
  MCP tool.
- Explain the mathematical setup briefly when useful; omit engine, worker,
  schema, and protocol details from the ordinary answer.
- Stop after the first successful call for an ordinary calculation. Repeating
  identical input is not independent validation.
- A successful tool response proves that the declared operation ran; it does
  not prove that the user's problem was translated correctly.
- Before presenting a consequential result, check the cheapest relevant
  invariant already available: dimensions, sign and magnitude, support,
  residual or condition, sample size and method, or period and timing.
- If an invariant conflicts with the result, correct the declared input or
  operation once. If the conflict remains, report that the calculation could
  not be validated.
- For conceptual explanation without calculation, answer normally without the
  tools. For high-consequence decisions, use Math Anchor as calculation
  support rather than the sole authority.
