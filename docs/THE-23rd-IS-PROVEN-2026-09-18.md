# Why 487 sends on the 23rd. Walked, not sampled.

Measured 2026-09-18 with `scripts/bison_forward_book_census.py`, which walks
`/campaigns/{id}/scheduled-emails` by CURSOR rather than by offset page.
Read-only GETs. No PII below: sender ids and dates only.

## The answer

Sender 2736's forward book, from a **COMPLETE** walk of campaign 327 (48,759
rows, 3,251 pages) plus campaign 487 (10 rows):

    2026-09-17    15 of 15      campaign 327
    2026-09-18    15 of 15      campaign 327     <- FULL
    2026-09-19                  Saturday, not a sending day
    2026-09-20                  Sunday, not a sending day
    2026-09-21    15 of 15      campaign 327
    2026-09-22    15 of 15      campaign 328
    2026-09-23    10 of 15      campaign 487 - its own ten openers

**487's ten openers are queued for 2026-09-23 because mailbox 2736 is booked
to its daily limit of 15 on every sending day until then, and the 23rd is the
first day with room.**

`STATUS = OBSERVED`, and now provable rather than inferred.

## Why this is stronger than the table it replaces

`PRODUCTION-HANDOFF-2026-09-17.md` reached the same conclusion from a
9,000-row SAMPLE of queues holding ~180,000 rows, and its own tooling warns
that sample size is load-bearing - at 3,600 rows sender 2911 read ZERO free on
the 18th, and a swap onto it looked safe until a bigger sample read 15.

Sampling can only ever **undercount** a mailbox's commitments. That asymmetry
is what makes the two halves of that table different in kind:

    a count that REACHES the limit    SOUND. Undercounting cannot invent a
                                      full mailbox.
    a ZERO                            UNPROVEN. "Not seen yet" and "not
                                      there" are indistinguishable.

So the sampled "2736 is full on the 18th" was always sound. The sampled
"every mailbox is free on the 23rd" never was. This walk settles the first
one absolutely: **campaign 327 ALONE fills 2736 to its limit on the 18th,
21st and the 17th**, before campaign 328 or 352 have been counted at all.
328 and 352 can only add to those numbers.

## What was needed to walk it at all

`bison.scheduled_emails` refuses these queues - `PartialInventory: 3251 /
2583 / 6382 pages to walk` - because offset pagination is refused with 422
beyond roughly 500 pages, and it correctly raises rather than answering with
its first page.

Grok reported a documented second mode, and it was **verified against this
estate** on 2026-09-17: `pagination_type=cursor` answers 200, returns
`meta.next_cursor`, and the row ids genuinely advance. `per_page` stays 15 in
cursor mode, so this is not cheaper - roughly 12,000 requests and two hours
for the three active client campaigns - only possible.

## What this rules out

- **Swapping 487 onto another of that human's inboxes does not help.** They
  are booked on the same days; this was the 2911 recommendation, already
  withdrawn.
- **Pausing and resuming 487 to re-run the scheduler does not help.** The
  documented scheduler behaviour would re-plan against the same full mailbox
  and land on the same day, and a probe already paused this campaign once and
  could not restart it.
- **Nothing about the step delay.** Canary 451 carried the identical
  `wait_in_days: 3` and its first `scheduled_date` was the same day it was
  created.

## What it leaves open

The walk of 328 and 352 was still running when this was written. It cannot
change the conclusion - it can only raise counts that have already reached the
limit - but it will answer a second question the sample could not: **which
mailboxes across the whole estate genuinely have room on a given day.** The
script refuses to report that while any walk is incomplete, because an unseen
row and an absent row look identical, and that confusion is precisely what
produced the withdrawn 2911 recommendation.
