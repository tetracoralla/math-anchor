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

The broader research-adoption goal remains open until the runtime is exercised
inside a real external math-Agent workflow. A proof-kernel bridge and one
bounded model-backed A/B smoke now exist, but neither establishes adoption,
quality gain, or a reason to scale the experiment. Publication, registry
pushes, release tags, and claims of adoption remain owner-authorized external
stages.

## Current state

- Working baseline for this campaign: `main` at `1209653`, already two local
  commits ahead of `origin/main` at `da29d8b`; the 0.5 changes below remain
  uncommitted. The independent active clone is under `Development/tools-dev`;
  the File Provider backup and its running 0.4 application were not replaced.
- Current product contract: Math Anchor 0.5.0, 45 operation ids, exactly four
  public MCP tools, compact one-call execution, strict per-operation
  validation, isolated worker bounds, separate exact/approximate result
  fields, and a versioned runtime-owned assurance envelope with actual selected
  backend provenance.
- The first certificate vertical is complete end to end: a bounded rational
  polynomial identity certificate is recomputed by an independent
  standard-library checker, translated through a separate safe AST path, and
  accepted by pinned Lean 4.33.1 plus Mathlib before the result is labelled
  `kernel_checked`.
- Current numerical strength is bounded and explicit: deterministic and
  diagnostic operations remain broad, while `numeric.minimize` reports only an
  internal mpmath interval enclosure for its supported expression subset. It
  is not described as an external certificate or general proof.
- Remaining research gaps: no real external math-Agent integration, no
  measured scientific workflow benefit, only one narrow Lean certificate
  family, and no claim of scientific adoption. The OCI definition is
  CI-runnable, but local image build/run remains blocked until a container
  daemon is available.
- Environment repair in this campaign: a File Provider copy preserved the
  hidden flag on editable-install `.pth` files, so Python ignored the current
  package. Bootstrap now uses a relocatable non-editable project install and
  runtime packaging refreshes it before use.

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
- Do not commit, push, tag, publish, or replace the managed global installation
  without explicit owner authorization. Model-backed runs must remain bounded
  by an exact planned-call confirmation and stop when the smoke does not justify
  scaling.

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

- `./script/check_all.sh`: PASS against the rebuilt arm64 Plugin runtime; 855
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
- Latest headless load receipt: PASS at
  `build/load-checks/load-check-20260831T172426Z.json`; serial p95 was 14.806 ms,
  cancellation and worker-crash recovery succeeded, and child-process, thread,
  and file-descriptor deltas were zero after cleanup.
- The pinned Lean bridge: PASS. The standard-library checker accepted the
  certificate first, then Lean 4.33.1 and the pinned Mathlib dependency graph
  accepted the generated theorem. Toolchain and Mathlib caches remain outside
  the ordinary Plugin/runtime artifact.
- Isolated Plugin preflight: PASS for the 0.5.0 package with an exact installed
  file inventory, Skill identity, and MCP executable resolved inside the
  installer-reported root. The managed Agent Host installation remains the
  healthy existing 0.4 component and was not replaced.
- Zero-model direct-host smoke: 13/13 PASS; median cold latency was 283 ms and
  mean latency 328.15 ms. No model cost field was available or inferred.
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

1. Repair cold Agent routing and context cost before adding operation count:
   make both required smoke opportunities reach `math.run` directly, preserve
   zero irrelevant calls, and re-run only the eight-call smoke.
2. Integrate the explicit route into one real external mathematics or physics
   Agent workflow and measure task-level error prevention, retries, latency,
   and context cost. Internal arithmetic tasks alone cannot establish adoption.
3. Add the next certificate vertical only from that workflow's repeated need,
   keeping each theorem family bounded, independently recomputable, and
   separately kernel-checked. Do not turn the four-tool runtime into a theorem
   planner or universal CAS facade.
4. Run the existing Linux/container matrix in its owning CI environment; keep
   local container status BLOCKED until a real daemon run exists.
5. Seek owner business/experience acceptance and release authorization only
   after the current uncommitted diff and the external-workflow result are
   reviewed.
