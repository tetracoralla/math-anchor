# Shadow verifier (Research Epoch 2 scaffold)

This note is a research report, not a product Capability, not an overall
benefit percentage, and **not Epoch 2 completion**. Method packs are **not**
promoted. Dated research status: experimental draft **2026-09-15**. Do not
start H1.

Green harness tests are not completion of this research claim. Live B0/B1
model numbers are **not invented**. `model_arms=deferred`.

Gates **G1–G6 are targets**. Epoch 2 is not done until live four-arm model
evidence exists.

## Progressive assurance

The measured object is a **Mathematical Evidence Runtime** step, not a
calculator answer:

Claim → Certificate/Witness → Independent Verifier → Binding → Assurance → Receipt.

The macOS calculator remains a compact human utility over the same core. It
is not the center of this experiment. That is a priority, not a standing ban.

## Mandatory question

Can the **existing** obligation runtime detect seeded mathematical
corruptions (B2) and project Host shadow-checkpoint semantics (B3: quiet
success, `failures_only`, receipt outside model context, repair hook)
without a second stack, while recording B0/B1 as deferred live-model arms?

## Arms

| Arm | What it is | This smoke |
| --- | --- | --- |
| **B0** | Model-only, no mathematical provider | **deferred** (`model_arms=deferred`) |
| **B1** | Model + current MCP (`math.search` / `math.describe` / `math.run` / `math.batch`), voluntary tool use. No fifth tool. A correct answer without a target call is not adoption | **deferred** |
| **B2** | Explicit `math-anchor.obligation-set.v0.1` request, `responseMode=full` | **ran** (library) |
| **B3** | Host/harness shadow checkpoint: full receipt on disk; library quiet success **projects** zero model-context bytes when checked; `failures_only` only when action is required; seeded same-claim repair-loop hook | **ran** (library + CLI probes) |

B2/B3 call `math_anchor.obligations.check_obligation_set`. They are not a
second mathematical stack.

## Independence (producer vs checker)

- Polynomial identity: the **stdlib** checker
  (`math-anchor-stdlib-polynomial-checker`) recomputes coefficients without
  importing the SymPy producer. A valid certificate for a **different**
  statement returns `unknown` / `certificate_rejected`, not `checked`.
- Expression equivalence and dimension consistency **reuse the same
  registered providers** as the MCP catalog. They are not a second checker.
- B3 “independence” is Host-triggered execution plus **context isolation**
  (receipt outside the model context), not a separately implemented verifier
  for every kind.
- A receipt does not prove surrounding prose, coverage completeness, or
  caller assumptions.

## Gates G1–G6 (targets)

| Gate | Name | Target | This smoke |
| --- | --- | --- | --- |
| **G1** | detection | ≥80% of **supported** seeded errors | B2/B3 corpus measured; **not** Epoch 2 G1 (no live models) |
| **G2** | accepted-error drop | material reduction vs matched B0 | **deferred** (needs live B0) |
| **G3** | false reject | valid controls stay checked | B2/B3 controls measured; **not** live-model G3 |
| **G4** | context | ≤10% main-context growth; **0** returned content on successful checkpoints | B3 library 0 bytes is a **wrapper projection**; product evidence is CLI `--quiet-success` empty stdout; **≤10% vs B0 deferred** |
| **G5** | repair | after `failures_only`, repair can reach checked / quiet success | same-claim seeded hook (sign-flip) measured; dimension-mismatch resubmit is a **different valid claim**; **not** live-model repair; **G5 unmet** |
| **G6** | strong + weak models | same protocol on a stronger and a weaker model | **deferred** |

Silence on success is **zero returned content**, not proof the Agent used
the receipt. B3 library `modelContextBytes=0` on checked cells is a
**wrapper projection** (`quiet_success` and `feedback.status=="checked"`
zero the count even though the runtime `failures_only` envelope is
non-empty). Product evidence is the CLI probe: `check-obligations
--quiet-success` on a valid identity emits empty stdout. Seeded repair
probes are **same-claim pre-authored corrections** only, not evidence
that a model repaired from feedback. Submitting a different valid claim
is not a repair of the original error. G5 remains unmet.

## Commands and artifact paths

Pre-registered protocol (frozen before the run):

`research/shadow_verifier_eval/protocol.json`

Unsupported arm/task/gate/honesty/model/budget/live-command overrides are rejected.

```sh
.venv/bin/python research/shadow_verifier_eval/run.py \
  --output build/shadow-verifier-report.json
```

`--output` refuses to overwrite. `build/` is gitignored.

```sh
.venv/bin/python -m pytest tests/python/test_shadow_verifier.py
```

`--include-model-arms` is **rejected** in this scaffold. Later live command
(not implemented here; `N` is a written planned-call count; do not start
without a budget; do not invent numbers):

```sh
.venv/bin/python research/shadow_verifier_eval/run.py \
  --include-model-arms \
  --confirm-model-runs N \
  --output build/shadow-verifier-live-report.json
```

Core conformance (existing corpus, still required before any larger
model-backed run):

```sh
.venv/bin/python script/check_obligations.py
```

This-machine report used for the tables below was written with the
deterministic command to `/tmp/shadow-verifier-report.json`. Environment:
Math Anchor 0.7.1, Python 3.13.5. Harness commit `0426908` (quote
`environment.gitHead` from a report generated on that commit). Do not treat
`main` `fdc5031` as the harness commit.

Byte counts below are canonical JSON sizes of obligation **feedback**
(model-context projection) and **receipt** artifacts. They are not tokens
and not a 10% context claim. B3 control rows showing **0** model-context
bytes are the B3 wrapper projection described above, not a measurement of
Host I/O and not independent evidence that an Agent saw zero bytes. The
report also records `runtimeFeedbackBytes` (canonical size of the runtime
feedback object before that projection). Product quiet-success evidence is
CLI `--quiet-success` empty stdout, already probed.

## Pre-registered corpus

Fixed before looking at arm outcomes:

| Task | Corruption | Trusted primary status | G1 seeded error? |
| --- | --- | --- | --- |
| control-polynomial-identity | none | `checked` | no (G3 control) |
| control-dimension-consistency | none | `checked` | no (G3 control) |
| sign-flip | `(x+y)^2` vs `x^2 - 2xy + y^2` | `falsified` | yes |
| domain-overshoot-definedness | `(x^2-1)/(x-1)` vs `x+1`, strict real | `falsified` | yes |
| dimension-mismatch | distance vs speed + time | `falsified` | yes |
| unsupported-kind | unregistered sheaf cohomology | `unsupported` | no (completeness) |
| dependency-blocked | identity depending on unsupported | `unknown` | no (completeness) |

Structural probes (not comparison cells):

- `evals/obligations/core.v0.1.json` must still match (checked, falsified,
  unsupported, dependency-blocked).
- Wrong witness: producer `x = x` bound to `(x+y)^2` identity →
  `certificate_rejected`.
- Stale/swapped: producer `(x+y)^2` certificate bound to `(x-y)^2` identity
  → `certificate_rejected`.
- CLI `--quiet-success` on a valid identity: exit 0, empty stdout, receipt
  on disk.
- CLI `--quiet-success` on sign-flip: exit 1, `failures_only`
  `attention_required`.

`coversOriginalTaskClaim` stays false. `formalKernelChecked` stays false.
No dollar costs. No savings percentage.

## Results (this machine, deterministic B2/B3)

B0/B1 cells are `status=deferred`, `model_arms=deferred`, with
`liveQualityDelta` / `finalAccuracy` / `acceptedSeededError` all `null`.

| Arm | Task | Primary | Detected | Model-context bytes | Quiet success |
| --- | --- | --- | --- | --- | --- |
| B2 | control-polynomial-identity | checked | no | 1651 | no (full feedback) |
| B2 | control-dimension-consistency | checked | no | 1539 | no |
| B2 | sign-flip | falsified | yes | 1696 | no |
| B2 | domain-overshoot-definedness | falsified | yes | 1465 | no |
| B2 | dimension-mismatch | falsified | yes | 1672 | no |
| B2 | unsupported-kind | unsupported | yes | 1251 | no |
| B2 | dependency-blocked | unknown | yes | 1925 | no |
| B3 | control-polynomial-identity | checked | no | **0** | **yes** |
| B3 | control-dimension-consistency | checked | no | **0** | **yes** |
| B3 | sign-flip | falsified | yes | 1705 | no |
| B3 | domain-overshoot-definedness | falsified | yes | 1474 | no |
| B3 | dimension-mismatch | falsified | yes | 1681 | no |
| B3 | unsupported-kind | unsupported | yes | 1260 | no |
| B3 | dependency-blocked | unknown | yes | 1934 | no |

B3 canonical `receiptBytes` for those cells were 1346–2020 (pretty-printed
files are larger) and **not** returned on quiet success. B2 cells write
the same debug receipts but set `receiptOutsideModelContext=false` because
full feedback is returned to the model-context projection.

Seeded **same-claim** correction on sign-flip (restore `+2xy` on the same
identity) reached `checked` with quiet success. That hook is **not** a live
model repair. The dimension-mismatch follow-up submits a **different**
valid claim (`force = mass * acceleration`, the G3 control), not a
correction of `distance` vs `speed + time`. It is recorded as
`unrelated_valid_resubmit` and does **not** count as a G5 repair probe.
G5 stays unmet.

Structural:

- core.v0.1.json matched, including injected sign error, strict definedness,
  dimension error, unsupported kind, and dependency-blocked unknown
- wrong witness: `unknown` / `certificate_rejected`
- stale swapped certificate: `unknown` / `certificate_rejected`
- CLI quiet success: 0 stdout bytes, receipt `checked=1`
- CLI sign-flip: exit 1, failures_only `["sign-flip"]`

This-machine G1 on the three **supported** seeded error tasks: B2 3/3, B3
3/3, binding probes 2/2. **That does not meet Epoch 2 G1.** G1 requires live
four-arm evidence. G2 and G6 were not measured. G3 false rejects on the two
controls: 0. G4 ≤10% vs B0: not measured.

## Decision (this smoke only)

**evidence insufficient — do not promote. Epoch 2 is not complete.**
Experiment verdict: **`deterministic_b2_b3_scaffold_ran`**.

| Brief branch | This smoke |
| --- | --- |
| Promote | **No.** `publicPromotion` stays false. |
| H1 / method accumulation | **No.** Dated freeze 2026-09-15 pending new workload evidence; not a standing ban. |
| Targeted fix | **No** correctness bug on the pre-registered cells. |
| Epoch 2 complete | **No.** Live B0/B1/G2/G6 missing. |
| Evidence insufficient | **Yes** for promotion and for Epoch 2 completion. |

Do not invent a savings percentage or a model quality delta.

## Honesty

- Smoke ≠ overall benefit percentage. The report refuses to emit one.
- Green harness tests ≠ completion of Epoch 2.
- G1–G6 stay targets.
- `model_arms=deferred`. No live-model numbers.
- Quiet success is zero returned content, not proof of use.
- B3 library `modelContextBytes=0` is a wrapper projection when checked;
  product evidence is CLI `--quiet-success` empty stdout.
- Seeded repair is not live-model repair. Only same-claim corrections
  count as repair probes. Dimension-mismatch resubmit is not a repair of
  the original claim. G5 remains unmet.
- `coversOriginalTaskClaim` stays false.
- Call-alone is not adoption.
- Polynomial checker independence is not independence for every kind.
- No dollar costs. No model calls. No savings %.
- Method packs not promoted. Do not start H1 from this scaffold.

## Gaps (not covered)

- No live B0/B1 run, no reasoning-effort comparison, no token accounting.
- No accepted-error drop vs a matched no-provider model (G2).
- No ≤10% context comparison vs B0 (G4 remainder).
- No live repair loop (G5 remainder).
- No strong+weak model pair (G6).
- No LP certificates (Epoch 3).
- No Host product integration beyond the existing CLI shadow path.

## Next

Keep experimental. **Do not start H1.** Do not promote packs.

A later paid four-arm run is justified only with a written budget, core
conformance still green, this B2/B3 scaffold still matching, and
`--confirm-model-runs N`. Until that evidence exists, Epoch 2 remains open.
