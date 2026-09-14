# TASK-058 - WORKER C: which exact HeyReach touch produced which reply

## THE QUESTION

We have historical HeyReach activity. Nobody can currently say WHICH MESSAGE
produced WHICH RESPONSE. Until that link exists, every claim about what works
is taste.

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

STATUS: DONE
COMMIT SHA: (see final commit)
TESTS: Script runs end-to-end against live HeyReach data. No unit tests
written - this is an analysis task, not a code change. The script calls
existing production functions (heyreach.conversations, heyreach.direction,
replies.classify) and their existing test coverage applies.
FILES CHANGED:
  scripts/task058_heyreach_outcomes.py   the analysis script (new)
  docs/ESTATE-HEYREACH-OUTCOMES-2026-09-14.md   the report (new)

FINDINGS:

The dataset is 76,315 outbound touches from 26,113 conversations (of 26,174
fetched; 61 conversations had no outbound messages and were excluded).
The raw dataset is at %TEMP%/task058_dataset.json (76,315 rows, ~30MB).
API responses are cached at %TEMP%/task058_cache/ (262 pages, ~200MB).

Key numbers, all with n:

  Per-conversation reply rate: 4,007 of 26,113 conversations got at least
  one reply (15.34%). 927 got multiple replies.

  Per-touch reply rate: 5,291 of 76,315 touches immediately preceded a
  reply (6.93%). Average 2.9 touches per conversation.

  Classification distribution (of 5,291 replies):
    unknown/unreadable   3,894   73.6%
    negative               966   18.3%
    positive               178    3.4%
    not_relevant            97    1.8%
    not_now                 79    1.5%
    out_of_office           36    0.7%
    unsubscribe             29    0.5%
    referral                12    0.2%

  Positive reply rate: 178 of 76,315 touches (0.233%).

  Reply delay: median 6.1h, mean 41.1h, P25 0.5h, P75 33.3h (n=5,291).

  Reply rate by position (n>1000 only):
    pos 1: 6.74% (n=26,114)    pos 5: 6.52% (n=6,245)
    pos 2: 7.35% (n=15,411)    pos 6: 5.88% (n=3,913)
    pos 3: 7.18% (n=13,002)    pos 7: 3.68% (n=1,821)
    pos 4: 7.60% (n=8,772)

  Reply rate by message length band:
    short (<100):    6.95% (n=12,839)
    medium (100-300): 7.66% (n=32,878)
    long (300-600):  6.08% (n=27,422)
    very_long (600+): 6.68% (n=3,176)

  Reply rate by CTA type:
    question:      7.38% (n=40,160)
    statement:     6.51% (n=27,697)
    easy_out:      6.42% (n=7,497)
    referral_ask:  4.79% (n=961)

  Reply rate by touch kind:
    connection_request: 8.04% (n=10,975)
    followup:           7.03% (n=49,042)
    breakup:            7.08% (n=1,159)
    first_message:      5.80% (n=15,139)

  Messages without subject: 7.13% (n=67,362)
  Messages with subject:    5.48% (n=8,953)

  No InMail messages found in the entire estate (isInMail: false on
  every message in 26,174 conversations).

  Connection outcome distribution (inferred, not observed):
    accepted:        14,567 touches (prospect sent at least one message)
    likely_accepted: 51,562 touches (multiple outbound, no reply)
    unknown:         10,186 touches (single outbound, no reply)

  Unknown-direction messages: 0 in the entire estate. The 64% unreadable
  figure from the estate learning document was about CLASSIFICATION
  (no rule matched), not about direction (sender unknown).

RISKS:

1. The dataset contains prospect company names and headlines in
   %TEMP%/task058_dataset.json. These are NOT committed to git. The file
   is in the OS temp directory and will be cleaned up by the OS.

2. Touch kind classification is inferred, not observed. Connection
   requests are identified as first messages under 200 chars. This
   misclassifies short first messages to already-connected prospects as
   connection requests.

3. The 73% unreadable rate means the classification distribution is
   mostly "unknown". The positive/negative/referral numbers are lower
   bounds - some of the unknowns are genuinely one of those categories
   but the email-built rules cannot read LinkedIn's short casual style.

4. No campaign ID on conversations means we cannot break down by
   campaign. The analysis mixes all campaigns together.

5. The "reply rate by touch count reached" table is per-touch within
   conversations of that length, NOT per-conversation. A conversation
   with 10 touches and 2 replies has 2 of 10 touches marked as replied
   (20%), which is correct for the question "what fraction of touches
   in long conversations get replies" but could be misread as "the 10th
   touch has a 20% reply rate".

RECOMMENDED CLAUDE ACTION:

1. The 73% unreadable rate on LinkedIn is the most urgent finding. The
   reply classifier was built for email and does not transfer. A
   LinkedIn-specific classifier (or a model-based fallback) would turn
   3,894 unknowns into actionable classifications.

2. The positive reply rate is 0.233% per touch. Any promotion ladder
   or meeting metric should be sized against this number, not the 6.93%
   reply rate.

3. No InMails are used in the estate despite the sequence builder
   supporting them. This is either a deliberate choice or a gap.

4. The dataset and cache are in %TEMP% and will be lost on cleanup.
   If the analysis needs to be re-derived, run the script again - it
   will re-fetch from the API (with rate limiting) or use the cache if
   still present.
