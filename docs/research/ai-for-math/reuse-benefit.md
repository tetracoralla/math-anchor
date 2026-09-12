# Reuse benefit vs strong CAS baselines (no model)

This note is a research report, not a product Capability and not an overall
benefit percentage. The frozen shifted-square pack is **not** promoted. Agent
Host, the four MCP tools, the human calculator UI, and Skill Refinery are
unchanged. Do not start H1.

A1–A4, F1–F5, R1–R3, and the parameterized pack apply path are unchanged.
Green harness tests are not completion of this research claim.

The three judgments below are **separate**. They are not one `success` flag.

## Mandatory claim

相对强基线，这个包额外保存了什么；哪一步因此不必再做；是否仍有净收益。

相对 B0（每次 SymPy summation）与 B_template/B_codegen（同一条缓存的参数化
反差分做模板代入或 QQ 系数表求值），这个包额外保存的仍是 `G(k,c)` 与可检查
的二元恒等式；因此不必再对每个 `(c,a,b)` 构造 G。但 B_template 已经同样跳过
构造并得到相同有理数；包路径仍做适用性与恒等式检查，本机耗时并不更低。相对
这些强基线，本实验未见净收益。相对冷启动 Gosper（B1）更快不能单独证明
Math Anchor 的差异化。

## Workload: what actually repeats

Family: inclusive finite sums of `(k+c)^2` for rational `c` and integer bounds
with `|a|,|b| <= 10^6`. Empty sum when `upper == lower - 1`.

For each new `(c,a,b)` the repeated work is:

1. **Construct** a polynomial antidifference `G` (Gosper / undetermined
   coefficients / CAS summation).
2. **Check** `G(k+1)-G(k)=(k+c)^2` (optional in a CAS; required on the pack
   path).
3. **Evaluate** `G(b+1)-G(a)`.
4. **Decide** applicability / domain.

The pack already stores instantiable math from the previous experiment:

`G(k,c)=k(k-1)(2k-1)/6 + c k(k-1) + c^2 k`, with identity
`G(k+1,c)-G(k,c)=(k+c)^2`.

That is what a later task can skip **constructing**. It does not skip
applicability, the instance identity check, or telescoping. It is not a unique
closed form: SymPy summation already returns the number, and a CAS user can
cache the same `G`.

**Not claimed:** new mathematics; dollar savings; semantic adoption from
`lifecycleEvidence`; uniqueness from “faster than cold Gosper”.

## Arms (equal budget; baselines not crippled)

| Arm | What it is | May construct / cache | Independent checker |
| --- | --- | --- | --- |
| **B0** | Existing SymPy `summation` each time | construct a closed value | no |
| **B1** | A1 polynomial finite-sum runner | construct via Gosper | yes (instance identity) |
| **B_template** | SymPy-side cached `G(k,c)`; substitute `c`, evaluate `G(b+1)-G(a)` | cache / fair template | no |
| **B_codegen** | Exact QQ coefficient table of `S(c,a,b)=G(b+1,c)-G(a,c)` from `sympy.Poly`; `Fraction` eval | generated exact evaluator | no |
| **P-pack** | Frozen shifted-square apply | reconstruction **disabled** (mechanism test on this arm only) | yes (general + instance) |

Mechanism test may disable reconstruction on the pack path. Benefit comparison
does **not** disable B0/B1 construction or B_template/B_codegen cache.

`B_codegen` does **not** use SymPy C codegen, pycode, or autowrap:

- `sympy.utilities.codegen` C for this closed form emits `double` / `pow`
  (float). Observed on this machine; not used.
- `pycode` emits `/` (Python 3 float division). `exec` of generated source is
  forbidden in this repository.
- `autowrap` needs a compiler/Cython toolchain and would still typically be
  float.

The exact evaluator is the QQ coefficient table, not a floating approximation.

## Commands and artifact paths

Pre-registered protocol (frozen before the run):

`research/reuse_benefit_eval/protocol.json`

Unsupported arm/task/latency overrides are rejected (pinned execution plan).

```sh
.venv/bin/python research/reuse_benefit_eval/run.py \
  --output build/reuse-benefit-report.json
```

`--output` refuses to overwrite. `build/` is gitignored.

```sh
.venv/bin/python -m pytest tests/python/test_reuse_benefit.py
```

This-machine report used for the tables below was written with that command to
`/tmp/reuse-benefit-report.json`. Environment: Math Anchor 0.7.1, Python 3.13.5,
SymPy 1.14.0, git `3d01d0266150f14b705dfa4c46e5d6618b687a25` at run time (main
tip). Harness commit `27fb191`; this documentation commit is later.

## Pre-registered tasks

Fixed before looking at arm deltas:

| Task | Input | Pre-registered expectation |
| --- | --- | --- |
| P0 replay | `(k+1)^2`, `c=1`, `0..4` | exact `55` (extraction replay, not held-out) |
| P1 held-out | `(k+3)^2`, `c=3`, `2..7` | exact `355` (not a rename of P0) |
| P2 rational | `(k+1/2)^2`, `c=1/2`, `1..3` | exact `83/4` |
| P3 held-out | `(k-2)^2`, `c=-2`, `-1..5` | exact `28` (negative `c`, bounds cross zero) |
| P4 empty | `(k+5)^2`, `c=5`, `3..2` | exact `0` (`upper == lower - 1`) |
| Negative harmonic | `1/k` on `1..3` | **never counted as solved** |
| Negative reversed | `(k+1)^2` on `5..1` | **never counted as solved**; fair CAS may emit Karr `-50` |

B0 may return `11/6` for `1/k` and `-50` for reversed bounds. Those are not
polynomial-finite-sum successes in this proposal.

Structural probes (not timed comparison cells):

- Strip `parametricAntidifference` → P-pack refuses (`PackFormatError` `E_INPUT`).
- Wrong saved `G` (`k` instead of the quadratic) → P-pack fail-closes; no sum.
- Out-of-family `k^3` on `1..20`: B0/B1 may still construct `44100`; family
  template, codegen, and P-pack must refuse. Fair baselines are not crippled.

`coversOriginalTaskClaim` stays false. `formalKernelChecked` stays false.
No dollar costs. No savings percentage.

## Three judgments (this smoke)

| Judgment | Verdict | What it does *not* mean |
| --- | --- | --- |
| **Trustworthiness** | `holds_in_declared_domain` | Not a utility win; not uniqueness |
| **Behavior** | `pack_uses_saved_content` | Not unique reuse: B_template/B_codegen also use saved `G` |
| **Utility** | `no_net_benefit_vs_strong_baselines` | Not a correctness failure; not a reason to promote |

Promotion decision remains **`evidence_insufficient`**. The three verdicts are
not OR-ed into one `success`.

## Results (this machine, in-process)

Latencies are sequential in-process wall times in arm order B0 → B1 →
B_template → B_codegen → P-pack. **B1 P0 first trial includes
obligation-checker warmup; later cells are already warm.** Trial labels are
`first` / `repeat`. These were never isolated cold processes. Prep for
B_template (`3.3 ms`) and B_codegen (`26.8 ms`, 13 QQ terms, P0 self-check
`55`) is reported separately and is **not** folded into a savings percentage.

Construction trace is the wrap of `gosper_sum` / `construct_antidifference`.

| Arm | Task | Status | Value / code | Counted as solved | gosper | first ms | repeat ms |
| --- | --- | --- | --- | --- | --- | --- | --- |
| B0 | P0 | ok | 55 | yes | 0 | 2.8 | 1.9 |
| B0 | P1 | ok | 355 | yes | 0 | 19.3 | 1.8 |
| B0 | P2 | ok | 83/4 | yes | 0 | 4.0 | 2.1 |
| B0 | P3 | ok | 28 | yes | 0 | 3.8 | 3.0 |
| B0 | P4 | ok | 0 | yes | 0 | 0.3 | 0.2 |
| B0 | `1/k` | ok | 11/6 | **no** | 0 | 0.9 | 0.6 |
| B0 | reversed | ok | -50 | **no** | 0 | 1.8 | 1.9 |
| B1 | P0 | ok | 55 | yes | 1 | 434.1 | 21.5 |
| B1 | P1 | ok | 355 | yes | 1 | 32.5 | 26.4 |
| B1 | P2 | ok | 83/4 | yes | 1 | 33.8 | 20.5 |
| B1 | P3 | ok | 28 | yes | 1 | 30.9 | 22.3 |
| B1 | P4 | ok | 0 | yes | 1 | 32.5 | 19.3 |
| B1 | `1/k` | error | `E_UNSUPPORTED` | **no** | 0 | 0.0 | 0.0 |
| B1 | reversed | error | `E_DOMAIN` | **no** | 0 | 0.0 | 0.0 |
| B_template | P0 | ok | 55 | yes | 0 | 1.0 | 0.2 |
| B_template | P1 | ok | 355 | yes | 0 | 1.2 | 0.2 |
| B_template | P2 | ok | 83/4 | yes | 0 | 1.0 | 0.2 |
| B_template | P3 | ok | 28 | yes | 0 | 1.0 | 0.1 |
| B_template | P4 | ok | 0 | yes | 0 | 0.7 | 0.1 |
| B_template | `1/k` | inapplicable | `E_UNSUPPORTED` | **no** | 0 | 0.0 | 0.0 |
| B_template | reversed | ok | -50 | **no** | 0 | 0.2 | 0.1 |
| B_codegen | P0 | ok | 55 | yes | 0 | 0.1 | 0.1 |
| B_codegen | P1 | ok | 355 | yes | 0 | 0.1 | 0.1 |
| B_codegen | P2 | ok | 83/4 | yes | 0 | 0.1 | 0.1 |
| B_codegen | P3 | ok | 28 | yes | 0 | 0.1 | 0.1 |
| B_codegen | P4 | ok | 0 | yes | 0 | 0.1 | 0.1 |
| B_codegen | `1/k` | inapplicable | `E_UNSUPPORTED` | **no** | 0 | 0.0 | 0.0 |
| B_codegen | reversed | ok | -50 | **no** | 0 | 0.1 | 0.1 |
| P-pack | P0 | ok | 55 | yes | 0 | 10.8 | 8.8 |
| P-pack | P1 | ok | 355 | yes | 0 | 7.4 | 7.9 |
| P-pack | P2 | ok | 83/4 | yes | 0 | 7.4 | 7.2 |
| P-pack | P3 | ok | 28 | yes | 0 | 8.1 | 7.5 |
| P-pack | P4 | ok | 0 | yes | 0 | 15.5 | 11.3 |
| P-pack | `1/k` | inapplicable | `E_UNSUPPORTED` | **no** | 0 | 0.6 | 0.5 |
| P-pack | reversed | inapplicable | `E_DOMAIN` | **no** | 0 | 0.5 | 0.5 |

Work steps actually executed on in-family successes:

| Arm | Steps |
| --- | --- |
| B0 | `cas_summation` |
| B1 | `construct_antidifference`, `check_instance_identity`, `evaluate_telescoping` |
| B_template | `applicability`, `instantiate_saved_G`, `evaluate_telescoping` |
| B_codegen | `applicability`, `codegen_eval` |
| P-pack | `retrieve`, `applicability`, `instantiate`, `verify_general_difference_identity`, `verify_difference_identity`, `combine_with_infrastructure_telescoping` |

P-pack P1 constructor was `instantiated-saved-parametric-antidifference`.
`gosperCalled` JSON flag was false; the wrap also recorded 0 constructor calls.
B1 P1 constructor was `sympy.concrete.gosper.gosper_sum`.

Call-alone is not adoption. `bTemplateAlreadyMatchesP` is true.
`bCodegenAlreadyMatchesP` is true.

## What Math Anchor still reduces (or does not)

Versus **B1** (cold Gosper each time): the pack skips construction of this `G`.
That is real behavior, already shown in the parameterized-method experiment.
It is **not** unique once B_template/B_codegen are allowed to cache the same
formula.

Versus **B0** (direct CAS each time): B0 already matches every in-family exact
value and is simpler when only a number is required. Repeat-trial P-pack was
slower than B0 on every in-family task (`observedSlowerCheckedPath=true`).

Versus **B_template / B_codegen**: they already skip construction, match the
same in-family rationals, and are faster on this machine. The pack's extra
work is independent identity checking plus fail-closed domain. Checking is
additional work, not a reduction.

Versus **reversed bounds**: B0 / B_template / B_codegen emit Karr `-50`. B1 and
P-pack refuse (`E_DOMAIN`). That convention difference is **A1 infrastructure**,
already present without the pack. It is not pack-unique versus B1.

## Decision (this smoke only)

**evidence insufficient — do not promote.** Utility versus strong baselines is
**no net benefit** on this family. That is a completed experiment, not a
failed harness.

| Brief branch | This smoke |
| --- | --- |
| Promote | **No.** `publicPromotion` stays false. |
| H1 / method accumulation | **No.** Do not start H1. |
| Targeted fix | **No** correctness bug on the pre-registered cells. |
| Evidence insufficient | **Yes** for promotion. One family, no model, no tokens, no prices. |

Do not invent a savings percentage from these milliseconds.

## Honesty

- Smoke ≠ overall benefit percentage. The report refuses to emit one.
- Green harness tests ≠ completion of the research claim.
- The three judgments are not one success flag.
- `lifecycleEvidence=cross-task-use-evidence` alone is not semantic adoption.
- Call-alone is not adoption.
- `coversOriginalTaskClaim` stays false.
- `1/k` and reversed bounds are never counted as solved.
- No dollar costs. No model calls. No savings %.
- Telescoping remains hand-provided infrastructure.
- What the pack saved versus B1 is the parametric `G(k,c)` (construction).
  Versus B_template, that construction skip is already available.

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

A later experiment is only justified if it targets work that B0, a cached
parametric template, and an exact generated evaluator cannot already do — not
another family whose closed form is a short SymPy `summation`.
