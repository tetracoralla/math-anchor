# Push / PR notes for A0–A3

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

```sh
git checkout chore/ai-for-math-a3-coverage
git log --oneline -10
```

## Push and open a PR

```sh
git push -u origin chore/ai-for-math-a3-coverage
gh pr create --base main --head chore/ai-for-math-a3-coverage \
  --title "A3: claim-to-obligation coverage for polynomial finite sums" \
  --body "$(cat <<'EOF'
Research proposal (not a public Capability/Procedure): record claim→obligation coverage for the polynomial finite-sum / method-pack workflow, bind G(upper+1)-G(lower) as an exact rational, and add mutation tests (wrong G, foreign certificate, stale pack version, rewritten result, unsupported-as-counterexample). Obligation success is not claim coverage. Telescoping remains A1 infrastructure. formal_kernel_checked stays false.

Does not add a fifth MCP tool, Host core changes, UI, Skill Refinery rewrite, or a general obligation dataflow language.

Run:
`.venv/bin/python research/method_packs/run.py apply --task research/method_packs/examples/sum-k-cubed-1-to-20.json --coverage-output build/method-pack-sum-k-cubed-coverage.json`
EOF
)"
```

If `gh` is not logged in, create the PR from GitHub after the push.
