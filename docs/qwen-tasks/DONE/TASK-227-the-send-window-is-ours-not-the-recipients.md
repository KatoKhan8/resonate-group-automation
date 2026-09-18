# TASK-227: The send window is ours, not the recipient's

## Problem

EmailBison campaign 487 sends on a 09:00-17:00 Europe/Zagreb window to
recipients who are not in Zagreb. 09:00 Zagreb is 03:00 US Eastern.
`bison.set_schedule` already takes a timezone; nothing computes which one
a cohort should get.

## Task

Build a PURE READ-ONLY function that proposes a cohort send window from the
recipients. Classify every recipient RESOLVED (with evidence), AMBIGUOUS, or
UNKNOWN. When too few resolve, return NO PROPOSAL with the reason so the
caller falls back to the existing production default.

## Rules

- MISSING EVIDENCE IS NEVER POSITIVE EVIDENCE
- A GUESSED TIMEZONE IS WORSE THAN A MISSING ONE
- No provider write, no canonical write, no credit spend
- Do not change any existing campaign's schedule

## Tests required

1. A country that spans several timezones, known only as a country, must
   return UNKNOWN/AMBIGUOUS and must NOT return a timezone
2. A single-region cohort proposing that region's window
3. A three-continent cohort returning NO PROPOSAL

## RESULT BLOCK

**STATUS:** DONE

**COMMIT SHA:** 9c126097

**TESTS:** 24 new tests in `tests/test_cohort_window.py`, all passing.
27 existing `test_geo_iso` tests still passing. One pre-existing invariant
failure (`test_emailbison_posts_only_to_routes_it_declares`) confirmed
unrelated to this change.

**FILES CHANGED:**
- `src/geo.py` — added `propose_cohort_window()`, `_classify_recipient()`,
  `RESOLVED`, `AMBIGUOUS` constants
- `tests/test_cohort_window.py` — new test file, 24 tests

**FINDINGS:**
- `propose_cohort_window` is defined in `src/geo.py` and consumed by 15 test
  calls in `tests/test_cohort_window.py`. The wiring to campaign scheduling
  is Claude's: the task explicitly says "no provider write, no canonical
  write, do not change any existing campaign's schedule".
- Multi-timezone countries (US, CA, AU) are classified AMBIGUOUS (not
  UNKNOWN, not RESOLVED) — we know the country but cannot pick a zone
  without state/city evidence.
- The function returns NO PROPOSAL with a machine-readable reason in every
  case where a coherent window cannot be determined: too few resolved,
  multiple timezones, no recipients, no location evidence.

**RISKS:**
- The function is a building block. It proposes but does not apply. Claude
  must wire it into campaign scheduling before it affects any send.
- `min_resolved` defaults to 3. If a cohort has fewer than 3 members, the
  caller must lower the threshold explicitly.

**RECOMMENDED CLAUDE ACTION:**
Wire `propose_cohort_window` into the campaign scheduling path so that when
a cohort is assembled, the function is called to propose a timezone before
`bison.set_schedule` is invoked. The function is pure read-only and safe to
call at any point.
