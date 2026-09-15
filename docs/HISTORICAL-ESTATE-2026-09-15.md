# Historical Estate Measurement — 2026-09-15

**TASK-153 deliverable.** Four measurements against the 550-record snapshot,
with provider-side reads for email send status and LinkedIn conversation
history.

**Snapshot stamp:** `2026-09-15T17:52:12+00:00 from master cf23154 550 records`
**Workspace:** PRODUCTIVE (id 10, org_unit 118832)
**Scripts:** `scripts/task153_snapshot_analysis.py`, `scripts/task153_provider_reads.py`
**Provider calls:** READ ONLY. 29 × `GET /leads/{id}`, 2 tenant scope reads,
68 × HeyReach conversation search. No write route was called.

---

## 1. The 13/16 split re-confirmed at 550 records

**The split holds exactly.** Of 29 contacts carrying a `bison_lead_id`:

### 13 never emailed (effectively cold)

All 13 are campaign 481. The campaign was PAUSED before it sent anything.

**The proving field:** `overall_stats.emails_sent = 0` on `GET /leads/{id}`.

| Hash | Lead ID | Campaign 481 status |
|---|---|---|
| h:239ca5ce4597 | 203715 | sending_paused |
| h:6a24728e581e | 203707 | stopped |
| h:4db650d002c6 | 203711 | sending_paused |
| h:047f20f91f81 | 203708 | sending_paused |
| h:df6c1a9a828b | 203709 | sending_paused |
| h:e9279d198e8b | 203716 | sending_paused |
| h:51f85a8c5e44 | 203710 | sending_paused |
| h:8c78def950d5 | 203718 | sending_paused |
| h:ecf632bb449b | 203713 | sending_paused |
| h:47a5f182ce08 | 203714 | sending_paused |
| h:b928c2e8b5fd | 203712 | stopped |
| h:54df979f2961 | 203717 | stopped |
| h:6f73ba16dd46 | 203719 | stopped |

10 sending_paused, 3 stopped. Zero emails, zero replies, zero opens.

### 16 actually emailed (NOT cold)

| Hash | Lead ID | Total emails | Campaigns | Status |
|---|---|---|---|---|
| h:e196bb262403 | 135163 | 14 | 265, 328, 352, 481 | stopped/finished |
| h:e94e4034018c | 144582 | 10 | 274, 327, 352, 481 | stopped/finished |
| h:5a933ccca87b | 133292 | 21 | 264, 274, 327, 352, 481 | finished |
| h:02d4bb5076b1 | 199963 | 1 | 352 | in_sequence |
| h:14204392c2b1 | 142476 | 5 | 274, 327 | bounced |
| h:3b355bdfb4fa | 136059 | 5 | 266, 352, 481 | finished |
| h:28b77bd041ba | 168853 | 9 | 328, 352, 481 | stopped/finished |
| h:cce930f64073 | 173033 | 9 | 328, 352 | in_sequence/finished |
| h:158c987fbcb5 | 142762 | 21 | 274, 327, 352, 481 | finished |
| h:2b09be450aa4 | 174331 | 8 | 328, 331 | in_sequence/finished |
| h:3e415b66c5ec | 168654 | 21 | 328, 330, 352, 481 | finished |
| h:788f51decef9 | 168616 | 9 | 328, 352, 481 | stopped/finished |
| h:8c85d73f4c94 | 176926 | 8 | 328, 330 | in_sequence/finished |
| h:b283357f9cc7 | 141805 | 21 | 274, 327, 352, 481 | finished |
| h:458449f4139f | 203657 | 1 | 451 | finished |
| h:748002ca4e79 | 140550 | 21 | 274, 327, 352, 481 | finished |

Zero replies across all 16 at the provider. Two currently in_sequence
(Agnieszka Sito in 352, Aurelie Bollinne in 328). One bounced (Jeremy Green).

**Conclusion:** The 13/16 split from TASK-147 holds exactly at the 550-record
snapshot. No new bison_lead_id contacts were added between the two snapshots.

---

## 2. LinkedIn conversation history across the eligible pool

**Tenant scope:** org_unit 118832, 41 seats from provider, 50 campaigns visible.
Every campaign this key can see belongs to the same org unit — single tenant.

**68 verified contacts checked.** The search is by first name (the only field
HeyReach's `searchString` filters on), matched locally on profile slug, scoped
to tenant seats.

### 7 of 68 have prior LinkedIn conversation history (10.3%)

#### 1 REPLIED

| Hash | Name | Seat | Messages | Last message | They replied |
|---|---|---|---|---|---|
| h:e196bb262403 | Izabelle A | h:seat_174803 | 2 | 2026-05-07 | **YES** |

This contact has a LinkedIn conversation where the prospect replied. The
last message was from them, on 2026-05-07. This is the check that caught
one contact at the provider gate (per the task description). The reply was
on the LinkedIn channel, not email — and the email side shows 14 emails
sent with 0 replies. The two channels disagree about whether this person
has answered.

#### 6 TOUCHED (no reply)

| Hash | Name | Seat | Messages | Last message |
|---|---|---|---|---|
| h:02d4bb5076b1 | Agnieszka Sito | h:seat_201978 | 6 | 2026-09-04 |
| h:28b77bd041ba | Tobiasz Bierka | h:seat_174822 | 3 | 2026-07-25 |
| h:3e415b66c5ec | Nena Berfelo | h:seat_174822 | 8 | 2026-09-03 |
| h:2467b68fd6f5 | Avigail Schlosser | h:seat_175455 | 1 | 2026-06-12 |
| h:08c025559404 | Christian Liesegang | h:seat_174845 | 1 | 2026-07-19 |
| h:748002ca4e79 | Jonathan Moisan | h:seat_174748 | 9 | 2026-08-30 |

All six are on the "actually emailed" list — they have both email and
LinkedIn history. The LinkedIn conversations are on 5 different seats,
showing this is not concentrated on one person's inbox.

### 59 of 68 clear (86.8%)

No conversation matching their profile slug was found on any tenant seat.

### 2 broad match (2.9%)

The first-name search returned more than 300 results — too many to
conclude anything from a local slug match. These contacts cannot be
certified clear from this method alone.

### Cross-reference with email history

| | LinkedIn CLEAR | LinkedIn HISTORY | LinkedIn BROAD |
|---|---|---|---|
| **Email: actually emailed (16)** | 12 | 4 | 0 |
| **Email: never emailed (13)** | 12 | 0 | 1 |
| **No bison_lead_id (39)** | 35 | 3 | 1 |

4 contacts have BOTH email sends AND LinkedIn conversations. 3 contacts
with no bison_lead_id have LinkedIn history despite no email history.

---

## 3. Prior reply inventory

### Canonical state (events array)

**Zero `reply_received` events in the entire 550-record estate.** The
classification machinery (`replies.classify`, `accountpolicy.apply_reply`)
is fully wired and has never fired. No reply has been imported.

### Provider state (EmailBison)

**Zero replies across all 29 bison_lead_id contacts.** `overall_replies = 0`
on every single one. The 16 who were emailed received a combined 196 emails
and produced 0 replies.

### Provider state (HeyReach)

**One reply on LinkedIn.** h:e196bb262403 (Izabelle A) has a 2-message
LinkedIn conversation where `they_replied = true`, last message
2026-05-07. This is NOT recorded in canonical state — no `reply_received`
event, no contact state transition. The estate does not know this person
replied on LinkedIn.

### Log array

**Zero reply entries in any record's log array.** The `log` carries 1,708
`linkedin_note` entries (generated copy, not confirmed sends) and 4,037
`lint_failed` entries, but no reply evidence.

### Where prior replies ARE recorded

| Source | Field | Count | What it proves |
|---|---|---|---|
| EmailBison | `overall_stats.replies` | 0/29 | No email replies at provider |
| HeyReach | `lastMessageSender = CORRESPONDENT` | 1/68 | One LinkedIn reply, not in canonical state |
| Canonical | `events[]` type `reply_received` | 0/277 | Import has never fired |
| Canonical | `contact["unsubscribed"]` | 0/277 | No unsubscribe recorded |
| Canonical | `contact["stopped"]` | 0/277 | No stop recorded |

**The gap:** The HeyReach reply on h:e196bb262403 is a real reply that
canonical state does not know about. `eligibility._replied()` would block
this contact if the reply were imported. It is not imported, so the
pipeline does not know this person has answered.

---

## 4. The honest total: cold / warm / never

### Pool: 277 contacts on 425 active records

| Category | Count | Evidence |
|---|---|---|
| **Unverified (cannot contact yet)** | 209 | `verification.state != "verified"` |
| **Verified, no history (genuinely cold)** | 36 | Verified + no bison emails + no LinkedIn history |
| **Verified, bison never-emailed (effectively cold)** | 13 | `overall_stats.emails_sent = 0`, campaign 481 |
| **Verified, LinkedIn history only (warm)** | 3 | HeyReach conversation, no email history, no bison |
| **Verified, email history (warm)** | 12 | `overall_stats.emails_sent > 0`, no LinkedIn match |
| **Verified, both email + LinkedIn (warm)** | 4 | Both provider histories |
| **Verified, LinkedIn reply (warm, special)** | 1 | h:e196bb262403, they replied on LinkedIn |
| **Suppressed / must-not-contact** | 0 | No suppression signals anywhere |
| **LinkedIn broad match (unknown)** | 2 | Name too common to certify clear |
| **TOTAL** | **277** | |

### The three-way split

**Cold (genuinely reachable, no prior contact): 49**
- 36 verified, no history at all
- 13 never-emailed bison contacts (campaign 481)

**Warm (prior contact exists, needs different treatment): 20**
- 16 actually emailed (various campaigns, 0 replies)
- 3 LinkedIn-only history (no email)
- 1 LinkedIn reply (h:e196bb262403 — the one that was caught at the gate)

**Must never contact: 0**
- No suppressed contacts
- No agency DNC matches
- No unsubscribed contacts
- No stopped contacts

**Unknown (cannot certify): 2**
- Broad name match on LinkedIn
- 209 unverified contacts (not cold, not warm — unevaluable)

### What this means for the eligible pool

Of 68 verified contacts:
- **49 are cold** (72%) — no prior contact on any channel
- **19 are warm** (28%) — prior contact on at least one channel
- **0 must never be contacted**
- **2 are unknown** (broad match)

Of the 49 cold, 13 carry a `bison_lead_id` that currently holds them out
of the email cohort on a false assumption (they were never emailed). If
those 13 are released, the cold pool grows from 36 to 49 — a 36%
increase.

### The warm contacts are NOT interchangeable

The 19 warm contacts fall into three distinct categories that the current
pipeline treats identically:

1. **Emailed, no reply (16):** These people received up to 21 emails and
   did not answer. They are not cold — but they are also not engaged.
   Sending them more of the same is the definition of fatigue.

2. **LinkedIn touched, no reply (3):** Someone on the client's team
   started a LinkedIn conversation that went unanswered. The contact has
   seen the client's name. A cold email to this person would pretend
   nobody has spoken.

3. **LinkedIn replied (1):** This person answered. They are warm in a
   fundamentally different way from the other 18. They are a conversation,
   not a prospect. Holding them out is right; treating them the same as
   the 16 who ignored 21 emails is wrong.

---

## Summary of findings

### The four answers

1. **13/16 split confirmed at 550.** The 13 never-emailed contacts are all
   campaign 481 (paused before sending). The 16 actually emailed have
   between 1 and 21 emails across older campaigns. Zero replies at the
   provider on either side.

2. **7 of 68 verified contacts have LinkedIn conversation history** on the
   client's 41 seats. One replied (h:e196bb262403, 2 messages, last
   2026-05-07). Six were touched without reply. 59 are clear. 2 are
   unresolvable (broad name match).

3. **Zero replies in canonical state.** The one LinkedIn reply at the
   provider (h:e196bb262403) is not imported. `eligibility._replied()`
   would block it if it were. The email side has 0 replies across 196
   sent emails.

4. **Cold: 49, Warm: 19+2, Never: 0.** Of 68 verified contacts, 72% are
   genuinely cold. The 13 never-emailed bison contacts are effectively
   cold and currently held out on a false assumption. The 19 warm contacts
   are three different kinds of warm, and the pipeline does not
   distinguish them.

### The number that matters

**49 verified contacts are cold and reachable.** That is 36 with no history
plus 13 never-emailed bison contacts. The 13 are held out by
`build_control_cohort.eligible_contacts()` on the assumption they were
contacted. They were not.

**7 contacts have LinkedIn history the pipeline does not read.** One of
them replied. The reply is at the provider and not in canonical state. If
the pipeline does not learn about it from a provider read, it will treat
this person as cold.

### What has changed since TASK-139

| Finding | TASK-139 (300 records) | TASK-153 (550 records) |
|---|---|---|
| Contacts | 92 | 277 |
| Verified contacts | 92 | 68 |
| bison_lead_id | 29 | 29 |
| 13/16 split | discovered | confirmed |
| LinkedIn history checked | 0 (no provider reads) | 7 of 68 |
| Reply evidence | 0 | 1 (LinkedIn, not imported) |
| Cold/warm/never | not computed | 49/19+2/0 |

### The snapshot problem

The stamp is `2026-09-15T17:52:12+00:00 from master cf23154`. The
provider-side reads (Parts 1 and 2) are live — they hit the actual
EmailBison and HeyReach estates. But the cohort membership is read from
the snapshot. Numbers may have moved since.

---

*Resolved 2026-09-15 against snapshot stamp
`2026-09-15T17:52:12+00:00 from master cf23154 550 records`. Read-only.
No write route was called. Scripts: `scripts/task153_snapshot_analysis.py`,
`scripts/task153_provider_reads.py`. Results: `scripts/task153_results.json`.*
