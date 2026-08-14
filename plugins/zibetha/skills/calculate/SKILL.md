---
name: calculate
description: Use Zibetha's deterministic mathematical tools for arithmetic, exact or high-precision evaluation, equivalence and solution verification, algebra, calculus, number theory, combinatorics, exact or stability-aware linear algebra, financial math, probability, statistics, and physical quantities. Trigger when a user asks for a computed result whose correctness or precision matters, when an Agent would otherwise simulate a standard algorithm, or when exact and approximate values must remain distinct.
---

# Calculate

Use the mathematical runtime for the calculation. Let reasoning translate the user's request into mathematics; do not spend model reasoning simulating arithmetic or a standard scientific algorithm.

## Select the operation

- For an ordinary supported request, call `math.run` directly. Its executable schema contains the stable operation ids and each operation's current arguments.
- Call `math.search` only when the mathematical operation is genuinely unfamiliar or ambiguous. Search using the user's task language.
- Call `math.describe` only for the selected unfamiliar operation when its contract still needs inspection.

## Execute

- Call `math.run` for one calculation.
- Call `math.batch` for 2 to 32 independent calculations when they can run without consuming one another's output. Preserve input order when matching results back to the request.
- For large matrices or other bulky results, prefer `resultMode: "exact"` or `resultMode: "approx"` when only one representation is needed. Increase `maxOutputBytes` only when the additional content is genuinely useful. `math.batch` keeps a compact generic item contract; use `math.describe` only if an item's operation schema is unfamiliar.
- Supply all business assumptions explicitly as expressions, variables, bounds, units, or data. Do not invent a missing unit, equation, time period, statistical convention, root bracket, or variable meaning when it changes the answer.
- For matrix solving, rank, RREF, and basis operations, send exact integers or rational text such as `1/10`. Do not silently turn approximate decimal matrices into exact structural claims.
- Use `matrix.solve_approximate` for decimal matrices only when the tolerance is meaningful to the request; preserve its condition, residual, backward-error, and stability fields.
- Use `numeric.integrate` when a symbolic definite integral is unavailable or a numerical interval is requested. Preserve that its `resultInterval` is estimate-based whenever `errorBoundCertified` is false. A result with `status: uncertain` met only the local error estimate; do not call it converged. Supply `breakpoints` only when they identify every material discontinuity or localized feature, or `featureScale` only when the user can bound the minimum material feature width.
- Use `expression.equivalent` instead of comparing formatted strings. Keep its default strict definedness policy unless the user explicitly means equality only where both expressions are defined.
- Use `solution.verify` to check supplied roots or assignments. Do not describe candidates as exhaustive unless `omissionRisk` is `none_proven`.
- Write unit arithmetic with explicit multiplication, such as `80 * kg * 9.81 * m / s^2`, and use `toUnit` when a named result unit matters.
- For financial work, pass decimal text and preserve the returned period, timing, IRR-bracket, and rounding conventions. The runtime is a calculator, not a transaction quote.
- If the runtime returns `E_INPUT`, `E_DOMAIN`, or `E_UNIT`, correct the mathematical input or ask for the missing choice. Do not replace the calculation with a mental estimate.
- If it returns `E_TIMEOUT` or `E_MEMORY`, reduce a genuinely oversized request or explain the execution limit. Do not claim a result.

## Present the result

- Prefer `exact` when the user needs a symbolic answer. Include `approx` only when it helps or when the user requested a decimal value.
- Never describe `approx` as exact. Preserve the returned precision, unit, solution branch, and warnings when they affect use of the answer.
- Preserve explicit operation actions, linear-system classification, matrix pivots or basis vectors, and series order when they affect interpretation.
- Preserve returned statistical methods and degrees of freedom when they affect interpretation. For exact decimal statistics or unit conversion, send decimal inputs as strings rather than JSON floating-point numbers.
- Preserve distribution support, inferential assumptions, sample size, and approximate provenance for probability and statistics results.
- Explain the mathematical setup briefly when it helps the user verify that the right problem was computed; keep engine names, worker limits, schemas, and protocol fields out of the ordinary answer.
- For a conceptual explanation that needs no calculation, answer normally without calling the tools.
