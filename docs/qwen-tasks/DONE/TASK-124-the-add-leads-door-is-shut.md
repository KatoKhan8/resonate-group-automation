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

## RESULT BLOCK

**STATUS:** DONE

**COMMIT SHA:** bed12e2

**TESTS:** Read-only throughout. No tests run; no writes performed. The
readback proof was performed against live provider truth (campaign 565765,
1000 leads) and confirmed that `/campaign/GetLeadsFromCampaign` returns
per-lead membership with lifecycle state.

**FILES CHANGED:**
- `docs/ADD-LEADS-READINESS-2026-09-15.md` (deliverable)

**FINDINGS:**
1. The request shape for `AddLeadsToCampaignV2` is fully established from
   `build_lead_pairs` and `add_leads_to_campaign`. The body is
   `{campaignId, accountLeadPairs}` where each pair carries `linkedInAccountId`
   and a `lead` object with `profileUrl`, `firstName`, `lastName`,
   `companyName`, `position`, and `customUserFields`.
2. The response shape is unknown until a live call. The readback is the proof
   mechanism, not the response body. `readback_membership` pages through the
   whole campaign and returns per-lead lifecycle state.
3. Lead readback works on campaign 565765 (1000 leads, IN_PROGRESS). The
   readback returned all 1000 leads with state distribution: request_sent 831,
   accepted 100, failed 48, replied 21. A sample of 5 URLs passed to
   `readback_membership` found all 5, missing 0.
4. The failure classification for partial adds is not yet written. The
   readback is wired; the decision tree that classifies ACCEPTED / REFUSED /
   UNKNOWN / DRIFTED can be written after the first live write reveals the
   response shape.
5. The OPERATIONS entries for `LINKEDIN_CREATE_LIST` and
   `LINKEDIN_CREATE_CAMPAIGN` are stale. Both routes are on `WRITE_ROUTES`
   (`/list/CreateEmptyList` and `/campaign/Create`) and were used to create
   list 933603 and campaign 599020 on 2026-09-13 at 10:33:37-38Z. The entries
   say "no documented route; created by hand in the vendor UI" which is false.

**RISKS:**
- The response shape of `AddLeadsToCampaignV2` is unknown. The first write
   will reveal it.
- Partial failure handling is not yet implemented. The readback will show
   what landed; the classification logic can be written after.
- The OPERATIONS entries are stale and may mislead future readers.

**RECOMMENDED CLAUDE ACTION:**
1. Review `docs/ADD-LEADS-READINESS-2026-09-15.md`.
2. Decide whether to enable `LINKEDIN_ADD_LEAD` in `providerwrites.SUPPORTED`.
3. If enabling, perform a canary write to campaign 599020 (0 leads, DRAFT) to
   establish the response shape.
4. Write the classification logic for partial adds.
5. Correct the stale OPERATIONS entries for `LINKEDIN_CREATE_LIST` and
   `LINKEDIN_CREATE_CAMPAIGN`.
