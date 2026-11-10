---
name: review-change
description: Use when reviewing a branch or pull request in this repository before it is merged.
---

# Review a change

## When this applies
A feature branch is ready and someone (a person or an agent) wants it checked before merging.

## Steps
1. Run `git diff main...HEAD --stat` and read every changed file, not just the summary.
2. Run `python3 run_tests.py`. It must end with `0 failures, 0 errors`. New behaviour needs a new test.
3. Check the honesty rules:
   - status words are exactly *implemented*, *simulated* or *planned*, and match what the code does;
   - the "Read as" line and every message are built from the filters that ran, never from model text;
   - no setting changes silently: an operator, location scope or seniority choice is either stated
     by the user or visible as a chip.
4. Check the boundaries in AGENTS.md: no new dependency, no keys or `.env`, no logs, and no code, data,
   screenshots or branding from a real product.
5. Check the commits: conventional format (`feat(scope): …`, `fix: …`, `docs: …`, `test: …`,
   `chore: …`), each one logical change, and the pull request body says `Closes #<issue>`.

## Check
Report each step as pass or fail, with the file and line for any failure. Approve only if every step passes.

## Do not
Do not fix problems while reviewing. List them, so the author decides what changes.
