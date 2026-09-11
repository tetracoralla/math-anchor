# Parameterized method pack: sums of `(k+c)^2`

This note is a research report, not a product Capability and not a claim of
statistical reuse benefit or new mathematics. A1–A4 and the F1–F5 binding
fixes are unchanged. Agent Host, the four MCP tools, the human calculator UI,
and Skill Refinery are unchanged.

## Mandatory claim

这个方法包相对不带包的 B1 流程，额外保存了什么数学信息；未来哪一步工作可以因此不再重复？

相对不带包的 B1，这个包额外保存了参数化反差分
`G(k,c)=k(k-1)(2k-1)/6 + c k(k-1) + c^2 k`，以及可检查的二元恒等式
`G(k+1,c)-G(k,c)=(k+c)^2`。对未见过的有理数 `c` 与整数边界，apply
代入该 `G`、检查适用条件、再查实例恒等式并做望远镜组合，不必再对每个
`(c,a,b)` 运行 Gosper 或待定系数构造。身份检查仍会做；省下的是构造，
不是证明义务。

If the honest answer were only “labels/call rules but the same solver every
time”, this experiment would not be finished. The A2 Gosper pack still
reconstructs `G` on every task; this pack does not.

## What was extracted

From P0 `sum_{k=0}^{4} (k+1)^2` (value `55`):

- Monomial antidifferences of `1`, `k`, and `k^2` by undetermined
  coefficients over `Q` (`research/method_packs/shifted_square.py`).
- Linearity: `G(k,c) = G_{k^2}(k) + 2c G_k(k) + c^2 G_1(k)`.
- Frozen source
  `k*(k - 1)*(2*k - 1)/6 + c*k*(k - 1) + (c**2)*k`.

**Not extracted (infrastructure):** the hand-provided telescoping rule
`math-anchor.research.discrete-telescoping-combination.v0`.

Frozen pack:
`research/method_packs/shifted_square_antidifference.v0/pack.json`.

## Provenance

**known-method-adaptation.** Not rediscovery-as-new, not unproven-new, never
auto-claimed.

Faulhaber's formula for `sum k^2`, discrete polynomial antidifferences, and
Gosper already exist. The formula was derived in-tree by solving
`G(k+1)-G(k)=k^n` for `n=0,1,2` and combining; it was not pasted from an
external page as “agent-extracted”. The independent stdlib polynomial
certificate checker verifies the bivariate identity. Telescoping remains A1
infrastructure.

## Domain

Family: inclusive finite sums of `(k+c)^2` for rational `c` and integer
bounds with `|a|,|b| <= 10^6`. Empty sum when `upper == lower - 1`. Leading
coefficient of the quadratic must be 1.

Unsupported: `k^3`, quadratics that are not `(k+c)^2` (example
`k^2+6k+8`), `1/k`, special functions, non-rational `c`, reversed bounds,
caller-supplied `G` (reconstruction is disabled).

Identity assurance: `exact_symbolic`. Whole conclusion: **not**
`formal_kernel_checked`.

## General vs instance

| Layer | What is checked | What it is not |
| --- | --- | --- |
| General | `G(k+1,c)-G(k,c)=(k+c)^2` as a bivariate polynomial identity in `(k,c)`, from the pack payload, on every apply | A Lean kernel theorem; a proof for other templates |
| Instance | After substituting this task’s rational `c`, `G_c(k+1)-G_c(k)=(k+c)^2` in one variable | A second general proof. It is a separate program step so a bad substitution or a tampered `G` still fails closed |
| Bounds / value | Integer bounds, empty-sum convention, `G(b+1,c)-G(a,c)` | Covered by the identity obligation |

A checked general identity plus in-domain `c` implies the instance if
substitution is correct. We still re-check the instance.

## Apply path (reconstruction disabled)

For a new `(c,a,b)`:

1. Check applicability (template `(k+c)^2`, rational `c`, integer bounds).
2. Instantiate the saved `G` by substituting `c`. **Do not** call
   `gosper_sum` or re-run undetermined coefficients.
3. Independently check the general bivariate identity from the payload, then
   the univariate instance identity.
4. Apply infrastructure telescoping `G(b+1)-G(a)`.
5. Fail closed out of domain.

Structural proof: tests monkeypatch `gosper_sum` and
`construct_antidifference` to explode; the held-out task still completes.
Stripping `parametricAntidifference` from the pack makes that path refuse
even though B1 could still construct. Wrong saved `G` is falsified; no sum
is emitted.

## Fair B1 / SymPy baseline

B1 (`run_polynomial_finite_sum`) and B0 (`sympy_finite_sum`) are **not**
crippled. They may still construct. Equal-budget comparisons must keep those
paths intact. Optional `compare_baseline` on the pack path uses SymPy
*summation of the original summand* as a value check, not Gosper
construction of `G`.

## Held-out and negatives

| Task | Input | Expectation |
| --- | --- | --- |
| P0 extraction | `(k+1)^2`, `c=1`, `0..4` | `55` (replay is not cross-task evidence) |
| P1 held-out | `(k+3)^2`, `c=3`, `2..7` | `355` (different `c` and bounds) |
| P2 extra | `(k+1/2)^2`, `c=1/2`, `1..3` | `83/4` |
| Wrong template | `k^3` or `k^2+6k+8` | `E_UNSUPPORTED`, fail closed |
| Harmonic | `1/k` | `E_UNSUPPORTED`, fail closed |
| Reversed bounds | `upper < lower - 1` | `E_DOMAIN`, fail closed |

P1 is not a rename of P0.

## Commands

```sh
.venv/bin/python research/method_packs/run.py extract-shifted-square

.venv/bin/python research/method_packs/run.py apply \
  --pack research/method_packs/shifted_square_antidifference.v0/pack.json \
  --task research/method_packs/examples/shifted-square-held-out-c3-2-to-7.json

.venv/bin/python research/method_packs/run.py apply \
  --pack research/method_packs/shifted_square_antidifference.v0/pack.json \
  --task research/method_packs/examples/shifted-square-inapplicable-k-cubed.json

.venv/bin/python -m pytest tests/python/test_parameterized_method_pack.py
```

## Honesty limits

- This is one family, not a general method extractor.
- Saving `G(k,c)` avoids reconstructing *this* antidifference. It does not
  make polynomial finite sums cheaper in general, and it does not beat SymPy
  when only a number is required.
- No model. No dollar cost. No Host/UI/MCP change. Not a public Capability.
- `cross-task-use-evidence` is not semantic adoption.
- Next cost experiment is only now well-posed: compare B1 (may construct)
  against this apply path (must not construct) on a pre-registered list of
  `(c,a,b)` with reconstruction disabled on the pack arm. Do not invent
  savings before that run.
