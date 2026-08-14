# Security policy

## Supported versions

Security fixes are applied to the latest source on the default branch. No binary
release is supported until a release is explicitly published with a version,
Developer ID signature, notarization record, and matching source tag.

## Reporting a vulnerability

Please use GitHub's private vulnerability reporting for this repository. Do not
open a public issue for an unpatched vulnerability or include secrets, personal
data, or exploit payloads in a public report.

Include the affected version or commit, entry point (macOS app, CLI, MCP, or
Plugin), the smallest reproduction, expected impact, and whether the issue can
escape the parser, worker resource boundary, output budget, or local cache
boundary.

## Scope reminders

- Mathematical disagreement without a reproducible contract violation is a
  correctness report, not automatically a security vulnerability.
- The only public MCP tools are `math.search`, `math.describe`, `math.run`, and
  `math.batch`.
- Generated applications or runtimes copied from an untagged local build are
  development artifacts and are not supported release binaries.
