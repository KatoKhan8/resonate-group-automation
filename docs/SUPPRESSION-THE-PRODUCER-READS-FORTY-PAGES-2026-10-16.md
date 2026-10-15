# The producer reads 40 pages where the watcher reads 400

TASK-0130, lane `suppression`. Measured in `wt-suppression-2026-10-14` on
**master `02761a708`** (the lane branch `task-suppression-bounce-RULE-2026-10-15`
stands on it; nothing was merged and nothing was pushed to master).

**No provider call was made.** Every provider number below is read from an
artifact the system already wrote: `work/heartbeat/bison-<id>.json`, written by
`scripts/bison_watch_loop.py` at 2026-10-15T21:55-21:58Z, and
`work/forward-book-census.json`, the completed cursor walk of 2026-10-03.
Both live beside the MAIN checkout, not in this worktree.

---

## 0. THE ONE-LINE ANSWER

The blindness is ours. `src/leadobserve.scheduled_rows` passes no `cap`, so it
takes `bison.PAGE_CAP = 40` — 600 rows — while the watcher reads the same
endpoint at `bison.CAMPAIGN_QUEUE_PAGE_CAP = 400` every 180 seconds and has
done since 2026-09-23. **One campaign of twenty is over the line: 491, at 665
rows and 45 pages.** The fix is two call sites. On 491 it costs **five extra
HTTP requests and about one second**, measured.

**And the premise in the brief needs one correction.** The producer does not
read the *oldest* 600 rows of 491 and miss the newest 65. `bison._paged`
**raises `PartialInventory`** rather than returning a prefix, so the producer
sees **nothing at all** — zero rows, not 600. That refusal is the thing this
provider module is most careful about and it is working exactly as designed.
A bounce gate that cannot see the newest rows would be a bounce gate for
history; what we have instead is a bounce gate that, on the one campaign over
the line, **does not run**. The second is louder and better than the first, and
it is still broken.

---

## 1. EVERY CALLER, AND WHAT CAP EACH GETS

The defect named in the brief is real and it is worse than two numbers. There
are **five** distinct caps in production code for one endpoint.

### `src/` — the modules

| # | Call site | Cap asked | Effective | On a refusal |
|---|---|---|---|---|
| 1 | `src/leadobserve.py:462` — `scheduled_rows`, the suppression producer | none | **40** | propagates `PartialInventory` ✅ |
| 2 | `src/collision.py:553` — `_queue_is_silent` | none | **40** | `False` + reason — fails closed ✅ |
| 3 | `src/bisonfactory.py:2291` — `_already_on_campaign` | none | **40** | `set()` — documented safe direction (adds checks) ✅ |
| 4 | `src/bisonfactory.py:2763` — the blank-render push gate | `CAMPAIGN_QUEUE_PAGE_CAP` | **400** | `FactoryRefused` ✅ |
| 5 | `src/slackagentreadback.py:243` — `queue`, the agent's reader | `QUEUE_PAGE_CAP` (= 400) | **400** | propagates ✅ |

### `scripts/` — the entry points

| # | Call site | Cap asked | Effective | On a refusal |
|---|---|---|---|---|
| 6 | `scripts/bison_watch_loop.py:155` — the watcher | `CAMPAIGN_QUEUE_PAGE_CAP` | **400** | queue `None`, rest of snapshot kept ✅ |
| 7 | `scripts/hard_stop_check.py:64` | `QUEUE_PAGE_CAP` (= 400) | **400** | reported BLIND, never skipped ✅ |
| 8 | `scripts/build_collision_index.py:77` | `CAMPAIGN_QUEUE_PAGE_CAP` | **400** | reported ✅ |
| 9 | `scripts/qa/check_readback.py:271` — rule 2 | `cap=200` default | **200** | `UNCONFIRMED` ✅ |
| 10 | `scripts/batch1_build.py:668` | `cap=80` | **80** | load UNKNOWN ✅ |
| 11 | `scripts/bounce_stop_7day.py:73` — the 2% bounce hard stop | none | **40** | **UNCAUGHT — aborts the run** ❌ |
| 12 | `scripts/batch_activate.py:158` | none | **40** | **`queue = []` — silent empty** ❌ |
| 13 | `scripts/batch1_build.py:761` | none | **40** | printed unreadable ✅ |
| 14 | `scripts/batch1_push.py:165` | none | **40** | printed, readback failed ✅ |
| 15 | `scripts/production_status.py:226` | none | **40** | `UNKNOWN` string ✅ |
| 16 | `scripts/queued_copy_readback.py:153` | none | **40** | propagates ✅ |
| 17 | `scripts/activate_us_cohort_campaign.py:364` | none | **40** | propagates ✅ |
| 18 | `scripts/nudge_487_scheduler.py:58` | none | **40** | propagates ✅ |

**The five numbers are 40, 80, 200, 400 and "whatever the caller passed".**
That is the defect, exactly as the brief frames it: the answer to *has this
address bounced* depends on which path asked. The reason the agent-side readers
already have 400 is that
`tests/test_the_largest_campaign_is_the_one_the_agent_cannot_read.py` fixed
them on 2026-09-23 after campaign 491 cost the live agent half a day's sends.
**That fix stopped at the agent. The suppression producer was never included,
and `scheduled_rows`' own docstring has said so in plain words ever since:**

> *"this function passes no cap, so it takes `bison.PAGE_CAP = 40` and refuses
> on any queue past 600 rows. Campaign 491 is 665."*

A defect documented in the module that has it, for weeks, with no test and no
fix. That is this repository's own signature failure — a thing computed
correctly that nothing downstream acts on.

### Two findings beyond the cap

- **`scripts/bounce_stop_7day.py` has zero `except` clauses in the whole file.**
  Its own `OURS` tuple is `(487, 489, 491, 492, 493, 494, 495, 496, 497, 498)`,
  and 491 is the **third** campaign it walks. So the standing **bounce > 2% per
  mailbox over 7 days** hard stop raises `PartialInventory` out of `measure()`
  and produces no verdict at all for any mailbox. The one safety control in
  this list cannot currently be measured, for the same one-parameter reason.
- **`scripts/batch_activate.py:158` turns a refusal into `queue = []`** and then
  reports `queue_rows: 0`, `sent_rows: 0`, `first_scheduled: None` into
  `work/batch-activation-report.json`. That is the false zero the whole module
  is written against. It is the only silent-empty of the eighteen.

Items 2, 3, 4, 5, 7, 8, 9, 10, 13, 14, 15 all handle a refusal correctly. The
problem with 2 and 3 is not safety, it is reach: `collision.zero_send_evidence`
can **never** clear campaign 491, because the queue read it depends on refuses
at 40 and will refuse for ever.

---

## 2. WHICH CAMPAIGNS ARE OVER WHICH LINE TODAY

All twenty, from the watcher's own heartbeat at 2026-10-15T21:55-21:58Z. The
page counts are confirmed independently by the 2026-10-03 census, which
recorded `pages: 45` for `rows: 665` on 491 — the same arithmetic, measured
rather than derived.

| Campaign | Status | Leads | Queue rows | Pages | vs `PAGE_CAP` 40 | rows/lead | at a 3rd step |
|---|---|---|---|---|---|---|---|
| **491** | paused | 333 | **665** | **45** | **REFUSED** | 2.00 | 998 |
| 503 | paused | 250 | 500 | 34 | ok, 6 pages clear | 2.00 | **750** |
| 504 | paused | 223 | 446 | 30 | ok, 10 clear | 2.00 | **669** |
| 505 | paused | 217 | 434 | 29 | ok, 11 clear | 2.00 | **651** |
| 492 | paused | 206 | 409 | 28 | ok, 12 clear | 1.99 | **614** |
| 494 | paused | 76 | 152 | 11 | ok | 2.00 | 228 |
| 495 | archived | 60 | 114 | 8 | ok | 1.90 | 171 |
| 493 | paused | 22 | 64 | 5 | ok | 2.91 | 96 |
| 498 | completed | 15 | 26 | 2 | ok | 1.73 | 39 |
| 487 | paused | 10 | 20 | 2 | ok | 2.00 | 30 |
| 496 | paused | 43 | 17 | 2 | ok | 0.40 | 26 |
| 489 | paused | 5 | 15 | 1 | ok | 3.00 | 22 |
| 497 | completed | 20 | 13 | 1 | ok | 0.65 | 20 |
| 481 | paused | 23 | 10 | 1 | ok | 0.43 | 15 |
| 451 | archived | 1 | 1 | 1 | ok | 1.00 | 2 |
| 501 | completed | 1 | 1 | 1 | ok | 1.00 | 2 |
| 506 | completed | 1 | 1 | 1 | ok | 1.00 | 2 |
| 485 | draft | 10 | 0 | — | ok | 0.00 | 0 |
| 484 | draft | 0 | 0 | — | ok | — | 0 |
| 500 | paused | 0 | 0 | — | ok | — | 0 |

**Twenty campaigns, 2,888 queue rows, 205 pages in total. One is over.**
No campaign is anywhere near the 400-page cap: the largest needs 45 of 400.

**THE LINE IS NOT 600 ROWS, IT IS 300 LEADS.** The five largest campaigns all
sit at exactly two scheduled rows per lead — 665/333, 500/250, 446/223,
434/217, 409/206. At that ratio `PAGE_CAP = 40` means *any campaign holding
more than 300 leads is invisible to this producer*. 491 has 333. **503 is fifty
leads away from the same wall.**

And the queue grows by step, not only by lead. The last column is each
campaign's row count if a third sequence step were added at today's lead count:
**503, 504, 505 and 492 would all cross 600.** So this is not "a limit nobody
is near" — it is a limit one campaign has crossed and four more cross on the
next sequence change, with no lead added at all.

---

## 3. WHAT IS SILENTLY MISSED — AND WHAT IS LOUDLY MISSED

For 491, the campaign already over the line:

**Nothing is missed silently.** `_paged` raises, and every `src/` consumer of
`scheduled_rows` propagates. `leadobserve.record_bounces(491)`,
`leadobserve.confirm_email_touches(491)` and `leadobserve.observe_emails(491)`
all raise `PartialInventory` rather than returning an empty or partial list.
Measured, not argued: the born-red test in §5 reproduces the real refusal
contract and all three raise.

**What is missed is the whole campaign.** The watcher sees all 665 rows; the
producer sees zero. In particular:

- **491 carries a bounce.** Its heartbeat membership reads
  `{stopped: 103, sending_paused: 218, replied: 11, bounced: 1}` and its
  campaign counters read `bounced: 1`. Across the twenty the bounces are
  491 ×1, 492 ×1, 495 ×1, 503 ×2 — the five this lane has been working
  through since TASK-0100. **One of the five sits in the only campaign the
  bounce producer cannot read.** Its address has never passed through
  `bouncepolicy.decide` by this path and cannot, at cap 40, ever.
- **411 sends and 11 replies** on 491 are likewise unreachable through this
  producer. They are not needed by `record_bounces`, which narrows to
  `bounced` before the writer — but they are the reach `confirm_email_touches`
  would need, and it is already the larger gap (§6).
- **Whether a truncating reader would lose the newest or the oldest rows is
  UNKNOWN**, and it is the one question here I will not answer by inference.
  Neither `docs/BISON-API-CAPABILITY-MAP-2026-09-14.md` nor
  `docs/BISON-API-ROUTE-EVIDENCE-2026-09-15.md` records a sort order for
  `GET /campaigns/{id}/scheduled-emails`, and no stored artifact carries rows
  with their page index. The authority would be a single provider read of
  page 1 and page 45 of 491's queue, comparing `id` and `scheduled_date` — a
  provider call this task forbids. **It does not change the fix**: the
  producer gets no rows at all today, so there is no "which half" to lose.
  It matters only to anyone tempted to replace the refusal with a prefix, and
  the test in §5 makes that replacement go red regardless.

---

## 4. IS RAISING THE CAP SAFE? YES, AND THE WATCHER'S OWN RECORD PROVES IT

Confirmed from the record rather than assumed, four ways.

**(a) The same campaign, the same endpoint, 40 versus 400, both logged.**
Two generations of watcher log sit side by side in the main checkout's `work/`:

    w-bison-491.out            (the uncapped generation, pre-2026-09-23)
      ... SEND 491 queue rows sent 254 of 585
      READ-ERROR 491 unreadable 3x: PartialInventory
      READ-ERROR 491 unreadable 12x: PartialInventory

    w-bison_watch_loop.py.491.out   (cap=400, post-fix)
      WATCHING 491 status=active leads=331 sent=281
      ... SEND 491 queue rows sent 303 -> 304 of 649

At 40 the queue read 585 rows and then died the moment it crossed 600. At 400
the identical read answers 649, then 665, and keeps answering. **`grep
QUEUE-UNREADABLE` across the whole of `work/` returns nothing** — the watcher's
own "I could not read the queue" line has never fired since the cap was raised.

**(b) The provider's answer is complete, not merely non-erroring.**
`bison._paged` also refuses when `len(rows) != meta.total`. So
`queue_rows: 665` in `bison-491.json` is not "it did not crash" — it is the
provider's own `meta.total` agreeing with 665 rows actually delivered across 45
pages.

**(c) Cost, measured.** From `work/forward-book-census.json`, complete walks of
2026-10-03, same route:

| Campaign | Pages | Rows | Elapsed | Rate |
|---|---|---|---|---|
| 491 | 45 | 665 | **9 s** | 5.0 pages/s |
| 503 | 34 | 500 | 6 s | 5.7 |
| 504 | 30 | 446 | 5 s | 6.0 |
| 505 | 29 | 434 | 6 s | 4.8 |
| 492 | 28 | 409 | 5 s | 5.6 |
| 352 (client) | 6,480 | 97,195 | 3,129 s | 2.07 |
| 327 (client) | 3,419 | 51,276 | 1,304 s | 2.62 |
| 328 (client) | 2,816 | 42,233 | 815 s | 3.46 |

A full read of 491 is **45 requests and 9 seconds**. A full read of all twenty
of our queues in one pass is **205 requests**, well under a minute. The census
walked 12,715 pages across three client campaigns in 87 minutes, every one
`complete: true`, with no 429 and no retry recorded.

**The marginal cost of the proposed fix is five requests and about one second**
— 45 pages instead of 40 — and on the only campaign it changes.

**(d) The sustained rate the provider already tolerates.** The watcher reads
all twenty queues every 180 s at cap 400: ~205 page requests per cycle, about
**1.1 requests per second, continuously, since 2026-09-23**. Nothing proposed
here adds a cycle or a campaign.

### But do NOT remove the cap

Three reasons, and the first is measured against this estate:

1. **Offset pagination on this instance is refused with HTTP 422 beyond roughly
   500 pages** — recorded against campaign 352 in
   `docs/THE-23rd-IS-PROVEN-2026-09-18.md` and
   `docs/CONTEXT-RESET-2026-09-15-D.md`, and the reason
   `scripts/bison_forward_book_census.py` exists in cursor mode at all. The
   documented limit is 1,000 pages; the measured one is ~500.
   `CAMPAIGN_QUEUE_PAGE_CAP = 400` sits deliberately below it.
2. **An uncapped walk would turn a named `PartialInventory` into an unnamed
   `ProviderError`.** Every caller in §1 is written against the first.
   `hard_stop_check` reports BLIND on it; the watcher records the queue as
   `None` rather than `0` on it. A 422 at page 501 reads as a transport
   failure, which is retried, which fails again.
3. **The refusal is the property, not the number** — `bison.py`'s own words.
   An uncapped read of a client campaign would walk 6,000 pages before
   refusing, instead of saying no in 40.

---

## 5. PROPOSED CHANGE — NOT APPLIED

**Smallest robust fix: an explicit argument at two `src/` call sites. Not a
default, and not removing the cap.**

```python
# src/leadobserve.py:462 — scheduled_rows
    for row in (bison.scheduled_emails(
                    campaign_id, cap=bison.CAMPAIGN_QUEUE_PAGE_CAP)
                if queue is None
                else queue):

# src/collision.py:553 — _queue_is_silent
        rows = bison.scheduled_emails(
            campaign_id, cap=bison.CAMPAIGN_QUEUE_PAGE_CAP)
```

Two lines of real change. Nothing else in `src/` needs touching:
`bisonfactory`'s push gate and `slackagentreadback` already pass 400, and
`bisonfactory._already_on_campaign`'s 40 is argued correct in its own docstring
(an unreadable queue returns `set()`, which can only add collision checks).

### Why NOT a default

Changing `PAGE_CAP` from 40 to 400, or defaulting `scheduled_emails`' `cap` to
`CAMPAIGN_QUEUE_PAGE_CAP`, would be one character fewer and wrong:

- `PAGE_CAP` also guards `membership()` and `campaign_lead_ids()`, whole-campaign
  **membership** walks. Raising it there would let a walk of client campaign 352
  — 21,159 leads — run 400 pages before refusing instead of 40, and the bounded
  answers (`campaign_lead_count`, `membership(campaign, lead_ids)`) exist
  precisely so that walk is never attempted.
- A default is how this defect happened. `scheduled_rows` did not choose 40; it
  inherited it. A second implicit inheritance is not a fix, it is the same bug
  with a better number — and it would silently re-point the eight uncapped
  `scripts/` call sites in §1, several of which (`batch1_build` at 80,
  `check_readback` at 200) have deliberately chosen their own.

### Why not fix all eighteen in this change

`scripts/bounce_stop_7day.py` and `scripts/batch_activate.py` are real defects
(§1) and both are **outside this task's scope** — one is a safety control whose
repair is a `try/except` and a BLIND verdict, not a cap, and the other is a
silent-empty that wants the same treatment. **Filed, per the FOCUS RULE, not
folded into this diff.** The remaining six uncapped scripts handle a refusal
correctly and are one-off operator tools, not production readers.

### The born-red test — written, run, and attacked

`tests/test_the_producer_reads_forty_pages_and_the_watcher_four_hundred.py`,
13 tests. Committed; **the production change is NOT committed.**

It cannot use `tests/fakebison.py`, whose `scheduled_emails` ignores `cap`
entirely and never paginates — which is why no existing fixture could have
caught this. Instead a `_Pager` stands in at the provider seam with the real
refusal contract: fifteen rows a page, raise past the cap, never a prefix.

On master `02761a708`, unmodified — **6 RED, 7 green**:

    test_scheduled_rows_asks_for_the_queue_cap            FAIL  [None] != [400]
    test_confirm_email_touches_asks_for_the_queue_cap     FAIL  [None] != [400]
    test_observe_emails_asks_for_the_queue_cap            FAIL  [None] != [400]
    test_every_src_queue_reader_asks_for_the_queue_cap    FAIL  leadobserve + collision
    test_scheduled_rows_reads_every_row_of_491            ERROR PartialInventory: 45 pages,
                                                                this read stops at 40
    test_record_bounces_reaches_every_bounced_row         ERROR same

With the two-line change applied in a scratch edit: **13/13 OK**, then reverted
and the revert proven by hash (§7).

Three attacks, each applied on top of the fix, each caught by exactly the
intended tests and no others:

| Attack | Red |
|---|---|
| catch `PartialInventory`, return `[]` | `TheRefusalSurvivesTheRaise` ×2 — and only those |
| pass the cap, then `[:600]` the rows | `..._reads_every_row_of_491`, `..._reaches_every_bounced_row` |
| pass `cap=80` instead of the constant | the four one-number tests (80 still reads 491, so the row-count tests correctly stay green) |

The third attack is the important one: it proves the test asserts *one number
for one queue*, not merely *a number big enough for today*. 491 needs 45 pages;
a reader given 80 would work today and disagree with the watcher tomorrow.

The test also pins the ceiling — `assertLess(CAMPAIGN_QUEUE_PAGE_CAP, 500)` —
so "just remove the cap" goes red too, with the 422 measurement in the
docstring.

---

## 6. WHAT THIS DOES NOT FIX

**`leadobserve.confirm_email_touches` still has no production caller, and a
complete read into a gate nobody calls changes nothing.** This is the larger
gap and this task does not touch it. The provider confirms **918 sends across
the twenty campaigns against ONE confirmed touch in 1,582 records** — the
number `record_bounces`' own docstring cites as the reason the full
`confirm_email_touches` is deliberately *not* wired into a loop: doing so would
write 918 touches and silently change who may be contacted, which is a decision
nobody has taken.

So the honest accounting of what the two lines buy:

- `record_bounces(491)` becomes **possible** instead of raising. It does not
  become **called** — the lane's own TASK-0120 report already records that
  there is no production caller and no reversal command.
- `collision.zero_send_evidence(491)` becomes capable of answering. It is
  still only reached from the paths that already reach it.
- The 2% bounce hard stop still cannot be measured, because
  `bounce_stop_7day.py` is a separate uncaught-refusal defect (§1) that a cap
  change alone does not repair.

**The cap is a necessary condition and nothing more.** The producer currently
cannot read 491; after this it can. Whether anything then asks it to is a
different, filed, unresolved question — and raising the cap without saying that
would be exactly the "existence is not function" defect CLAUDE.md names.

---

## 7. TREE AND MEASUREMENT HYGIENE

- Every number above was measured on **`02761a708`**, in
  `wt-suppression-2026-10-14`, between 2026-10-16 00:05 and 01:20 local. The
  worktree stayed on its branch throughout.
- **The scratch edit was reverted and the revert proven by hash, not by
  `git status`.** `src/leadobserve.py` md5
  `02dded57e781c958b19c0905609c2b96` before and after.
- **`src/collision.py`'s LINE ENDINGS CHANGED IN THIS TREE AND THE NEXT LANE
  MUST KNOW.** It was on disk in the **CRLF** form of HEAD's content
  (`40189473505b642d1fbfadb72dc9de36`) while `git status` called the tree
  clean; after the scratch edit and `git checkout --` it is the **LF** form
  (`028dab4587a390ac9b0695bdab339ad1`), which `git hash-object` confirms is
  byte-identical to `HEAD:src/collision.py`
  (`50efeb8aadf163c41d2ce2fc8349ae0c23a2eceb`). Proven, not inferred: the
  blob piped through `sed 's/$/\r/'` md5s to exactly the pre-edit value.
  `git status` called the tree clean **both** before and after, so the stale
  state was invisible — this tree's index stat-cache was hiding a non-HEAD
  file, the same class as the `src/claims.py` finding. The file was left at
  HEAD's bytes, which is the canonical state and leaves the tree genuinely
  clean; restoring the CRLF form made `git status` report ` M src/collision.py`,
  which is what it should have been saying all along. **A suite name-set
  measured in this tree before 2026-10-16 may differ from one measured after,
  by any name that reads `src/collision.py`'s bytes.**
- **No full suite was run and none is claimed.** The 13 tests above were run
  as a single module. Per the standing merge gate this branch owes a full
  reference run on `02761a708` before anything merges, and adding an untracked
  file under `tests/` changes the fixture-hygiene corpus, so the owed reference
  must be measured **with** this file present.
- Raw artifacts: `work/suppression-measure/0130/bornred.{out,err}` and
  `bornred-names.txt` (gitignored, local to this tree).

---

## 8. FOR THE OPERATOR — three decisions, none blocking

1. **Apply the two-line cap fix?** Recommended: yes. Five extra requests on
   one campaign, against a producer that currently cannot read the only
   campaign over the line, which is also one of only four campaigns in the
   estate carrying an unrecorded bounce. Reversible, local, no provider write.
2. **Repair `scripts/bounce_stop_7day.py`?** Recommended: yes, separately and
   soon. The standing **bounce > 2% per mailbox over 7 days** hard stop
   produces no verdict at all today, for any mailbox, because the third
   campaign in its own list is 45 pages. That is a safety control that is
   currently a no-op, and nobody would know from its output — there is no
   output.
3. **The 918-sends-to-one-touch question is still open** and is not this
   task's to decide. Wiring `confirm_email_touches` into a loop changes who
   may be contacted. It needs the operator, and it is recorded here only so
   that "the cap is fixed" is never read as "the gate now runs".
