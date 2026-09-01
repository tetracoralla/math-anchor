# Deterministic mathematics policy

Use an available deterministic mathematics tool when a task depends on
fixed-width overflow or bits, IEEE-754 representation, a named rounding or
division convention, a large exact integer, a nontrivial matrix result, units
or dimensions, uncertainty, probability, numerical methods, or finance.
This also applies when a nontrivial symbolic identity or generated certificate
must be validated exactly.

For a known supported operation, prefer one direct execution call. Do not call
a mathematics tool for trivial low-risk arithmetic, plain text manipulation,
or unrelated programming questions. If no deterministic mathematics tool is
available, solve the task directly without claiming that a tool was used.
