# The snapshot, measured in three buckets: 811 undecidable, 716 of them ALLOW

TASK 0060. Lane `task-suppression-2026-10-14`, worktree
`Desktop/wt-suppression-2026-10-14`, on top of `3b560deaf`.

**No provider call was made.** Every byte below came off disk. No suppression
applied, no campaign touched, nothing resumed or activated, no write to
production `work/`, no push to master. `UNKNOWN_IS_NOT_A_PASS` is still `True`
and nothing here changed it.

---

## 0. The premise, checked first

The task says the blacklist snapshot "is still open". **It is half open.**
TASK 0010 built the snapshot and measured §6a by count; what it did not
produce is the thing section 3 of this task asks for - the three buckets by
name - and it did not state the drift risk at all. So: section 1 and 2 below
are a RE-VERIFICATION of 0010 rather than new work, and sections 3 and 4 are
new. Saying which is which matters, because a re-verification that quietly
presents itself as a fresh finding is how a number gets believed twice.

**One premise of 0010 did not survive.** It excluded `work/heartbeat/bison-*.json`
as "campaign-level only". That is true of the watch events - 5,560 of them now,
across 22 files, and **0 carry any lead key**, re-checked here - but it is not
true of the heartbeats. `state.blanks.already` carries per-lead rows with a
`lead` id and a `status`. 20 heartbeat files, 95 distinct lead ids, 165
distinct `(lead, status)` pairs, written minutes ago rather than 21 days ago.
They are still not added as a snapshot source, for a measured reason rather
than the stated one - see section 4.

---

## 1. Can the provider blacklist be read from disk

**No. Re-checked, not cited.**

| checked, this task | result |
|---|---|
| `/blocklist/emails`, `/blocklist/domains` | **404** - `docs/BISON-API-ROUTE-EVIDENCE-2026-09-15.md:612-613` |
| `/unsubscribes`, `/suppressions`, `/blocklist`, `/do-not-contact` | **404** - `scripts/reengagement_provider_confirmed.py:510-513` |
| a blacklist route declared in `src/providers/bison.py` | **none.** The only two hits for `blocklist\|blacklist\|unsubscribes\|do-not-contact\|suppression` are comment lines at 1375 and 1403 |
| any file under production `work/` whose name suggests a provider blacklist | **none.** Five name matches, and every one is ours: four GLM run logs and `review/SUPPRESSION-PROPOSAL-2026-10-12.json`, which is our own 94-person proposal derived from the reply feed and says so in its own `authority` field |

**The authority that would supply it is EmailBison, through a route it does
not expose.** There is no second source. ContactOut, Reoon and Deliverable
answer deliverability, which is a different question - and 0010 already
measured them disagreeing with the provider's own send result on three
addresses.

So what is measured below is the blacklist's **effect**, per lead, which is
what §6a was built to take.

---

## 2. The snapshot, and what each file actually covers

749 addresses, six files, joined on `bison_lead_id`. Regenerated this task and
**identical to 0010's**: every one of the six sources is byte-for-byte and
mtime-for-mtime what it was, so the snapshot is reproducible and nothing new
has arrived.

New in this task: the time range each file **covers**, which is not its mtime.
An mtime says when a reader last wrote the file down. It says nothing about how
old the facts inside are, and that is the whole drift question.

| file | mtime (written) | the rows themselves cover | rows | with a timestamp |
|---|---|---|---|---|
| `stage/pc-leads.jsonl` | 2026-09-24T18:12:20 | 2026-04-04 → **2026-09-24T15:24** | 2,111 | 2,111 |
| `stage/pc-sends.jsonl` | 2026-09-24T18:12:21 | 2026-04-04 → **2026-09-30T14:04** | 9,454 | 9,454 |
| `stage/pc-lead-sends.jsonl` | 2026-09-24T18:27:49 | 2026-04-04 → **2026-09-29T11:51** | 20,221 | 20,221 |
| `stage/reengagement-inventory.jsonl` | 2026-09-23T21:05:31 | 2026-04-04 → **2026-09-23T20:47** | 2,081 | 2,081 |
| `lead-observations.jsonl` | 2026-09-13T09:28:53 | 2026-09-11 → **2026-09-13T09:28** | 2 | 2 |
| `queue.jsonl` (the join key) | 2026-10-03T20:41:37 | 2026-09-08 → **2026-10-03T20:19** | 1,584 | 28,671 events |

0 damaged lines anywhere. 0 declared sources absent. 216 queue records carry no
event at all, which is why the queue range is reported over events and labelled
that way.

**Two things that table says and a list of mtimes does not.**

* The two send files reach into **2026-09-30**, six days past their own mtime,
  because `sent_at` is absent on an unsent row and the fallback is
  `scheduled_date`, which is forward-looking. A range that crosses its own
  mtime is a schedule, not an observation - worth knowing before anybody reads
  "covers to 09-30" as "we know what happened on 09-30".
* **Nothing in the per-lead sources is newer than 2026-09-24T18:27.** That is
  the real age of the snapshot: 21 days, not the 12 days the newest mtime
  (`queue.jsonl`, which is our side) would suggest.

**Reach, unchanged and restated because it bounds everything below:** 2,081
provider lead ids are in stored state, 749 join to an address, **1,332 cannot
be turned into a person at all.** No provider read closes that - they are leads
at EmailBison we hold no queue contact for.

---

## 3. §6a measured by name - the three buckets

The four `reconcile` findings reproduce exactly, 3,008 calls and 3,008
consultations, `reconcile_all` agreeing as a control on its own key handling:

    provider_state_unknown              1,254
    suppressed_here_still_active_there    123
    blocked_at_provider_not_here            3
    agree                                   1

**That is not the question this task asks.** `UNKNOWN_THERE` collapses two
different situations with two different prices, so the estate is partitioned
again, on whether the SNAPSHOT had an answer:

| bucket | people | ALLOW here | BLOCK here |
|---|---|---|---|
| **MATCHED** - the snapshot carried a word §6a recognises | **570** | 540 | 30 |
| **NOT MATCHED** - the snapshot does not mention them | **564** | 562 | 2 |
| **NOT MATCHED** - no address to match on at all | **68** | 68 | 0 |
| **COULD NOT DECIDE** - in the snapshot, every word in neither vocabulary | **179** | 86 | 93 |

570 + 564 + 68 + 179 = 1,381. Each bucket is enumerated by
`agencydnc.fingerprint` digest - the same key `agencydnc.add()` writes, so any
bucket is directly applicable without an address ever being published. The
lists live in gitignored
`work/suppression-measure/PROVIDER-SUPPRESSION-SNAPSHOT-FULL.json`; the
committed `docs/state/PROVIDER-SUPPRESSION-SNAPSHOT.json` carries each bucket's
count and a **sha256 of its sorted list**, so the claim stays checkable without
the roster being in git. Why it is not in git is in section 6.

### The third bucket, and the honest cost

**811 people - 59% of the estate - the snapshot cannot decide. 716 of them our
own gate currently says ALLOW.**

That is the number this task asks for. Every one of the 716 is a HOLD under
`UNKNOWN_IS_NOT_A_PASS` the day something consults `reconcile`, and **nothing
consults it** - 0010's defect 1, still true: `reconcile` and `reconcile_all`
have zero callers in `src/` or `scripts/`. So the rule is currently costing
nothing because it is currently doing nothing, and 716 is what it will cost
when it starts.

The 179 are the sharper half, because they are **not** a coverage gap. The
snapshot reached them, and the word it came back with decides nothing:

    stopped             178
    sent                165
    sequence_finished   127
    sending_paused       22
    replied              21

Not one of those five words is in `PROVIDER_STOPPED` or `PROVIDER_ACTIVE`. The
564 absent could be closed by a wider read; these 179 could not. Only the
provider saying what `stopped` means for its blacklist closes them, and
**`stopped` is the most common provider word in the whole estate at 762
occurrences.** Widening the vocabulary is a gate change and is not mine to
make; it is filed, not done.

### Three people replied, and we have approved drafts for them

`replied` being in neither vocabulary has a named cost. Three contacts carry a
provider `replied` and our own verdict is **ALLOW with zero reasons**:

| fingerprint (first 16) | bison lead | campaign | witnesses |
|---|---|---|---|
| `51f67fa76e980e7a` | 204664 | 491 | `pc-leads` + `reengagement-inventory` say `replied`; `pc-sends` says `stopped` |
| `36eda7a9dc397b31` | 204665 | 491 | same three |
| `b28fd94e19f2acfa` | 204525 | 492 | same three |

Named by fingerprint, not address, for 0010's reason. All three records are at
state `verified`, all three contacts carry `sendable: true` and
`verdict: "valid"`, and **every event on all three records is
`draft_approved`.** Nothing in our state knows a reply happened.

This is the same shape as 0010's three bounced people, in a different word, and
it is corroborated three ways:

* 138 lead ids in stored state carry a `replied`. The join can name a person
  for **21**; the other **117 are invisible to us entirely**.
* Of the 21 we can name, 18 are already BLOCK here. These three are not.
* A heartbeat written **minutes ago** counts **27 replies** across the 20
  watched campaigns (11 in 491, 11 in 492, and one each in 494/497/501/504/506)
  while `work/replywatch.json` reports `new_replies_ingested: 0`,
  `events_inspected: 0` and `healthy: true`, checkpoint 2026-10-15T07:54.
  The reply ingester is running, reporting healthy, and reading nothing.

Under CLAUDE.md lead rule 1 a reply is the strongest signal there is and a live
conversation goes to a human. **Recommendation: suppress these three, and treat
the reply backlog as the higher-priority finding of the two.** Not applied -
applying is outside this task.

---

## 4. Drift - how fast the photograph goes stale

### Measured, not estimated

The heartbeats give an independent second read of the same leads, 21 days
newer. Of **95** lead ids they name, 95 are also in the stale sources and
**1 carries a word the stale snapshot does not have** - lead 203709, stale
`in_sequence` + `scheduled` + `stopped`, fresh `sending_paused`.

**Measured drift: 1 of 95 over 21 days, and the one that drifted drifted
SAFE** - the stale reading was `PROVIDER_ACTIVE`, which against a stopped-here
person yields `SUPPRESSED_HERE_ONLY`, while the fresh reading is a word in
neither set. The stale snapshot was the more conservative of the two.

**0 of the 95 were new.** The heartbeat cannot extend the snapshot's reach at
all, only refresh 95 of 2,081 lead ids, and only the fault-filtered subset at
that - `blanks.already` is the blank-copy audit, not a census. That is why they
are not added as a source: no coverage gain, a biased subsample, and absence
from it means nothing. 0010's exclusion was right for the wrong reason.

### What makes the drift rate 1-in-95 rather than catastrophic

**Nothing of ours is sending.** Every one of the 20 watched campaigns reads
`paused`, `archived`, `completed` or `draft` in a heartbeat minutes old. A
paused estate generates no new bounces, no new unsubscribes and no new replies,
so the snapshot ages slowly for a reason that is a property of the freeze and
not of the snapshot.

**That reverses the instant anything sends.** A single send can produce a hard
bounce in seconds and an unsubscribe in minutes. The snapshot's half-life is
not a number in days; it is "until the next send".

### Where it is already unreliable, and it is not uniform

**228 of the 749 snapshot addresses hold a row in a campaign that nothing
watches** - 264, 265, 266, 274, 327, 328, 330, 334 and 352. The remaining 521
sit in campaigns with a heartbeat, where movement would at least be visible at
campaign level. For those 228 there is no refresh mechanism short of a provider
read, and four of those campaigns (274/327/328/352) are the operator-declared
internal ones, three of which CLAUDE.md records as still sending.

### The blind spot that is about to open

0010's finding stands and this run reproduces it: across 749 addresses and
36,523 status pairs, `unsubscribed` occurs **zero** times, and of
`PROVIDER_STOPPED`'s eleven words only `bounced` ever appears (9 occurrences).
The copy carried no opt-out route, so nobody could click one. **The day a
compliant footer ships, `unsubscribed` becomes possible for the first time and
the snapshot has never once witnessed one.** It will be wrong in the one
direction that reaches a real person.

### Recommendations - not implemented

1. **A snapshot can only ever ADD a stop, never clear one.** So age makes it
   unsafe for passing and never for blocking. The canary should therefore
   **never derive an ALLOW from the snapshot at any age**, and should keep
   consuming its stops at any age. That is `UNKNOWN_IS_NOT_A_PASS` applied to
   the artifact instead of the address, and it costs nothing to adopt because
   the canary's allowlist is already independent.
2. **Refuse on age only where age can mislead - the stops.** Recommended
   threshold: the canary REFUSES to start if the newest per-lead source is
   older than **24 hours and anything is sending**, and WARNS, naming the age,
   if nothing is sending. Today that is 21 days with nothing sending, which
   under this rule is a warning, not a refusal. Deriving the threshold from
   sending state rather than from the clock is the point: the clock is not what
   makes the file wrong.
3. **Re-read before and after the first compliant send**, not on a schedule.
   The first send with an opt-out route is the event that makes `unsubscribed`
   possible, and a snapshot taken either side of it is worth more than thirty
   taken during the freeze.
4. **Record the snapshot age in the canary's own log**, as the number, beside
   the decision. A refusal that does not say how stale the file was cannot be
   audited later.
5. **The 228 in unwatched campaigns should be held regardless of snapshot
   age.** Nothing can refresh them and four of those campaigns are internal,
   which CLAUDE.md already treats as not-clean-for-outreach.

---

## 5. Three defects from 0010, re-checked and still open

1. `reconcile` and `reconcile_all` have **zero callers** in `src/` or
   `scripts/`. 716 holds that nothing will ever apply.
2. `reconcile` has **no parameter for our own roster**; it reads
   `ingest.SUPPRESS_LOCAL` anchored to ROOT, so a worktree loads 2 domains
   instead of 14 unless `--suppress-local` is passed. This run passed it.
3. `suppression.decide` accepts `agency=` and uses it nowhere.

One observation new to this run: **`hold_here` is 0 in all four buckets.**
Our own gate, at `SCOPE_SEND`, answers only ALLOW or BLOCK over this estate -
no person is currently HOLD for any reason. Worth knowing before anyone reads
the HOLD path as exercised.

---

## 6. Why the roster is not in the committed artifact

The first cut of this change put all 1,381 bucket digests in
`docs/state/PROVIDER-SUPPRESSION-SNAPSHOT.json`. Two things were wrong with
that, and the second one failed a test rather than being noticed:

* A bucketed list of every production contact is closer to "enough to rebuild
  the prospect list" than the 749-entry snapshot was, and `work/` is gitignored
  for exactly that line.
* `test_fixture_hygiene.test_no_live_account_figures` greps the tracked corpus
  for forbidden figures as **substrings**, and a sha256 digest is 64 characters
  of which ten are decimal digits. At 2,130 digests one of the five-digit
  forbidden figures appeared inside a digest by chance, and the hygiene suite
  went from 5 failing names to 6.

Widening the hygiene rule to skip digests would have been widening a lint rule
to make a file pass. The committed artifact now carries each bucket's count and
a sha256 of its sorted list; the lists themselves are in the gitignored full
artifact, from which they are recoverable per person. The hygiene suite is back
to its 5-name reference set.

Two smaller instances of the same mistake, both caught by the same suite and
both fixed: a test fixture used a real person's name slug taken from the
production queue, and the paragraph explaining the figure incident quoted the
figure.

---

## 7. Verification

* `tests/test_the_provider_snapshot_is_assembled_from_stored_state.py`:
  **25 green**, 12 of them new.
* **Three mutations, each caught by the intended tests and nothing else.**
  Absence returning `DECIDED` - 3 failures, all three in the partition class.
  An unrecognised word returning `DECIDED` - the same 3. The no-address bucket
  publishing the raw contact key - 1 failure, the PII test. Source restored and
  md5 re-verified as the pre-mutation one.
* `tests/test_a_suppressed_address_cannot_reach_a_provider.py`: **37 green.**
* `test_fixture_hygiene` **5 failing names** and `test_invariants` **3**, the
  same sets 0010 recorded against the branch reference, and none of the 24
  hygiene hits is in a file this task touched.
* The committed artifact was read back off disk: 105,425 bytes, **0
  occurrences of `@`**, 0 forbidden figures, every published identifier a
  64-character hex digest.
* **A full-suite reference is OWED**: `tests/` changed.

## 8. Files

| file | state |
|---|---|
| `scripts/suppression_snapshot.py` | changed - time coverage, the three buckets, the git/work split |
| `tests/test_the_provider_snapshot_is_assembled_from_stored_state.py` | changed - 12 new tests |
| `docs/state/PROVIDER-SUPPRESSION-SNAPSHOT.json` | regenerated |
| `docs/SUPPRESSION-SNAPSHOT-0060-2026-10-15.md` | this file |
| `work/suppression-measure/PROVIDER-SUPPRESSION-SNAPSHOT-FULL.json` | regenerated, gitignored, holds the per-bucket lists |
