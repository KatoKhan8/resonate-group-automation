# TASK-059 - WORKER D: the same question for EmailBison

## THE QUESTION

Which email produced which reply, across the historical EmailBison estate.

This is TASK-058's twin and the two must NOT share an implementation until
Claude has seen both - the providers report different things and a premature
abstraction will hide whichever one is worse.

## YOU NOW HAVE PROVIDER CREDENTIALS. READS ONLY.

As of 2026-09-14 `config/.env` is present in this worktree, so the provider
modules work here. Read whatever the analysis needs.

**READS ONLY, AND THIS IS ABSOLUTE.** You hold real EmailBison and HeyReach
keys. No write, no send, no campaign mutation, no lead added, no sequence
replaced. If a function name contains `set_`, `create_`, `add_`, `update_`,
`resume_`, `pause_` or `stop_`, you are not calling it.

Provider reads cost nothing here but they are rate limited. Cache what you
pull to a local file and re-read the cache rather than the API while you
iterate on the analysis.

## WHAT EXISTS ALREADY

    src/providers/bison.py   `fetch_replies`, `classify_reply_row`,
                             `events_contract`, `membership`,
                             `scheduled_emails`, `campaign_lead_ids`
    src/replies.py           `classify`
    src/inbound.py           how a reply becomes state

`bison.classify_reply_row` already exists. Establish what it does before
writing a second classifier beside it.

## THE TRAPS, AND EMAIL HAS THREE

1. **Our own quoted email inside their reply.** An email reply usually
   contains the entire original underneath it. Counting that as their words
   is the defect that makes copy predict itself. Email reply classification
   was last measured at **46.5% unreadable** - report that bucket.

2. **Auto-replies are not replies.** Out-of-office, bounce notifications and
   provider-flagged automated responses must be separated. TASK-020 and
   TASK-030 both exist because an out-of-office was treated as a human
   answer. `verdict["is_automated"]` carries the provider's own flag.

3. **`opened` may not mean anything.** Campaign 451 has
   `open_tracking: False`, so its zero opens are an absent measurement
   rather than an absent open. CHECK THE FLAG PER CAMPAIGN before using
   opens in any rate, and exclude campaigns that do not track them rather
   than averaging a zero into the numerator.

## WHAT TO PRODUCE

One row per SENT EMAIL:

    campaign, sequence step, step order, touch number
    sender, send time, subject, body
    recipient role family, company type, size where known
    delivered / bounced / opened-if-tracked / replied
    time to reply
    reply text, classification, confidence, is_automated, UNREADABLE flag

And the analysis:

    reply rate by step position (does step 5 still earn its place?)
    reply rate by sequence LENGTH - the estate claims 8-step sequences
      reply at 8.49% against every other shape, n=17,690. Re-derive it.
      If it does not reproduce, that is the most valuable finding available.
    reply rate by subject shape and by body length band
    positive-reply rate separately
    bounce rate by domain type

## SEPARATE OBSERVATION / HYPOTHESIS / PROVEN LEARNING, with n on everything.

## OUTPUT

`docs/ESTATE-BISON-OUTCOMES-<date>.md` plus the script under `scripts/`.
No unsanitised prospect PII in git.

## WHAT YOU MAY NOT DO

- No provider WRITE. Reads only.
- Do not touch `work/queue.jsonl` or `work/campaigns.jsonl`.
- Do not commit real names, emails or domains of real people.

## RESULT BLOCK

STATUS, COMMIT SHA, TESTS, FILES CHANGED, FINDINGS, RISKS, RECOMMENDED
CLAUDE ACTION.

---

## RECOVERY NOTE, 2026-09-15 after unplanned shutdown

The run COMPLETED. It wrote `docs/ESTATE-BISON-OUTCOMES-2026-09-15.md` at
01:26 and the laptop shut down before the worker committed. Recovered
verbatim from the `resonate-qwen-4` worktree and committed to branch
`qwen-worker-4` at `f164f8c`. **The collection was NOT re-run.**

STATUS: COMPLETE, NOT INTEGRATED. The report contradicts itself in four
places - "matched" counts 8792 rows that did not match, an empty body reports
0.0% unreadable against a previous 46.5%, 1561 of 1570 positives come from
rows with no body at all, and 16.14% positive cannot be reconciled with the
0.3-0.4% reply rates measured in BISON-CADENCE-FINDINGS.

TASK-090 carries the rework. Do not re-run the collection.
