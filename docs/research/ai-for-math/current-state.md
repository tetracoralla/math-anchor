# Current state vs capabilities (A0)

Review SHA: `1be6afe70b11c7434a51356c805444eafa12ed80` (pyproject 0.7.1).
This note is a research snapshot, not a claim that the A0/A1 proposal is a
supported product module.

Evidence labels are kept separate on purpose:

- **source**: the file exists in this checkout or was fetched at a pinned SHA.
- **tests**: automated tests exist in this checkout.
- **run**: this implementation pass executed it on this machine.
- **used**: observed in a real multi-step mathematical workflow, not only a unit test.
- **benefit**: comparative quality or cost evidence against a matched baseline.

Absent labels are not implied by the others.

## Math Anchor in this checkout

| Capability | source | tests | run | used | benefit |
| --- | --- | --- | --- | --- | --- |
| Obligation runtime `src/math_anchor/obligations.py` | yes | `tests/python/test_obligations.py`, `evals/obligations/core.v0.1.json` | yes: selected pytest plus the A1 runner's identity check | no real research-task trace in this pass | none |
| Independent polynomial certificate checker `src/math_anchor/certificate_checker.py` | yes | `test_research_contract.py`, obligation mapping tests | yes | no | none |
| `certificate.polynomial_identity` producer | yes | `test_research_contract.py` | yes | no | none |
| Expression equivalence, dimension check, local almost-complex providers | yes | obligation and operation tests exist | not re-run this pass | no | none |
| CLI `check-obligations` / `verify-certificate` | yes | CLI and obligation tests | not the packaged CLI this pass; library `check_obligation_set` was used | no | none |
| Cost script `script/measure_obligation_cost.py` | yes | `test_agent_cost.py` | not this pass | no | no dollar or token savings |
| Lean/Pantograph kernel bridge | source and docs exist; optional | `test_lean_bridge.py` | not this pass; Lean is not required for A1 | no | none |
| Four public MCP tools | yes | MCP/transport tests exist | not this pass | no | none |
| Human macOS calculator | yes | Swift tests exist | not this Linux pass | n/a | n/a |

Ran on this machine after `./script/bootstrap.sh`:

- `.venv/bin/python -m pytest tests/python/test_research_contract.py::test_polynomial_identity_certificate_passes_the_independent_checker tests/python/test_obligations.py::test_obligation_schemas_are_valid_and_outputs_validate`
- `.venv/bin/python -m pytest tests/python/test_polynomial_finite_sum_proposal.py`
- the proposal CLI on `examples/sum-k-squared-1-to-10.json`

`./script/check_all.sh` was not run. This host is Linux and the complete
development lane includes Swift, packaged MCP, load, and plugin checks.

## What actually repeats in current artifacts

The brief asked whether real multi-step math work repeats calculation, checking,
task translation, expression cleanup, startup, repeated search, or result
passing.

This checkout has **no Agent trajectory corpus** that could answer that with
counts. Present evidence is only of *harness assets*, not of observed Agent
behaviour:

- `evals/obligations/core.v0.1.json` is a seeded finite obligation set. It shows
  checking, not exploration.
- `evals/research/public-math-smoke.md` and Putnam 1976 A2 are Agent-evaluation
  smokes. Docs already say they are not research-utility claims.
- `docs/agent-evaluation.md` records that a correct final answer without a
  treatment tool call is not adoption, and that routing/utility numbers are
  experiment-specific.

So: checking and typed execution are implemented. Repeated search, result
passing across proof steps, and method extraction are **not evidenced as
recurring costs** here. A2 must not treat those as measured bottlenecks.

## Agent Host (pinned SHA, not in this checkout)

Fetched 2026-09-10 from
`tetracoralla/agent-host-suite@329e50b0d1106eea8f2f9921b80efb3ce190cdd7`.

| Capability | source | tests | run | used | benefit |
| --- | --- | --- | --- | --- | --- |
| Direct Execution Runtime README | yes (fetched) | not in this checkout | no | no | none |
| Trace Plane | yes (fetched) | not in this checkout | no | no | none |
| Skill Refinery vertical script named in the brief | named; not fetched as a run | no | no | no | none |

Trace Plane facts that matter for A0: default collection is metadata-only;
selected content requires explicit export and confirmation; `tool result` is not
adoption; passive observation cannot prove semantic use. Direct Runtime owns
closed structured calls, admission, timeouts, cancellation, and correlation. It
does not own mathematical equivalence or proof rules.

This A0/A1 vertical does not call Host.

## Skill Refinery / agent-tool-labs

The brief's Skill Refinery README URL 404'd from this environment on 2026-09-10
(`packages/skill-refinery/README.md` on `agent-tool-labs` main). That repository
is not a sibling of this checkout.

Reuse conclusion from the brief's already-read note, marked **not re-verified
here**: Skill Refinery currently supports `json-schema-validator.v0.1`; Agent
does semantic split, Refinery does structure/source checks. That is a Skill
assumption. It must not be migrated as a mathematical proof refiner.

A2 may later write a thin adapter. A1 does not.

## Upstream probes (reuse / thin adapt / do not attach)

### 1. SymPy Concrete / Gosper — **reuse for construction**

Source: [SymPy Concrete](https://docs.sympy.org/latest/modules/concrete.html),
SymPy 1.14.0 in the lockfile. Ran `gosper_sum` and `summation` on this machine.

Polynomials are hypergeometric, so Gosper applies. For `p(k)=k^2`,
`gosper_sum(k**2, k)` returns `k*(k-1)*(2*k-1)/6`, and expanding
`G(k+1)-G(k)` recovers `k**2`. `summation` on integer bounds returns the closed
value (`385` for `1..10`).

SymPy follows Karr: reversed bounds become a negative swapped sum
(`summation(k**2, (k, 5, 1)) == -29`). Empty sums `upper == lower - 1` are 0.

**Reuse** Gosper/summation to construct `G`. **Do not reimplement** Gosper.
**Do not attach** Karr reversed-bound evaluation as this proposal's convention.

### 2. LLM library learning, equal-budget evaluation — **do not attach as a math method; reuse the evaluation warning**

[Berlot-Attwell et al., EACL 2026](https://aclanthology.org/2026.eacl-long.163/):
ICL library-learning papers often skip equal-compute baselines; reported gains
can vanish; LEGO-Prover showed no evidence of direct lemma reuse.

**Do not attach** a lemma library or Skill-mining loop in A1. **Reuse** the
requirement that A4 compare B0/B1/B2 at equal budget and inspect actual reuse
behaviour. This pass has no model budget, so it stops before that experiment.

### 3. Lean / Pantograph — **do not attach to the first vertical**

Math Anchor already has an optional polynomial Lean bridge. A1 does not mark
`formal_kernel_checked`. Lean is not required to run the sample. Attach later
only if a selected task needs a kernel-checked lemma and the toolchain is
present.

## Honest split: what SymPy already covers

For rational-coefficient polynomial finite sums, SymPy's `summation` already
returns the exact value in a few lines. That is the A0 baseline
(`research/polynomial_finite_sum_proposal/baseline.py`).

Math Anchor does **not** add summation coverage. The structural add-on, if any,
is verification and convention, not computation:

1. `G(k+1)-G(k)=p(k)` is re-checked by a stdlib coefficient checker that does
   not import SymPy.
2. Integer bounds, empty sums, and reversed bounds are explicit and fail-closed.
   SymPy silently applies Karr reversal; this proposal rejects `upper < lower-1`.
3. The step from a difference identity to a finite sum is a named, tested rule
   rather than an implicit CAS identity.
4. The obligation receipt is replayable evidence. It still does not prove the
   surrounding prose task, and it is not a kernel result.

If the only required output is the number, SymPy is enough and the Math Anchor
layer is overhead. The layer is justified only as a checked evidence pipeline,
which matches the product's obligation/receipt identity rather than a CAS
catalogue expansion.

## What the model would need later (not used in A1)

If an Agent is later attached:

- Into the model: the task, the allowed input fields, and failures/unsupported
  reasons.
- Out of the model, into programs: `G`, the identity certificate/receipt, bound
  convention, exact `G(b+1)-G(a)`, and the combination-rule id.

Certificate coefficients and full receipts should stay outside the main context
(`failures_only` / local files). A1 already does that without a model.

## Parameterized pack (batch 2; experimental)

A second experimental pack
`math-anchor.research.method-pack.shifted-square-antidifference.v0` stores a
parametric `G(k,c)` for `(k+c)^2`. Apply instantiates that payload with
reconstruction disabled. B1/SymPy may still construct; they are not crippled.
An equal-budget no-model timing smoke exists
([parameterized-cost-smoke.md](parameterized-cost-smoke.md)): B0 already
matches the in-family numbers. A later equal-budget smoke against a cached
parametric template and an exact QQ evaluator
([reuse-benefit.md](reuse-benefit.md)) found **no net utility** versus those
strong baselines. Trustworthiness and reuse behavior still hold in the
declared domain; they are not collapsed into one success flag. That is not a
public Capability and not a dollar or promotion claim. See
[parameterized-method.md](parameterized-method.md).
