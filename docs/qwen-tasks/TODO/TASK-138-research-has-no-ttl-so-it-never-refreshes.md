PRIORITY: P1
DEPENDS:

# TASK-138 - research never refreshes, and the reason is one line

## THE DEFECT, MEASURED

`src/research.py`, `why()` opens with:

    if existing_evidence(rec): return None

**Once a record has ANY evidence row, research never runs on it again.** Not
stale evidence, not thin evidence, not one junk row - any row at all. There is
no TTL, no staleness comparison and no per-fact-type rule.

Measured on the estate 2026-09-15:

    research rows                      695 across 203 of 300 records
    age_days / published_at / confidence   NULL on all 695
    newest evidence                    3 days old
    oldest                             8 days old

Three days is tolerable for "this company builds software for agencies". It is
NOT tolerable for a hiring signal, a funding announcement or a launch, and the
signal layer reads exactly those.

## WHAT THIS TASK IS

Give evidence a SHELF LIFE THAT DEPENDS ON WHAT IT IS, and make `why()` consult
it. Not a global TTL - a global number is wrong for every fact at once.

The shape the repository already suggests:

    LONG-LIVED     positioning, core services, headquarters, categories
    SHORT-LIVED    hiring, job openings, announcements, launches, team changes,
                   recent initiatives

The classification must come from the evidence row's OWN `field`, which
`research.for_prompt` already reads and passes to the prompt. Do not add a new
parallel state for this - ask what already holds the truth.

## WHAT MUST BE TRUE WHEN YOU ARE DONE

1. A record whose evidence is all long-lived and 3 days old is NOT re-crawled.
2. A record carrying a hiring or announcement row older than that type's life
   IS re-crawled, and `why()` says which row aged out.
3. A record with no evidence behaves exactly as it does today.
4. `age_days` is COMPUTED from `retrieved_at` rather than read from the NULL
   column. A field nothing writes is not a source of truth - this repository
   has been bitten by exactly that (an evaluator reporting INSUFFICIENT_DATA
   forever because nothing wrote the field it read). If you make `age_days`
   meaningful, prove something reads it.
5. Refreshing REPLACES the aged rows for that field and keeps the rest. A
   refresh that drops good long-lived evidence to renew one hiring row has
   made the record worse.

## PROVE IT IS CONSUMED

`grep -rn "<your new name>" src/` must show a caller that is not the
definition, and the result block must carry that grep's output. Drive the test
through `research.why()` - the function production calls - not through the
classifier you write. Then DELETE the call from `why()` and re-run: if your
tests still pass, they prove nothing.

## COST

Re-crawling is not free. `src/webfetch.py` is the free leg and Apify is the
paid one. A TTL that makes the estate re-crawl every record every day has
replaced a correctness problem with a bill. State, in the result block, how
many of the 203 records with evidence would re-crawl TODAY under your rule and
why that number is the right one.

## FILES ALLOWED

    src/research.py
    tests/test_research*.py  (and one new test module if you need it)

## FILES FORBIDDEN

    src/providerwrites.py      src/heyreachfactory.py
    src/store.py               work/  (anything)
    config/clients/*.yaml

## DELIVERABLE

The rule, wired into `why()`, tests driven through `why()`, the counterfactual
(delete the call, watch the right test fail), the grep output, and the
re-crawl count with its reasoning.
