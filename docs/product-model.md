# Zibetha product model

## Users and tasks

The human surface is a compact, enjoyable macOS calculator for people who need ordinary arithmetic, scientific functions, common physical-unit conversions, and reference currency conversion without learning a new workspace. Familiar keypad and keyboard entry remain the default experience. The calculator face stays focused on the entered value and result; history, errors, rate status, and optional details or copy choices appear only when requested or relevant.

The Agent surface is a deterministic mathematical runtime for assistants that have translated a user request into a mathematical operation. An ordinary supported request should complete in one typed `math.run` call. Discovery is reserved for genuinely unfamiliar operations, and every execution receives mechanically validated arguments plus typed results that distinguish exact values from approximations.

## Related surfaces and flows

1. **Basic human calculation:** enter with the keypad or keyboard, evaluate, continue from the result, copy, clear, and undo the last entry.
2. **Scientific human calculation:** use trigonometric, logarithmic, root, power, constants, and parentheses in the same expression flow.
3. **Physical-unit conversion:** choose compatible source and target units, enter a number with the same keypad or hardware keyboard, receive a live offline conversion, swap direction, or copy the result.
4. **Reference currency conversion:** choose from the current ECB reference-rate catalog, receive a live conversion with compact source, publication time, and current/expired/unavailable state, inspect full timing details, or explicitly refresh.
5. **Local history:** review prior expressions and results, restore one into the display, or clear history. Conversion stays out of arithmetic history because it is a separate live-value flow.
6. **Agent direct execution:** call `math.run` once for an ordinary supported operation; the tool schema carries the operation-specific contract.
7. **Agent discovery and batch:** use `math.search` and `math.describe` only for unfamiliar operations, or `math.batch` for independent work; receive structured success or a stable structured error.
8. **Installation:** the repository contains a local Codex Plugin whose thin Skill explains when to use the four tools. Mathematical truth remains in the runtime.

## Shared inventory

This repository started empty. There were no components, types, tokens, or domain fields to reuse. The implementation therefore establishes these shared elements once:

- a safe expression AST translated directly into SymPy objects;
- one operation registry containing descriptions, JSON-shaped input contracts, and handlers;
- one structured result vocabulary covering scalars, transformations, verification judgments and residuals, integer structures, matrices and bases, exact and approximate linear systems, bracketed roots, numerical integrals with honest error estimates, series, derivative matrices, financial results, probability, statistics, and quantities;
- one isolated execution boundary with time and memory limits;
- SwiftUI calculation and conversion models that share one warm local runtime for expression evaluation, the existing `units.convert` operation, and an app-internal currency operation;
- one curated human conversion catalog that maps readable physical units to the core's Pint identifiers and currency names to ECB codes without reimplementing factors or rates in Swift;
- one bounded ECB reference-rate provider and local cache carrying source, rate date, publication, check, expiry, cache, and refresh-failure metadata;
- one adaptive mineral-blue and teal visual system shared by the calculator face, display, keys, history drawer, and packaged app icon;
- a four-tool MCP facade and a product-local calculation Skill.

The earlier time-zone utility supplied the reusable product pattern—shared deterministic core, human surface, MCP facade, plugin, and thin Skill—not calculator fields or UI components.

## Human surface

- Use a single `WindowGroup`; state is window-scoped except local history, which is persisted in `UserDefaults`.
- Use system window chrome, typography, menus, keyboard shortcuts, and accessibility labels. Follow the surrounding Light or Dark appearance through one adaptive mineral-blue, neutral, and teal palette rather than forcing a fixed black calculator face.
- Start in Basic mode. Scientific mode expands the same calculator rather than opening a separate expert product.
- Offer Convert as a third sibling mode at the compact Basic width. Physical quantities remain offline; currency is a category in the same lightweight flow rather than a new page or calculator mode.
- Treat the calculator as a compact fixed-size macOS utility, not a resizable form: Basic uses a narrow four-column face and Scientific expands into one aligned ten-column face.
- Treat entry as a calculator state machine, not a text editor. Keypad and supported hardware-keyboard input append to the current sequence; the display is read-only and offers no cursor insertion, arbitrary selection, or paste-based free-form editing.
- Keep conversion numeric entry under the same rule. Unit names are selected from a searchable popover, but the conversion value itself remains keypad-driven and read-only on the display.
- Present conversion in one compact result panel with the source row above the target row, separated by a quiet downward cue. Give each number nearly the full panel width so long values do not depend on a fragile half-width column. Use compatible target filtering and one explicit swap action; the vertical relationship is shared with familiar calculators, while this product keeps its own panel, unit controls, keypad, palette, and spacing.
- When converting currency, keep an always-visible compact ECB source, publication time, and `CURRENT`, `EXPIRED`, `UPDATING`, or `UNAVAILABLE` state in the result panel. Put full publication/check/expiry details, source link, information-only qualification, and manual refresh in one secondary popover.
- Treat currency output as calculated reference information, never as a transaction quote. A cache remains current only until the earlier of 24 hours or the next expected ECB business-day release. If the feed is still old or refresh fails, retain the visibly expired cache and wait at least 15 minutes before another automatic attempt; concurrent requests share one refresh. Without usable cached rates, show an unavailable state instead of inventing a rate.
- Update physical conversions locally after numeric or unit changes. Preserve the full runtime result for copy and exact-value access while using a restrained significant-digit presentation on the narrow face.
- Keep the display quiet and right-aligned with generous vertical space. While entering an expression, show it once at the primary size; only after a successful evaluation show the submitted expression as a quiet secondary line above the result. A distinct exact form remains available through the result's secondary copy menu and keyboard shortcut, not as a persistent display row.
- Keep history and mode controls together in a stable trailing header group. Leave the rest of the header visually quiet: do not display a logo or the application name in the human calculator surface.
- Use one consistent continuous-rounded-rectangle key geometry in both modes. Digits stay neutral, edit and scientific keys use progressively quieter mineral surfaces, arithmetic operators use teal ink and a restrained tinted surface, and only equals receives a solid teal commitment treatment.
- Keep the inset result panel, adaptive palette, key geometry, spacing rhythm, and diamond-equals app icon as one coherent product visual identity. Preserve familiar calculator input semantics, but do not reintroduce another calculator's circular gray keypad, saturated orange operator column, fixed-black face, or matching proportions as the default composition.
- Keep the entered expression separate from the expression sent to the core. The display and history preserve familiar notation such as `200+10%`; hidden expansions exist only for deterministic execution and continuation.
- Apply sign and percent to the current operand. For addition and subtraction, percent means the entered percentage of the accumulated left expression, matching familiar Mac calculator behavior.
- Apply adjacent fixed-power keys consistently: `x²` and `x³` both raise the whole current expression.
- Show only the entered expression, primary result, keypad, relevant error, optional history, and ordinary calculator actions. Mathematical method or warning information may appear only when it changes interpretation. Do not add persistent copy feedback, exact-value badges, MCP tools, engine names, schemas, raw precision metadata, or Agent instructions.

## Agent contract

- `math.search`: compact multilingual catalog discovery by natural-language query and optional category, used only when the operation is not already clear.
- `math.describe`: exact input contract and examples for one operation.
- `math.run`: one isolated operation through an operation-specific advertised schema and the same mechanically enforced runtime schema.
- `math.batch`: up to 32 independent isolated operations with bounded concurrency, preserving input order.

`math.run` keeps the operation-specific input catalog for one-call routing. `math.batch` intentionally advertises one compact generic item shape rather than repeating all twenty-nine operation schemas; items are still validated against the same registry during execution. Both tools apply explicit result selection and strict output byte budgets, with automatic omission of redundant approximate matrix data when exact entries already satisfy the request.

The catalog covers expression evaluation, simplification, and semantic equivalence; explicit algebraic transforms; symbolic equation solving and candidate verification; single- and multivariable calculus; bracketed numerical roots with error bounds; adaptive numerical integration whose interval is non-certified and whose overall status remains `uncertain` unless the caller supplies a complete feature-point or minimum-feature-scale assumption; integer number theory and combinatorics; exact matrix structure plus tolerance-aware approximate linear solving; financial calculations; common probability distributions; descriptive and inferential statistics; unit conversion; and unit-bearing expressions. Its twenty-nine current operations remain inside the generated `math.run` schema so ordinary supported work can complete in one call. Further growth still requires a fresh measurement of schema size, cold-session selection, retries, and generic fallbacks before changing the four-tool boundary.

## Safety and correctness boundaries

- Input expressions are parsed with Python's AST and translated node by node through a whitelist. Attribute access, indexing, lambdas, comprehensions, imports, assignments, and unregistered calls are rejected.
- Undefined expression values such as division by zero return `E_DOMAIN`; they are never successful values and never enter human history.
- Agent operation execution leases one exclusively held child process from a bounded warm pool with a wall-clock timeout and resident-memory limit. A timeout, memory breach, worker failure, or incompatible lower memory request destroys that worker before another operation can use it. The human app likewise keeps one local Python worker warm and sends only bounded expression-evaluation or curated physical-unit-conversion requests, avoiding a new scientific-runtime startup for every interaction. Neither route executes raw model-generated code.
- Physical conversion uses the same Pint-backed `units.convert` handler as the Agent surface. Swift owns only curated display metadata and input state; it stores no independent conversion factors.
- Currency conversion uses the ECB daily euro reference-rate feed through one fixed HTTPS endpoint. Responses and cache files are size-bounded and validated; network work is time-bounded; cache writes are atomic and private; provider errors are reduced to stable human-safe states.
- Each successful currency result carries the ECB source URL, rate date, publication time when supplied, local check and expiry times, cache state, and refresh outcome. Cross-rates are calculated with `Decimal`; floating approximations are never presented as exact values.
- `currency.convert` is an internal app-runtime request, not an Agent operation or a fifth public MCP tool. The four-tool Agent boundary remains unchanged.
- Agent `timeoutMs` is one cumulative deadline across worker-queue wait, cold worker readiness, and operation execution. Pool saturation therefore returns `E_TIMEOUT` instead of waiting behind earlier work without a bound. Agent pool workers and the human warm worker are terminated and rebuilt after cancellation, timeout, memory breach, or protocol failure so one expensive or damaged execution cannot block subsequent work.
- Symbolic algorithms come from SymPy, numerical roots from mpmath, large approximate statistics from NumPy, arbitrary precision from mpmath/SymPy, and units from Pint. Statistics and quantities must state exact/approximate provenance and any method choice that can change interpretation. This project owns the interface and safety boundary, not replacement mathematics.
- Structural matrix operations (`matrix.solve` and `matrix.reduce`) accept only exact integers or rational-expression text. Approximate floating matrices require a separately specified tolerance policy and are rejected rather than assigned a potentially unstable rank or solution classification.
- `matrix.solve_approximate` is the separate decimal-text-to-binary64 lane for square systems that have an explicit tolerance policy. It returns condition, residual, backward-error, and forward-error-bound diagnostics instead of exact structural claims.
- Equivalence verification defaults to strict definedness equality; simplification to the same value does not erase a removable discontinuity. Multivariable definedness that cannot be proven remains `unknown` rather than being guessed.
- Solution verification checks only supplied candidates unless a finite univariate solution set can be proven and explicitly compared. It always reports omission risk.
- Financial results state rate and cash-flow timing conventions and apply an explicit decimal rounding mode. Bracketed IRR returns one selected root and never implies that another root is absent.
- Probability and inferential statistics accept decimal text, expose their numerical method, and keep distribution support, sample assumptions, degrees of freedom, and approximate provenance visible to the Agent result without surfacing them in the human calculator UI.
- Development checks can veto a broken implementation. They do not establish whether the human interface feels good; that remains a separate current-canvas judgment.
- Release packaging builds the same standalone calculation runtime for the current architecture and embeds it inside both the Codex Plugin and macOS app bundle. Generated runtimes stay out of Git; their build manifest records architecture, Python tag, locked dependency digest, and complete file hashes, while generated third-party notices and an SPDX SBOM travel with the artifact. Installed products do not locate a development checkout or repository-local virtual environment at runtime.
