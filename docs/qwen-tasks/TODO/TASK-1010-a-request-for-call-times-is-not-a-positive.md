# TASK-1010 - a request for call times is not read as a positive

**Opened by lane 3, 2026-10-03**, classifying the 21 unmatched phase-2
firings. Full context: `docs/PHASE2-UNMATCHED-CLASSIFICATION-2026-10-03.md`,
section 2 rows 1-4. Verdict: **pravi defekt**.

The number was chosen by inspection (1007 is the highest in use across every
ref) and NOT by the task allocator, which is itself an open operator
decision. If the allocator assigns differently, renumber this file.

## The defect

A reply that asks for times for a call is classified `interested` at 0.60 by
the analysis taxonomy, whose every category maps to `unknown` in
`accountpolicy`, which is the one outcome with no `OUTCOME_POLICY` entry. So
the account is not held, the cadence is not stopped, and nobody is told.

This matters more than one scenario. The operator's own definition of a
positive, dated 2026-10-03 in
`resonate-ops/copy-review/POSITIVE-SAMPLE-2026-10-03.md`, is "an explicit
statement of interest, **a request to talk**, or a question about the offer".
A request to talk is limb two of three, and `positive` is 20 of 899 replies -
the only path a meeting comes down.

## Reproduction

On master `2bf7b8a5`. Run from anywhere EXCEPT the `%TEMP%` root, where a
stray `inspect.py` shadows the stdlib and drives this import chain into a
live `bison.fetch_replies`.

    py -3 -c "import sys; sys.path.insert(0, r'<repo>'); \
      from src import replies, accountpolicy; \
      v = replies.classify('this is interesting, can you send some times for a call next week'); \
      print(v['classification'], v['confidence'], accountpolicy.CLASSIFIER_OUTCOME[v['classification']])"

Observed:

    interested 0.6 unknown

Expected, under the operator's definition:

    positive 0.75 positive

### Why the rules miss it

`POSITIVE_PATTERNS` holds 34 patterns. The call-booking family is
`book (a|some) time`, `can we (schedule|arrange|organise|set up)`,
`set up a (call|meeting)`, `availability`, `calendar`, `next week works`.
**"can you send some times" is in none of them.** The sentence then falls
through every production rule and is caught by the taxonomy's `interested`
pattern on the OTHER clause, "this is interesting" - note that the production
pattern is the whole word `interested`, which "interesting" does not match.

Controls, measured in the same run:

    "can you send some times for a call next week"          -> unknown 0.00
    "sounds good ... can you send some times for a call"    -> positive 0.75  (on "sounds good")

So the positive half of that sentence contributes nothing today.

## The fix, and what it must not be

Add the "send times / send availability / what times suit" family to
`POSITIVE_PATTERNS`, **validated against the 899-reply corpus and not against
this one sentence.** A pattern that makes S09 pass and moves no other row is
a pattern fitted to a test, and the operator's own file already measured
`positive` at 38.5% precision - a widened pattern that lowers it further is
worse than the miss.

The acceptance condition is therefore two-sided and both halves are required:

1. the four S09 fields match; and
2. re-running the classifier over the 899-reply corpus shows the `positive`
   count rising only on replies that a reader agrees are requests to talk,
   with the diff listed row by row.

**Do not** reach for this by promoting the taxonomy's `interested` or
`meeting_intent` into `positive`. TASK-074's reason still holds: a taxonomy
verdict may not widen what automation is allowed to do.

## What this task does NOT cover

Row 4 of the classification table - that a correctly classified non-positive
reply reaches nobody - is **TASK-1004**, written, at REVIEW, on branch
`task-1004-positive-replies-reach-a-human`. Merging that is the action there.
No duplicate was opened here.

## Status

TODO. Not started. No code changed by lane 3.
