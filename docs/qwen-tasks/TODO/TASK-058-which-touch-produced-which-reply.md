# TASK-058 - WORKER C: which exact HeyReach touch produced which reply

## THE QUESTION

We have historical HeyReach activity. Nobody can currently say WHICH MESSAGE
produced WHICH RESPONSE. Until that link exists, every claim about what works
is taste.

## YOU HAVE NO PROVIDER CREDENTIALS. WORK FROM THE EXPORT.

`config/.env` exists only in Claude's worktree, so `heyreach.campaigns`
and every other provider call will fail here. That is the isolation
working, not a problem to solve.

Claude exports the raw historical data to `work/exports/heyreach/` and
that directory is your input. If it is not there yet, say so in FINDINGS
and build the analysis against a small fixture you construct, so the
moment the export lands the script runs unchanged.

## WHAT EXISTS ALREADY - READ BEFORE BUILDING

    src/providers/heyreach.py   `campaigns`, `campaign_leads`,
                                `campaign_stats`, `campaigns_for_lead`,
                                `inbound_messages`, `direction`,
                                `is_from_correspondent`, `unknown_directions`
    src/replies.py              `classify`
    docs/ESTATE-LEARNING-2026-09-14.md   what was already measured

`heyreach.direction` and `is_from_correspondent` exist precisely because
telling OUR message from THEIR reply is the hard part. Use them.

## THE TRAP THAT INVALIDATES THIS WHOLE ANALYSIS

**Do not classify our own quoted copy as the prospect's reply.** A threaded
conversation carries our message inside their reply. An analysis that counts
our own words as their response will report that our copy predicts itself.

`unknown_directions` exists to tell you how much of a conversation cannot be
attributed to a side at all. The last measurement put LinkedIn reply
classification at **64% unreadable**. If your analysis silently treats
unreadable as negative, or drops it, the result is fiction. Report it as its
own bucket, with a count, every time.

## WHAT TO PRODUCE

A dataset, one row per OUTBOUND TOUCH, carrying at minimum:

    campaign, sequence step / message position, touch number
    channel, sender, send time
    the message text that went out
    prospect role / title family, company type, company size where known
    connection outcome (requested / accepted / not accepted / already)
    whether a reply followed, and how long after
    the reply text
    classification, and the CONFIDENCE
    whether the classification was UNREADABLE

Then the analysis on top of it, and the analysis is the deliverable:

    reply rate by message POSITION
    reply rate by touch count reached
    acceptance rate by connection-note shape
    reply rate by message length band
    reply rate by CTA type (question / statement / referral ask / easy out)
    positive-reply rate, separately, and never conflated with reply rate

## SEPARATE THREE THINGS, IN WRITING

    OBSERVATION      what the rows say, with n
    HYPOTHESIS       what it might mean
    PROVEN LEARNING  what survives a sample-size objection

`docs/COPY-EXPERIMENTS.md` already records why the evaluator refuses to call
a winner from four replies against three. Apply the same standard to
yourself. A difference with n=6 is an observation, never a learning.

## OUTPUT

`docs/ESTATE-HEYREACH-OUTCOMES-<date>.md`, plus the script that produced it
under `scripts/`, so the numbers can be re-derived rather than trusted.

Put the raw dataset somewhere reproducible. Do NOT commit unsanitised
prospect PII: names, profile URLs and company names of real people do not
belong in git. Aggregate, or hash the identifier and say so.

## WHAT YOU MAY NOT DO

- No provider WRITE of any kind.
- Do not touch `work/queue.jsonl` or `work/campaigns.jsonl`.
- Do not commit real people's names, emails or LinkedIn URLs.
- Do not call something proven that a sample-size objection would kill.

## RESULT BLOCK

STATUS, COMMIT SHA, TESTS, FILES CHANGED, FINDINGS, RISKS, RECOMMENDED
CLAUDE ACTION. FINDINGS must carry n for every number quoted.
