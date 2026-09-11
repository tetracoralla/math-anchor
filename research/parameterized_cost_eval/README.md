# Parameterized pack equal-budget cost/timing smoke (research)

Research-only. **Not** a public Capability, **not** a benefit percentage, **not**
a Host/UI/MCP change. The frozen shifted-square pack is not promoted.

Pre-registered no-model comparison of:

- **B0:** existing SymPy `summation` baseline (allowed to construct a value)
- **B1:** A1 polynomial finite-sum runner (allowed to construct via Gosper)
- **P-pack:** frozen shifted-square apply (instantiate saved `G`; reconstruction disabled)

Same pre-registered `(c,a,b)` on every arm, including held-out `(k+3)^2` on
`2..7` → `355`. Zero model calls. In-process first/repeat wall time only.
No dollar costs.

## Command

```sh
.venv/bin/python research/parameterized_cost_eval/run.py \
  --output build/parameterized-cost-smoke-report.json
```

`--output` refuses to overwrite. `build/` is gitignored.

Tests:

```sh
.venv/bin/python -m pytest tests/python/test_parameterized_cost_smoke.py
```

Summary: `docs/research/ai-for-math/parameterized-cost-smoke.md`.
