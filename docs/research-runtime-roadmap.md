# Math Anchor evidence-runtime roadmap

## Product direction

Math Anchor anchors finite mathematical claims to executable, replayable, and
scope-limited checks. Its Agent product is a small mathematical obligation and
receipt runtime that a Host or harness can embed outside the model's main
context. It is not primarily a larger operation catalogue, a mathematical
reasoning model, a theorem planner, a universal CAS, or a replacement for a
formal proof kernel.

The strategic division is:

- the Host owns trigger policy, provider discovery and routing, artifact
  storage, permissions, lifecycle, caching, retries, and presentation to the
  Agent;
- Math Anchor owns the bounded obligation shapes it understands, deterministic
  provider execution, assurance and claim scope, replay digests, conformance
  cases, and explicit unsupported boundaries;
- a domain pack may compile domain material into core obligations and disclose
  what it did not translate, but it must not turn one research route into the
  core product model.

The macOS calculator remains a compact human utility over the same calculation
core. Obligation graphs, receipts, provider metadata, and Agent routing remain
out of its UI.

## Current productized slice

Current development source provides a versioned local contract at
`math-anchor.obligation-set.v0.1` through the Python library and the
`check-obligations` CLI command. This route deliberately does not add a fifth
MCP tool.

The first slice provides:

- a bounded set of up to 32 obligations and 16 shared assumption sets;
- hash binding of caller-declared assumptions without pretending to interpret
  or prove those assumptions;
- dependency-ordered execution where an unchecked dependency prevents the
  downstream provider from running; dependencies do not substitute result data
  into another claim;
- the terminal states `checked`, `falsified`, `unknown`, and `unsupported`;
- the assurance vocabulary `formal_kernel_checked`, `exact_symbolic`,
  `rigorous_interval`, `numerical`, and `heuristic`, with `null` used when no
  provider established a result;
- exact claim, assumption, provider-result, outcome, and receipt digests;
- a full deterministic receipt for replay plus a default `failures_only`
  feedback projection;
- `--quiet-success`, which lets a checkpoint write the full receipt locally and
  emit no main-context output when every obligation is checked;
- replay classification that distinguishes an exact match, runtime-only drift,
  and mathematical outcome drift.

The registered v0.1 obligation providers are rational polynomial identity,
expression equivalence under an explicit domain and definedness policy,
symbolic dimensional consistency, and the bounded local almost-complex check.
The current 46-operation registry remains available behind the four established
MCP tools as a compatibility provider surface; operation count is no longer the
strategic progress metric.

`geometry.almost_complex.local_check` is retained as a narrow provider. It
checks rational-polynomial `J^2 = -I` and coordinate-basis Nijenhuis components
in one supplied chart. It is not an atlas verifier and does not establish a
global complex structure, including on the six-sphere. A future S6 audit pack
may compile selected finite obligations into the core contract, but it is a
case study rather than the product kernel.

## Claim and receipt boundary

A receipt records what current code executed and binds its exact request,
provider result, runtime versions, status, assurance level, scope, and stated
limitations. It is not durable authority for the wider theorem and does not
validate natural-language-to-formula translation, coverage completeness,
external theorem use, or the truth of caller-declared assumptions.

`exact_symbolic` means the registered provider established the stated finite
claim over its declared symbolic domain. A separately checked polynomial
certificate still does not become `formal_kernel_checked`; that level may be
used only after the bound statement is accepted by a named formal kernel.
`rigorous_interval` is reserved for a genuine enclosure contract, not a
diagnostic error estimate. `numerical` and `heuristic` remain weaker outcomes
and cannot be promoted because they happen to look exact.

Unknown obligation kinds return `unsupported` without interpreting the claim
object. Provider timeouts, resource failures, certificate rejection, and
inconclusive symbolic work return `unknown`. A dependency on anything other
than `checked` is also `unknown` and records the blocking obligation ids.

## Current validation ladder

Use the narrow obligation tests and conformance corpus during iteration, then
close source changes with:

1. `.venv/bin/python script/check_obligations.py` for the current injected
   sign error, strict-definedness trap, unit mismatch, unsupported-domain, and
   dependency-blocking cases;
2. `./script/check_all.sh` for Python and Swift regressions, source safety,
   packaged MCP behavior, load/recovery, Plugin validation, and release
   hygiene;
3. `./script/check_headless.sh` for wheel and source-archive construction plus
   a fresh-target obligation-runtime smoke;
4. `./script/check_lean_bridge.sh` only for the separately pinned polynomial
   kernel route;
5. `./script/build_and_run.sh --verify` when the macOS carrier is refreshed.

Development checks can veto broken implementation. Runtime Agent flow, runtime
human flow, distribution, and business/experience acceptance remain separate
lanes.

## Next construction boundaries

The next Agent-owned construction work is ordered by dependency, not by adding
mathematical domains:

1. measure the current no-tool, model-visible MCP, explicit obligation, and
   harness-triggered paths with schema, routing, request, result, and repair
   cost reported separately;
2. integrate the local CLI as a real Host or harness checkpoint with receipt
   artifacts kept outside the model context and only actionable failures fed
   back;
3. add typed result-to-result bindings only from repeated workflows that need
   them; dependency order alone must not be described as data propagation;
4. add a provider or certificate family only when at least three real repeated
   workflows share one bounded meaning and the conformance corpus can falsify
   it;
5. after the kernel and checkpoint route are stable, build a thin research
   audit pack from selected source material and publish a coverage table that
   keeps external theorem steps explicitly unchecked.

Promotion to a high-frequency or research-utility claim requires current
comparative results, not a green provider suite. The working stop conditions
remain: detect at least 80% of supported seeded errors, materially reduce
accepted mathematical errors against the matched no-tool route, keep main
context growth near or below 10%, keep successful checks silent or compact,
obtain one external harness integration, and observe two non-author users
repeating a real workflow. External integration, adoption, and owner value
acceptance are not current source facts. If a bounded campaign produces only
more operations without those signals, the correct state is maintenance rather
than further domain expansion.
