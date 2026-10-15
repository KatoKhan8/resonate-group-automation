# The bounce gate is wired and blind, and the 145 are not in unknown-owner campaigns

TASK 0070, suppression lane, 2026-10-15. Measured on branch
`task-suppression-2026-10-14` at **`f4ea432be`**, tree clean. No provider call,
no network call, no write to production `work/`, no push or merge to master
(`origin/master` unchanged at `b1f290c84`).

People are named by `agencydnc.fingerprint("email", <normalised address>)`,
the same 64-character form the applied list of 90 uses. **No address appears in
this file**, and none of the names or company domains behind these fingerprints
does either. They are resolvable only from
`work/suppression-measure/PROVIDER-SUPPRESSION-SNAPSHOT-FULL.json`, which is
gitignored.

---

## 1. The three who bounced at the provider and read ALLOW here

    d13e93d56e314e02d1ad136183b326675b39586d50b6ea9e73f5dd58babd0a6c   lead 204562, campaign 495
    f38022b4e74b6e516baeba4d6704c94317978c31f2ace17b339a28a610e97871   lead 204472, campaign 492
    0a5148a392afd2db74e2df98932dcb9b7e91cfe299f1027b8e03184cbda25228   lead 204668, campaign 491

491, 492 and 495 are **our own** campaigns. These three bounced on sends this
system made, not on a manual or internal one.

### Where each side is recorded

**The bounce** is in the stored provider mirror, three independent files per
person, all three agreeing:

    stage/pc-leads.jsonl               witness: campaign membership
    stage/pc-sends.jsonl               witness: queue row
    stage/reengagement-inventory.jsonl witness: campaign membership

(paths relative to production `work/`; newest row 2026-09-30, mtime
2026-09-24). Each also carries a `stopped` row from `stage/pc-sends.jsonl`.
`bounced` is the only word in `leadobserve.PROVIDER_STOPPED`'s vocabulary that
ever appears in this estate — 9 occurrences across 36,523 status pairs.

**The ALLOW** is computed by `suppression.decide`
(`src/suppression.py:253`), whose BLOCK set is `eligibility.must_not_contact`
(`src/eligibility.py:420`), **called rather than re-derived**. That function
returns exactly six person-level reasons (`src/eligibility.py:440-445`):
operator exclusion, suppression list, client's own domain, record state, this
contact's reply, account pause. **None of them is a bounce**, so
`suppression.decide` can never return BLOCK for one. It returned
`ours=allow, our_reasons=[]` for all three.

### Which read is wrong

**Neither, at that layer — they measure different things.** A bounce is a fact
about one address on one channel; `suppression.decide` answers a
channel-agnostic question about a person. The bounce rule is deliberately one
layer later, where the channel is known, with its reason written down in the
source (`src/eligibility.py:796-805`): *"a dead mailbox says nothing about the
same person's LinkedIn profile"*.

The real defect is one layer further in, and it is a feed, not a read.

## The send path reads the bounce record. The record is empty.

`eligibility.decide` → `_email_checks` → `channels._bounced` →
`BLOCKED_BOUNCED`, at **`src/eligibility.py:806-807`**, before MX and before
verification. Proven by measurement on `f4ea432be`, bypassing the fixture fault
in §1a below by handing `decide` the step content directly:

    with a bounce event   -> {"verdict": "blocked", "reason": "blocked:address_bounced"}
    without one           -> {"verdict": "blocked", "reason": "blocked:lint_failed"}

The control matters: the second line proves the guard is not refusing
everything.

**`channels._bounced` reads `rec["events"]` for `events.EMAIL_BOUNCED`
(`src/channels.py:123`), and nothing in production ever writes one.** Measured
against the three real production records (read-only; the file was
byte-identical before and after, sha256
`b37b46b195bb96fdb3cdaa5a2f8d9452a2fcfe9094ba28edfc3bffc7df48394c`):

    fingerprint         rec.state   events on record     EMAIL_BOUNCED   email_verdict
    d13e93d56e314e02    verified    12 x draft_approved  0               (True, None)
    f38022b4e74b6e51    verified     3 x draft_approved  0               (True, None)
    0a5148a392afd2db    verified     3 x draft_approved  0               (True, None)

`channels.email_verdict` says **SENDABLE, no reason** for three addresses the
provider has already refused, today, on the live records.

Why the record is empty, traced to the writer:

* **`leadobserve.confirm_email_touches`** (`src/leadobserve.py:579`) is the
  only code that turns a provider lead status of `bounced` into an
  `EMAIL_BOUNCED` event on a record (`EVENT_FOR`, `src/leadobserve.py:383-387`,
  consumed at `:615`). **It has zero production callers.** Its only caller is
  its own CLI `main()` at `src/leadobserve.py:699` and four tests. No monitor,
  no poller, no scheduled job. Running it needs `bison.scheduled_emails` — a
  provider read.
* **`adapters.from_emailbison`** (`src/adapters.py:109-131`) does have a
  production path — `poller` → `inbound.ingest` (`src/poller.py:471`,
  `src/inbound.py:531`) — but it reads `GET /api/replies`, a different surface
  from a lead status, and the EmailBison checkpoint was advanced to
  `2026-10-14T08:30:56` with `events_inspected: 0`. An advanced checkpoint is
  not re-walked, so whatever that feed held is behind it.

So this is the project's recurring defect in its purest form: the gate is
correct, consulted, and tested, and the field it consults is never written.
A derived report would show a bounce gate in place.

### §1a. The test that claims otherwise is broken, and its control is vacuous

`test_a_bounced_address_stops_being_sendable.TheSENDPathReadsIt.test_decide_blocks_a_bounced_address`
appears in every failing-name set this estate holds. Run alone on
`f4ea432be`: **13 of 14 pass; this one fails**, and the failure is

    AssertionError: 'skipped' != 'blocked'

The full verdict is `{"verdict": "skipped", "reason": "skipped:no_such_step"}`.
`decide` never reaches `_email_checks`: it returns at
`src/eligibility.py:747-748` because the fixture asks about step **`day1`**,
and `day1` belongs to the DEFAULT cadence spec (`src/cadence.py:43`), while the
record's client is `productive`, whose cadence is `productive_li_heavy_v1`.
Measured timeline for that fixture: `li1 li2 li3 li4 li5`, all LinkedIn. Its
email steps are `em1..em5`. There is no `day1` anywhere in this client's
vocabulary, and the fixture's hand-written `rec["cadence"]` is looked up by the
**spec's** keys (`src/cadence.py:890`), so it is never consulted either.

The test was correct for 42 minutes. It landed at `efe8b7042`,
2026-09-13 11:48:24 +0200; productive moved to the LinkedIn-heavy cadence at
`ee254e1f2`, 12:30:26 the same day.

**Its guard-the-guard is vacuous.**
`test_without_a_bounce_it_fails_for_a_different_reason` asserts only
`reason != BLOCKED_BOUNCED`, which `skipped:no_such_step` satisfies. Both
tests have been reporting on an unreached code path for a month and the
designed control could not tell.

**Not applied here.** The fix is to stop asking about a step that does not
exist — either pass the content through `decide`'s own `step=` parameter, which
is what a caller holding a payload does, or key the fixture to `em1`. Either
removes one name from the failing set, and because it is a change under
`tests/` it owes a full-suite reference on the merged master with no exception.
No suite was run for this task.

### Disposition for the three — recommended, not applied

1. **Add all three to the local agency DNC now**, reason `bounced`, by the
   path the 90 used. It is the only barrier that does not depend on a feed
   nobody runs: `_suppressed` is inside `must_not_contact`, so a DNC row makes
   `suppression.decide` BLOCK **and** `eligibility.decide` refuse at the
   person level, on every channel, from disk, with no provider read.
   Blast radius is nil today — all three are `verified`, none is in the canary
   25, none is in the 90, none is in the 145, and the overlap with every
   shippable set is 0 in both directions.
2. **Do not** rely on recording `EMAIL_BOUNCED` instead. Writing the event is
   the correct long-term fix and it needs `confirm_email_touches` to acquire a
   production caller plus a provider read; it is not available today and it
   would protect only the email channel.
3. **The feed is the real finding.** Three bounces are the instance; the
   population is every bounce this estate will ever take, because nothing
   writes any of them. Queue the work: give `confirm_email_touches` a caller,
   or ingest lead status in the same place `pc-leads.jsonl` is refreshed.
4. Operator question, not blocking: these three bounced on **our** sends in
   491/492/495 and the sending-domain cost of writing to a dead address falls
   on the whole estate, which is the stated reason this gate exists.

---

## 2. The 145 ALLOW with a row in one of 274 / 327 / 328 / 352 / 418

Reproduced independently on `f4ea432be` from
`work/suppression-measure/PROVIDER-SUPPRESSION-SNAPSHOT-FULL.json`
(generated 2026-10-15T10:19 by this lane's 0060): **223** people hold a row in
those five campaigns, **145** read ALLOW. Both figures match 0010 exactly.

### The premise is wrong: these are not unknown-owner campaigns

    classify_campaign("email", 274) = resonate_internal
    classify_campaign("email", 327) = resonate_internal
    classify_campaign("email", 328) = resonate_internal
    classify_campaign("email", 352) = resonate_internal
    classify_campaign("email", 418) = unknown

`src/providerwrites.py:2028`, reading the operator's declaration of 2026-10-01
at `config/internal-campaigns.txt:51-54` — which is **in git**, so this
classification is sound from a worktree. The declared list is checked before
the ledger (`:2048` before `:2050`) and wins.

**418 contributes 0 people to the snapshot.** It is not in the data at all. So
every one of the 145 is ALLOW with a row in an **operator-declared internal**
campaign, and none is ALLOW because of an unknown owner.

    campaign   of the 145 holding a row there   classification
    274        113                              resonate_internal
    327        113                              resonate_internal
    328         28                              resonate_internal
    352        144                              resonate_internal
    418          0                              unknown

### What makes an owner "unknown" — the three states, counted separately

The task offered three candidates. Measured, **none of them is what is
happening**, and the real third state is a fourth one.

1. **No ledger binding — true, and not the cause.** No canonical row binds
   274/327/328/352: `work/campaigns.jsonl` begins 2026-09-02 and these were
   created 2026-04-08, 2026-04-23, 2026-04-23 and 2026-05-13. Count of the 145
   whose declared-campaign row is ledger-bound: **0**. It does not make them
   unknown, because the declaration is read first.
2. **A binding to a campaign nobody owns — 0.** No such row exists, and if one
   did it would lose: the source records (`src/providerwrites.py:2037-2039`) a
   measured case of a canonical row re-bound to 327 carrying an authorization
   onto it, which is why the declaration outranks anything a row claims.
3. **A row whose owner field is empty — 0, and the state cannot exist.**
   EmailBison's campaign record carries no owner, creator, user, team or
   tenant field, confirmed across all 29 listing keys. The `owner` key in
   `docs/state/PROVIDER-CAMPAIGNS.json` is **our own derived value**, not the
   provider's — and the stored file predates the third state. Its
   `owner_totals` is `{"resonate": 20, "client_or_other": 20}` with **no
   `unknown` key**, `generated_at` `2026-09-30T20:40:42Z`: one day before both
   the 2026-10-01 fix that gave `campaign_owner` three states
   (`scripts/provider_truth.py:62-70, 178-190`) and the operator's declaration.
   So the committed provider-truth file still labels all four
   operator-declared **internal** campaigns `client_or_other`, by a boolean
   that wrote "not provably ours" down as the client's. `provider_truth.py`
   itself calls that *"a false accusation against four campaigns carrying tens
   of thousands of sends"*.
4. **The state actually in play: `unknown` because the ledger is unreadable
   from where you stand.** `_ledger_rows_binding` (`src/providerwrites.py:1996`)
   reads `campaigns.load()`, i.e. production `work/campaigns.jsonl`. `work/` is
   gitignored and therefore per-worktree, so from
   `wt-suppression-2026-10-14` it loads **0 rows** and every campaign not on
   the declared list classifies `unknown` — including 487, 489 and 493, which
   CLAUDE.md and the provider file both record as ours. Thirteen campaigns
   touching the 145 read `unknown` from here for that reason alone
   (481, 491–498, 264, 265, 266, 330). The guard fails **closed**, which is
   right for a write; but `unknown` is unusable as an ownership *report*,
   because it does not distinguish "nobody owns this" from "you cannot see the
   ledger". The ledger's authority is production `work/campaigns.jsonl` and
   this task did not read it; the only copy outside it,
   `Desktop\campaigns-before-declare.jsonl`, is 2026-09-15, 11 rows, binding
   only 451 and 481, and is not the authority.

So the honest restatement of the 145: **145 people our suppression view says
ALLOW, each of whom was sent to by hand out of an operator-declared internal
campaign.** That is CLAUDE.md's rule 2 case — manual history does not make a
lead ours, and they are COLD subject to a configured gap since the last manual
or internal touch. The gap is `hold_after_last_touch_days`, which is one of the
three unconfirmed numbers in §3.

### Reachability

All 145 hold a queue record: **145 of 145**, both directions, `0` missing,
against 1,584 records (read-only; production `work/queue.jsonl` byte-identical
before and after). That is by construction — the snapshot is built from the
queue — so unlike the 90, whose queue overlap was 0, these are candidates for
every cohort any builder assembles from the queue.

Record state: **140 `verified`, 4 `drafted`, 1 `approved`.**

    47184f8d7b55c943   approved
    8225384da3268f10   drafted
    18bf93421a49015e   drafted
    fcfbe12c1ac31b34   drafted
    7f580800f5b70751   drafted     <- also CANARY-01 row 6

**Six of the 145 are in CANARY-01's 25 contacts** — the one enumerated cohort
that could ship. By fingerprint, both directions: 6 of 145, 6 of 25.

    canary row   fingerprint         internal rows                       our rows
     7           6c81ac748e8f849b…   274,327,352 sequence_finished    |   494 in_sequence,scheduled,sending_paused,sent
     5           73395154b49723ce…   274,327,352 sequence_finished    |   492 in_sequence,scheduled,sent
     3           c5235ec149f67323…   274,327,352 sent,seq_finished    |   481 stopped
     9           7a5468a9809de21f…   274,327,352 sent,seq_finished    |   495 sending_paused,sent,stopped
    13           a92665fe856dfd73…   328,352     sent,seq_finished    |   495 sending_paused,stopped
     6           7f580800f5b70751…   274,327,352 sent,seq_finished    |   495 stopped

Row numbers are
`resonate-ops/canary/APPROVAL-SHEET-SKELETON-2026-10-15.md`'s, which is where
the names behind these fingerprints are already written down.

Every one of the six has been **sent to** out of the internal campaigns, and
every one of their internal-campaign rows is terminal (`sent` /
`sequence_finished`) — so no internal row holds them under
`hold_on_active_sequence`. Two of them, canary rows 7 and 5, carry
`in_sequence` + `scheduled` rows in **our** 494 and
492. Whether those rows are still live is **UNKNOWN**: the newest per-lead
source is 21 days stale, and the only authority is an EmailBison read this
task may not make. A 2026-10-14 heartbeat shows zero `in_sequence` across all
20 watched campaigns, which contradicts them but does not retire them.
All six classify `provider_state_unknown`, not
`suppressed_here_still_active_there`.

**Recommendation, not applied:** the canary's enumeration should carry a
per-row column for prior internal-campaign contact, and these six should be
read by a human before the canary's first send. They are not suppressed and
nothing here argues they should be; they are the population for which "did
anyone already email this person by hand, and how long ago" is the live
question, and the answer is yes for all six.

### Overlaps with the other sets, by name, both directions

    the 145   vs the 90 applied today      0 of 145   /   0 of 90
    the 145   vs the canary's 25           6 of 145   /   6 of 25
    the 145   vs the 3 bounced             0 of 145   /   0 of 3
    the 3     vs the 90                    0 of 3     /   0 of 90
    the 3     vs the canary's 25           0 of 3     /   0 of 25
    the 90    vs the canary's 25           0 of 90    /   0 of 25

Controls, because a reader that finds nothing is indistinguishable from a
broken one: each set intersected against one of its own members returns 1.

**The 51 fictitious-person mailboxes cannot be intersected and this is not a
measurement failure.** They are **sender mailboxes** in our own estate
(provider ids 3687–3737, three names, 17 each), not prospects, and
`CANARY-01-ALLOWLIST-2026-10-15.md` deliberately holds no addresses — the
id-to-address printer is `scripts/email_sender_estate.py` over the operator's
EmailBison export, which is a provider surface this task may not read. So the
intersection is **UNKNOWN**, and the authority needed to close it is named
rather than estimated around. The nearest sound negative: the snapshot's
own-side roster loaded 14 of our domains and 0010 measured that none of the 14
appears among the queue's 1,584 records, so no prospect in this estate sits on
a domain of ours.

---

## 3. What "confirm 30 / 10 / 90" is asking

`src/suppression.py:98-110`, `DEFAULTS`, marked *"PROVISIONAL. Every one of
these is awaiting client confirmation"*: **`hold_after_last_touch_days: 30`**
(a touch inside 30 days HOLDs), **`hold_above_total_sends: 10`** (more than 10
sends ever HOLDs for manual review), **`cooling_days: 90`** (after 90 days a
lead may be contacted again — the operator has already confirmed 90; it stays
config so the three cannot drift apart).

**What confirming them would change: nothing today, and everything the moment a
provider touch feed exists.** The three are read only at `SCOPE_ENROL`
(`src/suppression.py:322, 334, 339`), from `provider_touches`, which is
caller-supplied and which **nothing** populates — so every enrolment currently
answers `hold:provider_touch_history_unknown` and the three numbers have never
decided a single case. They become load-bearing against exactly the population
in §2: 145 people with real prior contact out of the internal campaigns, whose
COLD-versus-hold answer is `hold_after_last_touch_days`, and 94 of whom carry
an `in_sequence` row (92 a `scheduled` one) that `hold_on_active_sequence`
would hold on its own.

---

## Authorities this task did not read, named rather than estimated

* **EmailBison and HeyReach.** No provider call was made. Whether 492's and
  494's `in_sequence` rows are live, whether the three bounces also appear in
  the reply feed behind the advanced checkpoint, and whether the 21-day-old
  snapshot still holds are all UNKNOWN for that reason.
* **Production `work/campaigns.jsonl`.** The ownership ledger. Not read, so
  `resonate_os` is not measurable from this worktree and the 13 `unknown`
  classifications above are artefacts of location.
* **The sender estate in clear.** `scripts/email_sender_estate.py` over the
  operator's export. Not read, so the 51-mailbox intersection stays UNKNOWN.
* **A full suite.** Not run. Nothing under `src/` or `tests/` changed in this
  task; this file is the only artifact, and `tests.test_fixture_hygiene` was
  run alone before and after writing it to prove it adds no name.


---

## APPLIED, 2026-10-15 — and this file is the only durable record of WHY

TASK 0100. The operator decided APPLY at 21:25 local, having read and accepted
0080's correction: `agencydnc.REASONS` is a closed four, there is no `bounced`
member, and the stored row has three fields and no free text. So the three rows
now on the list say `internal` and are **indistinguishable from any other
internal suppression**. He took that cost knowingly, and the reason recorded in
the decision is that three addresses which bounced and are still sendable is
worse than three rows carrying a reason that under-describes them.

**The consequence for a reader in six months: the list cannot tell you these
three were deliverability. This section can, and it is in git.** The reversal
manifest in production `work/` can too, and it is not.

    applied at        2026-10-15T19:37:15+00:00
    prerequisite      fa964f8cc  SETS gained "the-3", one token, nothing else
    sink              scripts/apply_the_90.py --set the-3 --reason-undecided internal
    file              <main checkout>/work/agency-dnc.jsonl
    sha256 before     a5f390e09dbc96ab...  105 fingerprints, 105 rows, damaged NONE
    sha256 after      6c6485b1b0ca33d4...  108 fingerprints, 108 rows, damaged NONE
    NEW 3  GONE 0     all 105 prior fingerprints kept, by name-set, both directions
    reasons after     internal 6, requested 100, legal 2   (internal was 3)
    reversal manifest <main checkout>/work/dnc-backup/REVERSAL-20261015T193715Z.json

The three fingerprints the manifest removes are exactly the three in section 1
above, each with `reason: internal`. Re-running the identical apply **refuses
before any write** — "3 target(s) are ALREADY on the list ... The whole run
stops" — proven by sha256 and mtime_ns unchanged across the refused run, and by
no second backup or manifest appearing.

**The chain was proven to the real gate, not to a probe.** `agencydnc.load()`
resolves from the main checkout to the file that was written (108 rows,
`6c6485b1b0ca33d4`) with no `AGENCY_DNC` set, so the bytes applied are the bytes
the gate reads. Each of the three live records whose contact hashes to one of
these digests was passed to `eligibility.must_not_contact`, which returned
`blocked:agency_dnc` for all three, where three control contacts from the same
store returned all-`None`. `_suppressed` sits inside `must_not_contact`, so this
blocks at the **person** level on **every channel**, from disk, with no provider
read and no dependence on the missing `EMAIL_BOUNCED` producer.

**What this does not fix.** `leadobserve.confirm_email_touches` still has zero
production callers. The bounce gate remains tested rather than working: these
three are suppressed, and a future bounce still does not reach the record. The
population is **five, not three** — 0090 measured two more from the watchers'
own output, and they cannot be named without a provider read.
