# The provider refuses the state our gate requires

Measured 2026-09-15, against HeyReach campaign 599020, by an actual write.

    POST /campaign/AddLeadsToCampaignV2
    HTTP 400
    {"errorMessage": "You cannot add new leads to a draft campaign."}

Provider state immediately after: **DRAFT, 0 leads.** Nothing was written. The
action-ledger key was settled FAILED from that readback, not from assumption.

---

## Why this matters more than a failed call

`providerwrites.CONDITIONAL[LINKEDIN_ADD_LEAD]` admits a write only when
`heyreach.campaign_cannot_send(campaign)` is True, and
`_STATUSES_THAT_CANNOT_SEND` is `(DRAFT,)`. The whole safety argument for
enabling the first prospect-facing route rests on that: a lead staged into a
campaign that cannot send reaches nobody.

**HeyReach does not accept leads into a campaign that cannot send.** The state
our gate requires is the one state the provider refuses. As built, the
condition is not strict - it is unsatisfiable, and the route can never be used.

That was not knowable from the documentation or from any read. The request
shape was established, the readback was live-validated against campaign
565765, and `docs/ADD-LEADS-READINESS-2026-09-15.md` removed every unknown it
could - but it also recorded honestly that "the response body of
AddLeadsToCampaignV2 itself is UNKNOWN. No successful response has ever been
read." This is what reading one costs.

## The three states, and what each actually permits

    DRAFT          leads REFUSED by the provider (measured, 400)
                   cannot send
    PAUSED         leads accepted (inferred - not yet measured)
                   does not send until somebody resumes it
    IN_PROGRESS    leads accepted
                   SENDS IMMEDIATELY - the sequence acts on a new lead at once

So the only state in which leads can be staged AND nothing is sent is
**PAUSED** - and PAUSED is the state the gate deliberately excludes.

`campaign_cannot_send` excludes it for a stated reason, and the reason is
sound: *"PAUSED because it can be resumed at any moment, and leads added to it
sit waiting for the resume button."* That is a real risk and it is pinned by
its own test.

## What is actually being traded

The risk PAUSED carries is that a human resumes the campaign in the vendor UI
while our leads sit in it. Worth stating precisely what that is and is not:

- It is NOT our system sending. `LINKEDIN_ACTIVATE` is sealed, carries no
  entry in `providerwrites.CONDITIONAL`, and there is no value anybody can
  pass to `perform` that admits it. Nothing in Resonate OS can start 599020.
- It IS a real exposure to somebody else's hand on the vendor UI. 599020 is a
  Resonate-created campaign in the client's own account, and the client has 82
  other campaigns and people who work in that interface.
- The same exposure exists the moment we activate deliberately, which is the
  intended end state. PAUSED moves the window earlier, it does not create it.
- The mitigation that already exists: `heyreach.pause` is live-validated and
  in `SUPPORTED`, so a campaign that starts unexpectedly can be stopped by
  this system. That is the condition the stoppability ceiling was waiting on
  and it has been met since 2026-09-12.

## What has NOT been measured

**Whether PAUSED actually accepts leads.** It is inferred from the error
message naming DRAFT specifically. It has not been tested, and the honest
position is that one provider error message is evidence about DRAFT and a
hypothesis about everything else.

The cheapest way to find out is one lead into a PAUSED campaign, with an
immediate readback - the same canary shape, one state to the right.

## What this does not change

The rest of the write path is now proven end to end. Reaching this error meant
clearing, in order: the cohort's account collision, the person's LinkedIn
conversation history, copy approval by fingerprint, the campaign approval, the
provider-configuration diff, tenancy, the sender roster, fatigue, caps, the
ledger reservation, the killswitch, the approved-words comparison, and the
conditional permission itself. All of it works. The transport was reached.

The remaining question is which campaign state to reach it in.
