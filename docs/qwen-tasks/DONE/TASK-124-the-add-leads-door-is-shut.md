PRIORITY: P0
DEPENDS: 

# TASK-124 - prove the add-leads write end to end, so Claude can open the door

## THE BLOCKER, LOCATED EXACTLY

The operator cannot see new campaigns in HeyReach. Provider truth, re-read
2026-09-15: exactly ONE campaign created by Resonate OS - 599020, DRAFT,
**0 leads**, `startedAt` null, created 2026-09-13. Nothing since.

The blocker is not credentials, not the sequence, not the senders, and not
quality. It is one line:

    heyreach.WRITE_ROUTES  contains  /campaign/AddLeadsToCampaignV2
    providerwrites.SUPPORTED  does NOT contain  LINKEDIN_ADD_LEAD

The module says it plainly: *"A route on WRITE_ROUTES is a route this module
CAN call; a route in SUPPORTED is a route this build WILL call. The two lists
are the difference between 'the mechanism exists' and 'it is live'."*

And the reason it is not live, from `OPERATIONS`:

> "the URL is named ... and the route is on WRITE_ROUTES, but **no successful
> response has ever been read**. The request shape is established from
> `build_lead_pairs` and the readback uses `/campaign/GetLeadsFromCampaign`,
> which is already wired. The response body of AddLeadsToCampaignV2 itself is
> UNKNOWN."

## WHAT THIS TASK DOES - AND WHAT IT MUST NOT

**You do NOT enable the route and you do NOT add a lead.** Enabling a
prospect-facing write is Claude's decision after review, and the operator's
standing authorisation routes it through Claude, not through a worker. A
worker that edits `SUPPORTED` has crossed the one boundary that matters most.

Your job is to make that review possible by removing every unknown from it.

1. **Establish the request shape completely.** Read `build_lead_pairs`,
   `add_leads_endpoint`, `supplied_field_names` and `refuse_unsupported_sequence`.
   Produce the exact JSON body that WOULD be sent for a real cohort, written
   to a file, with prospect identifiers HASHED in anything tracked.
2. **Establish the response shape without writing.** The response body is the
   stated unknown. Find out what the provider documents, what the existing
   code expects, and what the readback would need to confirm success. If the
   only way to learn it is to perform a write, say so plainly - that is the
   finding, and it tells Claude exactly what the first write buys.
3. **Prove the readback works on a campaign that already has leads.**
   `/campaign/GetLeadsFromCampaign` is wired. Campaign 599020 has zero leads,
   so it proves nothing. Find a campaign in the account that HAS leads, read
   its leads back, and show the readback returns what it should. **That is the
   single most valuable thing in this task** - it turns "we think we could
   confirm a write" into "we have confirmed we can read the result".
4. **Write the failure classification.** What does a partial add look like?
   What if 50 leads are sent and 43 land? What does the code do today, and
   what should it do? A write whose partial failure is invisible is worse than
   no write.
5. **Check the two stale OPERATIONS entries.** `LINKEDIN_CREATE_LIST` says
   "no documented route; the list was created by hand in the vendor UI" and
   `LINKEDIN_CREATE_CAMPAIGN` says "no documented route". But
   `/list/CreateEmptyList` and `/campaign/Create` are BOTH on WRITE_ROUTES,
   and campaign 599020 and list 933603 were created one second apart on
   2026-09-13, which is not a human in a UI. **Those descriptions are stale in
   the same way the module docstring was.** Establish what actually happened
   and correct them.

## HARD RULES

- **NO WRITES.** No POST that creates, adds, activates or modifies anything.
  Reads only. Do not "test" the add-leads route.
- **Do not edit `providerwrites.SUPPORTED`.** Not even to add a comment
  suggesting it. That edit is Claude's.
- Do not add a lead to any campaign, including 599020, including "just one".
- Hash every prospect identifier in anything tracked. The hygiene guard went
  green today after 16 real tokens were redacted from 9 files, and a report
  naming a record id reddens it within the hour.
- Read every test exit code OFF THE PROCESS, never through a pipe.

## DELIVERABLE

`docs/ADD-LEADS-READINESS-2026-09-15.md`: the exact request body shape, what
is known and unknown about the response, **proof that lead readback works on a
campaign that has leads**, the partial-failure classification, and the
corrected OPERATIONS descriptions. End with a plain list of what remains
unknown, because that list is what Claude is reviewing when the door opens.

---

## RESULT

**STATUS:** DONE

**COMMIT SHA:** d955357

**TESTS:** Not applicable — this task produced a readiness report, not code
changes. Two read-only scripts were written and executed against the live
HeyReach API. All prospect identifiers are hashed in the output.

**FILES CHANGED:**
- `docs/ADD-LEADS-READINESS-2026-09-15.md` — the deliverable
- `scripts/task124_prove_readback.py` — readback proof (1-lead and 0-lead campaigns)
- `scripts/task124_readback_larger.py` — readback proof (28-lead campaign with diverse states)
- `docs/qwen-tasks/RUNNING/TASK-124-the-add-leads-door-is-shut.md` — moved from TODO

**FINDINGS:**

1. **Readback PROVED on campaigns with leads.** Campaign 594061 (1 lead,
   request_pending) and campaign 567689 (28 leads: 25 accepted, 3 replied,
   2 error codes, 28/28 with profile URLs) both confirm
   `/campaign/GetLeadsFromCampaign` returns the full per-lead lifecycle and
   `readback_membership` matches correctly. Campaign 599020 has 0 leads and
   proves nothing.

2. **Request body shape FULLY ESTABLISHED.** `build_lead_pairs` constructs
   `{campaignId, accountLeadPairs: [{linkedInAccountId, lead: {profileUrl,
   firstName, lastName, companyName, position, customUserFields}}]}`.
   `supplied_field_names` derives the field intersection. `refuse_unsupported_sequence`
   raises when the campaign's copy uses a variable the push does not supply.

3. **Response shape INFERRED but not confirmed.** Third-party audit
   (heyreach-cli, 2026-05-04) says V2 returns
   `{addedLeadsCount, updatedLeadsCount, failedLeadsCount}`. No direct read
   by this codebase. The response body does not determine the verdict —
   `readback_membership` does.

4. **Partial failure is VISIBLE but not retryable.** `readback_membership`
   detects when found ≠ expected → DRIFTED → UNRESOLVED. But the key-level
   lock blocks retry on the missing subset. Design needed for targeted retry.

5. **Two OPERATIONS entries are STALE.** `LINKEDIN_CREATE_LIST` says "no
   documented route; the list was created by hand in the vendor UI" — but
   `/list/CreateEmptyList` is on WRITE_ROUTES and list 933603 was created by
   this system on 2026-09-13. `LINKEDIN_CREATE_CAMPAIGN` says "no documented
   route" — but `/campaign/Create` is on WRITE_ROUTES and campaign 599020 was
   created by this system on 2026-09-13. Both entries predate commit f1fd6c0
   and were not updated when the routes were added.

6. **The first write buys information, not exposure.** Campaign 599020 is
   DRAFT with 0 leads and `startedAt: null`. Adding one lead would answer
   every remaining unknown (response shape, partial-failure behaviour, timing
   gap) without sending anything — the campaign cannot start without
   `/campaign/StartCampaign`, which is deliberately absent from WRITE_ROUTES.

**RISKS:**
- The OPERATIONS corrections in this report are observations, not edits.
  `providerwrites.py` was NOT modified. Claude should review and apply the
  corrections if agreed.
- The response shape inference comes from a third-party audit of a different
  workspace. The actual response may differ.

**RECOMMENDED CLAUDE ACTION:**
1. Review `docs/ADD-LEADS-READINESS-2026-09-15.md`
2. Decide whether to enable `LINKEDIN_ADD_LEAD` in `SUPPORTED`
3. If yes: the first write to campaign 599020 (DRAFT, 0 leads) settles every
   remaining unknown. The campaign sends nothing in DRAFT.
4. Apply the OPERATIONS corrections for `LINKEDIN_CREATE_LIST` and
   `LINKEDIN_CREATE_CAMPAIGN` if the analysis is agreed.
5. Design the targeted-retry path for partial-failure missing subsets.
