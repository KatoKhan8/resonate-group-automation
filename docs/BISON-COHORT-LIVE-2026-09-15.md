---
title: "EmailBison Cohort — resolved against the live snapshot"
task: "TASK-147"
date: "2026-09-15"
snapshot_stamp: "2026-09-15T17:52:12+00:00 from master cf23154 550 records"
builds_on:
  - "docs/EMAILBISON-PRODUCTION-COHORT-2026-09-15.md"
  - "docs/BISON-API-CAPABILITY-MAP-2026-09-14.md"
  - "docs/BISON-ATTRIBUTION-BOUNDARY-2026-09-15.md"
  - "docs/COHORT-HEADROOM-2026-09-15.md"
---

# EmailBison Cohort — Live Resolution

**TASK-147 deliverable.** Four questions answered against the 550-record
snapshot, with provider-side reads for every `bison_lead_id` contact and
account-level collision checks for every domain in the cold cohort.

**Snapshot stamp:** `2026-09-15T17:52:12+00:00 from master cf23154 550 records`
**Workspace:** PRODUCTIVE (id 10)
**Scripts:** `scripts/task147_cohort_live.py`, `scripts/task147_never_emailed_collision.py`
**Provider calls:** READ ONLY. No write route was called.

---

## Question 1: Who is actually cold on email, right now?

### Record-level partition (550 records)

| Partition | Records | Contacts |
|---|---|---|
| Cold email (verified, no bison_lead_id) | 38 | 39 |
| Prior outreach (bison_lead_id, no reply in log) | 29 | 29 |
| Bison with reply evidence | 0 | 0 |
| Unverified, neither | 483 | — |
| **SUM** | **550** | |

### What moved since TASK-145 (300-record snapshot)

| Partition | TASK-145 (300) | TASK-147 (550) | Delta |
|---|---|---|---|
| Cold email | 26 | 38 | +12 |
| Prior outreach (bison) | 29 | 29 | 0 |
| Unverified | 245 | 483 | +238 |

The estate grew by 250 records. All 250 landed in the unverified bucket.
The cold cohort grew by 12 records (26 → 38). The prior-outreach count is
unchanged at 29 — no new contacts were added to EmailBison between the two
snapshots.

### Contact-level counts

- 39 contacts in the cold cohort (verified email, no bison_lead_id)
- 29 contacts with bison_lead_id (all have verified email)
- The two groups do not overlap by construction

---

## Question 2: Were the 29 with a bison_lead_id ever actually EMAILED?

### The answer is split, and TASK-145's assumption was half wrong

TASK-145 found campaign 481 PAUSED with 0 sends and campaign 451 COMPLETED
with 1 send, and concluded "probably no" for most of the 29. The provider
says otherwise: **13 were never emailed, 16 were.**

### The proving field

`GET /leads/{id}` returns `overall_stats.emails_sent`. When that field is 0,
no email was ever sent to that lead in any campaign. The per-campaign
breakdown in `lead_campaign_data[].emails_sent` confirms which campaign the
lead was added to and whether it sent.

### 13 never emailed (effectively cold)

All 13 are campaign 481. The campaign was PAUSED before it sent anything.

| Name | Lead ID | Domain | Campaign 481 status |
|---|---|---|---|
| Jacob Faertz | 203715 | ogpartner.dk | sending_paused |
| Janie Karas | 203707 | px-6a518e690008 | stopped |
| Rik De Veirman | 203711 | px-2a51e132bab4 | sending_paused |
| Brian Price | 203708 | acqcom.com | sending_paused |
| Ranjan Damodar | 203709 | px-a8ca1565fdd1 | sending_paused |
| Collette Savoie | 203716 | portsidemarketing.com | sending_paused |
| Al Scornaienchi | 203710 | agency59.ca | sending_paused |
| Paula Savage Hansen | 203718 | savagebrands.com | sending_paused |
| Michelle Payne-witten | 203713 | mischacommunications.com | sending_paused |
| Jennie Johnson | 203714 | mypersonalestatesale.com | sending_paused |
| Christine Xoinis | 203712 | ethoscreate.com | stopped |
| Jason Baker | 203717 | roaringmedia.co | stopped |
| Ray Kingman | 203719 | semcasting.com | stopped |

**The field that proves it:** `overall_stats.emails_sent = 0` and
`lead_campaign_data[0].emails_sent = 0` for every one. Campaign 481 status
is either `sending_paused` (10) or `stopped` (3). A lead created but never
emailed is not a contacted lead.

### 16 actually emailed (NOT cold)

| Name | Lead ID | Total emails | Campaigns |
|---|---|---|---|
| Izabelle A | 135163 | 14 | 265 (stopped), 328 (finished), 352 (finished) |
| Claudia Papa | 144582 | 10 | 274 (stopped), 327 (finished) |
| Rachele Crumpler | 133292 | 21 | 274 (finished), 327 (finished), 352 (finished) |
| Agnieszka Sito | 199963 | 1 | 352 (in_sequence) |
| Jeremy Green | 142476 | 5 | 274 (bounced), 327 (bounced) |
| Devon Spector | 136059 | 5 | 352 (finished) |
| Tobiasz Bierka | 168853 | 9 | 328 (stopped), 352 (finished) |
| Aurelie Bollinne | 173033 | 9 | 328 (in_sequence), 352 (finished) |
| David Liljegren | 142762 | 21 | 274 (finished), 327 (finished), 352 (finished) |
| Andreas Alex | 174331 | 8 | 331 (finished) |
| Nena Berfelo | 168654 | 21 | 328 (finished), 330 (finished), 352 (finished) |
| Agnieszka Chrobot | 168616 | 9 | 328 (stopped), 352 (finished) |
| Erjen Rijnders | 176926 | 8 | 330 (finished) |
| Caleb Crail | 141805 | 21 | 274 (finished), 327 (finished), 352 (finished) |
| Hussein Samnani | 203657 | 1 | 451 (finished) |
| Jonathan Moisan | 140550 | 21 | 274 (finished), 327 (finished), 352 (finished) |

These 16 contacts have real send history across the client's older campaigns.
They are NOT cold. Two are currently `in_sequence` (Agnieszka Sito in
campaign 352, Aurelie Bollinne in campaign 328). Two bounced (Jeremy Green).
The rest finished their sequences.

### The consequence

The addressable email cohort is NOT 29 (all bison_lead_id) and NOT 26
(TASK-145's cold count from the old snapshot). It is:

    39 cold contacts (verified, never in EmailBison)
  + 13 never-emailed bison contacts (campaign 481, effectively cold)
  = 52 effectively cold contacts

The 16 actually-emailed contacts are excluded from any cold cohort. They
have been contacted and the standing engagement-hygiene rule applies.

---

## Question 3: What does the account-collision rule do to the email cohort?

### Cold cohort (38 records, 39 contacts)

`collision.check_account` was run on all 38 unique domains, cached per
domain, against workspace PRODUCTIVE (id 10).

| Verdict | Domains | Records | Contacts |
|---|---|---|---|
| ALLOW | 8 | 8 | 8 |
| STOP | 16 | 16 | 16 |
| HOLD | 14 | 14 | 15 |
| **Total** | **38** | **38** | **39** |

**31 of 39 contacts rejected at the account level (79.5%).**

The breakdown of rejections:

- **STOP — mid-sequence** (8 domains): adc.de, directmail.com, e-2.at,
  eliassen.com, interest-media.com, medicalvision.de, metrosolver.com,
  remerge.io, studiopax.io, upperonestudiosinc.com
- **STOP — replied/interested** (6 domains): 2ton.com, cgcreative.com,
  citycubes.be, grayloon.com, hypercrew.pl, yesandagency.com
- **HOLD — stopped campaign** (11 domains): 8ms.com, automotiveonly.com,
  azonetwork.com, backbone.media, brandiq.com, chiefmedia.com, invnt.com,
  mediafederation.org.au, px-355075e3f546, prdirect.com, seismicproductions.com,
  smegateway.com.au, waynemedia.com
- **HOLD — bounced** (1 domain): chicochamber.com

The 8 ALLOW domains: digitalthirdcoast.com, feddirect.com, inmobi.com,
ritway.com, skyad.com, thecommunity.ca, viralityllc.com, wearejsa.com.

### Never-emailed bison contacts (13 contacts)

Same check on their 13 domains:

| Verdict | Count | Contacts |
|---|---|---|
| ALLOW | 9 | ogpartner.dk, px-2a51e132bab4, acqcom.com, px-a8ca1565fdd1, portsidemarketing.com, agency59.ca, savagebrands.com, mischacommunications.com, mypersonalestatesale.com |
| HOLD | 4 | px-6a518e690008, ethoscreate.com, roaringmedia.co, semcasting.com |
| STOP | 0 | — |

**9 of 13 survive.** The never-emailed group has a much better collision
profile than the cold cohort, because campaign 481 was assembled from
younger inventory that the client's older campaigns never touched.

### Combined survival

| Pool | Total | Survive ALLOW | Survive % |
|---|---|---|---|
| Cold cohort (verified, no bison) | 39 | 8 | 20.5% |
| Never-emailed bison (campaign 481) | 13 | 9 | 69.2% |
| **Combined** | **52** | **17** | **32.7%** |

**17 contacts are both effectively cold AND account-clear.** That is the
number the email campaign has to work with.

---

## Question 4: What cohorts fall out, and are they worth separating?

### The honest answer: the data does not support cohort separation

TASK-140 found signal was 100% null on the LinkedIn side. The email side is
the same:

| Dimension | Coverage (38 cold records) | Notes |
|---|---|---|
| industry | 100% | populated |
| employees | 100% | populated |
| headcount_signal | 100% | populated |
| revenue | 89% | populated |
| employee_range | 8% | too sparse to cohort on |
| signal | **0%** | null — no signal field populated |
| angle (record) | **0%** | null at record level |

At contact level:

| Dimension | Coverage (39 cold contacts) |
|---|---|
| title | 100% |
| linkedin | 100% |
| persona | 69% |
| angle | 62% |

### What the ICP flags say

Most cold contacts are under the client's stated 20-employee minimum or
geo-excluded:

    5  geo outside client's stated markets
    2  11 employees, under the client minimum of 20
    2  5 employees, under the client minimum of 20
    2  6 employees, under the client minimum of 20
    2  geo excluded by client: India
    1  3 employees, under the client minimum of 20
    1  19 employees, under the client minimum of 20
    1  4 employees, under the client minimum of 20
    1  16 employees, under the client minimum of 20

### The cohort proposal

With 17 contacts surviving all gates and no signal dimension populated,
cohort separation is not viable. The PRODUCTION-SCALE-POLICY contract says
~50 where inventory supports it and consolidation over proliferation. 17 is
one cohort, not multiple.

**One CONTROL cohort of 17 contacts.** The validated fallback copy, which
asserts nothing specific, so the cohort is for READING the result. No
CHALLENGER arm: a challenger needs per-contact evidence for its claims and
the signal field is null. A campaign that asserts something about a group
with no evidenced dimension is asserting nothing.

| Cohort | Size | Arm | Dimension | Basis |
|---|---|---|---|---|
| Email cold | 17 | CONTROL | None (signal null) | Validated fallback copy |

The 8 from the cold cohort and 9 from the never-emailed group share one
thing: they are verified, cold, and account-clear. They do NOT share a
signal, an industry cluster, or a persona pattern. The cohort is "nobody
else rejected them," which is a necessary condition but not a hypothesis.

### What would make cohorts readable

1. **Signal population.** The signal field is null for all 38 cold records.
   Until records carry a signal (hiring, growth, leadership change, etc.),
   there is nothing to cohort on. This is a discovery/enrichment problem,
   not a campaign problem.

2. **More inventory.** 17 contacts is below the ~50 target. The 20,944-domain
   estate is the answer (per COHORT-HEADROOM-2026-09-15.md), but expanding
   it requires ICP-qualified records with verified emails, which is a
   discovery-phase investment.

3. **Stopped-campaign resolution.** 14 of 38 cold-cohort domains are HOLD
   because a stopped campaign's status is ambiguous. If those could be
   resolved (the client's own pause vs. an unsubscribe vs. a provider stop),
   some would become ALLOW. That is a data question, not an engineering one.

---

## Summary of findings

### The four answers

1. **Who is cold:** 39 verified contacts with no EmailBison history, plus 250
   new unverified records that grew the estate from 300 to 550.

2. **Were the 29 emailed:** Split. 13 never emailed (campaign 481, 0 sends,
   proven by `overall_stats.emails_sent = 0`). 16 actually emailed across
   older campaigns. The 13 are effectively cold; the 16 are not.

3. **Account collision:** 31 of 39 cold contacts rejected at account level
   (79.5%). 4 of 13 never-emailed rejected (30.8%). **17 contacts survive
   all gates.**

4. **Cohort proposal:** One CONTROL cohort of 17. No signal dimension is
   populated, so no CHALLENGER arm is supportable. The cohort is "nobody
   rejected them," which is necessary but not a hypothesis.

### The number that matters

**17 contacts are deployable on email right now.** That is the number the
campaign has to fit inside. It is below the ~50 target but above the canary
threshold of 3. It is enough to learn from, and the learning is what matters
at this stage — the first email campaign's job is to produce data, not
volume.

### What changed since TASK-145

| Finding | TASK-145 | TASK-147 |
|---|---|---|
| Snapshot size | 300 | 550 |
| Cold records | 26 | 38 |
| Cold contacts | 26 | 39 |
| Prior outreach | 29 (assumed not emailed) | 29 (13 not emailed, 16 emailed) |
| Addressable after collision | unknown | 17 |
| Signal coverage | 100% null (LinkedIn) | 100% null (email, same) |

### The snapshot problem

The stamp is `2026-09-15T17:52:12+00:00 from master cf23154`. This is
fresher than TASK-145's stamp (`2026-09-14T21:52:15Z`, 300 records) but is
still a snapshot, not the live queue. Numbers may have moved since. The
provider-side reads (Q2, Q3) are live — they hit the actual EmailBison
estate — but the cohort membership is read from the snapshot.

---

*Resolved 2026-09-15 against snapshot stamp
`2026-09-15T17:52:12+00:00 from master cf23154 550 records`. Read-only. No
write route was called. Scripts: `scripts/task147_cohort_live.py`,
`scripts/task147_never_emailed_collision.py`.*
