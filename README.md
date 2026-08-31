# Math Anchor

Math Anchor is one product with two quiet entry points:

- a native macOS calculator for people, with familiar basic/scientific input, lightweight offline physical-unit conversion, ECB reference currency conversion with visible source and freshness, a read-only calculator display, optional exact-value copy, and local history;
- a safe scientific runtime for Agents, with one-call execution for known operations through a Codex-host-safe `math.run` envelope and exact per-operation contracts available on demand.

Both surfaces use the same Python calculation core. The Agent catalog currently provides 45 typed operations spanning exact and high-precision arithmetic, explicit decimal rounding and integer-division conventions, fixed-width machine arithmetic, programmer representations and bit operations, IEEE-754 inspection, symbolic and vector calculus, verification and independently checkable polynomial-identity certificates, numerical methods, exact eigenspaces and matrix decompositions, diagnostic numerical linear algebra, number theory, combinatorics, finance, probability and statistical inference, covariance-based measurement-uncertainty propagation, stable unit discovery and conversion, unit-bearing expressions, and symbolic dimensional analysis. The safe expression grammar includes registered Airy, Bessel, beta/gamma, error, Lambert W, polygamma, and zeta functions without admitting arbitrary code. The project reuses SymPy, NumPy, mpmath, and Pint for mathematics; its own work is the safe parser, capability catalog, structured result contract, isolation boundary, human app, and Agent-facing interface.

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
- `calculus.multivariate` now adds unnormalized directional derivatives,
  divergence, curl, and the Laplacian without adding another public operation.
  `matrix.reduce` adds exact eigenspaces with diagonalizability plus LU and
  Cholesky decompositions while continuing to reject approximate structural
  claims.
- Probability and inference add Beta, Gamma, lognormal, paired/two-sample t,
  and chi-square methods. `measurement.propagate` adds first-order covariance
  propagation with positive-semidefinite correlation validation.
- Agent execution now has bounded admission, a 4 GiB weighted request-memory
  budget, a reserved interactive lane during batches, safe duplicate batch
  coalescing, real sibling cancellation, adaptive worker recycling/prewarming,
  a provider circuit breaker, and stable retry guidance. Every always-listed
  input schema remains below the current Codex host's lossy-compaction boundary,
  and the complete four-tool listing remains below a 10,000-byte regression.
- Every successful Agent result now carries a runtime-owned assurance level,
  claim scope, assumptions, runtime/backend versions, and explicit certificate
  and kernel-check state. `certificate.polynomial_identity` emits a bounded
  rational-polynomial artifact that the separate standard-library checker can
  recompute without SymPy.
- The headless runtime now builds as a verified wheel and source archive, runs
  in Linux CI on x86_64 and arm64, and has a digest-pinned, non-root OCI image
  definition. These paths do not depend on the macOS application.

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

- Python 3.11 or newer for the headless runtime;
- macOS 14 or newer plus Xcode Command Line Tools with Swift 6 for the native
  app.

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

Generate and independently verify a bounded rational polynomial certificate:

```bash
.venv/bin/math-anchor run certificate.polynomial_identity \
  '{"left":"(x+1)^2","right":"x^2+2*x+1","variables":["x"]}' \
  > build/polynomial-certificate.json
.venv/bin/math-anchor verify-certificate build/polynomial-certificate.json
```

The checker recomputes the statement and coefficients without importing SymPy
or the certificate producer. A successful check establishes only the declared
rational-polynomial identity classification; it is not a formal proof-kernel
acceptance.

Start the MCP server with:

```bash
.venv/bin/math-anchor-mcp
```

## Agent tool model

Math Anchor keeps a stable four-tool MCP boundary while the operation registry
grows:

| Tool | Use |
| --- | --- |
| `math.run` | Run one known operation from the complete stable-id enum. This is the normal one-call route. |
| `math.batch` | Run 1 to 32 independent operations in input order. |
| `math.search` | Find an operation only when its stable id is not already known. |
| `math.describe` | Retrieve the exact closed argument schema and examples for one selected unfamiliar operation. |

Exact and approximate results remain separate. Mathematical and dimensional
expressions pass explicit AST allowlists rather than Python evaluation, and
expensive Agent work runs behind cumulative time, memory, cancellation, and
output limits.

High-frequency structured callers should keep one MCP session open and call the
same four tools directly; they do not need a model turn per calculation. See
[docs/agent-runtime.md](docs/agent-runtime.md) for admission, retries, load
evidence, and direct-host usage.

Math Anchor 0.4 supports this explicit structured route. Cold selection from a
fresh natural-language Agent session is host/model-dependent integration
behavior, not a guaranteed zero-configuration feature or a source-release
condition.

Coding Agent adoption and conditional utility are measured through the
repo-owned paired corpus in [docs/agent-evaluation.md](docs/agent-evaluation.md),
including a single-Plugin installed Skill/MCP smoke kept separate from
transport conformance, ambient user configuration, and direct-host performance.
The zero-model structured route has its own cold direct-host smoke via
`script/direct_host_eval.py`; repeated production calls should reuse one MCP
session or use `math.batch`, not start one Agent turn per calculation.

The installable Codex Plugin source is in `plugins/math-anchor/`.

Symbolic formula checks and dimension inference are documented in
[docs/dimensional-analysis.md](docs/dimensional-analysis.md). They report
dimensional consistency only and never claim that a physical law is correct.

`script/package_runtime.sh` builds the standalone mathematical runtime used by both the installed plugin and the macOS app bundle. The packaged app and plugin do not depend on this repository or its `.venv` after installation.

For a headless-only verification and distributable Python artifacts:

```bash
./script/check_headless.sh
.venv/bin/python script/build_python_dist.py build
.venv/bin/python script/build_python_dist.py verify
docker build --tag math-anchor-runtime .
```

The resulting wheel/source archive and OCI definition are release inputs. A
GitHub tag is still required before they become published release assets.

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

This runs Python regression tests, Swift package and state tests/build, the
four-tool MCP discovery and execution flow, and plugin validation. Use
`./script/swift_test.sh` for the focused `MathAnchorCore` SwiftPM suite; it
supplies the framework lookup needed by some Command Line Tools installations.
Human visual acceptance remains separate from those development checks.
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
