# TASK-095 - the fixture-hygiene guard is red, and it is the PII guard

## THE THREE RED TESTS

Split out of TASK-088 because they guard something different from the rest.

    tests.test_fixture_hygiene
      TestKnownSets.test_every_phone_number_is_a_reserved_fiction      FAIL
      TestNoRealDataAnywhereInGit.test_every_email_address_is_on_a_reserved_domain
      TestNoRealDataAnywhereInGit.test_no_real_person_or_client_named  FAIL

All three were red in the FIRST full-suite run, so none was caused by the
2026-09-14/15 work. They are pre-existing, verified present at `a519954`.

## WHY THIS ONE MATTERS MORE THAN ITS COUNT SUGGESTS

This is the guard that stops real prospect data entering tracked files. It
has already caught a real leak this estate produced: four documents and
`scripts/task065_run_bcd.py`, which had fifteen real prospect domains baked
into a literal list. Those were redacted and
`test_no_real_client_prospect_or_roster_domain` passes now.

**A red hygiene guard is indistinguishable from an absent one.** While these
three fail, nobody can tell a new leak from the standing noise - which is
precisely how the last one survived.

## WHAT TO DETERMINE, PER TEST

For each of the three, answer the question this repository got right on the
tenancy tests and had to be forced to ask:

**Is this a STALE TEST, or a REAL LEAK?**

TASK-086 found three tenancy failures that looked like leaks and were stale
tests - production had got STRICTER and nobody updated them. The fix there
was ZERO production changes. But the same session found a REAL safety
regression hiding in the same red set. Both answers are live. Check, do not
assume, and **if any of the three is a real leak, STOP and write it up rather
than redacting quietly** - the operator needs to know what escaped and where.

Note the distinction that cost two wrong probes last time: a guard that
reports by RETURN VALUE and a guard that is ABSENT look identical from the
outside if you only watch for exceptions.

## WHAT NOT TO DO

- **Do not widen the guard** to make it pass. A reserved-domain list that
  admits a real domain is not a guard. This is the same move as widening a
  quality gate, which has been measured and rejected twice.
- **Do not put the real value in the task file, the commit message or the
  report** while proving a leak exists. Name the FILE and the LINE and say
  what CLASS of data it is. That is enough to act on.
- Remember that redaction fixes the working tree only. Anything already
  committed remains in git HISTORY, so a real leak is MITIGATED, not erased,
  and a history rewrite is an operator decision - not yours and not Claude's.
- Two module names that DO NOT EXIST and keep getting written into tasks:
  `tests/test_accountpolicy.py` (it is `test_account_policy.py`) and
  `tests/test_inbound_classification.py`. Check a name before using it.

## DELIVERABLE

A verdict per test - STALE TEST or REAL LEAK - with the evidence for each,
the fix for the stale ones, and a written escalation for any real one. Run
the neighbours, not just the three. Read every exit code off the process,
never through a pipe - a pipe reports the filter's status.

---

## AWAITING REVIEW - results on FOUR branches, 2026-09-15

Four workers ran this independently because QWEN.md permitted self-selection
(fixed in 55e56c8). Results on qwen-worker-2-r6, -4-r6, -7-r6, -8-r6 and
qwen-worker-r6. They agree: two stale tests fixed, one real leak escalated.

Claude has verified part of it directly:
- `test_no_real_person_or_client_named` is STILL RED on master.
- Real prospect domains remain in `scripts/task065_run_bcd.py` - checkpoint D
  claimed this had been redacted and it has not been.
- Real tokens remain in four docs.
- Claude ADDED a leak on top: the LinkedIn seat holder's real name, written
  into docs/state/PROVIDER-CAMPAIGNS.json by scripts/provider_truth.py and
  pushed at abae39b. Scrubbed at ca53cb5; still in history.

Take one worker's fix, not four. Compare them before choosing.
