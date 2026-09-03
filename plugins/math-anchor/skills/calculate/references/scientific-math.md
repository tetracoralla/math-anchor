# Scientific mathematics

Use the selected operation's live schema as the argument authority. The notes
below identify semantic boundaries that must survive presentation.

- Use `expression.equivalent` rather than comparing rendered strings. Keep
  strict definedness unless the user explicitly wants equality only where both
  expressions are defined.
- `calculus.multivariate` covers gradients, Jacobians, Hessians, unnormalized
  directional derivatives, divergence, curl, and Laplacians. Preserve variable
  order. Directional derivative, divergence, and Laplacian are scalar results;
  gradient, Jacobian, Hessian, and curl are matrix results. Curl is 3D.
- `numeric.root` with `findAll` finds sign-changing roots in the bracket; it can
  miss even-multiplicity or closer-than-resolution roots. Preserve that limit.
- `numeric.integrate` can return an estimate-based `resultInterval`; when
  `errorBoundCertified` is false it is not a rigorous enclosure. `status:
  uncertain` means only the local estimate was met. Supply breakpoints only
  when they cover material discontinuities or localized features.
- `numeric.minimize` returns internal mpmath interval enclosures over its
  supported expression subset. Treat `uncertain` as the best reported bound,
  not a finished answer, external certificate, or proof-kernel result, and
  avoid undefined points in the bracket.
- For exact matrix solving, rank, RREF, bases, eigenspaces, LU, and Cholesky,
  use integers or rational text. Do not turn approximate decimals into exact
  structural claims.
- Use `matrix.solve_approximate` or `linear_algebra.numeric` for decimal
  binary64 work with an explicit tolerance. Preserve condition, rank,
  residual, backward-error, reconstruction, orthogonality, stability, and
  uniqueness/minimum-norm diagnostics.
- Use `linear_algebra.exact` for exact matrix multiplication/transpose and
  provably real vector algebra. Do not guess complex inner-product semantics.
- `solution.verify` checks supplied candidates. Call them exhaustive only when
  `omissionRisk` is `none_proven`.
- `certificate.polynomial_identity` is for bounded polynomials over rational
  coefficients. Write exact fractions as integer division, preserve the
  returned certificate, and do not describe `checkedBy: null` as formal proof
  or completed independent verification.
- `geometry.almost_complex.local_check` takes an ordered even-dimensional
  coordinate list and the square matrix `structure[k][i] = J^k_i` as rational
  polynomial strings. It checks `J^2 = -I` and coordinate-basis Nijenhuis
  components exactly, but leaves chart coverage, overlaps, global extension,
  and global existence explicitly unchecked. Call the known shape directly;
  do not search or describe first.
