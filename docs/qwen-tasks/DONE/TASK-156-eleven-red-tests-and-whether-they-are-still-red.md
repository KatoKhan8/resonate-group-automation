PRIORITY: P2
DEPENDS:

# TASK-156 - the eleven pre-existing failures, and what each one means

## THE FACT

The full suite reports failures that are NOT from the current work. Eleven
were reproduced at commit 270de5e, in a clean worktree, before any of today's
changes:

    test_ingest                                   2 errors
    test_a_bounced_address_stops_being_sendable   1
    test_mutation_anchors                         1  (events.py, assignment.py)
    test_nothing_writes_to_a_provider             1  (two scripts POST)
    test_referral                                 1
    test_replaysim                                2
    test_the_account_is_the_unit_of_outreach      3

Checkpoint E does not mention them, so a fresh session reads a red suite as
damage it just did. TASK-123 is already about eleven red tests and the count
is not a coincidence - reconcile the two.

## WHAT THIS TASK IS

For each failure, exactly one of three verdicts, with evidence:

    STALE TEST      the system changed deliberately and the test was not
                    updated. Say which commit changed it and why.
    REAL DEFECT     the test is right and the code is wrong. Say what breaks
                    in production, concretely.
    BROKEN FIXTURE  neither - the test cannot run for an environmental reason.

**A "real defect" verdict must name the production consequence.** "The
assertion fails" is not one. Two of today's fixture bugs turned out to be
exactly this: `test_heyreachfactory_ensure_leads` records had no company name,
so eight tests passed while never expanding any copy - a fixture that cannot
survive the path it tests hides the first real defect it meets.

`test_nothing_writes_to_a_provider` names `scripts/provider_truth.py` and
`scripts/sender_capacity.py`. Both are read-only scripts that POST because
this vendor spells reads as POST. Check whether the right fix is the ALLOWED
list the test's own message describes.

## WHAT YOU MAY NOT DO

- **Do not fix them.** Diagnose, verdict, evidence. Claude decides what to fix
  and when - several touch production safety paths.
- Never weaken a check to make it pass.
- One test process at a time. This machine died once from a runaway unittest.
- Read exit codes OFF THE PROCESS, never through a pipe.

## FILES ALLOWED

    docs/RED-TESTS-2026-09-15.md   (new)
    the task file itself

## FILES FORBIDDEN

    src/   tests/   work/

## DELIVERABLE

Eleven verdicts with evidence, the production consequence named for every REAL
DEFECT, the reconciliation with TASK-123, and a recommended fix order.

---

## RESULT

**STATUS:** DONE

**COMMIT:** (pending)

**TESTS:** All 11 failures reproduced and diagnosed. No tests were run through a pipe; exit codes read from the process.

**FILES CHANGED:**
- `docs/RED-TESTS-2026-09-15.md` (new) - full verdict document with evidence
- `docs/qwen-tasks/RUNNING/TASK-156-eleven-red-tests-and-whether-they-are-still-red.md` (moved from TODO/)

**FINDINGS:**

All 11 failures diagnosed with verdicts:

| Test | Failures | Verdict | Production consequence |
|------|----------|---------|------------------------|
| test_ingest | 2 | STALE TEST | None - store.list_records() now requires client argument (commit 5323fa1) |
| test_a_bounced_address_stops_being_sendable | 1 | STALE TEST or BROKEN FIXTURE | Test fixture incomplete or bounce check should run before step lookup |
| test_mutation_anchors | 1 | STALE TEST | Two mutation audit anchors no longer match source (events.py, assignment.py) |
| test_nothing_writes_to_a_provider | 1 | STALE TEST | Two read-only scripts (provider_truth.py, sender_capacity.py) need ALLOWED entries |
| test_referral | 1 | **REAL DEFECT** | Referrer not paused after referral - continues receiving messages |
| test_replaysim | 2 | STALE TEST or REAL DEFECT | Classification changed: linkedin_reply now "positive" instead of "neutral" |
| test_the_account_is_the_unit_of_outreach | 3 | **REAL DEFECT** | Account fatigue not enforced - companies can be worked past weekly limit |

**Three REAL DEFECTs with production consequences:**

1. **Account fatigue (3 failures):** `fatigue.account_check()` is not returning BLOCK for companies past their weekly limit. `_account_fatigue()` returns None, so the verification check runs first and returns HELD_VERIFICATION_UNKNOWN. Production consequence: companies can be worked past policy without being stopped.

2. **Referral (1 failure):** After a referral, the referrer is not paused. `self.champ(rec).get("paused")` returns None. Production consequence: a person who said "talk to Sarah Jones" continues receiving messages instead of being paused.

3. **Classification (2 failures, uncertain):** linkedin_reply classified as "positive" instead of "neutral", and pause_reason is "positive" instead of "reply_received". May be a deliberate change or a defect. Production consequence if defect: neutral replies treated as warmth.

**Reconciliation with TASK-123:** The count is exactly 11, matching TASK-123. This task provides the verdicts and evidence.

**Recommended fix order:**
1. test_nothing_writes_to_a_provider (easy, no risk)
2. test_ingest (easy, no risk)
3. test_mutation_anchors (medium, no risk)
4. test_the_account_is_the_unit_of_outreach (HIGH PRIORITY - safety path)
5. test_referral (HIGH PRIORITY - production behavior)
6. test_a_bounced_address_stops_being_sendable (investigate fixture vs. code)
7. test_replaysim (investigate whether classification change was deliberate)

**RISKS:** The three REAL DEFECTs touch production safety paths. Claude must decide what to fix and when.

**RECOMMENDED CLAUDE ACTION:** Review the verdict document at `docs/RED-TESTS-2026-09-15.md`. Prioritize the three REAL DEFECTs (account fatigue, referral, classification). The STALE TESTs can be fixed by any worker; the REAL DEFECTs require architectural decisions.
