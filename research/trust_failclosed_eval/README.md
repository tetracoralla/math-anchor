# Trust / fail-closed vs fair template (research)

Research-only. **Not** a public Capability, **not** a benefit percentage, **not**
a Host/UI/MCP change, **not** a latency bake-off. The frozen shifted-square
pack is not promoted. Dated research status: experimental draft 2026-09-14.

Pre-registered no-model comparison of:

- **B_template:** fair SymPy-side cached parametric `G(k,c)` instantiation
  **without** pack identity/domain checks (naive reuse). Family matching stays
  on so the arm is not crippled into applying `G` to `1/k` or `k^3`.
- **P-pack:** frozen shifted-square apply (instantiate saved `G`; reconstruction
  disabled; existing applicability / identity / domain checks).

Question: when does pack + checks fail closed (wrong saved `G` / out-of-domain /
identity or obligation binding) while the fair template silently accepts
(policy `no_value`) or returns a wrong answer (arithmetic silent-wrong)?

Three judgments stay separate: trustworthiness, behavior, utility.
Utility is **not** the primary claim. Timings are informational if present.

## Command

```sh
.venv/bin/python research/trust_failclosed_eval/run.py \
  --output build/trust-failclosed-report.json
```

`--output` refuses to overwrite. `build/` is gitignored.

Tests:

```sh
.venv/bin/python -m pytest tests/python/test_trust_failclosed.py
```

Summary: `docs/research/ai-for-math/trust-failclosed.md`.
