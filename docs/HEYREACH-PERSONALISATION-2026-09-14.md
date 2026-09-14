# HeyReach campaign 599020: what a lead write would actually have sent

Measured 2026-09-14 against provider truth, before any lead was written. Read
this before adding anybody to a HeyReach campaign. Nothing here is inferred
from the plan; every line was read back from `/campaign/GetCampaignSequence`
or from the sequence builder that produced it.

The short version: **599020 was one call away from sending fourteen people a
message addressed to a fifteenth.** It is not a shell problem and it is not a
copy-quality problem. It is that a HeyReach sequence is CAMPAIGN-level and
this system was baking ONE contact's personalised words into it.

---

## FINDING 1 - the sequence carries one contact's copy, campaign-wide

`heyreachfactory._plan` collects approved LinkedIn copy for every eligible
contact, then does this:

    complete = [c for c in per_contact if not c["missing"]]
    copy_block = complete[0]["copy"]          # <- the FIRST one
    sequence, touch_report = build_sequence(copy_block, ...)

The graph is then built from that single copy block and written to the
campaign. Provider truth on 599020, read back today:

    CONNECTION_REQUEST  "hi jacob, as a founder, you know the importance of
                         having profitability visible on monday. let's connect!"
    MESSAGE             "...how are you currently managing this at &Partner?"

`jacob` is `ogpartner-dk` / `jacob-faertz`, who sorts first. The canonical
campaign row `productive-linkedin-production-v1` holds **14 record_ids**. Had
`AddLeadsToCampaignV2` been enabled and run against that row, thirteen people
at thirteen other companies would have received a connection note addressing
them as Jacob and a message asking about profitability at &Partner.

There are **no merge fields anywhere in the graph** - the payloads are literal
strings.

This is why "enable `LINKEDIN_ADD_LEAD`, it is one line" was the wrong next
action. The line is one line. The campaign behind it was not ready.

## FINDING 2 - the already-connected branch sends the same message twice

`COPY_MAPPING` maps cadence step `li2` to two graph roles, `connected_1` and
`message_2`. `heyreachfactory`'s own docstring justifies that:

    "`li2` serves two positions because the graph has two branches that both
     start with 'the first message to a connection': `connected_1` on the
     already-connected branch and `message_2` on the post-connection branch."

That is true of `chain()`, which builds the post-connection branch. It is NOT
true of `already`, which builds the already-connected branch - that one uses
BOTH roles, one after the other:

    already = MESSAGE connected_1 (3 HOUR)
            -> MESSAGE message_2  (3 DAY)
            -> VIEW_PROFILE
            -> MESSAGE message_3 -> MESSAGE message_4

Read back from the provider, with identical text on both nodes:

    IF connected: MESSAGE (3H) [2fe9] "how do you currently ensure
                                       profitability is visible in your
                                       projects?"
      ELSE (no reply): MESSAGE (3D) [2fe9] "how do you currently ensure
                                            profitability is visible in your
                                            projects?"

So a prospect who is already a connection gets the identical sentence twice,
three days apart. The docstring describes a graph the builder does not build.

This is the LinkedIn instance of the defect the email half already fixed -
"60 of 65 staged email steps repeated another step in their own sequence" -
except here the repetition is structural rather than a model weakness, so no
amount of regeneration would have removed it.

## FINDING 3 - the fix is already supported, and proven on this workspace

Per-lead personalisation does not need a new mechanism. All three pieces
exist:

- `heyreach.build_lead_pairs` already passes an arbitrary per-row
  `custom_fields` dict into `customUserFields` on the wire.
- `heyreach.supplied_field_names(rows)` derives what every row actually
  supplies, as an INTERSECTION - a field only counts when every lead has it.
- `heyreach.refuse_unsupported_sequence(sequence, rows)` raises
  `SequenceRefused` when the sequence uses a variable the push does not
  supply, precisely because "HeyReach does not error on an unknown variable -
  it sends the fallback message instead".

And it is proven in production on this very workspace. The client's own live
campaign **565765** uses merge fields today:

    merge fields = ['{COMPANY}', '{FIRST_NAME}', '{Icebreaker}']
    sample: "Hey {FIRST_NAME},\n\n{Icebreaker}\n \nWe built Productive so
             budgets, time tracking and resourcing actually talk to each
             other..."

`{FIRST_NAME}` and `{COMPANY}` are HeyReach built-ins; `{Icebreaker}` is a
custom user field the client supplies per lead. So the substitution mechanism
works, on this provider, on this workspace, for exactly this purpose.

## WHAT THIS CHANGES

The HeyReach blocker was recorded as "`LINKEDIN_ADD_LEAD` is not in
`SUPPORTED`". That is still true and is still one line. It was never the real
blocker.

    WAS   enable the route, add the 14 leads
    IS    make the sequence per-lead first, THEN enable the route

The order matters and it is not a preference: with the route enabled and the
sequence as it stood, the first live HeyReach action this system ever took
would have been a personalisation failure against thirteen real people at
thirteen real companies, in a workspace where HeyReach has no campaign DELETE.

## STATUS OF THE CAMPAIGN AS READ TODAY

    599020   RESONATE - PRODUCTIVE LINKEDIN PRODUCTION V1
             status            DRAFT
             seat              174892
             linkedInUserListId 933603   (NOT null - see below)
             list total items  0
             sequence          24 nodes, 4 distinct message texts
             "NOT APPROVED COPY" markers   0
             leads             0

Two corrections to `docs/CONTEXT-RESET-2026-09-14.md`, which recorded
`listId None`:

- The campaign HAS a bound list, **933603**, named the same as the campaign
  and reporting `campaignIds: [599020]`. It holds **0** items, so the
  substantive claim - no leads - holds. The difference matters because a
  campaign with a bound empty list is one route call from holding people,
  where a campaign with no list needs a list first.
- The canonical row's `note` is stale in two ways. It says "Every message
  payload at the provider reads 'NOT APPROVED COPY ... must not be started'"
  (there are zero such markers - the sequence was replaced with real copy by
  TASK-013) and "no list" (there is one). A note that contradicts provider
  truth is worse than no note.

## THE FOUR DISTINCT MESSAGE TEXTS CURRENTLY AT THE PROVIDER

For the record, so a later reader can tell whether the graph was rewritten:

    [24ef] CONNECTION_REQUEST
           "hi jacob, as a founder, you know the importance of having
            profitability visible on monday. let's connect!"
    [2fe9] "how do you currently ensure profitability is visible in your
            projects?"
    [57b2] "without clear visibility on profitability, projects can easily go
            off track. how are you currently managing this at &Partner?"
    [0a85] "i'd love to share how teams like yours have improved their project
            visibility and profitability. have you seen any challenges in
            tracking project performance?"

`li5` and `li6` appear nowhere. That part is known and reported in
`touch_report` rather than silent - the graph carries four message
opportunities and the cadence names five.
