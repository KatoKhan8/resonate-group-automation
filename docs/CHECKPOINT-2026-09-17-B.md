# Checkpoint 2026-09-17-B — what the handoff got wrong, and what is waiting on whom

Written for a session with zero conversation context.
**Read `docs/PRODUCTION-HANDOFF-2026-09-17.md` first. This corrects four of
its claims and supersedes none of the rest.** Recompute before acting:

    py -3 scripts/production_status.py
    py -3 scripts/verification_inventory.py
    py -3 scripts/email_sender_estate.py
    py -3 scripts/bison_mailbox_utilisation.py --report

    master   7e9c88f8, pushed and verified equal to origin/master

---

## 1. PRODUCTION, 2026-09-17T11:35Z

    EMAILBISON   487     active    10 leads   0 sent   0 queued   0 replies
    HEYREACH     605732  IN_PROGRESS 3 leads  0 sent   0 connects 0 replies
    LEDGER       13 keys, all `unresolved` - the honest state for
                 "running, nobody contacted yet"

**The two zeros have different causes and only one is a question.**

### LinkedIn is mid-ramp, not stalled

`docs/THE-LINKEDIN-STALL-IS-THE-GRAPH-2026-09-17.md`. The sequence's own graph
puts **thirty hours** between entering and the first connection request for a
non-connected lead: `CHECK_IS_CONNECTION -> VIEW_PROFILE (+3h) -> FOLLOW (+3h)
-> CONNECTION_REQUEST (+1 DAY)`. All three leads entered at ~09:04Z on
2026-09-17 (`lastActionTime` moved off `creationTime`). **First connection
request due 2026-09-18.** If 2026-09-19 opens with all three still at
`leadConnectionStatus: None` and `lastActionTime` unmoved since the 17th, that
is wrong and needs investigating rather than extending.

The watcher was blind to this: the three lifecycle fields describe connection
and message only, so a campaign working through profile views emitted nothing
and read exactly like a dead one. `heyreach_watch_loop` now emits `PROGRESS`.

### EmailBison has not been QUEUED, which is sharper than "has not sent"

`scheduled_emails` is a **lookahead queue, not a receipt** - canary 451's row
appeared carrying `scheduled_date: 2026-09-13T13:19Z`, nineteen minutes after
its window opened, then moved overnight and fired on the 14th twenty seconds
late. 487 has zero rows, and its `updated_at` has not moved since OUR write at
10:45:10Z while sibling campaigns 352 and 328 move theirs every few minutes.

`bison_watch_loop` now emits `QUEUED` and `TOUCHED`. **The standing hypothesis
- the provider assigns a day's leads at or near the window opening, and 487
was activated after 09:00 Zagreb on both attempts - predicts TOUCHED then
QUEUED between 07:00Z and 07:30Z on 2026-09-18.** If the window opens and both
stay silent, the hypothesis is dead. Discard it; do not extend it a day.

**487 must stay active and untouched until then. A pause resets the
experiment.**

### The capacity explanation is weaker than the handoff implies

Measured over 36 minutes across all 225 mailboxes: **11 emails from 7
inboxes**, roughly 5% of the estate's nominal 3,375/day. Sender 2736 sent
**zero** of them. A mailbox saturated by its other three campaigns is not what
that looks like. The sharing is real; the saturation is not established.

---

## 2. FOUR CORRECTIONS TO THE HANDOFF

**(a) "All 225 email and all 32 LinkedIn productive accounts carry
`sender_id: null` and there are ZERO ownership attestations."** Thirteen
accounts are attested and all thirteen are FIXTURES - workspaces `contactout`
and `demo-client`, provider ids `bison-1`, `4001`. The productive ones carry
real provider ids and none has an owner. Worse: the roster's seven
`productive` humans do not exist at the provider, which owns its 225 inboxes
under TEN different names. `allocate` returns `display_name` off the roster
row, so a naive backfill would attribute real sends to people who do not
exist. **The emptiness is protective.** See
`docs/THE-ROSTER-NAMES-PEOPLE-WHO-DO-NOT-SEND-2026-09-17.md`.

**(b) "`ensure` SWALLOWS it."** It does not. `NoEligibleSender` is recorded
under `block['unavailable'][channel]` with the reason, deliberately, so a
contact with no LinkedIn sender stays an email contact. Not a defect.

**(c) "143 contacts held by insufficient confirmations" / the 159.** The 159
is right and live. The decision number is not in the handoff at all: **those
159 contacts sit on 32 records, and 19 already have a sendable contact.**
318 credits buys at most 13 new accounts; 58 credits buys the same 13. See
`docs/THE-159-ARE-WORTH-58-CREDITS-2026-09-17.md`.

**(d) The queue manifest.** `docs/state/QUEUE-MANIFEST.json` was published
with `stages: {"unset": 550}` and `dropped: 0` because the generator read
three field names no record carries. 126 records really are dropped. Fixed,
with six behavioural tests.

---

## 3. WHAT IS WAITING, AND ON WHOM

    OPERATOR   approve some of the 17 near-miss contacts. Nothing else
               converts anybody this week.
    OPERATOR   open the Deliverable leg, or name a different secondary
               verification vendor. Until then ContactOut supplies one of two
               required confirmations and verification spend buys nothing.
    THE CLOCK  487's window opens 07:00Z 2026-09-18. 605732's first
               connection request is due the same day.
    A WORKER   TASK-202, the full suite, on branch `task202-suite-2026-09-17`.

**The estate's arithmetic, which says where the constraint actually is:**

    91  records hold any contact
    67  already have a SENDABLE contact
    17  contacts pass every gate except approval
    13  are live

The verified pool is nearly five times what the approval queue can pass.
Neither verification nor capacity nor providers nor copy is the bottleneck.

---

## 4. WHAT WAS DONE, 2026-09-17 SESSION B

Recovered an uncommitted worktree (a provider-agreement gate whose expected
side was EMPTY, eight test modules' fixtures, PII in two cohort scripts).
Retired `work/queue.snapshot.jsonl` to `RETIRED-2026-09-17-*` in all nine
worktrees - renamed, not deleted, so its fifteen readers fail loudly. Fixed
the queue manifest. Preserved a diverged local worker branch to
`qwen-worker-r9-local-2026-09-17`. Checkpointed an uncommitted worker result;
moved a PII-bearing result file out of a tracked path.

Four hygiene assertions were failing on one design document, which named a
real person, a personal address, a LinkedIn vanity and five client domains.
Redacted. Then `test_fixture_hygiene` gained the client's SENDING roster -
every name it knew was a prospect or one of ours, none was a person who sends,
so three tracked files named all ten inbox owners and all thirteen assertions
passed. Added, it immediately caught a fourth.

New tools, all read-only: `email_sender_estate.py` (who owns which inbox,
which ACTIVE campaigns hold it, what moved), `bison_mailbox_utilisation.py`
(differences a lifetime counter into a send rate),
`verification_inventory.py` (SENDABLE / HELD / NEVER_OFFERED / NO_ADDRESS,
live, with what a run would cost and never running one).

---

## 5. DO NOT REDO

The seven ruled-out send explanations. The sender capacity audits. The
deterministic-first audit. The seal re-pointing. D1/D2. And now also:

- **The account holds are correct.** All 32 contacts held by "a campaign at
  this account ended early" carry real prior sends (2 to 31 emails). None is
  our own stopped staging. `collision.without_our_staging` is working.
- **Generating the 9 missing-copy LinkedIn steps unblocks nobody.** All nine
  are account-blocked as well.
- **Verifying the 159 is not the bottleneck** and is gated on a vendor
  decision regardless.

---

## ADDENDUM, 2026-09-17T15:02:48Z — 487 IS QUEUED

Section 1's prediction was **wrong and is withdrawn**. It said 487 would emit
`TOUCHED` then `QUEUED` between 07:00Z and 07:30Z on 2026-09-18, when the
Zagreb window opened on an already-active campaign. Both fired at **15:02:48Z
on 2026-09-17, two minutes after that window CLOSED.** The provider assigns on
a cycle and the cycle ran at the close of the sending day, not its opening.
One observation is not a schedule.

    QUEUED 487 scheduled rows 0 -> 10 (none sent)
    TOUCHED 487 updated_at 2026-09-17T10:45:10Z -> 15:02:48Z

Ten rows, one per lead, opener step, `thread_reply: false`, sender 2736,
status `scheduled`, **all dated 2026-09-23** between 07:12Z and 14:00Z - which
is 09:12 to 16:00 Zagreb, every one inside the campaign's own window.

**The copy renders.** Across all ten: zero unresolved placeholders, zero empty
subjects or bodies, zero greetings with no name. First name, company and
industry all resolved. Ingest to rendered provider copy is proven end to end
for this cohort; only the send has not happened.

The ledger's 13 keys stay `unresolved`. **Scheduled is not sent**, and the
rule that a key becomes `sent` only when the provider says that person was
sent to is unchanged.

**The instruction in section 3 stands and is now stronger: do not touch 487.**
Not a pause, a re-approval, a sender change or a re-activation. The queue is
the first real artefact this campaign has produced. See
`docs/487-IS-QUEUED-AND-THE-HYPOTHESIS-IS-WRONG-2026-09-17.md`, and watch
`SCHEDULE-MOVED` - canary 451's row moved once overnight before firing.

---

## ADDENDUM 2, 2026-09-17T18:10Z — CAPACITY, AND THREE MORE OPERATOR ITEMS

`docs/REAL-AVAILABLE-CAPACITY-2026-09-17.md` is the P3 answer, measured over
6h44m of a live sending day and grouped by attested HUMAN, which is the only
unit capacity can be planned in here:

    estate       3,150/day connected, 540 used, 2,610 headroom, 137 IDLE
                 mailboxes, and NOT ONE inbox reached its limit
    487's human  6 inboxes, 90/day, 51 used, ZERO idle - its sender 2736 is
                 the second busiest inbox that person owns
    three humans 17 connected inboxes each: 51 mailboxes, 765 emails a day,
                 entirely untouched

That is why 487 is scheduled for 2026-09-23 and it is the price of having no
per-lead attribution: the capacity exists and belongs to people this system
cannot name.

**The roster was eight days stale and has been rebuilt** (email only). Fifteen
inboxes had gone `Connected -> Not connected` while canonical state called
them `active: true, health: "ok"`. Harmless only because nothing has an owner;
it would have bitten on the first day attestation worked. Ready capacity after
the rebuild is **2,790/day**, not 3,150 and not 3,375. LinkedIn is four days
stale with 14 drifted accounts and one seat storing `daily_limit: 40` against
a provider-reported ZERO - **not rebuilt**, because `build_linkedin` drops any
seat missing from the operator's allowlist. See
`docs/THE-ROSTER-IS-A-SNAPSHOT-NOBODY-REFRESHES-2026-09-17.md`.

### Operator items now standing, in order of what they unlock

    1  APPROVE some of the 17 near-miss contacts. Still the only thing that
       converts anybody this week.
    2  OPEN the Deliverable leg or name another secondary verification vendor.
    3  RECONNECT 15 email inboxes reading `Not connected` - each has 328-371
       lifetime sends, so each used to work.
    4  Look at 24 inboxes DEGRADED on a lifetime bounce rate at or above 2%.
    5  Supply the LinkedIn seat allowlist so that roster can be refreshed too.

### Two dated experiments that must not be reset

    2026-09-18  605732's first connection request. Falsifier: if the 19th
                opens with all three leads still `None` and `lastActionTime`
                unmoved since the 17th, the graph explanation is wrong.
    2026-09-23  487's ten scheduled sends. DO NOT pause, re-approve, change
                the sender on, or re-activate 487 before then. The 23rd is
                itself a measurement of whether a scheduled date here holds.

---

## ADDENDUM 3, 2026-09-17T19:00Z — THE WORKER LANES, AND WHAT THEY CHANGED

Four lanes ran in parallel. Every result is committed; nothing below is
availability.

### GLM — three targets that had never produced a report

`glm_review.py` listed `storage`, `collision` and `ledger` since it was
written and had never run any of them. The cause was `glm.GLM_TIMEOUT = 60`,
clamped over every caller, against a model whose ordinary calls take 20-95s.
Raised to 180 on that measurement (`docs/GLM-REVIEW-*-2026-09-17.md`).

    LEDGER     two record-fidelity defects, both confirmed, both FIXED
               (6a1858f3, 8 tests, 2 red on deliberate break). A FAILED
               settlement inherited the prior UNRESOLVED row's
               `provider_response`, so a deferral's 421 was recorded as
               though the failure produced it - on every key transiting
               UNRESOLVED -> FAILED, and thirteen keys sit at `unresolved`
               now. And a same-state replay returned success while silently
               discarding a corrected message id.
    STORAGE    arithmetic ACCEPTED - full-file rewrite per 5-record
               checkpoint, O(N^2), 63.6 TB per pass at 100k records, and
               every size-derived benchmark here understated 7.57x.
               Recommendation REJECTED: raising the interval trades against
               the lesson that put checkpoint-per-record there. The shape is
               the defect; incremental persistence is the fix.
    COLLISION  FALSE POSITIVE, verified not argued. The claimed defeat needs
               an `in_sequence` row to be excludable and `_excludable`
               refuses anything outside {'sending_paused','stopped'}.
    WEBHOOK    dispatched against `bisonevents` BEFORE it has a caller.

### GROK — six questions, and the documentation answered three of them

`docs/PROVIDER-TRUTH-FROM-DOCUMENTATION-2026-09-17.md` and
`GROK-PROVIDER-RESEARCH{,-B}-2026-09-17.md`. Same defect as GLM first:
`XAI_TIMEOUT = 60` clamped a `timeout=180` and killed the call - which is why
`GROK-VS-FREE-RESEARCH-2026-09-16.md` records that the adapter "was not used".
Raised to 300.

    DOCUMENTED  per-lead sender stickiness on EmailBison - "the same Sender
                Email will send the remaining steps for that lead" - which
                AGREES with our own measurement of 243 leads and 0 rotations
                taken before the page was found.
    DOCUMENTED  the FIRST send's picker is NOT documented. No selection field
                in the OpenAPI spec. So the human is observable, never chosen.
    DOCUMENTED  recipient-local sending does NOT exist. No flag, no setting,
                no lead timezone field. A marketing page claims it; the
                researcher flagged the claim rather than passing it on.
    DOCUMENTED  the scheduler runs "at the end of each sending day", which is
                why 487 queued at 15:02:48Z and why MY window-opening
                hypothesis was wrong by sixteen hours.
    DOCUMENTED  webhooks for every event the reply watcher polls, 5 retries
                over 24h, `/api/events` replaying 10 days.
    DOCUMENTED  HeyReach defaults an omitted schedule to Mon-Fri 09:00-17:00
                UTC - so 605732's 09:04:00Z first action is the window
                opening, to the minute.
    BY-INTEGRATOR  `accountLeadPairs` binds a lead to a `linkedInAccountId`,
                max 100 pairs - documented by Scalekit, Cotera and the n8n
                node, NOT by HeyReach. So LinkedIn's per-lead sender is
                CHOSEN and email's is OBSERVED. **Two channels, two allocator
                contracts.**
    NEW SOURCE  a full OpenAPI spec at dedi.emailbison.com/api/
                reference.openapi, plus llms.txt. Nothing here had read either.

### QWEN — three tasks, each in its own worktree, all integrated

    geo-iso-resolution            timezone resolution 21 -> 33 of 67, US
                                  refusal intact, MEDIUM tier verified
                                  CONSUMED by `schedulable()` rather than
                                  merely computed. Two defects corrected in
                                  the worker's own measurement script.
    staged-paused-activation      8 tests pinning that whichever of two
                                  staged campaigns activates SECOND is
                                  refused. Zero lines changed under src/.
    bison-webhook-ingest          a pure normaliser + idempotency key. No
                                  server, no network import. Tenancy fails
                                  closed on an UNSET pin. Two corrections on
                                  review, including the residual risk that
                                  its fallback key rests on `occurred_at`
                                  meaning occurrence and not delivery.

### The GTM comparison

`docs/GTM-REPO-REVIEW-2026-09-17.md`, under one rule: a README is a claim, not
an implementation. It earned the rule - OpenGTM's "~90 sourcing sources" are
92 DuckDuckGo query templates, and its cross-row cache and confidence
early-exit are not called on the workbook hot path.

Four ADAPT: evidence TTL by FIELD; a cost/yield ledger as evidence for
changing the routing policy rather than as an automatic reorder; a spend
ceiling in MONEY not calls; connector cursors. DEFER the MCP/CLI surface.
REJECT the workbook DAG. **Nothing we already do better gets traded** -
reservation-before-call and account collision gating were NOT FOUND in any of
the five.

### THE SENDER-CAPACITY CHAIN, now fully mapped — three links, not one

`scripts/sender_pool_census.py` and `scripts/propose_sender_attestation.py`:

    1  TWELVE humans own the 225 inboxes and canonical state has never heard
       of ONE of them. Each must be CREATED before an inbox can be attested.
       A near-duplicate pair one edit apart holds 66 inboxes and 5.
    2  Zero attestations, so `eligible_senders` returns [] and
       SAFE_FOR_PRODUCTIVE = 0.
    3  `executionguard._sender_for` refuses any row naming more than one
       sender, so even with 1 and 2 solved a campaign holds one.

All three are operator-facing or gate-facing. Documented stickiness is what
makes the eventual pool safe: several inboxes of ONE attested human cannot
produce a prospect who hears from two people.
