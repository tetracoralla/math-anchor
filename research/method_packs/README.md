# Experimental method packs (A2)

Research-only. **Not** a public Capability or Procedure, **not** a supported
Math Anchor domain module, **not** a fifth MCP tool.

This directory turns T1 solving intermediates into a verifiable experimental
method pack and applies that pack to a held-out second task without carrying
T1's antidifference or T1's numeric answer.

Frozen pack:
`polynomial_antidifference_gosper.v0/pack.json`

Novelty label (honest): **known-method-adaptation**. Gosper, Faulhaber, SymPy
summation, and the Math Anchor polynomial certificate checker already exist.
The hand-provided telescoping combination rule is A1 **infrastructure** and is
not counted as A2 novelty.

## Commands

Extract from T1 (writes evidence; does **not** run the held-out second task):

```sh
.venv/bin/python research/method_packs/run.py extract
```

Apply the frozen pack to the second task `sum_{k=1}^{20} k^3`:

```sh
.venv/bin/python research/method_packs/run.py apply \
  --task research/method_packs/examples/sum-k-cubed-1-to-20.json \
  --output build/method-pack-sum-k-cubed.json \
  --chain-output build/method-pack-sum-k-cubed-chain.json \
  --adoption-output build/method-pack-sum-k-cubed-adoption.json \
  --coverage-output build/method-pack-sum-k-cubed-coverage.json
```

Inapplicable input (must fail closed):

```sh
.venv/bin/python research/method_packs/run.py apply \
  --task research/method_packs/examples/inapplicable-1-over-k.json
```

Tests:

```sh
.venv/bin/python -m pytest \
  tests/python/test_method_pack_proposal.py \
  tests/python/test_polynomial_finite_sum_proposal.py \
  tests/python/test_coverage_proposal.py \
  tests/python/test_parameterized_method_pack.py
```

## Parameterized pack (batch 2)

Separate experimental id
`math-anchor.research.method-pack.shifted-square-antidifference.v0`.
It stores a parametric `G(k,c)` for sums of `(k+c)^2`. Apply instantiates
that `G`; it does not call Gosper. The A2 Gosper pack above is unchanged
and still reconstructs.

```sh
.venv/bin/python research/method_packs/run.py extract-shifted-square

.venv/bin/python research/method_packs/run.py apply \
  --pack research/method_packs/shifted_square_antidifference.v0/pack.json \
  --task research/method_packs/examples/shifted-square-held-out-c3-2-to-7.json
```

See `docs/research/ai-for-math/parameterized-method.md` for provenance,
the mandatory “what math is saved” claim, and honesty limits. Equal-budget
no-model timing: `docs/research/ai-for-math/parameterized-cost-smoke.md`.
Strong-baseline reuse-benefit smoke (B0 / B1 / B_template / B_codegen /
P-pack; three separate judgments):
`docs/research/ai-for-math/reuse-benefit.md`.

## Mathematical scope

Univariate rational-coefficient polynomials, constant denominators only,
inclusive integer bounds, empty sum when `upper == lower - 1`. Reversed bounds
and `1/k` are unsupported. Identity assurance is `exact_symbolic`. The
conclusion is never `formal_kernel_checked`.

## Second task

`sum_{k=1}^{20} k^3` (expected `44100`). This is not a rename of T1
(`k^2`, `1..10`, `385`): different degree, bounds, and value.

An extra in-domain example, `examples/hockey-stick-c-k-2-rewritten.json`,
applies the same pack after a caller-declared rewrite `C(k,2)=k(k-1)/2`. That
rewrite stays **conditional**.

## Lifecycle

| State | Where |
| --- | --- |
| candidate | proposed from T1 in `extract.py` |
| verified-in-declared-scope | frozen `pack.json` after T1/T3/T4 plus negatives |
| cross-task-use-evidence | adoption record from `apply` on a non-T1 task |

Replaying T1 (`k^2` on 1..10, or `taskId` equal to `provenance.extractionTaskId`)
does not mint `cross-task-use-evidence`.
