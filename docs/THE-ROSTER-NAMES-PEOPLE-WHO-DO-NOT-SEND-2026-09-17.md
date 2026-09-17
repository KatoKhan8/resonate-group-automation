# The canonical sender roster names seven people the provider has never heard of

2026-09-17. Measured against live `senderidentity.load()` and against the
EmailBison roster read the same hour.

`docs/PRODUCTION-HANDOFF-2026-09-17.md` says: "All 225 email and all 32
LinkedIn productive accounts carry `sender_id: null` and there are ZERO
ownership attestations, so `eligible_senders` returns [], `allocate` raises,
`ensure` SWALLOWS it, and everything falls back to the hardcoded seat."

The conclusion is right. Two of the details are wrong in ways that matter, and
the thing underneath them is worse than the thing described.

## What the roster actually holds

    285 rows      11 sender (human)   235 email_account   35 linkedin_account
                   3 pairing           1 outreach_team

    accounts with an owner      13 of 270
    productive accounts         257
    productive accounts owned   ZERO

So it is not that nothing is attested. Thirteen accounts are - **and all
thirteen are fixtures.** They live in workspaces `contactout` and
`demo-client` and their `provider_account_id`s are `bison-1`, `bison-2`,
`4001`, `4002`. There is no such EmailBison sender and no such HeyReach seat.
The productive accounts, by contrast, carry the provider's REAL ids: 3948,
3947, 3946, 3945, 3944, 3943, 3942, 3941.

## The part that is not a detail

The roster's seven `productive` humans are:

    Anna Novak   Mark Weber   John Adeyemi   Sarah Lindqvist
    Petar Horvat   Tom Ricci   Sara Simic

**None of them exists at the provider.** EmailBison's 225 inboxes are owned,
by the `name` on each inbox, by ten people, and the roster names none of them:

    human-7cc85aecf642   66 inboxes        human-a8d24efdbbaa   13 inboxes
    human-9e58861fb87e   58               human-2b4e867056bc   12
    human-7798a10e783c   17               human-35ecf4f32d2f   11
    human-083df9628156   17               human-c62bbb200b21    6   <- 487's sender
    human-013d683eec7a   17               human-6782bfbfb93f    5
                                          human-a7c559b981ac    2

Names are hashed here for the same reason the design document's were: this
file is tracked and `tests/test_fixture_hygiene.py` forbids a real name in a
tracked file. **It did not catch these** - its denylist knows one surname from
an earlier leak and not the client's sending roster, and it cannot be taught
them without storing the names it exists to keep out. That is a real limit of
the guard and the reason to look at a diff as well as run the test. The hashes
are `sha256(name.lower())[:12]`, the same function
`scripts/email_sender_estate.py` uses, so the human-readable table is one
command away for anyone holding the credential.

`assignment.allocate` returns `display_name` off the roster row. So if the 257
productive accounts were ever attached to those seven humans - which is exactly
what "fix the attestation gap" sounds like it means - **every allocation would
attribute a real send to a person who does not exist**, while the inbox's own
`email_signature` signed it as human-c62bbb200b21. That is the invariant in
CLAUDE.md and in section 8 of the handoff, failing silently and at scale:
exact identity only, never claim a continuity that did not happen.

**The emptiness is protective. Do not fill it by hand.**

## Nothing is fabricated today, and here is the trace that proves it

    assignment.ensure          writes contact.sender_assignment
      -> eligible_senders('productive', ...)   returns []  (no owned account)
      -> allocate                              raises NoEligibleSender
      -> ensure                                records it under
                                               block['unavailable'][channel]

That last step is NOT a swallow, and the distinction matters because a swallow
would be a defect worth fixing: it is a classified refusal, recorded on the
contact, and the comment says why - a contact with no LinkedIn sender is an
email-only contact, and refusing the whole assignment would take the email
away too.

Downstream, `push._sender_of` reads the stored assignment and returns empty
strings for all five sender fields. `bison._variables` DROPS empty values
rather than sending them blank - deliberately, because "a blank `record_id`
reads exactly like an attributed one until somebody tries to use it". And
`sender_name` is not a lead variable at all. **So no fabricated name can reach
a prospect through this path.** Campaign 487's ten leads carry no sender
attribution whatsoever, which is honest rather than wrong.

## Where the chain actually breaks, per link

The interesting part is that the plumbing is nearly complete:

    assignment.ensure            WRITES contact.sender_assignment        yes
    push._sender_of              READS it into the payload row           yes
    heyreach.build_lead_pairs    reads row['provider_account_id'] PER
                                 LEAD, falling back to the campaign id   yes
    heyreach.add_leads_to_campaign  posts accountLeadPairs               yes

Four links, all present. Two things break it:

1. **No productive account has an owner**, so link one produces `unavailable`
   and links two to four carry nothing.
2. **The live LinkedIn path does not go through `push` at all.**
   `stage_linkedin_cohort_b.py` imports `liststaging` and `heyreach`, builds a
   LIST, and binds the campaign to one seat. `heyreachfactory._seat_for` then
   resolves a seat PER CAMPAIGN - from `senders.linkedin` on the canonical
   row, else from `campaignAccountIds` - and refuses outright when more than
   one is bound, because "which human a prospect hears from would be decided
   by list order".

So there are two implementations of "which seat does this lead send from", one
per-lead and consumed by nothing live, one per-campaign and carrying every
real send. That is the parallel state machine CLAUDE.md warns about, and it is
why P4 is not a small change even though `build_lead_pairs` already does the
hard part.

## What the provider offers that we are not using

`emails_sent` is not the only thing `scheduled_emails` returns. Campaign 451's
single row carries a full `sender_email` object - id, address, signature,
lifetime counters. **Per-lead sender is OBSERVABLE after the fact on
EmailBison**, exactly as the attribution design says, and 451 is the proof it
is readable rather than theoretical. HeyReach returns `linkedInSenderId` per
lead on `GetLeadsFromCampaign`, already mapped, already read by
`heyreach_first_send_watch.py` - every one of 605732's three leads reads
`sender_id: 174892`.

## The next step, and what it is not

The attestation cannot be invented and it does not have to be. The provider
publishes an owner for every inbox - the `name` field - and
`scripts/email_sender_estate.py` already groups all 225 by it. That is
EVIDENCE of ownership, not proof: a display name is set by whoever configured
the inbox, and this estate contains a pair of names differing by a single
letter - `human-7cc85aecf642` with 66 inboxes and `human-6782bfbfb93f` with 5.
They are either one person typed two ways or two colleagues who share a
surname, and **no amount of reading the provider settles it.** A backfill that
guessed would either merge two people's sending histories or split one
person's, and both are the identity failure this is meant to prevent.

So the next step is to derive a candidate attestation from provider truth,
present it for a human to confirm, and record the confirmation with its
source - not to write seven names into a roster and let `allocate` speak for
them.

Until that exists, the arity rule stands and is doing its job.
