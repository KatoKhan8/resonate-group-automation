PRIORITY: P0
DEPENDS:

# TASK-216 - the supported route from an unbound list to a campaign

## WHERE THIS SITS

This is the only thing between a proven staged lead and the first real
LinkedIn send. Everything else exists.

Provider truth, 2026-09-16:

    list 940797    campaignIds [] - UNBOUND. Holds exactly ONE lead, an
                   operator-approved contact whose li1-li5 all carry
                   `operator-control-arm` approval with fingerprints, and
                   whose profile `/lead/GetLead` resolves.
    list 933603    campaignIds [599020] - bound. NOT a staging destination.
    campaign 599020  status FINISHED, 0 leads, sender 174892 attached,
                   resolves and is active.

TASK-158 proved the list-add schema against the provider. TASK-165 designed
the staging path, TASK-172 defined `heyreach.add_lead_to_list`, the operator
enabled it, and TASK-186 rehearsed it. The lead is staged and read back.

**And there is no route in `src/providers/heyreach.py` that attaches a list to
a campaign.** `grep` for attach_list, bind_list, set_list, AddListToCampaign,
campaign_lists returns nothing. So the staged lead has nowhere to go.

## THE RESEAL YOU MAY NOT TOUCH

Adding a lead directly to campaign 599020 is `LINKEDIN_ADD_LEAD`. It is
refused on the FIRST LINE of its own condition while
`CAMPAIGN_LEVEL_STAGING_IS_PROVEN` is False, because adding a lead to a
HeyReach campaign ACTIVATES it - the vendor documents it for PAUSED and
FINISHED both, and 599020 is FINISHED right now, so an add there is a send.

Do not flip that flag. Do not add to 599020. Do not propose either.

## THE QUESTION

1. **Find the provider route.** Does HeyReach expose a way to attach an
   existing list to an existing campaign - at creation, by update, or at all?
   Check, in this order: the routes already named in `heyreach.py`
   (`READ_ROUTES`, `READ_ROUTES_ALL`, `WRITE_ROUTES`); the vendor's own
   documentation; and the two community sources TASK-158 used successfully
   when the official docs were useless -
   `github.com/bcharleson/n8n-nodes-heyreach` and
   `github.com/bcharleson/heyreach-cli`.
2. **Answer one of three, and say which:**
     (a) a supported bind route EXISTS - name the endpoint, its body, and what
         it does to a FINISHED campaign
     (b) a list can only be attached AT CAMPAIGN CREATION - in which case the
         path is a NEW campaign created around list 940797, and 599020's
         24-node sequence has to be reproduced on it
     (c) no route exists in any form - say so, with what you searched
3. **If (a) or (b): what does binding do to campaign state?** This is the
   safety question and it decides everything. If attaching a list to a
   FINISHED or PAUSED campaign starts it sending, then binding IS activation
   and it needs the full activation gate immediately before it - exactly as
   `LINKEDIN_ADD_LEAD` does. Prove it from documentation, not by trying it.
4. **Then the shortest safe sequence**, written as steps someone can follow,
   from the staged lead to a first send, naming for each step: the route, the
   verb it would need in `providerwrites`, whether that verb exists, and
   whether it is prospect-facing.
5. **Do not perform any of it.** No bind, no create, no activate, no add.

## THE TRAP

`campaignIds` on a list is the safety property the whole staging design rests
on: a list attached to nothing reaches nobody. The moment a bind succeeds,
that property is gone and every lead in the list is a lead in a campaign. So
the bind is the boundary where staging becomes sending, and a design that
treats it as bookkeeping has moved the activation gate without noticing.

Second trap: a 200 on this provider is not a success. TASK-158 measured twelve
body shapes that all returned `addedLeadsCount 0` with HTTP 200 - the silent
drop. If you find a bind route, say what its readback would have to prove,
because "the call returned 200" will not be evidence that anything was bound.

## WHAT YOU MAY NOT DO

- **No provider writes.** No bind, no campaign creation, no activation, no
  lead add. Reads are expected.
- Do not add anything to `SUPPORTED` or `CONDITIONAL`.
- Do not change `CAMPAIGN_LEVEL_STAGING_IS_PROVEN` or
  `_campaign_is_a_declared_staging_campaign`.
- Do not touch list 940797, list 933603 or campaign 599020.
- Never commit a profile URL, a prospect name or a domain.

## FILES ALLOWED

    docs/HEYREACH-BIND-ROUTE-2026-09-16.md   (new)
    scripts/task216_*.py   (read-only probes against READ routes only)

## FILES FORBIDDEN

    src/   work/   config/

## DELIVERABLE

The (a)/(b)/(c) answer with what you searched and where; if a route exists,
its endpoint, body and documented effect on campaign state; what its readback
must prove; and the shortest safe sequence with the verb, its existence and
its prospect-facing status per step.

---

## RESULT

**STATUS:** DONE
**COMMIT:** (pending)
**TESTS:** Not a code-change task; investigation only. No tests run.
**FILES CHANGED:** `docs/HEYREACH-BIND-ROUTE-2026-09-16.md` (new), this task file.
**FINDINGS:** See deliverable document. Summary below.
**RISKS:** None — read-only investigation, no provider writes performed.
**RECOMMENDED CLAUDE ACTION:** Review findings. The previous completion (commit 24de8de5) missed the `UpdateSettings` route. This correction documents it.

### Answer: (a) A Supported Bind Route EXISTS

**Endpoint:** `POST /api/public/campaign/UpdateSettings`

**What it does:** Updates a campaign's general settings including `linkedInUserListId` (the lead list binding).

**Constraints:**
1. Can ONLY be called on DRAFT, SCHEDULED, or PAUSED campaigns — NOT on ACTIVE (IN_PROGRESS) or COMPLETED (FINISHED)
2. Cannot change the list after the campaign has started at least once (returns 400)
3. Does NOT activate the campaign — activation requires separate `StartCampaign` or `Resume`
4. If campaign is SCHEDULED, updating settings reverts it to DRAFT

**For campaign 599020 (FINISHED):** Cannot use `UpdateSettings`. Path is (b): create a NEW campaign around list 940797.

**What the readback must prove:**
- `linkedInUserListId` matches the requested list id
- `status` is unchanged (DRAFT or PAUSED, not IN_PROGRESS)
- List's `campaignIds` includes this campaign id

### Shortest Safe Sequence (for 599020's path: new campaign)

| Step | Route | Verb | In SUPPORTED? | Prospect-facing? |
|------|-------|------|---------------|------------------|
| 1. Create campaign with list binding | `POST /campaign/Create` | `LINKEDIN_CREATE_CAMPAIGN` | **NO** (sealed) | NO (DRAFT, sends nothing) |
| 2. Start empty campaign | `POST /campaign/StartCampaign` | `LINKEDIN_ACTIVATE` (via `start_empty_for_staging`) | YES (zero-lead only) | NO (nobody to act on) |
| 3. Add leads to campaign | `POST /campaign/AddLeadsToCampaignV2` | `LINKEDIN_ADD_LEAD` | YES (but `CAMPAIGN_LEVEL_STAGING_IS_PROVEN=False` reseals) | **YES** (sequence acts on them) |

### What the Previous Completion Missed

The previous TASK-216 (commit 24de8de5, in DONE/) stated "There is no separate attach/detach verb" and "the bind happens ONLY at campaign creation time." This was incorrect. The vendor's own blog post (`https://www.heyreach.io/blog/campaign-api`) documents `UpdateSettings` with full schema, and the HeyReach CLI implements it. The previous completion searched only in-codebase routes and did not check external sources as the task required.

The corrected deliverable is in `docs/HEYREACH-BIND-ROUTE-2026-09-16.md`.
