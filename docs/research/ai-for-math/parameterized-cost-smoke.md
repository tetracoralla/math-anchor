# Parameterized pack: equal-budget cost/timing smoke (no model)

This note is a research report, not a product Capability and not an overall
benefit percentage. The frozen shifted-square pack is **not** promoted. Agent
Host, the four MCP tools, the human calculator UI, and Skill Refinery are
unchanged.

A1–A4 and F1–F5 are unchanged. Green harness tests are not completion of this
research claim.

## What changed (user-visible for this vertical)

A no-model equal-budget runner now compares, on the same pre-registered
`(c,a,b)` tasks:

| Arm | What it is |
| --- | --- |
| **B0** | Existing SymPy `summation` baseline. Allowed to construct a closed value. No method pack. |
| **B1** | A1 polynomial finite-sum runner. Allowed to construct via `gosper_sum` / `construct_antidifference`. No extracted pack. `compare_baseline=false` so B0 is not embedded. |
| **P-pack** | Frozen shifted-square apply: instantiate saved `G(k,c)`; reconstruction disabled. Must refuse if `parametricAntidifference` is stripped. |

`gosper_sum` remains the untrusted B1 constructor. B0 uses the existing
`sympy_finite_sum` baseline (`sympy.summation`) for the definite-sum value.
P-pack must not call either constructor.

There is no P-minus arm. B1 on the same `(c,a,b)` **is** the drop-library
contrast: if B1 already produces the number by constructing, the pack is not a
unique closed form.

## Commands and artifact paths

Pre-registered protocol (frozen before the run):

`research/parameterized_cost_eval/protocol.json`

Smoke (machine-readable report is gitignored under `build/`):

```sh
.venv/bin/python research/parameterized_cost_eval/run.py \
  --output build/parameterized-cost-smoke-report.json
```

`--output` refuses to overwrite.

Harness honesty tests:

```sh
.venv/bin/python -m pytest tests/python/test_parameterized_cost_smoke.py
```

This-machine report used for the table below was written with that command
to `/tmp/parameterized-cost-smoke-report.json`. Environment: Math Anchor 0.7.1,
Python 3.13.5, SymPy 1.14.0, git `c4dbccde4c5757145b01ce789a97883f90d8eabc`
(harness commit; this documentation commit is later).

## Pre-registered tasks and scoring

Fixed before looking at arm deltas:

| Task | Input | Pre-registered expectation |
| --- | --- | --- |
| P0 replay | `(k+1)^2`, `c=1`, `0..4` | exact `55` (extraction replay, not held-out) |
| P1 held-out | `(k+3)^2`, `c=3`, `2..7` | exact `355` (not a rename of P0) |
| P2 rational | `(k+1/2)^2`, `c=1/2`, `1..3` | exact `83/4` |
| Negative | `1/k` on `1..3` | **never counted as solved**; B1/P-pack fail-closed `E_UNSUPPORTED`, not a false proposition |

B0 may return a rational for `1/k` (harmonic number). That is not a polynomial
finite-sum success and is not counted as solving the negative.

Structural probes (not timed comparison cells):

- Strip `parametricAntidifference` from the pack → P-pack must refuse (this run:
  `PackFormatError` `E_INPUT`).
- Out-of-family `k^3` on `1..20`: B0/B1 may still construct `44100`; P-pack must
  refuse. Fair baselines are not crippled.

`coversOriginalTaskClaim` stays false. `formalKernelChecked` stays false.
No dollar costs are emitted. No savings percentage is emitted.

Construction tracing wraps `gosper_sum` and `construct_antidifference`. The
JSON `gosperCalled` flag is a path invariant; the wrap is the probe.

## Results (this machine, in-process)

Latencies are sequential in-process wall times in arm order B0 → B1 → P-pack.
**B1 P0 first trial includes obligation-checker warmup; later P-pack cells are
already warm.** Trial labels are `first` / `repeat`. These were never isolated
cold processes. This is not a statistical benchmark and not a dollar cost.

| Arm | Task | Status | Value / code | Counted as solved | Construction trace (gosper, construct) | Lifecycle | first ms | repeat ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B0 | P0 | ok | 55 | yes | 0, 0 | — | 21.0 | 1.9 |
| B0 | P1 | ok | 355 | yes | 0, 0 | — | 4.3 | 2.1 |
| B0 | P2 | ok | 83/4 | yes | 0, 0 | — | 2.8 | 2.0 |
| B0 | `1/k` | ok | 11/6 | **no** | 0, 0 | — | 0.9 | 0.6 |
| B1 | P0 | ok | 55 | yes | 1, 1 | — | 449.3 | 24.6 |
| B1 | P1 | ok | 355 | yes | 1, 1 | — | 44.7 | 24.9 |
| B1 | P2 | ok | 83/4 | yes | 1, 1 | — | 40.8 | 21.5 |
| B1 | `1/k` | error | `E_UNSUPPORTED` | **no** | 0, 0 | — | 0.0 | 0.0 |
| P-pack | P0 | ok | 55 | yes | 0, 0 | `verified-in-declared-scope` | 11.6 | 8.0 |
| P-pack | P1 | ok | 355 | yes | 0, 0 | `cross-task-use-evidence` | 8.5 | 8.2 |
| P-pack | P2 | ok | 83/4 | yes | 0, 0 | `cross-task-use-evidence` | 7.6 | 7.7 |
| P-pack | `1/k` | inapplicable | `E_UNSUPPORTED` (rejected) | **no** | 0, 0 | — | 0.6 | 0.6 |

P-pack P1 constructor was `instantiated-saved-parametric-antidifference`.
`gosperCalled` JSON flag was false; the wrap also recorded 0 constructor calls.
B1 P1 constructor was `sympy.concrete.gosper.gosper_sum`.

Call-alone is not adoption: P-pack P1 `callAloneIsNotAdoption` is true even
though the apply chain ran and `lifecycleEvidence` is `cross-task-use-evidence`.

## Decision (this smoke only)

**evidence insufficient — do not promote.**

| Brief branch | This smoke |
| --- | --- |
| Promote | **No.** `publicPromotion` stays false. A few integration cells are not a promotion case. |
| H1 / method accumulation | **No.** Do not start H1. |
| Targeted fix | **No** correctness bug on the pre-registered cells. |
| Evidence insufficient | **Yes.** One family, no model, no tokens, no prices. Not an overall benefit percentage. |

Observed, not a cost claim:

- **B0 already matches** every in-family exact value (`55`, `355`, `83/4`) and
  is the simpler path when only a number is required.
- Repeat-trial in-process latency for B1 and P-pack was higher than B0 on every
  in-family task (`observedSlowerCheckedPath=true`).
- P-pack repeat was lower than B1 on every in-family task. That is consistent
  with skipping Gosper construction while still checking identities. **It is
  not a dollar saving and not a reason to promote.**
- B1 on the same `(c,a,b)` already produces the number by constructing, so the
  pack is not a unique closed form.

Do not invent a savings percentage from these milliseconds.

## Honesty

- Smoke ≠ overall benefit percentage. The report refuses to emit one.
- Green harness tests ≠ completion of the research claim.
- `lifecycleEvidence=cross-task-use-evidence` alone is not semantic adoption.
- Call-alone is not adoption.
- `coversOriginalTaskClaim` stays false.
- `1/k` is never counted as solved. B0 returning `11/6` is the SymPy baseline
  computing a harmonic number; B1/P-pack fail closed and do not treat that as a
  false proposition.
- No dollar costs. No model calls. No savings %.
- Telescoping remains hand-provided infrastructure. Pack JSON is not an
  interpreter. `formalKernelChecked` stays false.
- What the pack saved versus B1 is the parametric `G(k,c)` (construction).
  Applicability and identity checks still run.

## Gaps (not covered)

- No model, no reasoning-effort comparison, no token accounting.
- No dollar costs (none invented).
- Latency is sequential in-process, not isolated per-arm cold start, not a
  distribution, not amortized prep cost.
- One pack id, one polynomial family (`(k+c)^2` with leading coefficient 1).
- No Lean kernel check of the finite-sum conclusion.
- No Host/UI/MCP work.

## Next

Keep experimental. **Do not start H1.** Do not promote the pack.

The follow-up with strong cache/template/codegen baselines and three separate
judgments is [reuse-benefit.md](reuse-benefit.md). It does **not** promote the
pack. B_template already matches P-pack on this family.
