# Shadow verifier (Research Epoch 2 scaffold)

This note is a research report, not a product Capability, not an overall
benefit percentage, and **not Epoch 2 completion**. Method packs are **not**
promoted. Dated research status: experimental draft **2026-09-16**. Do not
start H1. Dated H1 freeze **2026-09-15** is unchanged.

Green harness tests are not completion of this research claim. Live B0/B1
model numbers are **not invented**. Default smoke stays `model_arms=deferred`.
Authorized live evidence, when present, is recorded in
[shadow-verifier-live.md](shadow-verifier-live.md) with real counts only.

Gates **G1–G6 are targets**. Epoch 2 is not done until live four-arm model
evidence exists.

## What this PR adds (Epoch 2 still incomplete)

Advances live-arm **readiness** and an expanded silent-wrong corpus. Still
**experimental**. **No promote.** Do not start H1.

1. **Expanded deterministic corpus (B2/B3):** rounding sneak into an exact
   chain; unit-kind mismatch that still looks numeric; assumption swap on a
   look-alike identity; step-N result replaced with another legal but
   wrong-for-this-claim value. Plus an SI-prefix scale **completeness**
   blind-spot cell (provider returns `checked`; not G1).
2. **Live-arm runner:** `LiveFourArmPlan`, `--emit-live-plan` (no model
   calls), fail-closed `--include-model-arms` unless budget confirm +
   registered `LiveModelBackend` + `--confirm-model-runs N`. Authorized
   runs execute live B0/B1 up to N `complete()` calls (xAI/Grok). Numbers
   are not invented.
3. **Natural-error-shaped task pack:** `research/shadow_verifier_eval/natural_tasks/`
   human-authored multi-step prompts with controller-only oracle notes. No
   live scores.


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
| **B0** | Model-only, no mathematical provider | Default smoke **deferred**. Authorized live: [shadow-verifier-live.md](shadow-verifier-live.md) |
| **B1** | Model + current MCP (`math.search` / `math.describe` / `math.run` / `math.batch`), voluntary tool use. No fifth tool. A correct answer without a target call is not adoption | Default smoke **deferred**. Authorized live uses in-process four-tool catalog dispatch (not Host JSON-RPC MCP): [shadow-verifier-live.md](shadow-verifier-live.md) |
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
| **G1** | detection | ≥80% of **supported** seeded errors | B2/B3 7/7 on this corpus; live B0/B1 ran — see [shadow-verifier-live.md](shadow-verifier-live.md). **G1 unmet** there because two B1 G1 cells were unparseable after the call cap |
| **G2** | accepted-error drop | material reduction vs matched B0 | live B0 accepted **0** seeded errors on this model/corpus (vacuous). **G2 unmet** |
| **G3** | false reject | valid controls stay checked | B2/B3 0 false rejects; live B0/B1 0/2 on controls in the live report |
| **G4** | context | ≤10% main-context growth; **0** returned content on successful checkpoints | B3 library 0 bytes is a **wrapper projection**; product evidence is CLI `--quiet-success` empty stdout; live B1 vs B0 token growth was **not** ≤10% |
| **G5** | repair | after `failures_only`, repair can reach checked / quiet success | same-claim seeded hook (sign-flip) measured; dimension-mismatch resubmit is a **different valid claim**; **not** live-model repair; **G5 unmet** |
| **G6** | strong + weak models | same protocol on a stronger and a weaker model | **unmet** (one live model: xAI `grok-4.6`) |

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

Emit a live four-arm JSON plan (**no model calls**):

```sh
.venv/bin/python research/shadow_verifier_eval/run.py \
  --emit-live-plan \
  --natural-tasks-pack research/shadow_verifier_eval/natural_tasks \
  --output build/shadow-verifier-live-plan.json
```

`--include-model-arms` stays **fail-closed** unless `--confirm-live-budget`
(or `MATH_ANCHOR_SHADOW_LIVE=1`), `--confirm-model-runs N` with `N > 0`, and
a registered `LiveModelBackend`. The CLI auto-registers an xAI/Grok backend
when credentials are available. Authorized live command:

```sh
.venv/bin/python research/shadow_verifier_eval/run.py \
  --include-model-arms \
  --confirm-live-budget \
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
| rounding-in-exact-chain | `1/3` vs `0.333333` (exact chain context) | `falsified` | yes |
| unit-scale-mismatch | pressure = force/area with area as meter | `falsified` | yes |
| assumption-swapped | `sqrt(x)^2 = x` for all reals, strict | `falsified` | yes |
| step-n-legal-wrong-value | `(x+y)^2` claimed as `x^2 - y^2` after legal DoS step | `falsified` | yes |
| unsupported-kind | unregistered sheaf cohomology | `unsupported` | no (completeness) |
| dependency-blocked | identity depending on unsupported | `unknown` | no (completeness) |
| si-prefix-scale-blind-spot | work = force*distance with kilometer | `checked` | no (completeness / known blind spot) |

Structural probes (not comparison cells):

- `evals/obligations/core.v0.1.json` must still match (checked, falsified,
  unsupported, dependency-blocked).
- Wrong witness: producer `x = x` bound to `(x+y)^2` identity →
  `certificate_rejected`.
- Stale/swapped: producer `(x+y)^2` certificate bound to `(x-y)^2` identity
  → `certificate_rejected`.
- Rounding sneak / unit-kind mismatch / assumption swap / step-N legal-wrong:
  obligation runtime falsifies (same stack; not a parallel checker).
- CLI `--quiet-success` on a valid identity: exit 0, empty stdout, receipt
  on disk.
- CLI `--quiet-success` on sign-flip: exit 1, `failures_only`
  `attention_required`.

`coversOriginalTaskClaim` stays false. `formalKernelChecked` stays false.
No dollar costs. No savings percentage.

## Results (this machine, deterministic B2/B3)

Expanded-corpus tip (this PR): G1 supported seeded errors B2 **7/7**, B3
**7/7**, binding probes 2/2, plus adversarial structural probes all
falsified. SI-prefix blind-spot stayed `checked` as pre-registered
(completeness). Decision remains `evidence_insufficient` /
`deterministic_b2_b3_scaffold_ran` / `promote=false` /
`epoch2Complete=false`. Quote `environment.gitHead` from the report on this
tip. **Still not Epoch 2 G1.**

Historical table below is harness commit `0426908` evidence for the original
seven-task corpus (three supported seeded errors). Byte counts there are
not re-claimed for the new cells.

Default-smoke B0/B1 cells stay `status=deferred`, `model_arms=deferred`, with
`liveQualityDelta` / `finalAccuracy` / `acceptedSeededError` all `null`.
Authorized live B0/B1 counts are only in
[shadow-verifier-live.md](shadow-verifier-live.md) (real numbers; no
invented quality delta).

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

Historical harness commit `0426908` measured G1 on the original three
supported seeded-error tasks (B2 3/3, B3 3/3, binding probes 2/2). This PR
expands the supported set to **seven** tasks; quote `environment.gitHead` and
gate totals from a report generated on this tip. **That still does not meet
Epoch 2 G1.** G1 requires live four-arm evidence. G2 and G6 were not
measured. G3 false rejects on the two controls: 0. G4 ≤10% vs B0: not
measured. SI-prefix blind-spot is completeness-only (expected `checked`).

## Decision (this smoke only)

**evidence insufficient — do not promote. Epoch 2 is not complete.**
Experiment verdict: **`deterministic_b2_b3_scaffold_ran`**.

| Brief branch | This smoke |
| --- | --- |
| Promote | **No.** `publicPromotion` stays false. |
| H1 / method accumulation | **No.** Dated freeze 2026-09-15 pending new workload evidence; not a standing ban. |
| Targeted fix | **No** correctness bug on the pre-registered cells. |
| Epoch 2 complete | **No.** Live B0/B1 ran under a call cap; G1/G2/G4/G5/G6 still unmet. See [shadow-verifier-live.md](shadow-verifier-live.md). |
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

- Completeness and `natural_tasks/` cells were not in the N=48 live run.
- G2 accepted-error drop is vacuous on this `grok-4.6` / corpus pair (B0 accepted 0).
- G4 ≤10% vs B0 not met (B1 tool-schema traces).
- No live repair loop (G5 remainder).
- No strong+weak model pair (G6).
- No LP certificates (Epoch 3).
- No Host product integration beyond the existing CLI shadow path. B1 was in-process catalog dispatch, not Host MCP JSON-RPC.

## Next

Keep experimental. **Do not start H1.** Do not promote packs.

A first authorized live B0/B1 run is recorded in
[shadow-verifier-live.md](shadow-verifier-live.md). Epoch 2 remains open.
Further live work (larger N, completeness + natural tasks, live repair, a
weaker second model) still needs a written budget and must not invent
numbers. Do not start H1. Do not promote packs.
