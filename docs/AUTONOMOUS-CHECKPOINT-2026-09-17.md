# Autonomous run checkpoint - 2026-09-17, overnight

Both channels are LIVE. This is the state a fresh session on another machine
would need, read off provider truth and canonical state rather than carried
forward from scrollback.

---

## 1. PRODUCTION - both channels live, nothing sent yet

    HEYREACH_LIVE=TRUE     campaign 605732 IN_PROGRESS since 2026-09-16T20:12:25Z
                           list 944355, 3 leads, seat 174892
                           sequence hash 32f8dde79bfa0f27 == audited 599020
                           canonical row productive-linkedin-cohort-v2
    HEYREACH_SENT=0        every lead Pending
    HEYREACH_FIRST_SEND=FALSE

    EMAILBISON_LIVE=TRUE   campaign 487 active, workspace 10
                           10 leads, sender 2736, cap 20/day, 3 steps
                           canonical row productive-email-control-v3
    EMAILBISON_SENT=0      counter 0, queue 0 rows
    EMAILBISON_FIRST_SEND=FALSE

**Zero sent is expected, not a fault.** Activation happened around 22:00 and
01:00 Europe/Zagreb - outside any sane sending window. HeyReach exposes no
schedule read route, so the dispatch time cannot be asserted from provider
truth, only that nothing is erroring.

**And on HeyReach it will be slow when it starts.** Seat 174892's 40/day is a
PER-ACCOUNT limit that the vendor shares proportionally across every campaign
the seat is in, and it is in 13. Campaign 605732's share is roughly 3
connection requests a day. That is a capacity fact, not a defect.

### Ledger

Thirteen keys, all `unresolved` - three LinkedIn, ten email. That is the honest
state for "the campaign is running and nobody has been contacted yet". A key
becomes `sent` only when the provider says that person was sent to. Never infer
a send from campaign status.

    HeyReach     /campaign/GetLeadsFromCampaign -> leadMessageStatus
                 MessageSent / MessageReply. NOT leadCampaignStatus - leads in
                 this estate read `Failed` while also reading `MessageSent`.
                 NOT progressStats, which returns negative numbers.
    EmailBison   emails_sent AND scheduled_emails (one row per message). Two
                 witnesses, because this provider silently discarded
                 max_emails_per_day at create and read it back as 1000.

`py -3 scripts/production_status.py` recomputes all of this. Quote it, do not
quote this file.

---

## 2. WATCHERS ARMED (session-scoped - they die with the session)

    scripts/heyreach_watch_loop.py   605732: SEND, CONNECT, REPLY, LEAD-ERROR,
                                     STATUS, COHORT, READ-ERROR
    scripts/bison_watch_loop.py      487: SEND, REPLY, BOUNCE, UNSUB, STATUS,
                                     COHORT, READ-ERROR
    scripts/reply_watch_loop.py      both providers: REPLY, POLL-ERROR, SKIPPED

Each emits on FAILURE as well as success, so silence means "unchanged" rather
than "died an hour ago".

**A fresh session must re-arm these.** They are Monitor tasks in one session,
not a service.

**Why the reply watcher exists.** `ACCOUNT-OUTREACH.md` guarantees a confirmed
reply stops that lead on BOTH channels. `src/replywatch` implements it as a
daemon thread inside the deployed Railway service - which is not what is
driving these two campaigns. `replywatch --status` on this machine said "no
poll has ever run" while both were live. The logic was green in 50 tests; the
loop simply was not running. First poll: 74 EmailBison + 21 HeyReach
conversations inspected, 0 ingested.

---

## 3. WHAT CHANGED TONIGHT, AND WHY

### D1 - an approval now certifies the words that ship, on BOTH lanes

Measured on campaign 485: ten leads, `missing_copy: []`, and THIRTY steps whose
stored words disagreed with the fingerprint stamped on them. Two halves:
`approve_step` copied fields only `if field not in slot`, stamping a
campaign-expanded fingerprint onto a slot still holding generated copy; and
`_resolve_step_copy`'s no-variant branch staged the slot's words after checking
only that an approval EXISTED.

`bisonfactory._certified_copy` is now the only place email copy becomes
stageable, and it hashes the entry's OWN subject and body. `heyreachfactory.
_step_copy` carried the identical defect on the LIVE LinkedIn lane and was
fixed the same way.

Remedy applied to data: the thirty approvals were retaken with `campaign=`.
30/30 now certify their own words.

### D2 - our own silent staging is not prior contact

`bison.membership(485)` read 10 of 10 leads as `stopped` - fallout from
EmailBison archiving a campaign that has no sender. A membership row is dropped
only when four independent arms hold: ours on both sides, every counter zero,
provider queue silent, our ledger silent. The 13-email account keeps its
history and is never called cold.

Extended tonight to `check_address`, which had never learned it - so staging a
cohort made all ten of those people read TOUCHED and the gate refused the
campaign that had just staged them.

### Three defects found only by trying to activate

1. **`_ledger_is_silent` counted superseded rows forever.** `settle` APPENDS,
   so a key reserved then settled leaves both rows. Ten keys settled
   `abandoned` against provider proof still read as ten unrefuted actions, and
   a campaign became permanently unactivatable after its first settled attempt.
   Now reads the latest state per key.

2. **`_require_approved_words` compared against JSON.** It searched
   `json.dumps(payload)`, and JSON escapes newlines and quotes - so it refused
   an activation where the provider held the approved body EXACTLY. A false
   refusal here is indistinguishable from the real defect it exists for. Now
   walks the payload's own string values.

3. **`activate_campaign` counted the wrong side.** Leads enrol when a campaign
   STARTS, so a DRAFT bound to a list of three read ZERO from `campaign_leads`
   - the containment refused every honest caller and admitted no dishonest one.

### The HeyReach lead-variable discovery

The first activation was refused because list 944355's leads held
`customFields: []`. The sequence holds only variables and HeyReach substitutes
`fallbackMessage` for any it cannot fill, so activating would have sent generic
copy to three real people under authorizations fingerprinted to their
personalised copy. Root cause: `add_leads_to_list` never sent
`customUserFields` ("three fields is what was proven" was an over-read - none
of the twelve 2026-09-15 probes ever sent the key), and `list_leads` discarded
the response's `customFields`. Request key is `customUserFields`, response key
is `customFields`.

### The activation seal

Both ACTIVATE verbs are prospect-facing, so `providerwrites.perform` refuses
them without an Authorization - and `executionguard` could not mint one for ANY
campaign on EITHER channel. The GLOBAL killswitch layer is derived from
`push.LiveSendNotEnabled` EXISTING, and the CAMPAIGN layer needs a status
nothing in this build can reach. `LIVE_ACTIVATION_GRANTS` unseals named
campaigns only, is empty by default, and is pinned by value in its own test.
`push.run`'s refusal is untouched: activation flips a provider switch, it does
not transmit from this build.

---

## 4. TWO AUDITS THAT OVERTURN ASSUMPTIONS

`docs/SCALE-HARDENING-2026-09-17.md` - **deterministic-first was already true.**
Normalization, dedupe, matching, ICP, DM titles, verification routing,
collision, allocation, caps, provider writes, readbacks, reconciliation and
READY/HOLD/DROP all grep to zero model references. Six of nine model seams are
genuinely LLM_REQUIRED.

**The real bottleneck is the queue.** `work/queue.jsonl` is 17,484,788 bytes
over 550 records - 31.8 KB/record against the 4.2 KB every benchmark assumed.
`store.save` rewrites the whole file and builds two full indexes; `run.py`
checkpoints every 5 records. At 5,000 domains: a ~159 MB file in memory and
~1,000 full-file writes per stage. That is why an agent still babysits a
cohort - not because the judgement needs a human, but because the run cannot be
left alone. And `evidence_id` hashes `record_id`, so a company met in a second
cohort reuses nothing already paid for.

`docs/HEYREACH-SENDER-CAPACITY-2026-09-17.md` - **41 seats, 32 eligible, ZERO
free.** Every eligible seat already sits in 8-13 in-progress client campaigns.
MAX_SAFE_SENDERS = 1 today, and not for a good reason: `executionguard` refuses
a canonical campaign holding more than one seat, and stickiness is preserved
only BY THAT ARITY - every productive `linkedin_account` row has `sender_id`
null, there are zero ownership attestations, so everything falls back to the
hardcoded seat. Add a second seat today and the provider's rotation decides who
a prospect hears from.

---

## 5. OPEN, NAMED, NOT FIXED

- **`approval.fingerprint` hashes channel/subject/body/note - NOT `message` or
  `linkedin_action`.** An InMail body replaced after approval still certifies,
  and `_step_copy` prefers `message` over `note`. Closing it invalidates every
  stored approval on both lanes: a decision, not a fix.
- **The Z.AI key in `config/.env` was pasted into a chat transcript** and has
  not been rotated. Carried from the 2026-09-16 handoff.
- **Seat 174810** is healthy, credential-valid, in 8 live client campaigns, and
  absent from our roster. Fail-closed, but the decision is unrecorded.
- **The roster over-reports capacity by 26%** - `daily_limit` stores
  `connectioRequestMax`, so it reports 1,280/day against a configured 1,014.
- **Campaign 481 is a hazard, and the overlap is exact.** Re-read from the
  provider 2026-09-17:

      481   paused, 23 leads, 0 sent, cap 20/day
            5 steps, EVERY ONE thread_reply=false, subjects {SUBJECT_1}
            through {SUBJECT_5} - five independent prospect-facing subjects,
            which is precisely the shape the threading invariant forbids
            membership: 14 stopped, 9 sending_paused (resumable)

      overlap by lead id with campaign 487: NINE of nine.

  Every resumable lead in 481 is one of the ten people now live on 487. A
  single resume in the vendor UI sends 45 invariant-violating emails to exactly
  the people we are already, correctly, emailing.

  **Our own code cannot do it.** `EMAIL_ACTIVATE`'s condition refuses 481 under
  every canonical row tried, including none. The remaining path is a human
  clicking resume, which is why this is written down rather than fixed: 481 is
  not ours to mutate tonight, and a protective write on somebody else's paused
  campaign is still a write on a campaign outside the authorization.
  RECOMMENDED OPERATOR ACTION: archive or stop-future-emails on 481's nine
  resumable leads before anyone touches that campaign.
- `waterfall.counters()` has no production caller; `CONTACTOUT_CACHE_HITS` has
  no producer.

---

## 6. IF YOU ARE A FRESH SESSION

1. `py -3 scripts/production_status.py` - the numbers, recomputed.
2. Re-arm the three watchers in section 2.
3. Read `docs/HEYREACH-SENDER-CAPACITY-2026-09-17.md` before planning any
   LinkedIn cohort larger than what one seat can carry.
4. Do NOT modify campaign 487 or 605732. Both are live and correct. CONTROL V3
   being three steps is a production-safe CONTROL, not evidence that three
   touches is optimal - that is a learnable parameter, and the experiment
   belongs in a NEW campaign.
5. `work/queue.snapshot.jsonl` is STALE and has produced wrong numbers. Read
   live state.
