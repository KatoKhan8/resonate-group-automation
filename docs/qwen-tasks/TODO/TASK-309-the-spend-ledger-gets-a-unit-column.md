PRIORITY: P0
SIZE: M
DEPENDS:

# TASK-309 — the spend ledger gets a unit column, before anything writes dollars

**Operator decision, 2026-09-25: every row carries `provider`, its native unit
(`credits` / `cents` / `usd`) and a `usd_estimate`. Reports sum ONLY
`usd_estimate`. Existing rows are backfilled by provider.**

**This lands BEFORE the first Sonnet call writes a row** (TASK-308). That
ordering is the operator's and it is the point: once dollars are in an
undeclared column, the ambiguity is permanent and the backfill becomes
guesswork about which rows were which.

## The defect this closes, measured

`researchpack/actors.py` writes Apify costs in **integer cents** into the same
column where Deliverable and Reoon write **credits**. A spend report summed
18,809 / 14,365 / 31,191 across both as though they were one quantity. They
were not. The number was wrong and nothing in the ledger could have said so.

Dollars from the Anthropic API would be a **third** unit in that column.

## What to build

1. **`unit` on every row**, one of `credits`, `cents`, `usd`. Required on new
   writes. A write with no unit is REFUSED, not defaulted - a default is how
   the next unit arrives silently.
2. **`usd_estimate` on every row**, a float. For `usd` rows it is the amount.
   For the others it is the amount converted at a rate you record ON THE ROW
   (`rate` and `rate_source`), so a report can be re-derived and a wrong rate
   can be corrected later rather than being baked in.
3. **Reports sum `usd_estimate` and nothing else.** Find every summing caller
   - `spendledger`, the spend report, the PROGRESS block, `scripts/task151_*`,
   TASK-278/291's report - and make them read that field. A caller still
   summing the raw amount is the bug surviving the fix.
4. **Backfill by provider.** Each existing row gets the unit its provider was
   writing at the time. Do not guess per row: establish it per provider from
   the code that wrote it, and say in your report which provider you assigned
   which unit and on what evidence.

## The conversion rates are the operator's, not yours

Credits are not dollars and the rate differs per provider and per plan. **Do
not invent one.** Where you cannot establish a rate from a provider's own
billing page or the operator's stated numbers, write `usd_estimate: null` with
`rate_source: "unknown"` and list those providers in your report for the
operator to price. **A null is honest and a made-up rate is not**, and a report
that sums a fabricated conversion is exactly the failure this task exists to
end.

## Acceptance, in one command

    py -3 -c "import sys;sys.path.insert(0,'.');from src import spendledger as s;\
    rows=s.load();bad=[r for r in rows if not r.get('unit')];\
    print(len(rows),'rows,',len(bad),'without a unit');assert not bad"

plus: a new write with no `unit` must RAISE. Prove that with a test that fails
when the refusal is removed, not merely one that passes today.

## What would make this a FALSE PASS

- A default unit. The whole defect is a column whose meaning was assumed.
- Backfilling `usd_estimate` with an invented conversion rate.
- Adding the column while a report still sums the raw amount.
- Reporting "all rows have units" when the backfill wrote the same unit for
  every provider without checking which one each was actually writing.

## ADDED 2026-09-25 — read this before you touch spendledger.py

**The per-provider-ceilings lane holds 13 commits on this file and has already
built the `unit=` seam** through `record` / `reserve` / `settle`, plus
`row_unit()` and `units_seen()`. It is deliberately NOT defaulted: a writer
that passes nothing leaves its row byte-for-byte unchanged, and the absence is
read as the provider's convention.

**Do not rewrite this file from a pre-merge read.** That lane deleted its own
cross-process `store.lock` exactly that way and only a test on master caught
it. Read the current file first. Where the seam exists, build on it; your work
is `usd_estimate`, the backfill, and making every report sum that field.

**THE TRUNCATION TRAP, which changes what the backfill must do.**
`record()` does `int(expected_cost or 0)`. Measured against the Sonnet price:

    one lead     $0.00256  -> int() -> 0
    50 leads     $0.128    -> int() -> 0

So a dollar-denominated provider cannot store its native amount in that column
at all. `usd_estimate` must therefore be a **float**, and any integer column
holding dollars must hold micro-dollars. A backfill that writes
`usd_estimate` as an int silently zeroes every sub-dollar row — which is the
same defect as the one this task exists to fix, one column to the left.
