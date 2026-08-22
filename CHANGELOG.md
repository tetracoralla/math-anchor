# Changelog

This file records notable user-visible source and Plugin changes. A source
milestone is not automatically a downloadable macOS release: signed binaries
are supported only when a matching tag, GitHub Release, Developer ID signature,
and Apple notarization record exist.

## Unreleased

### Fixed

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
