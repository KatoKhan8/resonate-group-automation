PRIORITY: P1
SIZE: S
DEPENDS: TASK-332

# TASK-352 - a spend report the operator can act on

**Operator instruction, 2026-09-26:** a spend report.

Depends on TASK-332, which stops `report()` summing cents, credits and microusd
into one printed number. **Do not start before 332 is on master** - a report
built on that sum would be wrong in the same way.

## What the operator actually needs, from this session's own questions

The fifty cost $3.1464. Three different true numbers came out of it, and the
handoff quoted one of them without saying which:

    per cohort lead (50)             6.29c
    per WRITTEN lead (31)           10.15c     <- what the handoff called "per lead"
    per lead passing BOTH gates (13) 24.20c    <- the one that matters

A report that prints one cost-per-lead without naming its denominator invites the
same confusion. **Print all three, labelled.**

## Build

    src/spendledger.py   READ - `report()`, `client_balance()`, `progress_block()`.
    scripts/spend_report.py   NEW
    tests/test_the_spend_report_never_sums_two_units.py   NEW

Per client and per day, report: spend per provider **in that provider's own
unit**, `usd_estimate` where a rate is established, and cost per lead on all
three denominators above.

## The rules

- **Never sum two units.** Where units differ, print them separately and emit
  `MIXED UNITS - a tripwire, not an amount`, the wording `client_balance` already
  uses.
- **Never invent a rate.** `USD_PER_UNIT["credits"]` is `None` because nobody has
  priced a credit. An unpriced provider reports `usd_estimate: null` and
  `rate_source: "unknown"`. A report that sums a made-up rate is the defect the
  unit table exists to prevent.
- **Say what is NOT counted.** Model rows currently carry `client="_model"`
  (TASK-346 fixes this) and there are `_model` rows already on disk that cannot be
  attributed. Report their count and total separately, as unattributed, rather
  than dropping or guessing them.

## Acceptance - RUN each, paste real output

1. The report runs against the real ledger and prints per-provider,
   per-unit figures:

    py -3 scripts/spend_report.py --client productive

2. **A mixed-unit client gets the tripwire, not a total.** Prove it with a
   fixture holding one `cents` row and one `credits` row, asserting no summed
   integer is printed.

3. All three cost-per-lead denominators appear, each labelled with its
   denominator. A bare "cost per lead" is a FAIL.

4. **An unpriced provider reports null, not zero and not a guess:**

    py -3 -c "import sys;sys.path.insert(0,'.');from src import spendledger as S;\
    u,rate,src=S.usd_estimate(500,'credits');\
    assert u is None and src=='unknown',(u,src);print('credits unpriced ->',u,src)"

5. Unattributed `_model` rows reported separately, with a count.

6. Read-only: assert the ledger is byte-identical before and after.

## What this task may NOT do

- Do not write to the ledger, backfill, or rewrite a historical row.
- Do not invent a credit rate. Do not sum across units.
- No provider call, no model call. Nothing sent, nothing activated.
