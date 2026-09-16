# Natural-error-shaped task pack (human-authored)

Research-only prompts for a **later** live B0/B1 run. Designed to elicit
silent wrong propagation across multi-step math / engineering reasoning.

- **No live scores** in this pack.
- Oracle notes are **controller-only** (`oracleNotes`); keep them outside the
  evaluated Agent view.
- `--natural-tasks-pack` **loads and validates** `index.json` + task files into
  the emitted live plan under an `agentView` / `controllerOracle` split.
  Missing or invalid paths fail closed with one error JSON (no silent skip).
- Not Epoch 2 completion. Not a benefit percentage. Do not start H1.
- Dated: experimental draft 2026-09-16.

Use with the live-arm plan emitter (no model calls):

```sh
.venv/bin/python research/shadow_verifier_eval/run.py \
  --emit-live-plan \
  --natural-tasks-pack research/shadow_verifier_eval/natural_tasks \
  --output build/shadow-verifier-live-plan.json
```
