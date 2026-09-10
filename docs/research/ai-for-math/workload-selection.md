# Workload selection (A0)

Chosen first-round flow: **inclusive finite sums of a univariate
rational-coefficient polynomial**, verified through a discrete difference
identity.

This is the brief's default. Current-HEAD evidence did not support replacing it
with another exact-algebra flow already covered by Math Anchor.

## Why this flow

1. Construction already exists in the lockfile (`sympy.concrete.gosper.gosper_sum`,
   `sympy.summation`). A1 does not rewrite Gosper.
2. Verification already exists: `certificate.polynomial_identity` plus
   `certificate_checker` (rational polynomials, **constant denominators only**).
3. The missing piece is a *combination rule*, not a new CAS: once
   `G(k+1)-G(k)=p(k)` is checked and `a,b` are integers with `b >= a-1`,
   `sum_{k=a}^{b} p(k) = G(b+1)-G(a)`.
4. The domain can be stated strictly enough to fail closed: no extra parameters,
   no special functions, no infinite sums, no Karr reversed sums.

The A1 sample is
`research/polynomial_finite_sum_proposal/`. It is a proposal runner, not a
supported domain module.

## Domain of the first vertical

- Summand `p(k)`: univariate polynomial in one index, coefficients in `Q`.
  Division is allowed only by a nonzero rational constant (the checker grammar).
- Bounds `a,b`: Python integers, `|a|,|b| <= 10^6`, inclusive.
- Empty sum: `b = a - 1` equals `0`.
- Reversed bounds: `b < a - 1` is **unsupported**, not a negative sum.
- Construction: SymPy Gosper, with `summation` only if Gosper returns `None`.
- Check: one `polynomial_identity` obligation on `G(k+1)-G(k)` vs `p(k)`.
- Combination: `math-anchor.research.discrete-telescoping-combination.v0`,
  hand-provided infrastructure, not Agent-extracted.
- Assurance: `exact_symbolic` for the identity. The whole conclusion is **not**
  `formal_kernel_checked`.

## Why not the other covered exact-algebra flows

### Expression equivalence (`expression.equivalent`)

Already a one-shot provider: two expressions, a domain, a definedness policy.
There is no construct-then-combine gap, and no independent coefficient
certificate. Using it for A1 would only re-demo an existing operation.

Deferred as a later consumer of *results*, not as the first method-shaped
workflow.

### Local almost-complex check (`geometry.almost_complex.local_check`)

Covered, tested, and deliberately chart-local. It does not produce a reusable
finite-sum method. The roadmap already warns against promoting the S6 case study
into the product kernel.

Deferred.

### Dimensional consistency

Exact, but it checks dimensions only. It is not an algebraic identity workflow.

Deferred.

### Lean kernel on polynomial identities

Useful later for the *same* identity `G(k+1)-G(k)=p(k)`, not as a substitute
for constructing and combining a finite sum. Not every environment has Lean.
A1 therefore constructs, checks, and combines without marking kernel acceptance.

## Why not hypergeometric sums beyond polynomials

Gosper can sum many hypergeometric terms (`1/k` fails; some factorial ratios
succeed). The independent checker **cannot** verify those identities: it rejects
non-constant denominators. Expanding A1 to rational *functions* would require a
new checker, which is not a finished vertical.

Out of domain in this pass: `1/k`, special functions, symbolic limits, infinite
sums.

## Comparison with the no-model baseline

The baseline is `sympy.summation` on the same summand and bounds. On in-domain
tasks the checked path must agree with it. On reversed bounds they **disagree
by design**: SymPy returns a Karr negative sum; the proposal returns
`unsupported`. That disagreement is a convention test, not a numerical defect.
