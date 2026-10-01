PRIORITY: P1
SIZE: S
DEPENDS:

# TASK-938 — A gate must catch PII in a fixture, because attention already failed twice in one day

Opened as a ramp task by operator decision, 2026-10-01.

## Why

Fixtures written while reading the live corpus carry real identities into the repo. This
happened twice independently on 2026-10-01, in two different lanes, within hours:

- The reply-classification lane put a real company name in a COMMIT MESSAGE. It was caught by
  a human reading the branch, then repaired by squashing to a single commit (36445185) with a
  clean message. Interactive rebase does not work in this environment, so squash was the
  route. Two things were verified afterwards: the diff between the old and new trees was empty
  (nothing was lost) and the name occurs 0 times in the new history.
- The step-objectives lane added fixtures naming a real prospect; the agent caught it itself
  and removed it in 0afb9642 before anything left the machine.

Both were caught by somebody looking. That is not a control. The agent writing a fixture has
just been reading the real corpus, so the real name is the nearest value to hand — this will
recur.

## Task

A gate that refuses a commit introducing a real identity into test fixtures or into a commit
message.

## Acceptance

1. The gate runs BEFORE the commit, not after. This ordering is the whole point: a redaction
   filter that runs after the first command has already leaked once in this repo — one IPv4
   got through because it was checked afterwards.
2. It scans fixture content AND the commit message. The reply-classification leak was in the
   message only; a tree-only scan would have passed it.
3. It self-tests against every value it claims to protect. A filter that has not been run
   against the actual corpus values is a filter that agrees with you.
4. A positive control is mandatory and must be part of the test: plant a known synthetic
   "real-looking" identity and prove the gate fires. A gate that has never fired is not known
   to work.
5. Beware the search tool itself: the repo's Grep tool respects `.gitignore`, so a "no PII in
   the repo" search over the gitignored `work/` tree can never hit. The gate must not be built
   on a search that silently excludes the directories where the corpus actually lives, and the
   test must prove the gate sees into them.
6. False positives are expected and must be cheap to override with a named, reviewed
   exception — otherwise it will be disabled the first time it blocks a legitimate commit.

## Scope note

This is a pre-commit control, not a history rewrite. Any already-landed identity is a separate
decision for the operator, because rewriting shared history has its own cost.
