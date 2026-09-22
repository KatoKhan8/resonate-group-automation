# Operator authorization — 2026-09-22 — activate 491-498, allow a note-less request

Recorded verbatim. Nothing below the grant reinterprets it.

---

OPERATOR AUTHORIZATION, 2026-09-22, Zvonimir:

    activate 491-498 and allow the note-less connection request

---

## What each half authorizes, stated as the change it licenses

### 1. `bison.activate` covers the eight batch campaigns

`_AUTHORIZED_EMAIL_CAMPAIGNS` held two entries — 487 and 489. It now holds
ten. Each new entry is PINNED to the provider id the canonical row is already
bound to, so the row and the grant have to agree:

    (491, productive-email-batch1-kresimir)   (495, ...-tomislav)
    (492, productive-email-batch1-bernarda)   (496, ...-bojan)
    (493, productive-email-batch1-ivan)       (497, ...-jakov)
    (494, productive-email-batch1-fran)       (498, ...-luka)

**THIS IS THE VERB THAT MAKES A CAMPAIGN SEND.** 151 real people receive a
first step from it. Everything else about them was already finished: two
independent fresh verifications each, MX open, collision cleared against the
client's own LIVE estate, copy rendered from 489's approved words and
approved under the batch-1 grant, client approval via snapshot
PRODUCTIVE-2026-09-07, 154 attested mailboxes bound, caps set per campaign,
and a sending window per timezone cohort.

What this does NOT widen: `_NEVER_ACTIVATE` still refuses 481 and 485, the
client's own 327/328/352 are still refused by the first check, and every
campaign created after this line is still refused until somebody names it.

### 2. A `CONNECTION_REQUEST` may carry no note

`validate_sequence_for_write` refused a payload with no non-empty `messages`
entry on MESSAGE, INMAIL **and** CONNECTION_REQUEST alike, on the grounds
that it "sends a blank".

That is true of a MESSAGE and an INMAIL — a person receives an empty letter.
It is NOT true of a CONNECTION_REQUEST: LinkedIn sends the request with no
note, which is what happens every time somebody clicks Connect without
writing anything, and it is what Productive's best-performing campaign does
at **13.6% acceptance over 951 requests** (565765).

So the rule is NARROWED to the two node types where an empty payload really
is a blank message. It is not skipped, and CONNECTION_REQUEST keeps every
other check: payload present, delay, branch shape, termination.

## What is still NOT authorized by this

- **HeyReach activation.** `heyreach.activate` still names campaign 604869
  and nothing else. The 33 LinkedIn campaigns stay DRAFT and issue no
  connection request until that is a separate decision.
- Any write to 487 or 489, which the batch-1 grant already excluded.
- A second batch beyond the pacing rule, which the CONTINUOUS grant already
  governs.

---

# Amendment — 2026-09-22 — HeyReach activation

Recorded verbatim.

    AUTHORIZED: widen HeyReach activation to the 33 batch campaigns created
    last night (list them by id in the authorization record), check hard
    stops per seat, activate, read back status and connection-request
    counters per campaign. Connection requests follow the graph's own
    timing; report "enrolled is not requested".

## The thirty-three, by id and seat

Read from the provider 2026-09-22, all DRAFT at the time of this record.
Each is `RESONATE PRODUCTIVE LI B1 SEAT <seat>` and names exactly one seat.

    613724 / 116968      613737 / 174742      613750 / 181653
    613725 / 116973      613738 / 174748      613751 / 181658
    613726 / 116988      613739 / 174797      613752 / 191848
    613727 / 116989      613740 / 174803      613753 / 201959
    613728 / 119588      613741 / 174810      613754 / 201978
    613729 / 125748      613742 / 174822      613755 / 208242
    613730 / 125775      613744 / 174892      613756 / 208253
    613731 / 129082      613746 / 175455      613757 / 212356
    613732 / 139699      613747 / 175552      613761 / 174845
    613733 / 143105      613748 / 177751
    613734 / 159259      613749 / 179527
    613735 / 169600
    613736 / 174332

**No other HeyReach campaign is covered.** 604869 keeps its own separate
grant, and the client's own campaigns — 565765, 523983, 524002 and the rest
of the estate on the shared key — are refused by the same check that refuses
an unnamed EmailBison campaign.

## What activation means on this channel

A DRAFT campaign has issued nothing. Started, it begins working its list at
the seat's own pace: **10 connection requests per seat per day**, and the
graph's own timing decides everything after that — a 3-hour wait before the
first message on the accepted branch, five days between messages, five days
before each profile view.

**ENROLLED IS NOT REQUESTED.** 151 leads sit on 33 lists. Starting the
campaigns does not issue 151 connection requests; it lets each seat begin
issuing up to ten a day against its own four or five leads, and LinkedIn
decides whether each is accepted.
