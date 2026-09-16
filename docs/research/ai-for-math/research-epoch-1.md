# Research Epoch 1 archive (A0 → trust-failclosed)

This note archives **Research Epoch 1** on `main` tip `fdc5031` (merge of
PR #16). It is a research reframe, not a product Capability, not a promotion,
and not a claim that Math Anchor succeeded as an AI-for-math method library.

Green harness tests are not completion. No savings percentage is invented here.
Millisecond tables in earlier notes stay bound to the SHAs those notes already
quote; this archive does not re-measure them.

## Bet that was tested

Epoch 1 asked whether a **saved method pack** (retrieve / instantiate a
polynomial antidifference, check an identity, telescope) is a differentiated
research product versus strong CAS baselines, and whether **independent
checks that fail closed** are doing work a naive cached template does not.

The owner-adopted successor bet (2026-09-15) is a **Mathematical Evidence
Runtime** / proof-carrying Agent work:

Claim → Certificate/Witness → Independent Verifier → Binding → Assurance → Receipt.

That is progressive assurance, not “problem → Math Anchor computes → answer”.
It is not a competition with AI theorem provers. The macOS calculator remains
a compact human utility over the same calculation core; it is not the center
of this research line. That is a priority, not a standing ban on the human
surface.

## Verdict (honest)

| Hypothesis | Result on this family | Where |
| --- | --- | --- |
| **Method reuse** as the primary R&D bet (saved `G` plus pack apply beats strong CAS baselines with net utility) | **Rejected** | PR #15 / [reuse-benefit.md](reuse-benefit.md) |
| **Independent verification / fail-closed** (wrong saved content, swapped payload, declared-domain skip, claim binding) | **Survives as a hypothesis** — differentiation was observed; that is not product success | PR #16 / [trust-failclosed.md](trust-failclosed.md) |

Promotion stayed `evidence_insufficient` on every smoke in this epoch.
`publicPromotion` stayed false. **Do not promote method packs. Do not start
H1 method-pack accumulation** from these results. The freeze below is
**dated 2026-09-15** and pending new workload evidence; it is not
“永远不做 / never accumulate methods”.

## What ran (A0 → #16)

These documents and harnesses are the epoch, not a fifth MCP tool and not a
supported domain module.

| Stage | What it is | Decision already on record | SHA / PR to quote |
| --- | --- | --- | --- |
| A0 | Capability snapshot; labels source / tests / run / used / benefit kept separate | Checking is implemented; no Agent trajectory corpus; SymPy already returns the finite-sum number | [current-state.md](current-state.md) review SHA `1be6afe70b11c7434a51356c805444eafa12ed80` |
| A1 | Polynomial finite-sum proposal runner (construct `G`, independent identity, fail-closed bounds) | Proposal, not a public operation | `research/polynomial_finite_sum_proposal/` |
| A2 | Experimental method pack from T1; held-out `sum k^3` | known-method-adaptation; not a Capability | [a2-method-pack.md](a2-method-pack.md) |
| A3 | Claim→obligation coverage; typed binding fail-closed | Obligation success is not claim coverage | [a3-coverage.md](a3-coverage.md) |
| A4 | Equal-budget no-model B0/B1/B2 smoke | **evidence insufficient — do not promote.** B0 already matches `385` / `44100` | [a4-smoke.md](a4-smoke.md) table SHA `5217679`; PR #13 merged as `a14e432` |
| Parameterized pack | Saved `G(k,c)` for `(k+c)^2`; reconstruction disabled on the pack path | Not a public Capability | PR #14 merged as `3d01d02` |
| Parameterized cost | B0 / B1 / P-pack timing | B0 already matches in-family numbers; not a benefit percentage | [parameterized-cost-smoke.md](parameterized-cost-smoke.md) |
| **#15 reuse-benefit** | B0 / B1 / B_template / B_codegen / P-pack | Utility **`no_net_benefit_vs_strong_baselines`**. Promotion **`evidence_insufficient`** | PR #15 merged `fde6a6b`. Harness `27fb191` / docs `d7f664c`. See below. |
| **#16 trust/fail-closed** | Fair template vs P-pack on corrupted `G` and domain probes | Experiment **`differentiation_observed`**. Promotion **`evidence_insufficient`**. Latency is not the primary claim | PR #16 merged `fdc5031`. Harness `13ebce1`; scoring vocabulary `71a442a`. See below. |

## PR #15 — method reuse rejected on this family

Quote [reuse-benefit.md](reuse-benefit.md), not a new run.

Mandatory claim already recorded there: relative to B0 (SymPy `summation` each
time) and B_template / B_codegen (the same cached parametric antidifference as
a template or an exact QQ evaluator), the pack still stores `G(k,c)` and
checkable identities, so it need not **construct** `G` for each `(c,a,b)`.
B_template already skips construction and matches the same rationals; the pack
path still does applicability and identity checks and was not faster on that
machine. **Relative to those strong baselines, that smoke did not observe net
utility.** Faster than cold Gosper (B1) is not Math Anchor differentiation.

Three judgments stayed separate (not one `success` flag):

| Judgment | Verdict in that smoke |
| --- | --- |
| Trustworthiness | `holds_in_declared_domain` |
| Behavior | `pack_uses_saved_content` (not unique: B_template / B_codegen also use saved `G`) |
| Utility | `no_net_benefit_vs_strong_baselines` |

In-family exacts already on record (harness `27fb191` / docs `d7f664c`; quote
`environment.gitHead` from a report, do not treat `main` as that harness
commit): P0 `55`, P1 `355`, P2 `83/4`, P3 `28`, P4 `0`. `1/k` and reversed
bounds were never counted as solved. B0 / B_template / B_codegen emitted Karr
`-50` on reversed bounds; B1 and P-pack refused `E_DOMAIN`.

**Do not invent a savings percentage from those milliseconds.**

## PR #16 — fail-closed hypothesis survives (not product success)

Quote [trust-failclosed.md](trust-failclosed.md), not a new run.

Question already recorded there: when does pack + checks fail closed (wrong
saved `G` / out-of-domain / identity or obligation binding) while a **fair**
SymPy-side cached template silently accepts or returns a wrong answer?

That smoke did **not** re-ask the #15 latency question.

Trustworthiness stayed per-cell `holds` / `fail-closed` / `silent-wrong` /
`silent-accept-out-of-declared-domain` (vocabulary nits `71a442a`; cell values
and the promotion decision unchanged from harness `13ebce1`).

Documented contrast (do not restate as a new measurement):

| Probe | P-pack | Fair B_template |
| --- | --- | --- |
| control-P1 canonical `G`, `(k+3)^2` on `2..7` | holds `355` | holds `355` (template not crippled) |
| wrong saved `G = k` | fail-closed, no value | arithmetic silent-wrong `6` |
| swapped cubes antidifference | fail-closed, no value | arithmetic silent-wrong `783` |
| reversed bounds | fail-closed `E_DOMAIN` | policy silent-accept Karr `-50` (`wrongAcceptance` false) |
| over-limit `|a|,|b|>10^6` | fail-closed `E_LIMIT` | policy silent-accept mathematical `2000018000041` (`wrongAcceptance` false) |
| out-of-family `k^3` / `1/k` | fail-closed | fail-closed (family matching is **not** pack-unique) |
| `parameterC` / summand mismatch | fail-closed | fail-closed (not pack-unique) |

Identity/obligation binding: `verify_typed_binding` fail-closed a swapped
`identity.right` on a pack result. The fair template never recorded an
identity, so it could not detect that mismatch.

Experiment verdict: **`differentiation_observed`**. Promotion:
**`evidence_insufficient`**. One family, no model, no tokens, no prices, not
product readiness.

## Independence (producer vs checker)

Where Epoch 1 claimed an independent check, the independent piece is the
**stdlib polynomial certificate checker**
(`math-anchor-stdlib-polynomial-checker`), which recomputes coefficients
without importing the SymPy producer. Applicability, declared-domain
fail-closed, and typed binding are pack/harness policy on top of that checker
and the existing obligation runtime.

That is **not** a second mathematical stack, and it is **not** independence
for every obligation kind. Expression equivalence and dimension checks reuse
the same registered providers as the MCP catalog. A receipt still does not
prove surrounding prose, coverage completeness, or caller assumptions.

## Method packs after Epoch 1

The in-tree packs remain **research samples** and a **dated freeze of H1
accumulation** (2026-09-15) pending a workload that strong CAS cache/template
paths cannot already do:

- `research/method_packs/polynomial_antidifference_gosper.v0/`
- `research/method_packs/shifted_square_antidifference.v0/`

They are not public Capabilities or Procedures. They are not deleted. They
are not a standing “forever no” on method accumulation. A later epoch may
re-open H1 only with new workload evidence; Epoch 2 does not start H1.

## What Epoch 1 did not show

- No live Coding Agent four-arm comparison (no-provider / MCP / explicit
  obligation / shadow checkpoint).
- No token, context-growth, or repair-loop evidence against a matched model.
- No dollar costs (none invented).
- No Lean `formal_kernel_checked` finite-sum conclusion.
- No Host/UI/MCP product change as a Capability promotion.
- `coversOriginalTaskClaim` stayed false. Call-alone is not adoption.
- `lifecycleEvidence=cross-task-use-evidence` is not semantic adoption.

## Next: Epoch 2 (P0)

**Shadow Verifier** — matched arms B0 (model-only), B1 (model + current MCP,
voluntary), B2 (explicit `math-anchor.obligation-set.v0.1`), B3 (Host/harness
shadow checkpoint: quiet success / `failures_only`). Gates G1–G6 are
**targets**. Epoch 2 is not done until live four-arm model evidence exists.

Scaffold: `research/shadow_verifier_eval/`.
Note: [shadow-verifier.md](shadow-verifier.md).
