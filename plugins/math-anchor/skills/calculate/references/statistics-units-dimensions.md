# Statistics, units, dimensions, and finance

- Use `units.search` only when a stable unit id or compound spelling is
  unknown. `units.convert` accepts stable ids directly. Use
  `quantity.evaluate` for concrete unit-bearing arithmetic and explicit
  multiplication such as `80 * kg * 9.81 * m / s^2`.
- A month or year is not a fixed physical duration. Keep the default rejection
  for civil-calendar work; use `calendarPolicy: "average_duration"` only when
  the user explicitly asks for that fixed convention, and preserve its warning.
- Use `dimension.check` for consistency, `dimension.infer` for unknown declared
  symbol dimensions, and `dimension.pi_groups` for a Buckingham Pi basis.
  Declare every symbol. Preserve `scope: dimensional_consistency_only`:
  consistency does not prove a physical law or coefficient. Inference returns
  dimensions, not preferred units; do not guess unresolved or inconsistent
  entries. A Pi basis is exact but not a unique named physical quantity.
- Preserve probability distribution support, statistical method, sample size,
  assumptions, degrees of freedom, and approximate provenance. Send decimal
  values as strings when exact decimal interpretation matters.
- For `measurement.propagate`, first put every input in one coherent numerical
  unit system. Preserve covariance/correlation, combined standard versus
  coverage-expanded uncertainty, and nonlinear first-order warnings. Exact
  fields are exact only inside the stated linearized model.
- For finance, pass decimal text and preserve period, timing, IRR bracket, and
  rounding conventions. The result is a calculation, not a transaction quote.
