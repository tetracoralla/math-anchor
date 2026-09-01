# Public mathematics smoke sources and claim boundary

This four-task suite is a development smoke for one named Agent, harness,
runtime, and attempt. It is not a benchmark score or a claim about mathematical
research ability.

- `putnam-2023-b1.m37-n64` specializes the official 2023 Putnam B1 result to
  `m = 37`, `n = 64`. The Controller oracle is Python's independent
  `math.comb(99, 36)`.
- `putnam-2023-b6.n12` specializes the official 2023 Putnam B6 matrix to
  `n = 12`. The Controller regenerates every entry from the Diophantine count
  and computes the determinant with fraction-free Bareiss elimination.
- `nist-hilbert-12.stability` uses the NIST Matrix Market definition of the
  Hilbert matrix and asks only for the runtime's stability classification,
  numeric rank, and whether a finite forward-error bound is available. It does
  not grade an environment-specific condition-number rendering.
- `buckingham-pi.drag-nullity` asks only for the nullity of the dimensional
  exponent matrix. A basis of Pi groups is deliberately not string-graded
  because equivalent bases are non-unique.

Primary source pages:

- <https://maa.org/maa-putnam-archive/>
- <https://maa.org/wp-content/uploads/2025/02/2023-Putnam-Problems-and-Solutions.pdf>
- <https://math.nist.gov/MatrixMarket/deli/Hilbert/information.html>
- <https://math.mit.edu/~dunkel/Teach/18.354/18.354_course_notes.pdf>

The treatment must contain an observed successful target execution before any
repeat expansion is justified. Discovery-only calls, a correct baseline, or a
correct treatment with zero target calls do not establish adoption or utility.
The separately versioned adoption suite contains only B6 and Buckingham Pi,
the two tasks whose Terra and Luna smoke treatments both executed `math.run`.
It uses three Luna repeats, the minimum accepted for a conditional utility
estimate, and does not reuse B1 or Hilbert merely to enlarge the sample.
