# The send date is set by the mailbox, not by the campaign

> **SUPERSEDED IN PART, 2026-09-19T11:35Z, by
> `docs/THE-SCHEDULER-PLACES-THE-WHOLE-COHORT-2026-09-19.md`.** The central
> finding stands and is stronger: the send date is a property of the mailbox.
> But the RULE stated below - "the first day its mailbox had a free slot" -
> is REFUTED by the completed walk. Sender 3437 had two free slots on the
> 22nd and one on the 23rd and 489 still went to the 24th. The rule is the
> first sending day with room for the WHOLE COHORT, which predicts both
> campaigns exactly. The 489 section below also expects the 22nd on stale
> numbers; read the correction instead.

Read 2026-09-19T09:30Z. **It is Saturday.** Both email campaigns are Mon-Fri,
so nothing is due from either today and a zero today is the clock, not a fault.

## The falsifier from yesterday resolved, and the inference held

`docs/489-WAS-NOT-PLANNED-2026-09-18.md` ended with a cheap test: watch 21:00Z,
because 489's window closes then and the hypothesis was that the provider plans
a campaign at window CLOSE. The test has now run.

    489  updated_at  2026-09-18T21:03:56Z     window closes 21:00Z   +3m56s
    487  updated_at  2026-09-18T16:03:54Z     window closes 15:00Z   +63m

489 was planned three minutes and fifty-six seconds after its window closed,
and it now holds five scheduled rows where it held none. **Planning at window
close is confirmed for 489 and was already observed for 487** (planned at
15:02:48Z on the 17th, two minutes after that window closed).

Both stamps land at :03 past an hour, which suggests an hourly planning tick
rather than a per-campaign timer. 487's is 63 minutes after its own close
rather than 3, so the tick does not pick every campaign up at the first
opportunity. **The tick is OBSERVED. The rule that selects which campaigns a
tick plans is UNKNOWN and I am not asserting one.**

## But window-close is the wrong answer to the question that matters

Planning-at-close explains WHEN the rows were written. It does not explain
WHICH DAY they were written for, and that is the number anyone cares about:

    487   10 rows   all 2026-09-23   08:41-14:32Z = 10:41-16:32 Europe/Zagreb
    489    5 rows   all 2026-09-24   13:05-16:44Z = 09:05-12:44 America/New_York

Both sit correctly inside their own windows. Both are days away. The previous
handoff treated the 23rd as a property of campaign 487. **It is not a property
of the campaign at all. It is a property of the mailbox.**

## WHY_23_SEPTEMBER = PROVEN, and it is capacity

From the complete forward-book walk in `work/forward-book-census.json`
(campaigns 327, 328 and 352 all `complete: true`, 183,229 rows), attributed per
campaign per sender per day. Sender 2736 carries 487, daily limit 15:

    sender 2736      09-21 Mon   09-22 Tue   09-23 Wed
      campaign 327      15           0           0
      campaign 328       0          15           0
      campaign 487       0           0          10
      ------------------------------------------------
      total            15/15       15/15       10/15
                       FULL        FULL        first free day

**Monday is full. Tuesday is full. Wednesday is the first day sender 2736 has
a single free slot, and that is exactly where all ten of 487's openers went.**
Both of the days that block it are filled by the client's own campaigns.

That is not an inference from one data point. It is a complete walk of every
scheduled row in every active campaign, and the ten rows sitting on the 23rd
are 487's own.

## 489 is the same mechanism, one step weaker

    sender 3437      09-19   09-20   09-21   09-22   09-23
      campaign 352      14      14      15       4       0

By the same rule 489 should have landed on the 22nd, where the walk saw eleven
free slots. It landed on the 24th.

**The walk is dated 2026-09-17 and 489 was planned on the 18th at 21:03Z.** The
client's campaign 352 holds 95,726 rows and inserts more every sending day, so
3437's 22nd and 23rd had a full day to fill between the measurement and the
planning. That fits, and nothing else observed contradicts it, but the
measurement that would prove it did not exist at the time.

    487 lands on the first day its mailbox has a free slot     PROVEN
    489 lands on the first day its mailbox has a free slot     INFERRED
    the client's book grew between the walk and the planning   INFERRED
    a fresh complete walk would settle it                      the test

A fresh census over 327, 328, 352, 487 and 489 was started at 09:28Z on the
19th and is the test. **If it shows 3437 full on the 22nd and 23rd, 489 is
proven by the same rule as 487.** If it shows those days free, the rule is
wrong for 489 and the question reopens.

## What this changes

**No campaign-side change moves these dates.** Not the window, not the
activation, not the approval, not the cap, not the sequence. The rows are
placed where the mailbox has room, and both of our mailboxes are shared with
a client whose three campaigns hold 183,239 scheduled rows between them.

This is the same finding as
`docs/THE-ESTATE-IS-SATURATED-NOT-UNAPPROVED-2026-09-18.md`, one layer down.
That document proved the client's outreach blocks our cohort at the ACCOUNT
gate. This proves it also throttles the cohorts that got through, at the
MAILBOX. Expansion is a sourcing problem; latency is a sender problem.

**It is systemic, not a property of these two campaigns.** Every future cohort
attached to a shared mailbox will queue behind the client's book the same way,
and the queue gets longer as the client's campaigns grow.

## The defect this exposes in how a sender is chosen

Sender 3437 was chosen for 489 on `senderinventory.health_of()`, which checks
connected and warming. Yesterday's handoff already recorded that this missed a
2.11% lifetime bounce rate that `readiness()` calls DEGRADED.

It misses something else, and this one decides the send date:

**Nothing in sender selection reads the forward book.** `health_of()` cannot
tell a mailbox with fifteen free slots tomorrow from one booked solid for three
days, because it never looks. The census that can answer it exists, is complete,
and no selection path calls it.

So the selector optimises for deliverability and is blind to latency, which is
why a cohort approved on the 18th sends on the 24th. That is the next
engineering item and it is a real one: `bison_forward_book_census.py` already
computes the input.

## What must NOT be done about it

**Do not re-sender 487 or 489 to chase an earlier date.** Both hold real
approved people, both are correctly configured, both will send. Detaching a
sender from a live campaign to save three days is a mutation against live
state to buy a number, and the previous session declined the same trade for
the same reason.

The three mailboxes with a genuinely empty forward book - 3941, 3930, 3919 -
are empty because they have **never sent an email**, which this system's own
vocabulary calls DEGRADED. An empty book is not the same as free capacity.

The fix is a sender allocator that reads the book before it picks, applied to
the NEXT cohort. Not a swap on this one.

## Numbers, as read

    487_STATUS       active   10 leads   0 sent   sender 2736   queue 0/10
    487_NEXT_SEND    2026-09-23   first row 08:41Z
    489_STATUS       active    5 leads   0 sent   sender 3437   queue 0/5
    489_NEXT_SEND    2026-09-24   first row 13:05Z
    REAL_EMAIL_SENDS 0 since canary 451 on 2026-09-14
    TODAY            Saturday. Both campaigns Mon-Fri. Nothing is due.
