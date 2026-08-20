# Releasing Math Anchor

## Source repository

The Git repository contains source, exact version-and-hash dependency locks, tests, Plugin
configuration, and release tooling. Generated files under
`plugins/math-anchor/runtime/`, `.build/`, and `dist/` are intentionally ignored.
Do not force-add them to source history.

The version on `main` is the current source and Plugin milestone. Merging a
version bump does not by itself publish or support a downloadable macOS binary.
Record notable source behavior in `CHANGELOG.md`; create a GitHub Release only
through the signed, notarized, matching-tag workflow described below.

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
contains a virtual environment, Plugin runtime, Swift/build cache, benchmark
receipt, or app artifact. `check_all.sh` uses the separate
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

Keep `main` protected after publication: changes arrive through pull requests,
both macOS matrix jobs are required and up to date, and administrators follow
the same rule. Keep secret scanning with push protection, Dependabot alerts and
security updates, and CodeQL default setup enabled. Repository Actions are
limited to GitHub-owned actions; every workflow reference is pinned to an
immutable commit SHA.

## Dependency lock updates

Regenerate the development lock against the CI Python patch version and verify
that both macOS architectures resolve the same file:

```bash
uv pip compile pyproject.toml --extra dev --python-version 3.11.9 \
  --python-platform aarch64-apple-darwin --generate-hashes --no-annotate \
  --no-header --output-file requirements-dev.lock
uv pip compile pyproject.toml --extra dev --python-version 3.11.9 \
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
start a fresh Codex task. For a repeatable CLI installation from this checkout,
use:

```bash
codex plugin marketplace add .
codex plugin add math-anchor@openadam
```

The installed Plugin is healthy only when its loaded
Skill and all four tools (`math.search`, `math.describe`, `math.run`, and
`math.batch`) are visible together. A source checkout without the generated
runtime is intentionally not an installable Plugin artifact.

To exercise the independent installed copy rather than the source directory,
pass its path from `codex plugin add` back to the transport check:

```bash
.venv/bin/python script/check_mcp.py \
  --plugin-root ~/.codex/plugins/cache/openadam/math-anchor/0.2.0
```

## Signed macOS artifacts

Never upload `dist/Math Anchor.app` from `build_and_run.sh`; it is a local
development artifact. Distribution requires a Developer ID Application
identity and a configured `notarytool` keychain profile:

1. Update the canonical version in `pyproject.toml` and mirror it in
   `plugins/math-anchor/.codex-plugin/plugin.json`.
2. Merge the release commit through the protected `main` branch and wait for
   both architecture jobs to pass.
3. From a clean checkout of that commit, create an annotated tag such as
   `git tag -a v0.2.0 -m "Math Anchor 0.2.0"`.
4. Run the release command below on the matching architecture.

```bash
export MATH_ANCHOR_APP_VERSION=0.2.0
export MATH_ANCHOR_BUILD_NUMBER=1
export MATH_ANCHOR_CODESIGN_IDENTITY="Developer ID Application: Example (TEAMID)"
export MATH_ANCHOR_NOTARY_PROFILE="math-anchor-notary"
# Set this as well when the profile lives in a non-default keychain.
export MATH_ANCHOR_NOTARY_KEYCHAIN="/path/to/release.keychain-db"
export MATH_ANCHOR_EXPECTED_ARCH="$(uname -m)"
./script/release_macos.sh
```

The release script builds with Swift's release configuration, validates the
clean annotated source tag, canonical App/Plugin/Python/runtime version, build
number, runtime manifest, and target architecture. It signs nested Mach-O files
with the hardened runtime, regenerates the embedded SBOM and file manifest from
those final signed bytes before sealing the outer app, verifies the bundle, submits it for notarization,
staples and validates the ticket, runs Gatekeeper assessment, and only then
creates the final architecture-labelled zip, detached SHA-256 checksum, and
architecture-labelled SPDX SBOM. Build arm64 and x86_64 artifacts
on matching hosts; do not relabel one architecture as another.

Pushing the annotated release tag runs `.github/workflows/release.yml` on both
matching GitHub macOS architectures and publishes a GitHub Release only after
both signed artifacts pass notarization and checksum verification. Configure
these repository Actions secrets before pushing the tag:

- `APPLE_DEVELOPER_ID_P12_BASE64`: base64-encoded Developer ID Application
  certificate and private key in PKCS#12 format;
- `APPLE_DEVELOPER_ID_P12_PASSWORD`: password for that PKCS#12 file;
- `APPLE_NOTARY_KEY_ID` and `APPLE_NOTARY_ISSUER_ID`: App Store Connect API key
  identifiers;
- `APPLE_NOTARY_PRIVATE_KEY_BASE64`: base64-encoded App Store Connect `.p8`
  private key.

The workflow imports credentials into an ephemeral runner keychain, explicitly
uses that same keychain for the notarization submission, and does not place the
credentials in the source tree or release assets. Without these five configured
secrets, the release job fails closed before signing. It also refuses to replace
assets on an existing GitHub Release: correcting published bytes requires an
explicitly new version and tag rather than silently changing an old release.

Signing identities and notarization credentials are owner-controlled secrets.
Their absence is an honest binary-release blocker, not something the source
checks can waive.
