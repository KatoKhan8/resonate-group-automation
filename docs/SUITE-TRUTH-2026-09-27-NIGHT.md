# The suite, measured with the project's own tool — 2026-09-27 night

**Why this document exists:** three parties measured the suite tonight and
reported **126**, **128** and **197** distinct failing names for essentially the
same tree. One of them concluded from its number that the standing baseline
"under-reports master by 75 names" and that somebody must regenerate it. **Acting
on that conclusion would have adopted a ~197-name baseline, which is exactly the
`TASK-372` mistake the operator rejected earlier the same day** — normalising
caught regressions by promoting them into the baseline. So the number had to be
settled before anyone edited `docs/state/SUITE-BASELINE-2026-09-26.txt`.

## THE MEASUREMENT

Taken with `scripts/suite_baseline.py --measure` — **the same tool and the same
harness that produced the committed baseline**, which is the whole point. Tree:
`0a4c9317` = master `4bff3a7a` + `TASK-426`.

    runner              py -3 -m tests.offline
    tests_run           13,114
    failures 101        errors 27
    distinct names      128 (full)   120 (standalone)
    order-dependent     8            only-standalone   0

**128 in full mode. The committed baseline is 128.** The 197 figure is not
reproducible with this tool and must have come from a different harness. **Two
harnesses exist here and are NOT comparable** — one process via `tests.offline`
versus each module in its own process — and `suite_baseline.py` exists precisely
because they answer different questions. A number measured one way and compared
against a baseline measured the other way is not evidence of drift.

## AND THE COUNT WAS STILL THE WRONG QUESTION

128 measured against a 128-name baseline, and the sets are **not** the same:
**7 new names and 7 cleared.** Two identical counts hiding fourteen differences
is the exact failure this repository already paid for once, and it is why the
baseline is a LIST:

> "`74 failures` and `74 failures` compare equal while a different 74 tests
> fail." — `scripts/suite_baseline.py`

### The 7 new names, diagnosed rather than counted

**FOUR are real in both modes, and all four are a TEST CONTRADICTING A RECORDED
OPERATOR DECISION.** Independently verified as pre-existing at base `1f4d464c`
by two separate parties tonight, so **none is a regression from `TASK-426`.**
They are **gaps in the committed baseline — it is short by 4 names, not 75.**

1. `test_an_offer_cannot_be_invented::test_approval_status_is_not_defaulted_to_approved`
   asserts that **no** offer carries `approval_status: approved`. It now fails on
   `OFFER-A-ECONOMIC-BUYER` — because **the operator approved A and B on
   2026-09-27**, with `approved_by`, `approved_on` and `approved_at_sha`
   recorded. The test's stated intent is "production does not approve its own
   offers"; what it actually asserts is that nothing is ever approved, which
   forbids the operator's own decision. The intent is right and the assertion is
   wrong. `TASK-448`.
2. `test_fixture_hygiene::test_no_real_client_prospect_or_roster_domain` and
3. `test_fixture_hygiene::test_every_email_address_is_on_a_reserved_domain`
   fail on **`productive.io`** appearing in tracked files — including
   `src/copylint.py` and several docs. **This is not a PII leak, and that was
   checked rather than assumed:** `productive.io` is the CLIENT's own public
   domain and the single approved CTA (`https://productive.io/get-started/`,
   operator-approved, 2026-09-26). The test cannot currently tell the client's
   own public domain apart from a prospect or roster domain. `TASK-448`.
4. `test_the_cadence_reacts_to_what_the_prospect_did::test_the_meeting_reaches_the_send_gate_too`
   — the sibling test in that module IS a baseline name; this one is not.
   `TASK-448`.

**THREE are ORDER-DEPENDENT** — they fail in the full run and PASS standalone,
confirmed both by the tool's own `order_dependent` set and by running them
directly on master, where they pass:

    test_a_dead_cta_link_is_refused.GuardFailureTests.test_removing_allowlist_check_lets_dead_link_through
    test_a_dead_cta_link_is_refused.ProductionPathTests.test_allowlisted_url_passes_through_check_batch
    test_no_test_leaves_the_environment_changed...test_no_module_left_a_variable_set

**These are NOT dismissed as flakes.** CLAUDE.md: "An intermittent failure is
diagnosed - alone, as a class, and in an isolated full run - never dismissed."
`TASK-449`. Note the third one's own output says the honest thing about itself:
*"no leaks recorded. If this was not a full suite run, that is a pass about
nothing"* — it is only meaningful in a discovered run, so its standalone pass
proves nothing either way.

### The 7 cleared names

Five in `test_a_resume_leaves_a_ledger_row`, plus
`test_nothing_writes_to_a_provider::test_every_http_write_in_the_repository_is_declared`
and `test_secrets::test_every_classified_variable_is_in_the_example` — the last
of which the integration pass fixed deliberately tonight by adding three
classified variables to `config/.env.example`.

## WHAT THIS MEANS, AND WHAT MUST NOT HAPPEN

1. **`TASK-426` introduced ZERO new failing names.** Measured by its author,
   reproduced name-for-name by an independent reviewer, and consistent with this
   measurement once the four baseline gaps are accounted for.
2. **DO NOT regenerate the baseline at ~197 names.** That conclusion rests on a
   cross-harness comparison. The baseline's real defect is small and specific:
   **it is missing 4 names**, each verified pre-existing.
3. **DO NOT fix the four by deleting or weakening their assertions**, and do not
   whitelist the offers or the domain. Each must assert the invariant actually in
   force — an approved offer carries named human attribution and provenance; the
   client's own public domain is not a prospect domain. Never delete a legitimate
   test for green CI, and a safety test failing because production violates the
   contract is evidence.
4. The baseline is **not** re-measured or replaced tonight. It is a standing
   reference point and changing it during a critical-path night is how a
   regression becomes invisible. Fix the four tests, diagnose the three, then
   re-measure at a named SHA in daylight.

## PROVENANCE

Measured at `0a4c9317` by `scripts/suite_baseline.py --measure`, 2026-09-27,
~2h10m wall clock, on win32 / Python 3.14.3. The comparison against the
committed baseline required normalising the `FAIL `/`ERROR ` prefixes the
baseline file carries — **my own first diff reported "128 new and 128 cleared"
because I compared prefixed strings against bare test names.** That artifact is
recorded here because it is the same trap in miniature: a diff is only evidence
once both sides are shaped the same way.
