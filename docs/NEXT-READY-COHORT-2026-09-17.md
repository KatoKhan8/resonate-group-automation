# NEXT READY COHORT - 2026-09-17

**Read-only.** Nothing was staged, activated, paused, re-approved or written.
Every provider call behind this document is a GET. The two live channels were
not touched:

| channel | campaign | provider state | leads | seat |
|---|---|---|---|---|
| HeyReach | 605732, list 944355 | IN_PROGRESS | 3 | 174892 |
| EmailBison | 487, workspace 10 | active | 10 | 2736 |

Produced by `scripts/next_ready_cohort.py`, which walks the contact-level part
of the `executionguard.authorize` ladder in the guard's own order and stops at
the first refusal.

## HEADLINE

    LINKEDIN_READY_NOW = 0
    EMAIL_READY_NOW    = 0

Not zero because the estate is empty. Zero because **every contact whose copy
is currently approved is either already live or sits on an account the
collision policy refuses**, and every contact on a clean account has no
approval.

The gap is one operator approval pass. After it:

    LINKEDIN_READY_NOW = 12   (7 after the channel-separation split below)
    EMAIL_READY_NOW    = 5

## WHAT WAS MEASURED, AND WHAT WAS NOT

The ladder below is `executionguard.authorize`, restricted to the gates that
are a fact about a **contact**. The campaign-level gates cannot be evaluated
for a batch that has no campaign row yet.

| # | gate | evaluated here | how |
|---|---|---|---|
| 0 | `copy` | yes | every step the channel's sequence needs renders through `cadence.expand_step` against the spec `executionguard._spec_for` resolves |
| 1 | `tenancy` | yes | record client == campaign client |
| 2 | `approval` | yes | `approval.fingerprint(step)` equals the fingerprint recorded on the step, for **every** required step |
| 2b | `campaign_approval` | **no** | property of a campaign row that does not exist yet |
| 3 | `readback` | **no** | a sealed, single-use provider diff; obtaining one would spend a read-back against a live campaign |
| 4 | `eligibility` | yes | `eligibility.decide(...)` on the first step |
| 4 | `suppression` | yes | intersection with `executionguard.SUPPRESSION_REASONS` |
| 4 | `copy_lint` / `claims` | yes | `lint.check_step`, `claims.check` |
| 4 | `fatigue` | yes | `fatigue.check(..., at=now)` |
| 4 | `collision` | yes | LinkedIn: `check_linkedin_profile(raw_linkedin, name, expect_workspace="productive")`. Email: `check_address(email, expect_workspace=10)` |
| 4 | `account_collision` | yes | `check_account(domain, expect_workspace=10)` + `account_policy`, **mandatory on both channels** |
| 5-7 | `sender`, `pilot_cap`, `stoppability`, `ledger`, `killswitch` | **no** | campaign-, seat- and day-level |

A contact this report calls READY is a contact whose **own** facts are clean.
The batch that stages it still has to pass the seven gates above marked "no".

### Two calls that had to be made exactly, and were

**The LinkedIn collision call takes the RAW value, the NAME and the SLUG.**
`collision.check_linkedin_profile(contact["linkedin"], contact["name"],
expect_workspace="productive")`. Canonicalising the URL first, dropping the
name, or passing the numeric workspace each returns `clear` on a profile the
guard refuses - the reasoning is recorded in `scripts/linkedin_ready_truth.py`
and this screen reuses it verbatim. It found one touched profile in this run
that a softer call would have certified.

**The approval gate is the FOUR-argument call.**
`approval.is_approved(rec, key, step_key)` with no fourth argument compares the
stored step to itself and agrees unconditionally. The difference is not
theoretical:

| channel | passes 3-arg `is_approved` | passes fingerprint equality |
|---|---|---|
| email | 23 | 10 |
| LinkedIn | 6 | 6 |

The thirteen email contacts the two forms disagree about are examined under
"The approval estate is not what it looks like" below.

---

## LINKEDIN

**TOTAL = 81** contacts carry at least one `li*` cadence step, across 68
records. (The estate holds 277 contacts in total; the rest have no LinkedIn
cadence at all.)

### 1. The counts

| bucket | n |
|---|---|
| READY_NOW | **0** |
| ALREADY_LIVE (list 944355) | 3 |
| NEAR_MISS - blocked only by something we can fix | 12 |
| SAFETY_BLOCKED - blocked by a real verdict | 66 |
| **total** | **81** |

### 2. First gate that stops each contact, ranked

| rank | first gate | n | share |
|---|---|---|---|
| 1 | `approval` | 66 | 81% |
| 2 | `copy` (a required step does not render) | 9 | 11% |
| - | *(passes every contact-level gate)* | 3 | 4% |
| 3 | `account_collision` | 2 | 2% |
| 4 | `collision` | 1 | 1% |
| | **total** | **81** | |

`tenancy`, `suppression`, `copy_lint`, `claims` and `fatigue` stopped **nobody**
on this channel. Every record is `productive`; no contact is suppressed,
unsubscribed, stopped or replied; fatigue is `ok` for all 81.

Approval sub-reasons (the 66):

| why | n |
|---|---|
| no step carries an approval at all | 56 |
| only 1 of 5 steps carry an approval | 8 |
| only 3 of 5 steps carry an approval | 1 |
| only 2 of 5 steps carry an approval | 1 |

Copy sub-reasons (the 9) - `li4` is the step that most often fails to render:

| why | n |
|---|---|
| `li4` alone does not render | 5 |
| `li4`,`li5` | 1 |
| `li2`,`li5` | 1 |
| `li2`,`li4`,`li5` | 1 |
| `li2`,`li3`,`li4`,`li5` | 1 |

### 3. What is really underneath: the safety pass

The "first gate" above is the guard's order, and the guard asks for approval
before it asks whether anybody may be contacted at all. So the screen also asks
the safety questions of **everyone**, including the people the approval gate
stopped first. Of the 78 non-live contacts, 66 fail a safety verdict
independently of their approval state:

| rank | genuine safety verdict | n | share of blocked |
|---|---|---|---|
| 1 | account STOP - somebody at this account is mid-sequence right now | 26 | 39% |
| 2 | account HOLD - a campaign there ended early (`stopped`) and the status does not say who ended it | 15 | 23% |
| 3 | account STOP - somebody there has already replied or been marked interested | 11 | 17% |
| 4 | person-level LinkedIn collision `touched` - our own seat has messaged this profile | 9 | 14% |
| 5 | person-level LinkedIn collision `unknown` - the provider read failed after 3 attempts | 3 | 5% |
| 6 | person-level LinkedIn collision `in_sequence` - they have replied to us | 1 | 2% |
| 7 | account HOLD - an address at this account bounced | 1 | 2% |
| | **total** | **66** | |

**52 of the 66 are account-level, not person-level.** Person-level screening
would have cleared them. This is the account gate doing precisely what
`ACCOUNT-OUTREACH.md` says it is for, on the channel that cannot ask the
question itself (`collision.account_is_unanswerable`).

### 4. NEAR_MISS vs genuine safety

| | n | what would lift it |
|---|---|---|
| NEAR_MISS | **12** | an operator approval on `li1`-`li5`. Nothing else. |
| SAFETY_BLOCKED | 66 | an operator decision about a specific account or conversation, or a new provider read |

All 12 near-misses share the same profile: all five LinkedIn steps render,
`eligibility.decide` returns `held` with **exactly one** reason
(`held:draft_not_approved` or `held:approval_stale`), collision is `clear`,
account policy is `allow`, fatigue is `ok`, tenancy is correct.

Note what is **not** in the near-miss list: **generating the missing `li4`
copy unblocks nobody.** All 9 copy-blocked contacts sit on accounts that are
already STOP or HOLD. The same is true of the 3 `unknown` collisions - every
one of them is also on a STOP/HOLD account, so a successful re-read changes
no verdict.

### 5. The 12 near-misses

`account` is the hashed account identity; two pairs share an account.

| contact | account | persona | steps rendered | approvals now | collision | account | fatigue | tenancy | suppression |
|---|---|---|---|---|---|---|---|---|---|
| `ef849b390ce8` | `5aa13c5766c9` | economic_buyer | li1-li5 | none | clear | allow | ok | ok | none |
| `6c02a154a485` | `63084828d69e` | economic_buyer | li1-li5 | none | clear | allow | ok | ok | none |
| `f2db8143a14f` | `ad83ab4912c1` | economic_buyer | li1-li5 | none | clear | allow | ok | ok | none |
| `d65fbd4a0546` | `ad83ab4912c1` | champion | li1-li5 | 1 of 5, self-recorded | clear | allow | ok | ok | none |
| `bd751f563564` | `22cc5f977293` | economic_buyer | li1-li5 | none | clear | allow | ok | ok | none |
| `8f8f4d36f7fb` | `36ab1e71eb5e` | economic_buyer | li1-li5 | none | clear | allow | ok | ok | none |
| `67a98a612f22` | `36ab1e71eb5e` | champion | li1-li5 | none | clear | allow | ok | ok | none |
| `e77da95c0ff1` | `663c917ceea0` | economic_buyer | li1-li5 | 3 of 5, self-recorded | clear | allow | ok | ok | none |
| `3a835ed8c80d` | `77aa81931d66` | economic_buyer | li1-li5 | none | clear | allow | ok | ok | none |
| `41ec5334fda0` | `1f507fd7fba0` | economic_buyer | li1-li5 | 1 of 5, self-recorded | clear | allow | ok | ok | none |
| `b141afad2284` | `a3f981c16e38` | economic_buyer | li1-li5 | none | clear | allow | ok | ok | none |
| `4b7417723a27` | `3a34a4282c63` | economic_buyer | li1-li5 | none | clear | allow | ok | ok | none |

Email verification state is reported for completeness but is **not** a LinkedIn
gate - `eligibility._linkedin_checks` never consults it. Five of the twelve
(`d65fbd4a0546`, `8f8f4d36f7fb`, `67a98a612f22`, `3a835ed8c80d`,
`4b7417723a27`) are `unknown` or `accept_all_uncleared` on email and are
LinkedIn-only until verification clears.

### 6. ALREADY_LIVE (list 944355, campaign 605732)

| contact | account | persona | approvals | collision | account |
|---|---|---|---|---|---|
| `d0ce1ae856f3` | `035712846aff` | economic_buyer | 5 of 5, operator | clear | allow |
| `de937c48c811` | `7c559ffe3538` | champion | 5 of 5, operator | clear | allow |
| `3f848c9b2e22` | `7c559ffe3538` | champion | 5 of 5, operator | clear | allow |

These three still pass every contact-level gate today. Two of them share an
account, which the `account.max_active_contacts: 2` limit permits.

---

## EMAIL

**TOTAL = 51** contacts carry at least one `em*` cadence step, across 50
records.

### 1. The counts

| bucket | n |
|---|---|
| READY_NOW | **0** |
| ALREADY_LIVE (campaign 487) | 10 |
| NEAR_MISS | 5 |
| SAFETY_BLOCKED | 36 |
| **total** | **51** |

### 2. First gate that stops each contact, ranked

| rank | first gate | n | share |
|---|---|---|---|
| 1 | `approval` | 41 | 80% |
| 2 | `collision` | 10 | 20% |
| | **total** | **51** | |

The 10 stopped at `collision` are the 10 leads already on 487: `check_address`
finds their own lead row `in_sequence`. They collide with **themselves**, which
is why the screen classifies `already_live` before it classifies safety. They
are reported as ALREADY_LIVE, not as blocked.

`copy`, `tenancy`, `suppression`, `copy_lint`, `claims` and `fatigue` stopped
nobody. All 51 contacts render em1-em3, all 51 are `productive`, all 51 are
`verified` on email, and fatigue is `ok` for all 51.

Approval sub-reasons (the 41):

| why | n |
|---|---|
| no step carries an approval at all | 27 |
| **every step carries an approval but the fingerprint has moved on all 3** | 13 |
| only 1 of 3 steps carry an approval | 1 |

### 3. The safety pass

Of the 41 approval-blocked contacts, 36 fail a safety verdict as well:

| rank | genuine safety verdict | n | share of blocked |
|---|---|---|---|
| 1 | person-level address collision `touched` - this address has been emailed from this estate before | 20 | 56% |
| 2 | person-level address collision `in_sequence` | 7 | 19% |
| 3 | account HOLD - a campaign there ended early (`stopped`) | 3 | 8% |
| 4 | account STOP - somebody there is mid-sequence | 3 | 8% |
| 5 | account STOP - somebody there has replied or been marked interested | 3 | 8% |
| | **total** | **36** | |

Unlike LinkedIn, email is dominated by **person-level** history: 27 of 36 are
the address itself, not a colleague.

### 4. NEAR_MISS vs genuine safety

| | n | what would lift it |
|---|---|---|
| NEAR_MISS | **5** | an operator approval on `em1`-`em3`. Nothing else. |
| SAFETY_BLOCKED | 36 | an operator decision about a specific address or account |

All 5 are `verified`, `economic_buyer`, render em1-em3, are `clear` at person
level and `allow` at account level.

### 5. The 5 near-misses

| contact | account | persona | verified email | steps rendered | approvals now | collision | account | fatigue | tenancy | suppression |
|---|---|---|---|---|---|---|---|---|---|---|
| `ef849b390ce8` | `5aa13c5766c9` | economic_buyer | verified | em1-em3 | none | clear | allow | ok | ok | none |
| `6c02a154a485` | `63084828d69e` | economic_buyer | verified | em1-em3 | none | clear | allow | ok | ok | none |
| `e77da95c0ff1` | `663c917ceea0` | economic_buyer | verified | em1-em3 | none | clear | allow | ok | ok | none |
| `41ec5334fda0` | `1f507fd7fba0` | economic_buyer | verified | em1-em3 | none | clear | allow | ok | ok | none |
| `b141afad2284` | `a3f981c16e38` | economic_buyer | verified | em1-em3 | 1 of 3, self-recorded | clear | allow | ok | ok | none |

### 6. ALREADY_LIVE (campaign 487, workspace 10, sender 2736)

`f7b6a151a1d2`, `94f144ffc96b`, `e9bea5455e20`, `84814000e654`,
`6c8e101aba2f`, `34e079896a22`, `4838a4d16e62`, `31806b8899f9`,
`20f392465309`, `d1810dbaca5f` - all 10 carry operator approval on all three
steps and all 10 read `in_sequence` against themselves.

---

## THE APPROVAL ESTATE IS NOT WHAT IT LOOKS LIKE

Approvals recorded across the whole estate, by who recorded them:

| channel | recorded by an operator | recorded by this system (`by: "claude"`) |
|---|---|---|
| email steps | 30 (10 contacts x 3) | 69 (23 contacts x 3) |
| LinkedIn steps | 30 (6 contacts x 5, `operator-control-arm`) | 15 |

Two things follow, and the second is a latent hole rather than a today
problem.

**On email the fingerprint gate catches the self-approvals, by accident of
sequence shape.** Campaign 487 declares its own `cadence_steps`, in which `em1`
carries `template: persona_pain` and no `generated` flag, so
`cadence.expand_step` re-renders it from the template. The client's default
cadence marks `em1` `generated: true`, so it returns the stored words verbatim.
The 13 self-recorded email approvals were taken against the **generated**
rendering and are current under it; under 487's template-driven spec the
fingerprint moves and they fail. That is why 3-arg `is_approved` passes 23 and
fingerprint equality passes 10.

**On LinkedIn the fingerprint gate cannot catch them at all.** `li2`-`li5` are
`generated: true` in every sequence this client runs, so `expand_step` returns
the stored words and the fingerprint of a self-recorded approval stays current
for ever. `approval.fingerprint` answers "are these the words that were
approved"; it was never designed to answer "did a human approve them". Today no
contact has all five LinkedIn steps self-approved - the self-approvals cover 1,
2 or 3 steps - so none reaches READY. That is luck, not a gate.

If the next batch is screened by this ladder alone, **also screen
`approval.by`**, as `scripts/linkedin_ready_truth.py` already does with
`REQUIRED_APPROVER`. Attribution and fingerprint are different questions and
the estate needs both.

---

## THE EXACT NEXT BATCH

Nothing below is staged. This is the batch that would be staged once the
approval pass is done, and the sizing rules that shape it.

### Three limits shape it, and they are not the same limit

1. **`account.min_hours_between_first_touches: 72`** (`fatigue`). Two different
   people at one account cannot be opened on the same day. Two pairs in the
   LinkedIn near-miss list share an account, so one of each pair waits 72h.
2. **`pilot_caps.linkedin_per_day: 10`, `per_sender_per_day: 10`**
   (`pilotcaps`, enforced by the guard at gate 5). `email_per_day: 20`.
   Neither batch reaches these.
3. **`eligibility._separation` with `DEFAULT_MIN_SEPARATION_DAYS = 1`.** `li1`
   and `em1` are both cadence day 1, so a person pushed on one channel is
   `held:channel_separation` on the other. **Five people appear in both
   near-miss lists** - `ef849b390ce8`, `6c02a154a485`, `e77da95c0ff1`,
   `41ec5334fda0`, `b141afad2284`. They must be assigned to one channel, not
   both.

The split below gives each channel a batch: the five dual-eligible people go to
**email** (where they are the entire candidate pool), and LinkedIn takes the
remaining seven.

### LinkedIn - day 1 (5 contacts, 5 distinct accounts)

| contact | account | persona | needs |
|---|---|---|---|
| `f2db8143a14f` | `ad83ab4912c1` | economic_buyer | operator approval li1-li5 |
| `bd751f563564` | `22cc5f977293` | economic_buyer | operator approval li1-li5 |
| `8f8f4d36f7fb` | `36ab1e71eb5e` | economic_buyer | operator approval li1-li5 |
| `3a835ed8c80d` | `77aa81931d66` | economic_buyer | operator approval li1-li5 |
| `4b7417723a27` | `3a34a4282c63` | economic_buyer | operator approval li1-li5 |

### LinkedIn - day 4, after the 72h account spacing (2 contacts)

| contact | account | persona | held by |
|---|---|---|---|
| `d65fbd4a0546` | `ad83ab4912c1` | champion | second person at `ad83ab4912c1` |
| `67a98a612f22` | `36ab1e71eb5e` | champion | second person at `36ab1e71eb5e` |

### Email (5 contacts, 5 distinct accounts)

| contact | account | persona | needs |
|---|---|---|---|
| `ef849b390ce8` | `5aa13c5766c9` | economic_buyer | operator approval em1-em3 |
| `6c02a154a485` | `63084828d69e` | economic_buyer | operator approval em1-em3 |
| `e77da95c0ff1` | `663c917ceea0` | economic_buyer | operator approval em1-em3 |
| `41ec5334fda0` | `1f507fd7fba0` | economic_buyer | operator approval em1-em3 |
| `b141afad2284` | `a3f981c16e38` | economic_buyer | operator approval em1-em3 |

### Two cautions on the batch

**`pilot_caps.new_accounts_per_day: 5` WAS declared and enforced by nobody.
CLOSED 2026-09-17 - and the batch above is the thing it now refuses.**

When this was written `pilotcaps` defined the ceiling, no caller in `src/`
passed it to `require`, and `executionguard` asked only for
`linkedin_per_day`, `email_per_day` and `per_sender_per_day`. `check` listed
the rest as `unchecked` and nothing read that list, so `require` answered True
having examined one ceiling of seven.

Gate 5 now derives today's opened accounts from the durable ledger and refuses
the sixth, and `reserve` re-checks it inside the file lock. `require` will no
longer answer over a silence: it takes an exact `not_checking` acknowledgement,
so the next ceiling added to `CEILING` breaks every call site at the moment the
"who enforces this" decision is actually being made - which is the moment that
went unmade here.

**SO THE BATCH BELOW NO LONGER RUNS IN ONE DAY, AND THAT IS THE POINT.** The
two batches open 10 new accounts; staging will now refuse at the SIXTH with
`NotAuthorized("pilot_cap")`. Split them across two days, or raise the ceiling
deliberately. The count is per workspace and per calendar day, and it is NOT
channel-scoped - a LinkedIn invite and a cold email land on the same company on
the same morning, so they share the ceiling. A second contact at an account
already opened today does not consume it again.

**The five campaign-level gates still apply.** A new campaign row for either
batch needs its own `campaign_approval` (senders, limits, provider binding,
tenant and lead set), a fresh sealed `configdiff` read-back inside its 15-minute
TTL, a seat in the canonical roster that is active and healthy, a clear ledger
key, and the killswitch's last word. `providerwrites.is_supported` now answers
True for both pause operations, so the `stoppability` cap of
`UNSTOPPABLE_CHANNEL_CAP = 1` no longer binds - that is what makes a batch
larger than a canary possible at all.

---

## THE SINGLE HIGHEST-LEVERAGE THING

**An operator approval pass over 12 LinkedIn contacts and 5 email contacts -
17 approvals covering 75 steps - is the only action that converts anybody.**

It accounts for 100% of the convertible population on both channels:

| action | LinkedIn unblocked | email unblocked |
|---|---|---|
| operator approval on the near-miss lists | **12** | **5** |
| generate the missing `li4`/`li2`/`li5` copy (9 contacts) | 0 | - |
| re-read the 3 failed LinkedIn collision probes | 0 | - |
| clear email verification on the 4 unknown/accept-all near-misses | 0 (not a LinkedIn gate) | 0 |
| anything else | 0 | 0 |

Everything else in the estate - 66 LinkedIn contacts and 36 email contacts - is
held by a verdict that says the account or the person has already heard from
us, is mid-conversation, or has answered. Those are not engineering tasks.
Lifting any of them is an operator decision about one named account, taken with
the conversation in front of them.

## HOW TO REPRODUCE

    py -3 scripts/next_ready_cohort.py
    py -3 scripts/next_ready_cohort.py --json work/tmp/next-cohort.json

Read-only. Identifiers in this document are `sha256(record_id:contact_key)[:12]`
and `sha256(domain)[:12]`, per the repository convention enforced by
`tests/test_fixture_hygiene.py`.
