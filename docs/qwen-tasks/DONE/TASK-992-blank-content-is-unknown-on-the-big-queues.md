# TASK-992 — blank-content is UNKNOWN on the only campaigns that send

STAGE: DONE
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

---

## RESULT BLOCK

STATUS: DONE
ARTIFACT KIND: code + test

COMMIT: 16f0adbd9

FILES CHANGED:
- src/providers/bison.py: added `scheduled_emails_sample(campaign_id, max_pages=None)` and `SCHEDULED_EMAILS_SAMPLE_PAGES = 10`
- src/emptyrender.py: `scan(rows, total=None)` now carries `sampled: True`, `sampled_count`, `total` when `len(rows) < total`
- scripts/bison_watch_loop.py: watcher falls back to sampling when full read refuses; halt logic refuses to act on sampled scan; alert carries coverage info
- tests/test_blank_content_bounded_sample.py: 9 new tests

TESTS:
- 9 new tests in test_blank_content_bounded_sample.py: all pass
- 30 existing tests in test_a_blank_email_can_never_be_sent_again.py: all pass (backward compatibility verified)

FINDINGS:

The bounded-sampling contract is implemented and tested. The four properties:

1. `bison.scheduled_emails_sample(campaign_id, max_pages=None)` reads up to `max_pages` pages (default SCHEDULED_EMAILS_SAMPLE_PAGES = 10, so 150 rows) and returns `(rows, total)` where `total` is the provider's `meta.total`. It does NOT raise `PartialInventory` - it is honest about being a sample.

2. `emptyrender.scan(rows, total=N)` includes `sampled: True` plus `sampled_count` and `total` when `len(rows) < total`. A full read (`len(rows) == total`) does NOT carry `sampled`. A scan without `total` is unchanged (backward compatible with bisonfactory.py:2699 and check_readback.py:320).

3. The halt logic (`_halt_on_blank_content`) refuses to act on a sampled scan. When `blanks["sampled"]` is truthy, the pause is skipped, the alert fires with `sampled=yes` and coverage info, and the log says "BLANK-CONTENT-SAMPLED ... NOT halting, coverage insufficient to act".

4. The watcher falls back to sampling when the full read refuses (`PartialInventory`), and reports coverage: "QUEUE-SAMPLE 352: 150 of 97670 rows (0.2%)". If the sample itself fails, the queue is UNKNOWN (unchanged behavior).

The refusal stays: `CAMPAIGN_QUEUE_PAGE_CAP = 400` is unchanged, and `scheduled_emails` still raises `PartialInventory` past the cap. The sample is a separate function with a separate contract.

A sampled scan NEVER clears: it carries `sampled: True`, the halt logic refuses to act, and the alert says "sampled scan - halt refused". A sample that found nothing in 150 of 97,670 rows reports exactly that, not "no blanks found".

WIRING VERIFIED:
- `scheduled_emails_sample` is consumed by `scripts/bison_watch_loop.py:159` (fallback from PartialInventory)
- `emptyrender.scan(queue, total=queue_total)` is called at `scripts/bison_watch_loop.py:192`
- Other callers of `emptyrender.scan` (bisonfactory.py:2699, check_readback.py:320) remain backward compatible - they call without `total`

RISKS:
- The sample covers only 0.15% of the largest queue. A blank in the unsampled 99.85% is invisible. This is the honest answer: the task said "a sample under 1% clears nothing", and the contract enforces that.
- The sample adds 10 API calls per cycle per campaign that exceeds the cap. Three campaigns × 10 pages = 30 extra calls per 3-minute cycle, which is negligible.
- The halt refuses on a sampled scan even if blanks are found in the sample. This is deliberate: pausing a campaign for a fault that may not exist in the unsampled portion is the false positive the incident was about. The alert fires, the operator sees it, and they can investigate by hand.

RECOMMENDED CLAUDE ACTION:
- Review the bounded-sampling contract and confirm the halt refusal is the right call.
- Consider whether the sample size (10 pages = 150 rows) is the right default, or whether it should be configurable.
- The task file can move to DONE after review.
