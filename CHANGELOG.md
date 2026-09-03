# Changelog

This file records notable user-visible source and Plugin changes. A source
milestone is not automatically a downloadable macOS release: signed binaries
are supported only when a matching tag, GitHub Release, Developer ID signature,
and Apple notarization record exist.

## Unreleased

### Added

- Added the provider-native `math-anchor.obligation-set.v0.1` Python/CLI
  contract without adding a fifth MCP tool. It supports bounded obligation
  DAGs, shared caller-assumption digests, `checked`/`falsified`/`unknown`/
  `unsupported` outcomes, exact assurance and scope, deterministic replayable
  receipts, default failures-only feedback, and a silent-success checkpoint
  mode. The initial conformance corpus covers an injected algebra sign error,
  strict-definedness mismatch, dimensional mismatch, unsupported domain, and
  dependency blocking.
- Added `geometry.almost_complex.local_check`, a bounded rational-polynomial
  verifier for `J^2 = -I` and coordinate-basis Nijenhuis components in one
  supplied even-dimensional chart. It returns an exact first counterexample
  and names the global obligations it does not check. The registry now contains
  46 operations while the public MCP boundary remains four tools.
- Added assurance contract version `1.0`, operation-path and selected-backend
  provenance, plus an optional Lean 4.33.1/Mathlib 4.33.1 bridge that translates
  a true rational-polynomial certificate into a generated theorem and records
  `kernel_checked` only after Lean accepts the proof. The formal toolchain stays
  outside the ordinary runtime and four-tool MCP surface.
- Added one runtime-owned assurance envelope to every successful Agent result,
  including claim scope, assumptions, runtime/backend versions, certificate
  presence, and actual kernel-check identity. Added the bounded
  `certificate.polynomial_identity` operation plus a separate standard-library
  checker that recomputes its rational-polynomial statement and coefficients
  without importing SymPy or the producing operation.
- Added verified wheel and source-archive builds, x86_64 and arm64 Linux CI,
  and a digest-pinned non-root OCI runtime definition. Versioned GitHub releases
  now collect the headless Python artifacts beside the signed macOS assets.
- Expanded the existing `calculus.multivariate` operation with exact
  unnormalized directional derivatives, divergence, three-dimensional curl,
  and the Laplacian. Expanded `matrix.reduce` with exact eigenspaces and
  diagonalizability plus row-pivoted LU and positive-definite Hermitian
  Cholesky decompositions, including explicit factor relations and negative
  shape/domain regressions. This work brought the registry to 45 operations;
  the later local-geometry verifier brings the current total to 46 while the
  MCP boundary remains four tools.
- Added safe-expression registrations for Airy Ai/Bi, Bessel Y, beta, and
  polygamma alongside the existing Bessel J, gamma, error, Lambert W, and zeta
  functions; calls still pass the explicit AST/function whitelist.
- Added a 30-task paired Coding Agent evaluation corpus, independent
  Controller-side expected-value checks, natural-routing smoke, and an
  exact-model-call-confirmed runner that keeps reports out of source control;
  separate unassisted and provider-neutral-policy lanes prevent spontaneous MCP
  discovery from being conflated with policy-guided routing. A disposable
  single-Plugin Codex lane separately measures installed Skill/MCP activation
  without unrelated user Plugin contamination.
- Added a separate zero-model direct-host cold-smoke lane for 13 structured
  Coding Agent workloads. It fingerprints the local driver, OS-denies the
  provider from Controller oracles, grades typed Math Anchor results, preserves
  unknown cost, and stays structurally separate from Agent routing and utility
  claims.
- Added independently graded public-mathematics Agent suites for specialized
  Putnam 2023 B1/B6 tasks, NIST Hilbert-matrix diagnostics, and Buckingham-Pi
  nullity. Terra/Luna smoke and a bounded repeated Luna lane keep incomplete or
  over-budget runs from being promoted into adoption or utility claims.

- Expanded the typed Agent registry from 34 to 44 operations without adding a
  fifth MCP tool: programmer integer/bitwise semantics, decimal quantization,
  explicit signed division, stable unit search, exact vector algebra,
  diagnostic QR/SVD/least-squares/pseudoinverse, and first-order covariance
  propagation.
- Added fixed-width checked/wrapping/saturating machine arithmetic, bit-field
  extraction/insertion, population and zero counts, bit reversal, alignment,
  and IEEE-754 binary32/binary64 inspection and comparison with exact
  represented values, ULPs, adjacent values, signed zero, and NaN handling.
- Added Beta, Gamma, and lognormal PDF/CDF/quantiles plus paired t, Welch/equal
  variance two-sample t, and Pearson chi-square goodness-of-fit inference.
- Added data quantity/rate, frequency, force, acceleration, torque, and density
  to the human conversion catalog, backed by the same Pint conversion core.
- Rejected implicit month/year duration conversion and required an explicit
  average-duration policy with a non-civil-calendar warning.
- Added a repeatable supervisor load/soak gate (`script/load_check.py`, a
  10,000-call default lane; the complete development verification runs the
  1,000-call form) whose 13-case Coding Agent profile verifies representative
  programmer, numeric, unit, uncertainty, finance, and dimension results under
  serial and concurrent traffic, mixed caller failures, batch
  ordering/coalescing, cancellation storms, worker-crash recovery, bounded
  latency sampling, process-tree RSS trend, and final resource cleanup.

### Fixed

- Aligned protocol-level MCP `isError` with structured failures for discovery
  tools as well as calculation tools, so an unknown operation or invalid search
  category cannot be mistaken for a successful tool call.
- Kept caller-correctable obligation input rejections `unsupported`, while a
  missing operation for an already-bound Provider is now `unknown` instead of
  hiding registry, package, or runtime drift as an unsupported claim.
- Assigned the expanded obligation runtime the distinct `0.6.0` product
  identity so Plugin caches and replay receipts cannot confuse it with the
  previously installed 45-operation `0.5.0` runtime.
- Made receipt publication atomic and no-clobber: a failed write removes its
  private staging file and never strands invalid JSON at the requested path.
- Tightened catalog support classification so registered concepts must cover
  the substantive English or Chinese query, while retaining explicit Chinese
  task aliases.

### Performance

- Precomputed the immutable operation search index, lazy-loaded command-only
  CLI modules, removed the single-obligation thread-pool hop, and reduced the
  always-loaded Skill plus four-tool catalog without weakening runtime schema
  validation.
- Removed the duplicate macOS Python Framework copy only after proving it is
  byte-identical to the materialized standalone loader and contains no
  unexpected payload, and excluded unreferenced NumPy random/FFT feature
  families from the self-contained carrier.

- Made multi-concept catalog search require two substantive term matches or a
  registered phrase, and added `matchStatus: no_registered_operation` for zero
  matches. This prevents one generic lexical collision from being presented as
  support for an unrelated mathematical domain.
- Kept fully specified fixed-width machine arithmetic on the one-call path by
  loading the machine-semantics reference only when a representation,
  bit/IEEE, rounding, division, or missing-convention policy is actually needed.
- Corrected interval optimization for ordinary SymPy function nodes,
  non-monotone `cosh`, inverse-trigonometric endpoints, and directed interval
  rounding. Its contract now distinguishes an internal mpmath interval bound
  from an external certificate or proof-kernel result.
- Bound production and reference Lean subprocess output while draining both
  pipes, terminate timed-out process groups, require one complete axiom
  readback with no `sorryAx`, and bind checks to exact transitive Mathlib
  revisions and executable/manifest digests.
- Bound Agent-evaluation reports to the repository build directory, stage the
  packaged runtime outside denied source roots, and reject evaluator, task,
  run-membership, isolation, or target-server identity drift before a report
  can be treated as comparison-valid.
- Canonicalized macOS and Linux host/binary architecture aliases in runtime
  manifests and Swift setup, validated shared dependency locks against
  supported platform markers, used the repository's exact lowercase Swift
  test path, and restored idle worker unit-registry warming after
  bounded-ingress refactoring. Cross-host cancellation, warmup, and app-timeout
  checks now observe the intended lifecycle instead of assuming one fixed
  machine-speed interval.
- Made local Plugin installation consume Codex's authoritative
  `installedPath`, compare the installed bytes before execution, and reject an
  MCP route that does not resolve to that exact installed artifact.
- Gave the assurance/Lean milestone the distinct `0.5.0` package identity so a
  verified Plugin installation cannot retain older bytes behind version
  `0.4.0`.
- Returned scalar derivative contracts for directional derivative, divergence,
  and the Laplacian while retaining matrix contracts and shapes for gradient,
  Jacobian, Hessian, and curl. This keeps mathematical rank aligned across the
  registry, runtime, and MCP result schema.
- Kept the installed Codex `math.run` declaration typed by replacing the
  oversized always-listed 45-branch union with a compact host-safe envelope
  carrying every stable operation id and execution limit. Exact closed
  argument schemas remain registry-owned, are returned by `math.describe`, and
  are still enforced before execution; current Codex no longer compacts the
  entire model-facing call into `args: unknown`.
- Made model-backed evaluation preflight compare the versioned experiment's
  declared Codex CLI against the installed harness before spending any model
  calls, so host upgrades fail before producing an invalid comparison.
- Pinned the paired Luna experiments to low reasoning effort in both
  conditions instead of inheriting an ambient/default setting that could spend
  more than 100,000 tokens before a required calculation reached the tool.
- Isolated both `CODEX_HOME` and `HOME` for installed-Plugin Agent evaluation,
  and made preflight require the packaged Math Anchor Skill while rejecting
  ambient `~/.agents/skills` leakage.
- Promoted fixed-width machine arithmetic and large exact combinatorial counts
  to mandatory Skill triggers with their direct operation mappings, avoiding
  both mental fallback and unnecessary discovery on common high-risk tasks.
- Put the same two complete direct argument shapes in the always-visible
  `math.run` description and explicitly excluded them from `math.describe`, so
  a cold Agent need not load an 8.7 KB operation schema before one known call.
- Gave this expanded capability milestone the distinct `0.4.0` package
  identity and added byte-for-byte source-versus-cache validation plus a fresh
  Codex Skill-path check to the installation workflow, preventing an older
  runtime from remaining active behind the same version.
- Serialized conversion-popover dismissal, mode-menu presentation, and every
  pointer/menu/shortcut mode transition so the anchor remains mounted until
  AppKit finishes closing its panel, preventing an AX-invisible ECB rate
  popover from remaining over the Basic keypad until app restart.

- Kept matrix-valued `exact` and `approx` results valid in the compact advertised
  `math.run` output contract, closing a carrier rejection that affected existing
  gradient, Jacobian, and Hessian results as well as the new vector-calculus lane.
- Cancel and join an in-flight adaptive worker prewarm during runtime shutdown,
  classify the cancellation separately from provider startup failure, and make
  the load gate require zero residual child, thread, and file-descriptor deltas.
- Made the installed calculation Skill explicitly classify fixed-width,
  wrapping/saturating, bit-operation, and IEEE-754 tasks as nontrivial machine
  semantics, and repeated the required `{operation, arguments}` nesting at the
  Skill and MCP discovery boundaries so an Agent does not flatten a known
  operation into an invalid `math.run` call.
- Returned exact positive infinity for valid Beta and Gamma density
  singularities at support boundaries instead of leaking an internal
  `E_RUNTIME` failure.
- Rejected complex inputs from exact Euclidean vector operations until an
  explicit complex inner-product convention exists, and exposed whether a
  least-squares minimizer is unique or selected by minimum Euclidean norm.
- Preserved the calculator's base-10 `log` semantics when backspace or another
  edit re-derives a still-open function call before automatic parenthesis
  closure.
- Returned an unconsumed half-open circuit-breaker probe when a call failed
  admission (queue full, cancelled, or timed out before execution), instead of
  leaving the runtime permanently refusing every later call with
  `E_UNAVAILABLE` until a process restart.
- Made only a successful call close an open circuit breaker, so concurrent
  in-flight timeout, memory, or cancellation outcomes cannot bypass the
  open → half-open → healthy-probe recovery sequence.
- Converted an unexpected per-item supervision failure inside `math.batch`
  into that item's structured `E_RUNTIME` envelope instead of failing the
  whole batch call.
- Replaced warm workers prewarmed after resident-memory or dead-worker
  eviction, so sustained eviction pressure no longer decays the warm pool to a
  single process.
- Treated signed zeros as adjacent in IEEE-754 neighbor results, matching the
  total-order convention already used by ULP distance.
- Read the macOS runtime pipe through POSIX `read(2)` instead of
  `FileHandle.availableData`, so a stop closing the descriptor mid-read ends
  the reader normally instead of aborting the app with an uncatchable
  `NSFileHandleOperationException`.
- Selected the release CI gate's workflow runs by file path so renaming the
  CI workflow's display name cannot silently fail every later release.
- Included the project's exact `LICENSE` and `NOTICE` in every generated
  Plugin and app runtime, and covered them with source freshness, manifest,
  release-hygiene, and packaging checks.
- Removed nonessential Python framework aliases that the Codex Plugin installer
  omits, and rejected any other runtime symlink so the installed copy preserves
  the verified file inventory.
- Canonicalized symlinked Python interpreters before virtual-environment
  creation and made bootstrap rebuild an unusable partial environment, fixing
  clean-source startup with relocatable Python distributions.
- Accepted both framework-based and standalone `libpython` PyInstaller layouts
  while requiring their actual loader files to remain regular, making clean
  source packaging portable across Homebrew and uv-managed Python.
- Gave each calculator mode a derived usable-content height and preserved the
  live titlebar safe area while resizing, so mode switches no longer shrink
  the frame and clip the last key row or its lower inset at the rounded edge.
- Kept coalesced currency requests waiting through spurious condition wakes
  and propagated the leader's explicit refresh outcome, rather than inferring
  success from cache timestamps that can legitimately remain unchanged.
- Re-derived the hidden executable expression after backspace so the visible
  `log` key's `log10` runtime spelling cannot leave invisible input behind.
- Preserved timeout errors raised inside matrix inversion, rejected non-ASCII
  integer text and overlong variable names before engine work, and classified
  unprintably large exact integers as `E_OUTPUT_LIMIT` output failures with
  output-phase remediation instead of input-phase `E_LIMIT`.
- Stopped queued batch work once completed results already prove the aggregate
  response cannot fit the requested output budget.
- Required release tags to point into the protected default branch and to have
  green CI before signing, reserved enough workflow time for that wait plus
  notarization, and added a detached checksum for each published SPDX SBOM.
- Forwarded each request's `timeoutMs` to the worker-side in-process
  evaluation bound so budgets between ten and thirty seconds are no longer
  silently cut at the ten-second default.
- Stopped re-judging an already-completed worker response against the
  deadline, which killed healthy workers and discarded in-budget results
  whenever the parent's reader thread was descheduled after reading.
- Reused one output-reader thread for the lifetime of each persistent worker
  instead of creating and joining a new thread pool for every high-frequency
  operation, while still rejecting responses that arrive after the cumulative
  deadline.
- Preserved an earlier outer process alarm and reported the timeout actually
  armed by direct in-process callers, rather than extending nested deadlines
  or always claiming the ten-second default.
- Preserved the original error code with a truncated message when an error
  envelope exceeds the output byte budget, instead of masking the real
  failure as `E_OUTPUT_LIMIT`.
- Applied result projection and output byte limits inside the supervised
  worker before serialization to its stdout pipe, so oversized valid results
  no longer cross the process boundary in full before being rejected.
- Reported tool execution errors through `isError: true` on MCP tool results,
  per the MCP tool-execution error convention, so host frameworks cannot
  mistake a failed call for a successful one.
- Warmed both unit registries on a background thread after a persistent worker
  has been idle for 500 ms, so later unit and dimension work avoids definition
  parsing without stealing CPU from a startup burst of cheap operations.

### Changed

- Defined the 0.4 Agent promise as explicit structured invocation plus
  deterministic execution. Cold natural-language Plugin selection remains a
  separately measured host/model integration experiment and no longer blocks
  release of the direct product contract or implies automatic adoption.
- Split the Python operation catalogue, result contracts, and worker sandbox
  into bounded owning modules while preserving the generated registry and tool
  contracts byte-for-byte. Reduced the always-loaded calculation Skill to its
  routing and one-call contract, moving domain detail into four on-demand
  references guarded by package regressions.
- Split the macOS package into a testable `MathAnchorCore` library and the
  SwiftUI/AppKit `MathAnchor` executable, adding direct Swift Testing coverage
  for formatting, copy semantics, mode-switch race rejection, and shared
  physical conversion.
- Added a 36-request MCP ingress bound before executor submission, bounded
  calculation admission, a 4 GiB weighted global request-memory
  budget, a reserved single-call lane during batches, true running-sibling
  batch cancellation, safe duplicate batch coalescing, adaptive worker
  recycling/prewarming, and a short provider circuit breaker. Structured
  errors now expose retryability, phase, optional delay, and a suggested
  action without requiring Agents to parse prose.
- Removed only non-validating descriptions and titles from the always-listed
  `math.run` union while retaining its complete typed constraints and keeping
  operation prose/examples available through discovery, restoring schema
  headroom after the registry reached 44 operations.

- Matched app-runtime responses by request id across one shared warm worker,
  so abandoning a request (every keystroke in Convert) no longer terminates
  the worker and forces a cold SymPy restart on the next interaction. A
  request timeout only rebuilds the worker when it has stayed silent for the
  whole window.
- Served `currency.convert` on a small executor inside the app runtime
  instead of the stdin loop, so a multi-second ECB fetch no longer freezes
  later expression and unit requests behind it.
- Kept lightweight conversion cancellation non-destructive while restoring
  worker termination for an abandoned heavy expression, so editing a running
  calculation cannot leave the next submission queued behind its ten-second
  in-process timeout.
- Treated malformed app-runtime output as an immediate protocol failure and
  recovery event instead of silently waiting for request deadlines.
- Kept concurrent currency work away from process-global mpmath precision
  cleanup, preventing a provider response from changing numeric context during
  an overlapping local expression evaluation.
- Added real animation transactions to the calculator and conversion
  displays (numeric text roll, secondary expression fade, error fade), which
  the previous `.contentTransition` modifiers could never play without, while
  respecting the system Reduce Motion setting.
- Kept the previous conversion result and rate footer on screen during
  value-only edits instead of flashing `…` and UPDATING on every keystroke;
  the placeholder now waits ~180 ms so warm evaluations no longer flash.
- Unified scientific unary keys (`n!`, `|x|`, `floor`, `ceil`, `1/x`) on the
  familiar trailing-operand scope already used by `sin` and `√x`, instead of
  mixing whole-expression wrapping on adjacent keys.
- Closed unmatched opening parentheses automatically at submission, matched
  `)` input against the executable expression's balance, and scoped operator
  binding to the innermost open group so percent inside parentheses keeps
  familiar additive semantics (`(5+3%)` evaluates to `5.15`).
- Replaced a lone leading zero on digit entry (`0` `0` `5` now reads `5`,
  not `005`), ignored percent directly after an operator, made repeating
  `=` on a shown result a no-op, made undo on a result edit the value
  instead of clearing it, and capped operand entry at 18 digits like the
  Convert face.
- Animated mode, history, and window resizing on one shared 0.2 s timeline,
  clamped a growing window to stay on screen near the right edge, and
  stopped re-asserting window chrome on every keystroke-driven update.
- Focused the unit search field when its popover opens, dismissed popovers
  on calculator keystrokes so digits never edit invisibly behind them, and
  aligned the scientific face into one ten-column key grid.
- Rendered the `pi` constant as `π` on the display, dropped meaningless
  trailing zeros from approximate results, kept mid-entry copies plain
  ASCII, replaced the developer-facing "run script/bootstrap.sh" error copy,
  and gave the memory keys spoken labels ("Memory clear", "Memory recall").

## 0.2.1 - 2026-08-25

### Fixed

- Reported mathematical domain and input failures as MCP tool-execution errors
  while preserving their structured provider-owned error envelopes.
- Reported the Math Anchor product version during MCP initialization instead of
  inheriting the installed MCP SDK version as the server identity.

## 0.2.0 - 2026-08-20

### Added

- Added `dimension.check` for exact symbolic dimensional-consistency checks,
  including additive terms and dimensionless function arguments.
- Added `dimension.infer` for exact constraint-based inference with unique,
  underdetermined, and inconsistent classifications, including partial
  inference when only some symbols are fixed by an underdetermined system.
- Added `dimension.pi_groups` for deterministic primitive-integer Buckingham Pi
  bases with an explicit non-uniqueness warning.
- Added a dedicated dimensional-expression AST, result contracts, multilingual
  discovery terms, Plugin routing guidance, CLI/MCP examples, and negative
  parser/schema regressions.
- Added a Claude Code contract that directs coding Agents to close technical
  decisions autonomously and reserve owner questions for product direction or
  external authorization.

### Changed

- Expanded the typed Agent catalog from 31 to 34 operations without adding a
  fifth public MCP tool.
- Bumped the Python project and Codex Plugin version together from 0.1.0 to
  0.2.0.
- Prewarmed one reusable worker during MCP startup and kept tool intent visible
  while retaining a bounded four-tool listing.
- Documented that symbolic dimensional analysis remains Agent-first and does
  not add protocol or engine concepts to the human calculator UI.

### Fixed

- Separated declared dimension-exponent limits from the larger exact values
  produced by bounded dimensional expressions.
- Aligned dimension exponent schemas with runtime validation and accepted safe
  non-decimal integer literals in dimensional expressions.
- Prevented repeated or in-flight prewarming from leaking or resurrecting
  workers during shutdown.
- Prevented unserializable direct-call errors and unexpected supervisor failures
  from bypassing output limits or permanently consuming worker-pool slots.
- Replaced undrained worker stderr pipes with bounded-tail diagnostics that are
  cleared between reusable requests.
