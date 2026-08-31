# Lean kernel bridge

Math Anchor's optional Lean bridge turns a successful, true
`certificate.polynomial_identity` result into a theorem over the rationals and
asks a pinned Lean/Mathlib environment to accept it. This is the first bounded
formal-kernel lane; it is intentionally not a fifth MCP tool and is not bundled
into the ordinary Plugin or macOS runtime.

The bridge applies three distinct checks:

1. the independent Python standard-library checker recomputes the certificate
   statement and rational coefficients without SymPy or the producer;
2. a separate AST translator replaces source variable names with generated
   Lean identifiers and emits only the bounded polynomial grammar;
3. Mathlib's `ring` tactic constructs a proof for the emitted theorem and Lean
   4.33.1 checks the resulting proof term.

The returned `checkedBy` record names the observed Lean version and binds the
exact generated theorem artifact with SHA-256. It establishes the emitted
rational-polynomial theorem, not the correctness of a wider scientific model,
the translation from a user's prose, or any non-polynomial claim.

Run the complete pinned check on macOS:

```bash
./script/check_lean_bridge.sh
```

The first run downloads the official Lean 4.33.1 archive, verifies its pinned
SHA-256 digest, checks out Mathlib 4.33.1 and its locked transitive revisions,
and fetches Mathlib's compiled cache. All generated toolchain, dependency, and
certificate artifacts remain under ignored build directories.

For an existing certificate, bootstrap once and call the optional CLI route:

```bash
LAKE="$(./script/bootstrap_lean.sh | tail -n 1)"
.venv/bin/math-anchor verify-certificate-lean build/polynomial-certificate.json \
  --lake "$LAKE" \
  --project integrations/lean \
  --artifact-output build/lean-bridge/Certificate.lean
```

A false identity, a tampered certificate, an unsupported expression, a missing
toolchain, a timeout, or a Lean rejection returns a structured error and never
produces `assurance: kernel_checked`.
