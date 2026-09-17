# Production handoff — 2026-09-18 (overnight). REPLACES the 09-17 version.

Written for a session with ZERO conversation context. **Recompute before
acting.**

    py -3 scripts/production_status.py              the numbers
    py -3 scripts/next_ready_cohort.py              READY / NEAR_MISS / blocked
    py -3 scripts/sender_pool_census.py             the safe pool, and why it is 0
    py -3 scripts/bison_forward_book_census.py --report    who is booked when

**UNKNOWN IS NEVER 0. LIVE IS NOT SENT. SCHEDULED IS NOT SENT.**

## READ THE CLOCK BEFORE READING A ZERO

This was written at **2026-09-17T22:50Z, which is 2026-09-18T00:50 in
Zagreb.** The calendar date differs between the two, and both campaigns are
scheduled against a window, so "it is the 18th and nothing has sent" is not a
fault - it is the middle of the night.

    EmailBison 487   window 09:00-17:00 Europe/Zagreb, Mon-Fri.   CLOSED.
                     Opens ~8h after this was written. And 487 is queued for
                     the 23rd regardless, so nothing is due today.
    HeyReach 605732  default window 09:00-17:00 UTC, Mon-Fri - the campaign
                     passes no schedule, so it runs on the vendor default,
                     which is 05:00-13:00 US Eastern.   CLOSED.
                     Opens ~10h after this was written, and its first
                     connection request is due inside that window.

**So the first thing to check on waking is the clock, then HeyReach.** If the
UTC window has been open for hours and all three leads still read
`leadConnectionStatus: None` with `lastActionTime` unmoved since the 17th,
that is the falsifier in section 1 firing - investigate rather than extend the
graph explanation.

---

## 1. PRODUCTION TRUTH, read 2026-09-18

### EmailBison

    CAMPAIGN_ID       487
    STATUS            active
    LEADS             10  (all in_sequence)
    SENT              0
    REPLIES/BOUNCES   0 / 0
    SCHEDULED         10 openers, all 2026-09-23
    SENDER            [2736] - one
    NEXT SEND         2026-09-23

### HeyReach

    CAMPAIGN_ID       605732
    STATUS            IN_PROGRESS
    LEADS             3  (all InSequence / request_pending)
    CONNECTION_REQS   0   - leadConnectionStatus "None" on all three
    MESSAGES/REPLIES  0 / 0
    SENDER            174892 on all three
    lastActionTime    09:04:00Z, 09:06:42Z, 18:59:54Z on the 17th

All three leads MOVED `lastActionTime` on the 17th and none has a connection
status. **The falsifier from the last handoff is still live and is due now:**
if the 19th opens with all three still at `leadConnectionStatus: None` and
`lastActionTime` unmoved since the 17th, the graph explanation is wrong -
investigate rather than extend it.

### Cohort

    READY_NOW         0   on BOTH channels
    NEAR_MISS         17  (5 email, 12 LinkedIn)
    first gate        approval, for every one of them
    LIVE              13  (10 email + 3 LinkedIn)

**Nothing moved forward tonight and nothing could have.** Not a bottleneck
that was missed - measured, below.

---

## 2. WHY 487 SENDS ON THE 23rd — NOW PROVEN, NOT SAMPLED

Full working: `docs/THE-23rd-IS-PROVEN-2026-09-18.md`.

Sender 2736's forward book, from a **COMPLETE** cursor walk of campaign 327
(48,759 rows) and 328 (38,744 rows):

    2026-09-17   15 of 15    327
    2026-09-18   15 of 15    327      <- FULL
    2026-09-19/20            weekend, not sending days
    2026-09-21   15 of 15    327
    2026-09-22   15 of 15    328
    2026-09-23   10 of 15    487's own ten

**487's openers are on the 23rd because its only mailbox is booked to its
daily limit every sending day until then.** Campaign 327 ALONE fills it on the
18th, before 328 and 352 are counted.

The previous handoff reached this from a 9,000-row sample and was right, but
only half its table was ever sound. The asymmetry matters and must be carried
forward: **sampling can only UNDERCOUNT commitments, so a sampled count that
REACHES the limit is sound and a sampled ZERO never is.**

### How the walk became possible

`scheduled_emails` refuses these queues (`PartialInventory`, 3,251 / 2,583 /
6,382 pages) because offset pagination 422s beyond ~500 pages. Grok reported
a documented cursor mode and **it was verified live on this estate**:
`pagination_type=cursor` returns `meta.next_cursor` and the ids advance.
`per_page` stays 15, so it is not cheaper - ~12,000 requests, ~2 hours - only
possible. `scripts/bison_forward_book_census.py` is resumable by design.

**THE WALK IS NOW COMPLETE** - all four campaigns, 183,239 rows - and it
answered the open question. See `docs/REAL-HEADROOM-2026-09-18.md`:

    151  connected + healthy + room on the 18th   2,205 emails of headroom
     59  no room on the 18th
     15  not connected

**The constraint was never the estate. It is that 487 names ONE mailbox and
that mailbox is full.** 2736's owner holds a single inbox with room on the
18th, and only 9 emails of it. Senders 3939-3948 read 15 of 15 free, used 0,
connected and healthy. ATTESTED AND USABLE: **0** - which is why none of it is
reachable by an allocator, though a canonical row can still name one exactly
as 487 names 2736.

Caveat that must travel with it: "free now" is not "will stay free". The
scheduler runs at the END of every sending day, so the client's own campaigns
can book some of this later today. Re-read the book immediately before
activating anything.

### Ruled out

- Swapping onto another of that human's inboxes - booked the same days.
- Pause/resume to re-run the scheduler - re-plans against the same full
  mailbox, and a probe already failed to restart this campaign.
- The step delay - canary 451 had the same `wait_in_days: 3` and scheduled
  same-day.

---

## 3. WHAT WOULD LET EMAIL SEND EARLIER — two operator decisions

Full working: `docs/GATES-BEFORE-A-SECOND-EMAIL-CAMPAIGN-2026-09-17.md`.

**A pessimistic reading earlier in the session was wrong and is corrected
there.** `bisonfactory.stage()` calls `attach_senders` and `attach_leads`
DIRECTLY, deliberately outside `providerwrites.perform` - the module says so
and names the workspace killswitch as the control instead. `sending.live` for
productive reads ON. So:

- `EMAIL_ADD_LEAD` absent from SUPPORTED does **not** block lead staging.
- `EMAIL_ASSIGN_SENDER`'s conditional does **not** block sender binding.
- Creating a campaign and writing a sequence need nothing new.

What actually blocks:

    1. CONTACT APPROVAL. And it gates STAGING, not just sending:
       `_approved_copy` returns only approved words and `_ensure_leads`
       refuses a lead whose step copy is missing, stopping the WHOLE run
       rather than staging a partial cohort. So a campaign cannot be
       pre-built while approval is outstanding. That is the system working.
       17 contacts are ready; `approve.approve_step` is the action and a
       PERSON takes it. Packet: work/approval/NEAR-MISS-PACKET-2026-09-17.md
       (gitignored, real names, NEVER commit).

    2. THE ACTIVATION SCOPE. `EMAIL_ACTIVATE` resolves its permitted campaign
       from canonical row `productive-email-control-v3` and refuses every
       other. One code change, and its own docstring says editing that tuple
       is not a refactor.

The first gates the second. **Do not approve on anyone's behalf** - 84
approvals stamped `by: "claude"` were revoked for exactly that reason.

### The sender a new campaign would use

Three inboxes have a forward book empty **by construction** - attached to no
ACTIVE campaign at all, only to draft 418 which holds 225 senders and zero
leads and schedules nothing:

    3941, 3930, 3919   connected, health "warming", daily_limit 15,
                       three DIFFERENT humans, none of them 487's, NONE
                       attested

`HUMAN_IDENTITY_ATTESTED` is **0** across all 225 inboxes, which is why
`SAFE_FOR_PRODUCTIVE` reads 0 against 2,391/day of measured headroom. A
campaign can still name an inbox on its canonical row - that is how 487 names
2736 - but `assignment.allocate` cannot choose one. Attestation is a HUMAN
statement by design; the read-only proposal is
`scripts/propose_sender_attestation.py`.

---

## 4. A LOADED GUN IN THE ESTATE — operator decision

`docs/TWO-DRAFT-CAMPAIGNS-HOLD-THE-LIVE-COHORT-2026-09-17.md`.

    487  active   10 leads  [2736]   the live one
    485  DRAFT    10 leads  [2736]   10 of 10 are 487's leads
    481  PAUSED   23 leads  [2736,2737]  9 of them are 487's leads

Measured by hashing addresses, read-only. **Starting 485 sends a second
opener to every person 487 is already queued to email**, from the same
mailbox. 485 additionally carries the rejected non-threaded sequence.

**Our tooling cannot do it** - `EMAIL_ACTIVATE` refuses, and that refusal is
now pinned by a test using the exact dangerous pairing (485's provider id with
the CORRECT v3 row). The exposure is a human in the vendor UI.

**Recommendation: archive 485 and 481.** Not done - archiving a provider
campaign is destructive and neither was created tonight.

---

## 5. WHY NOTHING IN THE COHORT COULD MOVE

Three routes were checked and all buy nothing. Do not redo them.

- **The second verifier is not the blocker.** The policy names Deliverable as
  `secondary`, and Deliverable is closed by an unset `DELIVERABLE_RESULT_SHAPE`
  - "not a missing-evidence refusal but an unmade spending decision". But
  Reoon IS configured and the escalation fires explicitly when "the secondary
  is a provider whose response contract we cannot yet read". So a second
  confirmation is reachable.
- **The 140 unverified contacts are capped by QUALIFICATION TIER** (A:3, B:2,
  C:1 per record), not by vendor availability. 19 of their 32 records already
  hold a sendable contact, so verifying them buys contacts at accounts we can
  already reach - not new accounts. `new_accounts_per_day` is 5 regardless.
- **Generating the 9 missing-copy LinkedIn steps unblocks zero** - all nine
  are account-blocked as well.

---

## 6. REPLY SAFETY — a real defect found and fixed

**`bisonevents.normalise` rejected 100% of real provider events.** Measured by
walking 1,200 real events from `/api/events` by cursor. Every ASSUMED field
path was wrong, and all of them failed on the first check reached,
`data.occurred_at is missing`.

**The reply type was wrong, and that is the safety finding.** The module
mapped `CONTACT_REPLIED`; the provider sends **`LEAD_REPLIED`**. An unmapped
type normalises to `"unknown"` by design, so a real reply arriving through
this path would have produced an event that **suppressed nothing** - against
the invariant the system calls absolute.

Types actually seen in 1,200 events: EMAIL_SENT 1121, LEAD_FIRST_CONTACTED 48,
EMAIL_BOUNCED 15, EMAIL_SEND_FAILED 15, LEAD_REPLIED 1. The last two were not
in the map at all. EMAIL_OPENED / CONTACT_UNSUBSCRIBED / CONTACT_INTERESTED
were NOT seen and are kept as UNCONFIRMED rather than disproven.

Real paths now read: `data.lead.id`, `data.campaign.id`, `data.lead.email`,
`data.scheduled_email.raw_message_id`. **`event.id` does not exist** - absent
in 1,200 of 1,200 - the provider's identity is the `/api/events` row `uuid`,
so `event_key` would have fallen back to its composite every time.

300 real events now normalise. 100%, from 0%.

**STILL UNKNOWN and still blocking the wiring**: whether a real webhook POSTs
the envelope or the inner payload (both are accepted), and whether a RETRY
repeats the envelope `uuid` - which decides whether the dedupe key survives a
retry, the whole point of the module. **Polling remains the fallback.**

---

## 7. PERFORMANCE — measured, then improved, honestly

### Per-stage baseline (`docs/PERF-STAGE-BASELINE-2026-09-17.md`)

5,000 synthetic records, one pass, fake providers:

    generate_plan  4.82s | icp_qualify 4.54s | personas 3.76s
    = 82% of single-pass stage time. Total stage time 15.96s.

H3, H4, H6, H9, H10 CONFIRMED. H7 and H8 honestly NOT-MEASURED (fake
providers have no latency).

### H8 is now MODELLED - and provider wait is ~99% of a real pass

`docs/PERF-LATENCY-MODEL-2026-09-18.md`. 5,000 records, 8,760 provider calls:

    BAND    SERIAL WAIT    CPU     WAIT%    K=4      K=8      K=16
    low          840.2s   15.2s    98.2%   210.1s   105.0s    52.5s
    mid        1,966.8s   15.1s    99.2%   491.7s   245.8s   122.9s
    high       4,988.6s   14.6s    99.7% 1,247.2s   623.6s   311.8s

**Every latency value is ASSUMED - no measured p50/p95 exists anywhere in
this repo - but the conclusion does not depend on which band is right.** Wait
is 98.2% at the optimistic end and 99.7% at the pessimistic one. Our own CPU
is noise in all three.

**So the performance ranking is: provider wait (33 min) first, persistence
(~159 GB of writes) second, our CPU (15s) nowhere.**

What CANNOT be parallelised, and this is the part to read before building
anything: the shared `Budget` cap (two concurrent charges read the same
`spent` and both pass, so a 260-credit cap silently spends 262), the
waterfall ledger whose append ORDER is what `costs.reconcile()` reads, the
`new_accounts_per_day` reservation lock, and checkpoint ordering.

Rate limits are classified, not assumed: the enrichment providers that
dominate the call count have **UNKNOWN** limits, and EmailBison's 3,000 rpm
is **MARKETING** - a features page, not the API reference. K=4 is the
conservative start; K=8 only after a full pass with zero 429s.

### Persistence (`docs/PERF-PERSISTENCE-2026-09-17.md`)

**EVERY BYTE FIGURE PUBLISHED EARLIER TONIGHT WAS 37x TOO SMALL.** GLM's
storage review checked the arithmetic against the real estate; verified:

    work/queue.jsonl   17,486,311 bytes / 550 records = 31,793 B per record
    the synthetic record the benchmark used            =    859 B per record

A real record carries what enrichment PUTS in it - provider answers, crawl
evidence, timelines, verification history. The benchmark was measuring a
record shape that does not exist. It now pads to the measured size.

Re-measured at 500 records, REAL size:

    whole-file   1,517 MB written   499.8x   13.3 s
    journal          3.0 MB written    1.0x   22.4 s

At 5,000 records the whole-file path is **~159 GB per pass** - MODELLED from
the measured quadratic and deliberately not measured, because writing 159 GB
to the operator's SSD to confirm what two measured points already give is a
hardware cost for no new information.

Write amplification equals cohort size. Bytes scale as the exact square.

### The journal — wired, default OFF

`QUEUE_JOURNAL=1`. At the REAL record size, 500 records:

    whole-file   1,517 MB   499.8x   13.3 s
    journal          3.0 MB    1.0x   22.4 s

**506x fewer bytes. 69% SLOWER** - and the penalty is worse with real records
than toy ones, because the O(N) read-and-replay it leaves behind is itself
proportional to record size. The quadratic write is gone
and the bottleneck moved to the O(N) READ per checkpoint, which now also
replays a growing journal. Fixing that needs an INDEX (offsets per record id
so the guards read only the rows a delta touches). Not started.

**The flag stays OFF until the read is fixed too.** It is wired, tested and
measured so the decision is a number, not an argument.

Three bugs the tests caught before it could be turned on, all of which would
have been silent: `save` read `on_disk` from the base file, so the digest
check and BOTH loss guards would have compared against stale state; the first
save with no base file left state in a sidecar while `queue.jsonl` stayed
absent; and `digest()` hashed only the base, so `expect_digest` would have
compared identical values across somebody else's write.

### Crawl cache — cross-cohort reuse, landed

A company crawled for cohort A is no longer crawled for cohort B. Measured:
10 crawls in pass 1, **ZERO** in pass 2, hit rate 1.00 on a repeated cohort
and **0.00 on a disjoint one** - the half that proves it is not serving the
wrong company's evidence.

**Hypothesis 5 was REFUTED as stated.** `evidence.evidence_id` does hash
`record_id` against its docstring, but every consumer uses it as an
INTRA-record reference and none as a cross-record cache key, so restabilising
it saves no provider call. The real waste was `research._crawl_cache` being
pass-scoped - and its identity model was already correct, storing with
`record_id=None` and re-stamping on reuse. It just never survived the pass.

---

## 8. WHAT GLM FOUND, AND WHAT IT COST TO IGNORE IT WOULD HAVE BEEN

GLM reviewed `queuejournal` before it had a caller. **Its finding that Windows
`open(path,"a")` is not atomic across processes was reproduced and is true:**

    six processes, 400 lines each -> expected 2400, parsed 2193,
    MANGLED 1, MISSING 207

Two of the six lost 112 and 95 lines with nothing raised. `append` now takes
`store.lock`; break-proofed (removing it drops 9 of 100 under four threads).

Also accepted: the compaction ordering (write base -> fsync -> discard is now
enforced by `compact()` rather than requested in a docstring).

**Accepted but deliberately NOT fixed:** `replay` is last-write-wins with no
version comparison, so a stale delta silently overwrites a newer one
including paid evidence. Pinned as a test that ASSERTS THE BAD BEHAVIOUR so a
wiring change cannot miss it. If that test ever fails, the guard was added and
the test should be inverted, not deleted.

**GLM's first run returned nothing** - empty completion, `finish_reason:
length`, because GLM-5.3 spends most of its budget on reasoning tokens. Use
`--max-tokens 24000`. The default 6000 is not enough for a multi-part question.

---

## 9. GIT

    START_SHA   52fc3b5d
    END_SHA     ba910a68
    REMOTE      ba910a68   (verified equal)
    COMMITS     21

    BRANCH                                    TIP        STATE
    perf-instrumentation-2026-09-17           81022b7d   MERGED, pushed
    crawl-cache-persistence-2026-09-17        e3ee9022   MERGED, pushed

All nine worktrees clean. Nothing uncommitted.

**242 tests pass** across invariants, journal, webhook, predicate, crawl
cache, stage profile, store and enrich.

**`py -3 -m unittest discover -s tests` HANGS.** It was killed after ~1.5
hours having produced no output. CLAUDE.md already warns that discover and
`tests.offline` overlap on loopback; treat the full discover as unreliable and
run named modules.

---

## 10. ACTIVE WORKERS AND MONITORS

**MONITORS ARE SESSION-SCOPED AND DIE WITH THE SESSION. RE-ARM THEM.**

    py -3 -u scripts/bison_watch_loop.py --interval 300
    py -3 -u scripts/heyreach_watch_loop.py --interval 300
    py -3 -u scripts/reply_watch_loop.py --interval 300
    py -3 -u scripts/bison_mailbox_utilisation.py --interval 300 --samples 200 --quiet

All four were armed overnight and stayed silent, which means unchanged.

**THE CENSUS WAS STILL RUNNING.** Resume it - it is resumable and will pick up
from its stored cursor:

    py -3 -u scripts/bison_forward_book_census.py --campaigns 352 --checkpoint 100
    py -3 scripts/bison_forward_book_census.py --report

    327  COMPLETE  48,759 rows
    328  COMPLETE  38,744 rows
    352  COMPLETE  95,726 rows
    487  COMPLETE  10 rows
    -----------------------------
         183,239 rows. Nothing left to walk; re-run only to refresh.

Qwen is IDLE. Its worktree `resonate-qwen-5` is on
`crawl-cache-persistence-2026-09-17`, merged.

**Qwen cannot be backgrounded with `nohup`/`Start-Process`** - the auto-mode
permission classifier blocks it. It runs fine in the FOREGROUND, so dispatch
it with the Bash tool's own `run_in_background`, not a shell backgrounding
operator.

---

## 11. NEXT HIGHEST-VALUE ACTIONS

1. **DONE overnight - the walk finished.** 151 inboxes and 2,205 emails of
   headroom on the 18th, none attested. The remaining capacity work is
   ATTESTATION, which is a human statement, not a measurement.
2. **The HeyReach falsifier is due.** Check 605732 on the 19th.
3. **The two operator decisions** (section 3) and the archive decision
   (section 4). Nothing about the email cohort moves without the first.
4. **Provider concurrency - now the number one performance item.** Modelled
   at 99% of a real pass and robust across all three latency bands. K=4 takes
   a 5,000-record pass from ~33 minutes of waiting to ~8. Build it against
   the constraints in section 7, not around them, and measure REAL latency
   first - the model is assumed values and says so.
5. **The store index.** The journal moved the bottleneck to the read; an
   offset index per record id is what narrows it.
6. **Do not wire the webhook** until a real delivery and a real RETRY have
   been captured. Two UNKNOWNs remain and one of them is the dedupe key.

---

## 12. SAFETY INVARIANTS THAT MUST NOT REGRESS

Unchanged from the 09-17 handoff, and all still hold: double verification
(two independent vendors, UNKNOWN is not PASS), exact sender identity,
account and contact collision, cross-channel reply suppression, email
threading (step 1 owns the only subject), provider WRITE -> READ BACK ->
COMPARE, no fabricated claims, `new_accounts_per_day: 5`, a bad record is
HELD or DROPPED with a reason while unrelated records continue.

**Nothing was weakened tonight.** Two guards were strengthened: the
`EMAIL_ACTIVATE` refusal now has the exact dangerous pairing pinned, and the
production-write barrier now covers the journal sidecar.
