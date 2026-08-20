# Symbolic dimensional analysis

## Objective and finish line

Math Anchor extends its existing unit ladder from concrete conversion and
quantity arithmetic into symbolic dimensional reasoning:

```text
units.convert -> quantity.evaluate -> dimension.check -> dimension.infer -> dimension.pi_groups
```

This is one product capability, not another package or MCP server. The current
phase is complete when the source and packaged runtime expose symbolic checks,
inference, and dimensionless-group generation through the existing `math.run`
and `math.batch` tools, validate their typed contracts, preserve exact rational
dimension exponents, report inconsistency or basis non-uniqueness without
overstating physical meaning, and pass parser, constraint, schema, discovery,
batch, and transport regressions.

## Users, tasks, and route budget

- A human continues to use the compact calculator and concrete conversion
  flow. No symbolic-dimensional UI is added.
- An Agent uses `dimension.check` to determine whether two symbolic formula
  sides and every additive/function subexpression are dimensionally
  consistent.
- An Agent uses `dimension.infer` to solve the dimensions of declared unknown
  symbols from equations plus known symbol dimensions.
- An Agent uses `dimension.pi_groups` to construct one exact normalized basis
  for the dimensionless products spanned by variables declared with units.
- A known request should take one `math.run` call. Search and describe remain
  optional discovery for an unfamiliar operation, and independent checks or
  inferences may be sent through `math.batch`.

## Shared semantic core

Pint remains the unit database and translates declared unit expressions such
as `newton` or `meter / second^2` into dimensionality. Math Anchor owns a small
canonical `DimensionVector` whose base-dimension exponents are exact
`Fraction` values. JSON uses stable base-dimension names and rational text:

```json
{"mass": "1", "length": "1", "time": "-2"}
```

Direct vector inputs use unbracketed or Pint-style bracketed ASCII dimension
names and bounded integer or canonical rational exponents such as `-2` or
`"1/2"`. Decimal and scientific-notation strings are not a second exponent
language. The input bound protects declarations; exact exponents produced by a
bounded expression or solver use a separate derived-value budget, so a legal
declaration remains computable through the advertised power range.

A separate AST whitelist interprets names as declared symbols, never as unit
names. It supports numeric constants, parentheses, unary signs, `+`, `-`, `*`,
`/`, rational powers, and the bounded functions `sin`, `cos`, `tan`, `log`,
`exp`, `sqrt`, and `abs`. Additive terms must have equal dimensions;
trigonometric, logarithmic, and exponential arguments must be dimensionless.
The parser never evaluates Python source or delegates expression text to
SymPy, Pint, or another general evaluator.

`dimension.infer` turns equality, additive, and dimensionless-function rules
into exact linear constraints over the unknown symbol dimensions. SymPy solves
the bounded rational system, while Math Anchor owns the classification and
result contract:

- `unique`: every requested unknown dimension is determined;
- `underdetermined`: at least one degree of freedom remains;
- `inconsistent`: the supplied constraints contradict one another.

An underdetermined system may still determine some requested symbols uniquely.
Those symbols appear in `inferred`; only symbols whose dimensions still depend
on a free parameter appear in `unresolved`. Math Anchor never discards a valid
partial inference merely because another symbol remains unresolved.

`dimension.pi_groups` forms the exact rational dimensionality matrix and uses
bounded symbolic linear algebra to compute its nullspace. Each basis vector is
normalized to primitive integer exponents with a deterministic sign and
variable-order convention. The returned basis spans the dimensionless space;
another mathematically equivalent basis, product, inverse, or power may be just
as valid. Its narrower unit-expression input keeps the known operation
constructible in one call without duplicating the larger direct-vector schema
inside Agent tool discovery.

## Result boundaries

`dimension.check` returns `status: ok` even when
`dimensionallyConsistent` is false, because finding a contradiction is a
successful check result. It reports resolved left and right vectors plus
localized issues for addition, function arguments, or the top-level equation.
A side with an internal conflict has a `null` resolved vector rather than
borrowing one term's dimension.

`leftExpression` and `rightExpression` preserve the caller's trimmed text.
Each issue's `expression` uses normalized ASCII syntax (`*`, `/`, `**`) so all
machine-readable diagnostics have one stable representation.

Every successful check or inference includes
`scope: dimensional_consistency_only`. Dimensional consistency does not
establish that a physical law, coefficient, semantic quantity kind, or
real-world model is correct. Inference returns a dimension, never an arbitrary
preferred unit.

Pi-group results instead use `scope: dimensionless_basis_only` and explicitly
warn that a basis is not unique. They do not name a Reynolds number or infer a
physical law merely because one exponent combination matches it.

Check and inference symbol declarations accept either a bounded Pint unit
expression or a direct canonical dimension vector. Pint contexts are not
enabled: cross-dimensional relationships such as wavelength-to-frequency are
physical-law calculations, not ordinary unit conversion.

## Validation ladder

1. focused dimension-vector, parser, check, inference, Pi-group, and negative tests;
2. complete Python suite plus source-safety and schema-cost checks;
3. real four-tool MCP transport with direct, discovery, invalid, and ordered
   batch calls;
4. packaged plugin/runtime rebuild and the existing macOS build/runtime checks;
5. report development, Agent runtime, human runtime, and business/experience
   acceptance separately.

## Non-goals for this phase

- implicit or explicit Pint conversion contexts;
- a custom unit registry or physical quantity-kind ontology;
- another public MCP tool, server, package, or repository;
- symbolic-dimensional controls or protocol metadata in the human app.
