# AI-for-math research notes (A0/A1 proposal)

These documents and `research/polynomial_finite_sum_proposal/` are a new
research vertical. They are not a supported Math Anchor domain module and do
not add a fifth MCP tool.

- [current-state.md](current-state.md) — capabilities with source / tests / run / used / benefit kept separate.
- [workload-selection.md](workload-selection.md) — why polynomial finite sums, and what was deferred.
- [task-list.md](task-list.md) — candidate tasks and negative cases.

Run the vertical:

```sh
.venv/bin/python research/polynomial_finite_sum_proposal/run.py \
  --task research/polynomial_finite_sum_proposal/examples/sum-k-squared-1-to-10.json
```
