# TASK-071 - Inventory the whole EmailBison API surface, from the docs and from the wire

## TWO AUTHORITATIVE SOURCES, NEWLY SUPPLIED

    official   https://docs.emailbison.com/get-started/introduction
    ours       https://send.resonategroup.co/api/reference

**Read BOTH, and follow the linked and sub-pages.** The introduction page is
a table of contents, not the surface. Do not stop at the endpoints this
repository already calls - the point of this task is the ones it does not.

## THE SOURCE-OF-TRUTH HIERARCHY, AND IT IS NOT NEGOTIABLE

    1  real authenticated responses from send.resonategroup.co
    2  our actual historical estate
    3  https://send.resonategroup.co/api/reference
    4  https://docs.emailbison.com
    5  the existing code in src/providers/bison.py
    6  assumptions - NEVER sufficient for a production conclusion

Documentation says what SHOULD exist. An authenticated response says what
DOES exist FOR OUR ACCOUNT. **Where they disagree, record the discrepancy and
trust the measured behaviour.**

That is not hypothetical here. `src/providers/bison.py` already documents a
case where `workspace_id` is accepted and silently discarded, and the answer
for a workspace that does not exist is byte-identical to the answer for the
one that does. A documented parameter that does nothing is exactly the kind
of thing this inventory exists to catch.

## THE INVENTORY

Cover at least: campaigns, creation, status, activation, sequences, steps,
leads, membership, lead history, sent emails, individual messages, message
ids, threads, conversations, replies, reply bodies and timestamps, sender
accounts and identity, events, activity, scheduled emails, historical sends,
campaign / lead / step statistics, reply statistics, positive replies,
interested states, bounce, unsubscribe, variants, A/B testing, custom
variables, webhooks, pagination, filtering, date ranges, rate limits, and any
stated limits on historical data.

For each capability record:

    CAPABILITY / ENDPOINT / METHOD / DOCUMENTED SOURCE
    REQUEST PARAMETERS / RESPONSE FIELDS
    AVAILABLE IDs / AVAILABLE TIMESTAMPS
    RELATIONSHIPS TO OTHER ENTITIES
    PAGINATION / FILTERING / HISTORICAL AVAILABILITY
    IMPLEMENTED IN RESONATE OS?   yes / no / partial
    VERIFIED AGAINST LIVE API?    yes / no
    USEFUL FOR PRODUCTION?        how
    USEFUL FOR LEARNING?          how
    KNOWN LIMITATIONS / EVIDENCE

**A capability is never VERIFIED because the documentation says it exists.**
VERIFIED means you called it against our account and read the response. Any
row that is documented but unverified says so in the VERIFIED column, and a
row whose live behaviour contradicts the docs gets both recorded.

## WHAT THIS IS FOR, AND WHY IT IS NOT A DOCUMENTATION EXERCISE

TASK-069 has to answer four questions with evidence, and three of them may
well turn on an endpoint nobody here has called:

    A  historical per-lead / per-step sends with timestamps
    B  a reply joined DIRECTLY to a message or sequence step
    C  sequence position reconstructable when B is absent
    D  a persistent variant / A-B identifier surviving send and readback

Look specifically for id fields that could carry those joins - `reply_id`,
`message_id`, `email_id`, `thread_id`, `lead_id`, `campaign_id`,
`sequence_id`, `sequence_step_id` and anything else the docs name. **Do not
assume a field name.** Report the names that actually appear.

If you find an endpoint that answers A, B, C or D and this repository does
not call it, that is the most valuable thing this task can produce. Say so
plainly at the top of the document.

## READS ONLY, AND THE STAKES ARE HIGHER THAN USUAL

You hold real EmailBison credentials for a live client estate. You are
cataloguing WRITE endpoints as part of the inventory - **document them,
never call them.** No campaign creation, no sequence write, no lead write,
no activation, no resume, no pause, no send. A GET is permitted; anything
that changes state is not, whatever the documentation invites.

## OUTPUT

`docs/BISON-API-CAPABILITY-MAP-<date>.md`. Durable, so no future session has
to rediscover this. No credential values, no prospect PII, no real email
addresses.

## RESULT BLOCK

STATUS, COMMIT SHA, TESTS, FILES CHANGED, FINDINGS, RISKS, RECOMMENDED
CLAUDE ACTION. FINDINGS leads with any endpoint that answers A/B/C/D and is
not currently implemented.
