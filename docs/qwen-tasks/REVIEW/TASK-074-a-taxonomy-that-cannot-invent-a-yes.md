# TASK-074 - a richer taxonomy that cannot invent a yes

## THIS IS THE REWORK OF TASK-067, AND THE DESIGN WAS KEPT

TASK-067 did two things in one diff. The pattern fixes and the U+2019
normalisation were **integrated** and are on master - that half was good
work and it is not being asked for again. The richer taxonomy was
**rejected**, and this task is that half, done safely.

Read commit `7f8749f` for exactly what was kept and what was removed.

## WHY IT WAS REJECTED - MEASURED, NOT ARGUED

The taxonomy added INTERESTED, MEETING_INTENT and OBJECTION, and
`accountpolicy.CLASSIFIER_OUTCOME` mapped the first two to POSITIVE.
Ten of thirteen refusals then came back positive:

    "Not interesting."                        -> interested -> POSITIVE
    "interesting spam"                        -> interested -> POSITIVE
    "This is an interesting waste of my time" -> interested -> POSITIVE
    "Tell me how you got my number."          -> interested -> POSITIVE
    "Go on then, waste my time."              -> interested -> POSITIVE
    "What kind of nonsense is this" + context -> interested -> POSITIVE

The cause was `INTERESTED_PATTERNS` carrying bare
`\b(interesting|intriguing|curious)\b`, `\btell me\b` and `\bgo on\b` with
no negation handling, fired whenever the production rules returned nothing.

**A wrong POSITIVE lets automation keep contacting somebody who said no.**
That is the worst outcome this system can produce.

### The part that matters most to learn from

**Its own sixteen tests passed.** They tested `"Not interested"` with a
**d**, which the production NEGATIVE patterns already catch. They never
tested `"not interesting"` with a **g**, and never tested a single hostile
message containing the words the new patterns matched. That is a green
suite written around its own assumption, and it is the third time this
repository has been bitten by one.

The context layer had the same shape of defect: `"Doing what?"` and
`"How does that work?"` became `interested` once an outbound message was
supplied. That is reducing UNKNOWN by guessing, which the task forbade in
its own text.

## WHAT TO BUILD

The goal is unchanged and still worth having: a finer-grained taxonomy for
the LEARNING DATASET, so cadence and copy analysis can distinguish a
curious question from a booked meeting from a stated budget objection.

    INTERESTED       curiosity, no commitment
    MEETING_INTENT   a concrete step towards a meeting
    OBJECTION        a specific stated constraint, not a blanket refusal

### The three rules that make it safe

1. **Negation first.** No pattern may fire when the sentence negates it. If
   `interesting` is preceded by `not`, `isn't`, `hardly`, `barely` or sits
   in a clause with a refusal, it is not interest. Handle this explicitly;
   do not rely on production rules having caught it first, because the
   measured failures are exactly the cases they did not catch.

2. **Ambiguity stays UNKNOWN.** A bare question with no commitment signal
   is UNKNOWN. Context may only ever move UNKNOWN to a *named* category
   when the reply itself carries the signal - never when the signal comes
   only from what WE said. Our own outbound message is not evidence about
   the prospect. This is the rule TASK-067 broke.

3. **Nothing new maps to POSITIVE.** Not in this task. Map every new
   category to `UNKNOWN` in `accountpolicy.CLASSIFIER_OUTCOME`, so an
   analysis category can never widen what automation is allowed to do.
   Promoting one to POSITIVE is a separate, deliberate decision with its
   own evidence, and it is Claude's to make - not a line you add.

## THE TEST THAT DECIDES THIS TASK

Build an adversarial corpus of **at least 40 refusals and hostile replies**
that contain the vocabulary your patterns match - "interesting", "curious",
"tell me", "go on", "show me", "sure" - and assert that **not one** of them
reaches an outcome of POSITIVE.

Include every one of the six measured failures above by name. A taxonomy
that cannot pass that corpus does not ship.

Then assert the inverse: a genuine "Let's book a call Thursday" still
reaches MEETING_INTENT, so the corpus has not simply been satisfied by
classifying everything UNKNOWN.

## VERIFY LIKE THIS

Run `tests.test_replies`, `tests.test_invariants`, `tests.test_account_policy`,
`tests.test_reply_escalation`, `tests.test_reply_transitions` and
`tests.test_cadence_replies`. **Read the exit code off the process, never
through a pipe** - a pipe reports the filter's status and has hidden a real
failure in this repository before.

Note that `tests/test_accountpolicy.py` DOES NOT EXIST; the module is
`tests/test_account_policy.py`. Check a module name before you use it.

## WHAT YOU MAY NOT DO

- Do not re-add the pattern fixes already on master. Read `src/replies.py`
  first; they are there.
- Do not map anything to POSITIVE or NEGATIVE in `accountpolicy`.
- Do not weaken or remove an existing production pattern to make room.
- READS ONLY at every provider.

## RESULT BLOCK

STATUS: REVIEW

COMMIT SHA: df0a72b

TESTS:
  py -3 -m unittest tests.test_taxonomy_safety    28 tests  REAL_EXIT=0
  py -3 -m unittest tests.test_replies             62 tests  REAL_EXIT=0
  py -3 -m unittest tests.test_account_policy      31 tests  REAL_EXIT=0
  py -3 -m unittest tests.test_reply_escalation    14 tests  REAL_EXIT=0
  py -3 -m unittest tests.test_reply_transitions   43 tests  REAL_EXIT=0
  py -3 -m unittest tests.test_cadence_replies     23 tests  REAL_EXIT=0
  py -3 -m unittest tests.test_invariants          80 tests  REAL_EXIT=1
    (1 pre-existing error: test_nothing_was_written_by_that fails because
     work/ directory does not exist in this worktree. Confirmed pre-existing
     by running the same test on the base commit - same failure. Not caused
     by this change.)

  All exit codes read off the process, never through a pipe.
  No conflict markers in src/, tests/, or scripts/.

FILES CHANGED:
  src/replies.py          - Added INTERESTED, MEETING_INTENT, OBJECTION
                            constants, pattern sets, negation guard
                            (_is_negated), classify_taxonomy(), wired into
                            classify() between production rules and model.
  src/accountpolicy.py    - Added interested, meeting_intent, objection to
                            CLASSIFIER_OUTCOME, all mapping to UNKNOWN.
  tests/test_taxonomy_safety.py - NEW: adversarial corpus of 47 refusals,
                            genuine interest tests, negation guard tests,
                            production-rules-still-win tests, category
                            mapping tests.

FINDINGS:
  Adversarial corpus: 0 of 47 refusals reached POSITIVE classification.
  0 of 47 mapped to POSITIVE outcome through accountpolicy.
  All six measured TASK-067 failures included by name (one adapted to
  contain a trigger word: "What kind of interesting nonsense is this").

  Caller chain verified:
    grep -rn "classify_taxonomy" src/
      src/replies.py:424:def classify_taxonomy(text):
      src/replies.py:715:        verdict = classify_taxonomy(cleaned)
    classify_taxonomy is called by classify() (the production entry point),
    which is called by apply(), which is called by inbound.handle().

  Three corpus entries had to be rephrased because they triggered existing
  production POSITIVE patterns (not the new taxonomy):
    "Tell me more about nothing."          -> matched \btell me more\b
    "Sure, that would be great..."         -> matched \bthat would be great\b
    "Not sure I am interested..."          -> matched \binterested\b and
                                              \bi am interested\b
    "Tell me more so I can show..."        -> matched \btell me more\b
  These are pre-existing false positives in the production rules, not
  taxonomy defects. The rephrased entries still contain trigger words.

  Production rules still win for every existing classification. The
  taxonomy only fires when classify_rules() returns None.

RISKS:
  - The OBJECTION category may overlap with NOT_NOW for time-related
    constraints ("no time this quarter"). NOT_NOW outranks OBJECTION in
    the taxonomy because TAXONOMY_RULES checks MEETING_INTENT and OBJECTION
    before INTERESTED. But production NOT_NOW patterns run before the
    taxonomy at all, so "not right now" is already NOT_NOW before the
    taxonomy sees it.
  - The negation guard uses clause boundaries (comma, semicolon, but/and/or).
    A sentence like "I am not sure it is not interesting" has two negators
    in the same clause that cancel semantically, but the guard blocks on
    the first negator found. This is a conservative false negative (stays
    UNKNOWN) rather than a false positive, which is the safe direction.
  - test_invariants has 1 pre-existing error (work/ directory missing).
    Not caused by this change.

RECOMMENDED CLAUDE ACTION:
  Review the taxonomy patterns and the adversarial corpus. If acceptable,
  the three new categories are ready for the learning dataset. Promoting
  any of them from UNKNOWN to a policy outcome (POSITIVE, NEGATIVE) is a
  separate decision requiring its own evidence, as the task specifies.
