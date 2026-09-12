# Polynomial finite-sum proposal (A0 + A1)

Research proposal, not a supported Math Anchor domain module.

One command constructs `G` with SymPy Gosper/summation, checks
`G(k+1)-G(k)=p(k)` with the independent polynomial certificate checker, applies
a **hand-provided** telescoping rule, and returns the exact sum plus evidence.
No Agent Host and no model.

## Commands

Checked vertical (default example: `sum_{k=1}^{10} k^2 = 385`):

```sh
.venv/bin/python research/polynomial_finite_sum_proposal/run.py \
  --task research/polynomial_finite_sum_proposal/examples/sum-k-squared-1-to-10.json \
  --output build/polynomial-finite-sum.json \
  --receipt-output build/polynomial-finite-sum-receipt.json
```

No-model SymPy baseline only:

```sh
.venv/bin/python research/polynomial_finite_sum_proposal/run.py \
  --baseline-only --summand 'k^2' --lower 1 --upper 10
```

Claim→obligation coverage sidecar (A3):

```sh
.venv/bin/python research/polynomial_finite_sum_proposal/run.py \
  --task research/polynomial_finite_sum_proposal/examples/sum-k-squared-1-to-10.json \
  --coverage-output build/polynomial-finite-sum-coverage.json
```

Wrong coefficients (must falsify, exit 1):

```sh
.venv/bin/python research/polynomial_finite_sum_proposal/run.py \
  --task research/polynomial_finite_sum_proposal/examples/wrong-antidifference.json
```

Reversed bounds and `1/k` must fail closed (exit 2).

Tests:

```sh
.venv/bin/python -m pytest \
  tests/python/test_polynomial_finite_sum_proposal.py \
  tests/python/test_coverage_proposal.py
```

## Mathematical scope

- Univariate rational-coefficient polynomial `p(k)`, constant denominators only.
- Inclusive integer bounds; empty sum when `upper == lower - 1`.
- `upper < lower - 1` is unsupported (not Karr's negative reversed sum).
- Identity assurance is `exact_symbolic`. The conclusion is never marked
  `formal_kernel_checked` in this proposal.
- The combination rule id
  `math-anchor.research.discrete-telescoping-combination.v0` is infrastructure,
  not an Agent-extracted method.

## Honest limit

SymPy `summation` already computes the value. This runner exists to separate
construction, independent checking, bound conventions, and combination, and to
emit a replayable receipt. It does not discover new identities.
