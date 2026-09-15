PRIORITY: P0
DEPENDS: 

# TASK-132 - establish the campaign-building writes, so enabling them is evidenced

## WHY NOW

Provider execution needs five routes and none is enabled:

    heyreach.create_campaign   NOT prospect-facing
    heyreach.create_list       NOT prospect-facing
    heyreach.assign_sender     NOT prospect-facing
    heyreach.add_lead          PROSPECT-FACING   (TASK-125 built its gate)
    heyreach.activate          PROSPECT-FACING

The first three reach nobody: an empty draft campaign, an empty list, and a
sender attached to a campaign holding no leads cannot contact anyone. That is
exactly the argument that took `heyreach.set_sequence` out of the seal on
2026-09-14, and the seal's own comment says so - it records that the test "is
really about" `add_lead` and `activate`.

**This task does NOT enable anything.** It removes the unknowns so that
enabling is a reviewed decision on evidence, the way TASK-124 did for
add-leads. Claude enables.

## THE STANDARD, FROM providerwrites ITSELF

> An endpoint counts as established only when the provider documented it, or
> the existing code already carries its confirmed shape, or **a real response
> has been read**.

## WHAT TO ESTABLISH, PER ROUTE - READS ONLY

**1. `create_campaign` and `create_list`.** Their `OPERATIONS` entries say
*"no documented route; the list was created by hand in the vendor UI"* and
*"no documented route ... nothing suggests a create verb exists"*. **Both are
stale.** `/campaign/Create` and `/list/CreateEmptyList` are on
`heyreach.WRITE_ROUTES`, and campaign 599020 and list 933603 were created one
second apart on 2026-09-13 at 10:33:36-37Z, which is not a human in a UI.

Establish what actually happened: find the code that made those calls, what it
sent, and what came back. If the response shape was read and retained
anywhere - a log, a ledger entry, a test fixture - that IS the evidence.
Correct the two stale entries either way.

**2. `assign_sender`.** `/campaign/AddLinkedInAccountsToCampaign` and its
Remove counterpart are on WRITE_ROUTES. 48 campaigns in the estate carry
multiple senders and 599020 carries one, so the RESULT is visible. Has a
successful response ever been read? If not, say so - that is the same gap
`add_lead` had, and it is honest.

**3. The readback for each.** A write is only safe if its result can be
confirmed. `GetById` returns `campaignAccountIds`, `linkedInUserListId` and
`status`; `list/GetById` returns the list. Prove each readback works by
reading an EXISTING campaign and list - 83 campaigns are available.

**4. Failure classification.** What does a partial or failed create look like?
What happens if `create_campaign` succeeds and `create_list` then fails - is
there an orphaned campaign, and would anything notice?

## HARD RULES

- **NO WRITES.** Do not create a campaign, a list, or attach a sender to
  anything. Not "one small test campaign". The whole point is that the next
  write is a reviewed decision.
- **Do not edit `providerwrites.SUPPORTED`** and do not delete or weaken a
  seal. If a seal should narrow, propose the narrowing in the report.
- Do not touch campaign 599020 or any client campaign.
- Hash prospect and seat-holder identifiers in anything tracked.
- Read every test exit code OFF THE PROCESS, never through a pipe.

## DELIVERABLE

`docs/CAMPAIGN-WRITE-READINESS-2026-09-15.md`: per route, the request shape,
what is known and unknown about the response, proof the readback works against
an existing object, the failure classification, and the corrected `OPERATIONS`
text. End with the short list of what Claude is reviewing in order to enable -
short, because a long list means the establishment is not finished.

---

## RESULT BLOCK

**STATUS:** DONE

**COMMIT SHA:** 63b237c

**TESTS:** 36 tests in `test_the_heyreach_write_contract` and
`test_the_factory_verbs_exist_and_are_sealed`, all passing (4 skipped as
designed). Exit code read off the process: 0.

**FILES CHANGED:**
- `docs/CAMPAIGN-WRITE-READINESS-2026-09-15.md` (new) — the deliverable

**FINDINGS:**

1. **All three routes have working functions with built-in readback.**
   `create_campaign`, `create_list` and `add_senders`/`remove_senders` all
   read the provider back after the write and raise on any disagreement. The
   readbacks are inside the functions, not separate scripts, so no caller can
   skip them.

2. **The response shapes for `create_campaign` and `create_list` are KNOWN.**
   `create_campaign` returns `{campaignId: int}` (measured 2026-09-13 when
   campaign 599020 was created). `create_list` returns `{id: int}` (measured
   the same session, list 933603). Both were created by Claude in a live
   session and the responses were read by the functions' own readbacks.

3. **The raw response shape for `assign_sender` is UNKNOWN.** `_change_senders`
   discards the response from `_write_body` and reads the campaign back
   instead. This is the same gap `add_lead` had before TASK-124. The readback
   is the proof mechanism and it is solid: before/after comparison of
   `campaignAccountIds`.

4. **All three OPERATIONS entries are stale.** `LINKEDIN_CREATE_LIST` says "no
   documented route; the list was created by hand in the vendor UI" — false,
   list 933603 was created by `heyreach.create_list`. `LINKEDIN_CREATE_CAMPAIGN`
   says "no documented route; nothing suggests a create verb exists" — false,
   campaign 599020 was created by `heyreach.create_campaign`.
   `LINKEDIN_ASSIGN_SENDER` says "assignment was done by hand" — false,
   `add_senders` and `remove_senders` are implemented with full readback.
   Corrected texts are proposed in the deliverable.

5. **No caller in `src/` or `scripts/` invokes these functions.** `grep -rn
   "heyreach.create_campaign\|heyreach.create_list\|heyreach.add_senders"
   src/ scripts/` returns only definitions and constants. They were called
   directly by Claude in a live session on 2026-09-13. This is not a defect
   for this task — the task establishes the routes, not the wiring — but it
   means enabling them in SUPPORTED also needs a caller.

6. **The orphan scenario is bounded.** If `create_campaign` succeeds and
   `create_list` fails (or vice versa), the result is a DRAFT campaign with 0
   leads or an empty list. Neither reaches anybody. The name-uniqueness check
   prevents a second attempt from creating a duplicate. There is no delete
   verb on either object, so orphans are permanent but harmless.

7. **The seal tests will need updating when enabling.** Two tests assert the
   exact `SUPPORTED` tuple and the sealed-operations list. Adding three
   entries requires updating both. These are Claude's changes when enabling.

**RISKS:**
- The raw response shape for `assign_sender` remains unknown. The readback
  covers it, but the first live call should record the response for
  completeness.
- No caller exists in `src/` for any of the three functions. Enabling them in
  SUPPORTED without a caller is the same defect as `set_sequence` before
  TASK-013 — a supported operation with nothing driving it. The caller chain
  needs to be wired when enabling.

**RECOMMENDED CLAUDE ACTION:**
1. Review `docs/CAMPAIGN-WRITE-READINESS-2026-09-15.md`.
2. Apply the corrected OPERATIONS entries.
3. Add `LINKEDIN_CREATE_LIST`, `LINKEDIN_CREATE_CAMPAIGN` and
   `LINKEDIN_ASSIGN_SENDER` to `SUPPORTED`.
4. Update the two seal tests.
5. Wire a caller (likely in `heyreachfactory.py` or `web/api.py`) so the
   enabled operations are actually driven.
