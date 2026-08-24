# Agent runtime usage and resilience

Math Anchor's four MCP tools are a direct deterministic provider boundary.
They do not require a language-model turn once a structured caller knows the
operation and arguments. A high-frequency coding tool should start
`math-anchor-mcp`, keep the MCP session open, and issue `math.run` or
`math.batch` calls over that session. Starting the CLI once per calculation is
correct but repeatedly pays process and import startup.

## Choose the cheapest request shape

- Use one `math.run` for a known operation.
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

`script/load_check.py` runs a 10,000-call serial soak plus 8-way bursts, ordered
and duplicate batches, a cancellation storm, an idle-worker crash, recovery,
and final child/thread/file-descriptor/RSS checks. It writes a timestamped JSON
receipt under `build/load-checks/`. `script/check_all.sh` runs a shorter
1,000-call version on every complete development verification. These are
development/runtime facts, not a promise about another machine's latency.
