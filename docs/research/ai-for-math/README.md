# AI-for-math research notes (A0–A3 proposal)

These documents, `research/polynomial_finite_sum_proposal/`, and
`research/method_packs/` are a research vertical. They are not a supported
Math Anchor domain module, not a public Capability/Procedure, and do not add
a fifth MCP tool.

- [current-state.md](current-state.md) — capabilities with source / tests / run / used / benefit kept separate.
- [workload-selection.md](workload-selection.md) — why polynomial finite sums, and what was deferred.
- [task-list.md](task-list.md) — candidate tasks and negative cases.
- [a2-method-pack.md](a2-method-pack.md) — T1 extraction, novelty label, held-out reuse.
- [a3-coverage.md](a3-coverage.md) — claim→obligation coverage, typed binding, mutation tests.

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
