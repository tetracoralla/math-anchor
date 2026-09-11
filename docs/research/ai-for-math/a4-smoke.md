# A4: equal-budget smoke (no model)

This note is a research report, not a product Capability and not an overall
benefit percentage. The frozen Gosper pack is **not** promoted. Agent Host,
the four MCP tools, the human calculator UI, and Skill Refinery are unchanged.

A1/A2/A3 mathematical behaviour is unchanged. This smoke is an **integration
signal** on a pre-registered three-task split. Green harness tests are not
completion of A4 research claims.

## What changed (user-visible for this vertical)

A no-model equal-budget runner now compares, on the same pre-registered tasks:

| Arm | What it is |
| --- | --- |
| **B0** | Existing SymPy `summation` baseline. No method pack, no obligation checker. |
| **B1** | A1 polynomial finite-sum runner. No extracted pack. `compare_baseline=false` so B0 is not embedded. |
| **B2** | Frozen A2 pack apply path on the A1 backend. |
| **B2-minus** | Held-out cubes **without** the pack, run only because B2 showed a reuse signal. Same execution as B1 on that task. |

`gosper_sum` remains the untrusted B1/B2 constructor. B0 uses the existing
`sympy_finite_sum` baseline (`sympy.summation`) for the definite-sum value.

## Commands and artifact paths

Pre-registered protocol (frozen before the run):

`research/ai_for_math_eval/protocol.json`

Smoke (machine-readable report is gitignored under `build/`):

```sh
.venv/bin/python research/ai_for_math_eval/run.py \
  --output build/a4-smoke-report.json
```

`--output` refuses to overwrite.

Harness honesty tests:

```sh
.venv/bin/python -m pytest tests/python/test_a4_smoke.py
```

Related vertical (unchanged math):

```sh
.venv/bin/python -m pytest \
  tests/python/test_polynomial_finite_sum_proposal.py \
  tests/python/test_method_pack_proposal.py \
  tests/python/test_coverage_proposal.py \
  tests/python/test_a4_smoke.py
```

This-machine report used for the table below was written with that command
to `build/a4-smoke-report.json`. Environment: Math Anchor 0.7.1, Python
3.13.5, SymPy 1.14.0, starting git `e64a32e`.

## Pre-registered tasks and scoring

Fixed before looking at arm deltas:

| Task | Input | Pre-registered expectation |
| --- | --- | --- |
| T1 | `k^2` on 1..10 | exact `385` |
| Held-out cubes | `k^3` on 1..20 | exact `44100` (not a rename of T1) |
| Negative | `1/k` on 1..3 | **never counted as solved**; B1/B2 fail-closed `E_UNSUPPORTED`, not a false proposition |

B0 may return a rational for `1/k` (harmonic number). That is not a polynomial
finite-sum success and is not counted as solving the negative.

Reuse on B2 cubes requires retrieve, instantiate, independent identity check,
value entering a later step, `lifecycleEvidence=cross-task-use-evidence`,
extraction task not reused as the answer, and `callAloneIsNotAdoption`. That
bundle is still **not** semantic adoption. B2-minus is the drop-library check.

`coversOriginalTaskClaim` stays false. `formalKernelChecked` stays false.
No dollar costs are emitted.

## Results (this machine, in-process)

The table below is the **pre-F1–F5** smoke at reviewed HEAD
`5217679e6c84eb366e3bda487b3db42614c1e414`. It is historical evidence, not the
post-fix report. After F1–F5 the harness labels the two in-process trials
`first` / `repeat` (they were never isolated cold processes). A new report must
be generated after the fix commits; do not reuse these millisecond figures.

Latencies are sequential in-process wall times in arm order B0 → B1 → B2.
**B1 T1 first trial includes obligation-checker warmup; later B2 cells are
already warm.** This is not a statistical benchmark and not a dollar cost.

| Arm | Task | Status | Value / code | Counted as solved | Wrong accept | Applicability misjudgment | `coversOriginalTaskClaim` | Lifecycle | Reuse signal | semantic adoption | first ms (was labeled cold) | repeat ms (was labeled hot) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B0 | T1 | ok | 385 | yes | no | no | false | — | no | **false** | 22.1 | 1.3 |
| B0 | cubes | ok | 44100 | yes | no | no | false | — | no | **false** | 2.3 | 1.5 |
| B0 | `1/k` | ok | 11/6 | **no** | no | no | false | — | no | **false** | 1.5 | 0.7 |
| B1 | T1 | ok | 385 | yes | no | no | false | — | no | **false** | 459.1 | 18.7 |
| B1 | cubes | ok | 44100 | yes | no | no | false | — | no | **false** | 36.4 | 18.4 |
| B1 | `1/k` | error | `E_UNSUPPORTED` | **no** | no | no | false | — | no | **false** | 0.3 | 0.1 |
| B2 | T1 | ok | 385 | yes | no | no | false | `verified-in-declared-scope` | no (replay) | **false** | 17.3 | 16.1 |
| B2 | cubes | ok | 44100 | yes | no | no | false | `cross-task-use-evidence` | **yes** | **false** | 17.9 | 18.7 |
| B2 | `1/k` | inapplicable | `E_UNSUPPORTED` (rejected) | **no** | no | no | false | — | no | **false** | 0.3 | 0.2 |
| B2-minus | cubes | ok | 44100 | yes | no | no | false | — | no | **false** | 18.4 | 17.7 |

Call-alone is not adoption: B2 cubes `callAloneIsNotAdoption` is true even
though the apply chain ran and `lifecycleEvidence` is `cross-task-use-evidence`.

## B2-minus

B2 on held-out cubes **did** show a reuse signal (retrieve → instantiate →
checked identity → `44100` entered the telescoping step; extraction task not
reused as the answer). B2-minus therefore ran: same cubes task, pack not loaded
(A1 runner).

Impact: value stayed `44100`. Removing the pack does not change the finite-sum
number on this family. The A1 runner already produces it. Pack apply records
an evidence chain; `lifecycleEvidence=cross-task-use-evidence` is not semantic
adoption.

## Decision (this smoke only)

**evidence insufficient — do not promote.**

| Brief branch | This smoke |
| --- | --- |
| Promote | **No.** `publicPromotion` stays false. A three-task integration smoke is not a promotion case. |
| Targeted fix | **No** correctness bug on the pre-registered cells. Do not add layers to explain slowness. |
| Evidence insufficient | **Yes.** n=3, one family, no model, no tokens, no prices. Not an overall benefit percentage. |

Observed, not a cost claim: the checked B1/B2 path is typically slower than B0
on this machine after warmup, and B0 already computes `385` and `44100`. B1/B2
add independent identity checking and fail-closed `1/k`; that is domain honesty,
not an in-domain reliability lift on T1/cubes. B2-minus shows the pack is not a
unique closed form for cubes.

## Honesty

- Smoke ≠ overall benefit percentage. The report refuses to emit one.
- Green harness tests ≠ completion of A4 research claims
  (`greenHarnessTestsAreNotA4Completion`).
- `lifecycleEvidence=cross-task-use-evidence` alone is not semantic adoption.
- Call-alone is not adoption.
- `coversOriginalTaskClaim` stays false. Obligation success is not claim coverage.
- `1/k` is never counted as solved. B0 returning `11/6` is the SymPy baseline
  computing a harmonic number; B1/B2 fail closed and do not treat that as a
  false proposition.
- No dollar costs. No model calls.
- Telescoping remains hand-provided infrastructure. Pack JSON is not an
  interpreter. `formalKernelChecked` stays false.

## Gaps (not covered)

- No model, no reasoning-effort comparison, no token accounting.
- No dollar costs (none invented).
- Latency is sequential in-process, not isolated per-arm cold start, not a
  distribution, not amortized prep cost.
- One pack id, one polynomial family. Engines in pack JSON are still not dispatch.
- Hockey-stick binomial rewrite still unverified.
- No Lean kernel check of the finite-sum conclusion.
- No NL→claim compiler, no general obligation dataflow, no Host/UI/MCP work.
- Instances are not a universal proof.

## Next minimal experiment

Keep experimental. **Do not start H1.** Do not promote the pack.

Expand the neighborhood or run an authorized small model smoke **only if** a
later experiment is aimed at work B0 cannot already do on this family. Until
then, A4 on this vertical is an integration record, not a benefit claim.
