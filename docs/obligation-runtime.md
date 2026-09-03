# Obligation runtime contract

Math Anchor's obligation runtime is the provider-native integration seam for a
local Agent Host or harness. It composes a small number of already registered
mathematical providers without adding a public MCP tool or asking a model to
select from the complete operation catalogue.

The private Agent Host component and its staged Codex plugin use the distinct
id `math-anchor-obligation-runtime`. `math-anchor` is a reserved built-in Agent
Host component id, while the product and its MCP server keep the stable Math
Anchor identity. The dedicated `openadam-math-anchor` marketplace also avoids
displacing the existing `openadam` marketplace during a future activation.

## Request

The current request version is `math-anchor.obligation-set.v0.1`. Obtain its
exact schema with:

```bash
.venv/bin/math-anchor obligation-schema request
```

A minimal request is:

```json
{
  "schemaVersion": "math-anchor.obligation-set.v0.1",
  "obligations": [
    {
      "id": "binomial",
      "kind": "polynomial_identity",
      "claim": {
        "left": "(x + y)^2",
        "right": "x^2 + 2*x*y + y^2",
        "variables": ["x", "y"]
      }
    }
  ]
}
```

The supported obligation kinds and their exact provider contracts are:

| Obligation kind | Current provider | Checked claim |
| --- | --- | --- |
| `polynomial_identity` | `certificate.polynomial_identity` plus the independent standard-library checker | equality of the supplied bounded rational polynomials |
| `expression_equivalence` | `expression.equivalent` | equality or inequality under the supplied domain and definedness policy |
| `dimension_consistency` | `dimension.check` | dimensional consistency only |
| `local_almost_complex_integrability` | `geometry.almost_complex.local_check` | local rational-polynomial `J^2 = -I` and vanishing Nijenhuis components in the supplied coordinate frame |

An unregistered kind is accepted as bounded JSON so the runtime can return
`unsupported` explicitly. It is not lexically mapped to the nearest operation,
and its claim is not executed.

Up to 16 shared assumption sets may be declared and referenced by id. Their
canonical digest is placed in every relevant receipt entry. The runtime does
not parse or prove caller-authored assumption text; the receipt marks it
`bound_not_evaluated`. Assumptions that affect a provider's mathematical
semantics must still be represented in that provider's typed claim fields.

`dependsOn` forms an acyclic dependency graph. An obligation runs only after
all dependencies are `checked`. The graph supplies execution and coverage
ordering; v0.1 does not inject one result value into another claim.

## Feedback and full receipt

The default `responseMode` is `failures_only`. A completely checked set returns
only version, digests, and counts, with an empty `obligations` array. A
falsified, unknown, unsupported, or dependency-blocked entry returns the
relevant bounded detail. Set `responseMode` to `full` only when the caller
needs every entry in its immediate response.

The full receipt is a deterministic local artifact. It contains no timestamp,
so an unchanged request on the same runtime and backend versions reproduces
the same receipt digest. It records provider-result digests and compact result
details rather than embedding unbounded calculation output.

Run a checkpoint and write a new receipt without printing successful output:

```bash
.venv/bin/math-anchor check-obligations request.json \
  --receipt-output build/obligation-receipt.json \
  --quiet-success
```

The command refuses to overwrite an existing receipt. Exit status is `0` when
every obligation is checked, `1` when attention is required, and `2` for an
invalid request or runtime/receipt error. `--quiet-success` suppresses stdout
only for exit status `0`; actionable feedback and structured errors remain
visible.

Replay against a prior full receipt with:

```bash
.venv/bin/math-anchor replay-obligations \
  request.json build/obligation-receipt.json
```

Replay validates the prior receipt's content, entry details, outcome digest,
and self-digest before execution. It returns `matched`, `runtime_drift`, or
`outcome_drift`. Runtime drift with the same outcome is still reportable drift;
it is not silently accepted as the same execution.

## Assurance and scope

Every entry uses one of these statuses:

- `checked`: the registered provider established exactly the declared scope;
- `falsified`: the provider found an exact contradiction or counterexample;
- `unknown`: resources, dependencies, a rejected certificate, or the method
  left the outcome unresolved;
- `unsupported`: no registered provider owns the obligation kind or its
  mathematical input domain.

Assurance levels are `formal_kernel_checked`, `exact_symbolic`,
`rigorous_interval`, `numerical`, and `heuristic`. A level is `null` when no
provider established an outcome. The current obligation providers produce
`exact_symbolic` for established finite claims. The existing optional Lean
bridge remains separate; ordinary polynomial receipts do not claim kernel
acceptance.

No receipt establishes that an Agent translated prose correctly, selected all
proof obligations, used every necessary theorem, or proved the surrounding
mathematical result. Domain packs and harnesses must keep those omissions in
their own coverage reports.
