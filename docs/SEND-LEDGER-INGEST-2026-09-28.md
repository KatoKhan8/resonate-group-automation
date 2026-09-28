# THE SEND LEDGER WAS NEVER MISSING CODE — 2026-09-28

Operator decision 13, P0. Branch `task-send-ledger-ingest`.
**Not merged. Provider writes 0.**

Every state claim below carries CLAIM / AUTHORITY / MEASURED AT / STATE.
`UNKNOWN` is never written as PASS, zero, absent, idle, complete, safe or
ready.

---

## 0. THE ONE SENTENCE

`leadobserve.confirm_email_touches` — the function that reads EmailBison's own
sends and writes them into this system's event log — **was already correct and
had zero production callers.** It was reachable only from
`python -m src.leadobserve`. Nothing ever ran it, so the ledger stayed empty
while the provider sent 912 emails.

This is the repository's named recurring defect (*"a thing computed correctly
that nothing downstream reads"*) sitting on the most safety-relevant fact the
provider publishes.

---

## 1. WHAT WAS MEASURED, BEFORE ANYTHING CHANGED

    CLAIM        EmailBison reports 912 rows with status `sent` across the 20
                 campaigns this system claims.
    AUTHORITY    `bison.scheduled_emails` through `_paged`, which REFUSES a
                 partial read rather than returning a prefix. All 20 campaigns
                 read whole; none UNKNOWN.
    MEASURED AT  2026-09-28, read directly from send.resonategroup.co.
    STATE        VERIFIED

    CLAIM        The record event log carried ONE confirmed touch, total,
                 across 1,582 productive records.
    AUTHORITY    `store.load()` filtered by `touch.CONFIRMING_EVENTS`.
    MEASURED AT  2026-09-28, on a byte copy of the production store.
    STATE        VERIFIED

    CLAIM        The daily digest for `productive` said
                 "Confirmed sends: none recorded" while carrying
                 "Replies: 1 from 1 people".
    AUTHORITY    `digest.lines(digest.build("productive"))`.
    MEASURED AT  2026-09-28.
    STATE        VERIFIED

    CLAIM        `slackagenttools._ledger_carries_sends("productive")` == False
    AUTHORITY    the function itself, against the live provider.
    MEASURED AT  2026-09-28.
    STATE        VERIFIED

### Provider send truth, per campaign

Fully paginated at `CAMPAIGN_QUEUE_PAGE_CAP`. `sent` is the provider's own
word on a `scheduled-emails` row.

| campaign | queue rows | `sent` |
|---|---|---|
| 451 | 1 | 1 |
| 481 | 10 | 0 |
| 484 / 485 / 500 | 0 | 0 |
| 487 | 20 | **5** |
| 489 | 15 | 10 |
| 491 | 665 | **410** |
| 492 | 409 | 244 |
| 493 | 64 | 22 |
| 494 | 152 | 95 |
| 495 | 114 | 41 |
| 496 | 17 | 3 |
| 497 | 13 | 7 |
| 498 | 26 | 10 |
| 501 | 1 | 1 |
| 503 | 500 | 23 |
| 504 | 446 | 14 |
| 505 | 434 | 25 |
| 506 | 1 | 1 |
| **total** | **2,888** | **912** |

**`docs/state/PROVIDER-CAMPAIGNS.json` AND `CLAUDE.md` ARE BOTH WRONG ABOUT
487.** Both say *"487 (10 leads, 0 sent)"*. The provider says 5 sent, the
first at **2026-09-28T10:37:59Z — today**. The cached file is from
2026-09-26T18:29:43Z and 487 has been sending since. Derive it; do not read
it.

---

## 2. THREE DEFECTS, AND ALL THREE HAD TO CLOSE

### 2a. NO CONSUMER — the whole reason the ledger was empty

    grep for callers of `confirm_email_touches`:
      src/leadobserve.py:699   its own CLI
      (nothing else in src/, nothing in scripts/, no test at all)

Per ARCHITECTURAL INVARIANT 0, *"zero production callers = DISCONNECTED."*
The LinkedIn half (`confirm_touches`) has a test file of its own. The email
half had none.

**Closed by `replywatch._reconcile_sends`**, called from `poll_once` — same
provider, same credential check, same lock, same status row as the reply poll,
which already runs on a timer. It cannot raise: a missed reply is somebody
being written to after they answered, and that outranks the ledger. It
reports `sends_complete` as **True / False / None** — every queue read whole,
some campaign UNKNOWN, or the reconciliation could not run — because
collapsing those three is how an unread estate reports as a silent one.

### 2b. THE LARGEST SENDING CAMPAIGN WAS UNREADABLE

`scheduled_rows` was the **fourth** reader of the campaign queue and took the
40-page default while `slackagentreadback`, `scripts/hard_stop_check.py` and
`bison_watch_loop` all walk `bison.CAMPAIGN_QUEUE_PAGE_CAP`.

`tests/test_the_queue_cap_is_one_number.py` exists precisely to stop that
drift — *"two readers that disagree about how much of a campaign they can see
will disagree about what was sent"* — and it could not see this reader,
**because nothing called it.** The anti-drift test and the disconnected
consumer hid each other.

    campaign 491   665 queue rows = 45 pages   default cap 40   -> REFUSED
                   410 provider-confirmed sends, unreadable by the one
                   function whose job is to record them

The refusal was correct and is not what was fixed. What was fixed is a
reconciliation that reported on the estate while a campaign's sends were
unread. The cap is not the property; **the refusal is** — past the cap it
still raises, and the caller now reports itself BLIND.

### 2c. INGESTION ALONE DID NOT REACH `already_sent`

The subtle one, and it would have made a green ingestion prove nothing.

    CLAIM        Of every event on all 1,582 production records, exactly ONE
                 carries `scheduled_email_id`.
    AUTHORITY    a walk of `rec["events"]` on the production store copy.
    MEASURED AT  2026-09-28.
    STATE        VERIFIED

`_step_of` resolved the cadence step by matching that identifier, so it
answered `None` for effectively every real send — and
`generate.sent_so_far` **drops "a touch that names no step" by name.** So the
touch would be recorded, the digest would move, and `already_sent` would
still read empty for every recipient. Criterion 1 would have failed on a
system that looked ingested.

**Closed by `email_step_ordinals`**: the provider states its own sequence and
its own `order`; the record states its declared cadence; rung *N* is the
*N*th declared email step. This is provider truth joined by rung — never
matched on rendered subject text, which `_step_of` has always refused.

It fails closed, and each refusal is a case that would otherwise put
*"as I mentioned"* in front of somebody over words they never received:

| situation | answer |
|---|---|
| a step with no readable `order` | the **whole sequence** is refused |
| two steps sharing one `order` | the **whole sequence** is refused |
| a variant | the rung it varies **from** — a variant is the same rung in different words |
| a variant of nothing | no rung |
| a rung past the record's declaration | **None**, never clamped to the last step |
| an exact `scheduled_email_id` event exists | that wins; a rung never overrules an identifier |

The clamp case is the expensive one: a campaign with five sent rungs against a
record declaring three would attribute emails four and five to `em3` — three
confirmed touches reported as one. Every unresolved rung is **counted** and
returned as `stepless`, so the residual is a number rather than a silence.

Measured on this estate: 487, 489, 491, 493, 494, 495, 497 and 498 each hold
exactly three non-variant steps ordered 1, 2, 3, and 1,272 of the stored
records declare exactly `em1, em2, em3`. The join is unambiguous here and the
refusals above are what keep it honest when it stops being.

---

## 3. PROVIDER WRITES = 0, AND HOW THAT IS KNOWN

The interceptor sits on **`src.providers._transport`** — not on `bison`. That
is the single chokepoint: `providers.request()` calls `_transport` by module
global, so every module that did `from . import request` is covered, including
`bison._post` / `_patch` / `_put` / `_delete`.

**IT WAS FIRED DELIBERATELY AS THE FIRST ACTION OF EVERY RUN**, because an
interceptor that never triggered looks identical to a clean pass:

    INTERCEPTOR SELFTEST: fired -> INTERCEPTOR: refused
      POST https://send.resonategroup.co/api/leads - this run is read-only

Every run then reports its verb histogram. Across the five live runs against
the real host the total was **1 write attempt — the self-test — and 0 reaching
the network**; everything else was GET.

There are two further independent guards underneath, neither relied on here:
`bison._allow` refuses any path not in `WRITE_ROUTES`, and
`providers.refuse_unauthorized_write` runs as the first line of the transport
and refuses a mutating prospect-facing call with no `allow_writes` scope.

---

## 4. THE MUTATIONS — 9 APPLIED, 9 KILLED

Applied to the **real source**, not to a copy; the intended test red for the
intended reason; source restored and **verified byte-identical by SHA-256**.

| # | guard broken | intended test | verdict |
|---|---|---|---|
| M1 | the cap goes back to the 40-page default | `test_scheduled_rows_walks_the_campaign_queue_cap` | KILLED |
| M2 | a rung past the declaration is clamped | `test_a_rung_past_the_declaration_is_not_clamped_to_the_last_step` | KILLED |
| M3 | the production caller removed from the loop | `test_the_reply_watcher_records_the_send` | KILLED |
| M4 | an unrecognised provider status folded into `sent` | `test_a_sending_paused_row_writes_nothing` | KILLED |
| M5 | a blind campaign reported as complete | `test_the_blind_campaign_is_named_and_the_run_is_incomplete` | KILLED |
| M6 | the rung overrules an exact event | `test_an_exact_prior_event_still_wins_over_the_rung` | KILLED |
| M7 | the tenancy check on `client` removed | `test_another_tenants_lead_is_refused_on_the_client_field` | KILLED |
| M8 | a bounce recorded as a confirmed touch | `test_a_bounced_row_records_the_bounce_and_not_a_touch` | KILLED |
| M9 | a dry run writes to the ledger | `test_dry_is_the_default_and_writes_nothing` | KILLED |

**Two mutations were rejected as INEFFECTIVE before M4 reached the
behaviour**, and that is recorded rather than tidied away. Widening
`EVENT_FOR` alone SURVIVED, and so did widening `EMAIL_STATES` alone:
`_email_state` normalises an unrecognised status to `email_state_unknown`
**before** `EVENT_FOR` is consulted, so a row must get past **two independent
allowlists** to be read as a send. That doubling is a real property, measured
rather than assumed — and a mutation that cannot change behaviour proves
nothing about the test, which is the same trap one level up from the one the
mutation run exists for.

**A third failure mode was caught by the harness printing it.** The first run
reported three mutations `NOT_APPLIED`: the sources are CRLF on disk and every
anchor was written with `\n`, so each multi-line anchor silently did not
match. Had the script not distinguished NOT_APPLIED from SURVIVED, three
guards would have looked unbreakable. The harness asserts the file actually
changed before running the suite, for exactly that reason.

---

## 5. WHAT IS *NOT* DONE — named, not left to be discovered

### 5a. The duplication law still does not see these sends

`push.already_pushed` reads `rec["cadence"][contact][step]["status"]` through
`stepstate.is_terminal`, and this change does not write it. So
`eligibility._already_pushed` would not refuse a second send to somebody
EmailBison has already emailed.

It is **deliberately** not closed here. `stepstate.TRANSITIONS` admits
`CONFIRMED` only from `PUSHED`, and `PUSHED` only from `PREPARED`, so
recording a provider-confirmed send as terminal is either a two-hop write or a
change to the state machine — a decision about the state machine, not an
ingestion. `push.already_pushed`'s own docstring anticipates this exact
moment: *"`confirmed` is what a provider callback would naturally write, so
the first thing to produce one would have found this."* This is that thing.
**It is the next task and it is a safety improvement, not a regression:**
nothing is loosened, because the flag was already False.

### 5b. There are TWO send ledgers and this change writes one

    work/queue.jsonl  rec["events"]         written here. Read by
                                            `already_sent`, the digest,
                                            `account.touches`,
                                            `_ledger_carries_sends`
    work/action-ledger.jsonl                NOT written here. Read by
                                            `collision._ledger_is_silent`,
                                            the pilot caps, and
                                            `contacts_reached`

    CLAIM        `work/action-ledger.jsonl` holds 136 rows over 18 keys and
                 not one is `state: "sent"` — only attempted (64),
                 abandoned (41), unresolved (26) and failed (5).
    AUTHORITY    the file itself.
    MEASURED AT  2026-09-28.
    STATE        VERIFIED

It is not written here on purpose. `actionledger.settle` refuses a key that
was never `reserve`d, and `reserve` means *"claim the right to attempt"* — a
reservation invented today for a send that happened last week is a fabricated
audit trail, and it would also make `reserve` refuse the key for ever. That
ledger records **what this system did**; the event log records **what the
provider did**. Reconciling them is `leadobserve.reconcile`'s job and it needs
an operator decision about what a hand-staged send should look like in a
reservation ledger.

### 5c. Sends this system cannot place, and they are not zero

    CLAIM        66 provider-confirmed actions on campaigns 503, 504 and 505
                 match no record by `record_id`, address or `contact_key`.
    AUTHORITY    `leadobserve.match_scheduled` over a live provider read.
    MEASURED AT  2026-09-28.
    STATE        VERIFIED as unmatched — the sends are real and the recipients
                 are UNKNOWN to this system. Never reported as zero.

503/504/505 are the campaigns of the 09-25 incident that sent a different
agency's pitch. Their leads carry no round-tripping custom variables, so the
join has nothing to work with. This is a reconciliation question for a person;
nothing here guesses at a near miss.

### 5d. `_ledger_carries_sends` compares two differently-scoped numbers

Pre-existing, found while tracing the consumer chain, **not fixed here**: the
ledger side counts every confirming event on every record in the workspace,
while the provider side sums `emails_sent` over a **capped** campaign list
(`_campaigns_to_read(entry, SENDS_TODAY_CAP)`, with the `_hidden` remainder
discarded). A workspace with more campaigns than the cap under-counts the
provider and biases the verdict toward True. It is also wrapped in a bare
`except Exception: verdict = None`, which swallows a genuine
`PartialInventory`. Both belong in `docs/state/PROBLEM-REGISTER.md`.

---

## 6. LADDER

    the reconciler and its step resolver      INTEGRATION_TESTED
    the production wiring in `replywatch`     INTEGRATION_TESTED — proved
                                              through `poll_once`, with the
                                              mutation that removes the call
                                              turning the chain red
    the estate ingestion                      LIVE_VALIDATED — section 7
    PRODUCTION_ACTIVE                         NOT CLAIMED. The branch is not
                                              merged, and ~15 long-lived loops
                                              import at start and never
                                              reload: a merge is not a deploy.

---

## 7. THE THREE ACCEPTANCE CRITERIA

Exercised against a **byte copy of the production store** (SHA-256 verified
equal to `work/queue.jsonl` at 2026-09-28T10:38:18Z) and the **live
EmailBison instance**. Not against a fixture estate.

Run 1 (all 20 claimed campaigns) and run 2 (491 alone) both installed the
interceptor and fired it first. Backups taken and hash-verified before each.
The readback below was done by a **separate process**.

    before   1 confirmed touch     after   850 confirmed touches
                                           694 distinct contacts
                                           621 distinct accounts
                                           848 placed on a cadence rung
                                             2 stepless, counted and named

### Criterion 1 — `already_sent` proves TRUE on known really-sent contacts

**MET.** Six specific recipients, not a count — each identified by the
**provider's own identifiers**, which are exact, resolvable and not a person's
name. `already_sent` is the block `generate` hands the draft prompt, asked
exactly as `generate` asks it (`sequence_for` → `history_block`).

**NAMES AND RECORD KEYS ARE DELIBERATELY NOT PUBLISHED HERE.** `work/` is
gitignored because it is real companies and real contacts, and a contact key
is a person's name as a slug — `tests/test_fixture_hygiene.py` refuses one in
a tracked file, correctly. The provider lead id resolves each row exactly, for
anybody who can already see the estate.

| provider lead | campaign | `scheduled_email_id` | provider `sent_at` | rung | `already_sent` |
|---|---|---|---|---|---|
| 203715 | 487 | 22372853 | 2026-09-28T08:52:21Z | em1 | **TRUE** — 1 entry `[em1]` |
| 203711 | 487 | 22372847 | 2026-09-28T07:23:05Z | em1 | **TRUE** — 1 entry `[em1]` |
| 203708 | 487 | 22372841 | 2026-09-28T10:37:59Z | em1 | **TRUE** — 1 entry `[em1]` |
| 203710 | 487 | 22372845 | 2026-09-28T10:47:24Z | em1 | **TRUE** — 1 entry `[em1]` |
| 203707 | 489 | 22357233 | 2026-09-24T13:40:38Z | em2 | **TRUE** — 2 entries `[em1, em2]` |
| 203712 | 489 | 22357235 | 2026-09-24T15:24:50Z | em2 | **TRUE** — 2 entries `[em1, em2]` |

To resolve these to records and contacts locally, off the untracked store:

    py -3 -c "from src import store,touch; [print(r['id'], e.get('contact'), e.get('lead_id'), e.get('step'), e.get('at')) for r in store.load() for e in (r.get('events') or []) if e.get('type') in touch.CONFIRMING_EVENTS]"

Every entry carries the provider's RFC message id and the provider's own
timestamp. Each is dated **when the provider sent it**, not when the
reconciliation ran — lead 203707's em1 reads `2026-09-21T20:37:54Z`, which is
the day 489 first sent, seven days before this reconciliation ran.

**The two-rung rows are the ones that matter most.** Leads 203707 and 203712
each received em1 *and* em2, and `already_sent` returns both, in order, on the
right days (1 and 4). A resolver that clamped or guessed would have reported
one message where two went out.

**The words are withheld and that is correct**, not a shortfall.
`sent_so_far` returns `copy_withheld: "the stored step is not provably the one
that was sent"` because these sends were never pushed through our own path, so
no `push_id` ties the stored copy to what left. The fact, the day, the channel
and the rung license the follow-up; the text does not, and showing text that
was not sent is the larger error.

**Negative control:** `already_sent` stays `[]` on a `scheduled` row, a
`sending_paused` row, a `bounced` row, and on a confirmed touch whose rung
could not be resolved — each asserted in
`tests/test_a_provider_confirmed_send_reaches_the_ledger.py`.

### Criterion 2 — reconciled against the PROVIDER, not against our own copy

**MET.** Nothing in this reconciliation reads our own store for the answer to
"was this sent". `docs/state/PROVIDER-CAMPAIGNS.json` was **not** used; it was
read once only to demonstrate that it is stale on 487.

    authority   `bison.scheduled_emails(campaign, cap=CAMPAIGN_QUEUE_PAGE_CAP)`
                — the provider's own queue, its own `status` word, its own
                `sent_at`, its own `raw_message_id`
    pagination  `_paged` walks every page and RAISES on a short read or a
                cap overrun. 20 of 20 campaigns read whole; 2,888 rows.
    join        `lead.custom_variables` — `record_id` / `contact_key` /
                `client`, which this system itself staged and the provider
                hands back. Never an address heuristic, never subject text.
    tenancy     a `client` variable disagreeing with the record REFUSES the
                row rather than attaching it.

Per the canonical authority registry (§0a), the authority for *"was this email
sent"* is **the provider's own event or readback**, and the named
non-authorities are *our store* and *`PROVIDER-CAMPAIGNS.json`*. This used the
authority.

### Criterion 3 — the digest STOPS saying "no confirmed sends"

**MET**, measured through the real `digest.lines` and the real
`slackagenttools` rollup, before and after, on the same estate.

| | BEFORE | AFTER |
|---|---|---|
| `digest.lines(...)` | `Confirmed sends: none recorded` | `Confirmed sends: 5 to 5 people` |
| `_ledger_carries_sends("productive")` | `False` | `True` |
| weekly report `accounts.unanswerable` | **1,504** | **0** |
| weekly report `accounts_warning` | *"1504 account(s) could not be placed…"* | **not emitted** |
| account states | `sequenced 1 · dnc 65 · replied 12` | `sequenced 544 · untouched 961 · dnc 65 · replied 12` |

Replies were present throughout (`Replies: 1 from 1 people`), which is the
contradiction the criterion names.

**"5 to 5 people" is the digest's 24-hour window, not the total** — those five
are campaign 487's sends of this morning. The cumulative figure is the 850
above. A digest that reported all 850 as today's activity would be a different
and worse defect.

**The 1,504 is now explained rather than restated.** It was never a count of
uncontacted companies: it was `_account_state` refusing to call an account
untouched while the ledger could not answer. 1,504 = 544 + 961 − 1. The
estate did not change; the blind spot closed.

### Provider writes

    run 1 (20 campaigns)    GET 332   write attempts 1 (the self-test)
    run 2 (491)             GET 153   write attempts 1 (the self-test)
    baseline probe          GET 315   write attempts 1 (the self-test)
    readbacks               GET 107   write attempts 1 (the self-test)

**Writes reaching the network: 0.** Every non-GET verb counted was the
deliberate self-test, refused before the socket. Per §0a the authority here is
*the write-interceptor ledger with the interceptor proven to fire* — not a
zero request count from an interceptor that never triggered.

### What run 1 got WRONG, and why it is the best evidence in this document

Run 1 returned **`complete: false`** with campaign **491 BLIND** —
`PermissionError [WinError 5]` on the atomic `os.replace`, caused by my own
concurrent reader processes holding the file open on Windows.

491 had already had **346** of its rows written when the error landed. The
run did **not** report those 346 and did **not** report the campaign as read:
it reported the whole campaign UNKNOWN and the whole run incomplete. Re-run
alone with no concurrent readers, 491 completed — `recorded 135`,
`already 346`, `waiting 182`, `unmatched 2`, totalling the provider's own 665
rows exactly, `complete: true`.

**An unreadable campaign refused to become a zero, under a failure nobody
designed for, on the campaign with the most sends in the estate.** That is
the property this work is for, demonstrated by accident rather than by
fixture.

### Where this leaves the estate

    CLAIM        The record event log carries 850 provider-confirmed touches
                 for `productive`, over 694 contacts at 621 accounts, from
                 EmailBison readbacks of 20 campaigns read whole.
    AUTHORITY    `work/queue.jsonl` read by a fresh process, every event
                 carrying `provider: emailbison` plus the provider's
                 `scheduled_email_id`, `raw_message_id` and `sent_at`.
    MEASURED AT  2026-09-28.
    STATE        VERIFIED — **on a byte copy of the production store, not on
                 production itself.** See section 8.

    CLAIM        66 provider-confirmed actions on 503/504/505 match no record.
    AUTHORITY    `leadobserve.match_scheduled`.
    MEASURED AT  2026-09-28.
    STATE        UNMATCHED. Real sends; recipients UNKNOWN to this system.
                 Never zero.

---

## 8. PRODUCTION WAS NOT WRITTEN, AND THAT IS A DECISION

    CLAIM        Production `work/` is untouched by this task.
    AUTHORITY    mtime and size.
    MEASURED AT  2026-09-28, after every run.
    STATE        VERIFIED

        work/queue.jsonl             24,033,849  2026-09-28T10:38:18Z
        work/campaigns.jsonl            114,171  2026-09-26T19:05:08Z
        work/action-ledger.jsonl         83,144  2026-09-18T05:35:58Z
        work/lead-observations.jsonl      1,350  2026-09-13T09:28:53Z

    (`work/replywatch.json` moves on its own: the production reply loop
    writes its status every five minutes. That is not this task.)

**Why the ingestion was proved on a copy and not applied to production:**

1. **A running loop would have posted to Slack.** `scripts/digest_loop.py`
   and `scripts/weekly_report_loop.py` have been running on 300-second
   intervals since 2026-09-24. Writing 850 confirmed touches into production
   `work/queue.jsonl` makes the next digest tick post *"Confirmed sends: …"*
   within five minutes. This task was instructed not to post to Slack, and
   what a client-adjacent feed says is decision 11's territory, not a side
   effect of a backfill.
2. **This branch is unreviewed.** Putting an unreviewed branch's output into
   canonical production state is the same error as merging it to master.
3. **A merge is not a deploy.** `scripts/reply_watch_loop.py` has been
   running since 2026-09-25 and imports at start. The wiring in `replywatch`
   does nothing until that process is restarted, whatever master says.

**To apply it, after review — two steps, in this order:**

    py -3 -m src.leadobserve --provider emailbison --all-claimed --confirm --live
    # then restart scripts/reply_watch_loop.py so the loop keeps it current

Back up `work/queue.jsonl` first, run it with **no other process reading the
queue** (that is what made 491 blind), and expect roughly **45 minutes**:
`store.transaction()` rewrites the whole 24 MB queue per event, which is right
for a poller seeing one or two new sends a tick and slow for a one-time
backfill of a thousand. Then confirm `complete: true` and **no** `blind`
entries — anything else means part of the estate is UNKNOWN.

---

## 9. FINDINGS FILED, NOT ESCALATED

Per decision 20 (the FOCUS RULE) these are recorded with evidence and are
**not** operator questions:

1. `docs/state/PROVIDER-CAMPAIGNS.json` and `CLAUDE.md` both say 487 has sent
   0. The provider says 5, first at 2026-09-28T10:37:59Z. The cache is from
   09-26. — *stale cached read, §0a column three.*
2. `push.already_pushed` / `eligibility._already_pushed` still do not see
   these sends; `stepstate.CONFIRMED` is reachable only from `PUSHED`.
   — *section 5a. Safety-positive when closed; nothing is loosened by leaving
   it.*
3. `work/action-ledger.jsonl` holds no `sent` row and
   `collision._ledger_is_silent` reads it. — *section 5b.*
4. `_ledger_carries_sends` sums provider `emails_sent` over a **capped**
   campaign list while counting ledger events over **all** records, and wraps
   the lot in a bare `except Exception`. — *section 5d.*
5. 66 provider-confirmed sends on 503/504/505 cannot be placed on any record.
   — *section 5c. Needs a person, not a guess.*
6. Per §0c, none of the above changes any eligibility verdict. This work
   records **historical provider action** only. An account that now reads
   `sequenced` was emailed; that says nothing about whether it was licensed.
