# TASK-043 - Semantic duplicate detection across a whole campaign

The operator observed the same question - "how do you currently ensure
profitability is visible in your projects?" - appearing repeatedly in the real
campaign.

## WHAT IS ALREADY DONE

One cause is fixed: `COPY_MAPPING` fed cadence step `li2` into two ADJACENT
graph roles, so the already-connected branch sent the identical sentence twice
three days apart. Commit d0549d1, and
`tests/test_no_branch_repeats_a_message.py` walks every root-to-leaf path and
asserts no path carries the same TEXT twice.

That test compares exact strings. It would not catch "how do you track
profitability today?" following "how do you currently ensure profitability is
visible?" - which is the same message wearing different words, and is what the
operator is actually asking about.

## GOAL

Detect SEMANTIC duplication across a whole campaign sequence, not just exact
repeats, and refuse it before the sequence is written.

## SCOPE

1. Extend the path walk to compare messages semantically. `src/quality.py`
   already has `repetition_across_rungs` and `_distinctive_words`, built for
   the email ladder - establish whether it can serve here before writing
   anything new. A second implementation of "are these two messages the same"
   is exactly the drift this repository keeps finding.
2. `quality` discounts the company's own name, because every message in a
   sequence names the company. The same applies here and more so: every
   message in a Productive sequence says "profitability" or "margin". Those
   words are the SUBJECT, not the duplication - a comparison that flags them
   flags everything.
3. Compare across the WHOLE campaign, not only adjacent steps. The operator is
   explicit: "consecutive or non-consecutive".
4. Refuse rather than warn, and name BOTH steps and the overlap.
5. Say what your threshold is and why, and show the distribution it produces
   on the real corpus rather than asserting a number.

## PRODUCTION BOUNDARY

ZERO network, ZERO credentials - `config/.env` does not exist in this
worktree. No provider call. No write to `work/**`. Nothing staged, activated
or sent. Claude owns every live action.

## HANDOFF FORMAT

STATUS / COMMIT SHA / FILES CHANGED / TESTS RUN / TEST RESULTS / BUGS FOUND /
BUGS FIXED / RISKS / OPEN QUESTIONS / RECOMMENDED CLAUDE ACTION

Plus the grep proving each new name is CONSUMED, and confirmation that
deleting the CALL to your new code makes a test fail.

## TESTS REQUIRED

- two messages differing only in wording are caught;
- two messages that share only the subject vocabulary - profitability, margin,
  the company name - are NOT caught;
- a genuinely progressive sequence passes;
- the refusal names both steps;
- the existing exact-match path test still passes.

## DONE CONDITION

A sequence whose steps rephrase one another cannot be written, and a
legitimately progressive one is unaffected - shown on real stored copy, not
only on fixtures.

---

## ADDED 2026-09-14: STRUCTURAL repetition, with evidence

Read `docs/CAMPAIGN-ACCEPTANCE-2026-09-14.md` first. The five emails staged on
a real lead share one formula:

    [the company's own self-description]
    -> [why I am writing to you, by role]
    -> [question or pitch]

Four of the five open by naming the company and describing it - "describes
itself as", "offers a wide range of", "partners closely with", "focuses on
delivering". Four different sets of words, one shape. And "I am reaching out
to you as COO and Co-Founder" appears in two of them.

**`quality.repetition_across_rungs` passed all of it**, because it counts
shared distinctive WORDS and the formula uses different words every time.

So this task must catch SHAPE as well as CONTENT:

- do consecutive messages open with the same MOVE - naming the company,
  describing it, restating the role?
- does the same framing sentence recur with different nouns?
- is the sequence of moves identical across steps?

A sequence where every message is [context][why you][question] is a sequence
of one message told four ways, and it is what the operator means by "five
versions of the same message".

Report the measurement on the real stored copy. If your comparator flags the
five emails above, it works; if it passes them as it stands, it does not.
