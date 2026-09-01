# Math Anchor Lean reference consumer

This is an external consumer of Math Anchor's
`math-anchor.polynomial-identity.v1` certificate, not another MCP tool and not
part of the macOS calculator. It checks the certificate with the independent
standard-library checker, translates the certificate's restricted source
expressions to Lean syntax without textual interpolation, and asks the pinned
Lean kernel to accept a generated equality theorem.

The consumer emits a separate `certificate_kernel_check` result. It never
changes the producing `math.run` result, whose `checkedBy` field remains null.
Digests bind the checked artifact to the input certificate but do not prove the
mathematics; only successful elaboration and kernel checking of the generated
theorem controls the `kernel_checked` claim.

The default bootstrap owns an isolated Elan toolchain. A Controller that has
already verified the same pinned Lean release may instead pass its exact Lake
executable with `--lake`; the result records that executable's digest and still
uses this consumer's separate project, translator, and disposable run source.

The first public research fixture is the `n = 4` identity associated with
Putnam 1976 A2:

```text
(x + y)^4 + (x^4 + y^4) = 2 * (x^2 + x*y + y^2)^2
```

This bounded identity is a bridge fixture, not a proof of the original
all-natural-numbers Putnam problem. The broader problem is tracked separately
as a candidate Agent task.

Run from the repository root:

```sh
./script/bootstrap_lean_reference.sh
.venv/bin/python script/lean_reference_check.py --fixture putnam-1976-a2-n4
```

The bootstrap downloads a checksum-pinned `elan` release into the disposable
`/private/tmp/math-anchor-lean-reference-<uid>/` state directory, installs the
pinned Lean toolchain only under that directory, and resolves Mathlib from this
project's lock in a disposable copy of the reference project. Set
`MATH_ANCHOR_LEAN_STATE_DIR` to choose another isolated location. It does not
modify the shell profile or install a system/Homebrew package. Keeping both the
toolchain and `.lake` binary state outside cloud-synchronized source avoids File
Provider rewriting or evicting Lean's compiled artifacts.
