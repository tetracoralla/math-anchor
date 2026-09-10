# Push / PR notes for A0+A1

This checkout has **no GitHub authentication** in this environment, so commits
were left on the local branch. HEAD at start of work:
`1be6afe70b11c7434a51356c805444eafa12ed80` on `main`.

## Branch

```sh
git checkout chore/ai-for-math-a0a1-telescoping
git log --oneline -5
```

If you need a fresh branch from current `main`:

```sh
git checkout main
git pull
git checkout -b chore/ai-for-math-a0a1-telescoping
git cherry-pick <commit-sha>
```

## Push and open a PR

```sh
git push -u origin chore/ai-for-math-a0a1-telescoping
gh pr create --base main --head chore/ai-for-math-a0a1-telescoping \
  --title "A0/A1: polynomial finite-sum research vertical" \
  --body "$(cat <<'EOF'
Research proposal (not a supported domain module): construct a discrete antidifference with SymPy Gosper/summation, independently check G(k+1)-G(k)=p(k), apply a hand-provided telescoping rule, and emit result + obligation receipt.

Does not add a fifth MCP tool, Host core changes, or model calls.

Run:
`.venv/bin/python research/polynomial_finite_sum_proposal/run.py --task research/polynomial_finite_sum_proposal/examples/sum-k-squared-1-to-10.json`
EOF
)"
```

If `gh` is not logged in, create the PR from GitHub after the push.
