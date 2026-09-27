# TASK-291: Second Pass Review of TASK-278 Spend Report

**Date:** 2026-09-26  
**Reviewer:** qwen-7  
**Status:** REWORK — deliverables do not exist

---

## Executive Summary

**TASK-278 was never implemented.** The task brief exists and was moved to REVIEW with a note stating "DELIVERED BY qwen-5", but none of the three required deliverables were ever committed to any branch in the repository's entire git history:

- `scripts/spend_report.py` — **does not exist**
- `docs/SPEND-REPORT-2026-09-24.md` — **does not exist**
- `tests/test_spend_report.py` — **does not exist**

There is no spend report to review. The verdict is **REWORK** and **TASK-282 may NOT proceed**.

---

## Verification Method

### 1. Does `scripts/spend_report.py` exist on master?

**NO.** Checked three ways:

```bash
git show master:scripts/spend_report.py
# fatal: path 'scripts/spend_report.py' does not exist in 'master'

git show qwen-worker:scripts/spend_report.py
# fatal: path 'scripts/spend_report.py' does not exist in 'qwen-worker'

git log --all --oneline --diff-filter=A -- scripts/spend_report.py
# (empty)
```

The file has **never been added to any branch** in the repository's history.

### 2. Do any of TASK-278's deliverables exist anywhere?

**NO.** Searched all branches for all three files:

```bash
git log --all --source --all -- \
  scripts/spend_report.py \
  docs/SPEND-REPORT-2026-09-24.md \
  tests/test_spend_report.py
# (empty)
```

Zero commits have ever touched these files. The TASK-278 commits (`2209c952`, `f792203a`) only contain the task brief itself.

### 3. Does qwen-5's worktree have the deliverables?

**NO.** Checked `C:/Users/Zvonimir/Desktop/resonate-qwen-5/` on branch `qwen-worker-5-r59`:

```bash
ls C:/Users/Zvonimir/Desktop/resonate-qwen-5/scripts/spend_report.py
# ls: cannot access ... No such file or directory
```

qwen-5's branch has no commits mentioning "spend_report" or "SPEND-REPORT".

---

## Per-Provider Table

**Cannot be produced.** The report does not exist.

| Provider | Figure | Source | Endpoint+Field | Our Ledger | Delta |
|----------|--------|--------|----------------|------------|-------|
| (all)    | N/A    | N/A    | N/A            | N/A        | N/A   |

---

## The Underlying Bug: 22,000-Credit Gap

**The bug TASK-278 was built to address has been fixed**, but the report that was supposed to document it was never written.

### What was wrong

`scripts/stage_s5_verify.py` called `verification.verify(...)` without passing `rec`, and every `spendledger.record` call was guarded by `if rec is not None`. Result: ~22,000 verification credits with no ledger rows.

### What was fixed

`stage_s5_verify.py` line 647 now passes `rec=rec`:

```python
rec = ledger_record(contact)
try:
    decision = verification.verify(contact, policy, live=True,
                                   rec=rec, config=config) or {}
```

### What tests the fix

`tests/test_every_s5_verification_reaches_the_spend_ledger.py` exists and verifies the behavior. The test docstring states:

> `verification.verify` gates BOTH ledgers - `waterfall.record_step` per record and `spendledger.record` per client - behind `if rec is not None`, and `scripts/stage_s5_verify.py` called it with no `rec` at all. So the most expensive stage in the funnel was the one stage the spend audit could not see: ~22,000 credits of verification with not one row against them.

The test drives `stage_s5_verify.main()` with a fake verifier and asserts that every provider call produces a ledger row. **This test passes.**

### What is still missing

A report that documents:
- What each provider says we spent (from balance/usage endpoints)
- What our ledger says we spent
- Where the two disagree and by how much
- Which providers have no endpoint and must be read by hand

That report was TASK-278's deliverable. It does not exist.

---

## Credential Names

### What config.VARIABLES declares

Provider credentials in the registry (`src/config.py` lines 51-180):

- `CONTACTOUT_TOKEN` (LIVE, providers)
- `BLITZ_API_KEY` (LIVE, providers)
- `AIARK_KEY` (LIVE, providers)
- `REOON_KEY` (LIVE, providers)
- `DELIVERABLE_KEY` (LIVE, providers)
- `BISON_KEY` (LIVE, providers)
- `HEYREACH_KEY` (LIVE, providers)
- `APIFY_TOKEN` (LIVE, providers)
- `OPENROUTER_API_KEY` (LIVE, providers)
- `GROQ_API_KEY` (LIVE, providers)
- `ANTHROPIC_API_KEY` (LIVE, providers)

### What provider adapters actually use

- `src/providers/xai.py` line 32: `ENV_KEY = "XAI_API_KEY"`
- `src/providers/glm.py` line 69: `ENV_KEY = "ZAI_API_KEY"`

**Neither `XAI_API_KEY` nor `ZAI_API_KEY` are in `config.VARIABLES`.**

### What credential_health.py checks

`scripts/credential_health.py` CHECKERS map (lines 67-75):

```python
CHECKERS = {
    "CONTACTOUT_TOKEN": "contactout",
    "AIARK_KEY": "aiark",
    "REOON_KEY": "reoon",
    "BISON_KEY": "bison",
    "HEYREACH_KEY": "heyreach",
    "BLITZ_API_KEY": "blitz",
    "DELIVERABLE_KEY": "deliverable",
    "XAI_API_KEY": "xai",
    "ZAI_API_KEY": "glm",
}
```

The script's docstring says "this reads `config.VARIABLES`... and cannot invent a name", but the CHECKERS map has two names that are NOT in the registry. The `credential_names()` function does read from VARIABLES, so these two would not be reported by that path. The CHECKERS map is only used for `--verify`.

**This is a discrepancy, but not a blocking one for TASK-291.** The spend report would need to handle xAI and Z.ai, and if it followed the rule "credential names come from config.VARIABLES", it would not be able to check them at all.

---

## Redaction and Secrets

**Cannot be verified.** The script does not exist, so there is no output to inspect and no redaction mechanism to test.

The task brief carries the rule explicitly:

> **NEVER PRINT A CREDENTIAL VALUE, AND NEVER PRINT A WHOLE RESPONSE.** Print named fields only. Never `for k in response`. Never "everything except".

This rule exists because on 2026-09-24 a session read Apify's `/users/me`, filtered by hand to hide email and user id, and printed the account's **proxy password** in full. The allow-list-what-to-hide pattern is the defect.

Without a script, there is no mechanism to verify and no negative test to run.

---

## The Four States

The task brief requires keeping apart:

- `NOT_CONFIGURED` — variable unset or blank
- `CONFIGURED_UNVERIFIED` — set, nothing has asked the provider
- `AUTHENTICATION_VERIFIED` — provider answered as this account
- `AUTHENTICATION_FAILED` — provider rejected the credential
- `PROVIDER_UNAVAILABLE` — provider could not be reached

`scripts/credential_health.py` implements this correctly (lines 57-63):

```python
NOT_CONFIGURED = "CREDENTIAL_NOT_CONFIGURED"
UNVERIFIED = "CREDENTIAL_CONFIGURED_UNVERIFIED"
VERIFIED = "AUTHENTICATION_VERIFIED"
FAILED = "AUTHENTICATION_FAILED"
UNAVAILABLE = "PROVIDER_UNAVAILABLE"
```

The distinction matters: "a set variable is not an authenticated one, and a transport failure is not a bad key." Without a spend report, there is no claim to check for conflation.

---

## Flat Fees

The task brief requires:

- **Claude Max** — present and not double-counted
- **Apify Scale** — 199 USD prepaid, not double-counted against metered usage

**Cannot be verified.** The report does not exist.

---

## Baseline

The task brief requires stating which baseline was used:

- Earliest balance on record (2026-09-18), OR
- First ledger row, whichever is earlier

**Cannot be verified.** The report does not exist.

---

## Re-Runability

The task brief requires running the script twice and confirming the figures agree or stating why they moved.

**Cannot be verified.** The script does not exist.

---

## What TASK-278 Actually Delivered

The TASK-278 file in REVIEW/ (`docs/qwen-tasks/REVIEW/TASK-278-spend-report-from-provider-balances.md`) has a state note:

```
STATE RECORDED BY LANE E, 2026-09-24 late

    DELIVERED BY     qwen-5, 2026-09-24
    STATE            REVIEW (moved out of TODO/ tonight)
    ON MASTER        NO - `scripts/spend_report.py` does not exist on master.
    NEXT             TASK-291 - second pass.
```

The note says "DELIVERED BY qwen-5" but the deliverables do not exist. The note also says "ON MASTER NO" and acknowledges the script does not exist on master, but it does not say the script does not exist **anywhere**.

The task was moved to REVIEW without the work being done.

---

## Impact on TASK-282

TASK-282 (`docs/qwen-tasks/TODO/TASK-282-the-spend-report-nobody-reads-on-a-monday.md`) depends on TASK-278 and TASK-291. Its dispatch note says:

> **DO NOT START** until TASK-278 is merged to master or TASK-291 has cleared it — you would be wiring a thing that does not exist on master yet.

**TASK-282 may NOT proceed.** There is nothing to wire. The spend report does not exist on master, on qwen-worker, on qwen-5's branch, or anywhere in git history.

---

## Verdict

**REWORK.**

The spend report, the script that generates it, and the test that validates redaction do not exist. There is nothing to review.

### What must happen before TASK-282 can proceed

1. **TASK-278 must be re-implemented.** The script, report, and test must be written and committed.
2. **The report must be sourced from provider endpoints**, not from the ledger. The ledger is incomplete (though the 22,000-credit gap has been fixed for future runs).
3. **The redaction rule must be enforced:** named fields only, never everything-except.
4. **Credential names must come from `config.VARIABLES`**, or the discrepancy with `XAI_API_KEY` and `ZAI_API_KEY` must be resolved.
5. **The report must state, per provider, where our ledger disagrees with the provider and by how much.**

### What is already done

- The 22,000-credit gap bug is fixed (`stage_s5_verify.py` now passes `rec=rec`)
- The fix is tested (`test_every_s5_verification_reaches_the_spend_ledger.py`)
- The credential health script exists and implements the five-state model correctly
- The task brief carries all the right rules (named fields, no everything-except, credential names from VARIABLES)

The infrastructure is ready. The report is not.

---

## Result Block

```
BRANCH: qwen-worker-7-r60
COMMIT: (this document)
DOES scripts/spend_report.py EXIST ON master: NO
  - Checked: git show master:scripts/spend_report.py → fatal: path does not exist
  - Checked: git log --all --oneline --diff-filter=A -- scripts/spend_report.py → (empty)
  - Checked: qwen-5 worktree → file not found
  - Checked: all branches → zero commits touch this file

PER-PROVIDER TABLE: Cannot be produced. The report does not exist.

PROVIDERS ESTIMATED FROM OUR SIDE AND PRESENTED AS PROVIDER FIGURES: N/A

BASELINE USED, AND IS IT STATED: N/A

FLAT FEES PRESENT / DOUBLE-COUNTED: N/A

REDACTION MECHANISM (quoted) AND THE NEGATIVE TEST RESULT:
  - No script exists, so no mechanism to quote
  - No test exists, so no negative test to run
  - The task brief carries the rule: "print named fields only, never everything-except"

INVENTED CREDENTIAL NAMES FOUND:
  - XAI_API_KEY and ZAI_API_KEY are used by provider adapters but not in config.VARIABLES
  - This is a discrepancy but not blocking for TASK-291 (the report does not exist)

STATES CONFLATED: N/A (no report to check)

THE 22,000-CREDIT GAP AS REPORTED: N/A (no report exists)
  - The underlying bug is FIXED: stage_s5_verify.py now passes rec=rec
  - The fix is TESTED: test_every_s5_verification_reaches_the_spend_ledger.py passes

TWO RUNS AGREE, YES/NO: N/A (script does not exist)

VERDICT: REWORK
  - TASK-278 was moved to REVIEW but the deliverables were never committed
  - There is no spend report, no script, and no test
  - The task brief exists and carries the right rules, but the work was not done

MAY TASK-282 PROCEED: NO
  - TASK-282 depends on TASK-278 and TASK-291
  - TASK-278 does not exist on master or any other branch
  - There is nothing to wire into the Monday report
```

---

## Recommendations

1. **Re-dispatch TASK-278** to a worker with explicit instructions to commit the deliverables.
2. **Add a guard** to the task workflow: a task cannot move to REVIEW unless its deliverables exist in git. The current state — a task in REVIEW with no deliverables — should not be possible.
3. **Resolve the credential name discrepancy:** either add `XAI_API_KEY` and `ZAI_API_KEY` to `config.VARIABLES`, or remove them from `credential_health.py`'s CHECKERS map.
4. **The 22,000-credit gap is fixed for future runs**, but the historical gap remains. A one-time reconciliation pass may be needed if the operator wants to know what was actually spent from 2026-09-16 to 2026-09-26.

---

## Files Changed

- `docs/SPEND-SECOND-PASS-2026-09-25.md` — this report (NEW)

## Files Not Changed (forbidden)

- `src/providers/*` — not touched
- `config/.env` — not touched
- `work/*` — not touched
- `src/spendledger.py` — not touched
- `scripts/spend_report.py` — does not exist, not created (that is TASK-278's job)
- `tests/test_spend_report.py` — does not exist, not created (that is TASK-278's job)
