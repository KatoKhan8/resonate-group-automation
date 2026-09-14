# TASK-077 - the variant machinery has never met a model

## THE GAP, STATED PLAINLY

TASK-044 built `src/variantgen.py` and it is good: five approaches varying
tone, opening structure, pain-led versus observation-led, question versus
statement and CTA style, with the observation-led arm correctly unavailable
when no licensed observation exists. It builds no experiment ledger, which is
right - the provider carries variant identity itself.

**And every one of its tests uses a fake model.** Generation is opt-in behind
`generate_variants: true`, which no config sets. So five materially different
variants have NEVER BEEN PRODUCED - only the machinery that would produce
them.

This is the repository's recurring defect wearing its most flattering
disguise: 622 lines, 453 lines of tests, all green, nothing generated. Read
the "Existence is not function" paragraph in `CLAUDE.md` before starting.

## WHAT TO DO

Run it against the real model and read what comes out.

1. Enable `generate_variants` for the Productive client.
2. Generate five variants for at least THREE different steps across at
   least THREE records - a LinkedIn step and an email step among them.
3. Put every variant through the SAME quality gates as a single draft.
   Do not widen a gate. A variant that fails is a finding.
4. **Read them as a human and say whether they are actually different.**

## THE QUESTION THAT DECIDES THIS TASK

Five trivial paraphrases fail. For each set of five, say which DIMENSION
actually varies, quoting the opening line of each:

    variant   approach          opening line              genuinely different?
    1         pain_led          "..."
    2         observation_led   "..."
    ...

If three of the five are the same sentence with synonyms swapped, SAY SO.
That is the outcome this task exists to detect, and `variantgen`'s own
`diversity_collisions` check should be catching it - report whether it did.
A check that passes five paraphrases is a check that is not working.

## THE KNOWN LIMITATION TO CONFIRM OR DENY

TASK-044 flagged it and nobody has tested it: LinkedIn has no `problem_led`
style, so `problem_led` and `observation_led` both map into existing buckets
and TWO ARMS SHARE ONE. If that is real, two of the five LinkedIn variants
are not distinguishable to the evaluator and the arm count is really four.
Measure it and say which it is.

## WHAT YOU MAY NOT DO

- **READS ONLY at every provider.** No campaign write, no sequence write, no
  lead add. Calling the MODEL is the point of this task and is allowed.
- Do not approve anything. Approval is a human act.
- Do not widen a gate to make a variant pass.
- If `work/queue.jsonl.lock` names a LIVE process, wait or work read-only;
  only remove a lock naming a DEAD pid, and say so if you do.

## RESULT BLOCK

STATUS, COMMIT SHA, TESTS (exact commands, exact counts, exit codes read off
the process and never through a pipe), FILES CHANGED, FINDINGS (the variant
table above with quoted openings, plus the shared-bucket answer), RISKS,
RECOMMENDED CLAUDE ACTION.
