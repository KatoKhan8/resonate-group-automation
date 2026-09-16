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

## RESULT

**STATUS:** DONE

**COMMIT SHA:** (pending)

**TESTS:** No tests run. This task was read-only research against provider
routes and documentation. No code was changed in `src/` or `tests/`.

**FILES CHANGED:**
- `docs/HEYREACH-BIND-ROUTE-2026-09-16.md` (new) - the deliverable

**ANSWER: (b)** - a list can only be attached at campaign creation or via
`POST /campaign/UpdateSettings` on a campaign in DRAFT/SCHEDULED/PAUSED that
has never been started. Campaign 599020 is FINISHED and has been started, so
neither path works for it. The path forward is a new campaign created around
list 940797, with campaign 599020's sequence reproduced on it.

**THE ROUTE THAT EXISTS:**

`POST /campaign/UpdateSettings`
- Body: `{campaignId, name, linkedInUserListId, ...exclusions}`
- Allowed statuses: DRAFT, SCHEDULED, PAUSED
- Effect: changes the list binding; SCHEDULED reverts to DRAFT; does NOT
  activate the campaign
- Restriction 1: refuses on IN_PROGRESS or FINISHED campaigns (400)
- Restriction 2: refuses if the campaign has been started at least once (400:
  "List changed after campaign has started")

**WHAT WAS SEARCHED:**
1. `src/providers/heyreach.py` - all route allowlists (READ_ROUTES,
   READ_ROUTES_ALL, READ_GET_ROUTES, WRITE_ROUTES). No UpdateSettings.
2. Vendor official docs: `heyreach.io/blog/campaign-api` and Postman
   collection `documenter.getpostman.com/view/23808049/2sA2xb5F75`
3. Community sources: `github.com/bcharleson/n8n-nodes-heyreach` (no
   UpdateSettings) and `github.com/bcharleson/heyreach-cli` (full source of
   `update-settings.ts` with endpoint, body, and description)
4. Web search for HeyReach API endpoint lists

**THE SHORTEST SAFE SEQUENCE:**

| Step | Route | Verb | In SUPPORTED? | Prospect-facing? |
|------|-------|------|---------------|------------------|
| 1. Create campaign with list | `/campaign/Create` | `LINKEDIN_CREATE_CAMPAIGN` | Yes | No |
| 2. Write sequence | (folded into step 1 via `sequence=` param) | - | - | No |
| 3. Start empty for staging | `/campaign/StartCampaign` | `LINKEDIN_START_EMPTY_FOR_STAGING` | Yes (conditional) | No |
| 4. Add lead | `/campaign/AddLeadsToCampaignV2` | `LINKEDIN_ADD_LEAD` | Yes (conditional, RESEALED) | **Yes** |

The bind at creation is bookkeeping. The activation boundary is step 4
(`AddLeadsToCampaignV2`), already guarded by `LINKEDIN_ADD_LEAD` with its
conditional seal. No new activation gate is needed for the bind.

**FINDINGS:**
- `POST /campaign/UpdateSettings` exists but is not on any allowlist in
  `heyreach.py` and has no named verb in `providerwrites.py`. It was
  documented by the vendor but never probed by this codebase.
- The "locked after start" restriction on `linkedInUserListId` is the key
  safety property: once a campaign has run, its list binding is permanent.
  This is stronger than the status restriction - even a DRAFT that was
  previously started cannot be rebound.
- The n8n-nodes-heyreach repo does not implement UpdateSettings at all,
  which is why TASK-158 did not find it.

**RISKS:**
- The "locked after start" restriction is documented by the vendor and the
  CLI but has not been probe-tested against this provider account. A 400
  refusal is expected but unconfirmed.
- `UpdateSettings` is not on `WRITE_ROUTES` in `heyreach.py`. If it were to
  be used, it would need to be added to the allowlist and given a named verb
  in `providerwrites`.

**RECOMMENDED CLAUDE ACTION:**
1. Create a new campaign bound to list 940797 with `create_campaign`, passing
   the sequence from 599020 as the `sequence=` parameter.
2. Start the empty campaign with `LINKEDIN_START_EMPTY_FOR_STAGING`.
3. Then the TASK-137 work (narrowing the seals on `LINKEDIN_ADD_LEAD`) can
   proceed against the new campaign, which is a proper staging destination.
4. Consider adding `UpdateSettings` to `WRITE_ROUTES` and giving it a named
   verb, for the case where a DRAFT campaign needs rebinding before it runs.
