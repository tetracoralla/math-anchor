# Math Anchor research-runtime roadmap

## Objective and finish condition

Math Anchor's north-star is a small, dependable mathematical runtime that lets
research and scientific Agents replace repeated model calculation with
reproducible computation, explicit diagnostic limits, independently checkable
certificates, and inputs suitable for a formal proof kernel.

The current implementation campaign finishes its first productized slice when:

1. every successful operation carries one compact, versioned assurance
   contract that states the claim class, scope, assumptions, backend
   provenance, and whether an independent certificate or kernel check exists;
2. at least one high-value mathematical claim produces a bounded certificate
   that a separately implemented checker validates without calling the
   certificate-producing operation;
3. the Python runtime has a verified headless build/install path, Linux CI,
   and a runnable OCI definition without depending on the macOS application;
4. the stable public MCP surface remains exactly `math.search`,
   `math.describe`, `math.run`, and `math.batch`, and the human calculator does
   not expose research or Agent metadata;
5. current development, MCP/CLI, certificate, headless distribution, packaged
   runtime, and macOS build checks are reported separately from owner
   business/experience acceptance.

The broader research-adoption goal remains open after the first real external
math-Agent smokes and proof-kernel bridge. The fixed public task did not trigger
tool adoption, and the installed-Plugin smoke routed only one of two required
opportunities. Neither bounded observation establishes utility or adoption.

## Current state

- Working baseline: the reconciliation branch based on `22fe2f5`, incorporating
  the backup-only human/runtime fixes at `f7713f0` and the preserved research
  reference work at `e400cc3`.
- Current product contract: Math Anchor 0.5.0, 45 operation ids, exactly four
  public MCP tools, compact one-call execution, strict per-operation validation,
  bounded transport and workers, separate exact/approximate result fields, and
  a versioned runtime-owned assurance envelope with selected-backend provenance.
- The production Lean bridge and an independent reference consumer both check
  the bounded polynomial certificate with pinned Lean 4.33.1 and Mathlib commit
  `0df444a360eaa60ab8c11dca51a86af692955474` for both the `n = 4` bridge and
  `n = 18` promotion fixture. The reference route is a boundary test, not a
  second public capability, and neither fixture proves the full Putnam theorem.
- Current Agent smoke: paired low-reasoning Codex runs for Terra and Luna used
  the public Putnam 1976 A2 `n = 18` fixed instance. Both comparisons were
  infrastructure-valid and all answers were correct, but neither treatment
  invoked Math Anchor, so observed quality delta and adoption were zero.
- Remaining research gaps: a genuinely discriminating public-problem task,
  observed target adoption, a multi-task executable-oracle evaluation, an
  external consumer outside this repository, and scientific adoption.
- Environment repair in this campaign: a File Provider copy preserved the
  hidden flag on editable-install `.pth` files, so Python ignored the current
  package. Bootstrap now uses a relocatable non-editable project install and
  runtime packaging refreshes it before use.
- The registry and runtime now load operation engines on first use. Pure
  Python routes do not import SymPy, NumPy, Pint, or mpmath; high-frequency
  integer/combinatoric output uses a Python/Decimal formatter without changing
  the interpreter's global integer-string safety limit. Result validation
  dispatches to the selected kind/action contract while retaining the complete
  union as the fail-closed fallback.
- Request graphs are bounded before worker admission (8 MiB / 250,000 nodes /
  depth 64 per run; 16 MiB / 500,000 nodes per batch). Worker and app JSON-lines
  reads are bounded, and the MCP stdio carrier rejects messages above 17 MiB
  before SDK JSON parsing while preserving alignment for the next message.

## Boundaries

- Reuse the existing operation registry, result contracts, safe AST
  translators, sandbox, CLI/MCP adapters, packaging scripts, and thin Plugin
  Skill. Do not add a second operation catalogue or more public MCP tools.
- `deterministic` means reproducible bounded computation, not proof.
  `diagnostic` adds quality information but is not a rigorous enclosure.
  `certified` requires a bounded artifact accepted by an independent checker.
  `kernel_checked` may appear only after an external formal kernel actually
  accepts the bound artifact.
- A generated certificate with `checkedBy: null` is checkable but not yet
  externally checked. A checksum authenticates bytes, not mathematical truth.
- Keep the default result envelope compact enough for high-frequency ordinary
  callers. Heavy artifacts stay bounded and opt-in through a selected
  operation rather than appearing in every tool schema.
- Do not change the human UI in this campaign.
- The owner authorized this reconciliation campaign to commit, push, refresh
  the managed installation, and run bounded Terra/Luna smokes. Model-backed
  runs still require the exact planned-call confirmation and stop before a
  larger estimate unless the treatment actually adopts Math Anchor.

## Validation ladder and continuation anchor

- Development: focused negative tests, full Python/Swift suite, source safety,
  generated contract size, and `./script/check_all.sh`.
- Agent runtime: live four-tool MCP protocol plus CLI direct and batch calls,
  including the certificate operation and independent verification command.
- Headless distribution: build wheel/source archive, install the wheel through
  an isolated target, run a structured call, build/run the OCI image in Linux
  CI, and record local OCI verification as blocked when no daemon is available.
- Packaged carriers: rebuild the Plugin runtime and `dist/Math Anchor.app`, then
  probe the embedded runtime rather than trusting source tests.
- Business/experience: pending owner acceptance; this campaign does not modify
  the calculator UI.

Changed files and latest results are recoverable from `git diff --name-only`,
`git diff --stat`, and this document. The next executable action after any
interruption is the first incomplete item in the finish condition above,
followed by the affected rung of the validation ladder.

## Latest local observations (2026-09-01)

- Lean reference consumer: PASS for the tracked Putnam 1976 A2 `n = 4` and
  `n = 18` fixtures. Certificates were independently recomputed before the
  generated rational equality was accepted by Lean 4.33.1 plus pinned Mathlib;
  false identities, recomputed-digest coefficient tampering, unsupported AST
  syntax, and `sorryAx` output are rejected.
- Direct Agent research smoke: PASS for comparison integrity and answer
  correctness in one Terra pair and one Luna pair; FAIL for tool adoption in
  both. Each treatment observed the target capability as available but made
  zero target calls. These development reports carry `no-utility-claim`.
- Current backup-directory full regression: BLOCKED by macOS File Provider,
  not by an assertion failure. Source layout passed, the project `.venv` and
  wheel rebuilt, then runtime-manifest verification slept at 0% CPU while
  reading a `dataless` packaged metadata file. Two full pytest attempts also
  slept during collection on `dataless` source files even with a hydrated
  external interpreter, disabled bytecode/cache writes, and `/private/tmp`
  test state. The first inventory found 151 such source/test/script files. A
  later Finder download made representative files immediately readable but a
  fresh full pytest collection still slept inside the kernel `read()` path,
  so the carrier remains blocked. Sixteen focused tests covering the changed
  Lean bridge and Agent-evaluation assets passed. Full Python, Swift,
  packaged-runtime, and load results below remain the previous 2026-08-31
  observations and are not promoted to current post-change PASS.

- `./script/check_all.sh`: PASS against the rebuilt arm64 Plugin runtime; 868
  Python tests passed and one explicitly conditional test was skipped, followed
  by source safety, four Swift tests, Swift store checks/build, live packaged
  MCP, a 1,000-call load profile, Plugin validation, and release hygiene.
- `./script/check_headless.sh`: PASS against the latest source; 852 Python
  tests passed and four platform/carrier-conditional tests were skipped,
  followed by source safety, source-mode MCP, a 1,000-call load profile, and
  verified wheel/source-archive construction plus fresh-target wheel smoke.
- Packaged MCP: PASS with 45 operation ids; `math.run` input 1,807 bytes,
  output 1,470 bytes, and the complete four-tool listing 8,214 bytes. The live
  sequence includes assurance provenance, certificate generation, independent
  recomputation, cancellation recovery, and negative schema/domain cases.
- Same-checkout before/after load comparison against `a5c4f30`: serial p50
  improved from 3.805 ms to 0.557 ms, serial p95 from 13.920 ms to 9.198 ms,
  concurrent-warm p50 from 7.341 ms to 2.365 ms, and average worker startup
  from 192.471 ms to 60.655 ms. Both runs used the same 1,000-call, 13-case,
  concurrency-8 profile and passed cancellation/crash recovery and cleanup.
- Corrected sustained-load receipt:
  `build/load-checks/optimization/load-check-20260831T182938Z.json`. It passed
  10,000 serial calls plus 10 seconds at concurrency 8, completing 19,027
  sustained calls at 1,889.65 calls/s with p50 2.387 ms, p95 12.736 ms, p99
  18.208 ms, zero child/thread/file-descriptor residue, and 1.69 MiB parent RSS
  growth. The harness no longer retains every result payload; the earlier
  75.7 MiB apparent growth was measurement retention, not runtime telemetry.
- The pinned Lean bridge: PASS. The standard-library checker accepted the
  certificate first, then Lean 4.33.1 and the pinned Mathlib dependency graph
  accepted the generated theorem. Toolchain and Mathlib caches remain outside
  the ordinary Plugin/runtime artifact.
- Isolated Plugin preflight: PASS for the 0.5.0 package with 203 identical
  regular files, Skill identity, MCP executable resolved inside the
  installer-reported root, and a 13,207-byte carrier prompt. The main Skill
  body fell from 5,936 to 5,242 bytes. The managed Agent Host installation
  remains the healthy existing 0.4 component and was not replaced.
- Zero-model direct-host smoke: 13/13 PASS; median cold latency was 137 ms and
  mean latency 210.77 ms. No model cost field was available or inferred.
- Same-machine benchmark receipt:
  `build/benchmarks/benchmark-20260831T182525Z.json`. Versus the committed
  baseline, source expression cold-start p50 moved from 280.0 to 183.8 ms,
  packaged MCP first result from 627.6 to 402.2 ms, and packaged app first
  result from 242.4 to 190.9 ms; warm MCP round trip was 5.0 ms and the tool
  listing remained 8,214 bytes. Engine-specific inner cold p50s were 41.1 ms
  (machine integer), 40.8 ms (combinatorics), 138.5 ms (SymPy expression),
  162.0 ms (NumPy linear algebra), and 296.2 ms (Pint units).
- The bounded installed-Plugin Agent smoke was comparison-valid and both
  conditions solved 4/4 tasks, but treatment reached Math Anchor on only one of
  two required opportunities. Quality delta was zero; paired token delta was
  +16,210 total and paired mean latency delta +915.75 ms. This is a routing and
  cost finding, not an adoption or utility claim, so the 180-run estimate was
  not started.
- Wheel/source archive build and fresh-target wheel smoke: PASS. The active
  clone's arm64 development `.app` can be assembled with `--package`; the
  already-running backup application was deliberately left untouched.
- Local OCI build/run: BLOCKED because no Docker daemon socket is available.
  The digest-pinned, non-root definition and x86_64/arm64 Linux workflow are
  source-checked, but only an actual CI run can establish Linux/container
  runtime PASS.
- Business/experience acceptance: Pending. No human UI changed. No managed
  Plugin was replaced, and no commit, push, tag, registry publication, or
  public release occurred.

## Next product-strengthening sequence

1. Integrate the explicit route into one real external mathematics or physics
   Agent workflow and measure task-level error prevention, retries, latency,
   and context cost. Internal arithmetic tasks alone cannot establish adoption.
2. Add the next certificate vertical only from that workflow's repeated need,
   keeping each theorem family bounded, independently recomputable, and
   separately kernel-checked. Do not turn the four-tool runtime into a theorem
   planner or universal CAS facade.
3. Run the existing Linux/container matrix in its owning CI environment; keep
   local container status BLOCKED until a real daemon run exists.
4. Re-run the bounded eight-call installed routing smoke only after a carrier
   or routing change is expected to fix the remaining fixed-width miss; do not
   spend 180 model calls without that signal.
5. Seek owner business/experience acceptance and release authorization only
   after the current uncommitted diff and the external-workflow result are
   reviewed.
