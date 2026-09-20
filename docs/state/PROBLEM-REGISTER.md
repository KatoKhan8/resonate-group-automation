# Problem register — canonical

One place for confirmed problems, so the same ones stop being rediscovered.
Started 2026-09-20 after a session found, independently and from scratch, two
defects that were already written down: the geo ISO fix (fixed on master three
days earlier) and the vacuous coverage default (in Buggie's audit that morning).

**Rules for this file.**

- A row is CONFIRMED only with a reproduction or a measurement. A finding that
  has not been reproduced is UNVERIFIED and says so.
- **Code written is not FIXED.** FIXED means merged with a regression test.
  PRODUCTION_VERIFIED means the behaviour was observed against the real
  providers, and nothing reaches it on the strength of a passing test.
- REFUTED rows stay. Deleting them is how a disproven hypothesis gets
  resurrected six days later.
- Every row names its evidence. "Somebody said" is not evidence.

Sources folded in: `work/BUGGIE-FINDINGS-2026-09-20.md` (13 specialists, 16
adversarial skeptics, 83 pre-existing suite failures excluded), this session's
own measurements, and the GLM review docs.

---

## OPEN — ordered by production impact

_9 open at creation; ISSUE-006 closed the same day. ISSUE-010 added 2026-09-20 from the sender-utilisation review._

### ISSUE-001 · Reply ingestion discards the reply it just acted on · CRITICAL

- **Component** `src/leadstop.py::_record` nested inside `src/inbound.py::ingest`
- **Impact** For one poll interval (300s) a reply does not exist in canonical
  state. `eligibility._replied` and `_paused` answer clean, so a step can be
  authorised to somebody who has just answered. This is the positive-reply
  protection path.
- **Root cause** `_record` opens its own `store.transaction()` between ingest's
  `base = store.digest()` (`inbound.py:260`) and
  `store.save(recs, expect_digest=base)` (`inbound.py:276`), so the save raises
  `QueueChanged` and the REPLY_RECEIVED event, its classification and the
  account pause are all discarded.
- **Reproduction** Buggie reproduced it. Re-verified open 2026-09-20: the
  nested `store.transaction()` is still at `leadstop.py:206` and ingest's
  digest/save pair is unchanged.
- **Dominant live trigger** a LinkedIn reply from a contact who is also a
  staged EmailBison lead. HeyReach's reply is invisible to EmailBison, so the
  lead reads `in_sequence`, a real stop write happens, and the outer save is
  refused.
- **Fix** record onto the in-memory `rec` and let ingest's single save persist
  it. Do not add a second transaction.
- **Acceptance** a reply ingested while a stop write occurs is present in
  canonical state after one `ingest`, and `eligibility._replied` answers true
  on the next call rather than 300s later.
- **Status** NEW · unassigned · **no test covers it today**

### ISSUE-002 · A DNC or unsubscribe cannot stop a running HeyReach sequence · HIGH

- **Component** `src/leadstop.py`, `src/providerwrites.py`
- **Impact** Cross-channel stop is one-directional. The email half is latent
  (HeyReach-bound 4, Bison-bound 16, overlap 0). **The DNC and unsubscribe
  half is live now.**
- **Root cause** `heyreach.stop_lead_in_campaign` is implemented, on
  `WRITE_ROUTES`, with refusal-on-unconfirmed-readback — and has **no caller
  anywhere**. There is no `LINKEDIN_STOP_LEAD` verb while `EMAIL_STOP_LEAD`
  exists. `heyreach_lead_id` is read by two modules and written by none, so no
  record carries the id the stop route needs.
- **Reproduction** Re-verified open 2026-09-20: `grep LINKEDIN_STOP_LEAD`
  returns nothing and `stop_lead_in_campaign` has no caller outside its own
  module.
- **Also** `leadstop.sweep` `continue`s past every LinkedIn-staged contact
  **without incrementing `report['checked']`** — a sweep that reports clean
  because it counted nobody. That is the reason nothing surfaced this.
- **Status** NEW · unassigned · candidate for Qwen, bounded and testable

### ISSUE-003 · Nothing settles the action ledger, and it is growing · MEDIUM

- **Component** `scripts/reconcile_ledger.py`
- **Impact** No confirmed touch exists for any of the fifteen people in 487
  and 489. Reporting and fatigue both read confirmed touches.
- **Root cause** `CHECKABLE = ("heyreach.add_lead",)` while the stuck keys are
  `bison.activate` / `heyreach.activate`, so it settles **zero**. Nothing
  schedules it, and the three live watch loops do not import `actionledger`.
- **Measured 2026-09-20** 136 ledger rows: 64 attempted, 41 abandoned,
  **26 unresolved**, 5 failed. The audit counted 18 unresolved that morning,
  so the pool is growing.
- **NOT a duplicate-send risk** — see REFUTED-001.
- **Status** NEW · unassigned

### ISSUE-004 · The Qwen backlog is starved and 10 results are stranded · HIGH (throughput)

- **Impact** Eight workers, zero claims, no dispatch since 2026-09-16 15:42.
- **Root cause** two compounding: `claim_task.py --status` reports **2 ready
  tasks for 8 workers** against a healthy threshold of 16; and **89 stale
  branches** hide finished work from the dispatcher.
- **Stranded, finished, unintegrated** TASK-067, 212, 213, 214, 225, 229, 230,
  231, 232, 234. (TASK-227's ISO half is already on master as `27bcdb67`; its
  cohort-send-window half is not, and its branch conflicts on
  `scripts/task_geo_iso_coverage.py`, which master already carries.)
- **Status** NEW · integrating these is itself the fix for the stale-branch half

### ISSUE-005 · No notification is delivered anywhere · HIGH

- **Component** `src/notify.py`, `src/providers/slack.py`
- **Impact** **A positive reply on a live campaign would be written to a JSONL
  file and told to nobody.** 216 notifications produced, **207 `unconfigured`**.
  203 of those are `unmatched_reply_needs_review` at severity
  `action_required`, still arriving (last 2026-09-20T18:01Z).
- **Root cause** NOT an engineering defect. `SLACK_BOT_TOKEN`,
  `SLACK_SIGNING_SECRET`, `SLACK_OPS_CHANNEL` and `SLACK_LIVE` are all unset.
  The adapter and the routing table work correctly and refuse without a
  destination, exactly as SLACK-NOTIFICATIONS.md specifies.
- **Blocked on** operator. Channels already exist and must not be created:
  `#resonate-notifs` (C0AQB4KB9TM) for the global ops channel,
  `#productive-resonate-outbound` (C0ADUMGQX8S) and `#replies-productive`
  (C0BFUF4JRK9) for the per-workspace one.
- **Note a policy conflict before wiring** the standing contract routes
  `negative_reply`, `unsubscribe` and `neutral_reply` to NOWHERE deliberately.
  A recent instruction asks for NEGATIVE_REPLY and UNSUBSCRIBE alerts. That is
  an operator decision and a visible edit to the routing table, not a bug.
- **Status** BLOCKED on operator

### ISSUE-006 · The PII guard was red · HIGH · **FIXED `cecd4223`**

- Red since ~2026-09-18, reported green on the 16th, never triaged. **A red
  guard catches nothing**, so every leak after that date was invisible.
- What it was flagging: two seat-holders' real names and sending addresses
  across five tracked files, and **five real prospects hardcoded** in
  `scripts/build_us_cohort_row_and_approvals.py` - the cohort 489 enrolls.
- Fixed: identifiers redacted in place to placeholders keeping provider ids,
  and the prospect list moved to a gitignored sidecar the script reads,
  refusing when absent. **13/13 green.**
- Git history still holds the identifiers; rewriting a pushed history is the
  operator's decision, as recorded on the 09-17 redaction.

### ISSUE-010 · Zero senders are eligible, on either provider · HIGH

**Not a capacity problem. Answered, re-measured 2026-09-20T19:40Z.**

- **EmailBison** 225 inboxes, 210 connected, 207 healthy, **2,025 measured
  headroom slots**, 210 proven free on some day, 0 that could not be proven
  free. And `HUMAN_IDENTITY_ATTESTED = 0` across all 12 humans, so
  `SAFE_FOR_PRODUCTIVE = 0`. Every unallocated eligible sender classifies as
  **HUMAN_IDENTITY_MISMATCH** - no attested owner - not as
  `NO_COMPATIBLE_CAMPAIGN` or `DAILY_LIMIT`.
- **A second, independent cap:** `MAX_SENDERS_ONE_CAMPAIGN_MAY_NAME = 1`,
  enforced by `executionguard._sender_for` - "a guarded action is attributed
  to exactly one". The usable pool is the MINIMUM of the two, so it is zero
  twice over. This is DESIGN, not a defect: the replacement is already
  written as `docs/SENDER-ATTRIBUTION-DESIGN-2026-09-17.md`, status DESIGN
  ONLY, moving arity from the campaign to the action.
- **HeyReach** 41 accounts, 34 active, 33 with valid auth, and **0
  unallocated** - all 33 are already in campaigns, mostly the client's (we
  own 4 of 86). Classification: **EXISTING_COMMITMENT**. Connection limit is
  40/day per seat; 605732 has used **0** of its seat's 40.
- **So adding senders would change nothing on either channel today.** 487
  waits on an authorized resume, 489 on a stale plan, 605732 on 30 hours of
  graph delay and a weekend. None is a capacity constraint.
- **What must NOT be done:** attest a human to a mailbox to gain capacity.
  Attestation records who genuinely operates an inbox; inventing one
  fabricates the thing the gate checks. The three empty-book inboxes (3941,
  3930, 3919) are empty because they have NEVER SENT and are DEGRADED.
- **The bounded, honest unlock** is one genuine attestation of one human to
  one healthy uncommitted mailbox - an operator act, not an engineering one.
- **Status** BLOCKED on operator (attestation) · design exists for the arity
  half · `docs/THE-LATENCY-IS-ATTESTATION-NOT-CAPACITY-2026-09-19.md`

### ISSUE-007 · 489 is planned onto a full mailbox-day while Monday has room · MEDIUM

- `docs/489-COULD-GO-THREE-DAYS-EARLIER-2026-09-20.md`
- **Impact** three days of avoidable latency on a five-lead cohort.
- **Root cause** a stale plan, not a scheduler defect: placed when sender
  3437's Monday book read 16, which has since fallen to 3.
- **Blocked on** operator. The only mechanism is a pause/resume, named twice
  under "what is NOT authorized" in the standing grant.
- **Status** BLOCKED on operator decision

### ISSUE-008 · GLM's last review returned a truncated response · LOW

- Both targets came back `finish_reason='length'` with an empty completion.
  The adapter correctly refused rather than returning `""`. Auth is fine —
  `glm-5.3` verified live at 200 in 1840ms.
- **Fix** smaller review targets, or a raised output budget.
- **Status** NEW

### ISSUE-009 · Two model workers are invisible to credential health · LOW

- `ZAI_API_KEY` (GLM) and `XAI_API_KEY` (Grok) are absent from
  `config.VARIABLES`, so `scripts/credential_health.py` structurally cannot
  report on them. That is the honest failure by design, and it is still a gap.
- **Status** NEW

---

## FIXED THIS SESSION — regression-tested, pushed

| ID | Issue | Commit | Tests | Production |
| --- | --- | --- | --- | --- |
| F-001 | The write guard refused every HeyReach READ. The live 605732 watcher survived only because it predates the guard by 3h and holds the old module in memory; any restart would have killed the only LinkedIn monitor | `28f4766e` | 13 new, verified by disabling the exemption | **PRODUCTION_VERIFIED** — `provider_truth.py` completed live against all four HeyReach campaigns |
| F-002 | The forward-book census walked a hardcoded 3 campaigns while 6 can book a mailbox, so `senderheadroom` REFUSED every mailbox and capacity planning had no input at all | `d321c2ef` | 11 new, verified by breaking paging and by re-adding `paused` to the terminal set | **PRODUCTION_VERIFIED** — derived set matches the provider exactly; 487 and 489 headroom answerable again |
| F-003 | `active_campaign_ids` defaulted to `()`, making `coverage()` pass vacuously — the exact trap that produced a wrong ROOM reading for 489 earlier in this same session | `c9ddf35d` | 6 new, verified by restoring the old default | not yet — no production caller exists |
| F-004 | `senderheadroom` counted weekdays from 0 while the repo is ISO, so `sending_days=geo.windows()["days"]` read Mon-Fri as Tue-**Saturday** | `5ff914d1` | 3 new, one end-to-end through `geo.windows` | not yet — no production caller exists |
| F-005 | LIVE-READINESS.md and PRODUCT-GAPS.md asserted `SUPPORTED = ()`, "nothing sends" and "a pedal that is not connected to anything" while 14 verbs were enabled and a real email had been sent | `03d9da3f` | docs; corrections marked in place | n/a |

## FIXED EARLIER — verified still fixed today

| ID | Issue | Evidence |
| --- | --- | --- |
| F-006 | The stop button did not stop EmailBison 487: `staged_already` refused the pause before the transport, because a state-SETTING verb was being deduplicated by material fingerprint | `repeatable` is now declared in `providerwrites` (`98b05550`, TASK-234). Verified present 2026-09-20 |
| F-007 | `python -m src.scalesim` overwrote the live queue — 550 companies and 277 contacts, in a gitignored directory with no git recovery, three times per published benchmark run | `55ccb7b6` (TASK-233) |
| F-008 | `senderheadroom.walked_at` took the NEWEST stamp, so a walk resumed today read as fresh while carrying days-old rows | now takes `min()`, with the reasoning in the docstring. Verified 2026-09-20 |
| F-009 | The geo resolver matched country NAMES while the evidence is a two-letter CODE | `27bcdb67`, 2026-09-17 |

## REFUTED — kept so they are not resurrected

| ID | Claim | Why it is wrong |
| --- | --- | --- |
| REFUTED-001 | The 26 `unresolved` ledger keys permit a re-attempt and risk a duplicate send | Three independent refusals — `require_clear`, `reserve` under the lock, and `perform`'s ATTEMPTED-only check. Buggie attacked this and it held. The interrupted-write window on the facing path is correctly fail-closed. ISSUE-003 is about reporting, not safety |
| REFUTED-002 | The 215 ICP_REVIEW records are a backlog awaiting a human verdict | Zero of the 215 have any criterion at `fail`, none carries a contact, all are still `queued`, and 184 hold no company evidence at all. It is an enrichment task. Carried as an operator action in three consecutive handoffs |
| REFUTED-003 | Cohort expansion is blocked on an unauthenticated ContactOut | Four credential names were invented. Real names verified, ~36,700 credits remain. `docs/THE-CREDENTIAL-WAS-THERE-ALL-ALONG-2026-09-20.md` |
| REFUTED-004 | HeyReach 605732 has stalled — no connection request in two days | The graph spends 3h + 3h + 1 day before `CONNECTION_REQUEST`, and 09-19/09-20 were the weekend on a Mon-Fri campaign. `error_code` is null on all three leads and every one reads `InSequence`. The falsifier can only run on Monday |
| REFUTED-005 | 487 was paused by the provider, or by a decision about the campaign | An audit agent's throwaway probe paused it at 2026-09-20T12:44:45Z by passing a bare dict to `orchestrator.pause`. Nobody decided anything about 487, which is why resuming it overrides no judgement |

---

## The pattern under most of these

Six of the rows above are the same shape: **a value that was true when it was
written, cached somewhere that had no way to notice it had gone stale.**

    a hardcoded campaign list          F-002
    a hardcoded credential name        REFUTED-003
    a 0-based weekday constant         F-004
    a safety claim in a document       F-005
    a scheduler plan against an
      old forward book                 ISSUE-007
    a verdict computed before the
      resolver was fixed               REFUTED-002

The standing correction — **ask the thing that knows** — covers all six. The
registry names the credential, the provider names its campaigns, `geo` names
the weekday convention, and the queue can be re-qualified. Where a literal
stands in for one of those, it will drift, and nothing will report it.

The structural response is not more vigilance. It is that a cached value on a
safety path carries the date and the source it was derived from, and refuses
rather than answers when it cannot prove it is current. `senderheadroom`
already does exactly this and it is the model: complete, covering, fresh, or
REFUSED.
