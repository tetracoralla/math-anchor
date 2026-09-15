# AI-for-math research notes

These documents and the `research/` harnesses are a research vertical. They
are not a supported Math Anchor domain module, not a public
Capability/Procedure, and do not add a fifth MCP tool.

**Research Epoch 1** (A0 → trust-failclosed, including merged PRs #15 and
#16) is archived. Method reuse as the primary R&D bet was **rejected** on
the studied family. Independent verification / fail-closed **survives as a
hypothesis**. Method packs are research samples and a **dated freeze** of
H1 accumulation (2026-09-15) pending new workload evidence — not a standing
“永远不做”.

**P0 next:** Epoch 2 Shadow Verifier (Mathematical Evidence Runtime /
progressive assurance: Claim → Certificate → Verifier → Binding →
Assurance → Receipt). Calculator/UI stay a compact human utility, not the
research center, without a forever ban.

- [research-epoch-1.md](research-epoch-1.md) — Epoch 1 archive (#15/#16 quoted; no invented numbers).
- [shadow-verifier.md](shadow-verifier.md) — Epoch 2 scaffold; G1–G6 are **targets**; B0/B1 `model_arms=deferred`.
- [current-state.md](current-state.md) — capabilities with source / tests / run / used / benefit kept separate.
- [workload-selection.md](workload-selection.md) — why polynomial finite sums, and what was deferred.
- [task-list.md](task-list.md) — candidate tasks and negative cases; Epoch 2 P0.
- [a2-method-pack.md](a2-method-pack.md) — T1 extraction, novelty label, held-out reuse.
- [a3-coverage.md](a3-coverage.md) — claim→obligation coverage, typed binding, mutation tests.
- [a4-smoke.md](a4-smoke.md) — equal-budget B0/B1/B2 smoke; not a benefit percentage.
- [parameterized-method.md](parameterized-method.md) — saved `G(k,c)` for `(k+c)^2`; apply without Gosper.
- [parameterized-cost-smoke.md](parameterized-cost-smoke.md) — equal-budget B0/B1/P-pack timing; not a benefit percentage.
- [reuse-benefit.md](reuse-benefit.md) — same family vs B0/B1/B_template/B_codegen; three separate judgments; not a benefit percentage.
- [trust-failclosed.md](trust-failclosed.md) — pack fail-closed vs fair template silent-wrong / silent-accept; latency is not the primary claim; not a promotion.

A1 vertical:

```sh
.venv/bin/python research/polynomial_finite_sum_proposal/run.py \
  --task research/polynomial_finite_sum_proposal/examples/sum-k-squared-1-to-10.json
```

A2 pack apply (held-out `sum k^3`):

```sh
.venv/bin/python research/method_packs/run.py apply \
  --task research/method_packs/examples/sum-k-cubed-1-to-20.json
```

A3 coverage sidecar (same cubes task):

```sh
.venv/bin/python research/method_packs/run.py apply \
  --task research/method_packs/examples/sum-k-cubed-1-to-20.json \
  --coverage-output build/method-pack-sum-k-cubed-coverage.json
```

A4 equal-budget smoke (no model; report under gitignored `build/`):

```sh
.venv/bin/python research/ai_for_math_eval/run.py \
  --output build/a4-smoke-report.json
```

Parameterized shifted-square pack (held-out `c=3`, reconstruction disabled):

```sh
.venv/bin/python research/method_packs/run.py apply \
  --pack research/method_packs/shifted_square_antidifference.v0/pack.json \
  --task research/method_packs/examples/shifted-square-held-out-c3-2-to-7.json
```

Parameterized equal-budget cost/timing smoke (no model; report under gitignored `build/`):

```sh
.venv/bin/python research/parameterized_cost_eval/run.py \
  --output build/parameterized-cost-smoke-report.json
```

Reuse-benefit smoke vs strong CAS cache/template/codegen baselines (no model;
report under gitignored `build/`):

```sh
.venv/bin/python research/reuse_benefit_eval/run.py \
  --output build/reuse-benefit-report.json
```

Trust / fail-closed vs fair template (no model; not a latency bake-off;
report under gitignored `build/`):

```sh
.venv/bin/python research/trust_failclosed_eval/run.py \
  --output build/trust-failclosed-report.json
```

Epoch 2 shadow-verifier scaffold (deterministic B2/B3; B0/B1 deferred;
report under gitignored `build/`):

```sh
.venv/bin/python research/shadow_verifier_eval/run.py \
  --output build/shadow-verifier-report.json
```
