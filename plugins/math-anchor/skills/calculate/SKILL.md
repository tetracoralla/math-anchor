---
name: calculate
description: "Use Math Anchor for reliability-sensitive mathematics: fixed-width wrapping/saturating arithmetic, bit operations and fields, IEEE-754 representation, exact or high-precision evaluation, explicit decimal rounding and integer-division conventions, verification, algebra, calculus, linear algebra, finance, probability, statistics, measurement uncertainty, physical quantities, and dimensional analysis. Its four tools are already registered; for a known operation call math.run directly with {operation, arguments}, nesting every operation-specific field inside arguments. Do not load it for trivial, low-risk arithmetic the model can immediately verify; trigger when machine semantics, precision, exactness, units, diagnostics, reuse, or consequences justify deterministic calculation."
---

# Calculate

Let reasoning translate the user's request into mathematics, then use the runtime when a deterministic calculation materially improves reliability.

## Decide whether to call

- Call Math Anchor whenever the result depends on a fixed bit width, signedness,
  wrapping or saturation, bit-field/shift/rotate behavior, or IEEE-754 format.
  These are machine-semantics tasks even when the visible arithmetic is small;
  do not classify them as trivial arithmetic.
- Answer trivial, low-risk arithmetic directly when it is immediately verifiable, needs no units or special convention, and is not feeding a consequential decision. Examples include a single small addition or multiplication.
- Call Math Anchor when the user asks for exact or high-precision output, symbolic work, units, matrices, statistics, probability, financial math, verification, repeated calculations, or a result whose correctness affects a consequential next step.
- Call Math Anchor when the alternative would be mentally simulating a multi-step calculation or a standard scientific algorithm.
- If a missing assumption changes the mathematical problem, ask for it before calling. Do not use a tool call to hide ambiguity.

## Select the operation

- The four Math Anchor tools are already registered. Never call `list_mcp_resources`, inspect a source checkout, or use a shell command to discover them.
- For an ordinary known request, call `math.run` directly. Its host-safe schema contains every stable operation id and the execution envelope. If the exact argument contract is unfamiliar, call `math.describe` once for that selected id instead of guessing; runtime validation remains closed.
- Every `math.run` call uses the outer envelope `{operation, arguments}`. Put
  `action`, operands, widths, expressions, matrices, units, and every other
  operation-specific field inside `arguments`; never flatten them beside
  `operation`.
- Use `units.search` when a conversion unit's stable ID or compound runtime spelling is unknown. `units.convert` accepts those stable IDs directly.
- Use `quantity.evaluate` for concrete unit-bearing arithmetic such as `3 * meter + 25 * centimeter`. Use `dimension.check` for symbolic formula consistency, `dimension.infer` when declared symbol dimensions are unknown, and `dimension.pi_groups` for a Buckingham Pi basis of dimensionless products. These are known operations and do not require search or describe.
- Call `math.search` only when the mathematical operation is genuinely unfamiliar or ambiguous. Search using the user's task language.
- Call `math.describe` only for the selected unfamiliar operation when its contract still needs inspection.

## Execute

- Call `math.run` for one calculation.
- Call `math.batch` for 2 to 32 independent calculations when they can run without consuming one another's output. Preserve input order when matching results back to the request.
- For large matrices or other bulky results, prefer `resultMode: "exact"` or `resultMode: "approx"` when only one representation is needed. Increase `maxOutputBytes` only when the additional content is genuinely useful. `math.batch` keeps a compact generic item contract; use `math.describe` only if an item's operation schema is unfamiliar.
- Control output digits with the selected operation's `arguments.precision` field; its allowed range and default are operation-specific, and binary64 decomposition operations cap it at 15. `precision` is not a top-level `math.run` field. Exact values are exact regardless of precision; only the approximate field follows it. Do not request extreme precision reflexively: high precision slows evaluation and bloats results, and most inputs only carry a few trustworthy digits.
- `arguments.precision` counts significant digits, not decimal places. When the user requests decimal places, include the expected integer digits plus at least two guard digits in the first call, then round once for presentation; do not make a preliminary lower-precision call.
- Use `function.sample` to evaluate one expression at many points in a single call (explicit point list or an even grid) instead of issuing repeated single-point evaluations.

- Supply all business assumptions explicitly as expressions, variables, bounds, units, or data. Do not invent a missing unit, equation, time period, statistical convention, root bracket, or variable meaning when it changes the answer.
- Use `integer.represent` to decode or render a fixed-width value, `integer.bitwise` for logical/shift/rotate/bit-field/alignment work, and `integer.machine_arithmetic` when checked, wrapping, or saturating execution semantics matter. Always supply width, signedness, and value-versus-bits interpretation. Preserve the unbounded mathematical result, machine result, overflow, wrap, saturation, truncation, and discarded bits as different facts. Use `decimal.quantize` and `integer.divide` when tie-breaking, directed rounding, or quotient/remainder sign conventions matter outside a fixed-width machine operation.
- Use `float.ieee754` when a request depends on binary32/binary64 fields, signed zero, subnormals, infinity/NaN, the exact represented value, adjacent values, ULP size or distance, or numeric-versus-bit equality. Do not use ordinary decimal evaluation to infer those machine facts.
- For matrix solving, rank, RREF, and basis operations, send exact integers or rational text such as `1/10`. Do not silently turn approximate decimal matrices into exact structural claims.
- Use `matrix.solve_approximate` for decimal matrices only when the tolerance is meaningful to the request; preserve its condition, residual, backward-error, and stability fields.
- Use `matrix.reduce` for exact eigenspaces and diagonalizability, LU, or Cholesky as well as rank, RREF, nullspace, and column space. Preserve the returned multiplicities, basis, pivot permutation, and factor relation. Use `linear_algebra.exact` for matrix multiplication and transpose over exact inputs, or dot/cross products, norms, and projection over provably real exact vectors. Use `linear_algebra.numeric` for decimal-text least squares, QR, SVD, or pseudoinverse; preserve its binary64 provenance, singular-value tolerance, rank, condition, residual diagnostics, and the least-squares uniqueness/minimum-norm convention.
- Use `calculus.multivariate` for gradients, Jacobians, Hessians, unnormalized directional derivatives, divergence, curl, and the Laplacian. Preserve the declared variable order; divergence requires one field component per variable and curl is explicitly three-dimensional.
- Use `numeric.integrate` when a symbolic definite integral is unavailable or a numerical interval is requested. Preserve that its `resultInterval` is estimate-based whenever `errorBoundCertified` is false. A result with `status: uncertain` met only the local error estimate; do not call it converged. Supply `breakpoints` only when they identify every material discontinuity or localized feature, or `featureScale` only when the user can bound the minimum material feature width.
- Use `expression.equivalent` instead of comparing formatted strings. Keep its default strict definedness policy unless the user explicitly means equality only where both expressions are defined.
- Use `numeric.minimize` when a global minimum or maximum over a bracket is requested. Its `valueEnclosure` and `extremumIntervals` are rigorous interval-arithmetic results; treat `status: uncertain` as the best certified bound, not a finished answer. The bracket must avoid undefined points; supply a narrower bracket when it does not.
- Use `numeric.root` with `findAll` when every sign-changing root in a bracket is requested; report the honest limitation that even-multiplicity roots or roots closer together than the resolution can be missed.

- Use `solution.verify` to check supplied roots or assignments. Do not describe candidates as exhaustive unless `omissionRisk` is `none_proven`.
- Write unit arithmetic with explicit multiplication, such as `80 * kg * 9.81 * m / s^2`, and use `toUnit` when a named result unit matters.
- Do not treat month or year as a fixed physical duration. Leave the default rejection in place for civil-calendar work; select `calendarPolicy: "average_duration"` only when the user explicitly wants the fixed average convention, and preserve its warning.
- For symbolic checks and inference, declare every expression symbol with a unit or canonical dimension vector. Preserve `scope: dimensional_consistency_only`: consistency does not prove a physical law or coefficient is correct. `dimension.infer` returns dimensions, not a preferred unit. An `underdetermined` result can still contain parameter-independent entries in `inferred`; treat only `unresolved` symbols as unresolved, and never guess past them or an `inconsistent` classification. For `dimension.pi_groups`, declare each variable with a unit expression; it returns one exact primitive-integer basis, not a unique named physical quantity, so preserve its non-uniqueness warning.
- For financial work, pass decimal text and preserve the returned period, timing, IRR-bracket, and rounding conventions. The runtime is a calculator, not a transaction quote.
- Follow the error object's `retryable`, `phase`, `retryAfterMs`, and `suggestedAction` fields; do not infer retry policy from message text. For `E_INPUT`, `E_DOMAIN`, or `E_UNIT`, correct the mathematical input or ask for the missing choice. Do not replace the calculation with a mental estimate.
- For `E_TIMEOUT`, `E_MEMORY`, or `E_OUTPUT_LIMIT`, split or reduce a genuinely oversized request, select one result representation, or explain the execution limit. Do not repeat the identical call.
- For retryable `E_OVERLOADED`, `E_UNAVAILABLE`, or `E_RUNTIME`, wait for `retryAfterMs` when present and retry at most once. If the retry fails, report the stable error instead of looping or silently switching to mental arithmetic.

## Present the result

- Prefer `exact` when the user needs a symbolic answer. Include `approx` only when it helps or when the user requested a decimal value.
- Never describe `approx` as exact. Preserve the returned precision, unit, solution branch, and warnings when they affect use of the answer.
- Preserve explicit operation actions, linear-system classification, matrix pivots or basis vectors, and series order when they affect interpretation.
- Preserve returned statistical methods and degrees of freedom when they affect interpretation. For exact decimal statistics or unit conversion, send decimal inputs as strings rather than JSON floating-point numbers.
- Preserve distribution support, inferential assumptions, sample size, and approximate provenance for probability and statistics results.
- For `measurement.propagate`, convert every input into one coherent numerical unit system before calling. Preserve the distinction between combined standard and coverage-factor-expanded uncertainty, the correlation model, and any nonlinear first-order warning; exact fields are exact only inside the stated linearized covariance model.
- Explain the mathematical setup briefly when it helps the user verify that the right problem was computed; keep engine names, worker limits, schemas, and protocol fields out of the ordinary answer.
- For a conceptual explanation that needs no calculation, answer normally without calling the tools.

## Check the result

- A successful tool response proves that the declared operation ran; it does not prove that the Agent translated the user's problem correctly.
- Stop after the first successful call for an ordinary calculation. A rejected malformed call may be corrected once, but do not repeat an identical successful call as validation; it exercises the same implementation with the same inputs and is not independent evidence.
- Before presenting a consequential result, check the cheapest relevant invariant: units and dimensions, sign and plausible magnitude, probability support, matrix residual or condition, root residual and omission risk, statistical method and sample size, or financial period and timing convention.
- Prefer diagnostics already returned by that call. Make an additional call only when a consequential result needs a materially different operation or independent invariant that the first response does not provide.
- Preserve `status: uncertain`, warnings, residuals, error bounds, and stability diagnostics. Do not turn them into an unqualified answer.
- If the result conflicts with an invariant, do not rationalize it. Correct the declared inputs or operation and call again; if the conflict remains, report that the calculation could not be validated.
- For high-consequence decisions, treat Math Anchor as calculation support rather than the sole authority and use an independent review or domain source appropriate to the decision.
