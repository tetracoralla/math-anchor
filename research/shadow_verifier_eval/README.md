# Shadow verifier scaffold (research Epoch 2)

Research-only. **Not** a public Capability, **not** a benefit percentage,
**not** Epoch 2 completion, **not** a method-pack promotion. Dated research
status: experimental draft 2026-09-16. Do not start H1. Dated H1 freeze
2026-09-15 is unchanged.

Pre-registered no-model scaffold of:

- **B0:** model-only (no math provider) — live when `--include-model-arms` is authorized; otherwise `model_arms=deferred`
- **B1:** model + current four-tool MCP, voluntary use — live in-process catalog dispatch when authorized; otherwise deferred
- **B2:** explicit `math-anchor.obligation-set.v0.1` (full feedback)
- **B3:** Host/harness shadow checkpoint (`failures_only`, quiet success as a
  library wrapper projection of zero model-context bytes when checked — product
  evidence is CLI `--quiet-success` empty stdout — receipt outside model
  context, seeded same-claim repair-loop hook; unrelated valid resubmits are
  not repair probes)

B2/B3 reuse the existing obligation runtime. They are not a second stack.
Gates G1–G6 are **targets**. Live four-arm evidence is required before Epoch 2
can be called done.

## This PR advances (still incomplete)

1. Expanded deterministic adversarial corpus (rounding sneak, unit-kind
   mismatch, assumption swap, step-N legal-wrong) plus an SI-prefix
   completeness blind-spot cell.
2. Live-arm runner (`live_runner.py` / `live_loop.py`): `LiveFourArmPlan`,
   `--emit-live-plan`, fail-closed `--include-model-arms` unless budget
   confirm + registered `LiveModelBackend`. Authorized runs execute B0/B1
   up to `--confirm-model-runs N` (xAI/Grok backend; B1 is in-process
   four-tool catalog dispatch, not Host JSON-RPC MCP).
3. Human-authored `natural_tasks/` pack (oracle notes outside agent view;
   not part of the bounded protocol live run).

## Command

```sh
.venv/bin/python research/shadow_verifier_eval/run.py \
  --output build/shadow-verifier-report.json
```

`--output` refuses to overwrite. `build/` is gitignored.

Emit a live four-arm JSON plan (**no model calls**, no invented numbers):

```sh
.venv/bin/python research/shadow_verifier_eval/run.py \
  --emit-live-plan \
  --natural-tasks-pack research/shadow_verifier_eval/natural_tasks \
  --output build/shadow-verifier-live-plan.json
```

`--include-model-arms` stays **fail-closed** unless:

1. `--confirm-live-budget` or `MATH_ANCHOR_SHADOW_LIVE=1`
2. `--confirm-model-runs N` with `N > 0`
3. a pluggable `LiveModelBackend` is registered via
   `register_live_backend(...)`

When those hold, the CLI auto-registers an xAI/Grok `LiveModelBackend` from
`XAI_API_KEY` / `MATH_ANCHOR_XAI_API_KEY` or grok CLI OIDC auth and executes
live B0/B1 cells up to N `complete()` calls. It still invents no quality
deltas, dollars, or savings percentages.

```sh
.venv/bin/python research/shadow_verifier_eval/run.py \
  --include-model-arms \
  --confirm-live-budget \
  --confirm-model-runs N \
  --output build/shadow-verifier-live-report.json
```

Set `MATH_ANCHOR_SHADOW_DISABLE_AUTO_BACKEND=1` to keep fail-closed without
a test-registered backend.

Tests:

```sh
.venv/bin/python -m pytest tests/python/test_shadow_verifier.py
```

Summary: `docs/research/ai-for-math/shadow-verifier.md`.
Epoch 1 archive: `docs/research/ai-for-math/research-epoch-1.md`.
