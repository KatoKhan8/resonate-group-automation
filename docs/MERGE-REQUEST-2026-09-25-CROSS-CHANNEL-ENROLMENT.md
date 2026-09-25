# LANE R - cross-channel LinkedIn enrolment for 491-498

**2026-09-25, reads only.** No provider write was made by this lane. The
transport was sealed before the first read and the seal was EXERCISED, not
merely installed: every run begins by calling `StopLeadInCampaign` and
`AddLeadsToCampaignV2` through the real transport and aborting unless both
are refused. 466 provider requests in total, itemised in section 9.

**This worktree was branched from `24acafff`, 37 commits behind master, and
was fast-forwarded to `76f29779` before any work was done.** The brief said
"current master"; it was not. Everything below is measured at `76f29779`,
which is the commit that carries the decision doc, the corrected
`stop_lead_in_campaign` docstring and `campaign_leads`' `member_id`.

The foreground session performs every write. The executable plan is
`work/laneR/ENROLMENT-PLAN-2026-09-25.md` with its machine-readable rows
beside it; both are gitignored, because they hold real people.

Everything here re-runs from `scripts/laneR/`.

---

## 0. The headline: the client has already enrolled this cohort, and the
number for tonight is ZERO

| the number | what it is | denominator |
|---|---|---|
| **805** | contacts carrying a `bison_lead_id` | the WHOLE STORE, not 491-498 |
| **774** | of those, under a record attributed to 491-498 | the actual cohort |
| **774** | of the 774 carrying a resolvable `/in/` profile url | 774 - 100% |
| **2.0%** | share of swept cohort people in NO LinkedIn campaign | **3 of 147 swept** |
| **~16** | projected survivors of the LinkedIn-collision gate | 774 x 2.0% |
| **~3-7** | projected survivors of all three person gates | see section 3 |
| **0** | enrollable TONIGHT under the gates as they are shipped | see section 5 |

**Of 147 cohort people swept, 142 are already in a LinkedIn campaign and 2
more could not be answered for.** Not our campaigns - the client's. The median
candidate is in **eleven** at once and one is in **nineteen**. Eight client
campaigns holding between 3,616 and 33,710 leads each blanket the cohort; the
largest has already sent 16,814 connection requests.

Lane P's precedent was one candidate in thirteen campaigns and called it the
reason the lane existed. On THIS population it is not the exception, it is
the rule, and the reason is structural: 491-498 are the people we picked out
of the client's own target market, and the client is working that market on
LinkedIn at a scale of 949,683 lead-slots.

**The second blocker is ours, not theirs.** Even the candidates the LinkedIn
estate leaves alone are refused by `collision.account_policy`, because every
one of them is mid-sequence on email by construction and that gate is
person-blind. See section 5: it is a real conflict between the shipped gate
and the operator's stated design, and it is not something to route around.

---

## 1. The population, verified rather than re-derived

The brief hands `805 store contacts carry a bison_lead_id` for 491-498 and
`805 of 805 also carry a linkedin field`. Both halves are true of the STORE.
Neither is true of 491-498.

**No contact in this store carries an email campaign id at all.** The keys on
a contact are `name, linkedin, email, email_source, sendable, primary, key,
title, persona, angle, verdict, mx, verification, bison_lead_id, first_name,
last_name, reoon, campaign_id_linkedin, linkedin_list_id, stopped, paused,
do_not_contact, heyreach_lead_id, heyreach_campaign_id`. There is a
`campaign_id_linkedin` and there is no email counterpart. Membership lives in
`campaigns.jsonl`, as `bison_campaign_id` -> `record_ids`, so the cohort is

    campaigns whose bison_campaign_id is in 491..498   (8 rows)
      -> their record_ids                              (681 records)
        -> those records' contacts                     (774 contacts)

| level | count |
|---|---|
| campaign rows for 491-498 | 8 |
| distinct records behind them | 681 |
| contacts under those records | **774** |
| of those, carrying `bison_lead_id` | 774 (100%) |
| of those, carrying a non-empty `linkedin` | 774 (100%) |
| of those, whose `linkedin` is a resolvable `/in/` url | **774 (100%)** |
| carrying `heyreach_lead_id` | **1** - the operator's test identity |
| carrying `campaign_id_linkedin` in our store | 151 |
| stopped / paused / do-not-contact in our store | 10 |

Per campaign: 491 -> 300 records, 492 -> 181, 494 -> 68, 495 -> 52, 496 -> 31,
493 -> 19, 497 -> 16, 498 -> 14.

**Where the other 31 of the 805 are.** 16 sit under records attributed to
451/481/484/485/487/489 - earlier campaigns, not this cohort. 15 sit under a
record attributed to no campaign at all, and **all 15 of those carry a
`linkedin` value that is not a profile url**, so the 100% claim does not hold
for the store-wide 805 either. It holds for the 774, which is the number this
plan uses.

**503/504/505 are out of scope and the store cannot even enumerate them.**
All three campaign rows carry `record_ids: []`. Section 6.1 of the decision
doc says no profile was ever sourced for the 09-07 list; the store agrees by
holding nothing. No discovery was attempted and none was spent on.

## 2. The gates, and why the order is the opposite of lane P's

Lane P wanted people in NO email campaign. This lane wants precisely the
people who ARE in one, and pairs them. So the email gate inverts, and a gate
lane P never needed appears: these people have been emailed, and some of them
have already answered.

| gate | question | route | excludes |
|---|---|---|---|
| H1 | already in ANY LinkedIn campaign, ours or the client's? | `/campaign/GetCampaignsForLead` | any campaign -> EXCLUDE; a 404 is UNVERIFIABLE, never absence |
| X1 | what does the email membership say? | `GET /leads/{id}` -> `lead_campaign_data`, filtered to 491-498 | `replied` -> EXCLUDE absolutely. `stopped` -> EXCLUDE (see below). `bounced`/`unsubscribed` -> EXCLUDE |
| M1 | is this profile that person at that company? | `/lead/GetLead` | surname or company disagrees -> REFUSED; provider will not name one -> UNVERIFIABLE |
| A1 | does the account rule permit it? | `collision.check_account` + `account_policy` + the client's `fatigue.account.max_active_contacts` | see section 5 |

**H1 runs FIRST here, and that is a cost decision.** It is one request and it
removes 98% of the population; asking the email side first spends an
EmailBison read on people the LinkedIn estate has already spoken for.

**`unverifiable` is not a pass anywhere.** Every verdict starts at
`unverifiable` and only positive evidence moves it.

### 2a. `stopped` is excluded, and that is ISSUE-035 being honest

32% of a 40-person email sample read `stopped` in their 491-498 membership.
The word does not say whether we stopped them, they unsubscribed, or the
provider stopped them **on a reply** - and `reply_watch_loop` calls
`bison.stop_lead` on exactly that trigger, so a `stopped` row is as likely to
be somebody who answered as somebody we withdrew. Counting that as free
capacity is precisely the second message to somebody who already replied.
`collision.SUSPECT_STATUSES` already reaches HOLD on the same reasoning; this
lane reaches EXCLUDE, because a cross-channel pair is a new touch rather than
a continuation.

## 3. The collision measurement, and the control that could have made it a lie

The primary measurement is one sweep, one seed, one denominator:

| verdict | n | of 147 |
|---|---|---|
| `excluded:H1_already_on_linkedin` | 142 | 96.6% |
| `excluded:H1_unverifiable` (provider 404) | 2 | 1.4% |
| reached X1 | 3 | 2.0% |
| of those 3: `passes:person_gates` / `M1_refused` / `M1_unverifiable` | 1 / 1 / 1 | |

Corroborated by two earlier samples on different seeds: 33 email-live
candidates -> 32 excluded, and 30 sampled without regard to email state -> 30
of 30 excluded.

**Eight campaign ids appeared for every single person, which is also exactly
what an ignored filter looks like.** This vendor is documented to discard an
unrecognised filter key in silence and return the whole estate, which reads
as a result; a finding this size had to survive an attempt to destroy it.

| control | expectation | measured |
|---|---|---|
| C1 a well-formed profile url that cannot be in the estate | 0, or a refusal. Eleven campaigns means the filter is fiction | **404**, twice, on two different invented slugs |
| C2 a real profile in nothing | 0 campaigns, proving zero is reachable | **0 campaigns**, one candidate in the gate run |
| C3 four real profiles side by side | different sets | **identical sets of 11** |
| C4 how big are those campaigns | if huge, C3 is explained | 33,710 / 18,765 / 10,094 / 9,247 / 7,984 / 4,912 / 3,902 / 3,616 leads |

C3 on its own is the tell for an ignored filter. C1 and C2 kill that reading:
the route resolves the profile (a fake one 404s) and it can return zero (a
real one did). What remains is the honest explanation - a handful of client
campaigns large enough to contain our entire cohort. The largest has sent
16,814 connection requests and taken 263 replies.

**Their status in those campaigns is not dormant.** Across the memberships
read: 197 `Pending`, 91 `InSequence`, 57 `Excluded`, 15 `Finished`, 4
`Failed`; and the campaigns themselves 200 `PAUSED`, 162 `IN_PROGRESS`, 2
`FINISHED`. Ninety-one live sequence memberships is the client mid-conversation
with our cohort right now.

**Our store could not have told us any of this.** 151 of the 774 carry a
`campaign_id_linkedin`, which would have suggested 19% enrolled. The provider
says 98%. Exactly one contact in the store carries `heyreach_lead_id`, so the
store is structurally incapable of the answer and was never asked for it.

## 4. The member id, and a class of it that no stop has ever been validated
against

The binding is correct and it was checked from both ends rather than
inherited:

    /campaign/GetLeadsFromCampaign -> member_id     (linkedInUserProfile.linkedin_id)
    /lead/GetLead                  -> linkedin_id
    12 of 12 people, the two routes AGREE

So `lead_profile()` is a sound source for `heyreach_lead_id`, and the plan
binds it there. Nothing binds `linkedInUserProfileId`, which is what HeyReach
support named and which 404s.

**But the shape is not what the validation assumed.** The live-validated stop
of 2026-09-25 matched a NUMERIC member id. Across 75 real campaign rows:

| shape | rows | validated against a stop? |
|---|---|---|
| numeric | 28 (37%) | **yes**, 2026-09-25 |
| `imp_` prefixed | 47 (63%) | **never** |

An `imp_` id written into `heyreach_lead_id` would make every future
cross-channel stop for that person a call on a value the provider has never
accepted - and `StopLeadInCampaign` answers that with *"the lead is not
present in the campaign you are trying to modify"*, which reads as a
membership problem and sends the reader looking in the wrong place entirely.
That is the exact failure the hard rule exists to prevent, one layer deeper
than the rule states it.

**Measured, and the news is good: the `imp_` class is the client's alone.**
All **157** leads across the **39** HeyReach campaigns attributable to us
carry a **numeric** member id; zero are `imp_`. The one contact in the store
carrying `heyreach_lead_id` is numeric, and it is the identity the stop was
validated on. So leads we add resolve properly.

**But the read has to happen AFTER the enrolment, and that is not obvious.**
The one candidate in the sweep who was in no LinkedIn campaign returned an
`imp_` id from `/lead/GetLead`. A profile the estate has not resolved yet
answers with the unresolved form; the numeric id appears once the lead is in
a campaign. So binding `heyreach_lead_id` from a pre-enrolment `lead_profile`
call - the natural place, since that is the same call M1 already makes -
stores the wrong value for every single person, and the plan says so
explicitly: bind from `campaign_leads(campaign_id)` after the fact, and
**assert the shape** rather than trusting it. An enrolment whose stored id is
not numeric is recorded as one whose stop path is unproven, and is not counted
as complete.

## 5. THE BLOCKER THAT IS OURS: the account gate cannot see a cross-channel
pair

Rule 6 of the brief: *"A cross-channel pair is the same person on both
channels - that is the design - but a SECOND person at the same account is
governed by the rule."*

`collision.account_policy` cannot draw that distinction. Its first clause is

    if account.get("anyone_in_sequence"):
        return STOP, "somebody at this account is mid-sequence right now"

`anyone_in_sequence` is computed over every person at the account with no
regard to WHO. Every candidate in this cohort is mid-sequence on email by
construction, so that person's own row sets the flag and the gate STOPs the
account **because of the very person it is being asked about**. Measured: the
single candidate who survived H1, X1 and M1 in the gate sample was then
STOPped for exactly this reason.

**This is not a gate to route around.** The clause is right for its original
question - a colleague mid-sequence is a real collision and blanket-exempting
it would remove the only account-level protection there is. The fix is to
make the flag person-aware and leave everything else untouched:

* recompute `anyone_in_sequence` **excluding the paired person's own
  membership rows**, and STOP on any OTHER person at the account being
  mid-sequence, exactly as today;
* the `answered` clause keeps **no exemption of any kind** - a person who has
  replied is out, on either channel, including the pair themselves;
* the pair consumes the account's `max_active_contacts` budget as two active
  contacts, which is what the config's own comment already says it means:
  *"One email track plus one LinkedIn track is what the providers permit."*

**`fatigue.account.max_active_contacts` is `2` on master today**, not 3. At 2,
a cross-channel pair FILLS the account and no colleague may be added. The
brief says it is being raised to 3; that change has not landed in
`config/clients/productive.yaml` at `76f29779`, so this plan is built at 2 and
names what 3 would change: one additional colleague per paired account, and
nothing about the pair itself.

Until the person-scoped flag exists, **the number that can be enrolled tonight
without bypassing a shipped safety gate is zero.** That is stated as the
answer rather than engineered around.

## 6. Seats, read and not assumed

`/li_account/GetAll`, one request, today:

| | |
|---|---|
| seats returned | 41 |
| active with valid auth | 33 |
| configured daily connection limit | 40 x20, 25 x6, 23, 22, 19, 18, 17, 15, 15 |
| seats that cannot take 25 | **7** - 15, 15, 17, 18, 19, 22, 23 |
| sum of `min(25, seat limit)` | **779** |
| sum of `min(10, seat limit)` - the rule | **330** |

Independently reproduced from lane P, from the provider, not copied. 825 was
never available.

**No seat row carries a timezone.** Every key on every one of the 41 rows was
scanned for `time` or `zone` and none matched. So "07:00-23:00 seat-local"
cannot be verified from provider truth, and HeyReach exposes no schedule read
route either. What this plan does: it names the **prospect's** timezone,
derived from the record's region, sets it at `/campaign/Create` (the only
moment a schedule can be set at all), and states plainly that if the operator
means the seat's own local time, that value must come from the roster
attestation and not from the provider.

## 7. Packs and the connection note

681 accounts behind the cohort. Lane O's union cache covers **128 (18.8%)**;
its shippable set covers **114 (16.7%)**, of which **108** carry
`anchor_grounded >= 7` and **6** carry `anchor_grounded == 0`. 11 rest on one
word.

So for **83% of this cohort's accounts there is no pack fact at all.** Lane O
proved copylint rule 1 is mostly fake - a stranger's pack passes it up to
91.8% of the time while the anchor matches the wrong company zero times - so
a rule-1 pass on an ungrounded account is a category word, not a specific.

The rule this plan applies: **a connection note may assert something specific
about an account only when `anchor_grounded >= 7`.** Every other account gets
the neutral opener, which asserts nothing and is honest about it. Notes are
hard-capped under 280 characters and the cap is asserted per rendered note,
not assumed from a template.

## 8. The standing risk, restated because a lift does not remove it

GLM's review of the account rule: the gate reads `rec["events"]`, and the
store holds **one** `push_marked` against the provider's **2,319** sends.
**131 accounts pass that gate today only because their send history is absent
from the only source the gate reads.**

Cross-channel pairs are precisely the population where that costs a second
message to somebody who already replied, and this lane is that population in
full. Two things follow, and both are in the plan:

1. **Nothing in this lane's funnel reads `rec["events"]`.** X1 asks the
   provider for the membership status and A1 asks `collision.check_account`,
   which walks the provider's leads. The store's event array is not consulted
   for any eligibility decision, so the 131-account hole cannot widen through
   this door.
2. **The ledger write-back is still the fix and is still not done.** Anything
   that later reads `rec["events"]` about these people - a fatigue check, a
   report - is reading a near-empty array. This lane does not repair that and
   does not claim to.

A second finding in the same family: **9 of 40 sampled candidates (22.5%) are
also in an EmailBison campaign OUTSIDE 491-498** that our store has no record
of. Lane P measured the same class at 23 of 207 and it is the reason "in no
email campaign" may never be concluded from our store. Here it means a paired
person may be receiving the client's email as well as ours.

## 9. Request volume

Client business hours, so it was kept small deliberately and the full walk is
scheduled for tonight instead.

| read | requests |
|---|---|
| HeyReach seats | 1 |
| EmailBison campaign state, 491-498 | 8 |
| EmailBison per-lead email state (two samples) | 90 |
| HeyReach `GetCampaignsForLead` | 223 |
| HeyReach `GetLead` | 66 |
| HeyReach `GetLeadsFromCampaign` (member-id shapes, our 39 campaigns) | 50 |
| HeyReach `GetOverallStats` (the eight blanket campaigns) | 8 |
| `collision.check_account` | 17 |
| **total** | **466** |

Against the 5,079 a lane ran in business hours this morning and was flagged
for. The remaining 627 people are **~1,000 requests** and belong after hours;
`scripts/laneR/sweep.py` is checkpointed every 25 people so a run interrupted
by the end of that window resumes instead of re-spending.

One defect in that script was found by its own arithmetic and fixed: it keyed
progress by `record_id`, and 774 contacts sit under 681 records, so a 150-person
run reported 147. It now keys per person. The superseded state file is kept
rather than deleted, and marked superseded, so nobody builds on it.

## 10. What would have made this a false pass

| the trap | what was done |
|---|---|
| taking 805 as the cohort | joined through `campaigns.jsonl`; it is 774, and 15 of the other 31 have no profile url at all |
| "not in a LinkedIn campaign" from our store | never asked the store. It says 19% enrolled; the provider says 98% |
| 66-of-67 believed because it was dramatic | four controls run against it. A fake profile 404s and a real one returns zero, so neither a refusal nor an absence is being read as the other |
| `unverifiable` counted as a pass | it excludes, at H1 and at M1 both |
| a seat capacity assumed | `/li_account/GetAll` read per seat; 7 of 33 contradict 25 |
| "seat-local" asserted | every key on all 41 seat rows scanned; there is no timezone field, and it is reported as unverifiable rather than assumed |
| binding the member id to `linkedInUserProfileId` | bound to `linkedInUserProfile.linkedin_id`, cross-checked between two routes on 12 people, and the SHAPE recorded - 63% of the estate's rows are a class no stop has ever been validated against |
| a pack fact that is a category word | `anchor_grounded >= 7` required; 83% of the accounts have no pack at all and get the neutral opener |
| a worktree's empty `work/` read as an empty store | every store read is against the production checkout by absolute path via `scripts/laneR/boot.py`, which refuses to run if the files are absent |
| a read-only claim that was never tested | the seal is exercised before every run: two real write routes are called through the transport and the run aborts unless both are refused |
| routing around the account gate to produce a number | not done. The number is zero and the fix is specified instead |

## 11. What the operator has to decide

1. **Whether this cohort is enrollable at all.** 98% of it is in the client's
   own LinkedIn campaigns, 91 memberships live. This is a conversation with
   the client about who owns which channel for which person, not an
   engineering task.
2. **The person-scoped account flag** (section 5). Without it the answer for
   any cross-channel pair, in this cohort or a future one, is zero.
3. **`max_active_contacts` 2 -> 3.** Not landed. At 2 a pair fills the account.
4. **The `imp_` member-id class** (section 4). Ours are all numeric, so this
   is not blocking tonight, but any lane that stops a lead it did not add is
   on unvalidated ground.
5. **"Seat-local"** is unanswerable from the provider. Name the source.

## 12. What this lane did NOT do

* No provider write of any kind - no list, no campaign, no lead, no stop.
* No discovery spend on 503/504/505, and no attempt to enrol them.
* No claim about the existing campaigns' sending windows: unreadable by
  construction, on both providers.
* No claim that the agency do-not-contact index cleared anybody -
  `work/agency-dnc.jsonl` does not exist, so that gate watches nothing and is
  reported as vacuous rather than as a pass.
* No edit to `config/.env`, `src/providers/*` or `scripts/*_watch_loop.py`.
* The fix in section 5 is SPECIFIED, not applied. It changes a live safety
  gate and belongs to a session that owns that file.
