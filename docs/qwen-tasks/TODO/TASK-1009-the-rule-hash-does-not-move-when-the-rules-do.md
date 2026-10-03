# TASK-1009 — `RULE_HASH` does not move when the production rules do

**WRITE `REPORT.md` NOW, EMPTY, IN YOUR WORKTREE ROOT, BEFORE YOU READ
ANYTHING ELSE. Then append to it as you go.** One line per step you finish and
one line for anything you could not do and why. A report written at the end is
a report that does not exist when the session dies.

## The defect, measured

Found 2026-10-03 by the lane implementing the operator's reply rulings.

**`replies.OBJECTION_PATTERNS` is bound TWICE** — once around line 733, the
production tuple, and again around line 926, the taxonomy one. Python keeps
the last binding. So:

- `RULES` captured the **first** binding, at import time.
- `_rule_material()` walks `globals()` and therefore sees only the **second**.

**A pattern group added to the production tuple changes verdicts and does not
move `RULE_HASH`.**

That is an integrity mechanism failing silently, which is worse than not
having one: `RULE_HASH` exists so that a classification can be tied to the
rules that produced it, and a hash that does not move says "nothing changed"
with the full authority of a measurement.

## Why this is not a cosmetic fix

This repository already records three artefacts of the same 899 replies that
disagree with each other, and the rule that follows from it: **a count from a
classification has to carry that run's identity.** `RULE_HASH` IS that
identity. If it is stable across a real rule change, every count that cites it
is citing a lie, and the disagreement between artefacts becomes unexplainable
rather than merely unexplained.

## The deliverable

1. **Reproduce it first, as a failing test.** Add a group to the PRODUCTION
   `OBJECTION_PATTERNS` tuple, show that `replies.classify` changes a verdict,
   and show that `RULE_HASH` does NOT change. That test is the deliverable even
   if the fix turns out to be one line.
2. **Fix the smallest root cause.** The duplicate binding is the defect. Do
   NOT "fix" it by making `_rule_material` look harder — that treats the
   symptom and leaves two tuples with one name. Decide which binding is the
   real one, give the other its own name, and make every reader point at the
   one it means.
3. **Prove the fix by effect**, with `__pycache__` wiped: the same planted
   group now moves `RULE_HASH`, and removing it moves it back.
4. **Sweep for the same shape.** Any other module-level name bound twice in
   `src/` is the same defect waiting. `python -c "import ast, ..."` over the
   AST, counting top-level assignments per name, finds them. Report the list
   even if you fix none of them.

## Constraints

- **A FULL SUITE MAY BE RUNNING.** Do not run `python -m tests.offline`,
  `unittest discover` or `scripts/run_suite.py`. Individual modules only.
- **Two modules are ALREADY RED on master, standalone, and are not yours:**
  `test_replies.TestTheClassifier.test_every_verdict_carries_its_evidence` and
  `test_taxonomy_safety.GenuineInterestStillClassifies.test_genuine_curiosity_reaches_interested`.
  Compare by NAME, never by count.
- Your own worktree, never the main checkout, never master. The worktree name
  must not contain `aiark`, `apify`, `blitz`, `bison`, `contactout`, `glm`,
  `heyreach`, `slack` or `xai` — that list is substring-matched against the
  ABSOLUTE PATH by `test_invariants`' send guard, and such a name exempts every
  file in the repository.
- **No `git stash`** — the stack is shared across ~40 worktrees. WIP commit.
- `git push` is refused by the Claude Code classifier. Commit locally and
  report the branch and SHA.
- No provider call, no provider write, no Slack post.
- **Never weaken a check to make a test pass**, and never widen a pattern list.

## Acceptance

    py -3 -m unittest tests.test_the_rule_hash_moves_when_the_rules_do -v

Must pass with the fix, and the reproduction test inside it must fail against
the unfixed source with `__pycache__` wiped — recorded in `REPORT.md` with the
exact failure text, not asserted.
