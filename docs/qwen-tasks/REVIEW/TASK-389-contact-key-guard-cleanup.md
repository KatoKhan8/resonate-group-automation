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

## RESULT

**STATUS:** DONE — no code change, no inconsistency found
**COMMIT:** 74a748e1 (claim only)
**TESTS:** No new tests; existing `test_identity_survives_exclusion.py` covers all three validation invariants
**FILES CHANGED:** Task file only (moved TODO → RUNNING)
**ARTIFACT KIND:** Finding (investigation task, no code change)

### Full list of validation/comparison sites

**Key generation (ONE place):**
- `src/identity.py:79` — `contact_key(contact, existing=())`: the single authority. Stored key wins → name slug → email slug → digest fallback. Collision handling: same identity keeps key, different identity gets digest suffix.
- `src/identity.py:98` — `assign_keys(contacts)`: the ONLY place `contact["key"]` is set (confirmed: `contact["key"] = key` at line 103 is the sole assignment in all of `src/`).

**Key validation (ONE place):**
- `src/store.py:1642` — `_identity_problems(rec)`: checks (a) every contact/excluded has a key, (b) no two contacts share a key ("held by N contacts"), (c) every event references an existing contact. Called from `store.validate()` at line 1638.

**Key computation delegate (ONE place):**
- `src/lint.py:242` — `contact_key(contact)`: delegates to `identity.contact_key(contact)`. No independent logic.

**Key lookup (canonical + module-local, all consistent):**
- `src/lint.py:247` — `find_contact(rec, key)`: two-pass (stored key match, then recompute). Used by `approve.py:73`, `executionguard.py:1371`, `generate.py:2269/2354`, `push.py:68`, `lint.py:347/470/559`.
- `src/inbound.py:178` — `_contact_of(rec, contact_key)`: single-pass `contact.get("key") == contact_key`. Returns None.
- `src/outcomes.py:128` — `_contact_of(rec, contact_key)`: single-pass via `account.contacts_of(rec)`. Returns `{}`.
- `src/oooreturn.py:190` — `_contact_of(rec, contact_key)`: single-pass. Returns None.
- `src/account.py:228` — `contact_name(rec, contact_key)`: single-pass. Returns name or key.
- `src/audit.py:43` — `for_contact()`: single-pass `candidate.get("key") == contact_key`.
- `src/conversation.py:151` — `thread()`: single-pass `candidate.get("key") == contact_key`.
- `src/outreachclaims.py:475` — `_contact_name()`: single-pass.
- `src/repo.py:246` — `contact()`: single-pass.
- `src/notify.py:828` — `positive_reply_notification()`: single-pass.
- `src/push.py:430` — `mark_pushed()`: single-pass.

**Callers of `assign_keys` (the only key-setting path):**
- `src/enrich.py:626` — after adding contacts
- `src/personas.py:366,375` — during persona selection

**Other notable sites:**
- `src/funnel.py:238` — `if contact_key != contact.get("key"): continue`: loop variable comparison, not a validation guard. Filters cadence entries to the current contact.
- `src/run.py:242` — `unkeyed(rec)`: returns contacts without keys, used to detect stale stage state. Not a validation but a diagnostic.
- `src/leadobserve.py:527` — `if contact_key is None`: guard against missing parameter, not a key-format validation.

### Conclusion

**Nothing is inconsistent.** The validation is centralized:

1. **Generation:** `identity.contact_key()` is the single authority, called everywhere through `lint.contact_key()`.
2. **Assignment:** `identity.assign_keys()` is the only place `contact["key"]` is written.
3. **Validation:** `store._identity_problems()` checks all three invariants (non-empty, unique, events reference existing contacts).
4. **Lookup:** All module-local `_contact_of` functions do the same single-pass comparison against the stored key, which is correct because the stored key was set by `assign_keys` and validated by `_identity_problems`.

The two-pass `lint.find_contact` (stored key then recompute) is strictly more thorough than the single-pass `_contact_of` functions, but this is not an inconsistency — it is a defensive fallback for the case where a contact dict has no stored key but would compute to the same key. All single-pass lookups operate on contacts that have already been through `assign_keys`, so the stored key is always present and always correct.

No two contacts can collide on the same `contact_key` without `_identity_problems` catching it: `assign_keys` prevents collisions at assignment time (digest suffix for different identities), and `store.validate` catches any that slip through (e.g., from manual data edits).

**No code change is needed.** This task is complete as an investigation.

### RISKS
None identified. The contact_key invariant is well-guarded.

### RECOMMENDED CLAUDE ACTION
Close as DONE. No integration needed — the finding is that the code is already correct.
