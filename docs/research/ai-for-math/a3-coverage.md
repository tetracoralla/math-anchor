# A3: claim → obligation coverage for the polynomial finite-sum workflow

This note is a research report, not a product Capability and not a claim that
checked obligations cover the original finite-sum task. A1 and A2 are
unchanged in mathematical behaviour. Agent Host, the four MCP tools, the
human calculator UI, and Skill Refinery are unchanged.

## What changed (user-visible for this vertical)

For the **same** polynomial finite-sum / method-pack workflow, the relationship
between the structured task claim and the submitted checks is now explicit:

- one generated obligation id, `difference-identity` (`polynomial_identity`);
- declared goal, integer-bound convention, and `bound_not_evaluated` assumptions;
- which steps fixed rules cover and which they do not;
- a typed binding of the exact rational `G(upper+1)-G(lower)` into `value` /
  method-pack `downstream` / chain `valueEnteredLaterSteps`;
- the exact evidence scope, including that instances are not a universal proof.

The recorder is ordinary Python
(`research/polynomial_finite_sum_proposal/coverage.py`). It is not a general
obligation dataflow language, not a fifth MCP tool, and not an NL→claim
compiler. The A1 runner still emits a single obligation with unused
`dependsOn`. Telescoping remains hand-provided infrastructure.

## Commands and artifact paths

Frozen workflow table (no instance digests):

`research/polynomial_finite_sum_proposal/workflow_coverage.json`

T1 coverage alongside the A1 runner:

```sh
.venv/bin/python research/polynomial_finite_sum_proposal/run.py \
  --task research/polynomial_finite_sum_proposal/examples/sum-k-squared-1-to-10.json \
  --coverage-output build/polynomial-finite-sum-coverage.json
```

Held-out cubes coverage alongside method-pack apply:

```sh
.venv/bin/python research/method_packs/run.py apply \
  --task research/method_packs/examples/sum-k-cubed-1-to-20.json \
  --coverage-output build/method-pack-sum-k-cubed-coverage.json
```

Mutation / negative catalog:

```sh
.venv/bin/python -m research.polynomial_finite_sum_proposal.mutations
```

Tests:

```sh
.venv/bin/python -m pytest \
  tests/python/test_coverage_proposal.py \
  tests/python/test_polynomial_finite_sum_proposal.py \
  tests/python/test_method_pack_proposal.py
```

`--coverage-output` refuses to overwrite. Large receipts stay local artifacts;
the coverage record stores obligation id, digests, and binding, not a second
copy of the full receipt.

## What is covered

| Step | Coverage | What it actually establishes |
| --- | --- | --- |
| Parse univariate QQ-polynomial | fixed Python rule | Constant-denominator univariate `p(k)` |
| Integer bounds / empty / reversed | fixed Python rule + combination-rule gate | Inclusive integers; empty sum `upper == lower - 1`; reject `upper < lower - 1` |
| `G(k+1)-G(k)=p(k)` | obligation `difference-identity` | That identity, as rational polynomials, `exact_symbolic` |
| Endpoint evaluation | independent checker parser | Exact rationals `G(upper+1)` and `G(lower)` |
| `G(upper+1)-G(lower)` | hand-provided infrastructure `math-anchor.research.discrete-telescoping-combination.v0` | Finite-sum **value** after the identity is checked and bounds are in domain |
| Typed binding of that value | domain Python (`verify_typed_binding`) | Recorded `value` / `downstream` match independent recomputation; current `G` must be the `G` named by the checked identity |

On T1 (`sum_{k=1}^{10} k^2`) and the held-out cubes task, the identity
obligation is checked, the procedure can establish the finite-sum **value**,
and the binding recomputes to `385` and `44100` respectively.

## What is not covered

Obligation success is **not** claim coverage. Even when
`difference-identity` is `checked` and the procedure returns a value:

| Step | Why it is uncovered |
| --- | --- |
| Natural language → structured claim | No compiler. Inputs are already JSON. |
| Construction of `G` | Gosper/summation is untrusted construction, not a proof. |
| Binomial rewrite `C(k,2)=k(k-1)/2` | Hockey-stick remains a conditional caller premise. |
| Telescoping as an obligation or as A2 novelty | Infrastructure; `agentExtracted: false`. |
| Whole finite-sum conclusion in Lean | `formalKernelChecked` stays false. |
| Universal quantification over the family | A few instances ≠ a proof for every degree below the checker limit. |
| Assumption prose | Hash-bound, `bound_not_evaluated`. |
| Authorship or mathematical truth beyond the checker statement | Hash consistency binds **content** only. |
| Semantic adoption | A2 `lifecycleEvidence` is still not B2-minus. |

`coversOriginalTaskClaim` is always `false` in this workflow's coverage
record. `procedureEstablishedFiniteSumValue` can be true without covering the
original task claim.

Feedback uses existing `full` / `failures_only`. The runner still requests
`full` internally so it can read receipt fields. The outer compute surface
returns the value and necessary conditions; a background-check projection is
`failures_only` and does not swallow `unsupported`/`falsified`/`unknown`.
No new public `responseMode`.

## Mutation / negative tests added

Implemented in `research/polynomial_finite_sum_proposal/mutations.py` and
`tests/python/test_coverage_proposal.py`. Combination-rule unit tests stay in
`tests/python/test_polynomial_finite_sum_proposal.py` and are not reused as
hash-binding proofs. The hash-only path never calls
`apply_finite_telescoping_sum`.

| Mutation | Required behaviour |
| --- | --- |
| Tampered certificate coefficients (re-hashed) | Certificate internally inconsistent; does not bind |
| Wrong `G` (`k^3/3` for `k^2`) | Identity `falsified`; no finite-sum value |
| Deleted bound step + raw reversed subtraction | Checked identity does **not** establish a finite sum; typed binding rejects |
| Reversed bounds | `E_DOMAIN`; no obligation generated; not a falsified proposition |
| Wrong variable (`k^2` with index `n`; cert variables `n` vs `k`) | `E_UNSUPPORTED` and/or certificate does not match claim |
| Wrong domain `1/k` | `E_UNSUPPORTED`; not a counterexample |
| Certificate from T1 attached to the cubes identity | `certificate_statement_does_not_match_claim` |
| Forged `verifiedByPack` | Apply rejected |
| Forged `formalKernelChecked` | Coverage refuses to record it |
| Stale / unexpected pack version | Apply `stale_or_unexpected_pack_version` |
| Result rewritten (`value` or chain `valueEnteredLaterSteps`) | Typed binding `E_RUNTIME` |
| Joint rewrite of `G` and `value` leaving stale `identity.status=checked` | Typed binding `E_RUNTIME`; current `G` must match `identity.left` |
| `unsupported` treated as a counterexample | Explicitly classified as **not** proposition-false |

`--baseline-only` / baseline results with no receipt and no identity object
emit `generatedObligations=[]`. They do not synthesize a phantom
`difference-identity`. `coversOriginalTaskClaim` stays false.

## Honesty

- Success of submitted obligations ≠ coverage of the original task claim.
- A coverage sidecar without a receipt and without an identity object does
  not invent a `difference-identity` obligation. Baseline `kind` stays
  `sympy_summation_baseline`; source is not `unknown`.
- Typed binding binds current `G` to the checked identity statement
  (`identity.left` must be `G(k+1)-G(k)` for that `G`) before recording an
  established finite-sum value. Value-only rewrites remain rejected.
- Hash consistency binds content, not authorship or math truth, and does not
  apply the telescoping rule.
- `formal_kernel_checked` remains false unless Lean checks the whole
  conclusion (it does not).
- Telescoping remains hand-provided infrastructure, not extracted novelty.
- Pack JSON is still not an interpreter: engines are not dispatched.
- Structure validation is still not mathematical correctness.
- `apply().adoption.lifecycleEvidence` is still not semantic adoption. A4
  ran B2-minus on held-out cubes because a reuse *signal* appeared; that is
  still not semantic adoption ([a4-smoke.md](a4-smoke.md)).

## Gaps (not covered)

- No Lean kernel check of the finite-sum conclusion.
- No NL→claim compiler, and none is planned as a v0.1 obligation feature.
- No general obligation dataflow; typed binding is domain Python for this
  one value.
- Hockey-stick binomial rewrite still unverified.
- No checker for non-constant denominators / general hypergeometric terms.
- No model and no dollar cost. Equal-budget no-model smoke is in
  [a4-smoke.md](a4-smoke.md); it is not a benefit percentage.
- Loader still admits only this one pack id.
- Pack `engine` strings remain documentation, not dispatch.

## Next minimal experiment (after A4)

A4 no-model smoke: [a4-smoke.md](a4-smoke.md). Decision from that smoke:
**evidence insufficient — do not promote.** Keep experimental. Do not start
H1. Expand the neighborhood only if a later authorized experiment shows work
B0 cannot already do on this family.
