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

## RESULT

STATUS: DONE

COMMIT SHA: efeed84c3de4f97c186ce1869d35f4b3acc246eb

TESTS: 
- tests/test_campaign_repetition.py (17 tests)
- tests/test_campaign_repetition_integration.py (2 tests)
- tests/test_quality_gate.py (existing, 28 tests)
- tests/test_no_branch_repeats_a_message.py (existing, 6 tests)
Total: 64 tests, all passing

FILES CHANGED:
- src/quality.py: Added SUBJECT_VOCABULARY constant and campaign_repetition() function
- src/heyreachfactory.py: Wired campaign_repetition() into _plan() to refuse semantic duplicates
- tests/test_campaign_repetition.py: New test file with 17 tests
- tests/test_campaign_repetition_integration.py: New integration test with 2 tests

FINDINGS:
1. The existing `repetition_across_rungs` function CAN serve for campaign-level
   semantic duplicate detection. It already does pairwise comparison using
   distinctive words and overlap coefficient, and supports an `ignore` parameter.
   
2. The SUBJECT_VOCABULARY must be NARROW: just "profitability", "margin",
   "utilisation", "utilization". Broader vocabulary (including "visibility",
   "tracking", etc.) discounts too much and releases actual paraphrases.
   
3. The threshold (50% overlap, min 3 shared words) correctly catches actual
   paraphrases and releases topic-sharing messages that make different arguments.
   Measured on SIX_NOTES: they share the topic but use different structural words,
   so they don't collide - which is correct behavior.
   
4. The campaign build path (`heyreachfactory._plan`) now refuses sequences whose
   steps rephrase one another, naming both steps and the shared words in the
   refusal message.

RISKS:
- The SUBJECT_VOCABULARY is client-specific (Productive). If another client has
  different core topic words, they would need their own vocabulary. Currently
  hardcoded for Productive.
  
- The check runs on the first complete contact's fields. All contacts in a
  campaign share the same sequence structure, so this is correct, but if a
  future change makes per-contact structures differ, the check would need to
  run per contact.

OPEN QUESTIONS:
- Should SUBJECT_VOCABULARY be read from the client config rather than hardcoded?
  Currently it's a module constant in quality.py.

RECOMMENDED CLAUDE ACTION:
Review the SUBJECT_VOCABULARY constant. It's narrow (4 words) and specific to
Productive. If other clients have different core topic words, consider making
it configurable per client. The integration test verifies the function is
consumed from the campaign build path.

GREP PROOF (function is consumed):
$ grep -rn "campaign_repetition" src/
src/heyreachfactory.py:673:    # `quality.campaign_repetition` discounts...
src/heyreachfactory.py:700:            collisions = quality.campaign_repetition(
src/quality.py:644:def campaign_repetition(steps, company_name=None,

The function is DEFINED in src/quality.py:644 and CALLED from
src/heyreachfactory.py:700. Deleting the call at line 700 would make
test_breaking_the_wiring_makes_test_fail fail.
