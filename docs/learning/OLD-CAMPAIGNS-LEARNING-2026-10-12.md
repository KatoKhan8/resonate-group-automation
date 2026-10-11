# Old campaigns: learning material only

Operator scope ruling, 2026-10-12: campaigns 274/327/328/352 (EmailBison) and the
121 HeyReach campaigns are **learning material and nothing more**. No remediation,
no mailbox repair, no queue reads, no diagnosis. Anything found from now on gets
ONE LINE here and goes nowhere else.

All figures below were measured read-only from the providers on 2026-10-11/12,
each with a positive control proving the check could return non-zero.

## Measured, then closed

- EmailBison estate: 40 campaigns, 250,148 sent, 2,184 bounced (0.87%), 2,317 replied.
- Active at measurement: 327, 328, 352 (operator-internal) and **418**, which earlier
  audits missed. 327+328+352+274 = 210,274 sent, matching the operator's ~209k figure.
- Event feed 2026-10-01..10-11 (733 pages, cursor exhausted): EMAIL_SENT 1,341,
  EMAIL_SEND_FAILED 8,296, ACCOUNT_DISCONNECTED 602, ACCOUNT_RECONNECTED 573,
  WARMUP_DISABLED_CAUSING_BOUNCES 33, EMAIL_BOUNCED 6.
- Disconnects were **zero on 10-01..10-04 then 93/125/110/84/73/58/59 on 10-05..10-11**.
  5 October is the break date. 93 senders had failures, 34 disconnected.
- The provider exposes **no failure reason** on the event feed: `campaign_event`
  carries only {id,type,created_at_local,local_timezone,created_at}.
- HeyReach: 121 campaigns, 10 IN_PROGRESS, 60,857 connection requests, 4,783
  accepted, 632 replies. None RESONATE-prefixed.
- **No evidence of blank content.** The 13 events with an empty subject and body were
  all `MANUAL_EMAIL_SEND_FAILED`, and the control proved it is a payload-shape
  artefact: successful `MANUAL_EMAIL_SENT` events also omit the content keys, while
  automated `EMAIL_SENT` always carries them (subject 32-40 chars, body ~1,200).
- Blank-content scan on the three big queues is **UNKNOWN, not clean**: the full read
  refuses (50,619 / 41,871 / 97,670 rows; 3,375 / 2,792 / 6,512 pages against a
  400-page cap). Bounded samples of 0.74% / 0.90% / 0.38% found zero. Tasked, not fixed.
- Reply feed: 559 inbound. 86 classify as a removal signal on master, 11 more carry
  unmistakable removal language and classify `unknown`. **94 distinct people asked to
  be removed; 4 are suppressed.** Proposal for the other 90 is in
  `work/review/SUPPRESSION-PROPOSAL-2026-10-12.json` (fingerprints only, no plaintext).
- **0 sends after a removal request** across 10-01..10-11 (92 removal leads; the one
  that received mail received it before asking). Lower bound: an 11-day window.
- `work/learning-replies.jsonl` holds 179,715 reply ids, newest 2026-09-22, and carries
  **no reply text and no classification field**. 94 provider replies are absent from it,
  14 since 4 October. Removal signals cannot be rebuilt from local state; the providers
  are the only authority.

## Consequence carried into the sandbox

The sandbox uses synthetic replies with expected verdicts, so none of the above blocks
it. Two things are prerequisites and are being fixed as sandbox work: the inert
ingestion path, and the missing classification field in the reply store schema.
