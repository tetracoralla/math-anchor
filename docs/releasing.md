# Releasing Math Anchor

## Source repository

The Git repository contains source, exact version-and-hash dependency locks, tests, Plugin
configuration, and release tooling. Generated files under
`plugins/math-anchor/runtime/`, `.build/`, and `dist/` are intentionally ignored.
Do not force-add them to source history.

A clean checkout becomes runnable with:

```bash
./script/bootstrap.sh
./script/check_all.sh
```

Immediately after extracting a GitHub-generated source ZIP or tarball, verify
the original archive before generating any local outputs:

```bash
./script/check_source_layout.sh --archive-clean
./script/bootstrap.sh
./script/check_all.sh
```

`check_all.sh` builds a runtime for the current host, generates third-party
license material and an SPDX SBOM inside it, verifies the complete file
inventory and architecture, then exercises the real Plugin transport.
The explicit `--archive-clean` lane rejects a metadata-free archive that already
contains generated runtime files. `check_all.sh` uses the separate
`--development` lane, so it remains repeatable after its first run generates a
runtime. Both lanes reject symbolic links in any runtime-output path component
and verify that the resolved output path remains inside the source tree.

CI repeats this on GitHub's standard arm64 and Intel macOS runners. A source
release is not ready if either architecture fails.

For the first GitHub publication, create the repository privately, push only the
`main` branch (never `--mirror`), and require both matrix jobs in
`.github/workflows/ci.yml` to pass before changing repository visibility. Before
making the repository public, enable private vulnerability reporting under
Settings > Security > Advanced Security so the route documented in
`SECURITY.md` actually exists. Codex internal refs, ignored build outputs, and
local Git object history are not publication inputs.

## Dependency lock updates

Regenerate the development lock against the CI Python patch version and verify
that both macOS architectures resolve the same file:

```bash
uv pip compile pyproject.toml --extra dev --python-version 3.11.15 \
  --python-platform aarch64-apple-darwin --generate-hashes --no-annotate \
  --no-header --output-file requirements-dev.lock
uv pip compile pyproject.toml --extra dev --python-version 3.11.15 \
  --python-platform x86_64-apple-darwin --constraints requirements-dev.lock \
  --generate-hashes --no-annotate --no-header \
  --output-file /tmp/math-anchor-requirements-dev-x86.lock
cmp requirements-dev.lock /tmp/math-anchor-requirements-dev-x86.lock
```

Use `--upgrade-package <name>` only for dependencies intentionally being
updated. `bootstrap.sh` installs the resulting complete closure with
`--require-hashes`, and `check_release_hygiene.sh` rejects missing, extra, or
version-drifted packages.

## Local Plugin installation

Prepare the self-contained Plugin directory first:

```bash
./script/bootstrap.sh
./script/package_runtime.sh
./script/check_all.sh
```

Then select `plugins/math-anchor/` in Codex's local Plugin installation flow and
start a fresh Codex task. The installed Plugin is healthy only when its loaded
Skill and all four tools (`math.search`, `math.describe`, `math.run`, and
`math.batch`) are visible together. A source checkout without the generated
runtime is intentionally not an installable Plugin artifact.

## Signed macOS artifacts

Never upload `dist/Math Anchor.app` from `build_and_run.sh`; it is a local
development artifact. Distribution requires a Developer ID Application
identity and a configured `notarytool` keychain profile:

```bash
export MATH_ANCHOR_APP_VERSION=0.1.0
export MATH_ANCHOR_BUILD_NUMBER=1
export MATH_ANCHOR_CODESIGN_IDENTITY="Developer ID Application: Example (TEAMID)"
export MATH_ANCHOR_NOTARY_PROFILE="math-anchor-notary"
export MATH_ANCHOR_EXPECTED_ARCH="$(uname -m)"
./script/release_macos.sh
```

The release script builds with Swift's release configuration, validates the
runtime manifest and target architecture, signs nested Mach-O files with the
hardened runtime, verifies the bundle, submits it for notarization, staples and
validates the ticket, runs Gatekeeper assessment, and only then creates the
final architecture-labelled zip. Build arm64 and x86_64 artifacts on matching
hosts; do not relabel one architecture as another.

Signing identities and notarization credentials are owner-controlled secrets.
Their absence is an honest binary-release blocker, not something the source
checks can waive.
