# Human note (not a formal proof)

This file explains the experimental shifted-square pack. It is not an
obligation, not a Lean kernel result, and not a claim that one parametric
family is a product Capability.

## Mandatory claim

这个方法包相对不带包的 B1 流程，额外保存了什么数学信息；未来哪一步工作可以因此不再重复？

相对不带包的 B1，这个包额外保存了参数化反差分
`G(k,c)=k(k-1)(2k-1)/6 + c k(k-1) + c^2 k`，以及可检查的二元恒等式
`G(k+1,c)-G(k,c)=(k+c)^2`。对未见过的有理数 `c` 与整数边界，apply
代入该 `G`、检查适用条件、再查实例恒等式并做望远镜组合，不必再对每个
`(c,a,b)` 运行 Gosper 或待定系数构造。身份检查仍会做；省下的是构造，
不是证明义务。

If the honest answer were only “labels/call rules but the same solver every
time”, this pack would not be finished.

## Provenance

Known-method adaptation. Undetermined coefficients for the monomials `1`,
`k`, and `k^2`, then linearity for `(k+c)^2`. Faulhaber and Gosper already
know the `c=0` case. The formula is derived in
`research/method_packs/shifted_square.py` and checked by the independent
stdlib polynomial certificate checker. It is not pasted as
“agent-extracted” from an external source, and it is not claimed as new
mathematics.

Telescoping `G(b+1)-G(a)` remains A1 infrastructure.

## What is general vs instance

- **General:** `G(k+1,c)-G(k,c)=(k+c)^2` as a bivariate polynomial identity
  in `(k,c)`, checked from the pack payload on every apply.
- **Instance:** after substituting this task’s rational `c`, the univariate
  identity is re-checked. That is a separate program step, not a second
  general proof.
- A checked instance is not a kernel theorem and not a proof for `k^3`,
  `(k+c)^3`, or non-rational `c`.

## When not to use

- The summand is not `(k+c)^2` with leading coefficient 1.
- You need Gosper for a different polynomial family (use B1 or the A2
  Gosper pack, which *does* reconstruct).
- Bounds are reversed (`upper < lower - 1`).
- You need `formal_kernel_checked`. This pack never marks that.
- Reconstruction is disabled here on purpose. Stripping `G` from the pack
  makes this path fail even if Gosper is available elsewhere.
