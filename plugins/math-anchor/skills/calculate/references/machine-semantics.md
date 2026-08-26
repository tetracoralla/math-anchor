# Machine semantics

Use this reference when the visible task depends on how a machine represents or
executes a value.

- `integer.represent` decodes or renders a fixed-width value.
- `integer.bitwise` owns logical, shift, rotate, bit-field, and alignment work.
- `integer.machine_arithmetic` owns checked, wrapping, and saturating
  execution. Always supply width, signedness, and value-versus-bits input mode.
  Keep the unbounded mathematical result, machine result, overflow, wrap,
  saturation, truncation, and discarded bits distinct.
- `float.ieee754` owns binary32/binary64 fields, signed zero, subnormals,
  infinity and NaN, exact represented values, adjacent values, ULP size and
  distance, and numeric-versus-bit equality. Do not infer these facts through
  ordinary decimal evaluation.
- `decimal.quantize` and `integer.divide` own explicit rounding and
  quotient/remainder sign conventions outside fixed-width arithmetic.

These are not trivial arithmetic tasks even when the displayed numbers are
small. Preserve every returned convention and representation distinction that
changes the meaning.
