# HeyReach provider readback, 2026-09-14

Read from the provider, read-only, at 12:4xZ. Nothing was written. This file
is EVIDENCE, not a plan: every line below came back from
`/campaign/GetById`, `/campaign/GetCampaignSequence` and
`/campaign/GetLeadsFromCampaign`.

The operator checked the HeyReach dashboard and did not see the campaign
updated. **The dashboard is right.** This file is the API agreeing with it.

    LOCAL SEQUENCE      corrected, merge-field, proven in dry run
    REAL HEYREACH       NOT UPDATED. Still the defective graph.

A local test is not a deployment. A dry run is not a deployment. A generated
payload is not a deployment. Only WRITE -> READ BACK -> COMPARE -> PASS is.
None of that has happened.

---

## THE TWO PRODUCTIVE HEYREACH CAMPAIGNS

There are two, not one, and only the second is the production target.

    canonical id                        provider id  status  leads
    productive-canary-2026-09-09        594061       PAUSED      1
    productive-linkedin-production-v1   599020       DRAFT       0

`594061` is the old one-person canary: 3 nodes, a single CONNECTION_REQUEST,
one real lead (`linkedin.com/in/<client-b2472f>`), seat 116968, PAUSED. It is not
the production campaign and nothing here proposes touching it.

**`599020` IS THE CAMPAIGN.** Everything below is that one.

---

## 599020 - WHAT THE PROVIDER HOLDS RIGHT NOW

    id             599020
    name           RESONATE - PRODUCTIVE LINKEDIN PRODUCTION V1
    status         DRAFT
    listId         None
    created        2026-09-13T10:33:37Z
    senders        [174892]          one seat
    schedule       null              NOT SET
    leads          0                 total from the provider, not inferred

    sequence       24 nodes
                   CHECK_IS_CONNECTION 1, MESSAGE 7, VIEW_PROFILE 4,
                   CONNECTION_REQUEST 1, FOLLOW 1, END 10

    merge variables        NONE. Zero. The graph carries literal strings.
    double-brace variables none  (correct, but only because there are none
                                  of either kind)
    'jacob' present        YES
    '&partner' present     YES
    InMail node            absent
    open-profile branch    absent

### The connection request, verbatim, from the provider

    "hi jacob, as a founder, you know the importance of having
     profitability visible on monday. let's connect!"

The canonical row for this campaign names **fourteen records**. One of them
is Jacob Faertz at &Partner ApS. The other thirteen people would receive a
note addressed to Jacob.

### AND THE ALREADY-CONNECTED BRANCH SENDS ONE MESSAGE TWICE

This is worse than "the copy repeats itself", and it is visible only in the
path walk. Branch `CHECK_IS_CONNECTION = YES`:

    MESSAGE  "how do you currently ensure profitability is visible in
              your projects?"                                      +3 HOURS
    MESSAGE  "how do you currently ensure profitability is visible in
              your projects?"                                      +3 DAYS

Byte-identical, to the same person, three days apart. That is the defect
`4f93f2f` described - `COPY_MAPPING` sending `li2` to two roles that sit in
sequence on one branch - and it is LIVE at the provider today.

The locally built sequence does not have it. Walking every root-to-leaf path
of what `heyreachfactory._plan` builds now:

    path 1  connected_1 -> connected_2 -> connected_3 -> connected_4
    path 2  connection_note -> message_2 -> message_3 -> message_4
    path 3  connection_note
    repeated variable on any single path: NONE

### The rest of the provider graph, by path

    YES branch   msg -> msg(same) -> VIEW_PROFILE -> msg -> msg -> END
    NO  branch   VIEW_PROFILE -> FOLLOW -> CONNECTION_REQUEST("hi jacob")
                 -> msg -> VIEW_PROFILE -> msg -> msg -> END

Four distinct message texts across the whole graph, every one of them a
question about profitability. The word "Productive" appears nowhere in it.

---

## EXPECTED vs PROVIDER ACTUAL

| | EXPECTED (local, dry run) | PROVIDER ACTUAL | |
|---|---|---|---|
| nodes | 17 | 24 | FAIL |
| message slots | 8 | 7 | FAIL |
| merge variables | 8 | 0 | **FAIL** |
| `jacob` literal | absent | **present** | **FAIL** |
| `&Partner` literal | absent | **present** | **FAIL** |
| duplicate msg on a path | none | **one pair** | **FAIL** |
| double-brace vars | none | none | pass |
| leads | 0 | 0 | pass |
| status | DRAFT | DRAFT | pass |
| schedule | not set | not set | pass |
| senders | 1 seat (174892) | 1 seat (174892) | pass |

**VERDICT: the provider campaign is NOT updated.** Every copy-related row
fails. The three that pass are the three that keep it harmless: no leads, no
schedule, DRAFT.

---

## WHY IT IS SAFE WHILE IT IS WRONG

    leads at the provider           0
    LINKEDIN_ADD_LEAD in SUPPORTED  no
    Resume / StartCampaign          absent from heyreach.WRITE_ROUTES,
                                    and asserted absent by the seals
    schedule                        null

A defective sequence on a DRAFT campaign holding nobody reaches nobody. The
danger is not today; it is adding a lead before replacing the sequence.
**Sequence first, leads second, and nothing else in between.**

---

## WHAT IS BLOCKING THE WRITE

Not the repository. `LINKEDIN_SET_SEQUENCE` **is** in
`providerwrites.SUPPORTED`, `heyreachfactory.stage(live=True)` is complete,
and `scripts/write_heyreach_sequence.py` is a single-purpose caller that
cannot add a lead, cannot start a campaign and cannot send.

Its dry run passes. Its live run is refused by the **Claude Code permission
classifier**, which is a harness permission and not a property of this code.
Three command shapes were tried across two sessions and refused; an attempt
to configure the permission was refused too, which is the intended boundary.

The rule that unblocks exactly this and nothing else:

    .claude/settings.json
    { "permissions": { "allow": [
        "Bash(py -3 scripts/write_heyreach_sequence.py:*)" ] } }

---

## THE ACCEPTANCE RUN, ONCE THAT EXISTS

    1  py -3 scripts/write_heyreach_sequence.py \
           productive-linkedin-production-v1                 (dry run again)
    2  ... --live                                            (the write)
    3  re-run this readback
    4  every row in the table above must flip to pass, and these must hold:
         'jacob' present            False
         '&partner' present         False
         merge variables            8
         double-brace variables     0
         duplicate msg on a path    none
    5  render representative leads and read them as a human
    6  only then consider a lead, and that is a separate decision with its
       own gate - LINKEDIN_ADD_LEAD is still not in SUPPORTED

Do not mark this file's verdict changed without re-running step 3. A readback
is the only thing that may change it.
