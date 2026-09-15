PRIORITY: P2
DEPENDS: 

# TASK-117 - "as a fellow founder" and the claims the rule still cannot see

## THE FACT

A pushable contact carries the phrase "as a fellow founder". The claims rule
grew its FOURTH missing phrase to catch exactly this - checkpoint C predicted
it: it is an assertion about the SENDER where the rule watched the PROSPECT.

TASK-098 confirms the phrase is still present on a pushable contact, and notes
it is **structural, not stale** - regeneration will not remove it.

## THE QUESTION

The rule has now been extended four times, each time by one phrase, each time
after a phrase escaped. That is a pattern, and the pattern is the finding.

1. **What CLASS of claim is escaping?** "As a fellow founder" asserts the
   sender is a founder. What else in that class would pass today? Generate
   candidates and test them against the real rule: "speaking as someone who
   has scaled an agency", "having run a team your size", "as a fellow
   operator". Report which pass.
2. **Can the class be caught without a fifth phrase?** A rule that watches for
   assertions about the SENDER's identity or experience is a different shape
   from a list of four strings.
3. **What would such a rule falsely refuse?** This matters more than the
   catch rate. A rule that refuses "I work with agencies on resourcing" would
   destroy the sender-identity fix TASK-075 just landed - sender identity is
   now REQUIRED at rung 1, so a rule that treats every sender statement as an
   unsupported claim would make the ladder unsatisfiable.

**That tension is the real content of this task.** The sequence must say who
is writing and must not claim what the sender is not. Find where the line is.

## WHAT NOT TO DO

- Do not add a fifth literal phrase and call it fixed. That is the thing that
  has failed four times.
- Do not weaken the claims rule. If it correctly refuses copy, the copy is
  wrong.
- Do not break `test_rung_four_references_previous_questions` or the TASK-075
  sender-identity tests. Run them.

## RULES THAT APPLY TO THIS TASK

- Reads only at both providers. No POST/PATCH/PUT/DELETE, no sends, no
  campaign creation or activation, no adding leads.
- **A zero and a wrong lookup are indistinguishable from outside.** Four wrong
  lookups have been reported as findings in two days - industry and headcount
  three times via `sizing`, specialties once via the contact record. Prove the
  field you read is the right one before reporting a zero.
- Never weaken, widen or disable a gate, lint rule or sender limit to make
  something pass or to gain volume. Fix what produced the bad output.
- Read every test exit code OFF THE PROCESS, never through a pipe.
- **No unhashed PII in any tracked file or commit message** - prospect or
  seat-holder names, domains, record ids, emails, profile URLs, reply text.
  `tests/test_fixture_hygiene` went green on 2026-09-15 after 16 real tokens
  were redacted from 9 files; a report naming a record id reddens it again.
- Do not assert on the text of the source; assert on returned values.
- Do not report a PREDICTED result. You have model access via config/.env.
- Separate OBSERVATIONS (with n), HYPOTHESES and PROVEN LEARNINGS. Leave
  PROVEN LEARNINGS empty if nothing survives a sample-size objection.

## RESULT

**STATUS:** DONE
**COMMIT:** f5da78f
**TESTS:**
  - tests.task117_sender_identity_class: 24 tests, REAL_EXIT=0
  - tests.test_task075_sequence_introduces_sender: 23 tests, REAL_EXIT=0
  - tests.test_a_relationship_we_cannot_show_is_not_a_relationship: 16 tests, REAL_EXIT=0
  - tests.test_a_linkedin_note_is_claim_checked_too: 7 tests, REAL_EXIT=0
  - tests.test_invariants: 80 tests, REAL_EXIT=0
  - tests.test_replies + tests.test_taxonomy_safety: 106 tests, REAL_EXIT=0

**FILES CHANGED:**
  - src/claims.py: four safe patterns added to RELATIONSHIP tuple
  - tests/task117_sender_identity_class.py: new test module (24 tests)
  - docs/TASK-117-FINDINGS.md: full analysis document

**FINDINGS:**

OBSERVATIONS (n=28 candidates probed against real `claims.implies_prior_contact`
and `claims.check` on a bare record):

1. The existing 3 RELATIONSHIP patterns catch 7 of 28 sender-identity
   phrases (25%). All 7 use "as a fellow", "as someone who VERBs", or
   "speaking as a fellow".
2. 21 of 28 pass through. They fall into 8 syntactic shapes: "as a X"
   without fellow, participial experience ("having run"), "also a", "I am
   a fellow", present perfect experience, "like you I", "I know what it's
   like", possessive identity, and group identity with "too".
3. Four safe patterns catch 7 more (total 14/28, 50%) with ZERO false
   refusals on 22 must-pass phrases: having + identity verb, like you +
   first person, I am also a/an, role noun + too.
4. The remaining 14 cannot be caught by phrase patterns without false
   refusals. "as a founder myself" shares syntax with "as a result";
   "i have built two agencies" shares syntax with "i have a question";
   "my agency has 20 people" shares syntax with "my last message".

HYPOTHESIS: The real fix is not a fifth phrase but a config-level check.
When a sentence contains a role word (founder, CEO, owner) AND a
shared-identity marker (fellow, also, too, like you), check whether the
sender config supports the claimed identity. This is a different kind of
rule from phrase matching - it validates against config, not syntax.

PROVEN LEARNINGS:
- The escaping class is "sender-identity assertions that imply shared
  category with the recipient". The rule watched for PROSPECT claims and
  relationship claims; sender identity is a third category.
- The tension between "sequence must say who is writing" (TASK-075) and
  "must not claim what the sender is not" is real and has no phrase-level
  resolution. The line is: the sender may STATE their own identity from
  the config, but may not ASSERT that the recipient shares it.
- The `GENERIC_SUBJECTS` exit in `is_claim` prevents any "we" sentence
  from being classified as a claim, so "we are founders too" is
  structurally invisible to the rule regardless of patterns.

**RISKS:**
- The four new patterns add 7 catches but leave 14 escaping phrases.
  The partial coverage may create a false sense of security.
- The `[role] too` pattern lists 18 role nouns. A role not on the list
  escapes. The list is extensible but not exhaustive.
- The `like you ... I/we` pattern uses `.*` which could match across
  sentence boundaries in long texts. In practice, LinkedIn notes are
  under 300 chars and the pattern is bounded by the sentence splitter.

**RECOMMENDED CLAUDE ACTION:**
1. Review the four new patterns and the test module.
2. Consider the config-level sender-identity check as a follow-up task.
3. Update the linkedin_note.md prompt to explicitly forbid shared-category
   assertions ("as a fellow X", "having run a team your size", "like you,
   I am a founder") - the prompt currently says "NEVER invent a sender
   name, title or company" but the model extends beyond the literal words.
