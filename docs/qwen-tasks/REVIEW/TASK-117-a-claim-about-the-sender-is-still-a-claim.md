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
