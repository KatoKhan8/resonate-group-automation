# Production handoff - 2026-09-17

Written for a session with ZERO conversation context. Everything here is read
off provider truth, the code, or a measured run. **Recompute before acting:
`py -3 scripts/production_status.py`.** Quote that, not this file.

**UNKNOWN IS NEVER 0.** A provider that cannot be read says UNKNOWN. A zero
meaning "we could not ask" and a zero meaning "nothing happened" are the two
answers this system exists to keep apart.

**LIVE IS NOT SENT.** Both campaigns are running. Neither has sent anything.

---

## 1. CURRENT PRODUCTION TRUTH

### EmailBison

    campaign            487  "RESONATE - PRODUCTIVE - EMAIL - ZAGREB-HOURS -
                             CONTROL V3 [productive/productive-email-control-v3]"
    provider status     active
    live cohort         10 leads, all `in_sequence`
    senders             [2736]  a Productive human on a secondary sending
                        domain - read the identity from the provider, it is
                        not written into tracked source
                        Connected, warmup on, daily_limit 15, health `ok`,
                        1,742 lifetime sends
    REAL capacity       NOT 15/day. 2736 also serves ACTIVE campaigns 352, 328
                        and 327 - 173,558 emails between them. The limit is per
                        MAILBOX, so 487's share is a fraction of 15 and today
                        it is zero.
    campaign cap        20/day declared; the BINDING cap is the sender's 15
    sent                0        replies 0        bounces 0     unsubscribed 0
    scheduled_emails    0 rows
    canonical row       productive-email-control-v3
    readback            configdiff.compare_bison -> PASS
    sequence            3 steps. step1 `{SUBJECT_1}` thread_reply false wait 3;
                        step2 `Re: {SUBJECT_1}` thread_reply TRUE wait 4;
                        step3 `Re: {SUBJECT_1}` thread_reply TRUE wait 1.
                        The "Re:" is EmailBison's OWN - TASK-159 measured it
                        across 153 follow-ups. We never write it.
                        No SUBJECT_2/3 exists anywhere.

**SENDER 3941 IS NO LONGER ATTACHED, and that is deliberate.** It was attached
under operator authorization, then removed during a recovery (section 2). Do
not re-attach without reading the arity constraint below.

### HeyReach

    campaign            605732 "RESONATE - PRODUCTIVE LINKEDIN COHORT V2 - CONTROL"
    provider status     IN_PROGRESS since 2026-09-16T20:12:25Z
    live cohort         3 leads, all `Pending`
    bound list          944355 (3 leads, each holding its 8 approved variables)
    seat                174892  Active, authIsValid, NO cooldown
                        on search/connection-request/connection-note/InMail,
                        connectioRequestLimit 40 (its ceiling)
    REAL capacity       NOT 40/day. That seat sits in 46 campaigns, 13 of them
                        IN_PROGRESS. The vendor shares a seat's limit across
                        its campaigns, so 605732's share is roughly 3
                        connection requests a day.
    sent                0 messages, 0 connection requests, 0 replies
    canonical row       productive-linkedin-cohort-v2
    readback            configdiff.compare_heyreach -> PASS
    sequence            17 nodes / 8 word-bearing, hash 32f8dde79bfa0f27,
                        byte-identical to the audited 599020

### The ledger

13 keys, all `unresolved` - 3 LinkedIn, 10 email. That is the honest state for
"the campaign is running and nobody has been contacted yet". A key becomes
`sent` ONLY when the provider says that person was sent to:

    HeyReach    /campaign/GetLeadsFromCampaign -> leadMessageStatus
                MessageSent / MessageReply. NOT `leadCampaignStatus` - leads in
                this estate read `Failed` while also reading `MessageSent`. NOT
                `progressStats`, which returns negatives.
    EmailBison  `emails_sent` AND `scheduled_emails` (one row per message).
                Two witnesses - this provider silently discarded
                `max_emails_per_day` at create and read it back as 1000.

### The scheduler hypothesis, AND ITS FALSIFIER

487 has sent nothing despite hours inside its 09:00-17:00 Europe/Zagreb window.
**Seven explanations were tested against controls and ruled out**: the schedule
object's "Not Started" status (three ACTIVE campaigns with 173k sends read the
same); lead `unverified` status (451's DELIVERED lead reads the same); sender
health and caps; lead enrolment (all `in_sequence`); the `wait_in_days`
convention (the client's own sending campaigns carry step-1 waits of 2 and 3);
a field-by-field diff against sending campaign 327 (only our lower caps,
`plain_text`, auto-reply stats); and the sender being saturated, which is TRUE
and is the capacity finding, not a fault.

**Standing hypothesis:** the provider assigns "new leads for the day" on a
cycle at or near the window opening, and 487 was activated at 10:07 local -
after the 09:00 start - so it missed the assignment. Evidence: the campaign's
`updated_at` did not move from its activation timestamp for hours.

**THE FALSIFIER, and use it:** if 487 is still untouched after 09:00 Europe/
Zagreb on 2026-09-18, the hypothesis is WRONG. Discard it and investigate;
do not defend it. A standing explanation with no way to be wrong is how a
stalled campaign gets explained away for a week.

---

## 2. COMPLETED WORK

### PROVEN - provider-confirmed or test-proven with a deliberate-break

- **Both channels activated.** 487 active, 605732 IN_PROGRESS, both readbacks
  PASS.
- **D1 - an approval certifies the words that ship, on BOTH lanes.** Measured:
  30 steps on campaign 485 whose stored words disagreed with the fingerprint
  stamped on them. `bisonfactory._certified_copy` is now the only place email
  copy becomes stageable and hashes the entry's OWN words;
  `heyreachfactory._step_copy` carried the identical defect on the LIVE lane.
  15 tests, 8 fail when the guard is neutered.
- **D2 - our own silent staging is not prior contact.** Four independent arms:
  ours on both sides, every counter zero, provider queue silent, our ledger
  silent. Extended to `check_address`, which had never learned it. 46 tests.
  The 13-email account keeps its history and is never called cold.
- **84 approvals stamped `by: "claude"` no longer certify.** The system was
  signing its own work, and on a `generated: true` step the fingerprint never
  moves, so a self-stamp was permanent. Accountability is tested by SHAPE - an
  address or a declared operator arm - because a name allowlist goes stale and
  a machine-name denylist fails open for the next model added.
- **`_ledger_is_silent` counted superseded rows forever.** `settle` APPENDS, so
  a key settled `abandoned` still read as unrefuted. Now reads the latest state
  per key.
- **`_require_approved_words` compared against JSON.** It refused an activation
  where the provider held the approved body EXACTLY, because JSON escapes.
  Now walks the payload's own string values.
- **`activate_campaign` counted the wrong side.** Leads enrol when a campaign
  STARTS, so a DRAFT bound to a list of three read ZERO. Now counts the bound
  list when DRAFT.
- **HeyReach lead variables.** `add_leads_to_list` never sent
  `customUserFields` and `list_leads` discarded the response's `customFields`
  (note the asymmetry). Without them the graph sends `fallbackMessage` - generic
  copy to real people. All 3 leads verified holding their 8 approved variables.
- **`new_accounts_per_day: 5` is enforced.** It was declared, documented, in
  its own CLI output, and enforced by NOBODY - `require` answered True having
  examined one ceiling of seven. Now enforced at gate 5 AND inside the
  reservation lock. 32 tests, 4 break-proofs.
- **A sender detach route exists and now works.**
  `DELETE /campaigns/{id}/remove-sender-emails`, documented, added as a
  STOPPING verb. `providerwrites.py:327`'s "no documented route" was stale.
- **Capacity reporting corrected twice.** The HeyReach roster stored
  `connectioRequestMax` as `daily_limit` and over-reported by 26% (1,280 vs a
  configured 1,014); "remaining today" does not exist on that provider and now
  reports UNKNOWN as a string so `int(x or 0)` raises. `production_status` now
  prints the BINDING email cap and who else uses the mailbox.
- **Measurement made real.** `waterfall.counters()` had no production caller;
  it has one. `CONTACTOUT_CACHE_HITS` had no producer because there is no cache
  - it reports UNKNOWN rather than 0. Live: 1,056 ContactOut calls, 298
  crawler, 758 escalations, 0 Grok.
- **GLM integrated and earning.** `glm-5.3` verified serving (the remap table
  is correct, measured). Asked to DEFEAT the copy guards, it found two real
  holes: `_certified_copy` merges `extra` AFTER the fingerprint proof, and
  `_step_copy` returned `message`, which the fingerprint never covers - an
  InMail body edited after approval recomputed to the same stamp. Both fixed
  fail-closed. 41 adapter tests.
- **Variable-length threaded sequences proven at N=1..6**, with the negative at
  every follow-up position (14 combinations).
- **Reply watcher armed.** `replywatch --status` said "no poll has ever run"
  while two campaigns were live. First poll: 74 EmailBison + 21 HeyReach
  conversations inspected, 0 ingested. Reply-stop logic itself: 50 tests green.
- **Activation seal cluster re-pointed** across 12 modules. 604869, 605487, 481
  and 485 are asserted REFUSED rather than dropped.
- **`test_the_stop_is_broader_than_the_start`** - new, and it answers a question
  nobody had written down: both pause verbs are SUPPORTED with NO condition
  while each activate is scoped to one campaign, so there is no campaign this
  build can start and cannot stop.

### IMPLEMENTED, NOT YET PROVEN IN PRODUCTION

- The detach route has been exercised exactly once (successfully).
- The `new_accounts_per_day` same-campaign exemption is tested but has only run
  against 487's restoration.
- GLM's adapter has no production caller. Under PROVIDER-ROUTING-POLICY a new
  model provider is layer 5/6 and needs an explicit position and a `spend()`
  ledger entry first.

### THE FULL SUITE IS RED, AND WAS RED BEFORE THIS SESSION

    py -3 -m unittest discover -s tests
    Ran 9986 tests in 1656s
    FAILED (failures=46, errors=45, skipped=5, expected failures=14)

**Do not read `unittest discover`'s exit code from a chained command.** Twice
this session a run was reported as "exit 0" when that was the status of a
trailing `echo`, not of unittest. Read the `Ran .. / FAILED ..` line.

~91 failures across 29 modules, and an A/B against a reconstructed pre-change
tree proved none of them belongs to this session's work: no failure mentions
`pilot_cap`, `UnacknowledgedCap`, `accounts_opened_on`, `new_accounts` or
`not_checking`, and only 2 of the 29 modules even import the changed code -
both failing identically before and after. At least one
(`test_a_five_step_campaign_sends_five_different_emails`) passes alone and
fails only beside `test_a_gated_step_is_waiting_not_absent`: cross-test
pollution, not a defect.

**Consequence for a fresh session: `unittest discover` is NOT a usable green
bar today.** Run the targeted safety suites in section 10 instead, and treat
cleaning the 29 modules as its own task.

### IN PROGRESS / OPEN

- **Four holes in the threading guard**, found at specific lengths and marked
  `@unittest.expectedFailure` so closing one turns the marker red:
  N=1 picks its variable shape from the LEAD's copy count rather than the
  SEQUENCE's, so a one-step sequence writes `{SUBJECT_1}` to the provider and
  gives the lead unnumbered `subject` - empty subject, empty body, readback
  agrees; N=2 turns the guard off instead of tripping it; a threaded step that
  takes its OWN subject is accepted at every length; a hand-written "Re:" is
  accepted at every length - **campaign 485 actually carried that shape**.
- `approval.fingerprint` hashes channel/subject/body/note - NOT `message` or
  `linkedin_action`. Closing it invalidates every stored approval on both
  lanes: a decision, not a fix.
- `tests/test_task081_thread_reply.py` and `tests/test_bison_campaign_write.py`
  carry stale pre-threading fixtures that ASSERT the forbidden shape. Repairing
  them means re-deciding what each module claims.
- The Z.AI key in `config/.env` was pasted into a chat transcript and has not
  been rotated. Carried from the 2026-09-16 handoff.
- `docs/AUTONOMOUS-CHECKPOINT-2026-09-17.md` trips `test_fixture_hygiene` on a
  real domain name. Fix before that suite is trusted.

---

## 3. ACTIVE BACKGROUND WORK

Watchers are **session-scoped Monitor tasks** and die with the session. **A
fresh session MUST re-arm them** (section 10):

    scripts/heyreach_watch_loop.py   605732: SEND, CONNECT, REPLY, LEAD-ERROR,
                                     STATUS, COHORT, READ-ERROR
    scripts/bison_watch_loop.py      487: SEND, REPLY, BOUNCE, UNSUB, STATUS,
                                     COHORT, READ-ERROR
    scripts/reply_watch_loop.py      both providers: REPLY, POLL-ERROR, SKIPPED

Each emits on FAILURE as well as success, so silence means "unchanged" rather
than "died an hour ago".

One agent may still be finishing: a sender-attribution DESIGN (no code), due at
`docs/SENDER-ATTRIBUTION-DESIGN-2026-09-17.md`. If that file exists, read it
before any multi-sender work. No worker holds a worktree; all edits are on
master.

---

## 4. MISSION AND AUTHORIZATION

**P0 = REAL PROVIDER-CONFIRMED SENDING.** Then: largest SAFE live cohort,
continuous READY -> LIVE, both channels in parallel, larger rolling READY
inventory, more safe sender capacity, build Resonate OS while running it, learn
from real outcomes.

**487 HAS NO PENDING OPERATOR DECISION.** The operator authorized attaching the
additional sender and handling the canonical row and re-approval. That decision
is CLOSED. Do not ask again.

Continue normal bounded reversible production work autonomously inside the
existing gates. **Do NOT weaken:** double verification, collision/history,
reply suppression, sender identity, approval fingerprints, provider readback,
tenancy, pilot and account caps.

Stop for the operator ONLY on: a genuinely new irreversible or material
decision, a safety invariant that would have to be weakened, credentials you do
not have, or provider truth showing systemic production failure.

---

## 5. WORKFORCE

    CLAUDE   orchestration, integration, production control, provider
             mutations, reconciliation. NOT the repetitive engineering plane.
    QWEN     primary engineering workforce; parallel independent tasks.
    GLM      independent/adversarial review of the ACTUAL repository. It has
             already found two real holes. `scripts/glm_review.py --list`.
    GROK     external provider/API/current-web research. It found the detach
             route this session.
    PYTHON   deterministic data plane: batching, provider truth, reconciliation,
             benchmarks, counters.

---

## 6. ENGINEERING PRIORITIES

    P0  real sends
    P1  larger safe LIVE cohort
    P2  continuous READY -> LIVE
    P3  sender capacity
    P4  HeyReach sticky multi-sender ownership and allocation
    P5  queue/storage scaling
    P6  evidence reuse
    P7  production learning
    P8  operator/product improvements

Engineering must not delay sending.

---

## 7. MEASURED SCALE FINDINGS

Measured, not remembered:

    work/queue.jsonl        17,484,788 bytes over 550 records
    per record              31,791 bytes - 7.6x the 4.2 KB every benchmark
                            assumed
    load                    0.26s today
    store.save              rewrites the WHOLE file and builds two full indexes
                            en route; run.py checkpoints every 5 records
    at 5,000 records        a ~159 MB file in memory, ~1,000 full-file writes
                            per stage
    evidence_id             hashes `record_id`, so a company met in a second
                            cohort reuses nothing already paid for
    evidence prevalence     4 of 550 records carry any evidence - the reuse
                            loss is real and currently SMALL

    EmailBison senders      225 in workspace 10; 222 committed to active or
                            paused campaigns; 3 uncommitted (3941, 3930, 3919)
                            and all three are `health: warming` with ZERO
                            lifetime sends
    HeyReach seats          41 available, 32 eligible, ZERO free - every
                            eligible seat sits in 8-13 in-progress campaigns

**NOMINAL CAPACITY IS NOT REAL CAPACITY.** Both channels' limits are
per-mailbox and per-seat, shared across every campaign that holds them. Neither
channel is short of PEOPLE - the estate holds 81 LinkedIn-cadence and 51
email-cadence contacts and not one would move faster.

**The deterministic-first premise was already true.** Normalization, dedupe,
matching, ICP, DM titles, verification routing, collision, allocation, caps,
provider writes, readbacks, reconciliation and READY/HOLD/DROP all grep to ZERO
model references. Six of nine model seams are genuinely LLM_REQUIRED.

---

## 8. INVARIANTS THAT MUST NOT REGRESS

**Email copy.** Double independent verification. The opener owns the ONLY
subject; steps 2..N are thread replies referencing `{SUBJECT_1}`; no
`SUBJECT_2..N` is ever generated; we never write "Re:" ourselves. **CONTROL V3
is three steps and must not be modified casually** - it is a production-safe
CONTROL, NOT evidence that three touches is optimal. Number of touches is a
LEARNABLE PARAMETER and the experiment belongs in a NEW campaign.

**Replies.** An inbound reply on either channel suppresses future outreach to
the SAME LEAD on BOTH channels. Canonical state first, then provider effects.

**Identity.** Exact identity only. Sender ownership is sticky. Never claim a
continuity that did not happen.

**Provider truth.** WRITE -> READ BACK -> COMPARE -> RECONCILE. A 200 is not an
answer. LIVE is not SENT.

**The sender arity rule, and why it bit.** `executionguard` (~line 1079)
refuses any campaign whose canonical row names more than one sender: "a guarded
action is attributed to exactly one". It is CORRECT - an action must be
attributable to one human. But combined with `configdiff`'s `sender_ids`
comparison it means: two senders on the row is refused by arity, one sender on
the row mismatches a two-sender provider, and `attach_senders` ADDS rather than
replaces. **A two-sender campaign is un-authorizable until per-lead attribution
exists.** Do not "fix" this by relaxing the arity rule; build the attribution
that would REPLACE it with something stronger.

---

## 9. NEXT ACTIONS, ORDERED

1. **Boot** (section 10) and recompute production truth. Do not trust section 1.
2. **Re-arm the three watchers.** They died with the last session.
3. **Test the scheduler falsifier.** After 09:00 Europe/Zagreb, check whether
   487's `updated_at` has moved and whether `scheduled_emails` has rows. If it
   has not, the hypothesis is dead - investigate rather than wait another day.
4. **If either channel has sent**: reconcile the ledger with
   `scripts/heyreach_first_send_watch.py --settle`, and record the evidence.
5. **Expand the cohort.** `work/approval/NEAR-MISS-PACKET-2026-09-17.md`
   (gitignored) holds 17 contacts / 75 steps, every step lint clean and claims
   clean, held by nothing but a missing approval. **Approving them is an
   operator action - do not approve on their behalf.** Note the 5-accounts/day
   ceiling: 17 contacts span ~17 accounts, so it spreads over days.
6. **Sender capacity (P3/P4).** Read
   `docs/HEYREACH-SENDER-CAPACITY-2026-09-17.md` before any LinkedIn cohort
   larger than one seat can carry, and the attribution design if it exists.
7. **Scale engineering in parallel** - never instead of sending.

**Do NOT redo:** the seven ruled-out send explanations, the sender capacity
audits, the deterministic-first audit, the seal re-pointing, or the D1/D2 work.

---

## 10. EXACT COMMANDS

    cd ~/Desktop/resonate-group-automation
    git log --oneline -5 && git rev-parse HEAD origin/master

    py -3 scripts/production_status.py          # the numbers, recomputed
    py -3 scripts/next_ready_cohort.py          # READY/NEAR_MISS/blocked, slow
    py -3 scripts/heyreach_first_send_watch.py  # per-lead send truth
    py -3 scripts/linkedin_ready_truth.py       # both collision gates

Re-arm the watchers (each as a background Monitor):

    py -3 -u scripts/heyreach_watch_loop.py --interval 300
    py -3 -u scripts/bison_watch_loop.py --interval 300
    py -3 -u scripts/reply_watch_loop.py --interval 300

Safety suites before touching a gate:

    py -3 -m unittest tests.test_an_approval_certifies_the_words_that_ship \
      tests.test_a_linkedin_approval_certifies_the_words_that_ship \
      tests.test_the_fingerprint_does_not_cover_every_field \
      tests.test_our_own_staging_is_not_their_history \
      tests.test_the_live_activation_grant \
      tests.test_the_sixth_account_of_the_day_is_not_opened \
      tests.test_no_activation_without_an_exact_match

`work/queue.snapshot.jsonl` is STALE and has produced wrong numbers twice. Read
live state.

---

## 11. GIT STATE

    branch          master
    HEAD            3a4c7edd (at the time of writing; the handoff commit follows)
    remote          origin/master, verified equal before this commit
    worktrees       none held by any worker; all edits on master
    gitignored      `work/` - 300 real companies and 92 real contacts, plus the
                    approval packet, which must carry real copy to be readable
                    and therefore must never be committed

Never `git add -A`. Stage exact files. Never commit `.env`, keys, credentials,
prospect PII or the approval packet.

---

## FRESH SESSION BOOT PROMPT

> You are resuming Resonate OS, a live production outbound system. Two campaigns
> are LIVE and neither has sent yet.
>
> 1. Read `CLAUDE.md`, then `docs/PRODUCTION-HANDOFF-2026-09-17.md` in full.
> 2. `git log --oneline -5 && git rev-parse HEAD origin/master`. Confirm clean
>    and in sync.
> 3. Run `py -3 scripts/production_status.py` and trust THAT over the handoff.
> 4. Re-arm the three watchers listed in section 10 - they died with the last
>    session.
> 5. Resume the mission autonomously. **P0 is real provider-confirmed sending**,
>    then the largest SAFE live cohort, then continuous READY -> LIVE, then
>    sender capacity, then scale engineering in parallel.
> 6. Test the scheduler falsifier in section 1 before assuming anything about
>    why nothing has sent.
> 7. Use Qwen for engineering, GLM for adversarial review of real code, Grok for
>    external provider research, Python for the deterministic data plane. Keep
>    Claude on orchestration and irreversible provider actions.
> 8. Do not ask the operator to repeat decisions already recorded here -
>    campaign 487's sender decision is CLOSED. Do not redo completed
>    investigations listed in section 9.
> 9. Never weaken: double verification, collision/history, reply suppression,
>    sender identity, approval fingerprints, provider readback, tenancy, pilot
>    and account caps. If a gate blocks you, the gate is usually right - read
>    section 8 before concluding otherwise.
