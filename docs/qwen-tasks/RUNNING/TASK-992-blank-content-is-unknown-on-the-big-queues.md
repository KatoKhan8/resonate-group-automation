# TASK-992 — blank-content is UNKNOWN on the only campaigns that send

STAGE: TODO
PRIORITY: P1

## Measured 2026-10-12

The blank-content control (`emptyrender.scan` over `bison.scheduled_emails`)
**cannot read the three largest active campaigns.** The read refuses rather than
truncating, which is the right failure, but the result is UNKNOWN and UNKNOWN is
never clean:

    campaign 327   50,619 rows   3,375 pages
    campaign 328   41,871 rows   2,792 pages
    campaign 352   97,670 rows   6,512 pages
    cap               400 pages   (bison.CAMPAIGN_QUEUE_PAGE_CAP)

Bounded samples covered 0.74% / 0.90% / 0.38% and found zero blanks. The
detector is **proven capable of firing** — it flagged campaign 481's empty
subject in the same run — so the zero is a real sample result. A sample under 1%
clears nothing.

Campaign 418 WAS fully read (94 rows) and is clean.

## Why this matters less than it looks, and still matters

274/327/328/352 are operator-declared internal campaigns, never written to, so
this control could not pause them anyway. But the question asked was whether
anything is sending malformed content, and for the three campaigns actually
sending, the honest answer is "not measurable with the current reader".

## Acceptance

- Either a reader that can answer the question for a 6,512-page queue, or a
  stated bounded-sampling contract that reports its own denominator and is never
  permitted to read as a clean bill.
- The refusal stays. A prefix returned as though it were the whole queue is the
  precise failure this cap exists to prevent.
