# Math Anchor repository contract

Read `docs/product-model.md` and `docs/REVIEW_CONTRACT.md` before changing or reviewing the product surface.

A plain owner request to review, audit, 审核, or 复核 automatically invokes the
complete review contract in read-only mode unless fixes are also requested.
Treat it as the minimum scope, not a ceiling, and finish with `tools-dev
workspace escalations` for shared contracts, installation, or resource risks;
do not ask the owner to supply a separate checklist.

- Keep the human macOS app and the Agent interface on one calculation core.
- Keep Agent discovery, schemas, runtime metadata, and protocol concepts out of the human calculator UI.
- Keep the public MCP surface to `math.search`, `math.describe`, `math.run`, and `math.batch`; add capabilities to the operation registry, not as more public tools.
- Never evaluate input with Python `eval`, `exec`, string `sympify`, or `parse_expr`. Extend the explicit AST translator when new expression syntax is required.
- Preserve exact and approximate results as separate fields. Never label a floating approximation as exact.
- Add a negative regression test for parser, validation, timeout, and error-path fixes.
- Treat mathematical semantics, parser/schema alignment, internal bounds, error codes, refactors, tests, packaging, and runtime verification as Agent-owned technical closure. Decide from current source and executable behavior; do not ask the owner to choose among implementation details. Ask only for a plain-language product-direction or external-authorization decision.
- Report development regression, MCP/runtime user flow, and human experience acceptance separately.
- Do not commit or push unless the owner explicitly asks.
