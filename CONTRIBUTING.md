# Contributing to Math Anchor

Thank you for helping improve Math Anchor. Contributions should preserve one
deterministic calculation core shared by the macOS calculator, CLI, MCP server,
and Codex Plugin.

## Before opening a change

- Use macOS 14 or newer with Xcode Command Line Tools, Swift 6, and Python 3.11
  or newer.
- For a security vulnerability, use the repository's
  [private vulnerability reporting](https://github.com/tetracoralla/math-anchor/security/advisories/new)
  instead of a public issue.
- For behavior changes, describe the user task and the affected human or Agent
  flow before proposing new fields, tools, or UI.

## Set up and verify

```bash
./script/bootstrap.sh
./script/check_all.sh
```

`check_all.sh` runs the Python regression suite, Swift state checks and build,
the packaged four-tool MCP transport, Plugin validation, dependency/license
closure, and release-hygiene checks. A UI change also needs current rendered
inspection; automated checks do not decide visual acceptance.

Do not commit generated output under `.build/`, `dist/`, or
`plugins/math-anchor/runtime/`.

## Change requirements

- Keep the public MCP surface to `math.search`, `math.describe`, `math.run`, and
  `math.batch`; add operations to the registry.
- Keep exact and approximate results distinct.
- Never use Python `eval`, `exec`, string `sympify`, or `parse_expr` for input.
- Add the smallest negative regression for parser, validation, timeout,
  packaging, or error-path fixes.
- Keep Agent schemas, protocol metadata, and engine details out of the human
  calculator UI.
- Update `pyproject.toml` and the Plugin manifest together when changing the
  product version.

## Report and repair a wrong calculation

Include the user request, selected tool and operation, structured arguments,
complete result or stable error code, Math Anchor version, and whether the
problem reproduces through the packaged Plugin. Remove private business data
before posting a public issue.

Classify the defect before fixing it:

- wrong request translation or premature tool selection belongs in the product
  Skill and cold-session routing probes;
- rejected valid input or accepted invalid input belongs in the schema,
  validation, and a negative regression;
- a wrong successful value belongs in the shared calculation core plus an
  independent oracle or invariant regression;
- a crash, timeout, memory breach, cancellation failure, or malformed response
  belongs at the worker or transport boundary;
- packaging-only failure must reproduce from the installed Plugin rather than
  only the source checkout.

After a repair, rebuild the standalone runtime, reinstall the Plugin, start a
fresh Codex task, and rerun the original failing request plus the nearest
boundary cases. Do not close a wrong-result report from a unit test alone.

## Pull requests

Create a focused branch, keep unrelated changes out of the patch, and explain:

1. the behavior or risk being changed;
2. the source and tests that establish the new behavior;
3. the development, Agent runtime, and human runtime lanes actually verified;
4. any acceptance lane that remains pending.

The protected `main` branch requires both macOS architecture jobs to pass.
Signing credentials, notarization credentials, release tags, and published
artifacts remain maintainer-controlled.
