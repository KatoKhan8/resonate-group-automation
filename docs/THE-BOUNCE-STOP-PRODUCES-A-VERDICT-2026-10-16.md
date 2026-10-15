# The 2% bounce hard stop produced no verdict, and now produces three

TASK-0140, lane `suppression`. Measured and repaired in
`wt-suppression-2026-10-14` on branch `task-suppression-bounce-RULE-2026-10-15`,
whose tip was **`2edca33a6`** when the measurement was taken. `origin/master`
is unchanged at `b1f290c84`.

**No provider call and no `config/.env` read.** Both are stubbed at the seam.
What is not stubbed is the refusal contract: the pager raises exactly what
`bison._paged` raises, at the page counts
`docs/SUPPRESSION-THE-PRODUCER-READS-FORTY-PAGES-2026-10-16.md` measured off
the watcher's own heartbeat (2026-10-15T21:55-58Z) and the completed
forward-book census of 2026-10-03.

---

## 0. THE ONE-LINE ANSWER

The claim filed by TASK-0130 holds, and it is worse in one way and better in
another than it was filed.

**Worse:** it is not only that no mailbox got a verdict. 487 and 489 were read
**whole**, their rows counted, and then thrown away with the exception — so
the check discarded evidence it had already paid for. And campaigns 492
through 498 were never asked at all. Three of ten read, zero verdicts, nothing
on stdout.

**Better:** the run is not silent in a terminal. It exits **1** with a 1,397-byte
traceback on **stderr**. Which is its own defect: **1 is this script's own
TRIPPED code**, so a reader keyed on the exit status cannot tell a tripped hard
stop from a crashed one. That is why the repaired exit codes are three.

---

## 1. THE REPRODUCTION, BEFORE ANY REPAIR

`work/suppression-measure/0140/reproduce.py`, against the unmodified script.

    campaigns asked:   487 (cap None), 489 (cap None), 491 (cap None)
    campaigns never asked:  492 493 494 495 496 497 498
    stdout:            0 bytes
    stderr:            1397 bytes - a traceback
    exit:              1

    src.providers.bison.PartialInventory: emailbison scheduled_emails:
    45 pages to walk and this read stops at 40. Refusing to return 600 of
    665 as though it were all of them

It raises from `measure()`, line 73, on the **third** campaign in its own
`OURS` tuple. `main()` never reaches its first `print`.

**Run twice, and the second run is the one that matters.** With every row
dated outside the 7-day window the result could be dismissed as an empty
window. So the same queues were re-dated to yesterday — 487 with 20 in-window
sends and 489 with 15, both read whole before 491 is reached — and the output
is **byte-identical**: 0 bytes, exit 1, no verdict for either mailbox. The
silence is the refusal, not an empty window.

## 2. HOW LONG, AND HOW MANY SENDS

**Since 2026-09-22, which is 24 days.** Pinned from committed artifacts, not
inferred:

- `docs/THE-7-DAY-BOUNCE-STOP-2026-09-22.md` records a **successful** run that
  day at 11:27Z, window 09-15 → 09-22, reporting mailbox 3437 at 0.00% over 3
  sends and `TRIPPED: none`.
- `src/providers/bison.py:1659` records that **"On 2026-09-22 campaign 491
  grew to 43 pages and the check went BLIND"**, and
  `scripts/hard_stop_check.py:51` says 40 "stopped being enough the day 491
  reached 43 pages". 43 > 40, so from that moment this script could not
  complete.
- `docs/SLACK-AGENT-HANDOFF-2026-09-23-MORNING.md` has 491 at 645 rows / 43
  pages; the 2026-10-03 census has it at 665 / 45.

So the last verdict this script ever produced was on 2026-09-22, hours before
the campaign that breaks it crossed the line.

**How many sends happened in that window: UNKNOWN, bounded above by 918.**
That is the provider-confirmed total across all twenty of our campaigns, cited
in TASK-0130 §6. The honest bound is an upper one and the real number is
lower, because every one of our campaigns is paused, archived, completed or
draft as of 2026-10-15 and the three that ever sent for us were paused by the
operator on 2026-09-28. **Narrowing it further needs a provider read of
`sent_at` per row, which this task forbids** — the authority is
`GET /campaigns/{id}/scheduled-emails`, and no stored artifact carries our
rows with their dates.

## 3. AND NOBODY RUNS IT

Measured, because "what would a human watching see" has a prior question.
`grep` across the whole repository for `bounce_stop_7day` and
`hard_stop_check` returns **docs, the two scripts themselves, and nothing
else**. No service, no timer, no monitor, no `src/` module and no other script
invokes either. **Both are operator-run by hand.**

So for 24 days the standing hard stop had no caller AND could not have
answered if it had one. The repair fixes the second. **The first is an
operator decision and is recorded in §8.**

---

## 4. THE REPAIR

### Three verdicts, and BLIND is one of them

    PASS    measured, under 2%, off a COMPLETE read of every campaign
    STOP    measured AT OR OVER 2%
    BLIND   could not be measured, with the exception CLASS in the reason

**A PASS NEEDS A COMPLETE READ AND A STOP DOES NOT.** This is the load-bearing
asymmetry and it is this repository's own, borrowed from `senderheadroom`:
*"a walk can only undercount, so FULL is provable from any walk and ROOM is
provable from none but a complete, fresh, covering one. REFUSED IS NOT ROOM."*

A campaign we could not read may hold exactly the bounces that would trip a
mailbox, so while anything is unreadable **no mailbox is cleared** — a clean
1.00% comes out BLIND, not PASS. But a mailbox already at or over the line is
over it whatever else arrives, so a STOP stands on a partial read and is never
downgraded to BLIND.

### At or over, not over

`rate >= THRESHOLD`. The rule is written "> 2%" everywhere in this project and
that leaves a measured 2.00% **cleared as a PASS** — verified by mutation, not
argued: with `>`, 2 bounced of 100 comes out `PASS`. Over-inclusive is the
safe direction for a hard stop.

**This now disagrees with `scripts/hard_stop_check.py`, which measures the
same rule on the same endpoint and still uses `>`.** The two answer
differently at exactly 2.00% and nowhere else. Named in §8 as an operator
decision; not changed here, because it is a different file and the FOCUS RULE
applies.

### The catch is narrow

- **Per campaign:** `except bison.ProviderError` — the base of
  `PartialInventory`, `HttpTimeout`, `HttpTransportError`, `MissingKey` and
  `WorkspaceMismatch`, which is every way this read can legitimately fail.
  The campaign is recorded unreadable with `type(exc).__name__` and the
  message, and **the walk continues to the next campaign**.
- **Per row:** `except (ValueError, TypeError)` around the timestamp parse
  only, which blinds **that row's mailbox by name** and leaves every other
  mailbox in a fully-read campaign free to pass.
- **Anything else escapes.** A `KeyError` from our own row handling is not a
  provider refusal and must not be reported as one. `except Exception` round
  the loop would turn every future bug into a BLIND and hide it, which is a
  quieter version of the defect being repaired. There is a test that a
  `KeyError` propagates.

### Exit codes are three

    0   CLEAR or NO-DATA
    1   STOP    at least one mailbox at or over the threshold
    2   BLIND   no stop, but something could not be measured

Any non-zero means do not send until a human has read the line. The old script
used 1 for both a trip and a crash.

### The cap, and why it is in scope

TASK-0130 filed this repair as *"a try/except and a BLIND verdict, not a cap"*.
It is both, and the reason is that the first alone buys nothing:
**at `bison.PAGE_CAP = 40`, campaign 491 can never be read, so no mailbox in
this estate could ever reach PASS and the try/except alone would have produced
a permanent BLIND.** A BLIND-forever hard stop is still a no-op, only a louder
one.

So the script now asks `cap=bison.CAMPAIGN_QUEUE_PAGE_CAP` — **400, the number
its own sibling `scripts/hard_stop_check.py` has asked for since 2026-09-22**,
and the number the watcher and `slackagentreadback` have used on this same
endpoint since 2026-09-23. Cost from the completed census: 491 is 45 pages in
9 seconds, five requests more than 40. Still bounded, because offset
pagination on this instance 422s beyond ~500 pages, and a queue past 400 pages
is reported BLIND rather than measured in part — there is a test for that too,
at 401 pages.

### A send we cannot attribute is still a send

A `sent`/`bounced` row with no usable `sender_email.id` was dropped with no
trace, so a queue of unattributed sends read as a queue of none and every
other mailbox passed off a denominator missing them. Such rows are now
counted, printed, and they blind the roster for the same reason an unreadable
campaign does. They never suppress a STOP. `sender_email` is also a bare
string on some routes, where `.get` is an `AttributeError`; handled by shape,
so that it does not become a swallowed BLIND.

---

## 5. BORN RED, GREEN, RED AGAIN — EACH PROVEN BY HASH

`tests/test_the_bounce_stop_produces_a_verdict_for_every_mailbox.py`, 28
tests, nine classes. Asserted on the return value of `run()` rather than on
printed prose, except the one-line summary, which is asserted to be one line
and to say BLIND out loud.

| State | `scripts/bounce_stop_7day.py` md5 | Result |
|---|---|---|
| pristine | `0cd061318138e8a09da37022055ded2f` | **24 RED**, 4 green |
| repaired | `1ed8a22fdd9bbb93d2e3fa6806999cdd` | **28/28 OK** |
| reverted, byte-exact | `0cd061318138e8a09da37022055ded2f` | **24 RED**, 4 green |
| restored, byte-exact | `1ed8a22fdd9bbb93d2e3fa6806999cdd` | **28/28 OK** |

The four green before the change are the fixture-guard controls, and they are
green on purpose: they assert properties of `bison` rather than of the repair
— that the pager refuses past its cap and never returns a prefix, that 665
rows at 15 a page really is 45 pages and 45 > 40, that `PartialInventory` and
`HttpTimeout` share `ProviderError` as a base while `KeyError` does not, and
that `THRESHOLD` is 2.0. Without them the other 24 could pass vacuously.

### A test caught a hole in the repair itself

`test_a_stop_survives_an_unreadable_campaign` went red against the first
version of the fix. With a stopped mailbox **and** an unreadable campaign, no
mailbox came out BLIND, so the one-line summary said

    7-DAY BOUNCE STOP: 1 mailbox(es) STOPPED, worst 10.00%, 0 PASS - ...

and the blindness **disappeared from the only line the operator reads** — the
same disappearance this task exists to remove, one level up. The summary now
names an unreadable read whether or not any mailbox was blinded by it.

## 6. THE THREE ATTACKS

Each applied on top of the fix, run, then restored from a byte-exact copy with
the md5 confirmed. Names, never counts.

| Mutation | Killed by | Total red |
|---|---|---|
| **M1** swallow the BLIND (`elif not roster_complete` → `elif False`) | `AMailboxUnderTheThresholdPasses.test_a_clean_mailbox_cannot_pass_while_a_campaign_is_unreadable` | 6 |
| **M2** return exit 0 anyway (`EXIT_BLIND` → `EXIT_CLEAR`) | `AReadThatRaisesIsBlindAndLoud.test_a_blind_run_exits_non_zero` and `...test_main_returns_the_non_zero_code_it_computed` | 8 |
| **M3** strict where it should be inclusive (`>=` → `>`) | `AMailboxOverTheThresholdIsStopped.test_exactly_at_the_threshold_is_a_stop` | **1** |

Each named test was then run **alone** under its mutation, to confirm it failed
for the intended reason rather than because a different guard fired first:

    M1   AssertionError: {3437: 'PASS'} != {3437: 'BLIND'}
    M2   AssertionError: 0 == 0
    M3   AssertionError: {3437: 'PASS'} != {3437: 'STOP'}

M3 is the sharpest: it reddens **exactly one** test, which proves that test
asserts the boundary and nothing else — and its message is the finding that a
rule written "> 2%" does not merely leave a gap at its own limit, it **clears**
it.

## 7. THE WEEKLY LINE

What the repaired script prints as its last sentence. Produced by running it,
at the real page counts, with the real campaign list.

**Today, 2026-10-16.** Every one of our campaigns has been paused, archived,
completed or draft since 2026-09-28 and the last send any of them made was
before that, so a 7-day window holds nothing:

    7-DAY BOUNCE STOP: 0 PASS, 0 STOP, 0 BLIND - no mailbox sent for us in 7d
    across 10 campaigns read whole, so every rate is UNDEFINED and UNDEFINED
    is not a pass.                                      verdict NO-DATA exit 0

**The mailbox count in that line is zero, and that is the real count.** It is
not an artefact of the harness: a mailbox appears only if it sent for us in
the window, and none did. The roster of mailboxes with a 7-day rate is
derived from the queue rows and from nothing else, which is why a run that
cannot read the queues has no roster at all rather than a roster of BLINDs.

**During a canary batch**, with sends in the window, the same run at the same
page counts gives the shape the operator will actually see — one line, one
verdict, one exit code:

    7-DAY BOUNCE STOP: 10 mailbox(es) PASS under 2.0% over 7d, 0 STOPPED,
    0 BLIND - all 10 campaigns read whole.                verdict CLEAR exit 0

**And when it cannot measure**, which is the line that did not exist before:

    7-DAY BOUNCE STOP IS BLIND: 0 of 10 campaigns could be read, so no mailbox
    has a verdict and the 2.0% stop did NOT run.          verdict BLIND exit 2

    7-DAY BOUNCE STOP IS BLIND for 1 of 1 mailbox(es): campaign(s) 489
    unreadable, so no mailbox can be cleared (0 STOPPED anyway).
                                                          verdict BLIND exit 2

**The mailbox IDs in any live run are the provider's, not these.** The ten ids
used to shape the runs above are the harness's own, because the real roster is
a provider read and this task makes none. The counts and the campaign list are
real; the identities are not, and the first live run replaces them.

## 8. FOR THE OPERATOR — three decisions, none blocking

1. **`hard_stop_check.py` still uses `>` where this now uses `>=`.** Two
   scripts, one rule, one endpoint, and they disagree at exactly 2.00% and
   nowhere else. Recommended: align `hard_stop_check` to `>=`. One character,
   one file, and it is the conservative direction. Not done here — different
   file, FOCUS RULE.
2. **Neither bounce check has any caller.** No service, timer, monitor or
   module invokes `bounce_stop_7day.py` or `hard_stop_check.py`; both are run
   by hand or not at all. Recommended: before the canary's first batch, run
   `py -3 scripts/bounce_stop_7day.py` by hand and read the last line, and
   treat any non-zero exit as DO NOT SEND. Wiring it into the watcher loop is
   a larger change and is not proposed here.
3. **The window the stop was blind cannot be narrowed from stored state.** 24
   days, with an upper bound of 918 sends and a real number certainly far
   lower. Closing it needs one provider read of `sent_at` across our twenty
   queues — about 205 requests and under a minute, per the census — and that
   is an operator call, not a lane's.

## 9. TREE AND MEASUREMENT HYGIENE

- Every number here was measured in `wt-suppression-2026-10-14` on branch
  `task-suppression-bounce-RULE-2026-10-15` at `2edca33a6`, between
  2026-10-16 00:20 and 01:00 local — 2026-10-15T22:20Z to 23:00Z.
  **The worktree stayed on its branch
  throughout** and `origin/master` was re-checked as `b1f290c84`.
- **No provider call, no network call, no send, no activation, no suppression
  write, and no `config/.env` read.** `src/providers/bison.py` was READ, to
  establish the exception classes the narrow catch names — a repair cannot
  catch narrowly without knowing what it is catching — and nothing under
  `src/` was modified.
- **LINE ENDINGS.** This is a CRLF tree. `scripts/bounce_stop_7day.py` was
  rewritten whole and both it and the new test file were left **LF on disk**
  before being restored to the tree's own convention after commit; the stored
  blob is LF either way, so the committed diff is content-only — 287 insertions,
  39 deletions, with no whole-file ending churn.
- **No full suite was run and none is claimed.** Four modules were run:
  the new file (28/28), `test_the_queue_cap_is_one_number` and
  `test_the_largest_campaign_is_the_one_the_agent_cannot_read` (21/21 together),
  and `test_fixture_hygiene` (5 failures, **all pre-existing** — the new files
  appear nowhere in its output, confirmed by grep). The sibling
  `test_the_producer_reads_forty_pages_and_the_watcher_four_hundred` still
  shows **the same six** born-red names TASK-0130 recorded, because the two
  `src/` cap lines it proposes are still not applied. Per the standing merge
  gate this branch owes a full reference run before anything merges, and this
  commit adds two tracked files, so the owed reference must be measured with
  them present.
- Raw artifacts, local and gitignored, under `work/suppression-measure/0140/`:
  `reproduce.py`, `reproduce_terminal.py`, `mutate.py`,
  `repro-*-UNREPAIRED.txt`, `RED-before.txt`, `RED-again-names.txt`,
  `MUTATIONS.txt`, `MUTATION-REASONS.txt`, and the two byte-exact copies whose
  md5s appear in §5.
