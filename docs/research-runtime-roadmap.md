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

The broader research-adoption goal remains open until a real external math
Agent integration and a proof-kernel bridge are run against pinned external
versions. Paid model-backed A/B runs, publication, registry pushes, release
tags, and claims of adoption remain owner-authorized external stages.

## Current state

- Baseline: `main` at `da29d8b`, initially clean and equal to `origin/main`.
- Initial product contract: Math Anchor 0.4, 44 operation ids, four public MCP
  tools, compact one-call execution, strict per-operation validation, isolated
  worker bounds, and separate exact/approximate result fields.
- Current working-tree contract: 45 operation ids; a runtime-owned assurance
  envelope; one bounded rational polynomial certificate plus an independent
  standard-library checker; verified wheel/source-archive construction; and
  Linux x86_64/arm64 plus OCI CI definitions. The four-tool boundary and human
  calculator surface remain unchanged.
- Current strengths: broad deterministic and diagnostic mathematics, rigorous
  interval branch-and-bound, symbolic dimension checking/inference/Pi groups,
  packaged Plugin/runtime, macOS calculator, and bounded Agent/load evaluation
  assets.
- Remaining research gaps: no proof-kernel-accepted artifact, no current
  external math-Agent A/B result, and no claim of scientific adoption. The OCI
  definition is CI-runnable, but local image build/run remains blocked until a
  container daemon is available.
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
- Do not commit, push, tag, publish, install globally, or spend model budget.

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

## Latest local observations (2026-08-31)

- `./script/check_all.sh`: PASS against the rebuilt arm64 Plugin runtime; 844
  Python tests passed and one explicitly conditional test was skipped, followed
  by source safety, four Swift tests, Swift store
  checks/build, live packaged MCP, a 1,000-call load profile, Plugin validation,
  and release hygiene.
- `./script/check_headless.sh`: PASS against the latest source; 841 Python
  tests passed and four platform/carrier-conditional tests were skipped,
  followed by source safety, source-mode MCP, a 1,000-call load profile, and
  verified wheel/source-archive construction plus fresh-target wheel smoke.
- Packaged MCP: PASS with 45 operation ids; `math.run` input 1,807 bytes,
  output 1,425 bytes, and the complete four-tool listing 8,169 bytes. The live
  sequence includes certificate generation, independent recomputation,
  cancellation recovery, and negative schema/domain cases.
- Latest load receipt: PASS at
  `build/load-checks/load-check-20260831T143306Z.json`; serial p95 was 14.193 ms,
  and child-process, thread, and file-descriptor deltas were zero after cleanup.
- Wheel/source archive build and fresh-target wheel smoke: PASS. The current
  arm64 `.app` was assembled and its embedded runtime, architecture, legal
  materials, and manifest passed release hygiene.
- Local OCI build/run: BLOCKED because no Docker daemon socket is available.
  The digest-pinned, non-root definition and x86_64/arm64 Linux workflow are
  source-checked, but only an actual CI run can establish Linux/container
  runtime PASS.
- Business/experience acceptance: Pending. No human UI changed, no installed
  Plugin was replaced, and no commit, push, tag, publication, or paid model run
  occurred.
