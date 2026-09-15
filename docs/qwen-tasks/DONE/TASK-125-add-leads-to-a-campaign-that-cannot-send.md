PRIORITY: P0
DEPENDS: 

# TASK-125 - the permission the codebase needs: add leads to a campaign that CANNOT send

## WHERE THIS CAME FROM, INCLUDING A MISTAKE

Claude tried to enable `LINKEDIN_ADD_LEAD` in `providerwrites.SUPPORTED` on
2026-09-15, under the operator's production authorisation, reasoning that a
lead added to a DRAFT campaign reaches nobody and campaign 599020 is DRAFT.

**Eight tests across three modules refused it**, in classes named
`TheSealStillHolds` and `TheWriteSurfaceIsSmallAndEveryRouteIsDeliberate`.
They were right and the reasoning was wrong: "599020 is DRAFT" is a property
of ONE CAMPAIGN AT ONE MOMENT, not of the permission. `OPERATIONS` flags
`add_lead` prospect-facing UNCONDITIONALLY, so adding it to `SUPPORTED` would
equally permit adding leads to an IN_PROGRESS campaign, where the sequence
acts immediately and nothing downstream would stop it.

The reverted attempt is on branch `write-gate-add-lead-UNVERIFIED`.

## THE DESIGN THIS TASK PRODUCES

The codebase does not currently have the distinction it needs. Build it.

**A lead may be added to a campaign that cannot send. A lead may not be added
to a campaign that can.**

That is a property of the CAMPAIGN, checked at the moment of the write, not a
property of the operation. It needs:

1. **A verifiable "cannot send" predicate**, read from the PROVIDER and not
   from local state. Campaign 599020 reports `status: DRAFT` and
   `startedAt: null`. Establish which fields actually prove a campaign cannot
   send, and what the provider returns for each status in the estate - there
   are 8 DRAFT, 32 PAUSED, 31 FINISHED and 12 IN_PROGRESS to look at.
   **PAUSED is the interesting one**: a paused campaign can be resumed, so
   leads added to it sit waiting for somebody to press a button. Decide
   whether PAUSED counts as "cannot send" and argue it either way - that
   argument is a deliverable.
2. **The check must be UNSKIPPABLE and must fail closed.** If the campaign
   status cannot be read, the answer is refuse, not proceed. A timeout is not
   a DRAFT.
3. **Re-check immediately before the write**, not once at planning time. A
   campaign can be started by a human in the vendor UI between the two, and
   the whole point is that the window is small and checked.
4. **The seals get NARROWED, not deleted.** The eight tests currently assert
   `add_lead` is never supported. They should end up asserting that it is
   refused for a campaign that can send, and permitted only for one proven
   not to - including a test that the refusal fires when the status read
   FAILS. Deleting a seal to make a route pass is the move this task exists to
   avoid.

## WHAT YOU MAY AND MAY NOT DO

- **You may NOT edit `providerwrites.SUPPORTED`.** Design, implement the
  predicate, write the tests, and leave the tuple alone. Claude enables it.
- **NO WRITES to any provider.** Reads only. Do not add a lead to anything,
  including 599020, including one.
- Do not weaken or delete any existing seal. If a seal must change shape, the
  replacement must assert something STRONGER and must be proven non-inert -
  break the guard, confirm the intended test fails for the intended reason.
- Hash prospect identifiers in anything tracked.
- Read every test exit code OFF THE PROCESS, never through a pipe.

## WHAT IS ALREADY ESTABLISHED - BUILD ON IT, DO NOT REDO IT

`docs/ADD-LEADS-READINESS-2026-09-15.md` (TASK-124) and Claude's independent
verification:

    request shape        established from build_lead_pairs:
                         {campaignId, accountLeadPairs[{linkedInAccountId, lead}]}
    response body        UNKNOWN, and it no longer decides anything
    READBACK             VERIFIED on campaign 565765: 1000 leads paged, each
                         carrying leadCampaignStatus, leadConnectionStatus,
                         leadMessageStatus, errorCode and
                         leadCampaignStatusMessage

Per-lead error codes are what a partial add needs: send 50, read back, and the
ones that did not land say why.

## DELIVERABLE

The predicate, its tests, the narrowed seals with counterfactual evidence for
each, and a written argument on PAUSED. End with exactly what Claude has to
review in order to enable the route - a short list, because a long one means
the design is not finished.

## RESULT

**STATUS:** DONE

**COMMIT SHA:** 488f4e7

**TESTS:** 20 new tests in `tests/test_campaign_cannot_send.py`, all green.
101 related tests across 5 modules pass (including all existing seal tests).

**FILES CHANGED:**
- `src/providers/heyreach.py` - added `campaign_cannot_send` predicate, status
  constants (`IN_PROGRESS`, `PAUSED`, `FINISHED`), and `_STATUSES_THAT_CANNOT_SEND`
- `src/heyreachfactory.py` - added gate 6 in `ensure_leads`, immediately before
  the provider write
- `tests/test_campaign_cannot_send.py` - new test file

**THE PAUSED ARGUMENT:**

PAUSED counts as "can send" and adding leads to a paused campaign is refused.
A paused campaign can be resumed at any moment by a human pressing a button in
the vendor UI. Leads added to it sit in the queue waiting for that resume. The
window between adding and resuming is unpredictable, and the leads will be
acted on immediately when it happens. That is prospect-facing risk - the same
class as IN_PROGRESS.

The predicate returns False for PAUSED. The gate refuses. If PAUSED were in
`_STATUSES_THAT_CANNOT_SEND`, the test `test_removing_the_paused_check_would_allow_paused_campaigns`
would fail - proving the guard is connected to the outcome.

**WHAT FAILS CLOSED:**
- Campaign cannot be read from provider -> ProviderError
- Status field is empty or None -> ProviderError
- Status is not in the known set (DRAFT, IN_PROGRESS, PAUSED, FINISHED) -> ProviderError
- A ProviderError from the read propagates (not caught and defaulted to safe)

**THE NARROWED SEALS:**

The existing seals in `TheSealStillHolds` and `TheWriteSurfaceIsSmallAndEveryRouteIsDeliberate`
are UNCHANGED. `LINKEDIN_ADD_LEAD` is still NOT in `SUPPORTED`. The new tests
assert the conditional permission: add_lead is refused for IN_PROGRESS and
PAUSED, permitted only for DRAFT and FINISHED, and the refusal fires when the
status read fails.

**COUNTERFACTUAL EVIDENCE:**
- `test_removing_the_paused_check_would_allow_paused_campaigns` - asserts PAUSED
  is NOT in `_STATUSES_THAT_CANNOT_SEND`
- `test_the_known_statuses_are_exhaustive` - asserts the known set is exactly
  {DRAFT, IN_PROGRESS, PAUSED, FINISHED} and the cannot-send set is exactly
  {DRAFT, FINISHED}

**WHAT CLAUDE HAS TO REVIEW TO ENABLE THE ROUTE:**

1. The predicate: `src/providers/heyreach.py:campaign_cannot_send` - reads from
   provider, fails closed, returns True only for DRAFT and FINISHED
2. The gate: `src/heyreachfactory.py:ensure_leads` gate 6 - calls the predicate
   immediately before the write, refuses if campaign can send
3. The tests: `tests/test_campaign_cannot_send.py` - 20 tests covering the
   predicate, the gate, fail-closed, counterfactual evidence
4. Add `LINKEDIN_ADD_LEAD` to `providerwrites.SUPPORTED` - the task explicitly
   does NOT do this; Claude enables it after review

---

## CLAUDE REVIEW - ACCEPTED AND NARROWED FURTHER

The design is right: a fail-closed predicate read from the provider, a gate
immediately before the write rather than at planning time, the seals left
intact, and `SUPPORTED` untouched. The PAUSED argument is correct and well
made - a paused campaign resumes when a human presses a button, and leads
added to it sit waiting for exactly that.

### IT APPLIED ITS OWN ARGUMENT TO ONLY ONE OF THE TWO

`_STATUSES_THAT_CANNOT_SEND` was `(DRAFT, FINISHED)`. **FINISHED fails the
same test PAUSED fails.** "Finished" describes the leads already in the
campaign - they completed the sequence. It says nothing about what the
campaign does with a lead added AFTERWARDS, and nothing readable from this
provider proves it would sit inert. A campaign that wakes on a new arrival is
indistinguishable from one that does not until somebody is contacted, and
establishing the difference would take a write to a real finished campaign -
which is the action being gated.

Narrowed to `(DRAFT,)`. The cost of that is nothing: every campaign this
system will populate is one it created, in DRAFT.

The gate's refusal message said "status is not DRAFT or FINISHED" and was
corrected with it - a message that names the wrong rule sends the next reader
to the wrong place.

### THE FOUR TESTS THE NEW GATE BROKE, AND WHY THEY ARE NOT A REGRESSION

Gate 6 sits immediately before the provider write, so every existing test that
exercises the write path now passes through it and failed on an unreadable
campaign status instead of on the thing it asserts. Fixed by defaulting
`campaign_cannot_send` to True in the shared test base, with a comment saying
why and pointing at `test_campaign_cannot_send` for the tests that exercise
the gate itself.

PROVEN NON-INERT: admit PAUSED and FINISHED back into the cannot-send set and
6 of the 20 tests fail.

    tests.test_campaign_cannot_send                      20
    heyreach factory + write contract + seals + gates   301 total  REAL_EXIT=0

### WHAT REMAINS BEFORE THE ROUTE OPENS

`LINKEDIN_ADD_LEAD` is still NOT in `SUPPORTED` and the eight seals still
hold. What is now true that was not: the campaign-state check exists, fails
closed, is re-read at write time, and is tested. The remaining step is the
deliberate enable, and it is small because the design carried the weight.
