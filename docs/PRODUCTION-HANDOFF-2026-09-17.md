# Production handoff — 2026-09-17 (evening). REPLACES the morning version.

Written for a session with ZERO conversation context. Everything here is read
off provider truth, the code, or a measured run. **Recompute before acting.**

    py -3 scripts/production_status.py          the numbers
    py -3 scripts/verification_inventory.py     SENDABLE / HELD / NEVER_OFFERED
    py -3 scripts/email_sender_estate.py        who owns which inbox, headroom
    py -3 scripts/sender_pool_census.py         the safe pool, and why it is 0
    py -3 scripts/bison_mailbox_utilisation.py --report
    py -3 scripts/next_ready_cohort.py          READY / NEAR_MISS / blocked

**UNKNOWN IS NEVER 0. LIVE IS NOT SENT.** A zero meaning "we could not ask"
and a zero meaning "nothing happened" are the two answers this system exists
to keep apart.

**THE MORNING VERSION OF THIS FILE CARRIED TWO CLAIMS THAT ARE NOW DISPROVEN.**
Do not reinstate them: the "provider assigns leads at the window OPENING"
hypothesis is dead (it assigns at the END of the sending day, documented and
observed), and "487's share of its mailbox today is zero" was an inference,
not a measurement — the mailbox sent 11 of 15 and 487 got none of them for a
different and now-known reason.

---

## 1. CURRENT PRODUCTION TRUTH, 2026-09-17T19:30Z

### EmailBison

    CAMPAIGN_ID        487
    PROVIDER_STATUS    active
    LIVE               True
    LIVE_CONTACTS      10   (all in_sequence)
    SENT               0
    REPLIES            0
    BOUNCES            0
    UNSUBSCRIBES       0
    SCHEDULED_EMAILS   10   one per lead, step 4742 (the opener),
                            thread_reply false, status `scheduled`
    SCHEDULED_AT       2026-09-23  07:12 08:24 08:55 09:46 10:00
                                   11:13 12:35 12:42 13:22 14:00  UTC
    TIMEZONE           Europe/Zagreb
    SEND_WINDOW        09:00:00 – 17:00:00
    SENDING_DAYS       Mon–Fri (saturday false, sunday false)
    ATTACHED_SENDERS   [2736]          ← ONE sender, not two. 3941 was
                                        detached on 2026-09-17
    CONNECTED_SENDERS  210 of 225 in the workspace
    REAL_CAPACITY      2736: daily_limit 15, and its forward book is FULL
                       (15/15) on 18, 21 and 22 September
    READBACK_STATUS    configdiff.compare_bison → PASS
    SEQUENCE           3 steps. step1 `{SUBJECT_1}` thread_reply false wait 3;
                       step2 `Re: {SUBJECT_1}` thread_reply TRUE wait 4;
                       step3 `Re: {SUBJECT_1}` thread_reply TRUE wait 1.
                       The "Re:" is the provider's own. No SUBJECT_2/3 exists.

**THE COPY RENDERS.** All ten queued rows were checked: zero unresolved
`{PLACEHOLDER}` tokens, zero empty subjects, zero empty bodies, zero greetings
without a name. First name, company (three times in the body) and industry all
resolve. **Ingest → enrichment → ICP → verification → generation → lint →
claims → approval → stage → schedule is proven end to end for this cohort.**
Only the send has not happened.

### HeyReach

    CAMPAIGN_ID           605732
    PROVIDER_STATUS       IN_PROGRESS since 2026-09-16T20:12:25Z
    LIVE                  True
    LIVE_CONTACTS         3   (all InSequence)
    CONNECTION_REQUESTS   0
    MESSAGES_SENT         0
    REPLIES               0
    SENDER_IDS            [174892]
    REAL_CAPACITY         that seat sits in 46 campaigns, 13 IN_PROGRESS; its
                          share of a 40/day connection ceiling is roughly 3
    NEXT_PROVIDER_ACTION  a CONNECTION_REQUEST, expected 2026-09-18
    READBACK_STATUS       configdiff.compare_heyreach → PASS
    BOUND LIST            944355, 3 leads, each holding its 8 approved variables
    SEQUENCE              17 nodes / 8 word-bearing, hash 32f8dde79bfa0f27,
                          byte-identical to the audited 599020

### The ledger

13 keys, all `unresolved` — the honest state for "running, nobody contacted
yet". **Scheduled is not sent.** A key becomes `sent` only when the provider
says that person was sent to.

---

## 2. WHY 487'S TEN EMAILS ARE QUEUED FOR 23 SEPTEMBER

Full working in `docs/WHY-487-IS-QUEUED-FOR-THE-23rd-2026-09-17.md`.

### OBSERVED — the cause, measured from provider truth

`/campaigns/{id}/scheduled-emails` carries a full `sender_email` object per
row, so the sibling campaigns' queues say what mailbox 2736 is already
committed to. **Sampling 9,000 rows** across campaigns 327, 328 and 352 —
quote THIS table, not the 3,600-row one that appears in the working document,
which put 2911 at zero on the 18th and was a sampling artifact:

    sender   09-18  09-19  09-21  09-22  09-23  09-24  09-25   limit
      2736      15      0      15      15      0      0      0      15
      2903      16      0      15      15      0      0      0      15
      2904      15      0      15      15      0      0      0      15
      2906      16      0      15      15      0      0      0      15
      2911      15      0      15      15      0      0      0      15
      3437       6     14      15       4      0      0      0      15

**2736 is booked at its limit on the 18th, 21st and 22nd. The 23rd is the
first day with free capacity, and that is where all ten openers landed.**
Cross-check: `bison_mailbox_utilisation.py` measured 2736 actually sending +11
today, and the sample shows 11 rows scheduled for today. Two routes, one
number.

**Two caveats that a fresh session must carry forward.** 2903 and 2906 read
SIXTEEN against a configured limit of 15, so 15 is not provably a hard
per-day ceiling — UNKNOWN whether the limit is per calendar day at all, or
whether UTC-date bucketing crosses a boundary the provider does not use. And
ALL SIX read zero on the 23rd, 24th and 25th, so an equally good reading is
"the scheduler has planned these campaigns only as far as the 22nd and the
23rd is the frontier". Both put 487's ten in the same place; they differ in
what would happen if a mailbox were freed.

**NOT the step delay.** Canary 451 carried the identical `wait_in_days: 3` on
its only step and its first `scheduled_date` was the SAME DAY it was created.
Same field, same-day there and six-day here — so it is not what differs.

### DOCUMENTED

- The scheduler runs **on campaign resume and at the end of every sending
  day**, and **pause+resume is the documented way to run it early**.
  (docs.emailbison.com/campaigns/overview) — which is why 487's rows appeared
  at 15:02:48Z, two minutes after its window closed.
- `DELETE /api/campaigns/{id}/remove-sender-emails` is documented as "remove
  sender emails **from a draft or paused campaign**". 487 is ACTIVE.
- Sender `daily_limit` is documented mailbox-scoped: "the daily limit of
  emails that can be sent from this sender email."
- Per-lead sender stickiness **after the first send**: "once a lead has been
  sent an email in a campaign, the same Sender Email will send the remaining
  steps for that lead."

### OUR CONFIGURATION

Campaign 487 names exactly one sender, 2736, which also serves three ACTIVE
client campaigns. Window 09:00–17:00 Europe/Zagreb, Mon–Fri. Caps 20/20, both
non-binding against the mailbox's 15.

### UNKNOWN — every one of these was asked of the vendor and is not documented

- How `scheduled_date` is computed for the first step.
- Whether a shared `daily_limit` is what pushes leads to a later day (the
  measurement says it is; the vendor does not say so).
- What `wait_in_days` means on the FIRST step.
- **What happens to already-scheduled rows when a campaign's senders change.**
- Any field reporting a mailbox's remaining capacity or forward book.

A marketing FAQ says shared sender limits "may deplete first". That is not a
scheduling contract and must not be treated as one.

---

## 3. TOMORROW'S EMAIL OBJECTIVE — SAFE SENDS ON 2026-09-18

The operator wants safe Productive email going out on the 18th rather than
waiting for the 23rd. This is **not** permission to mutate 487 blindly.

### What would work, and why it is not simply available

487 needs ten free slots on the 18th. 2736 has **zero**. Raising its limit is
forbidden (`PRODUCTION-SCALE-POLICY.md`: a sender estate is never made to
carry more by raising a limit) and would push the client's own campaigns onto
a mailbox already at its ceiling.

**AND THERE IS NO FREE INBOX AMONG THIS HUMAN'S SIX.** A 3,600-row sample said
sender 2911 had all fifteen slots free on the 18th. A 9,000-row sample of the
same queues, run to firm that up BEFORE recommending a mutation, overturned
it:

    sender   09-18  09-19  09-21  09-22  09-23  09-24  09-25   limit
      2736      15      0      15      15      0      0      0      15
      2903      16      0      15      15      0      0      0      15
      2904      15      0      15      15      0      0      0      15
      2906      16      0      15      15      0      0      0      15
      2911      15      0      15      15      0      0      0      15
      3437       6     14      15       4      0      0      0      15

**2911 is at 15 on the 18th, like the rest.** The zero was a sampling
artifact. Two further observations: 2903 and 2906 read SIXTEEN, above their
configured limit, so 15 is not provably a hard per-day ceiling (UNKNOWN); and
all six read zero on the 23rd, 24th and 25th, so the pattern may be "the
scheduler has only planned as far as the 22nd" rather than "2736 is full".

What remains true and useful is the identity comparison: 2911 is the SAME
human as 2736 — same name hash `c62bbb200b21`, byte-identical signature
`9d5ab0201ca9`, Connected, 1,793 lifetime sends, 0.50% bounce against 2736's
0.63%. **If a free day ever exists, 2911 is the right inbox.** 3437 has room
on the 18th and is rejected at 2.1% lifetime bounce, above the DEGRADED
threshold `senderinventory` already applies.

### THE DOOR IS CLOSED BY DOCUMENTATION, NOT BY CAUTION

The swap needs `remove-sender-emails`, which is **documented only for a draft
or paused campaign**. Reaching that state means pausing 487 — and a probe
already paused this campaign once and could not restart it (commit 105b86ed).
On top of that, what a sender change does to the ten already-scheduled rows is
NOT DOCUMENTED. Those rows are the first real artefact this campaign has
produced.

**So: do not swap 487's sender to hit the 18th.** The risk is losing a working
queue to reach an undocumented state, on a route the vendor documents for a
different campaign state.

### THE SAFER ALTERNATIVE, and what it needs

**Because no inbox of 487's human is free on the 18th, a swap would not help
even if it were documented for an active campaign.** The alternative is
structural, not a mutation of 487.

A NEW campaign is created in DRAFT. A draft is exactly the state
`attach-sender-emails` and `remove-sender-emails` are documented for, so its
sender can be chosen freely — including 2911 or any other inbox with a free
forward book. Leads are staged while it is a draft (`maximum send exposure is
ZERO`), then it is activated, and the documented scheduler runs on resume.

**It cannot reuse 487's ten leads** — they are already queued, and a second
campaign holding them is a duplicate send. It therefore needs DIFFERENT
contacts, which means the near-miss seventeen, which are blocked on operator
approval (section 4). That is the real dependency, and it is worth stating
plainly: **tomorrow's send is gated on an approval, not on an engineering
problem.**

If no approval arrives, 487 sends on the 23rd and that is the safe outcome.

---

## 4. COHORT AND PIPELINE, recomputed

    TOTAL_RECORDS      550
    ACCOUNTS           91 records hold any contact; 67 hold a SENDABLE one
    CONTACTS           277
    EMAIL_CADENCE      51 contacts
    LINKEDIN_CADENCE   81 contacts
    DOUBLE_VERIFIED    68 SENDABLE (policy: 2 independent confirmations)
    HELD (verification) 13
    NEVER_OFFERED      159  (140 skipped by a per-record cap, 19 whose record's
                            verification stage never ran)
    NO_ADDRESS         37
    LIVE               13  (10 email + 3 LinkedIn)

Record states: `queued` 315, `dropped` 126, `verified` 64, `held` 33,
`drafted` 8, `approved` 4.

### The near-miss cohort — 17 contacts, blocked on ONE thing

    CONTACTS           17   (12 LinkedIn + 5 email)
    ACCOUNTS           15   (10 LinkedIn + 5 email)
    STEPS              75   (60 LinkedIn + 15 email)
    APPROVAL_STATUS    NOT APPROVED. 13 carry no approval at all; 4 carry a
                       `self` stamp, which does not certify
    SAFETY_STATUS      every other gate passes — copy renders, tenancy,
                       eligibility, suppression, lint, claims, fatigue,
                       collision, account collision
    PILOT_CAP_EFFECT   `new_accounts_per_day: 5` is enforced at gate 5 AND
                       inside the reservation lock, so 15 accounts spread over
                       about three days
    PACKET             work/approval/NEAR-MISS-PACKET-2026-09-17.md
                       (gitignored, real copy, real names — NEVER commit it)

**Approving them is an operator action. Do not approve on their behalf** — 84
approvals stamped `by: "claude"` were revoked for exactly this reason, and on
a `generated: true` step a self-stamp never expires.

### What blocks everyone else, measured — and three routes that buy NOTHING

    LINKEDIN 66 blocked          EMAIL 36 blocked
      33 account mid-sequence      14 account ended early (REAL history)
      18 account ended early       13 account mid-sequence
      11 account has replied        4 account has replied
       3 prior sends, finished      4 prior sends, finished
       1 an address bounced         1 an address bounced

- **Generating the 9 missing-copy LinkedIn steps unblocks zero** — all nine
  are account-blocked as well.
- **The 32 "campaign ended early" holds are NOT our own staging.** Every one
  carries real prior sends (2 to 31 emails). `collision.without_our_staging`
  is working; there is nothing to recover.
- **Verifying the 159 is not the bottleneck.** They sit on 32 records, 19 of
  which already have a sendable contact, so 318 credits buys at most 13 new
  accounts and 58 credits buys the same 13. And it converts nothing while the
  Deliverable leg is closed: with `required_confirmations: 2` and no secondary
  vendor, ContactOut alone moves them from NEVER_OFFERED to HELD.

---

## 5. MISSION AND AUTHORIZATION

    P0  REAL PROVIDER-CONFIRMED SENDS
    P1  MORE SAFE LIVE LEADS
    P2  CONTINUOUS READY -> LIVE
    P3  MAXIMUM SAFE SENDER CAPACITY
    P4  RECIPIENT-LOCAL SCHEDULING
    P5  HEYREACH MULTI-SENDER
    P6  STORAGE / EVIDENCE SCALE
    P7  LEARNING
    P8  CONTINUOUS PRODUCT DEVELOPMENT

Run the loop continuously and do not stop after the first send, ten leads,
seventeen leads or one larger cohort:

    DISCOVER -> QUALIFY -> ENRICH -> VERIFY -> COLLISION -> GENERATE ->
    APPROVE -> READY -> ALLOCATE -> LIVE -> SEND -> OBSERVE -> RECONCILE ->
    LEARN -> REPLENISH

`docs/OPERATOR-AUTHORIZATION-2026-09-15.md` is the standing grant and survives
`/clear`. **487's additional-sender decision is CLOSED. Do not ask again.**

Stop for the operator ONLY on: a genuinely new irreversible or material
decision, a safety invariant that would have to be weakened, credentials you
do not have, or provider truth showing systemic production failure.

---

## 6. SAFETY INVARIANTS THAT MUST NOT REGRESS

- **Double email verification.** Two independent vendors must explicitly PASS
  the same normalised address. UNKNOWN is not PASS. Catch-all stays
  conservative. Relaxing `required_confirmations` to 1 was measured: it admits
  three more contacts. Three.
- **Exact identity only.** `HumanSenderIdentity` is separate from a provider
  seat. Sender ownership is sticky once outreach begins. Never fake
  continuity.
- **Account and contact collision / history.** The account is the unit of
  outreach. Our own silent staging is not prior contact, and only four arms of
  positive provider evidence may exclude a row.
- **Cross-channel reply suppression.** An inbound reply on either channel
  stops future cadence for the SAME LEAD on BOTH. Canonical state first, then
  provider effects.
- **Email threading.** Step 1 owns the only subject; steps 2..N are thread
  replies referencing `{SUBJECT_1}`; no `SUBJECT_2..N` is ever generated; we
  never write "Re:" ourselves. **CONTROL V3 is three steps and must not be
  modified casually** — it is a production-safe control, not evidence that
  three touches is optimal.
- **Provider writes.** WRITE → READ BACK → COMPARE → RECONCILE. A 200 is not
  an answer.
- **No fabricated claims.** A message may only claim what the event log
  supports. A material copy edit invalidates its approval — `_certified_copy`
  hashes the words it is about to stage.
- **Pilot and account caps stay enforced.** `new_accounts_per_day: 5`, both at
  the gate and inside the reservation lock.
- **A bad record is HELD or DROPPED with a reason, and unrelated safe records
  continue.** One bad lead must never stop the batch.
- **The sender arity rule** (`executionguard._sender_for`) refuses a canonical
  row naming more than one sender. Do not relax it; the replacement predicate
  exists (section 9) and is not yet wired.

---

## 7. EMAILBISON AND HEYREACH LEARNINGS, CLASSIFIED

### DOCUMENTED (vendor docs or the OpenAPI spec, with a URL)

- **Per-lead sender stickiness after the first send.** "Once a lead has been
  sent an email in a campaign, the same Sender Email will send the remaining
  steps for that lead, as well as emails sent to the lead from a followup
  campaign." (docs.emailbison.com/campaigns/overview)
- **The first send's sender picker is NOT documented** — no round-robin, no
  weighting, no selection field anywhere in the spec. The only request field
  naming a sender is on a TEST send.
- **Recipient-local sending does not exist.** No schedule flag, no campaign
  setting, no lead timezone field. A marketing page claims it; there is no
  mechanism. **Do not build on it.**
- **The scheduler runs on resume and at the end of every sending day**, and
  pause+resume is the documented way to run it early.
- **`remove-sender-emails` is documented for a DRAFT OR PAUSED campaign.**
- **Webhooks** for Email Sent, Opened, Contact Replied, Email Bounced, Contact
  Unsubscribed, Contact Interested, Untracked Reply Received, Tag
  Attached/Removed. Configurable by `POST /api/webhooks`. Retried **5 times
  over 24 hours**, 15-second attempt timeout. **`/api/events` replays the last
  10 days**, so a missed webhook is recoverable.
- **HeyReach defaults an omitted schedule to Mon–Fri 09:00–17:00 UTC.**
  `create_linkedin_cohort_b_campaign.py` passes none, so 605732 runs on that
  default — which is 05:00–13:00 US Eastern.
- **A HeyReach schedule cannot be read back.** `UpdateSchedule` writes;
  `GetAll` carries no schedule field; whether `GetById` returns one is not
  documented. `heyreach.set_schedule` refuses to write one for this reason.
- **Primary sources nothing here had read**:
  `https://dedi.emailbison.com/api/reference.openapi` and
  `https://docs.emailbison.com/llms.txt`.

### DOCUMENTED BY INTEGRATOR (not by the vendor)

- **`POST /campaign/AddLeadsToCampaignV2` with `accountLeadPairs`** binds a
  lead to a `linkedInAccountId`, max 100 pairs — documented by Scalekit,
  Cotera and the n8n HeyReach node, **not** by HeyReach's own campaign page.
  `linkedInAccountId` is nullable and the omitted-case behaviour is not
  documented. `heyreach.build_lead_pairs` already builds this shape.
  **So LinkedIn's per-lead sender is CHOSEN and email's is OBSERVED. Two
  channels need two allocator contracts, not one.**

### OBSERVED (this estate, measured)

- **Sender stickiness, independently**: 243 leads seen at more than one
  sequence step across campaigns holding 59 and 222 attached senders, **zero
  rotations**. Measured before the documentation was found; they agree.
- **2736's forward book** is full at 15/15 on 18, 21 and 22 September; the
  23rd is the first free day. The cause of 487's schedule.
- **The estate is ~17% used.** 3,150/day connected capacity, 540 sent in a
  6h44m window, **137 connected mailboxes sent nothing at all**, and not one
  inbox reached its limit (busiest: 12 of 15).
- **Fifteen of 225 inboxes read `Not connected`**, each with 328–371 lifetime
  sends, each moving ZERO. They are not capacity.
- **Twelve humans own the 225 inboxes**, including a near-duplicate pair one
  edit apart holding 66 and 5 inboxes.
- **`scheduled_date_local` is six hours ahead of `scheduled_date`** while
  Zagreb is UTC+2, and six of ten "local" values fall outside the campaign's
  window while all ten UTC values fall inside it. `scheduled_date` is the
  field that means something. Nothing reads the other.
- **HeyReach `PROGRESS`**: on 2026-09-17 one of 605732's three leads moved
  `lastActionTime` from 09:05:39Z to **18:59:54Z** — two hours after the
  documented default window closes — while the other two did not move at all.
  Unexplained; four candidate readings recorded and none chosen.

### HYPOTHESIS

- That the mailbox's shared daily limit is the mechanism deferring 487. The
  measurement is strong and the vendor does not document the mechanism.

### UNKNOWN

Everything in section 2's UNKNOWN list. Also: whether `occurred_at` on a
webhook is occurrence time or delivery time — which decides whether the
webhook dedupe key survives a retry.

### DISPROVEN — do not reinstate

- "The provider assigns a day's leads at or near the window OPENING."
  It assigns at the END of the sending day. Documented and observed.
- "487's share of its mailbox today is zero because the mailbox is shared."
  The mailbox sent 11 of 15 today; the deferral is about the FORWARD book.

---

## 8. WORKFORCE STATE

    CLAUDE   orchestration, integration, provider mutations, final review.
    QWEN     C:\Users\Zvonimir\AppData\Local\qwen-code\bin\qwen.cmd
             --approval-mode yolo "<prompt>"  — run from inside its worktree.
             Write the brief to `work/TASK-*.md` in that worktree and give the
             one-line prompt "Read work/TASK-X.md now and follow it exactly."
             A long multi-line prompt on the command line gets truncated.
    GLM      `py -3 scripts/glm_review.py --list` — targets storage, ledger,
             collision, webhook, attestation.
    GROK     `py -3 scripts/grok_provider_research.py --list` — three of six
             questions still unrun: bulk, scheduling, heyreach_sender.
    PYTHON   the deterministic data plane; every script named at the top.

**ALL WORKERS ARE IDLE AS OF THIS HANDOFF.** Nothing is mid-flight. Every
branch below is pushed.

    BRANCH                                    WORKTREE            STATE
    geo-iso-resolution-2026-09-17             resonate-qwen-2     INTEGRATED
    staged-paused-activation-order-2026-09-17 resonate-qwen-3     INTEGRATED
    bison-webhook-ingest-2026-09-17           resonate-qwen-4     INTEGRATED
    task202-suite-2026-09-17                  resonate-qwen-worker INTEGRATED
    qwen-worker-5-r46 / -6-r40 / -7-r28 / -8-r28   older, untouched today

`qwen-worker-r9` reports UNPUSHED because its local tip diverged from its own
remote long ago; the 15 local commits were preserved to
`qwen-worker-r9-local-2026-09-17` rather than force-pushed. Nothing is at risk.

### MONITORS — session-scoped, they die with the session. RE-ARM THEM.

    py -3 -u scripts/bison_watch_loop.py --interval 300
    py -3 -u scripts/heyreach_watch_loop.py --interval 300
    py -3 -u scripts/reply_watch_loop.py --interval 300
    py -3 -u scripts/bison_mailbox_utilisation.py --interval 300 --samples 200 --quiet

Each emits on FAILURE as well as success, so silence means unchanged. The
first two now carry events added today: `QUEUED`, `TOUCHED` and
`SCHEDULE-MOVED` on EmailBison, `PROGRESS` on HeyReach. **`PROGRESS` caught
something no other tool could see** — use them.

---

## 9. VERIFIED ENGINEERING FINDINGS

    FIXED     actionledger.settle inherited the previous event's
              `provider_response`, so a deferral's 421 was recorded as though
              a later FAILED settlement had produced it. 13 keys sit at
              `unresolved` now, so this mattered today.
    FIXED     actionledger.settle silently discarded a same-state replay
              carrying NEW evidence — a corrected message id, a late delivery
              readback — while returning success. Identical replays still
              append nothing.
    FIXED     docs/state/QUEUE-MANIFEST.json published `stages: {"unset":550}`
              and `dropped: 0` because the generator read three field names no
              record carries. 126 records really are dropped.
    FIXED     the canonical sender roster was 8 days stale; 15 inboxes had
              gone Connected → Not connected while canonical state called them
              `active: true, health: "ok"`. Rebuilt; ready capacity 2,790/day.
    FIXED     `tests/test_fixture_hygiene.py` knew every prospect name and no
              name of a person who SENDS. Three tracked files named all ten
              inbox owners and all thirteen assertions passed. Extended; it
              immediately caught a fourth.
    FIXED     glm.GLM_TIMEOUT 60 → 180 and xai.XAI_TIMEOUT 60 → 300. Both were
              ceilings set below their model's working range, silently turning
              a review or a research call into nothing.
    FIXED     three holes in the webhook normaliser found by GLM before it had
              a caller: a bare ValueError on a non-numeric workspace id (and
              it preceded the tenancy check, so a probe got a distinguishable
              500); `int(True) == 1` passing tenancy on a workspace pinned to
              1; and unguarded indexing in `event_key`.
    PROVEN    geo/ISO resolution 21 → 33 of 67 records, US refusal intact,
              MEDIUM tier verified CONSUMED by `schedulable()`.
    PROVEN    whichever of two staged campaigns activates SECOND is refused.
              8 tests, zero `src/` lines changed, break-proof recorded.
    PROVEN    EmailBison sender stickiness, 243 leads, zero rotations.
    PROVEN    2736's forward book is the cause of the 23rd.
    IN_PROGRESS  `senderownership.one_attested_human` — the predicate that
              would REPLACE the arity rule. Landed, tested, GLM-reviewed, and
              deliberately WITH NO CALLER: adopting it needs a decision about
              what the action ledger records as `sender_id`, which is today a
              provider inbox and honestly a human once a campaign holds
              several.
    IN_PROGRESS  `src/bisonevents.py` — webhook normaliser + idempotency key.
              Pure, no server, no network import. **Not wired.** Every ASSUMED
              payload field must be checked against a real webhook, and
              `occurred_at` against a real RETRY.
    REJECTED  GLM's storage fix (checkpoint interval 5 → 200). Its arithmetic
              is accepted — O(N²), 63.6 TB per pass at 100k records, and every
              size-derived benchmark here understated 7.57× — but raising the
              interval trades against the lesson that put checkpoint-per-record
              there. The shape is the defect; incremental persistence is the
              fix.
    REJECTED  GLM's collision finding. FALSE POSITIVE, verified: the defeat
              needs an `in_sequence` row to be excludable and `_excludable`
              refuses anything outside {'sending_paused','stopped'}.
    REJECTED  my own ADAPT #1 (adopt a per-field evidence TTL). We already
              have a richer freshness model. **The real gap is identity:**
              `evidence.evidence_id` hashes `record_id` into its material
              while its docstring claims the id is derived from what the
              evidence IS, so a company met in a second cohort re-pays and no
              TTL would help.
    DEFERRED  an MCP/CLI control surface. Right shape, wrong time; half of it
              already exists as the status scripts.

---

## 10. EXTERNAL LEARNING BACKLOG

`docs/GTM-REPO-REVIEW-2026-09-17.md` holds the first pass, under one rule:
**a README is a claim, not an implementation.** It earned the rule — OpenGTM's
"~90 sourcing sources" are 92 DuckDuckGo query templates, and its cross-row
cache and confidence early-exit are not called on the workbook hot path.

Reviewed: OpenGTM (deep), OpenProspector, outreach-agent, linki, gtm-system.
**Still to review**: jay-sahnan/signal, getaero-io/gtm-signal-scoring,
cmn-labs/autogtm, explorium-ai/gtm-skills, dhisana-ai/gtm-ai-tools,
signaliz/signaliz, pypesdev/coldflow, salim-ship-it/outbound-os,
Samyrrrrrr990/openleads.

Themes: provider waterfalls, cross-row evidence cache, evidence TTL, cost/yield
ledger, signal monitors, baseline/diff, buying signals, global contact history,
positive-reply metrics, sender health state machines, quarantine/recovery,
async callbacks, webhooks, MCP/CLI control surface, READY reservoir,
autonomous scheduling, multi-channel state, long-running agent recovery,
multi-tenancy, spend ceilings, provider capability registry.

**What we already do better and must not trade away** — none of the five
reviewed has any of it: reservation BEFORE the provider call, account-level
collision gating, two-vendor verification, approval fingerprints, live
LinkedIn execution.

**ADAPT, revised**: (1) stable evidence identity across cohorts; (2) a
cost/yield ledger as EVIDENCE FOR changing the routing policy, never an
automatic reorder that would quietly demote ContactOut; (3) a spend ceiling in
MONEY not calls — tonight's numbers are $0.196 a domain for Grok evidence and
~$1.40 a documentation question; (4) connector cursors that resume.

GLM compares patterns against our repo. Grok validates external facts. Qwen
implements only accepted bounded improvements. **Nothing is adopted because
another repository has it.**

---

## 11. GIT DURABILITY

    BRANCH              master
    WORKTREE_STATUS     clean (all nine)
    UNCOMMITTED_FILES   none
    ACTIVE_WORKTREES    9, listed in section 8

Never `git add -A`. Stage exact files. Never commit `.env`, a key, a
credential, prospect PII or `work/approval/*`. `work/` is gitignored and holds
300 real companies and 92 real contacts.

`work/queue.snapshot.jsonl` was RETIRED to `work/RETIRED-2026-09-17-*` in all
nine worktrees — renamed rather than deleted, so its fifteen historical
readers fail loudly instead of quietly answering from 2026-09-15. **Read live
state.**

---

## 12. OVERNIGHT FRESH SESSION BOOT PROMPT

> You are resuming Resonate OS, a live production outbound system, overnight
> and autonomously. Two campaigns are LIVE and neither has sent yet.
>
> 1. Read `CLAUDE.md`, then `docs/PRODUCTION-HANDOFF-2026-09-17.md` in full.
> 2. `git log --oneline -5 && git rev-parse master origin/master && git worktree list`.
>    Confirm clean and in sync.
> 3. Recompute provider truth and trust THAT over any document:
>    `production_status.py`, `verification_inventory.py`,
>    `email_sender_estate.py`, `sender_pool_census.py`,
>    `bison_mailbox_utilisation.py --report`.
> 4. **Re-arm the four monitors** in section 8 — they died with the last
>    session. Watch for `QUEUED`, `TOUCHED`, `SCHEDULE-MOVED` and `PROGRESS`.
> 5. **P0 is real provider-confirmed sending.** 487's ten openers are queued
>    for 2026-09-23 because mailbox 2736's forward book is full until then —
>    section 2 has the measurement. **Do not pause, re-approve, change the
>    sender on, or re-activate 487** without proving the change first;
>    `remove-sender-emails` is documented only for a draft or paused campaign
>    and what it does to ten already-scheduled rows is NOT documented.
> 6. The operator wants safe email sending on 2026-09-18. Section 3 says the
>    safe route is a NEW draft campaign on a mailbox with a free forward book
>    (the six inboxes of 487's human are all booked through the 22nd, so it needs
>    an inbox from a DIFFERENT human — which is why attestation matters) — and
>    that it needs contacts 487 does not already hold, which means the
>    seventeen near-miss contacts, which need an operator approval. If that
>    approval has arrived, build it. If not, say so and do not force it.
> 7. HeyReach 605732's first connection request is due 2026-09-18. **The
>    falsifier: if 2026-09-19 opens with all three leads at
>    `leadConnectionStatus: None` and `lastActionTime` unmoved since the 17th,
>    the graph explanation is wrong — investigate rather than extend it.**
> 8. Grow the SAFE cohort continuously. Do not stop at seventeen. Section 4
>    records three routes that buy nothing, so do not redo them.
> 9. Use Qwen for bounded engineering in its own worktree, GLM for adversarial
>    review of real code, Grok for external provider research, Python for the
>    deterministic data plane. Keep Claude on orchestration and irreversible
>    provider actions. Dispatch them in PARALLEL.
> 10. Continue the external architecture review (section 10) and implement
>     only ACCEPTED bounded improvements.
> 11. Commit and push after every integrated unit and VERIFY the remote.
>     Never `git add -A`. Never commit secrets, PII or the approval packet.
> 12. Write a new morning handoff/checkpoint before you finish.
>
> Decide and act on routine reversible work without asking. Stop for the
> operator only on a genuinely new irreversible decision, a safety invariant
> that would have to be weakened, credentials you do not have, or provider
> truth showing systemic production failure. **487's additional-sender
> decision is CLOSED — do not ask again.**
