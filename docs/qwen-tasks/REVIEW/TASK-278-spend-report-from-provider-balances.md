PRIORITY: P1
DEPENDS:

# TASK-278 — what we have actually spent, read from the providers

**Our ledger cannot answer this and that is the point of the task.**
`work/spend-ledger.jsonl` has not been written since 2026-09-16 and holds 79
deliverable and 97 reoon rows against 11,417 verification journal rows — some
22,000 credits with no ledger row, because `stage_s5_verify.py` calls
`verification.verify(...)` with no `rec` and every `spendledger.record` is
guarded by `if rec is not None`. So the figure must come from the PROVIDERS.

## Build `scripts/spend_report.py`

For each of **ContactOut, AI-ARK, Reoon, Deliverable, Apify, OpenRouter, xAI
and Z.ai**:

1. Read the account balance or usage endpoint **now**.
2. Compare against the earliest balance we have recorded — 2026-09-18, or the
   first row in the spend ledger, whichever is earlier. Say which you used.
3. State **credits used** and **USD at list price**, per provider.
4. Add the flat fees: **Claude Max** and **Apify Scale (199 USD prepaid)**.
5. **Where a provider exposes no balance or usage endpoint, SAY SO** and give
   the dashboard path for a person to read by hand. Do not estimate it from
   our side and present it as a provider figure.

Write `docs/SPEND-REPORT-2026-09-24.md`. The script must be re-runnable and is
wired into the Monday report.

## THE RULE THAT MATTERS MOST HERE

**NEVER PRINT A CREDENTIAL VALUE, AND NEVER PRINT A WHOLE RESPONSE.**

On 2026-09-24 a session read Apify's `/users/me`, filtered the output by hand
to hide email and user id, and printed the account's **proxy password** in
full — because it allow-listed what to HIDE instead of naming what to SHOW.
That is the same shape as the 2026-09-23 redaction defect and the same shape
as the `emptyrender` allowlist.

So: **print named fields only.** Never `for k in response`. Never "everything
except". If you need a field you did not anticipate, add it by name.

## THE OTHER RULE

**Credential names come from `config.VARIABLES`. Never guess one.** On
2026-09-20 a session invented four plausible variable names and reported four
providers as unauthenticated when all four were set and working.
`CONTACTOUT_KEY` does not exist. Run
`py -3 scripts/credential_health.py --verify`, which reads the registry and so
cannot invent a name, and keeps NOT_CONFIGURED / CONFIGURED_UNVERIFIED /
AUTHENTICATION_VERIFIED / AUTHENTICATION_FAILED / PROVIDER_UNAVAILABLE apart.
**A set variable is not an authenticated one, and a transport failure is not a
bad key.**

## Done when

- `scripts/spend_report.py` exists, runs, and prints nothing secret
- `docs/SPEND-REPORT-2026-09-24.md` carries a row per provider with credits
  used, USD at list, and the source of each figure
- providers with no endpoint are named as such, with the dashboard path
- a test asserts the report never emits a value from `config.VARIABLES`

Test command: `py -3 -m unittest tests.test_spend_report -v`

## Result block

    BRANCH:
    COMMIT:
    PROVIDERS WITH A LIVE BALANCE ENDPOINT:
    PROVIDERS WITH NONE (and the dashboard path):
    TOTAL USD AT LIST, 09-18 TO NOW:
    WHERE OUR LEDGER DISAGREES WITH THE PROVIDER:

---

## STATE RECORDED BY LANE E, 2026-09-24 late

    DELIVERED BY     qwen-5, 2026-09-24
    STATE            REVIEW (moved out of TODO/ tonight)
    ON MASTER        NO - `scripts/spend_report.py` does not exist on master.
                     Checked in this worktree at 24acaff, tip of master.
    NEXT             TASK-291 - second pass. Per provider: did the figure come
                     from the provider, from our ledger, or from arithmetic?

TASK-291 BLOCKS TASK-282, which wires the spend report into the Monday
report. Do not wire a report whose numbers have not been sourced: our ledger
holds 79 deliverable and 97 reoon rows against 11,417 verification journal
rows, so a ledger-sourced verification figure is wrong by roughly two orders
of magnitude and looks entirely plausible.

---

## REVIEW BLOCK — TASK-291, qwen-7, 2026-09-26

**VERDICT: REWORK — deliverables do not exist.**

None of the three required files were ever committed to any branch:

- `scripts/spend_report.py` — does not exist on master, qwen-worker, qwen-5,
  or any branch in git history. `git log --all --diff-filter=A` returns empty.
- `docs/SPEND-REPORT-2026-09-24.md` — does not exist anywhere.
- `tests/test_spend_report.py` — does not exist anywhere.

The state note says "DELIVERED BY qwen-5" but the work was never committed.
The TASK-278 commits (`2209c952`, `f792203a`) only contain the task brief.

**The underlying 22,000-credit gap bug IS fixed** — `stage_s5_verify.py`
line 647 now passes `rec=rec` to `verification.verify`, and
`tests/test_every_s5_verification_reaches_the_spend_ledger.py` verifies the
behaviour and passes. The ledger gap is closed for future runs.

**Credential name discrepancy found:** `XAI_API_KEY` and `ZAI_API_KEY` are
used by `src/providers/xai.py` and `src/providers/glm.py` respectively, but
neither is declared in `config.VARIABLES`. The credential_health CHECKERS
map references them but the registry does not. A spend report that follows
the rule "credential names come from config.VARIABLES" cannot check these
two providers at all.

**TASK-282 may NOT proceed.** Its dependency does not exist.

Full report: `docs/SPEND-SECOND-PASS-2026-09-25.md`.
