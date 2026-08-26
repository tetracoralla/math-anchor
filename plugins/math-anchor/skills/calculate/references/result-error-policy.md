# Result and error policy

## Results

- Preserve `status: uncertain`, warnings, residuals, error bounds, stability,
  exact-versus-approximate provenance, units, conventions, solution branches,
  and omission risk whenever they constrain use.
- A successful response shows that the declared operation ran. It does not
  establish that the user's request was translated correctly.
- Prefer diagnostics returned by the original call. Make another call only for
  a materially different independent invariant needed by a consequential
  result.

## Errors and retries

Follow `retryable`, `phase`, `retryAfterMs`, and `suggestedAction`; do not infer
retry policy from message prose.

- For `E_INPUT`, `E_DOMAIN`, or `E_UNIT`, correct the mathematical input or ask
  for the missing choice. Do not replace the calculation with a mental guess.
- For `E_TIMEOUT`, `E_MEMORY`, or `E_OUTPUT_LIMIT`, reduce or split a genuinely
  oversized request or select one representation. Do not repeat it unchanged.
- For retryable `E_OVERLOADED`, `E_UNAVAILABLE`, or `E_RUNTIME`, wait for
  `retryAfterMs` when supplied and retry at most once. If that fails, report the
  stable error instead of looping or silently switching to mental arithmetic.
