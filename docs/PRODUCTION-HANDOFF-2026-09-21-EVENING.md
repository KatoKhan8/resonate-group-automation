# Production handoff — 2026-09-21 evening

Written for a session with no conversation context. **Supersedes
`docs/PRODUCTION-HANDOFF-2026-09-21.md`**, which was written this morning and
whose headline — "still zero provider-confirmed sends" — is no longer true.

---

## 1. THE HEADLINE: THIS PROJECT SENDS EMAIL NOW

**489 sent two real emails today.** First at 13:34:48Z, second at 16:48:18Z.
Four independent witnesses on the first, three on the second:

    campaign counter   emails_sent 0 -> 1 -> 2
    scheduled rows     22341193 sent 13:34:48Z · 22341195 sent 16:48:18Z
    membership         5 leads in_sequence, per-lead [1,1,0,0,0]
    watcher            SEND on the counter AND on the queue row, both times

`bounced 0 · replied 0 · unsubscribed 0`. Six of eight rows still scheduled.
**No write was made to 489 on any day since activation.** It re-planned itself
at 22:01Z on 09-20 and sent on its own schedule.

**Enrolled is not sent, and two sends is not a campaign.** Deliverability is
unproven — one accepted send says nothing about inbox placement.

## 2. 487 IS BROKEN IN A WAY 489 IS NOT, AND THE GRANT IS SPENT

Three scheduler runs in one day, all leaving the queue at zero:

    09:06:10Z  the authorized resume          rows 10 -> 0
    15:05:15Z  the end-of-day cycle           rows 0, updated_at moved
    17:24:43Z  the authorized pause/resume    rows 0, readback at 17:27:45Z

`updated_at` moved on every one, so the provider acts on the campaign each
time and chooses to schedule no mail. `sending_schedule` reads
SendingScheduleEmpty for today, tomorrow and the day after.

**489 is the control that rules out the estate, the credential, the code path
and the sequence** — same workspace, same day, same everything, and it sent.

**DO NOT PAUSE/RESUME 487 AGAIN.** Both grants are spent. The standing
decision: read after tomorrow's end-of-day cycle (~15:05Z, Mon-Fri
07:00-15:00Z window). **If still zero, 487 is PARKED and its ten leads are
released** for re-enrollment into batch campaigns, subject to the collision
rule below.

## 3. THE ESTATE IS ATTESTED — 0 to 159 IN ONE DAY

    HUMAN_IDENTITY_ATTESTED   0 -> 159 mailboxes across 8 humans
    SAFE_FOR_PRODUCTIVE       0 -> 159
    LinkedIn seats            33 attested of 41 (8 skipped, invalid auth)

Per human: kresimir 64 · bernarda 50 · ivan 13 · fran 12 · tomislav 11 ·
bojan 6 · jakov 2 · luka 1. Fifteen Not-connected mailboxes skipped.

**The roster held DEMO PERSONAS before today** — `anna`, `john`, `mark` and
four others, seeded by `src/web/demoaccount.py`. The eight real humans are the
first real entries in it.

**EXCLUDED by operator decision, and this is a register row so nobody reads
them as spare capacity:** Casey Wright, Morgan Ellis, Riley Parker — 51
connected mailboxes, never attested, bounce rate 1.97% against the attested
estate's 0.83%.

**Real names are PII and live only in gitignored `work/senders.jsonl`.**

## 4. THE REPOSITORY IS PUBLIC

`private: false`, verified by an unauthenticated clone. Four real identities
were removed from HEAD today and **no real name remains in the tracked tree**,
but **thirteen commits since 2026-09-15 carry one in their diff**, two of them
heavily (`d765ccb1` 16 names, `65ae7316` 10), plus one real mailbox address in
two commits.

**Flip to private FIRST, then rewrite history.** A force-push alone does not
remove fetchable objects. Operator decision, not taken.

## 5. STANDING POLICY DECISIONS — all operator, all 2026-09-21

    PROVIDER ORDER        ContactOut -> free scrapers/endpoints -> Blitz ->
                          AI Ark -> other paid. Each called only for what the
                          previous did not return. ENRICHMENT only.
    VERIFICATION ROLES    primary deliverable · secondary reoon ·
                          catch_all reoon · confirmations 2 · disagreement
                          hold. ContactOut REMOVED from verification, kept
                          first for enrichment. Scoped to Productive via
                          `policy_for`, defaults untouched, asserted by
                          tests/test_productive_verification_roles.py
    CREDIT SPEND          reported, NEVER gated. No cap, no balance pause,
                          no cost-per-READY pause. A rate limit means back
                          off and continue, never halt.
    COLLISION RECENCY     permanent exclusion: unsubscribe, negative reply,
                          bounce, unknown-reason stop. Same person: >90d and
                          no reply. Different person at a touched account:
                          >30d, no negative/unsub in 180d. has_reply excludes
                          REGARDLESS of recency. Unknown stays HOLD.
    PIPELINE ORDER        S6 COLLISION BEFORE S5 VERIFICATION, always.
                          Collision is free, verification is not.
    CROSS-CHANNEL         email human and LinkedIn seat need NOT match.
                          Within a channel the same human holds the thread.
    BATCHES               continuous, 2..N under the batch-1 conditions.
                          Sized by the PACING RULE - enrolled-but-unsent per
                          campaign <= 3 days of first-step capacity - not by
                          500. Stats, 15-minute veto, push.

## 6. TONIGHT'S COLLISION WALK — the number that unblocks batch 1

The input file `work/Productive/productive_ICP_safe_to_send (1).csv` is a
CONTACT file, not a domain file: 33,887 rows, 24,710 unique domains, dated
2026-09-07. **It is largely Productive's own prior outreach.**

    S1 hygiene        24,404 survivors (9,177 dupes, 306 already in store)
    S3 ICP            5,094 IN · 15,642 OUT · 3,668 flagged   (ZERO credits -
                      /domain/enrich never moved the search meter)
    S4b MX            known_allowed 7,631 · unknown_provider 773 ·
                      known_blocked 313 · no_mx 39 · dns_failure 6
    S6 collision      of 644 touched accounts: 427->559->644 as S5 grew

**THE LAST-TOUCH INDEX IS BUILT AND PERSISTED: `work/stage/last-touch.json`.**
1,386 leads dated. This is the thing that must never be re-walked — keep it
current from every push and every reply webhook.

Getting it required three dead ends worth recording so nobody repeats them:

    scheduled_emails(352)   REFUSES - 96,045 rows over 6,403 pages, and the
                            adapter correctly will not return a partial as
                            though it were the whole
    membership()            returns status strings only, no dates
    lead.created_at         lead CREATION, not last touch - a lead created in
                            April may have been mailed last week
    lead.updated_at         THE ANSWER. Bounded, one call per lead, a real
                            provider last-activity timestamp

Real last-activity buckets over touched accounts:

    <=30 days    13        31-90 days   477        91-180 days  154

Applying the recency rule: **519 ELIGIBLE ACCOUNTS carrying 878 VERIFIED
CONTACTS.** Excluded: 110 has_reply, 25 any_bounce, 8 within 30 days.
Candidates in `work/stage/batch1-candidates.json`.

## 7. S5 VERIFICATION STATE

    3,340 decided of ~9,300      verified 1,245 · held 1,885 ·
                                 accept_all 133 · unknown 51 · invalid 26
    pairs                        (contactout, reoon) and (deliverable, reoon)

**Deliverable's contract gate was opened today on a real answer** (one credit,
our own address, parsed to `accept_all`). Its `valid`/`invalid` paths are
parsing — `unknown` is 51 of 3,340, not a wave.

**K=3 AND DO NOT RAISE IT WITHOUT MEASURING.** K=8 was sized against Reoon's
4/sec and ignored the primary: 93% of holds read "the primary is missing"
because ContactOut was 429ing and billing nothing. Verified went 16% (K=8) ->
47% (K=3, ContactOut primary) -> 92% (K=3, Deliverable primary). Those
throttled holds are now RE-ASKABLE rather than recorded as verdicts.

## 8. ENGINEERING

    TASK-214  MERGED e197f0b5   the free crawl had zero callers - it sat
                                below `if not live: return []`
    TASK-238  MERGED            seat-level attribution drops the client's
                                unmatched HeyReach traffic. 38 ambiguous
                                events, 0 notifications raised
    TASK-240  NOT MERGED        superseded by 241
    TASK-241  SUITE RUNNING     arity moved to the action, gate order
                                restored. 141 tests green including the
                                tenancy suite, spec file untouched.
                                MERGE ON ZERO NEW FAILURES against
                                10,671 / 50 / 33. On any new failure send it
                                back to Qwen with the failing test named.
    TASK-239  BLOCKED           behind arity, by operator ordering

**Until arity merges, batch campaigns name ONE mailbox each: 8 × 15 = 120
first-step sends/day.** Merged, each names all of its human's attested
mailboxes and the same 8 campaigns carry thousands.

Lowest-bounce mailbox per human is chosen and recorded (kresimir and bernarda
at 0.11%, jakov highest at 0.73% — all far under the 2% hard stop).

## 9. SLACK

Live on `#resonate-notifications` (C0C34GCAR27), smoke test returned
`ts 1789990679.422989`. `productive.slack_workspace_channel = C0BFUF4JRK9`.

**`notify.notify()` only PLANS.** `scripts/notify_deliver_loop.py` (NEW today)
is the only thing that delivers; before it, 244 notifications sat undelivered
while Slack was proven working. It touches PLANNED rows only — suppressed
stays held, unconfigured is the replay's business, sent is never re-sent.

**11 rows are SUPPRESSED by decision** — 2 pre-TASK-238 unmatched replies and
9 from 2026-08-28 pointing at stale channel names. No replay, ever, for
today's 21.

Watchers now raise `campaign_milestone` on first send / reply / bounce /
sequence finished, idempotent through `notification_id`. **Today's 489 send is
deliberately NOT back-filled.**

Digest: daily 05:00 UTC = 07:00 Zagreb. **DIGEST_HOUR moves 5 -> 6 on
2026-10-25** when DST ends.

## 10. MONITORS — restart bare, NEVER under `timeout`

    86848   bison_mailbox_utilisation --interval 300
    19236   reply_watch_loop --interval 300
    95760   notify_deliver_loop --interval 60
    89640   bison_watch_loop --campaign 487 --interval 180
    105276  bison_watch_loop --campaign 489 --interval 180
    92332   heyreach_watch_loop --interval 300
    90260   stage_s5_verify --workers 3
    105956  tests.offline (TASK-241 gate)

## 11. TOMORROW'S FIRST THREE ACTIONS

1. **Check TASK-241's suite.** Zero new failures against 10,671/50/33 ->
   merge without asking, re-run the eligibility readback, re-point the 8
   campaigns to all attested mailboxes of their human at 15/mailbox/day, and
   report the new first-step capacity. Any new failure -> back to Qwen with
   the failing test named, and continue everything else.

2. **Batch 1 before the 09:00 Zagreb window.** 878 candidates exist against a
   360 pacing cap (120/day × 3 days, single-mailbox branch). Run S7 copy from
   the approved Productive templates with the threading invariant, post the
   stats to `#resonate-notifications`, wait the fifteen-minute veto, push.
   State **120 first-step sends/day** explicitly and that **enrolled is not
   sent**.

3. **Read 487 after ~15:05Z.** Still zero -> park it and release its ten
   leads. Do not pause/resume it: both grants are spent.

Then: nightly sourcing at 02:00 Zagreb (AI-ARK company search, headcount >=20
and geos applied at source, walk to last=true, diff never delete), and the
learning tags on every enrolled lead.

## 12. WHAT MUST NOT BE RE-DERIVED

- `/domain/enrich` costs NOTHING measurable. 24,404 domains moved the search
  meter by zero. The 4,000-credit cap never governed S3.
- The endpoint returns ALL 30 domains per call. One call per domain is 6.8
  hours; batched it is fourteen minutes.
- ContactOut's limit on the verifier family is ~60/min. Eight workers made
  ~168/min and lost 93% of answers to 429s that billed nothing.
- There is NO documented HeyReach endpoint resolving a conversation id to its
  campaign. `GetConversationsV2` filters on campaignIds but whether items
  CARRY that field is not documented. Seat attribution works because
  `linkedInAccountId` IS present and 174892 is our only seat.
- Commit and push are TWO commands. A compound one was refused by the Claude
  Code permission classifier — not git, not GitHub — and the transcript said
  "push blocked" for an hour.
- `productive_ICP_safe_to_send` is the supplier's claim. 97% of its domains
  were already contacted.
