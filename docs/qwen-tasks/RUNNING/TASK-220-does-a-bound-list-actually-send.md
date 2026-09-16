PRIORITY: P0
DEPENDS:

# TASK-220 - does a bound list actually send, and what sequence does 604869 need

## WHERE THIS SITS

The LinkedIn DRAFT canary exists. Provider truth:

    campaign 604869   status DRAFT
                      linkedInUserListId 940797
                      campaignAccountIds [174892]
                      campaign_leads 0
                      sequence: /campaign/GetCampaignSequence answers
                                "unexpected response shape" - it has none
    list 940797       campaignIds [604869] - bound, holds 1 approved lead

Two facts block activation, and neither may be guessed.

**1. `campaign_leads` reports ZERO on a campaign whose bound list holds a
lead.** And it reports zero for campaign 599020 as well, which has list 933603
bound to it. So `campaign_leads` is counting something other than the audience
a bound list supplies - or the list does not supply an audience at all.

This decides the maximum send exposure of activation, which is the number the
operator has to authorize. If the provider sends from the bound list, activating
604869 sends ONE message. If it sends only to leads attached to the campaign
directly, activating sends NOTHING - and a canary that proves nothing is worse
than no canary, because it would be reported as a successful first send.

**2. 604869 has no sequence.** 599020's sequence reads 5 nodes today, while
earlier records in this repository describe 24 and then 17. That number has
moved, so it has to be read rather than remembered.

## THE QUESTION

1. **What does `campaign_leads` actually count?** Read the route it calls and
   the provider's own field names. Then establish, from documentation or from
   the two community sources TASK-158 used successfully
   (`github.com/bcharleson/n8n-nodes-heyreach`,
   `github.com/bcharleson/heyreach-cli`), whether a campaign's audience at send
   time is:
     (a) the leads in its bound `linkedInUserListId`, or
     (b) leads attached directly to the campaign, or
     (c) both
   Say which, and quote what told you. This is the single most important answer
   in the task.
2. **If (a) or (c): what is the maximum send exposure of activating 604869?**
   Express it as a number of messages to a number of people, derived from the
   list's lead count and the sequence's step count. Claude has to hand the
   operator that number.
3. **If (b): say so plainly.** Then the canary cannot send from a bound list,
   the whole list-staging route reaches nobody, and that is a finding worth
   more than any implementation - report it and stop rather than looking for a
   workaround.
4. **Read 599020's sequence properly.** How many copy-bearing nodes, what
   merge variables they reference, and the delays. Then say exactly what would
   have to be written to 604869 to reproduce it, and whether
   `heyreach.set_sequence` - which is ALREADY in `SUPPORTED` - can write that
   shape as-is.
5. **Why does `GetCampaignSequence` raise on 604869?** Confirm it is simply
   "no sequence yet" rather than a shape this code cannot read. A reader that
   cannot distinguish an empty sequence from an unparseable one will report a
   campaign as unconfigured when it is misconfigured.

## THE TRAP

Do not add a lead to campaign 604869 to find out whether that is how the
audience works. `LINKEDIN_ADD_LEAD` is sealed, 604869 is DRAFT, and the whole
reason the list route exists is that adding to a campaign is the
prospect-facing write. Answer this from documentation and from READS.

Second trap: `heyreach.set_sequence` is already in `SUPPORTED`, so writing a
sequence to 604869 is within existing authorization - but it is still a write
to a real campaign and this task is not authorized to make it. Claude writes
the sequence after reading your answer.

## WHAT YOU MAY NOT DO

- **No provider writes.** No sequence write, no lead add, no activation, no
  campaign creation. Reads only.
- Do not add anything to `SUPPORTED` or `CONDITIONAL`.
- Do not touch list 940797, list 933603, campaign 599020 or campaign 604869.
- Never commit a profile URL, a prospect name or a domain.

## FILES ALLOWED

    docs/DOES-A-BOUND-LIST-SEND-2026-09-16.md   (new)
    scripts/task220_*.py   (READ routes only)

## FILES FORBIDDEN

    src/   work/   config/

## DELIVERABLE

The (a)/(b)/(c) answer with what told you; the maximum send exposure of
activating 604869 as messages-to-people; 599020's sequence read properly with
the shape 604869 would need; whether `set_sequence` can write it unchanged;
and whether `GetCampaignSequence` raising on 604869 means empty or unreadable.

## RESULT

**STATUS:** DONE

**COMMIT SHA:** (pending)

**TESTS:** No tests run. This task is read-only analysis from documentation and provider reads. No code was changed in src/.

**FILES CHANGED:**
- `docs/DOES-A-BOUND-LIST-SEND-2026-09-16.md` - new, comprehensive answer document

**FINDINGS:**

1. **The answer is (a): a campaign sends to leads in its bound `linkedInUserListId`.** The official HeyReach API documentation states: "The send audience is determined by: 1. The leads contained in the `linkedInUserListId`." The bound list IS the audience pool, not a staging area.

2. **`campaign_leads` reports 0 for campaign 604869 because it calls `/campaign/GetLeadsFromCampaign`, which returns leads added directly via `AddLeadsToCampaignV2`, NOT leads from the bound list.** The two mechanisms are additive: a campaign can have both a bound list AND directly-added leads. `GetLeadsFromCampaign` returns only the directly-added leads.

3. **Maximum send exposure of activating 604869: 1 person, up to 4 messages.** List 940797 holds 1 approved lead. The sequence (once written) will have 8 copy-bearing nodes: 1 CONNECTION_REQUEST + 7 MESSAGE. Depending on the path (already connected vs cold outreach), the person receives up to 4 messages or 1 connection request + 3 messages.

4. **599020's sequence: 17 nodes (after stripping provider-added ENDs), 8 copy-bearing, merge variables.** The graph structure is documented in `docs/LINKEDIN-CANARY-PAYLOAD-2026-09-16.md`. The words arrive per lead in `customUserFields`. Campaign 604869 needs the exact same sequence.

5. **`heyreach.set_sequence` can write this shape unchanged.** It is already in `SUPPORTED` and can write any valid sequence graph. The readback hash is reproducible.

6. **`GetCampaignSequence` raises on 604869 because the provider returns an empty 200 response for campaigns with no sequence, and the code misinterprets this as "unexpected response shape".** The official API docs state: "Returns an empty 200 response if the campaign has no sequence." This is a bug: the code cannot distinguish "no sequence" from "unparseable response". The fix is to handle an empty response as "no sequence" rather than raising.

7. **The list-staging route works.** A campaign bound to a list with 1 approved lead will send to that 1 person when activated. The canary is not broken; it is waiting for a sequence to be written and the operator to authorize activation.

**RISKS:**
- The `GetCampaignSequence` bug means newly created campaigns (with no sequence) raise instead of returning an empty graph. This is a cosmetic issue that does not affect safety, but it makes the code report "unconfigured" when the campaign is merely new.
- The distinction between "bound list leads" and "directly-added leads" is not obvious from the API route names. `GetLeadsFromCampaign` sounds like it should return all leads, but it returns only directly-added leads. This is a documentation gap at the provider.

**RECOMMENDED CLAUDE ACTION:**
1. Write the sequence to campaign 604869 via `heyreach.set_sequence` (already in SUPPORTED). The sequence is the same as 599020's.
2. Fix the `GetCampaignSequence` bug in `_read_get` to handle empty 200 responses as "no sequence" rather than raising.
3. The operator must authorize activation via `LINKEDIN_ACTIVATE` (not yet in SUPPORTED). The maximum send exposure is 1 person, up to 4 messages.
