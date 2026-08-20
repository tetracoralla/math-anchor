# Agent mathematical capability expansion

## Current objective

Extend the existing four-tool Agent surface through the operation registry. The
human calculator remains unchanged. The work is complete only when the current
runtime can execute and validate all of these operation families:

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

## Shared model

- The target user is an Agent that has already translated a human request into
  a mathematical task and should normally finish in one `math.run` call.
- Discovery, direct execution, ordered batch execution, and the packaged plugin
  remain the related flows. No additional public MCP tool is introduced.
- Every operation is one registry entry with a bounded, discriminated input
  schema, a safe handler, an internally enforced strict result schema,
  examples, and multilingual discovery terms. The MCP listing advertises only
  the common result envelope so Agents do not pay for the entire result union
  before each call.
- Symbolic expressions continue through the explicit AST translator. Unit
  expressions and symbolic dimension expressions use separate smaller AST
  whitelists because a name means a unit in the former and a declared symbol
  in the latter. Model-generated Python is never executed.
- Exact values, decimal/binary approximations, error bounds, residuals, and
  method-dependent conclusions remain distinct fields.

## Sequencing and acceptance

The verification and quantity layer lands first because later financial and
statistical work depends on trustworthy comparison, provenance, and units. The
numeric layer then adds explicit accuracy contracts before finance and
statistics expose approximation-sensitive results.

Acceptance is separated into:

- development regression: schema validation, negative parser and domain cases,
  numerical edge cases, full Python checks, Swift checks, and packaging checks;
- Agent/runtime flow: direct calls plus isolated `math.run` and ordered batch
  calls from the packaged four-tool surface;
- human experience: the existing macOS calculator must build and launch without
  showing Agent capability or changing its interaction model.

No historical screenshot, report, or aggregate green result substitutes for a
fresh execution of these lanes against the current source.
