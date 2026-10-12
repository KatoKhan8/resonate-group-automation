# The inert ingestion path, reproduced through the real entry point

Measured by me on `task-sandbox-phase2-horizon` (which carries **no** ingestion
fix), 2026-10-12. This is a reproduction, not a citation: the figures below come
from a run I executed, against a tree with the defect still in it.

The operator's requirement was explicit — `replaysim.simulate()` alone does not
prove that the watcher/consumer calls ingestion, that a verdict is stored, or
that an unattributed reply is safely retained. So this drives the real poller
with a **provider-shaped** synthetic row.

## Method

- Wire sealed with `sandboxharness.seal_wire(allow=())`, and
  `assert_wire_sealed()` fired first as the positive control.
- Store relocated with `store.use_directory(tmp)`; clock injected with
  `sandboxclock.install`.
- `bison.fetch_replies` and `poller.IDENTIFY["emailbison"]` replaced with fake
  adapters. **No old provider replies were read and no live campaign was
  touched.** The synthetic row carries the full real `/replies` shape — all 30
  fields including `folder: inbox`, `type: reply`, `text_body`, `campaign_id`,
  `lead_id`, `scheduled_email_id` — with `.invalid` addresses throughout.
- `poller.run("emailbison", live=True, fetch=..., identify=..., recs=[])`.

## Result

    poller.run ->  events: 1    the reply WAS read off the feed
                   unmatched: 1 it could not be attributed to a record
                   applied: 0   so new_replies_ingested would report 0
                   pages: 1     duplicates: 0
                   outcomes: 1  status None

    fake adapter calls   fetch=1  identify=1
    real wire calls      1  -- see the note below

    Q1 does a reply store path exist on this tree?
       NO - store.reply_store_path is absent. There is nowhere to persist to.
    Q2 rows persisted by this poll:  0
    Q3 unattributed reply retained anywhere:  False

    production work/ UNCHANGED - asserted

**So: a reply arrives, is read off the feed, cannot be attributed, and is
silently dropped — while the watcher reports `new_replies_ingested: 0` with
`healthy: true`.** That is the whole defect, and it is now reproduced rather
than inferred from a status file.

### The one wire call, stated precisely so it is not read as a breach

`real wire calls: 1` is **the `assert_wire_sealed` control call I fired myself**
before any work, and the counter correctly includes it. The poller made **zero**
real calls: both its external boundaries were faked. A seal that has never
stopped anything is not a seal, so the probe is deliberate and its appearance in
the count is the evidence that the counter works.

## Why this matters for the sandbox specifically

The sandbox must measure reply handling over a long horizon. On this tree it
cannot, because an unattributed synthetic reply would vanish and the harness
would see a healthy zero — indistinguishable from "no replies arrived". Any
sandbox result about reply handling taken on this tree would be a measurement
of the harness.

This is also the reason the fix cannot be worked around by injecting replies
past ingestion: the thing being tested is precisely the step that drops them.

## Status of the fix

`task-reply-ingestion-2026-10-12` addresses it and was **REFUSED by adversarial
review** (see `docs/glm-reviews/branch-TASK-997-...`): the historical walk's
`_append` has no dedup, so losing the walk's state file would re-store the whole
history. Back in rework. **Nothing is merged, and no ingestion result is
presented as confirmed.**

Related: TASK-997 (the review task), TASK-991 (the corpus holds no text).

---

## Addendum: the duplicate mode is not hypothetical. It already happened.

Adversarial review refused the first fix because the historical walk's `_append`
had no dedup, so losing the walk's state file would re-store the whole history.
I measured the live file and it was clean, which did not refute the finding -
a clean file is what a latent mode looks like before it fires.

It had already fired. Measured by me, 2026-10-12:

| file | lines | distinct reply_ids | duplication | rows seen more than once |
|---|---:|---:|---:|---:|
| `work/learning-replies.jsonl` | 179,715 | 179,715 | **1.00x** | 0 |
| `work/learning-replies.jsonl.dupbak.2026-09-22` | 34,125 | 17,700 | **1.93x** | **16,425** |

The backup's own filename is `dupbak`. Somebody took it on 22 September because
the store had nearly doubled, and 16,425 replies were present more than once.
The live file is clean because that state was recovered from, not because the
mode cannot occur.

So the refusal named a real mode, the fix is necessary rather than defensive,
and the evidence was sitting in the same directory the whole time. Two writers
against one append-only file, with only one of them deduplicating, is how it
happens.

Also corrected in passing: the "32,025 rows in a 16,650-row file" figure that
could not be reconciled with 179,715 was a **pre-existing docstring** in
`acquire_lock`, and it was wrong about the backup too - the real counts are
34,125 and 17,700.
