# Shadow verifier live four-arm run (experimental)

This note is a research report, not a product Capability, not an overall
benefit percentage, and **not Epoch 2 completion**. Method packs are **not**
promoted. Do not start H1. Dated H1 freeze **2026-09-15** is unchanged.

Machine-readable artifact:

`docs/research/ai-for-math/shadow-verifier-live-report.json`

All counts below are copied from that file. Nothing here is an invented
accuracy, savings percentage, quality delta, or dollar cost.

## What ran

Authorized command (paid-call cap **N = 48**):

```sh
.venv/bin/python research/shadow_verifier_eval/run.py \
  --include-model-arms \
  --confirm-live-budget \
  --confirm-model-runs 48 \
  --output docs/research/ai-for-math/shadow-verifier-live-report.json
```

| Field | Observed |
| --- | --- |
| Provider | xAI |
| Model | `grok-4.6` |
| API | `https://api.x.ai/v1` `chat.completions` |
| Auth source | grok CLI OIDC (`authSource=grok-cli-oidc`; credential redacted) |
| Reasoning effort | `high` |
| `complete()` calls | **48** (cap 48; remaining 0) |
| Calls by arm | B0 **9**, B1 **39** |
| Generated at | `2026-09-18T17:21:31.639173+00:00` |
| Math Anchor | 0.7.1 |
| Python | 3.13.5 |
| `environment.gitHead` at run | `8b4ec93976362d105164901f8ac48d24fb0bd9b5` (main after PR #18). Live-loop sources were uncommitted on `chore/ai-for-math-epoch-2-live-four-arms`. Do not treat that SHA as this PR's tip. |
| `decision.experimentVerdict` | `live_b0_b1_ran` |
| `decision.promote` | `false` |
| `decision.epoch2Complete` | `false` |
| `decision.doNotStartH1` | `true` |

B2/B3 still used `math_anchor.obligations.check_obligation_set` (not a second
stack, not a mid-pipeline LLM). Natural-task pack cells were **not** part of
this bounded run.

## B1 tool surface (limits)

B1 offered the current four MCP tools only (`math.search` / `math.describe` /
`math.run` / `math.batch`). Dispatch was **in-process catalog** — the same
functions the MCP server uses — not a Host JSON-RPC MCP session. There is no
fifth tool. The obligation-set envelope was not exposed to the model.

A `math.run` / `math.batch` call is lifecycle evidence only.
`correctAnswerWithoutTargetCallIsNotAdoption` stays true. The harness never
sets `adoption=true`.

Max tool turns per B1 cell: 4 extra `complete()` calls after the first.
`--confirm-model-runs 48` counts every HTTP `complete()`, including those
tool turns.

## Live B0 / B1 cells

Controller grading used a `VERDICT: YES|NO|UNSURE` line (oracle notes were
not in the agent prompt). Unparseable is **not** detection and **not**
acceptance.

G1 supported seeded-error tasks: sign-flip, domain-overshoot-definedness,
dimension-mismatch, rounding-in-exact-chain, unit-scale-mismatch,
assumption-swapped, step-n-legal-wrong-value.

| Arm | Task | Verdict | Detected (G1) | Accepted seeded error | Target `math.run`/`math.batch` | HTTP calls | Total tokens |
| --- | --- | --- | --- | --- | --- | --- | --- |
| B0 | control-polynomial-identity | yes | — | — | 0 | 1 | 1055 |
| B0 | control-dimension-consistency | yes | — | — | 0 | 1 | 1094 |
| B0 | sign-flip | no | yes | no | 0 | 1 | 1123 |
| B0 | domain-overshoot-definedness | no | yes | no | 0 | 1 | 1356 |
| B0 | dimension-mismatch | no | yes | no | 0 | 1 | 1048 |
| B0 | rounding-in-exact-chain | no | yes | no | 0 | 1 | 1320 |
| B0 | unit-scale-mismatch | no | yes | no | 0 | 1 | 1331 |
| B0 | assumption-swapped | no | yes | no | 0 | 1 | 1316 |
| B0 | step-n-legal-wrong-value | no | yes | no | 0 | 1 | 1148 |
| B0 | unsupported-kind | *deferred* (budget exhausted) | — | — | — | — | — |
| B0 | dependency-blocked | *deferred* (budget exhausted) | — | — | — | — | — |
| B0 | si-prefix-scale-blind-spot | *deferred* (budget exhausted) | — | — | — | — | — |
| B1 | control-polynomial-identity | yes | — | — | 1 | 5 | 9784 |
| B1 | control-dimension-consistency | yes | — | — | 1 | 4 | 8309 |
| B1 | sign-flip | no | yes | no | 1 | 5 | 11066 |
| B1 | domain-overshoot-definedness | no | yes | no | 1 | 5 | 9866 |
| B1 | dimension-mismatch | no | yes | no | 1 | 4 | 8596 |
| B1 | rounding-in-exact-chain | no | yes | no | 1 | 5 | 10621 |
| B1 | unit-scale-mismatch | no | yes | no | 1 | 4 | 8617 |
| B1 | assumption-swapped | **unparseable** (empty text after 5 tool-loop calls; no `math.run`) | no | no | 0 | 5 | 8970 |
| B1 | step-n-legal-wrong-value | **unparseable** (cap hit mid-loop after 2 searches; empty text) | no | no | 0 | 2 | 3528 |
| B1 | unsupported-kind | *deferred* (budget exhausted) | — | — | — | — | — |
| B1 | dependency-blocked | *deferred* (budget exhausted) | — | — | — | — | — |
| B1 | si-prefix-scale-blind-spot | *deferred* (budget exhausted) | — | — | — | — | — |

B0 false rejects on the two G3 controls: **0**. B1 false rejects on those
controls: **0**. B0 accepted seeded errors on the seven G1 tasks: **0**.
B1 accepted seeded errors: **0** (two G1 cells unparseable, not counted as
accept).

B2/B3 on this same report: G1 supported seeded errors **7/7** and **7/7**.
Binding probes **2/2**. B3 quiet-success 0 model-context bytes on checked
controls remains a **wrapper projection**; product evidence is still CLI
`--quiet-success` empty stdout.

## Gates G1–G6 (this live report)

| Gate | `epoch2GateMet` | This report |
| --- | --- | --- |
| **G1** detection | **false** | B2 **7/7**, B3 **7/7**, binding **2/2**. Live B0 detected **7/7** with 0 unparseable. Live B1 detected **5/7** with **2 unparseable** (call cap / tool loop, empty text — not acceptance). G1 stays unmet until live B0 and B1 both have parseable verdicts on all seven G1 tasks. |
| **G2** accepted-error drop | **false** | B0 accepted seeded errors **0**. Drop vs matched B0 is vacuous on this corpus / this model. No savings percentage. |
| **G3** false reject | **true** | B2 **0**, B3 **0**. Live B0 **0/2**, live B1 **0/2** on the two controls. |
| **G4** context | **false** | Mean total tokens B0 **1199.0**, B1 **8817.444…**. Relative increase `(B1−B0)/B0` = **6.354** (not ≤10%). B3 library 0-byte quiet success is still a wrapper projection. |
| **G5** repair | **false** | Same-claim seeded sign-flip hook still matched on B3. That is not a live model repair. No live repair loop ran. |
| **G6** strong+weak | **false** | One model (`grok-4.6`) only. |

`decision.epoch2Complete` remains **false**. `decision.promote` remains
**false**. Do not start H1.

## Honesty

- Smoke ≠ overall benefit percentage. The report refuses to emit one.
- Green harness tests ≠ completion of Epoch 2.
- No invented `finalAccuracy`, `liveQualityDelta`, dollar cost, or savings %.
- Token counts are API usage fields (`promptTokens` / `completionTokens` /
  `totalTokens` / `reasoningTokens`). Provider fee fields were stripped.
- `$` characters in the JSON artifact are regex end-anchors inside catalog
  `math.describe` schemas in B1 tool traces, not currency.
- B1 in-process catalog dispatch is not Host MCP and not B2/B3.
- Call-alone / target-call lifecycle is not semantic adoption.
- Quiet success is zero returned content, not proof of use.
- Completeness tasks (unsupported-kind, dependency-blocked, SI-prefix
  blind-spot) were not live-run; the cap was spent on controls + G1 + B1
  tool turns.
- Natural-task pack was not live-run.

## Risks / limits

- This `grok-4.6` B0 already rejected all seven seeded errors, so G2 cannot
  show an accepted-error drop on this corpus.
- B1 spent 39 of 48 calls on tool turns; two G1 B1 cells ended unparseable
  because the cap stopped the loop before a `VERDICT` line.
- Completeness and natural-task cells need a larger written N.
- G6 needs a second, weaker model under the same protocol.
- G5 needs a live repair loop after `failures_only`, not the seeded hook.
- G4 ≤10% vs B0 is not plausible while B1 carries four-tool schemas and
  multi-turn traces.
- Not a Host product integration.

## Decision

**evidence insufficient — do not promote. Epoch 2 is not complete.**
Experiment verdict: **`live_b0_b1_ran`**.
