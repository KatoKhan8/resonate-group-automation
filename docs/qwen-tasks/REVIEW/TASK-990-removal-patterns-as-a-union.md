# TASK-990 — the removal patterns, as a union of master and the stranded branch

STAGE: AWAITING_REVIEW
BRANCH: task-removal-union-2026-10-12
PRIORITY: P0

## Why this exists

`task-reply-classification-clean` (`36445185`) held a real fix and could not be
merged. Measured 2026-10-12 against all 559 real inbound EmailBison replies:

- it FIXES 13 replies master classifies wrongly, including
  `"Please stop"`, `"Sorry, but we are not interested. Please remove us (<company>)
  from your contact list"` and `"not interested please delete my data and dont
  email me again"`;
- it BREAKS 7 replies master gets right — **every bare one-word form**:
  `remove`, `Remove`, `REMOVE`, `unsub`, `Unsub`;
- its merge-base is `0724e820` (2026-10-01 14:06). Master has moved 80 commits
  since; the branch has 1. **It predates the task-939 merge `e9ae9e6b`**, which is
  precisely why the bare forms regress: the two carry DIFFERENT bare-pattern sets.
  The branch has `^stop please$` and `^no contact$` and lacks `^remove$` and
  `^unsub$`.
- it also deletes 7,385 lines including four whole test files.

A naive merge would therefore reintroduce the bug task-939 fixed and delete
current work. This repository has been here before: TASK-229's merge would have
deleted 12,487 lines.

Separately measured: **11 real replies carry unmistakable removal language and
still classify `unknown` on master**, because the bare patterns only match when
the line is exactly the phrase — `"Remove from your list."`, `"Remove my email
now"`, `"Please remove from all mailing lists."`, `"remove from list"`,
`"You can remove us from this list!"`, and `"No thx, plse remove…"` among them.

## The deliverable

Master's `src/replies.py` as the base, with the branch's source changes applied
on top. Not a merge. Specifically:

1. The bare-pattern set is a strict UNION — all 7 of master's plus the 4 the
   branch genuinely adds. Nothing lost in either direction.
2. The 11-reply gap is closed: a removal phrase with words around it is
   recognised, not only a line that is exactly the phrase.
3. A removal signal is DECIDED FIRST rather than ranked. The branch's own commit
   records a case where `"remove us … Not something we are interested in"` came
   out POSITIVE 0.75 because `interested` matched a positive pattern.
4. No test file deleted. Nothing master gained in those 80 commits reverted.
5. `RULE_HASH` must move, since it is derived from every `*_PATTERNS` tuple.

## Acceptance

- Classify all 559 real replies before and after. Report moved-in and moved-out
  counts. **Moved-out must be 0 for the bare one-word forms.**
- Precision must not move in the expensive direction: a genuine positive reply
  silently becoming a removal is a suppressed buying signal. Assert the positives
  are unchanged.
- Tests covering every one of the 11 phrases AND every bare one-word form.
- Negative controls: break each pattern group deliberately and show the intended
  tests fail for the intended reason.
- Existing classifier tests: a name-set diff against master, zero NEW failing
  names. A count is not a baseline; the baseline is the named list.
- No prospect address may appear in any test, fixture, doc or commit message.

## Notes for the reviewer

The claim to attack hardest is "precision did not move". Twenty replies changing
verdict in the removal direction is easy to get by widening a regex until
everything matches; the question is whether any of the 20 is NOT a removal
request, and whether anything that was a real reply from an interested person
has been turned into a suppression.
