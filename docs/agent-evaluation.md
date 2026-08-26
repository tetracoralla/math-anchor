# Coding Agent evaluation

Math Anchor's deterministic core and transport checks do not establish that a
Coding Agent will select the runtime, translate a task correctly, or gain
enough reliability to justify the extra Agent/tool round. The paired assets in
`evals/agent/` measure those questions separately from provider conformance.

## Evaluation model

- The weakest intended current Agent class is `gpt-5.6-luna` at explicitly
  declared `low` reasoning effort through the installed Codex CLI harness.
  The experiment does not inherit a developer's ambient reasoning setting.
- Baseline and treatment use the same prompt, Agent, harness, driver, budgets,
  isolation, and effective configuration. Only the provenance-checked Math
  Anchor MCP server is available in treatment.
- Target-specific Plugin Skills and hooks are disabled in both conditions. The
  `smoke` and `utility` modes therefore measure unassisted MCP discovery from
  the live tool contract, not the full plugin experience. The separate
  `policy-smoke` and `policy-utility` modes apply the same short,
  provider-neutral deterministic-mathematics policy to both conditions; only
  target availability still differs. They measure a Coding Agent operating
  under an explicit reliability policy, not spontaneous tool preference.
- The `installed-smoke` mode exercises the packaged Plugin in a disposable
  Codex home containing no other Plugin. It stages the same installed Math
  Anchor identity for both conditions, keeps local command tools disabled, and
  varies only whether the verified Math Anchor MCP server is enabled. This is
  the bounded full-product Skill/dependency route; it is deliberately separate
  from an ambient user session whose unrelated Plugins and schemas would
  contaminate both routing and token cost.
- The ordinary known route budget is one direct `math.run` call. One
  `math.describe` call is acceptable when the selected operation's exact
  argument contract is genuinely unfamiliar; `math.search` is reserved for an
  unknown or ambiguous operation id. A correct final answer without a treatment target call is not
  adoption evidence.
- Expected answers remain in the Controller-owned suite and are OS-denied from
  the evaluated Agent. `tests/python/test_agent_evaluation_assets.py` derives
  them independently with Python standard-library arithmetic rather than
  calling Math Anchor.

The full suite contains 30 scalar-answer Coding Agent tasks: 24 required tool
opportunities, three deliberately simple optional tasks, and three irrelevant
controls. It covers fixed-width arithmetic, bit operations, IEEE-754 facts,
decimal and division conventions, exact large integers, linear algebra, data
and physical units, uncertainty, probability, numerical methods, finance, and
dimensions. The four-task smoke is an exact subset.

## Safe execution

The provider-neutral paired runner is the sibling `agent-tool-evals` workspace.
Override its location with `AGENT_TOOL_EVALS_ROOT` or `--evaluator-root` when
needed. Run `./script/bootstrap.sh` first when `.venv/bin/python` is absent.
Validation makes no model calls:

```sh
.venv/bin/python script/agent_eval.py validate --mode smoke
.venv/bin/python script/agent_eval.py validate --mode utility
.venv/bin/python script/agent_eval.py validate --mode policy-smoke
.venv/bin/python script/agent_eval.py validate --mode policy-utility
.venv/bin/python script/agent_eval.py validate --mode installed-smoke
.venv/bin/python script/agent_eval.py preflight --mode installed-smoke
```

Every model-backed run requires the exact planned-call confirmation. Reports
are new files under the gitignored `build/agent-evals/` directory:

```sh
.venv/bin/python script/agent_eval.py run --mode smoke --confirm-model-runs 8
.venv/bin/python script/agent_eval.py run --mode utility --confirm-model-runs 180
.venv/bin/python script/agent_eval.py run --mode policy-smoke --confirm-model-runs 8
.venv/bin/python script/agent_eval.py run --mode policy-utility --confirm-model-runs 180
.venv/bin/python script/agent_eval.py run --mode installed-smoke --confirm-model-runs 8
```

The matching smoke must be infrastructure-valid and show the intended routing
behavior before its 180-run utility estimate is started. A valid unassisted
smoke with zero target adoption is a carrier-selection finding, not permission
to spend the larger budget. Likewise, an installed-Skill probe that reaches the
target only after search, describe, malformed arguments, or a retry has not met
the ordinary one-call route and must be repaired before scale-up. Driver
failure, missing usage, budget excess,
runtime/config drift, incomplete pairs, or baseline target use invalidates
comparison rather than becoming a task failure or a zero. Do not overwrite an
earlier report.

The installed smoke creates one temporary Codex home, links the current Codex
authentication without copying it, installs only the current packaged Math
Anchor Plugin, isolates `HOME` as well as `CODEX_HOME` so ambient user Skills
cannot enter the prompt, verifies the target Skill and MCP entry, and removes
the temporary home after the paired run. Driver arguments remain digest-only in the report.
This setup cost is Controller overhead and is not confused with per-task Agent
tokens or tool turns.

## Claim interpretation

Math Anchor 0.4 supports explicit structured invocation and deterministic
execution. Source or binary release therefore does not require a fresh Agent
to select the Plugin from natural language. Promotion of a natural-language
selection, automatic-adoption, or Agent-quality claim requires current
evidence that:

- the paired comparison is valid and baseline never reaches the target;
- every required treatment task is correct and invokes Math Anchor;
- irrelevant treatment tasks do not invoke Math Anchor;
- valid tasks produce no semantic retries, and known operations normally use
  one public tool call for known contracts, or one describe plus one run when
  the exact selected contract is unfamiliar;
- the complete discovery envelope, direct-host performance, sustained load,
  cancellation, recovery, and resources remain within their declared bounds.

A zero paired quality delta can still support deterministic or direct-host
value, but cannot be described as an Agent quality gain. A negative treatment
delta blocks the corresponding natural-language selection or Agent-quality
claim until its task translation, schema, Skill, or runtime cause is repaired;
it does not by itself block the explicit-invocation product contract. Token or
latency overhead is reported rather than hidden; an Agent-mediated microtask is
not expected to beat an already structured zero-model direct-host call.

## Current isolated and direct-host findings

The first exact eight-call isolated installed-Plugin smoke on 2026-08-24 is an
invalid comparison, not adoption evidence. Two runs exceeded the 100,000-token
limit, the six completed runs were correct without any Math Anchor call, and
the treatment made zero target calls. The successful simple/control runs used
about 15,900 input tokens each, while the nontrivial successful runs approached
84,000–85,000 and the two failures exceeded 100,000. This shows that removing
ambient Plugins materially reduced simple cold-session context, but did not
make a fresh Agent turn economical or reliable for repeated structured
calculation. Driver v0.4.1 now explicitly enables the Plugin feature and locks
that precondition in a negative regression; that repair is development-tested
but has not been promoted into a second paid smoke.

An August 26 rerun first exposed a stale declared Codex CLI version before
confirming that inherited/default high reasoning can again exceed 100,000
tokens on the two required tasks. Current experiments therefore pin `low`
reasoning as part of their shared configuration and reject CLI-version drift
before model execution. Earlier reports remain invalid and are not merged into
the current result.

The same investigation found that isolating only `CODEX_HOME` still admitted
the user's global `~/.agents/skills` catalogue. Current installed runs isolate
both home roots and fail preflight unless the target Skill is present and
ambient Skills are absent.

The final August 26 installed smoke with Codex CLI `0.150.0-alpha.8`, Luna at
low reasoning, both home roots isolated, and the direct common-operation
templates still did not satisfy promotion. The large exact combination used
one successful `math.run` call and the simple and irrelevant controls made no
target call, but the required fixed-width treatment exceeded 100,000 tokens.
The comparison is therefore invalid and installed cold natural routing remains
`BLOCKED`; the 180-run estimate was not started. This blocks any claim of
automatic adoption or Agent-quality improvement, but does not invalidate or
block release of the separately measured deterministic explicit route.

The zero-model cold direct-host smoke is a separate observation. It invokes 13
structured `math.run` workloads once each, with no Agent, harness, prompt,
paired condition, token, or tool-adoption fields. Run it through
`script/direct_host_eval.py`; do not merge its latency summary into a paired
Agent report. High-frequency evidence still comes from the persistent-worker
load harness, because the direct-host v0.1 evaluator deliberately starts a new
bounded driver process for each task.

The report is conditional evidence for the named suite, Agent, harness,
budgets, driver, versions, and machine. It is not a universal Tool Score,
provider conformance certificate, evidence of the target-specific installed
Skill unless that route was separately observed, public-release authorization,
or owner business acceptance.
