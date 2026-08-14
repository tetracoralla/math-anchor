# Releasing Zibetha

## Source repository

The Git repository contains source, exact version-and-hash dependency locks, tests, Plugin
configuration, and release tooling. Generated files under
`plugins/zibetha/runtime/`, `.build/`, and `dist/` are intentionally ignored.
Do not force-add them to source history.

A clean checkout becomes runnable with:

```bash
./script/bootstrap.sh
./script/check_all.sh
```

`check_all.sh` builds a runtime for the current host, generates third-party
license material and an SPDX SBOM inside it, verifies the complete file
inventory and architecture, then exercises the real Plugin transport.

CI repeats this on GitHub's standard arm64 and Intel macOS runners. A source
release is not ready if either architecture fails.

## Local Plugin installation

Prepare the self-contained Plugin directory first:

```bash
./script/bootstrap.sh
./script/package_runtime.sh
./script/check_all.sh
```

Then select `plugins/zibetha/` in Codex's local Plugin installation flow and
start a fresh Codex task. The installed Plugin is healthy only when its loaded
Skill and all four tools (`math.search`, `math.describe`, `math.run`, and
`math.batch`) are visible together. A source checkout without the generated
runtime is intentionally not an installable Plugin artifact.

## Signed macOS artifacts

Never upload `dist/Zibetha.app` from `build_and_run.sh`; it is a local
development artifact. Distribution requires a Developer ID Application
identity and a configured `notarytool` keychain profile:

```bash
export ZIBETHA_APP_VERSION=0.1.0
export ZIBETHA_BUILD_NUMBER=1
export ZIBETHA_CODESIGN_IDENTITY="Developer ID Application: Example (TEAMID)"
export ZIBETHA_NOTARY_PROFILE="zibetha-notary"
export ZIBETHA_EXPECTED_ARCH="$(uname -m)"
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
