# 487 is queued, the copy renders, and the hypothesis that predicted it is wrong

2026-09-17T15:02:48Z. The `QUEUED` and `TOUCHED` events added to
`bison_watch_loop` four hours earlier fired on their first real test, and what
they caught contradicts the reason they were added.

## What happened

    15:02:48Z   QUEUED 487 scheduled rows 0 -> 10 (none sent)
                TOUCHED 487 updated_at 2026-09-17T10:45:10Z -> 15:02:48Z

Ten rows. One per lead. All step 4742 - the opener - `thread_reply: false`,
sender 2736, status `scheduled`.

## The hypothesis is falsified, and it was mine

`docs/THE-MAILBOX-WAS-NEVER-THE-PROBLEM-2026-09-17.md`, written three hours
before this:

> Between 07:00Z and 07:30Z on 2026-09-18, `bison_watch_loop` should emit
> TOUCHED and then QUEUED for 487. If the window opens and both stay silent,
> the hypothesis is dead.

It did not wait for the window to open. **It fired at 15:02:48Z, two minutes
after the Europe/Zagreb window CLOSED** (17:00 local). The standing
explanation - that this provider assigns a day's leads at or near the window
opening, and 487 missed the assignment by activating at 10:07 local - predicted
the wrong time by sixteen hours and the wrong edge of the day.

Discard it. What is actually supported now is narrower and duller: **the
provider assigns on a cycle, and that cycle ran at the close of the sending
day rather than at its opening.** One observation is not a schedule. The next
two cycles will say whether 15:02Z is the pattern or a coincidence, and
`bison_watch_loop` will catch them without anybody watching.

## The copy renders, and this is the first proof of it

`scheduled_emails` is the only place the RENDERED copy is visible - merge
fields resolved, exactly as a prospect will read it. Checked across all ten
rows:

    unresolved {PLACEHOLDER} tokens    0
    empty subjects                     0
    empty bodies                       0
    greetings with no name             0

    subject lengths   45-50 chars
    body lengths      551-612 chars

One opener, resolved, redacted only as to who it is addressed to:

> **profitability visible on Monday not two weeks late**
>
> \<First\>, I work with Advertising Services teams on profitability visible
> on Monday not two weeks late, and I do not know how \<Company\> handles it …

The first name resolved. The company name resolved, three times, in the body.
The industry resolved. The subject is the opener's own and carries no `Re:`.
`thread_reply` is false on step 1, which is the CONTROL V3 contract.

**Every stage from ingest to rendered provider copy is now proven end to end
for this cohort.** The only thing that has not happened is the send.

## The date, which is the new question

Every one of the ten is scheduled for **2026-09-23**, a Wednesday, six
calendar days and four working days out:

    07:12Z  08:24Z  08:55Z  09:46Z  10:00Z
    11:13Z  12:35Z  12:42Z  13:22Z  14:00Z

In Europe/Zagreb that is 09:12 to 16:00 - **all ten inside the campaign's
09:00-17:00 window**, spread across the day rather than bunched. The provider
is respecting the window it was given.

Why the 23rd and not the 18th is not answered. The candidate worth testing is
the one today's measurement nearly killed, in a sharper form: **not "the
mailbox is full today" but "the mailbox's forward book is full until then".**
Sender 2736 serves four ACTIVE campaigns, one of which holds 21,318 leads, and
487 needs ten slots on a single day from a mailbox capped at fifteen. That is
a claim about the future rather than about today, and today's evidence - 2736
using 2 of 15 - does not touch it.

It is not proven and must not be written down as if it were. There is no route
on this provider that lists a MAILBOX's forward schedule; `scheduled_emails`
is per campaign and the sibling campaigns' queues are too large to walk
(campaign 352 answers `meta.total: 95312`).

## `scheduled_date_local` is wrong and it does not matter yet

Each row carries a `scheduled_date_local` exactly six hours ahead of its
`scheduled_date`. Europe/Zagreb is UTC+2 in September. Six of the ten "local"
times fall outside the campaign's own 09:00-17:00 window, and the UTC times
all fall inside it - so **`scheduled_date` is the field that means something
and `scheduled_date_local` is rendered in a zone nobody chose.** Canary 451's
row carried the two identical.

Nothing here reads `scheduled_date_local`. Recorded so that nothing starts.

## What to do, which is still nothing

**Do not touch 487.** Not a pause, not a re-approval, not a sender change, not
a re-activation. The queue is the first real artefact this campaign has ever
produced and every one of those actions would destroy or re-roll it.

Watch instead. `SCHEDULE-MOVED` was added to `bison_watch_loop` on the
strength of canary 451, whose single row moved once overnight - 13:19Z to
16:24Z on the next day, with nothing staged in between - before firing twenty
seconds late. **A scheduled date on this provider is an intention, not a
commitment**, and the earliest of the ten is now a number worth watching on
its own.

The next honest checkpoint is whether the 23rd holds.
