# One campaign is past the queue cap and four cross it on the next step

TASK-0150, lane `suppression`. Measured in `wt-suppression-2026-10-14` on
branch `task-suppression-bounce-RULE-2026-10-15`, whose tip was **`755d43e3b`**
when this work started. `origin/master` unchanged at `b1f290c84`.

**No provider call and no network call.** Every number is read from a committed
artifact or derived from one. The counts are
`docs/state/QUEUE-COUNTS-2026-10-15.json`, transcribed from TASK-0130's
committed table, which came from the watcher's own heartbeat at
2026-10-15T21:55-58Z with page counts corroborated by the completed
forward-book census of 2026-10-03.

---

## 0. THREE CORRECTIONS, BEFORE ANY OF THE WORK

Two are to TASK-0130's own report — mine, from this lane — and one is to a
number both it and this brief repeat.

### 0a. 491's BOUNCE WAS NEVER OUT OF REACH. The production path does not take the cap.

TASK-0130 wrote that 491 *"carries a bounce … Its address has never passed
through `bouncepolicy.decide` by this path and cannot, at cap 40."* **That is
wrong.** Traced and tested:

    bison_watch_loop.main
      -> snapshot(watched, on_queue=_bounce_recorder(...))
      -> bison.scheduled_emails(id, cap=bison.CAMPAIGN_QUEUE_PAGE_CAP)   # 400
      -> on_queue(queue)
      -> leadobserve.record_bounces(id, queue=queue, live=True)
      -> leadobserve.scheduled_rows(id, queue=queue)   # iterates, NO read

The watcher hands over rows it has already paid for at **400**, and
`scheduled_rows` with a `queue=` makes no provider call at all — so the
40-page default was never on that path. `bison_watch_loop.py` says so in its
own docstring: *"ZERO EXTRA PROVIDER CALLS. `snapshot` has already paid for
this queue; it hands the rows here rather than letting a second reader walk
them, which would also be a SMALLER read."*

Measured, not argued: `test_handed_rows_make_no_provider_call_at_all` asserts
the pager recorded **no** calls, `test_all_665_rows_survive_the_trim_when_
handed_in` asserts all 665 reach the gate, and
`test_the_watcher_reads_the_queue_once_at_four_hundred` runs a real `snapshot`
cycle and asserts `caps == [400]` with one `on_queue` call carrying 665 rows.
**That whole class was GREEN before this change and is green after** — it is
the control that the cap fix must not move the production path onto a second
read. And M4 below, which reverts the cap, reddens seven tests and **none of
them is in that class**, which is the same fact from the other side.

**What the cap really bit:** `collision._queue_is_silent`, `observe_emails`,
and `confirm_email_touches`/`record_bounces` called WITHOUT `queue=` — which
is the `leadobserve` CLI. Those are real and they are fixed here. But
"the bounce gate cannot see 491" was not true, and anything built on it should
be rebuilt.

### 0b. "205 pages" is 205 REQUESTS across 202 pages of rows

202 pages carry rows. Three campaigns (484, 485, 500) hold none, and each
still costs one request to discover that. Both numbers are right and they are
not the same number; `src/queuewall.pages` returns 1 for an empty queue for
exactly this reason, and `test_the_totals_are_2888_rows_202_page_reads_205_
requests` pins all three.

### 0c. THE WATCHER'S INTERVAL IS 300 SECONDS IN THE CODE, NOT 180

TASK-0130 and this brief both say "every 180 seconds". `bison_watch_loop.main`
has `--interval` with **`default=300.0`**, and `--campaign` with
`default=PROVIDER_ID` — so **one process watches ONE campaign**, not twenty in
a loop. Whether a running watcher was launched with `--interval 180`, and how
many are running, is production state (`work/`, the process list) that this
task may not read. **So: the code default is 300s; the live cadence is
UNKNOWN and its authority is the running process's command line.** Every rate
below is given per process so the arithmetic survives either answer.

---

## 1. §1 — THE REFUSAL IS NOW NAMED, AND THE PREMISE NEEDED ONE FIX

The brief says *"a producer that returns an empty list for a reason is not the
same as one that returns an empty list because there is nothing"*. **Neither
reader returned an empty list.** `scheduled_rows` propagates
`PartialInventory`; `collision._queue_is_silent` catches and returns
`(False, reason)` naming the exception class. Both already distinguished the
two cases at the call site, and TASK-0130's table recorded that.

What did not exist is **a run that says which campaigns are past which cap and
exits non-zero.** That is `scripts/queue_wall_check.py`, and the per-campaign
refusal names the rows, the pages and the cap it hit:

    OVER 491 for producer-default (cap 40 pages = 600 rows): 665 rows is 45
    pages and this reader stops at 40; it cannot read this queue at all

Exit codes, and the third is the one that matters:

    0   every campaign fits every reader's cap AND survives one more step
    1   at least one campaign is OVER a cap, or AT-RISK on one more step
    2   cannot assess - the counts are stale, or a campaign's size is UNKNOWN

`2` outranks `1`: a run that could not measure must not report the same code
as a run that measured and found a wall. Same rule as TASK-0140's BLIND.

## 2. §2 — THE CAP, AND THE COST, MEASURED BEFORE THE PREFERENCE

### What moved

**Exactly one value, at two call sites, and nothing else:**

| Call site | Was | Is |
|---|---|---|
| `src/leadobserve.py` `scheduled_rows` | nothing passed → `bison.PAGE_CAP` = **40** | explicit `cap=bison.CAMPAIGN_QUEUE_PAGE_CAP` = **400** |
| `src/collision.py` `_queue_is_silent` | nothing passed → **40** | explicit **400** |

`bison.PAGE_CAP` is **unchanged at 40**. `bison.CAMPAIGN_QUEUE_PAGE_CAP` is
**unchanged at 400**. No constant was edited; two callers stopped inheriting.

### The cost, per process per hour

| | before | after |
|---|---|---|
| watcher process on 491 (300s, cap 400) | 45 req/pass, 12 passes/h = **540 req/h** | **540 req/h** — unchanged |
| the same for all twenty, one process each | 205 req/pass = **2,460 req/h** | **2,460 req/h** — unchanged |
| `record_bounces` inside that cycle | **0** (rows handed in) | **0** |
| `leadobserve` CLI on 491 | 40 requests then a refusal, no answer | **45 requests, ~9 s, an answer** |
| `collision._queue_is_silent(491)` | 40 requests then `False` for ever | **45 requests, an answer** |
| any other campaign | unchanged | unchanged — none exceeds 40 pages |

**The fix costs ZERO extra requests per hour in production**, because the only
reader in a loop already walked 400 and the bounce recorder is handed its
rows. Stronger than TASK-0130's "five requests and about one second", which
was right about the marginal read and wrong about where it happens: the five
requests are paid by a human running the CLI, not by the loop.

The 9 seconds is the census's own measurement of a complete 45-page walk of
491 (`work/forward-book-census.json`, `complete: true`), quoted in TASK-0130.

### Raising `PAGE_CAP` instead: rejected, with the number

`PAGE_CAP` also guards `membership()` and `campaign_lead_ids()` — whole-campaign
**membership** walks. Client campaign 352 holds 21,159 leads and 95,312 queue
rows. Today a stray whole-campaign walk of it refuses after **40** requests;
at 400 it would burn **400** before refusing. The bounded answers
(`campaign_lead_count`, `membership(campaign, lead_ids)`) exist precisely so
that walk is never attempted, and raising the cap there makes the mistake ten
times more expensive while fixing nothing. **And a default is how this defect
happened:** `scheduled_rows` did not choose 40, it inherited it, and a second
implicit inheritance would silently re-point eight uncapped `scripts/` call
sites, two of which (`batch1_build` at 80, `qa/check_readback` at 200)
deliberately chose their own.

### Removing the cap: rejected

Offset pagination on this instance is refused with HTTP 422 beyond roughly 500
pages, measured against 352 and recorded in
`docs/THE-23rd-IS-PROVEN-2026-09-18.md`. An uncapped walk converts a named
`PartialInventory`, which every caller is written against, into a
transport-shaped `ProviderError` that gets retried and fails again.
`test_the_cap_is_not_the_membership_default` pins `PAGE_CAP == 40` and
`CAMPAIGN_QUEUE_PAGE_CAP < 500` so both "just raise it" and "just remove it"
go red.

### A third option, considered and rejected

Make `scheduled_rows` REFUSE to read for itself — require `queue=` — so there
is exactly one reader of this endpoint. Rejected: `observe_emails` and the CLI
legitimately need their own read, and a caller-must-remember contract is the
same implicit-inheritance defect in a new shape, with the failure moved from a
wrong number to a missing argument.

**RECOMMENDATION: the explicit cap at the two call sites. Applied.** See §6 for
the standing-rules tension that makes this disclosable rather than silent.

## 3. §3 — THE EARLY WARNING, AND THE MARGIN IS NOT A PERCENTAGE

`src/queuewall.py` assesses every campaign against **every reader's cap**,
because TASK-0130 measured five distinct effective caps for one endpoint and a
campaign readable by the watcher can be invisible to the gate beside it. Each
campaign reports `readable_by` and `invisible_to` by reader name.

**The margin is one more sequence step at today's lead count.** Not chosen —
it is the largest discrete jump a queue can take, it needs no lead added, and
the operator can schedule it this afternoon. The five largest campaigns sit at
exactly two scheduled rows per lead, so the step count comes out of the counts
and a third step is `rows × 3/2`.

Against `producer-default` (cap 40, the value before this change):

| Campaign | leads | rows | pages | verdict | one more step |
|---|---|---|---|---|---|
| **491** | 333 | 665 | **45** | **OVER** | — already unreadable |
| 503 | 250 | 500 | 34 | **AT-RISK** | **750 rows, 50 pages** |
| 504 | 223 | 446 | 30 | **AT-RISK** | **669 rows, 45 pages** |
| 505 | 217 | 434 | 29 | **AT-RISK** | **651 rows, 44 pages** |
| 492 | 206 | 409 | 28 | **AT-RISK** | **614 rows, 41 pages** |
| the other fifteen | | | ≤11 | OK | fits |

**At cap 400 every one of the twenty is OK**, which is what the fix buys and
why the check reports per reader rather than once.

**The line is 300 leads, not 600 rows.** At two rows a lead,
`leads_of_headroom(leads, rows, 40)` gives 491 **−33** and 503 **+50**; 300
leads is exactly zero headroom.

**Stale counts assess NOTHING.** Past `--max-age-days` the run returns no
campaign verdicts at all and exits 2, because a stale cached provider file
reading as current is this project's own recorded defect. The counts file says
in its own `authority` field that it is not the authority.

**UNKNOWN is never OK.** A campaign with no row count is UNKNOWN and refuses
the run, and `PASSING` is literally `(OK,)`.

## 4. BORN RED, GREEN, RED AGAIN — HASH-VERIFIED

`tests/test_four_more_campaigns_walk_into_the_same_wall.py`, **41 tests**,
eleven classes. Together with TASK-0130's file that is **54 tests**, all green.

| State | `src/leadobserve.py` | `src/collision.py` | Result |
|---|---|---|---|
| pristine (new files present) | `02dded57…` | `028dab45…` | **3 RED**, 38 green |
| repaired | `787b3026…` | `f324e0ac…` | **41/41 OK** |
| pristine again, byte-exact | `02dded57…` | `028dab45…` | **3 RED**, 38 green |
| repaired again, byte-exact | `787b3026…` | `f324e0ac…` | **41/41 OK** |

The two pristine hashes are **exactly the values TASK-0130 recorded** for the
same files, which is the continuity check between the two tasks.

The 3 red are precisely the cap assertions —
`test_scheduled_rows_asks_for_four_hundred`,
`test_queue_is_silent_asks_for_four_hundred`,
`test_zero_send_evidence_can_now_reach_491s_queue`. **Everything else is green
before the change on purpose**: the correction class (§0a) asserts a property
that was already true, the arithmetic classes assert `src/queuewall.py`, and
the fixture guard asserts the counts file.

On the same pristine state TASK-0130's own module returns **exactly the six
born-red names it recorded** — `test_scheduled_rows_asks_for_the_queue_cap`,
`test_confirm_email_touches_asks_for_the_queue_cap`,
`test_observe_emails_asks_for_the_queue_cap`,
`test_every_src_queue_reader_asks_for_the_queue_cap`,
`test_scheduled_rows_reads_every_row_of_491`,
`test_record_bounces_reaches_every_bounced_row` — and **13/13 green** with the
fix. Its proposal is now applied and proven by its own tests.

**The honest limit of the red for the new module:** with `src/queuewall.py` and
`scripts/queue_wall_check.py` removed, the test file does not import at all —
**one error, not 41 names.** "The module does not exist" is a weak red, and
the strength of these tests rests on the three cap names above and on the four
attacks below, not on that import failure.

## 5. THE FOUR ATTACKS

Each applied on top of the fix, run across both modules, restored from a
byte-exact copy with the md5 proven after each.

| Mutation | Named kill | Total red |
|---|---|---|
| **M1** report off stale counts instead of refusing | `StaleCountsAssessNothing.test_a_stale_run_assesses_no_campaign_at_all` | 3 |
| **M2** downgrade AT-RISK to OK | `TheMarginIsOneMoreSequenceStep.test_all_four_behind_491_are_at_risk_at_cap_forty` | 4 |
| **M3** exit 0 even when refused | `TheExitCodesAreThree.test_main_returns_the_code_it_computed` | 4 |
| **M4** the producer inherits the cap again | `EverySrcQueueReaderAsksForTheQueueCap.test_scheduled_rows_asks_for_four_hundred` | 7 |

**M4 is the informative one.** It reddens seven tests across both files and
**not one of them is in `TheProductionBouncePathNeverTookTheCap`** — which is
§0a's correction measured from the other side: reverting the cap breaks the
CLI and gate readers and leaves the watcher's bounce path untouched, because
that path never used the cap.

M2 is the second most informative: it reddens the one-line summary test as
well as the classification, so a silent downgrade cannot hide in the sentence
the operator reads.

## 6. ONE PARAGRAPH FOR THE OPERATOR

Today, one of our campaigns — 491, with 333 leads — has a message queue too
long for one of the two bits of code that read it, so that bit of code sees
nothing at all rather than seeing part of it. It is the safe kind of failure
and it has been real since 22 September. The bounce recorder that matters was
never affected: the watcher reads the long queue correctly and hands the rows
over, which I confirmed rather than assumed, and an earlier report of mine
that said otherwise was wrong. What breaks next is the part worth your
attention: if a third email is added to any sequence, four more campaigns —
503, 504, 505 and 492 — cross the same line on the same afternoon, with no
lead added to any of them, because their queues grow by one row per lead per
step. I have raised the limit at the two readers that were short, from 40
pages to 400, which is the number the watcher and the other hard-stop check
have used since September; it costs nothing in the running system because that
system already read at 400, and it takes five extra requests and about nine
seconds when a person runs the check by hand. Nothing else moved, nothing was
sent, and no campaign was touched. **The one thing you may want to decide is
whether a pagination limit counts as a "cap" under the standing no-cap-change
rule** — I judged it does not, because it governs reading rather than sending
and fails closed in both directions, and I put it in its own commit so it can
be undone on its own with one command.

## 7. FOR THE OPERATOR — decisions, none blocking

1. **The standing-rules tension, named rather than glossed.**
   `_STANDING-RULES.md` says *"No cap or gate change"* under PROHIBITED,
   ALWAYS. This brief says *"Decide the cap honestly… Recommend one"* and
   *"Do not change any cap or gate that the standing rules protect without
   saying in your entry exactly which value moved, from what, to what"* —
   permission conditioned on disclosure, which §2 meets exactly. **My reading:
   a pagination page-limit on a READ path is not a sending cap or a safety
   gate; it fails closed in both directions and governs no volume.** TASK-0130
   took the stricter reading and proposed without applying. **If you prefer
   that reading, revert the cap commit alone** — it is one commit touching two
   files, and three named tests will go red to tell you it is gone.
2. **`hard_stop_check.py` still uses `>` where TASK-0140's bounce stop now uses
   `>=`.** Carried forward from 0140, unchanged. One character, one file.
3. **The watcher's live interval is UNKNOWN.** The code default is 300s and the
   record says 180s. It changes every rate in §2 by a factor of 1.67 and
   changes no verdict. The authority is the running process's command line.
4. **`confirm_email_touches` still has no production caller** — TASK-0130's §6,
   unchanged. The cap fix makes it *possible*, not *called*. 918 provider-
   confirmed sends against one confirmed touch in 1,582 records; wiring it
   changes who may be contacted and needs you.

## 8. TREE AND MEASUREMENT HYGIENE

- Measured in `wt-suppression-2026-10-14` on branch
  `task-suppression-bounce-RULE-2026-10-15`, starting from `755d43e3b`,
  between 2026-10-16 01:10 and 02:10 local. The worktree stayed on its branch
  and `origin/master` was re-read as `b1f290c84`.
- **No provider call, no network call, no send, no activation, no suppression
  write, no `config/.env` read, no `STOP-SENDING` file, no campaign touched.**
  `src/providers/bison.py` was READ (constants and the refusal contract) and
  **not modified**.
- Every mutation restore was proven by md5, not by `git status`. See §4 and §5.
- **This tree re-materialises files as LF** — see TASK-0140's §9; the shared
  `.git/config` sets `core.autocrlf=false` and overrides the system `true`, so
  the CRLF files here are leftovers from the hand checkout of 2026-10-14. The
  two `src/` files were edited in place and their pristine hashes match
  TASK-0130's recorded ones exactly, so no ending flipped under this change.
- **No full suite was run and none is claimed.** Two modules, 54 tests, all
  green. This branch now adds **four** tracked files across 0140 and 0150
  (`tests/…verdict_for_every_mailbox.py`, `tests/…same_wall.py`,
  `src/queuewall.py`, `scripts/queue_wall_check.py`, plus two docs and one
  state file), and the fixture-hygiene corpus includes tracked files, so **the
  owed full reference run must be measured with all of them present.**
- Raw artifacts, gitignored, under `work/suppression-measure/0150/`:
  `mutate.py`, `MUTATIONS.txt`, `RED-stageA.txt`, and the byte-exact pristine
  and fixed copies of both `src/` files.
