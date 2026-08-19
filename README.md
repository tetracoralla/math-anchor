# Math Anchor

Math Anchor is one product with two quiet entry points:

- a native macOS calculator for people, with familiar basic/scientific input, lightweight offline physical-unit conversion, ECB reference currency conversion with visible source and freshness, a read-only calculator display, optional exact-value copy, and local history;
- a safe scientific runtime for Agents, with one-call typed execution through `math.run` and optional discovery or batch tools.

Both surfaces use the same Python calculation core. The Agent catalog currently provides 31 typed operations spanning exact arithmetic, algebraic transforms, semantic and solution verification, single- and multivariable calculus, numerical roots, all-roots search, and certified interval-arithmetic global optimization, adaptive numerical integration with explicit accuracy metadata, exact and stability-aware approximate linear algebra, number theory, combinatorics, financial math, probability, descriptive and inferential statistics, unit conversion, and unit-bearing expressions. The project reuses SymPy, NumPy, mpmath, and Pint for mathematics; its own work is the safe parser, capability catalog, structured result contract, isolation boundary, human app, and Agent-facing interface.

Currency conversion is an online, human-app feature calculated from the European Central Bank's daily euro reference rates. The interface shows the source, publication time, and current or expired state; cached rates remain explicitly marked when a refresh cannot complete. These rates are informational and are not transaction quotes. Currency conversion remains an app-internal request and does not add another public MCP tool or Agent operation.

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

Start the MCP server with:

```bash
.venv/bin/math-anchor-mcp
```

The installable Codex Plugin source is in `plugins/math-anchor/`.

`script/package_runtime.sh` builds the standalone mathematical runtime used by both the installed plugin and the macOS app bundle. The packaged app and plugin do not depend on this repository or its `.venv` after installation.

Generated runtimes are deliberately excluded from Git. Before installing the
local Plugin, run `./script/bootstrap.sh`, `./script/package_runtime.sh`, and
`./script/check_all.sh`. Then install this checkout as a local Codex marketplace:

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
