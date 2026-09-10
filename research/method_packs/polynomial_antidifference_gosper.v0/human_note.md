# Human note (not a formal proof)

This file explains the experimental pack. It is not an obligation, not a Lean
kernel result, and not a claim that a few checked instances prove every
polynomial finite sum.

## Why this is useful

A later task that needs `sum p(k)` for a univariate rational polynomial should
not copy T1's particular antidifference `k(k-1)(2k-1)/6` or T1's number `385`.
It should retrieve this pack, instantiate it on its own summand and bounds, and
keep an independent identity check.

If the only required output is the number, SymPy `summation` is enough and this
pack is overhead. The pack is for a checked evidence pipeline with a named,
restricted interface.

## Key idea

Polynomials are hypergeometric, so Gosper produces a closed antidifference `G`.
In this restricted domain `G` is itself a rational-coefficient polynomial.
Construction may use SymPy. Correctness of `G(k+1)-G(k)=p(k)` is re-checked by
the independent stdlib certificate checker, which does not import SymPy.

The step from that identity to the finite sum is the hand-provided telescoping
rule from A1. That rule is infrastructure. It is not this pack's extracted
novelty.

## When not to use

- The summand is not a univariate QQ-polynomial (`1/k`, `sin(k)`, extra symbols).
- You need a hypergeometric identity the polynomial checker cannot verify.
- Bounds are reversed (`upper < lower - 1`). This pack does not use Karr reversal.
- You need a kernel-checked theorem. This pack never marks `formal_kernel_checked`.
- You only need a number and not evidence.
- Do not treat T1 plus two other instances as a proof for unbounded degree,
  non-constant denominators, or symbolic limits.
