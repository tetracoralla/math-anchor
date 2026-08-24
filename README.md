# Math Anchor

Math Anchor is one product with two quiet entry points:

- a native macOS calculator for people, with familiar basic/scientific input, lightweight offline physical-unit conversion, ECB reference currency conversion with visible source and freshness, a read-only calculator display, optional exact-value copy, and local history;
- a safe scientific runtime for Agents, with one-call typed execution through `math.run` and optional discovery or batch tools.

Both surfaces use the same Python calculation core. The Agent catalog currently provides 44 typed operations spanning exact and high-precision arithmetic, explicit decimal rounding and integer-division conventions, fixed-width machine arithmetic, programmer representations and bit operations, IEEE-754 inspection, algebra and calculus, verification, numerical methods, exact and diagnostic numerical linear algebra, number theory, combinatorics, finance, probability and statistical inference, covariance-based measurement-uncertainty propagation, stable unit discovery and conversion, unit-bearing expressions, and symbolic dimensional analysis. The project reuses SymPy, NumPy, mpmath, and Pint for mathematics; its own work is the safe parser, capability catalog, structured result contract, isolation boundary, human app, and Agent-facing interface.

Currency conversion is an online, human-app feature calculated from the European Central Bank's daily euro reference rates. The interface shows the source, publication time, and current or expired state; cached rates remain explicitly marked when a refresh cannot complete. These rates are informational and are not transaction quotes. Currency conversion remains an app-internal request and does not add another public MCP tool or Agent operation.

## Unreleased source capabilities

- Fixed-width integer representation and bitwise operations expose binary,
  octal, decimal, hexadecimal, character, overflow, wrap, and discarded-bit
  semantics explicitly.
- Machine arithmetic makes checked, wrapping, and saturating overflow plus
  truncating, floor, and Euclidean division explicit. Bit-field extraction,
  insertion, zero/population counts, reversal, and alignment stay width-bound.
- IEEE-754 binary32/binary64 inspection exposes raw fields, classification,
  exact represented value, ULP, adjacent values, signed zero, and bit-versus-
  numeric equality without presenting a binary approximation as exact input.
- Decimal quantization supports named tie and directed-rounding modes, while
  integer division distinguishes truncating, floor, and Euclidean quotients.
- `units.search` provides 89 stable unit IDs. Data quantity/rate, frequency,
  force, acceleration, torque, and density also appear in the human conversion
  picker. Calendar months and years require an explicit average-duration policy
  and are never presented as civil date arithmetic.
- Exact vector/matrix algebra is separate from binary64 least squares, QR, SVD,
  and pseudoinverse operations with rank, condition, and residual diagnostics.
- Probability and inference add Beta, Gamma, lognormal, paired/two-sample t,
  and chi-square methods. `measurement.propagate` adds first-order covariance
  propagation with positive-semidefinite correlation validation.
- Agent execution now has bounded admission, a 4 GiB weighted request-memory
  budget, a reserved interactive lane during batches, safe duplicate batch
  coalescing, real sibling cancellation, adaptive worker recycling/prewarming,
  a provider circuit breaker, and stable retry guidance. The four-tool listing
  remains below its 40,000-byte discovery veto.

## What's new in 0.2

- `dimension.check` verifies both sides of a symbolic formula plus additive and
  dimensionless-function constraints.
- `dimension.infer` solves exact dimensional constraints and distinguishes
  unique, underdetermined, and inconsistent systems.
- `dimension.pi_groups` returns a deterministic exact basis of Buckingham Pi
  dimensionless products without claiming that the basis is physically unique.
- The Agent runtime now reuses bounded workers, prewarms one worker during MCP
  startup, propagates cancellation, and applies the output byte budget to
  success and error envelopes.
- The Codex Plugin remains one self-contained installation with four public MCP
  tools and 34 typed operations; no symbolic-dimensional controls were added to
  the human calculator.
- Patch 0.2.1 makes MCP domain/input failures explicit tool-execution errors and
  reports the Math Anchor product version during server initialization.

See [CHANGELOG.md](CHANGELOG.md) for the source milestone details and
[docs/dimensional-analysis.md](docs/dimensional-analysis.md) for the capability
and claim boundaries.

## Requirements

- macOS 14 or newer;
- Xcode Command Line Tools with Swift 6;
- Python 3.11 or newer.

The repository publishes source. Downloadable macOS applications are supported
only when attached to a versioned GitHub Release with a matching source tag,
Developer ID signature, and Apple notarization record.

## Run the macOS app

```bash
./script/bootstrap.sh
./script/build_and_run.sh
```

The Codex app also exposes the same command as the repository's **Run** action.

## Use the local runtime

```bash
.venv/bin/math-anchor search calculus
.venv/bin/math-anchor describe calculus.integrate
.venv/bin/math-anchor run expression.evaluate '{"expression":"sqrt(2)","precision":50}'
```

Symbolic dimensional analysis uses the same `run` entry point:

```bash
.venv/bin/math-anchor run dimension.check \
  '{"left":"F","right":"m * a","symbols":{"F":"newton","m":"kilogram","a":"meter / second^2"}}'

.venv/bin/math-anchor run dimension.infer \
  '{"equations":[{"left":"F","right":"m * a"}],"known":{"F":"newton","m":"kilogram"},"unknown":["a"]}'

.venv/bin/math-anchor run dimension.pi_groups \
  '{"variables":{"rho":"kilogram / meter^3","v":"meter / second","L":"meter","mu":"pascal * second"}}'
```

Start the MCP server with:

```bash
.venv/bin/math-anchor-mcp
```

## Agent tool model

Math Anchor keeps a stable four-tool MCP boundary while the operation registry
grows:

| Tool | Use |
| --- | --- |
| `math.run` | Run one known typed operation. This is the normal one-call route. |
| `math.batch` | Run 1 to 32 independent operations in input order. |
| `math.search` | Find an operation only when its stable id is not already known. |
| `math.describe` | Retrieve the exact schema and examples for one selected unfamiliar operation. |

Exact and approximate results remain separate. Mathematical and dimensional
expressions pass explicit AST allowlists rather than Python evaluation, and
expensive Agent work runs behind cumulative time, memory, cancellation, and
output limits.

High-frequency structured callers should keep one MCP session open and call the
same four tools directly; they do not need a model turn per calculation. See
[docs/agent-runtime.md](docs/agent-runtime.md) for admission, retries, load
evidence, and direct-host usage.

The installable Codex Plugin source is in `plugins/math-anchor/`.

Symbolic formula checks and dimension inference are documented in
[docs/dimensional-analysis.md](docs/dimensional-analysis.md). They report
dimensional consistency only and never claim that a physical law is correct.

`script/package_runtime.sh` builds the standalone mathematical runtime used by both the installed plugin and the macOS app bundle. The packaged app and plugin do not depend on this repository or its `.venv` after installation.

Generated runtimes are deliberately excluded from Git. Before installing the
local Plugin, run `./script/bootstrap.sh`, `./script/package_runtime.sh`, and
`./script/check_all.sh`. Then register this checkout as a local Codex
marketplace and install the Plugin from it — the `openadam` marketplace name
resolves against this checkout, not a public registry:

```bash
codex plugin marketplace add .
codex plugin add math-anchor@openadam
```

Start a fresh Codex task after installation. The four MCP tools and the
calculation Skill must become visible together. The desktop app's local Plugin
installation flow may also select `plugins/math-anchor/` directly.

Bootstrap accepts any available Python 3.11 or newer interpreter. Set `MATH_ANCHOR_PYTHON` only when selecting a specific interpreter. The Swift scripts select an installed SDK compatible with the active compiler; `MATH_ANCHOR_SDKROOT` is available as an explicit override.

## Verify

```bash
./script/check_all.sh
```

This runs Python regression tests, Swift state checks/build, the four-tool MCP discovery and execution flow, and plugin validation. Human visual acceptance remains separate from those development checks.
For a GitHub-generated ZIP or tarball without `.git` metadata, run
`./script/check_source_layout.sh --archive-clean` once immediately after
extraction and before the first `check_all.sh`; subsequent development checks
are intentionally repeatable after the runtime has been generated.

## Publishing

Publish source from a clean checkout or an unmodified GitHub-generated source
archive; do not force-add
`plugins/math-anchor/runtime/`, `.build/`, or `dist/`. Runtime dependencies are
exactly pinned and SHA-256 verified in `requirements-runtime.lock`, including
dependencies activated through package extras. Bootstrap installs the complete
development lock with pip's `--require-hashes`. Each generated runtime includes artifact-derived
`THIRD_PARTY_NOTICES.txt`, an SPDX SBOM covering bundled Python distributions,
the PyInstaller bootloader, and every standalone native library, plus an
architecture/file manifest. An unmapped native library or unpinned bundled
distribution fails packaging.

Current local `.app` bundles are development artifacts, not downloadable
releases. Developer ID signing and Apple notarization are mandatory gates in
`script/release_macos.sh`; tagged releases build both macOS architectures and
publish detached checksums plus SPDX SBOMs through the pinned GitHub workflow.
See [docs/releasing.md](docs/releasing.md) for the
source, Plugin, CI, per-architecture, and signed binary workflow.

## Contributing and security

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup, change boundaries, and pull
request expectations, and [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) for community
standards. Report vulnerabilities through GitHub private vulnerability
reporting as described in [SECURITY.md](SECURITY.md), never in a public issue.
