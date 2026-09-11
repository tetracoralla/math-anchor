# Push / PR notes for A0–A4

This checkout has **no GitHub authentication** in this environment, so commits
stay on the local branch. HEAD at start of A0 work:
`1be6afe70b11c7434a51356c805444eafa12ed80` on `main`.

## A0+A1 (already on this branch)

Local commits originally on `chore/ai-for-math-a0a1-telescoping`, included here:

- `66dfb6b` Document A0 research notes for a polynomial finite-sum vertical.
- `ec9504d` Add A0/A1 polynomial finite-sum proposal runner and regressions.
- `60fff28` Record local A0/A1 commit SHAs in PUSH_NOTES.

## A2

Branch: `chore/ai-for-math-a2-method-pack` (cut from the A0+A1 tip).

Local A2 commits:

- `903b828` Add experimental A2 method pack for polynomial antidifferences.
- `a96711d` Document A2 method-pack extraction, reuse, and gaps.
- `6a6d958` Record local A2 commit SHAs in PUSH_NOTES.
- `94f7ab8` Stop stamping cross-task evidence on T1 method-pack replay.

## A3

Branch: `chore/ai-for-math-a3-coverage` (cut from the A2 tip including `94f7ab8`).

Local A3 commits (plus the PUSH_NOTES commit that records them):

- `d2d17fa` Add A3 claim-to-obligation coverage and mutation tests.
- `a0c9e8c` Document A3 coverage, uncovered steps, and A4 next step.
- `8b94e79` Fail closed on phantom baseline obligations and joint G rewrite.
- `e64a32e` Record the A3 nit-fix commit SHA in PUSH_NOTES.

## A4

Branch: `chore/ai-for-math-a4-smoke` (cut from the A3 nit-fix tip `e64a32e`).

Local A4 commits:

- `95974f2` Add A4 equal-budget no-model smoke harness and honesty tests.
- `b865568` Document A4 smoke results, decision, and honesty limits.
- `5217679` Record local A4 commit SHAs in PUSH_NOTES.

L2 F1–F5 (this batch, still Draft; parameterized method content is not done):

- `0684a28` Add PR13 L2 reviewer regressions for original-language and binding failures.
- `465c08e` Fix L2 F1–F5: original polynomial language, task binding, and observed smoke.
- `c8c1bd5` Mark the A4 smoke results table as pre-F1–F5 SHA 5217679 evidence.

The A4 table in `docs/research/ai-for-math/a4-smoke.md` is SHA `5217679` evidence.
Post-fix smoke is a new report (`/tmp/a4-smoke-after-f1f5.json` in the fix notes), not that table.

## Parameterized method pack (batch 2; stacked on #13, do not merge)

Branch: `chore/ai-for-math-parameterized-method` (cut from F1–F5 tip `89490a1`).
Does not reopen F1–F5. Separate draft PR; depends on #13.

Local commits:

- `14fcc32` Add experimental parameterized shifted-square method pack.
- `2d51e4c` Document parameterized method-pack provenance, domain, and reuse.

```sh
.venv/bin/python research/method_packs/run.py extract-shifted-square
.venv/bin/python research/method_packs/run.py apply \
  --pack research/method_packs/shifted_square_antidifference.v0/pack.json \
  --task research/method_packs/examples/shifted-square-held-out-c3-2-to-7.json
.venv/bin/python -m pytest tests/python/test_parameterized_method_pack.py
```

```sh
git checkout chore/ai-for-math-a4-smoke
git log --oneline -12
```

## Push and open a PR

```sh
git push -u origin chore/ai-for-math-a4-smoke
gh pr create --base main --head chore/ai-for-math-a4-smoke \
  --title "A4: equal-budget no-model smoke for polynomial finite sums" \
  --body "$(cat <<'EOF'
Research proposal (not a public Capability/Procedure): equal-budget no-model smoke of B0 (SymPy baseline) / B1 (A1 runner) / B2 (frozen pack apply) on pre-registered T1, held-out cubes, and 1/k. B2-minus ran because B2 showed a reuse signal; cubes value unchanged. Integration signal only — not a benefit percentage. Decision: evidence insufficient; do not promote the pack. call-alone and lifecycleEvidence are not semantic adoption. coversOriginalTaskClaim stays false. No dollar costs. No Host/UI/MCP.

Run:
`.venv/bin/python research/ai_for_math_eval/run.py --output build/a4-smoke-report.json`
EOF
)"
```

If `gh` is not logged in, create the PR from GitHub after the push.
