# HeyReach list estate — 2026-09-16

**TASK-175.** Read-only enumeration against the provider, timestamped
`2026-09-16T04:57:14Z`. The account sees 99 lists and 83 campaigns.

## 1. Every list the account can see

99 lists total. 42 are bound (attached to at least one campaign). 57 are
unattached as of the timestamp above. 2 are Resonate's; 97 are the client's.

### Resonate's lists

| List ID | Name | Leads | Bound? | Campaign(s) | Created |
|---------|------|-------|--------|-------------|---------|
| 933603 | RESONATE - PRODUCTIVE LINKEDIN PRODUCTION V1 | 0 | **BOUND** | 599020 (FINISHED) | 2026-09-13 |
| 940797 | RESONATE - STAGING PROBE - DO NOT USE | 1 | **UNBOUND** | none | 2026-09-15 |

933603 is attached to campaign 599020, which is FINISHED. Staging into
933603 is staging into a campaign — the list is NOT safe.

940797 is unattached. It holds one real lead (a schema probe from TASK-158,
profile `li:b2472f5b2458`). The list is unattached as of the timestamp; it is
not "safe" in any durable sense.

### Client lists — bound (42 lists)

| List ID | Name | Leads | Campaigns | Campaign statuses |
|---------|------|-------|-----------|-------------------|
| 926076 | PRODUCTIVE - CANARY - 2026-09-09 | 1 | 594061 | PAUSED |
| 906686 | Software Development - EU - Firstliners, Batch 1 | 1000 | 565765 | IN_PROGRESS |
| 903006 | Interested Email CLEANED | 7 | 583549 | DRAFT |
| 902890 | Maybe CLEANED | 71 | 583490 | DRAFT |
| 902839 | Hot Leads CLEANED | 11 | 583536 | DRAFT |
| 885955 | Ana L approved | 24 | 567758 | FINISHED |
| 885952 | Anita S approved | 26 | 567754 | FINISHED |
| 885950 | Bojan S approved | 25 | 567752 | FINISHED |
| 885949 | Dean B approved | 14 | 567750 | FINISHED |
| 885948 | Djordje J approved | 24 | 567747 | FINISHED |
| 885945 | Dorota P approved | 15 | 567745 | FINISHED |
| 885937 | Ivan M approved | 40 | 567743 | FINISHED |
| 885934 | Jelena M approved | 17 | 567736 | FINISHED |
| 885930 | Jelena I approved | 29 | 567738 | FINISHED |
| 885927 | Jovana K approved | 11 | 567733 | FINISHED |
| 885925 | Katarina K approved | 22 | 567730 | FINISHED |
| 885922 | Lazar L approved | 11 | 567727 | FINISHED |
| 885917 | Lucija Bilic approved | 16 | 567721 | FINISHED |
| 885914 | Lucija Bakic approved | 23 | 567715 | FINISHED |
| 885908 | Luka N approved | 22 | 567708 | FINISHED |
| 885905 | Marina I approved | 19 | 567703 | FINISHED |
| 885903 | Marko D approved | 21 | 567701 | FINISHED |
| 885901 | Martina H approved | 28 | 567689 | FINISHED |
| 885900 | Mihovil approved | 13 | 567698 | FINISHED |
| 885899 | Milan B approved | 7 | 567693 | FINISHED |
| 885896 | Mina r approved | 16 | 567683 | FINISHED |
| 885894 | Snjezana M approved | 2 | 567681 | FINISHED |
| 885884 | Vladimir H approved | 13 | 567677 | FINISHED |
| 876837 | Marko C approved | 256 | 565223 | FINISHED |
| 876826 | Luka C approved | 278 | 565211 | FINISHED |
| 876807 | Kresimir approved | 275 | 565198 | FINISHED |
| 876802 | Jakov approoved | 180 | 565196 | FINISHED |
| 876790 | Fran approved | 185 | 565195 | FINISHED |
| 876768 | Bruno approved | 285 | 565193 | FINISHED |
| 876757 | Bojan R approved | 273 | 565187 | FINISHED |
| 876751 | Bernarda approved | 192 | 562830 | FINISHED |
| 730071 | Productive employees warmup | 178 | 470035,470040,470037,470038,470010,470039 | all PAUSED |
| 727022 | inmails | 218 | 467951,523938 | PAUSED, DRAFT |
| 668409 | PRODUCTIVE - OMEGA | 33710 | 429679,523983,473854,429680,523932,523922,467366,523987 | 3 IN_PROGRESS, 5 PAUSED |
| 632277 | PRODUCTIVE - MARKETING AGENCIES - EU - SAFE TO SEND EMAIL - DOUBLE DOWN | 11128 | 428676,523997,524000,523993,406850,428674 | 3 IN_PROGRESS, 3 PAUSED |
| 605364 | PRODUCTIVE - AUSTRALIA - ICP - FILTERED OUT OF 200K LEADS | 5133 | 388942,523896,388939,388938 | 1 IN_PROGRESS, 3 PAUSED |
| 605361 | PRODUCTIVE - EUROPE - ICP - FILTERED OUT OF 200K LEADS | 44157 | 523913,388947,388949,388951 | 1 IN_PROGRESS, 3 PAUSED |

Two further large lists (605359 with 50469 leads bound to 3 campaigns, and
605355 with 50563 leads bound to 6 campaigns) follow the same pattern. The
full bound list is in the script output.

### Client lists — unattached as of 2026-09-16T04:57Z (57 lists)

The 57 unattached lists include connection dumps, reply archives, DNC
lists, report snapshots, and empty test lists. None of them can send,
because none of them is attached to a campaign. A person with account
access can attach any of them at any time, at which point every lead in
the list becomes a lead in a campaign.

Notable unattached client lists by size:

| List ID | Name | Leads |
|---------|------|-------|
| 605355 | PRODUCTIVE - USA 1ST - ICP - FILTERED OUT OF 200K LEADS | 50563 |
| 605359 | PRODUCTIVE - USA 2ND - ICP - FILTERED OUT OF 200K LEADS | 50469 |
| 605361 | PRODUCTIVE - EUROPE - ICP - FILTERED OUT OF 200K LEADS | 44157 |
| 668409 | PRODUCTIVE - OMEGA | 33710 |
| 770000 | Productive replies - June 2026 | 14341 |
| 632277 | PRODUCTIVE - MARKETING AGENCIES - EU | 11128 |

Wait — those are bound, not unattached. The large unattached ones are:

| List ID | Name | Leads |
|---------|------|-------|
| 917481 | all replies august | 1490 |
| 860390 | all connections | 6251 |
| 770000 | Productive replies - June 2026 | 14341 |
| 721802 | Message sent | 2859 |
| 720924 | May report | 361 |
| 656698 | Messages sent | 1179 |
| 647668 | Replied | 364 |
| 638778 | DNC | 698 |
| 599847 | CANADA | 2378 |
| 599841 | UK | 5552 |
| 599833 | PRODUCTIVE ICP ZVONIMIR MARCH 5TH | 696 |
| 565376 | s | 0 |

Plus 45 smaller connection-dump lists (60-750 leads each) and a handful of
test/empty lists. The full enumeration is in the script output.

## 2. How attachment is discovered

**From the list side:** the `campaignIds` field on the list object, returned
by both `POST /list/GetAll` and `GET /list/GetById?listId=`. It is an array
of campaign ids. Empty array means unattached.

**From the campaign side:** the `linkedInUserListId` field on the campaign
object, returned by both `POST /campaign/GetAll` and `GET /campaign/GetById?campaignId=`.
It is a single integer (or null). The campaign-side field is singular — a
campaign holds at most one list.

**Cost of discovery:**

- `/list/GetAll` pages at 100 per page. 99 lists = 1 request. Free (read).
- `/campaign/GetAll` pages at 100 per page. 83 campaigns = 1 request. Free.
- `/list/GetById` is one GET per list. Only needed when a specific list's
  binding must be checked at the moment of a write — `liststaging.assert_list_safe`
  does this.
- `/campaign/GetById` is one GET per campaign. Same pattern.

The full enumeration (all 99 lists with their campaign attachment) costs
2 paged reads plus 42 campaign lookups for the bound lists. About 44
requests total. All free. All read-only.

**Attachment CANNOT be answered by walking campaigns alone.** A list that
is not attached to any campaign does not appear in any campaign's
`linkedInUserListId`. You would have to walk all 83 campaigns and conclude
"this list id was not named" — which is a negative proof and costs 1 page
of campaigns. The list-side `campaignIds` field is the positive proof and
costs one GET.

## 3. One-to-many in both directions

### Can a list be attached to more than one campaign? **YES.**

Measured directly in this enumeration:

| List | Campaigns attached to |
|------|----------------------|
| 668409 (PRODUCTIVE - OMEGA, 33710 leads) | **8** campaigns |
| 605355 (USA 1ST, 50563 leads) | **6** campaigns |
| 632277 (EU SAFE TO SEND, 11128 leads) | **6** campaigns |
| 730071 (employees warmup, 178 leads) | **6** campaigns |
| 605361 (EUROPE, 44157 leads) | **4** campaigns |
| 605364 (AUSTRALIA, 5133 leads) | **4** campaigns |
| 599816 (prod, 1142 leads) | **4** campaigns |
| 727022 (inmails, 218 leads) | **2** campaigns |

A list attached to 8 campaigns means every lead in it is in 8 campaigns
simultaneously. This is the provider's design, not a defect.

### Can a campaign hold more than one list? **NO.**

The campaign object carries `linkedInUserListId` (singular), not
`linkedInUserListIds`. Every one of the 81 campaigns holding a list holds
exactly one. The 2 campaigns without a list (567683 and 565765 — wait,
565765 holds 906686; let me correct: the 2 campaigns without lists are
the ones whose `linkedInUserListId` is null/absent) hold none.

**Correction:** 81 of 83 campaigns carry a `linkedInUserListId`. The 2 that
do not are campaigns that were created without a list or had it removed.
A campaign holds **exactly one list or zero**.

### What this means for TASK-172's predicate

The predicate "list is unbound" (`campaignIds == []`) is necessary and
sufficient for list-level staging safety. But the many-to-one direction
(list → many campaigns) means that the moment a list is attached, it can
be attached to multiple campaigns simultaneously, and the blast radius is
the union of all of them. The predicate refuses on ANY attachment, which
is correct.

## 4. Recommended staging list for the canary

**Recommendation: create a new list.**

Three options evaluated:

### Option A: Reuse 940797

- **For:** already exists, unbound, Resonate-owned, proven writable (TASK-158)
- **Against:** holds 1 real lead (li:990379eddf6b, added by schema probe). A
  canary readback would have to account for the pre-existing member. The
  list name says "DO NOT USE", which is a signal to any human looking at
  the estate. The name cannot be changed (no rename route exists).
- **Verdict:** usable but carries baggage.

### Option B: Create a new list

- **For:** clean slate, no pre-existing leads, name can be chosen to
  communicate purpose ("RESONATE - CANARY STAGING V1"). The create route
  (`/list/CreateEmptyList`) is established and `heyreach.create_list` is
  implemented. An empty list reaches nobody.
- **Against:** a provider write. Permanent (no delete route). Needs Claude's
  call to execute.
- **Verdict:** the right answer. Costs one write, buys a clean safety
  argument.

### Option C: Reuse 933603

- **For:** already exists, Resonate-owned
- **Against:** BOUND to campaign 599020 (FINISHED). Staging into it is
  staging into a campaign. Not safe. The campaign is FINISHED, which means
  it describes leads the campaign already held, not one added afterwards —
  but the list is still attached, and the safety predicate is `campaignIds == []`.
- **Verdict:** refused. Not safe by the predicate this repository already
  wrote.

**Recommendation: Option B.** Create a new list named
`RESONATE - CANARY STAGING V1`. The write is `/list/CreateEmptyList`,
which is on `heyreach.WRITE_ROUTES` and is implemented in
`heyreach.create_list`. It is NOT in `providerwrites.SUPPORTED` — that is
an operator decision. The list is empty, reaches nobody, and the safety
argument is clean.

If Option B is declined, Option A (940797) is the fallback. The canary
readback must account for the pre-existing lead and the list name must
not mislead anyone into thinking it is disposable.

## 5. The binding step

### The path

    QUALIFIED -> LIST -> READBACK -> FINAL ELIGIBILITY -> CAMPAIGN -> SEND

Between LIST and CAMPAIGN, a list must become attached to a campaign. That
attachment is the moment staging becomes sending.

### Which provider operation performs it?

**`POST /campaign/Create`** with the `linkedInUserListId` body parameter.
This is the ONLY route that attaches a list to a campaign. There is no
separate "attach list to campaign" endpoint. The attachment happens at
campaign creation time, as part of the campaign object.

The implementation is `heyreach.create_campaign(name, list_id, ...)` in
`src/providers/heyreach.py`. The body parameter is `linkedInUserListId`.

### Does a verb for it exist in `providerwrites.py`?

The operation is declared as `LINKEDIN_CREATE_CAMPAIGN = "heyreach.create_campaign"`
in `providerwrites.OPERATIONS`. Its entry reads:

> "no documented route; POST /campaign/GetById already answers 405 and
> nothing suggests a create verb exists on the public API"

This is **stale**. The create route IS established: `/campaign/Create` is on
`heyreach.WRITE_ROUTES` and `heyreach.create_campaign` is implemented. The
entry has not been updated to reflect this.

### Is it in `SUPPORTED`?

**No.** `LINKEDIN_CREATE_CAMPAIGN` is NOT in `providerwrites.SUPPORTED`.
The tuple currently holds:

    LINKEDIN_PAUSE, EMAIL_PAUSE, EMAIL_STOP_LEAD,
    EMAIL_CREATE_CAMPAIGN, EMAIL_SET_SEQUENCE,
    LINKEDIN_SET_SEQUENCE, LINKEDIN_ADD_LEAD,
    LINKEDIN_START_EMPTY_FOR_STAGING

Creating a campaign (with its list attachment) is deliberately not enabled.

### What this means for the canary

The canary path needs:

1. A list (created via `/list/CreateEmptyList` — also not in SUPPORTED)
2. Leads added to the list (via `/list/AddLeadsToListV2` — not in SUPPORTED)
3. A campaign created with the list attached (via `/campaign/Create` — not
   in SUPPORTED)
4. The campaign started (via `/campaign/StartCampaign` — deliberately sealed)

None of these are in `SUPPORTED`. The canary cannot be staged through this
system's write path without operator decisions to enable them. The list
staging primitive (`src/liststaging.py`) exists as the safety layer for
step 2, but it is not wired into `providerwrites.perform`.

The binding step (step 3) is the sharpest gate: it is the moment a list
becomes a campaign's list, and every lead in the list becomes a lead in
the campaign. It is correctly sealed.

## 6. The safety argument, stated precisely

An unbound list is unattached **as of 2026-09-16T04:57Z**. Nothing in the
provider prevents a person with account access from attaching it a minute
later, at which point every lead in it is a lead in a campaign.

**What detects a later attachment:** `liststaging.assert_list_safe(list_id)`
reads `heyreach.list_by_id(list_id)` and checks `campaignIds == []`
immediately before every add. This is a live provider read, not a
remembered state. It is the same shape as `_campaign_is_a_declared_staging_campaign`
— the provider truth at the moment of the write.

**What does NOT detect it:** the enumeration in this document. It is a
snapshot. A list reported as unbound here can be bound by the time anybody
acts on the report. The snapshot is evidence of what was, not permission
for what may be.

## 7. Campaigns without lists

2 of 83 campaigns have no `linkedInUserListId`:

| Campaign ID | Name | Status |
|-------------|------|--------|
| 594060 | PRODUCTIVE - CANARY - 2026-09-09 | DRAFT |
| 594057 | PRODUCTIVE - CANARY - 2026-09-09 | DRAFT |

Both are earlier DRAFT canary campaigns from 2026-09-09, created without a
list attached. They are not relevant to the current list estate but are
noted for completeness.

## Appendix: raw data

The full JSON enumeration of all 99 lists with their attachment state is
produced by `scripts/task175_enumerate_lists.py`. Run it to reproduce or
to get a fresh timestamp.
