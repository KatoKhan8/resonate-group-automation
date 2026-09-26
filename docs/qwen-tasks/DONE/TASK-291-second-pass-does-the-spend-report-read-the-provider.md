PRIORITY: P1
DEPENDS:

# TASK-291 — second pass: does the spend report read the provider, or read us?

> **DISPATCH NOTE.** Reviews TASK-278 (delivered by qwen-5, now in `REVIEW/`,
> NOT on master). **This task BLOCKS TASK-282** — the Monday wiring waits on
> this verdict. Dispatchable now; do not give it to qwen-5, which wrote it.

## The question this answers

**Every figure in `docs/SPEND-REPORT-2026-09-24.md`: did it come from the
provider, from our ledger, or from arithmetic?**

The whole point of TASK-278 was that **our ledger cannot answer this**.
`work/spend-ledger.jsonl` has not been written since 2026-09-16 and holds 79
deliverable and 97 reoon rows against **11,417 verification journal rows** —
some 22,000 credits with no ledger row, because `stage_s5_verify.py` calls
`verification.verify(...)` with no `rec` and every `spendledger.record` is
guarded by `if rec is not None`.

So a report that is right in form and sourced from that ledger is wrong by
roughly two orders of magnitude on verification alone, and it will look
entirely plausible.

`scripts/spend_report.py` **does not exist on master.** Verify that for
yourself before you begin; it tells you which tree you are reading.

## What to check, per provider

ContactOut, AI-ARK, Reoon, Deliverable, Apify, OpenRouter, xAI, Z.ai.

1. **Source of the figure**, one of: a live balance/usage endpoint (name the
   endpoint and the field), our ledger, a price-page multiplication, or none.
2. **Providers with no endpoint** must be NAMED as such with a dashboard path
   for a person to read by hand. A provider estimated from our side and
   presented as a provider figure is the defect. Check every row for it.
3. **The baseline.** The comparison is against the earliest balance we have —
   2026-09-18, or the first ledger row, whichever is earlier. Which did it
   use, and is that stated in the report?
4. **The flat fees**: Claude Max, and Apify Scale at 199 USD prepaid. Present
   and not double-counted against metered Apify usage?
5. **Secrets.** Run the script and read every line of output. Does it print
   NAMED FIELDS ONLY? A `for k in response`, a "everything except" filter, or
   any whole-response dump is a fail even if today's response happens to be
   harmless. On 2026-09-24 a session filtered Apify's `/users/me` by hand to
   hide email and user id and printed the account's **proxy password** in full,
   because it allow-listed what to HIDE instead of naming what to SHOW.
6. **Credential names.** Do they come from `config.VARIABLES`, or were any
   invented? On 2026-09-20 four plausible names were invented and four working
   providers were reported unauthenticated. `CONTACTOUT_KEY` does not exist.
   Cross-check against `py -3 scripts/credential_health.py --verify`.
7. **The four states are kept apart**: NOT_CONFIGURED / CONFIGURED_UNVERIFIED
   / AUTHENTICATION_VERIFIED / AUTHENTICATION_FAILED / PROVIDER_UNAVAILABLE.
   **A set variable is not an authenticated one, and a transport failure is
   not a bad key.** Does the report conflate any of them?
8. **The ledger disagreement is the finding, not an error to smooth over.**
   Does the report state, per provider, where our ledger disagrees with the
   provider and by how much? The 22,000 unrecorded verification credits must
   appear.
9. **Re-runnable.** Run it twice. Same figures, or a stated reason they moved.

## The acceptance bar

- A per-provider table: figure, source, endpoint+field or dashboard path,
  ledger figure, delta.
- Confirmation by inspection that no output line can contain a credential
  value, with the mechanism ("named fields only", quoted from the code).
- The test asserting the report never emits a value from `config.VARIABLES`
  exists, and **removing the redaction makes it fail.** Self-test the filter
  against every value — one IPv4 leaked once because it was checked after.
- The 22,000-credit gap appears with a number.
- A verdict: ACCEPT / ACCEPT WITH CHANGES NAMED / REWORK, and an explicit
  yes/no on whether TASK-282 may proceed.

## What evidence counts

- The script's real output from a live run (redacted output is fine; a
  redacted-by-you-afterwards output is not — the script must redact).
- `py -3 scripts/spend_report.py` run twice, both outputs.
- `credential_health.py --verify` output beside the report's own claims.
- The negative test: remove the redaction, show the test failing.

## WHAT WOULD MAKE THIS A FALSE PASS

- **Reading the report and believing it.** The report is the claim under test.
- **A green `tests.test_spend_report`.** Fixtures will carry whatever the
  author put in them, and the buggy thing here is the source of a number, not
  its formatting. Run it against the providers.
- **Accepting a ledger-sourced figure as a provider figure** because the
  report does not say which it is. If it does not say, that is the finding.
- **Checking redaction after the first command.** Redact before, and self-test
  the filter against every value in `config.VARIABLES`.
- **Treating PROVIDER_UNAVAILABLE as AUTHENTICATION_FAILED**, or a set
  variable as a verified one.
- A "total USD" with no denominator of providers actually read.

## Boundaries

- Reads only. Balance and usage endpoints are reads; nothing here spends
  beyond the read itself.
- Never print a credential value or a whole response.
- Do not edit `src/providers/*`. If a provider adapter needs a balance call it
  does not have, that is a FINDING and a new task.

## Files

    ALLOWED    docs/SPEND-SECOND-PASS-2026-09-25.md,
               docs/qwen-tasks/REVIEW/TASK-278-spend-report-from-provider-balances.md
               (append a REVIEW block),
               tests/test_spend_report.py (additional negative tests only)
    FORBIDDEN  src/providers/*, config/.env, work/*, src/spendledger.py

## Result block

    BRANCH: qwen-worker-7-r60
    COMMIT: (pending)
    DOES scripts/spend_report.py EXIST ON master (yes/no, how you checked):
      NO. Three checks:
      1. git show master:scripts/spend_report.py → fatal: path does not exist
      2. git log --all --oneline --diff-filter=A -- scripts/spend_report.py → (empty)
      3. Checked qwen-5 worktree (C:/Users/Zvonimir/Desktop/resonate-qwen-5/) → not found
      The file has never been committed to any branch in git history.
    PER-PROVIDER TABLE: Cannot be produced. The report does not exist.
    PROVIDERS ESTIMATED FROM OUR SIDE AND PRESENTED AS PROVIDER FIGURES: N/A
    BASELINE USED, AND IS IT STATED: N/A
    FLAT FEES PRESENT / DOUBLE-COUNTED: N/A
    REDACTION MECHANISM (quoted) AND THE NEGATIVE TEST RESULT:
      No script exists, so no mechanism to quote and no test to run.
      The task brief carries the rule: "print named fields only, never
      everything-except" but there is no implementation to verify.
    INVENTED CREDENTIAL NAMES FOUND:
      XAI_API_KEY and ZAI_API_KEY are used by src/providers/xai.py (line 32)
      and src/providers/glm.py (line 69) respectively, but neither is declared
      in config.VARIABLES. The credential_health.py CHECKERS map references
      them but the central registry does not. A spend report following the
      rule "credential names come from config.VARIABLES" cannot check these
      two providers.
    STATES CONFLATED: N/A (no report to check)
    THE 22,000-CREDIT GAP AS REPORTED: N/A (no report exists)
      The underlying bug IS FIXED: stage_s5_verify.py line 647 now passes
      rec=rec to verification.verify. The fix is tested by
      tests/test_every_s5_verification_reaches_the_spend_ledger.py which
      passes. The ledger gap is closed for future runs.
    TWO RUNS AGREE, YES/NO: N/A (script does not exist)
    VERDICT: REWORK
      TASK-278 was moved to REVIEW with a note saying "DELIVERED BY qwen-5"
      but none of the three deliverables (script, report, test) were ever
      committed to any branch. The task brief exists and carries the right
      rules, but the work was not done. There is nothing to review.
    MAY TASK-282 PROCEED: NO
      TASK-282 depends on TASK-278 and TASK-291. TASK-278 does not exist on
      master or any other branch. There is nothing to wire into the Monday
      report.
