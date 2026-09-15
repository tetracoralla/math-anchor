# Shadow verifier scaffold (research Epoch 2)

Research-only. **Not** a public Capability, **not** a benefit percentage,
**not** Epoch 2 completion, **not** a method-pack promotion. Dated research
status: experimental draft 2026-09-15. Do not start H1.

Pre-registered no-model scaffold of:

- **B0:** model-only (no math provider) — interface recorded; `model_arms=deferred`
- **B1:** model + current four-tool MCP, voluntary use — interface recorded; deferred
- **B2:** explicit `math-anchor.obligation-set.v0.1` (full feedback)
- **B3:** Host/harness shadow checkpoint (`failures_only`, quiet success, receipt
  outside model context, seeded repair-loop hook)

B2/B3 reuse the existing obligation runtime. They are not a second stack.
Gates G1–G6 are **targets**. Live four-arm evidence is required before Epoch 2
can be called done.

## Command

```sh
.venv/bin/python research/shadow_verifier_eval/run.py \
  --output build/shadow-verifier-report.json
```

`--output` refuses to overwrite. `build/` is gitignored.

`--include-model-arms` is **rejected** in this scaffold (`model_arms=deferred`).
Later live command (not implemented here; do not invent numbers):

```sh
.venv/bin/python research/shadow_verifier_eval/run.py \
  --include-model-arms \
  --confirm-model-runs N \
  --output build/shadow-verifier-live-report.json
```

`N` is a written planned-call count. Do not start a paid run without a budget.

Tests:

```sh
.venv/bin/python -m pytest tests/python/test_shadow_verifier.py
```

Summary: `docs/research/ai-for-math/shadow-verifier.md`.
Epoch 1 archive: `docs/research/ai-for-math/research-epoch-1.md`.
