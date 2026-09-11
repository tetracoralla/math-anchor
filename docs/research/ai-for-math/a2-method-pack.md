# A2: experimental method pack from T1 (polynomial antidifference)

This note is a research report, not a product Capability and not a claim of
statistical reuse benefit. A1 is unchanged. Agent Host, the four MCP tools, the
human calculator UI, and Skill Refinery are unchanged.

## What was extracted

From T1 (`sum_{k=1}^{10} k^2`, A1 example
`research/polynomial_finite_sum_proposal/examples/sum-k-squared-1-to-10.json`):

- Construction of a discrete antidifference `G` with SymPy
  `gosper_sum` (summation fallback).
- Obligation shape: independently check `G(k+1)-G(k)=p(k)` as a
  `polynomial_identity`.
- Restricted instantiate interface for later finite sums of univariate
  QQ-polynomials.

**Not extracted (infrastructure, not A2 novelty):** the hand-provided
telescoping combination rule
`math-anchor.research.discrete-telescoping-combination.v0`.

Frozen pack:
`research/method_packs/polynomial_antidifference_gosper.v0/pack.json`.

## Novelty status

**known-method-adaptation.** Not rediscovery-as-new, not unproven-new, never
auto-claimed.

Gosper (1978) / *A = B*, Faulhaber's formula for `sum k^m`, SymPy 1.14.0
`gosper_sum`/`summation`, and Math Anchor's stdlib polynomial certificate
checker already cover construction and identity checking. If the only required
output is the number, SymPy is enough. The pack is a retrieve/instantiate
evidence wrapper, not new mathematics.

## Domain

Univariate rational-coefficient polynomial `p(k)`, constant denominators only,
inclusive integer bounds with `|a|,|b| <= 10^6`, empty sum when
`upper == lower - 1`. Reversed bounds (`upper < lower - 1`), `1/k`, special
functions, extra symbols, and infinite sums are unsupported.

Identity assurance: `exact_symbolic`. Whole conclusion: **not**
`formal_kernel_checked`.

In-scope verification used to enter the executable library (not a universal
proof): T1 `k^2` on `1..10`, empty sum, and `(2k+1)/3` on `0..2`. The held-out
second task was not part of that set.

## Second task (chosen)

`sum_{k=1}^{20} k^3`, expected `44100`.

T1 is `k^2` on `1..10` with value `385` and
`G = (1/3)k^3 - (1/2)k^2 + (1/6)k`. The second task is a different Faulhaber
degree, different bounds, and a different value. Apply constructed
`G = (1/4)k^4 - (1/2)k^3 + (1/4)k^2` from Gosper, checked
`G(k+1)-G(k)=k^3` with the stdlib certificate checker, then combined endpoints
with the infrastructure telescoping rule. T1's `G` and `385` are not inputs.

Primary rejection: `1/k` (non-constant denominator) → `E_UNSUPPORTED`.

Additional in-domain reuse (not the chosen second task): hockey-stick after an
explicit caller rewrite `C(k,2)=k(k-1)/2` for `k=2..10` (value `165`). The
binomial identity remains a **conditional** premise; the pack does not check
it.

## Lifecycle

| State | Artifact |
| --- | --- |
| candidate | proposed in `research/method_packs/extract.py` from T1 |
| verified-in-declared-scope | frozen `pack.json` after T1/T3/T4 plus negatives |
| cross-task-use-evidence | adoption record from `apply` on a task that is not T1 (`k^2` on 1..10 / extraction `taskId`) |

Replaying T1 through `apply` keeps `lifecycleEvidence` at pack status
(`verified-in-declared-scope`). It does not mint cross-task evidence.

## Commands and artifacts

```sh
.venv/bin/python research/method_packs/run.py extract

.venv/bin/python research/method_packs/run.py apply \
  --task research/method_packs/examples/sum-k-cubed-1-to-20.json \
  --output build/method-pack-sum-k-cubed.json \
  --chain-output build/method-pack-sum-k-cubed-chain.json \
  --adoption-output build/method-pack-sum-k-cubed-adoption.json

.venv/bin/python research/method_packs/run.py apply \
  --task research/method_packs/examples/inapplicable-1-over-k.json

.venv/bin/python -m pytest \
  tests/python/test_method_pack_proposal.py \
  tests/python/test_polynomial_finite_sum_proposal.py
```

Evidence from extraction lives under
`research/method_packs/polynomial_antidifference_gosper.v0/evidence/`.
Apply writes chain and adoption next to `--output` (refuses to overwrite).

## Gaps (not covered)

- No Lean kernel check of the finite-sum conclusion.
- No checker for non-constant denominators / general hypergeometric terms.
- The binomial rewrite for hockey-stick is not verified by this pack.
- No model, no equal-budget B0/B1/B2, no token or dollar cost (placeholders only).
- No claim→obligation coverage table (that is A3).
- Structure validation of `pack.json` is not mathematical correctness.
- A few in-scope instances are not a proof for all degrees below the checker limit.

## Next minimal experiment (A3)

Record, for this same domain workflow: task/source claim → generated obligation
id; declared goal, bounds, and assumptions; which steps the fixed rules cover
and which semantic steps they do not; typed binding of the computed value into
later parameters; exact evidence scope. Add mutation tests (wrong certificate
binding, forged verified, result rewritten between tools). Do not add a general
obligation dataflow language to do that.
