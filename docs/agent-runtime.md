# Agent runtime usage and resilience

Math Anchor's four MCP tools are a direct deterministic provider boundary.
They do not require a language-model turn once a structured caller knows the
operation and arguments. A high-frequency coding tool should start
`math-anchor-mcp`, keep the MCP session open, and issue `math.run` or
`math.batch` calls over that session. Starting the CLI once per calculation is
correct but repeatedly pays process and import startup.

The supported 0.4 boundary is explicit invocation. Cold natural-language
selection by a fresh Agent remains useful integration research, but it depends
on the host, model, installed catalogue, and context budget. It is not a
release gate and must not be presented as guaranteed automatic adoption.

The practical low-cost topology is therefore: use an Agent only to translate
an ambiguous natural-language request into a closed `{operation, arguments}`
invocation, then let the host reuse that invocation shape for direct calls. Do
not start a fresh Coding Agent turn for every item in a loop, file, test case,
or dataset. When the Agent already has several independent calculations, send
them together through `math.batch`; when a program already has structured
inputs, skip the model entirely.

## Choose the cheapest request shape

- Use one `math.run` for a known operation.
- If the operation id is known but its exact argument contract is not, call
  `math.describe` once, then pass that returned argument object under
  `math.run.arguments`; do not guess or flatten fields.
- Use `function.sample` when one expression must be evaluated at many points.
- Use `math.batch` for 2–32 independent operations. Identical safe items in one
  batch are executed once and expanded back into their original ordered
  positions.
- Select `resultMode: exact` or `approx` when the other representation is not
  needed. Raise output budgets only for content the caller will consume.

No result cache spans calls. This avoids stale policy, unbounded memory, and
cross-caller cancellation coupling. The calculation core is deterministic, so
a repeated identical successful call is also not independent validation.

## Admission and isolation

The MCP boundary admits at most 36 calculation requests before creating an
executor job, so a burst cannot grow an unbounded host-thread queue. At most
four operations execute at once. Batch work can use at most three
leases, leaving one lane for an interactive `math.run`. Active calls share a
4 GiB weighted budget based on their requested `memoryMb`; at most 32 admitted
calls may wait. A request's `timeoutMs` remains cumulative across admission, worker
startup, and execution.

Each lease owns one isolated persistent child. Serial use prewarms one child;
observed parallel demand raises the retained warm target. Workers are replaced
after a bounded request count, high resident-memory watermark, cancellation,
timeout, memory breach, protocol failure, or crash. Internal telemetry records
only aggregate counts and queue/startup/execution/total timings, never input
expressions or result values.

## Error policy

Every structured error contains:

- `code` and human-readable `message`;
- `retryable`;
- `phase` (`input`, `admission`, `queue`, `startup`, `execution`, `output`,
  `batch`, or `cancellation`);
- `suggestedAction`;
- optional `retryAfterMs` and bounded `details`.

Correct input/domain/unit errors. Split or reduce timeout, memory, and output
errors. A full ingress queue returns retryable `E_OVERLOADED`; three consecutive
provider failures open a short circuit that returns retryable `E_UNAVAILABLE`
until one half-open probe is allowed. Retry these transient errors at most once
after the supplied delay. Cancellation is terminal for that request.

## Current-source validation

`script/load_check.py` defaults to a 13-case Coding Agent profile spanning
machine integers, bits, IEEE-754, decimal rounding, exact combinatorics and
matrices, units, quantity arithmetic, uncertainty, probability, numerical
integration, finance, and dimensions. It verifies the expected result on every
call, then exercises serial traffic, concurrent scale-up and warm bursts,
ordered/coalesced batches, mixed caller failures, cancellation, worker crash,
recovery, and final child/thread/file-descriptor/RSS cleanup. An optional
wall-clock soak records throughput, sampled p50/p95/p99, operation counts,
queue/execution telemetry, and process-tree RSS trend. Timing samples use a
bounded deterministic reservoir, so a long run does not accumulate unbounded
measurement memory.

Receipts are written under `build/load-checks/`. `script/check_all.sh` runs the
bounded 1,000-call form on every complete development verification. For a
capacity investigation, run a time-bounded concurrent soak explicitly:

```sh
.venv/bin/python script/load_check.py --calls 10000 --concurrency 8 --sustained-seconds 300
```

These are current-machine development/runtime facts, not a universal latency
or throughput promise. The legacy homogeneous arithmetic profile remains
available as `--profile expression` for controlled before/after comparisons.

The separately bounded cold direct-host smoke is also zero-model, but starts a
fresh provider driver for every operation and must not be presented as warm
session throughput:

```sh
.venv/bin/python script/direct_host_eval.py validate
.venv/bin/python script/direct_host_eval.py run
```

Its Controller-owned suite covers the same 13 representative operation
families, denies the provider access to the expected answers, fingerprints the
driver, grades results deterministically, and records provider cost as unknown
unless the route actually reports it. Reports are new files under
`build/direct-evals/`. Use the load receipt for warm-session capacity and this
report for cold structured-invocation overhead; neither measures natural
language routing.

Agent selection and value are evaluated separately from transport and load.
See `docs/agent-evaluation.md` for the 30-task paired Coding Agent corpus, its
independent Controller-side oracles, exact model-run confirmations, and the
claim boundary between natural MCP discovery, deterministic direct-host value,
and the full installed Plugin experience.
