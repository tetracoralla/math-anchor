# Agent mathematical capability expansion

## Status

Current-source design record: every family listed below is implemented,
reachable through the four-tool Agent surface, and covered by the operation
registry, generated schemas, and current packaged-runtime checks. This is a
development-state claim, not a signed-release claim. The human calculator keeps
its focused interaction model while its existing Convert picker gains the
additional curated physical categories listed below.

This file is now an inventory of compatibility providers, not the product
roadmap. New operation families are frozen unless repeated current workflows
and a falsifiable conformance case establish the need. The strategic Agent
surface is the provider-native obligation and receipt runtime documented in
`obligation-runtime.md`; operation count is not a completion or value measure.

1. semantic expression equivalence with an explicit domain and definedness
   check;
2. candidate solution verification with per-constraint residuals and an honest
   statement of untested solution coverage;
3. arithmetic over unit-bearing expressions with dimensional validation;
4. financial calculations with explicit nominal/effective rate, period,
   cash-flow, root-bracket, and rounding conventions;
5. bracketed numerical roots, adaptive numerical integration, and approximate
   linear systems with tolerances, error estimates, residuals, condition
   estimates, and stability warnings;
6. common probability distributions and inferential statistics with methods,
   sample constraints, and numeric provenance.
7. symbolic dimensional checking, exact constraint-based inference, and exact
   Buckingham Pi bases with localized conflicts, honest classification, and
   explicit basis non-uniqueness.
8. fixed-width programmer integers, explicit bit operations, decimal
   quantization, and truncating/floor/Euclidean integer division;
9. stable unit discovery plus data quantity/rate, frequency, force,
   acceleration, torque, and density conversions, with civil month/year
   averages rejected unless explicitly selected;
10. exact vector and matrix operations separated from binary64 least squares,
    QR, SVD, and pseudoinverse diagnostics;
11. Beta, Gamma, and lognormal distributions; paired and two-sample t tests;
    chi-square goodness-of-fit; and first-order covariance propagation of
    measurement uncertainty.
12. fixed-width checked/wrapping/saturating machine arithmetic, width-bound
    bit-field and alignment operations, and IEEE-754 binary32/binary64
    inspection and comparison.
13. bounded rational polynomial-identity certificates with a separately
    implemented standard-library checker that recomputes the statement and
    coefficients without trusting the producer.
14. bounded local almost-complex candidate checks over rational-polynomial
    coordinate components, with exact `J^2 = -I` and Nijenhuis results plus
    explicit unverified global obligations.

## Shared model

- The target integration is an Agent Host or harness that has translated a
  larger workflow into bounded mathematical obligations, keeps the full
  receipt outside the main context, and returns only actionable failures. A
  compatibility caller that already knows one operation should still finish in
  one `math.run` call.
- Discovery, direct execution, ordered batch execution, and the packaged plugin
  remain the related flows. No additional public MCP tool is introduced.
- Every operation is one registry entry with a bounded, discriminated input
  schema, a safe handler, an internally enforced strict result schema,
  examples, and multilingual discovery terms. The always-listed `math.run`
  envelope advertises every stable id but keeps exact per-operation arguments
  in `math.describe`, so current Codex hosts preserve the typed root instead of
  compacting a large union to an opaque object.
- Symbolic expressions continue through the explicit AST translator. Unit
  expressions and symbolic dimension expressions use separate smaller AST
  whitelists because a name means a unit in the former and a declared symbol
  in the latter. Model-generated Python is never executed.
- Exact values, decimal/binary approximations, error bounds, residuals, and
  method-dependent conclusions remain distinct fields.
- Every success carries a runtime-owned assurance level, claim scope,
  assumptions, runtime/backend version provenance, and explicit certificate
  and kernel-check state. A handler cannot promote its own assurance metadata.
- The current catalog contains 46 operations, but the public surface remains
  four tools. Every listed input stays below the current Codex 4,800-byte
  compatibility regression; registry validation remains complete and closed.

## Sequencing and acceptance

The implemented provider families remain available. Further sequencing starts
with obligation-contract stability, harness integration, cost measurement, and
conformance against seeded errors. A new mathematical family comes later and
only from a demonstrated repeated obligation; a topical research problem alone
is not sufficient basis.

Acceptance is separated into:

- development regression: schema validation, negative parser and domain cases,
  numerical edge cases, full Python checks, Swift checks, and packaging checks;
- Agent/runtime flow: direct calls plus isolated `math.run` and ordered batch
  calls from the packaged four-tool surface;
- human experience: the macOS calculator must build and launch without showing
  Agent capability; its Convert picker may expose the new curated categories
  without adding a new mode or diagnostic surface.

No historical screenshot, report, or aggregate green result substitutes for a
fresh execution of these lanes against the current source.
