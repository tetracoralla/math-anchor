# Changelog

This file records notable user-visible source and Plugin changes. A source
milestone is not automatically a downloadable macOS release: signed binaries
are supported only when a matching tag, GitHub Release, Developer ID signature,
and Apple notarization record exist.

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
