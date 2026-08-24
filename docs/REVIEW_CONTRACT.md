# Math Anchor review contract

This contract tells a reviewer what current evidence is required before calling
Math Anchor safe, Agent-usable, efficient, or release-ready. It is a review
route, not a self-certifying checklist: a green script controls only the named
facts it actually exercises.

Read `product-model.md` and `agent-runtime.md` first. Review the current source,
the generated MCP surface, the packaged runtime, and the macOS app as separate
carriers of one calculation core. Never inherit an earlier completion claim or
benchmark number.

## Current authorities and carrier seams

- `src/math_anchor/catalog.py`, `contracts.py`, and `operations/` own operation
  identity, argument schemas, result shapes, examples, and mathematical
  semantics. The registry is the source for discovery and the typed
  `math.run` schema; do not maintain a second hand-written catalogue.
- `safe_expression.py` and the dimension/unit expression translators own the
  accepted expression language. They must remain explicit AST translators;
  Python `eval`, `exec`, string `sympify`, and `parse_expr` are forbidden.
- `sandbox.py`, `worker.py`, `runtime_control.py`, `runtime_telemetry.py`, and
  `output_policy.py` own isolation, deadlines, memory accounting, admission,
  cancellation, recovery, and response bounds.
- `mcp_server.py` owns the public Agent carrier. `cli.py`, `app_runtime.py`, and
  `bundled_runtime.py` are adapters and must not invent different operation or
  result semantics.
- `CalculatorApp/` owns the human carrier. It may add human-only conveniences
  such as the ECB-backed currency workflow, but its mathematical calculations
  still go through the shared core. Currency is not a hidden fifth MCP tool.
- `plugins/math-anchor/`, packaging scripts, and the installed plugin cache are
  distinct distribution carriers. Source tests do not prove an installed
  package starts, routes, or uses the intended bundled runtime.

## Invariants that every relevant change must preserve

1. **One operation model, four public tools.** The public MCP surface is exactly
   `math.search`, `math.describe`, `math.run`, and `math.batch`.
   `math.run` accepts the operation-specific closed schema generated from the
   registry. `math.batch` stays compact while validating each item against the
   same registry contract. Add mathematics to the registry, not as another
   public tool. The operation count is derived from current source, not frozen
   in prose.
2. **Direct routing stays cheap.** A caller that knows the operation ID can use
   `math.run` in one call. Search and describe are for genuine discovery, not a
   mandatory preflight. Batch takes 1–32 independent items, preserves input
   order, and returns per-item failure without converting a valid partial batch
   into a whole-call transport failure.
3. **Exactness and provenance remain typed.** Exact and approximate values stay
   distinct. Precision mode, uncertainty, units, conventions, assumptions, and
   algorithm provenance must not be collapsed into an attractive but ambiguous
   scalar or string. A floating approximation must never be labelled exact.
4. **Unsafe text never reaches a general evaluator.** Unknown names, syntax,
   AST nodes, fields, units, and operation IDs fail closed with stable errors.
   Parser and schema changes require hostile-input and size/depth regressions,
   not only happy examples.
5. **Errors are machine-actionable and bounded.** Failures preserve a stable
   `code`, human `message`, `retryable`, `phase`, and `suggestedAction`, with
   `retryAfterMs` only when useful. Oversized exception text or caller input
   must not escape response limits; trimming must preserve the original error
   code when possible. MCP `isError` must agree with whole-call failure, while
   partial batch items carry their own envelopes.
6. **One whole-call budget covers waiting and execution.** Queueing, worker
   startup, execution, serialization, and cancellation cleanup cannot each
   silently receive a fresh timeout. The current runtime admits at most four
   active calculations, at most three batch calculations, 32 queued requests,
   and 4096 MiB of requested memory in aggregate. The MCP ingress bound is the
   active-plus-queued envelope. Single calls can pass queued batch work so a
   burst does not consume the interactive lane.
7. **Cancellation and faults release every resource.** Cancellation while
   queued, starting, executing, or returning must eventually release ingress,
   admission, worker, temporary diagnostics, and memory accounting. Dead or
   oversized workers are evicted. Repeated infrastructure faults open the
   circuit and return `E_UNAVAILABLE`; a half-open probe and later healthy call
   restore service without a process restart.
8. **Output and discovery costs are explicit.** The complete listed MCP tool
   envelope remains below the repository budget of 40,000 encoded bytes. The
   default single and batch result limits remain 64 KiB and 128 KiB, with the
   documented 1 KiB–1 MiB caller range. `resultMode` may remove redundant
   representations but cannot change mathematical meaning or hide uncertainty.
   Samples, errors, telemetry, and diagnostics need their own bounded shapes.
9. **Duplicate work is safe, not magical.** Concurrent identical batch items
   may share an execution only when their limits and observable result are
   equivalent. There is no undocumented cross-call result cache. Ordering,
   cancellation, per-item budgets, and failure attribution remain correct when
   work is coalesced.
10. **Human and Agent carriers share semantics, not chrome.** The macOS UI must
    not expose MCP, schema, worker, or Agent metadata. Keyboard input, history,
    conversions, errors, and app restart are human-runtime concerns and need
    real app evidence. A correct MCP test is not visual or interaction
    acceptance.

## Mandatory adversarial review matrix

For any changed seam, exercise the smallest relevant rows below in addition to
the normal suite:

- registry entry -> generated `math.run` schema -> `math.describe` -> runtime
  validation -> plugin example; reject unknown and extra fields at every live
  ingress;
- exact versus approximate lanes, large integers, rounding/tie conventions,
  matrices, units and dimensions, domain boundaries, and independent-library
  differential checks where an oracle exists;
- hostile expressions: unknown names, calls, attributes, indexing, oversized
  input, excessive depth, and constructs adjacent to the accepted grammar;
- ordered mixed-success batch, duplicate items, conflicting per-item limits,
  cumulative deadline expiry, cancellation during a batch, and an output that
  would exceed the whole-batch response budget;
- queue saturation, the 33rd queued request, four active leases, the fourth
  concurrent batch, requested-memory exhaustion, cancellation storms, worker
  crash/recycle, circuit open/half-open/recovery, and a healthy call after each;
- packaged runtime startup without a source checkout or development-only
  environment, current installed-plugin routing, and a cold natural-language
  task that reaches the intended public tool;
- macOS launch, keyboard-only calculation, history, human-only currency cache
  and stale/failure paths, app relaunch, and visible error recovery.

Do not turn the numeric limits above into speculative scale claims. If a change
targets high-frequency or batch performance, compare current source before and
after with the same workload, machine, warm/cold state, concurrency, payload,
and output mode. Record throughput, p50/p95/p99, errors, retries, queue time,
memory/RSS trend, worker recovery, and cleanup residue. A faster median does not
offset tail collapse, unbounded memory, starvation, or a changed result.

## Rerunnable evidence

Run from the repository root:

```sh
./script/check_all.sh
```

That command is the development regression lane. Its current-source checks
include source safety, Python tests, Swift store tests/build, the real MCP
protocol probe, a bounded load/recovery run, plugin packaging, and release
hygiene. For focused iteration, use the owning narrow test first, then return to
the complete command before closeout.

The load harness is:

```sh
python3 script/load_check.py --calls 1000
```

Its default development run is not a universal production SLA. Use the longer
documented soak and a representative concurrent profile when making an actual
capacity claim.

Keep evidence lanes separate:

- **Development regression:** current source, schemas, tests, builds, protocol
  probes, safety checks, and bounded load/recovery.
- **Runtime Agent flow:** current packaged process and installed plugin, cold
  routing, cancellation, overload, and recovery in the real host.
- **Runtime human flow:** the built macOS app, keyboard/history/conversion/error
  behavior, persistence, and visible state after failure.
- **Distribution/release:** source archive, binary/app bundle, plugin package,
  licenses, checksums/signing where applicable, and hosted release state are
  separate claims.
- **Business/experience acceptance:** mathematical usefulness, task fit, and
  human interaction quality remain owner acceptance, not a test-script PASS.

## Reviewer closeout

Report `PASS`, `FAIL`, or `BLOCKED` for each applicable lane. Every PASS names
the exact current command or runtime flow and the observable it establishes.
Every defect includes a reproducer, affected carrier/seam, impact under normal
and burst use, and the smallest owning regression. List any untested carrier or
capacity assumption explicitly; do not promote it through aggregate green
checks.
