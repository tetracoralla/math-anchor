# Push / PR notes for A0–A2

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

```sh
git checkout chore/ai-for-math-a2-method-pack
git log --oneline -8
```

## Push and open a PR

```sh
git push -u origin chore/ai-for-math-a2-method-pack
gh pr create --base main --head chore/ai-for-math-a2-method-pack \
  --title "A2: experimental polynomial-antidifference method pack" \
  --body "$(cat <<'EOF'
Research proposal (not a public Capability/Procedure): extract a Gosper polynomial-antidifference pack from T1, apply it to held-out sum_{k=1}^{20} k^3, and reject 1/k. Novelty label is known-method-adaptation. Telescoping combination remains A1 infrastructure.

Does not add a fifth MCP tool, Host core changes, UI, or model calls. Does not rewrite A1.

Run:
`.venv/bin/python research/method_packs/run.py apply --task research/method_packs/examples/sum-k-cubed-1-to-20.json`
EOF
)"
```

If `gh` is not logged in, create the PR from GitHub after the push.
