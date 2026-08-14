# Zibetha repository contract

Read `docs/product-model.md` before changing the product surface.

- Keep the human macOS app and the Agent interface on one calculation core.
- Keep Agent discovery, schemas, runtime metadata, and protocol concepts out of the human calculator UI.
- Keep the public MCP surface to `math.search`, `math.describe`, `math.run`, and `math.batch`; add capabilities to the operation registry, not as more public tools.
- Never evaluate input with Python `eval`, `exec`, string `sympify`, or `parse_expr`. Extend the explicit AST translator when new expression syntax is required.
- Preserve exact and approximate results as separate fields. Never label a floating approximation as exact.
- Add a negative regression test for parser, validation, timeout, and error-path fixes.
- Report development regression, MCP/runtime user flow, and human experience acceptance separately.
- Do not commit or push unless the owner explicitly asks.

