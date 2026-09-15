PRIORITY: P2
DEPENDS: 

# TASK-118 - make it impossible to write a record id into a tracked report

## WHY

On 2026-09-15 the PII guard went green after 16 real tokens were redacted from
9 tracked files. **Within the same hour a newly integrated report reddened it
again** by naming four real record identifiers and a real contact. Claude
caught it only by running the guard before committing.

The guard works. It is the LAST line, and it fires after the text is written.
Everything upstream of it - workers writing reports, Claude writing task files
- has nothing but discipline, and discipline has now failed repeatedly:

    a script with 15 real prospect domains, believed redacted for a day
    a sender's real name written into a tracked JSON by a new script
    four record ids in a report written by a worker told not to
    one record id in a task file written by Claude

## WHAT TO BUILD

A helper every report generator can call, and a check that runs before commit
rather than after:

1. **`redact()`** - takes text, returns it with every forbidden token and
   every record-id-shaped token replaced by a STABLE pseudonym, so two
   mentions of one company stay linkable within a document. The existing
   redactions used `<client-hash>` and `<record-hash>`; match that.
2. **A pre-commit-style check** runnable as one command that reports what
   would leak, so a worker can run it before writing the file rather than
   discovering it in a test run.
3. **Wire at least one real generator through it** and prove the wiring is
   consumed - "existence is not function" is the recurring defect here, and a
   redactor nothing calls is exactly that shape.

## WHAT NOT TO DO

- Do not weaken `FORBIDDEN_NAMES` or the hygiene tests. This is an addition
  upstream of them, not a replacement.
- Do not redact in a way that destroys meaning. A report saying "40 of the 70
  overlap" must survive; only identifiers change.
- Do not put a real token in the test fixtures for this. Use the pseudonym
  shapes.

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
