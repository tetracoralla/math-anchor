# Deterministic mathematics result-use policy

When a task asks for a reliability-sensitive dependent calculation and an
appropriate deterministic mathematics tool is available, use it for every
declared stage instead of replacing a stage with mental arithmetic.

- For an exact matrix determinant followed by a modular remainder, calculate
  the determinant first and pass the exact returned value directly into the
  remainder calculation. Preserve both returned exact strings in the final
  object.
- For a polynomial-identity promotion decision, use the available bounded
  certificate operation. Copy its boolean identity result and certificate
  digest into the final object. Set `disposition` to `publish` only when the
  returned identity is true; otherwise set it to `reject`.
- Use one direct operation call per known stage. Do not search, describe,
  repeat, or retry a known successful operation.
- When no deterministic mathematics tool is available, complete the same task
  directly and return the same requested object shape. Do not invent a
  certificate digest; derive a real deterministic digest from the checked
  statement so that the baseline remains gradeable without target access.

This policy defines workflow behavior. It does not name a provider, disclose
an expected answer, or make tool availability itself proof of correctness.
