PRIORITY: P1
SIZE: S
DEPENDS:

# TASK-9802 — two modules compute `today` at import time, and nothing stops a third

## The blocker, measured 2026-10-13

`scripts/clockscan.py` scanned the whole of `src/` and returned 44 clock reads:

    {"unpatched": 14, "injectable": 22, "helper_body": 4, "module_level": 2, "indirect": 2}

The two `MODULE_LEVEL` rows are the ones that cannot be injected at all:

    src/demo.py         :20   TODAY = datetime.date.today().isoformat()
    src/secondbrain.py  :32   TODAY = datetime.date.today().isoformat()

A module-level date is bound ONCE, when the module is first imported, and every
later read returns that same value. In a simulated run that advances a business
clock, those two constants do not advance with it — and a long-lived process
reading `TODAY` is reading the day it started, not the day it is.

This is the same shape as the standing finding that a merge is not a deploy:
~15 loops import at start and never reload.

**Restricted to `SIMULATED_PATH_MODULES` the scanner returns 2 rows and both
are INJECTABLE** (`senderheadroom.freshness`, `senderheadroom.earliest_day`), so
neither of these two modules is on the simulated path today. That is why this is
P1 and not P0 — and it is still a blocker, because nothing prevents a module
that IS on that path from acquiring an import-time date tomorrow.

## What to do

1. Make `demo.py` and `secondbrain.py` read the date when they are USED, not
   when they are imported. Follow the precedent already in this tree:
   `clientreport.today()`, `executionguard._utcnow()` and `sqlitestore._now()`
   are all HELPER_BODY — a function that returns the value — which the scanner
   already disposes of as acceptable.
2. Keep the public name working. If anything reads `demo.TODAY`, it must keep
   working, so prefer a module-level `__getattr__` or a `today()` function plus
   a call-site change — whichever is the smaller diff. Say which you chose.

    FORBIDDEN: src/providers/*  config/  work/*.jsonl
               scripts/clockscan.py  (it is a measuring tool, not a seam — do
               not edit the scanner to make the finding go away)

## Acceptance — RUN each, paste the real output

1. **The scanner reports zero MODULE_LEVEL rows:**

       py -3 scripts/clockscan.py --json | py -3 -c \
         "import json,sys;d=json.load(sys.stdin);print(d['dispositions'])"

   `module_level` must be absent or 0. Paste the whole disposition dict before
   and after, and confirm no other disposition got WORSE — in particular that
   `unpatched` did not grow.

2. **A test that FAILS when a module-level date is reintroduced.** Add a test
   that runs the scanner and asserts `module_level == 0`. Then prove it can go
   red: add `TODAY = datetime.date.today()` at module level in any file under
   `src/`, run the test, paste the FAILING output, remove it, and paste the
   passing run. A gate that cannot fail is not a gate.

3. **The value actually advances.** A test that patches the clock forward and
   asserts the value read from each of the two modules changes with it. With
   the old import-time constant this test must fail; show that it does, by
   reverting your change in a scratch copy if necessary.

4. **No behaviour change elsewhere:** run the modules' own tests plus anything
   importing them, and report zero new failures by test NAME, diffed both
   directions against the baseline. Name the baseline commit you diffed against.

## Report

The disposition dict before and after, the exact lines changed, and the three
test outputs — passing, deliberately-broken-and-failing, passing again.
