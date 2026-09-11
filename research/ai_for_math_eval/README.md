# A4 equal-budget smoke (research)

Research-only. **Not** a public Capability, **not** a benefit percentage, **not**
a Host/UI/MCP change. The frozen Gosper pack is not promoted.

Pre-registered no-model comparison of:

- **B0:** existing SymPy `summation` baseline (no method pack)
- **B1:** A1 polynomial finite-sum runner (no extracted pack)
- **B2:** frozen A2 pack apply path
- **B2-minus:** held-out cubes without the pack, **only if** B2 shows a reuse signal

## Command

```sh
.venv/bin/python research/ai_for_math_eval/run.py \
  --output build/a4-smoke-report.json
```

`--output` refuses to overwrite. `build/` is gitignored.

Tests:

```sh
.venv/bin/python -m pytest tests/python/test_a4_smoke.py
```

Summary: `docs/research/ai-for-math/a4-smoke.md`.
