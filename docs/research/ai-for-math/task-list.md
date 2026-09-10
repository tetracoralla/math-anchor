# Candidate multi-step tasks (A0)

These are inputs for later method extraction (A2) and equal-budget evaluation
(A4). A1 implements only the polynomial finite-sum slice. Putnam smokes already
in the repo are listed as pipeline regressions, not as research workloads.

Each row records source, goal, complete input, acceptance, likely repeated
steps, and reusable intermediates.

## Selected for A1 (in domain)

### T1. Sum of squares, Faulhaber specialization

- **Source:** SymPy Concrete documentation identity
  `Sum(k**2, (k, 1, m)).doit() = m**3/3 + m**2/2 + m/6`
  (https://docs.sympy.org/latest/modules/concrete.html). Public docs.
- **Goal:** `sum_{k=1}^{10} k^2`.
- **Input:** `summand=k^2`, `variable=k`, `lower=1`, `upper=10`.
- **Acceptance:** exact `385`; identity `G(k+1)-G(k)=k^2` independently checked;
  combination rule applied; not `formal_kernel_checked`.
- **Repeated steps:** construct `G`, expand difference, substitute bounds.
- **Intermediates:** `G(k)=k(k-1)(2k-1)/6`, difference certificate, `G(11)-G(1)`.
- **A1 status:** implemented (`examples/sum-k-squared-1-to-10.json`).
- **A2 status:** extraction source for experimental pack
  `math-anchor.research.method-pack.polynomial-antidifference-gosper.v0`.

### T2. Sum of first n integers

- **Source:** same SymPy page, `Sum(k, (k, 1, m)).doit() = m**2/2 + m/2`.
- **Goal:** `sum_{k=1}^{100} k`.
- **Input:** `k`, `1`, `100`.
- **Acceptance:** `5050`.
- **Repeated steps:** same chain as T1 with a different polynomial.
- **Intermediates:** `G(k)=k(k-1)/2`.
- **A1 status:** covered by the same runner; useful as a second instance, not a
  second method.

### T3. Empty-sum convention

- **Source:** Karr empty-sum clause as documented by SymPy; Wikipedia empty sum.
  This proposal **agrees** on `b=a-1 => 0` and **rejects** Karr reversal.
- **Goal:** `sum_{k=5}^{4} k^2 = 0`.
- **Input:** `examples/empty-sum.json`.
- **Acceptance:** `0`, identity still checked.
- **Repeated steps:** bound handling without a special CAS empty-sum rewriter.
- **Intermediates:** `G(5)-G(5)=0`.

### T4. Arithmetic polynomial with constant denominator

- **Source:** same finite-sum convention; `p(k)=(2k+1)/3` is still a `QQ`
  polynomial (`k^2/3` antidifference).
- **Goal:** `sum_{k=0}^{2} (2k+1)/3`.
- **Acceptance:** `3`.
- **Repeated steps:** rational coefficients through the checker grammar
  (`integer/integer`).
- **Intermediates:** `G(k)=k^2/3`.

## Negative tasks (must fail or unsupported)

### N1. Wrong antidifference coefficients

- **Source:** constructed as a checker-binding adversarial case (same class as
  the obligation runtime's "valid certificate for a different statement" seam).
- **Input:** `examples/wrong-antidifference.json` (`G=k^3/3` for `p=k^2`).
- **Acceptance:** identity `falsified`; no sum value; exit status 1.

### N2. Reversed bounds

- **Source:** contrast with SymPy/Karr (`summation(k**2,(k,5,1))=-29` on this
  machine).
- **Input:** `lower=5`, `upper=1`.
- **Acceptance:** `unsupported` / `E_DOMAIN`, not `-29`.

### N3. Non-constant denominator / special function

- **Source:** Gosper docs use `1/k` and factorial ratios; the checker forbids
  them.
- **Input:** `1/k` or `sin(k)`.
- **Acceptance:** `E_UNSUPPORTED` before a fake numerical sum.

## Recorded but not selected as the A1 method (6–10)

### T5. Putnam 1976 A2 (existing smoke)

- **Source:** `evals/research/putnam-1976-a2-n4.json` and `...-n18.json`; MAA
  Putnam archive.
- **Goal:** the specialized Putnam instance already in-repo.
- **Role:** **pipeline regression only**. Do not call it a research workload.
- **Why not A1:** not a polynomial finite-sum identity; already has an eval
  harness.

### T6. Putnam 2023 B1 specialized binomial

- **Source:** `evals/research/public-math-smoke.md`; official 2023 Putnam PDF;
  oracle `math.comb(99, 36)`.
- **Role:** public-math smoke, not A1.
- **Possible later reuse:** binomial counts, not discrete antidifferences.

### T7. NIST Hilbert stability classification

- **Source:** public-math smoke; NIST Matrix Market Hilbert page.
- **Role:** numerical/stability smoke. Out of the exact-algebra first vertical.

### T8. A=B / Gosper hypergeometric worked example

- **Source:** Petkovšek, Wilf, Zeilberger, *A = B*, AK Peters, 1997, pp. 73–100,
  cited by SymPy `gosper_sum`; example
  `f=(4k+1) k! / (2k+1)!`.
- **Goal:** closed hypergeometric sum.
- **Why not A1:** the independent checker cannot verify the rational-function
  identity. Candidate for a later checker family, not this vertical.

### T9. Hockey-stick identity (binomial transform)

- **Source:** standard binomial identity
  `sum_{i=r}^{n} C(i,r) = C(n+1, r+1)`; appears throughout Concrete Mathematics
  and as a corollary of the discrete derivative of `C(k, r+1)`.
- **Why not A1:** `C(k,r)` is polynomial in `k` for fixed `r`, so a later A2
  instance can reuse T1's method after rewriting `C(k,2)=k(k-1)/2`. That rewrite
  is itself a method-extraction target, not a second A1 runner.

### T10. Dimensional consistency of a drag Pi-matrix (existing smoke)

- **Source:** public-math smoke Buckingham Pi task.
- **Why not A1:** already a provider; no construct-G-then-telescope shape.

## A2-oriented notes

Reusable intermediates from T1–T4, if extracted later, are:

- the polynomial antidifference constructor (already in SymPy; mark as
  **known-method adaptation**, not a discovery);
- the checked difference-identity obligation shape;
- the hand-provided telescoping rule (infrastructure; **do not count as
  Agent-extracted**);
- the fail-closed bound convention.

A second task that is not a variable rename should, for example, take T9 after
an explicit binomial-to-polynomial rewrite, or a different polynomial such as
`k^3`, not `k^2` from 1 to 11.

A2 chose `sum_{k=1}^{20} k^3` as the held-out task and kept `1/k` as the
inapplicable rejection. T9 after `C(k,2)=k(k-1)/2` is an extra in-domain apply
with the binomial rewrite left conditional. See [a2-method-pack.md](a2-method-pack.md).
