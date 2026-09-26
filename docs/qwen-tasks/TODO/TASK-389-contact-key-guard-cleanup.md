PRIORITY: P2
SIZE: S
DEPENDS:

# TASK-389 — contact-key guard clean-up

**Operator instruction, 2026-09-26/27 overnight standing order.** `contact_key`
is read and validated in many modules (`grep -rln contact_key src/` returns a
long list — `account.py`, `accountpolicy.py`, `actionledger.py`, `adapters.py`,
`approval.py` and more). Trace whether its VALIDATION — is this a well-formed
key, does it uniquely identify one contact, is it the same key on both
channels for one person — is done once in one place, or reimplemented
slightly differently in several, which is exactly the class of drift this
repository has been burned by before (`packfacts` vs `researchpack`, the
`heyreachfactory` daily-limit field, the two `NotApproved` classes TASK-379
found).

## Trace first — name the current state with file:line

1. `grep -rn "def.*contact_key\|contact_key ==" src/*.py` — every place that
   VALIDATES or COMPARES a contact_key (not just reads it as a dict key).
2. For each, does it check the same invariant (non-empty, matches the
   record's own email/LinkedIn identity, stable across a resume) or does one
   check something the others skip?
3. Name any place two contacts could collide on the same `contact_key`
   without either check catching it — this is the failure this task exists
   to prevent, not "the code is untidy."

## Build only if the trace finds a real inconsistency

If validation logic differs in a way that could let two different people
share a `contact_key`, or drop the check silently in one path, consolidate
to one function (in whichever module already owns identity — likely
`account.py` or `accountpolicy.py`, name which) and have every other site
call it. Do not consolidate cosmetic duplication that carries no risk — a
one-line `if not contact_key:` appearing in three files with identical
behaviour is not a bug, just repetition; only merge it if you also have a
smaller change in mind that removing the duplication makes possible.

## Acceptance

1. Report the full list of validation/comparison sites with file:line and
   what each actually checks.
2. If nothing is inconsistent: say so plainly and close this without a code
   change - that is an acceptable, complete answer.
3. If something is inconsistent: show the guard-failure test (revert your
   consolidation, confirm the collision case you found is no longer caught,
   restore).
4. Full suite: wait for `work/suite_verdict.txt`, diff the failing-name SET.

## What this task may NOT do

- Do not refactor identity code beyond the specific inconsistency found -
  this repo's own rule: surgical changes, delete only what your own change
  orphaned.
- Nothing sent, nothing activated.
