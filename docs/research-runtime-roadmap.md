# Math Anchor research-runtime roadmap

## Product direction

Math Anchor is a small mathematical execution and evidence runtime for Agents.
It should replace repeated model calculation with bounded, reproducible calls,
explicit numerical limits, independently checkable certificates where useful,
and inputs suitable for an external proof kernel.

It is not a mathematical reasoning model, theorem planner, universal CAS, or a
replacement for Lean. The human calculator and Agent interface continue to use
one calculation core while keeping Agent discovery and assurance metadata out
of the human UI.

## Current product slice

- Version 0.5 exposes 45 registered operations through exactly four public MCP
  tools: `math.search`, `math.describe`, `math.run`, and `math.batch`.
- Results keep exact and approximate values distinct and include a bounded
  runtime-owned assurance record with claim scope, assumptions, backend
  provenance, and certificate or kernel-check status.
- `certificate.polynomial_identity` produces one bounded rational-polynomial
  certificate. A separate standard-library checker recomputes its statement and
  coefficients without calling the producer.
- The optional production Lean bridge and independent reference consumer use
  pinned Lean 4.33.1 and exact Mathlib revision
  `0df444a360eaa60ab8c11dca51a86af692955474`. They are verification lanes, not
  additional public tools or proof of a user's wider informal claim.
- The Python headless runtime, Plugin runtime, and macOS app are separate
  carriers built from the same core. Carrier parity must be re-established
  after every source change.

## Claim boundary

`deterministic` means reproducible bounded computation, not proof.
`diagnostic` adds quality information but is not a rigorous enclosure.
`certified` requires a bounded artifact accepted by an independent checker.
`kernel_checked` may appear only after an external formal kernel accepts the
bound artifact. A digest authenticates bytes; it does not establish
mathematical truth.

Direct structured invocation is the supported Agent contract. Natural-language
tool selection, automatic adoption, quality gain, and research utility are
separate empirical claims. The current public-task evaluation observed some
successful tool adoption, one corrupted-certificate error prevented by the
explicit route, and one exact two-stage result chain with all declared bindings
satisfied. Natural installed routing remained incomplete and context cost was
material; see `docs/agent-evaluation.md`. No broad adoption or utility claim is
warranted.

## Validation ladder

Run the narrow affected checks during development, then close a release with:

1. `./script/check_all.sh` for Python and Swift regressions, source safety,
   packaged MCP behavior, load/recovery, Plugin validation, and release hygiene.
2. `./script/check_headless.sh` for wheel/source-archive construction and a
   fresh-target headless smoke.
3. `./script/check_lean_bridge.sh` for the complete pinned kernel route, plus
   `script/lean_reference_check.py` for the independent consumer boundary.
4. `codex plugin marketplace add .` and `./script/install_plugin.sh` for an
   installed-copy byte comparison, four-tool transport check, and fresh-host
   Skill-path observation.
5. A real launch and task flow for the macOS carrier when it is intended to be
   refreshed. A successful build alone does not establish visual or business
   acceptance.

Linux/container status remains conditional on the owning CI run or an actual
local daemon; source inspection cannot promote that runtime lane to PASS.

## Next product-strengthening sequence

1. Preserve the now-observed certificate-decision and determinant-to-remainder
   procedures as the first explicit external workflow boundary. Expand repeats
   only after every task in the selected suite conforms and binds its result.
2. Integrate provider-owned Procedure selection through a public Agent Host
   extension point once that owning tree is stable. More Skill wording is not
   a substitute for host-enforced routing; a correct treatment with no target
   call is not adoption.
3. Reduce cold context and operation-selection cost before a larger model run.
   A target call with no quality gain is not utility.
4. Add another certificate family only when the external workflow repeatedly
   needs it. Keep each family bounded, independently recomputable, and
   separately kernel-checked.
5. Keep the four-tool boundary and registry-first capability model unless
   current installed-host measurements demonstrate a concrete reason to change
   it.
6. Treat signed/notarized macOS distribution, hosted marketplace listing, and
   owner visual/business acceptance as separate release decisions from public
   source and local Plugin installation.
