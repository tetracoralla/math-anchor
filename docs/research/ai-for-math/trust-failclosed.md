# Trust / fail-closed vs fair template (no model)

This note is a research report, not a product Capability and not an overall
benefit percentage. The frozen shifted-square pack is **not** promoted. Dated
research status: experimental draft **2026-09-14**. Agent Host, the four MCP
tools, the human calculator UI, and Skill Refinery are unchanged in this PR.

A1–A4, F1–F5, R1–R3, the parameterized pack apply path, and the reuse-benefit
smoke are unchanged. Green harness tests are not completion of this research
claim. Do not start H1.

The three judgments below are **separate**. They are not one `success` flag.
Latency is **not** the primary claim.

## Mandatory claim

相对公平的 SymPy 侧缓存模板，包加检查在哪些探针上 fail-closed，而模板静默接受或给出错误值？

相对公平模板（同一条缓存 G 做代入，不做包身份检查，也不做包域检查），包路径在错误保存的 G、交换载荷、反转边界与越界上 fail-closed，而模板给出错误值或静默接受；出族 k^3、1/k 与 parameterC 不一致上双方都拒绝，不是包独有。身份/义务绑定钩子只在包路径上存在。本实验不以时延为主要结论。

## Question

Reuse-benefit already recorded utility `no_net_benefit_vs_strong_baselines`
versus B0 / B_template / B_codegen. That latency question is **not** re-asked
here.

This smoke asks: **when does Math Anchor pack + checks fail closed (wrong
saved G / out-of-domain / identity or obligation binding failures) while a
fair SymPy-side cached template path silently accepts or returns a wrong
answer?**

## Trustworthiness scale (per cell)

These labels are the trustworthiness vocabulary. They are not collapsed
into one `success`. Arithmetic silent-wrong and policy silent-accept stay
distinct. Wrong/swapped saved `G` is the clear silent-wrong differentiation.

| Label | Means |
| --- | --- |
| **holds** | Emitted the protocol's trusted exact rational (in-family control with canonical `G`) |
| **fail-closed** | Refused or falsified **without** a finite-sum value |
| **silent-wrong** | Emitted a finite-sum **other than** the true sum of the stated summand on the stated bounds (arithmetic; wrong/swapped saved `G`) |
| **silent-accept-out-of-declared-domain** | Emitted a finite-sum when the trusted outcome is `no_value` because pack declared-domain checks were skipped. The value may be mathematically correct (over-limit) or Karr-conventional (reversed bounds). Policy `no_value`, not arithmetic silent-wrong. `wrongAcceptance` stays false. |

Matching a pre-registered `silent-wrong` / silent-accept cell requires
`expectedExactIfComputed` when that field is set. Emitting an arbitrary
finite-sum is not a match. Non-emission on an `exact` cell is fail-closed,
never silent-wrong.

## Arms

| Arm | What it is | Identity / domain |
| --- | --- | --- |
| **B_template** | Fair SymPy-side cached `G(k,c)`; substitute `c`, evaluate `G(b+1)-G(a)` | **No** pack identity checks. **No** pack domain checks (Karr reversed bounds; no `\|a\|,\|b\|<=10^6` cap). Family matching **stays on**, so the arm is not crippled into applying `G` to `1/k` or `k^3`. |
| **P-pack** | Frozen shifted-square apply | Reconstruction disabled. Existing applicability, general/instance identity, and declared-domain checks. Reuses apply / certificate / `verify_typed_binding`. |

Mechanism test may mutate saved `G` on **both** arms. Benefit comparison is
not this smoke. B0 / B1 / B_codegen are omitted so this does not become
another same-family latency bake-off.

## Commands and artifact paths

Pre-registered protocol (frozen before the run):

`research/trust_failclosed_eval/protocol.json`

Unsupported arm/task/latency/Chinese-answer/saved-G/honesty/scoring/decisionRule
overrides are rejected (pinned execution plan). The differentiation clause in
the mandatory Chinese answer is also generated from live
`observedWrongGDifferentiation` / `observedDomainDifferentiation` flags.

```sh
.venv/bin/python research/trust_failclosed_eval/run.py \
  --output build/trust-failclosed-report.json
```

`--output` refuses to overwrite. `build/` is gitignored.

```sh
.venv/bin/python -m pytest tests/python/test_trust_failclosed.py
```

This-machine report used for the tables below was written with that command to
`/tmp/trust-failclosed-report.json`. Environment: Math Anchor 0.7.1, Python
3.13.5, SymPy 1.14.0. Quote `environment.gitHead` from that report — harness
commit `13ebce1`. Do not treat `main` `fde6a6b` as the harness commit.
Millisecond values are **informational** in-process wall times (one
`observed` trial). They are not a latency bake-off. P-pack control includes
obligation-checker warmup.

## Pre-registered probes

Fixed before looking at arm deltas:

| Task | Input / mutation | Protocol trusted outcome |
| --- | --- | --- |
| control-P1 | `(k+3)^2`, `c=3`, `2..7`, canonical `G` | exact `355` (template must not be crippled) |
| wrong-saved-G | same task, saved `G = k` | **no_value**; template naive `G(8)-G(2)=6` |
| swapped-saved-G | same task, saved `G = k^2(k-1)^2/4` | **no_value**; template naive `783` |
| out-of-family-cubes | `k^3` on `1..20` | **no_value**; both fail-closed if family matching holds |
| out-of-family-harmonic | `1/k` on `1..3` | **no_value**; both fail-closed |
| reversed-bounds | `(k+1)^2` on `5..1` | **no_value**; fair template may emit Karr `-50` |
| parameter-mismatch | `(k+1)^2` with `parameterC=2` | **no_value**; both fail-closed |
| over-limit | `(k+3)^2` on `1000001..1000002` | **no_value**; mathematical sum `2000018000041` |

Structural probes (not comparison cells):

- Strip `parametricAntidifference` → P-pack refuses (`PackFormatError` `E_INPUT`). B_template does not load pack JSON; pack-only.
- Tamper `identity.right` to `k**3` on a good P-pack control result → `verify_typed_binding` fail-closes (A3 / PR13 R1–R3). Fair template has no obligation binding hook.

`coversOriginalTaskClaim` stays false. `formalKernelChecked` stays false.
No dollar costs. No savings percentage.

## Three judgments (this smoke)

| Judgment | Verdict | What it does *not* mean |
| --- | --- | --- |
| **Trustworthiness** | per-cell `holds` / `fail-closed` / `silent-wrong` / `silent-accept-out-of-declared-domain`; contrast recorded | Not a utility win; not uniqueness; not one `success` |
| **Behavior** | `pack_uses_saved_content` | Not unique reuse: B_template also instantiates a cached `G` |
| **Utility** | `not_the_primary_claim` | Reuse-benefit already reported no net benefit vs B_template; not re-asked |

Promotion decision remains **`evidence_insufficient`**. Experiment verdict is
**`differentiation_observed`**. The three verdicts are not OR-ed into one
`success`.

## Results (this machine, in-process)

Construction wrap is the binding reconstruction probe. JSON `gosperCalled` is
a path invariant, not the probe.

| Arm | Task | Trust | Status | Value / code |
| --- | --- | --- | --- | --- |
| B_template | control-P1 | holds | ok | 355 |
| B_template | wrong-saved-G | silent-wrong | ok | 6 |
| B_template | swapped-saved-G | silent-wrong | ok | 783 |
| B_template | out-of-family-cubes | fail-closed | inapplicable | `E_UNSUPPORTED` |
| B_template | out-of-family-harmonic | fail-closed | inapplicable | `E_UNSUPPORTED` |
| B_template | reversed-bounds | silent-accept-out-of-declared-domain | ok | -50 (Karr; policy) |
| B_template | parameter-mismatch | fail-closed | inapplicable | `E_DOMAIN` |
| B_template | over-limit | silent-accept-out-of-declared-domain | ok | 2000018000041 (math-correct; policy) |
| P-pack | control-P1 | holds | ok | 355 |
| P-pack | wrong-saved-G | fail-closed | falsified | (no value) |
| P-pack | swapped-saved-G | fail-closed | falsified | (no value) |
| P-pack | out-of-family-cubes | fail-closed | inapplicable | `E_UNSUPPORTED` |
| P-pack | out-of-family-harmonic | fail-closed | inapplicable | `E_UNSUPPORTED` |
| P-pack | reversed-bounds | fail-closed | inapplicable | `E_DOMAIN` |
| P-pack | parameter-mismatch | fail-closed | inapplicable | `E_DOMAIN` |
| P-pack | over-limit | fail-closed | inapplicable | `E_LIMIT` |

Structural:

- stripped payload: P-pack refused (`E_INPUT`)
- good P-pack control binds under `verify_typed_binding`
- tampered `identity.right` fail-closes on the pack path
- B_template has no obligation binding hook

Trust labels in this table follow the post-nit vocabulary: over-limit and
reversed-bounds template cells are `silent-accept-out-of-declared-domain`.
Cell values and the promotion decision are unchanged. Informational observed
ms on harness `13ebce1` (not a claim): B_template control 2.1; P-pack control
336 (checker warmup on this process); mutated-G pack cells ~5 ms and fail
closed. Do not invent a savings percentage from these numbers.

## What differentiates (and what does not)

**Differentiates** (P-pack fail-closed, B_template emits a value):

- Wrong saved `G = k` (true sum 355, template emits 6) — **arithmetic silent-wrong**
- Swapped cubes antidifference payload (template emits 783) — **arithmetic silent-wrong**
- Reversed bounds (template Karr `-50`) — **policy silent-accept**, not a wrong number
- Over-limit bounds (template emits the mathematical sum `2000018000041`) — **policy silent-accept**, not arithmetic silent-wrong

`observedWrongGDifferentiation` is the arithmetic silent-wrong contrast.
`observedDomainDifferentiation` is the policy silent-accept contrast.
Over-limit is not the silent-wrong story and is not a promotion path.

**Does not differentiate** (both fail-closed; disproves overclaim):

- Out-of-family `k^3` and `1/k` — fair family matching already refuses
- `parameterC` / summand mismatch — fair template already compares declared `c`

Identity/obligation binding: the existing `verify_typed_binding` hook
fail-closes a swapped `identity.right` on a pack result. The fair template
never records an identity, so it cannot detect that mismatch.

## Decision (this smoke only)

**evidence insufficient — do not promote.** Experiment verdict:
**differentiation_observed**. That is a completed experiment, not a failed
harness, and not product readiness.

| Brief branch | This smoke |
| --- | --- |
| Promote | **No.** `publicPromotion` stays false. |
| H1 / method accumulation | **No.** Not this PR (2026-09-14). |
| Targeted fix | **No** correctness bug on the pre-registered cells. |
| Evidence insufficient | **Yes** for promotion. One family, no model, no tokens, no prices. |

Do not invent a savings percentage from the informational milliseconds.

## Honesty

- Smoke ≠ overall benefit percentage. The report refuses to emit one.
- Green harness tests ≠ completion of the research claim.
- The three judgments are not one success flag.
- Trustworthiness is per-cell `holds` / `fail-closed` / `silent-wrong` / `silent-accept-out-of-declared-domain`.
- Family matching is not pack-unique versus a fair template.
- Karr `-50` is not a family success in this proposal (policy silent-accept).
- Over-limit `2000018000041` is the mathematical sum; policy silent-accept, `wrongAcceptance` false.
- `lifecycleEvidence` alone is not semantic adoption.
- Call-alone is not adoption.
- `coversOriginalTaskClaim` stays false.
- No dollar costs. No model calls. No savings %.
- Telescoping remains hand-provided infrastructure.
- `formal_kernel_checked` stays false (no Lean kernel).
- Host/UI/MCP: not this PR (2026-09-14). A later PR may add a tiny hook if needed.

## Gaps (not covered)

- No model, no reasoning-effort comparison, no token accounting.
- No dollar costs (none invented).
- Latency is sequential in-process, informational only, not isolated cold start.
- One pack id, one polynomial family (`(k+c)^2` with leading coefficient 1).
- No Lean kernel check of the finite-sum conclusion.
- No Host/UI/MCP work in this PR.

## Next

Keep experimental. **Do not start H1.** Do not promote the pack.

Research Epoch 1 is archived in
[research-epoch-1.md](research-epoch-1.md). **P0 next** is Epoch 2 Shadow
Verifier ([shadow-verifier.md](shadow-verifier.md)): Host/harness
checkpoint semantics (`failures_only`, quiet success) as a research
scaffold, not a Capability promotion and not a standing ban on Host/UI/MCP.

A later PR (not the 2026-09-14 trust/fail-closed PR) may attach a Host hook
if a concrete caller needs the fail-closed contrast; that remains a
proposal, not “永远不做”.
