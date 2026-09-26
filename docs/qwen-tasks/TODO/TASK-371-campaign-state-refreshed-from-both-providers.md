PRIORITY: P0
SIZE: M
DEPENDS:

# TASK-371 — campaign state, refreshed from both providers, fully paginated

The evening handoff's first section opens by admitting it is not true:

> **No provider read was made today.** The figures below are from the
> 2026-09-26 morning handoff, and `docs/state/PROVIDER-CAMPAIGNS.json` was
> generated 2026-09-23T10:02Z — three days stale.

`scripts/provider_truth.py` was run on 2026-09-26 at 16:09Z, so **the HeyReach
half is now current**. The EmailBison half is not: that script never asks
EmailBison anything. It reads `bison_campaign_id` out of our own records and
reports it as an internal claim. So the line every handoff opens with —

    493   ACTIVE, the only campaign sending, 22 leads / 22 sent
    491 492 494 496 503 504 505   paused
    495   archived
    497 498   completed

— is **our belief about EmailBison, not EmailBison's answer**. §26: provider
truth wins, and unreadable provider state is `UNKNOWN`, never clean or zero.

## Build

    scripts/provider_truth.py    MODIFY — add the EmailBison half
    tests/test_provider_truth_refuses_a_partial_read.py   NEW

`src/providers/bison.py` has `campaign(campaign_id)` (`:1606`) and
`campaign_lead_count(campaign_id)`, which already reads `meta.total` rather
than counting a page — that fix exists because a fifteen-row page was once
mistaken for a whole campaign. Follow it.

`sender_emails()` (`src/providers/bison.py:130`) is the pagination pattern this
repo has already got right: read `meta` **first**, walk every page, and refuse
to return a partial answer. Reuse that shape; do not invent a second one.

The output must carry, per campaign and per provider:

- the provider's own id, name and status, as the provider returned them;
- the lead count from `meta.total`, never from a page length;
- `UNKNOWN` — a distinct value, not null, not zero — for anything unreadable,
  with the reason;
- the INTERNAL vs PROVIDER comparison the script already does for HeyReach, so
  a drifted claim shows up as a defect rather than as agreement;
- `generated_at`, and the **named set** of campaign ids seen.

## Acceptance — RUN each, paste real output

1. `py -3 scripts/provider_truth.py` completes and `docs/state/PROVIDER-CAMPAIGNS.json`
   carries a fresh `generated_at` **and both providers**. Paste the EmailBison
   block for 491-505.

2. **Named sets, not counts.** Print the sorted set of EmailBison campaign ids
   the provider returned and diff it against the set the handoff asserts
   (`{491,492,493,494,495,496,497,498,503,504,505}`). Report ids present at the
   provider and absent from our belief, and ids we believe in that the provider
   does not return — **by id**. A count that matches is not a set that matches.

3. **The pagination guard is seen to fail.** Force a truncated page (stub the
   transport to return page 1 of N and stop) and assert the script **refuses**
   rather than reporting the short answer. Paste the refusal. Then restore and
   re-run. Without this, acceptance 1 proves only that an endpoint answered.

4. **`UNKNOWN` is not zero.** Stub one campaign's read to fail and assert its
   status is `UNKNOWN` with a reason, and that nothing downstream reads it as
   clean, paused or empty.

5. Say in one line, from the provider's answer and not from our records,
   **which campaigns are sending right now** and how many leads each holds.

6. Full suite: wait for `work/suite_verdict.txt`, diff the failing-name SET
   against `docs/state/SUITE-BASELINE-2026-09-26.txt`.

## What this task may NOT do

- **READ ONLY.** `scripts/provider_truth.py` performs no writes and must stay
  that way — that is the whole point of a report you can trust to be free of
  side effects. No POST, PATCH, PUT or DELETE to either provider, by any route.
- **Nothing is sent, activated, resumed, paused, enrolled or attached.** 493 is
  ACTIVE and sending and is not touched, not even to "confirm" it. Production
  freeze: `docs/OPERATOR-PRODUCTION-FREEZE-2026-09-26.md`.
- Do not write a credential, a token, an address or an unhashed prospect
  identifier into the tracked output. The existing `short_hash` convention
  stands.
- Do not "correct" our internal records to match the provider in this task.
  Report the divergence; changing it is a separate decision.
