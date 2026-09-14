# TASK-066 - The classifier cannot read three quarters of LinkedIn replies

## THE FINDING, FROM REAL DATA

TASK-058 read 76,315 outbound touches and 5,291 replies from the live
HeyReach estate. Of those replies:

    unknown / unreadable   3,894    73.6%
    negative                 966    18.3%
    positive                 178     3.4%
    not_relevant              97     1.8%
    not_now                   79     1.5%
    out_of_office             36     0.7%
    unsubscribe               29     0.5%
    referral                  12     0.2%

**Every downstream learning rests on the 26% it can read.** The headline
"positive reply rate 0.233%" is really "0.233% survived a classifier that
could not read three quarters of its input", which makes it a floor rather
than a rate, and makes any copy comparison a comparison over a biased sample.

`replies.classify` was built for email. LinkedIn replies are short, lowercase,
often a single clause, frequently without punctuation - "sure", "not for us
right now", "who handles this", "send it over". Email heuristics do not fire
on them.

## GOAL

Materially reduce the unreadable fraction, measured on the same 5,291 replies,
without inventing classifications the text does not support.

## HOW TO WORK IT

1. **Look at the data first.** The dataset is at `%TEMP%/task058_dataset.json`
   and the cache at `%TEMP%/task058_cache/`. If they are gone, re-derive with
   `scripts/task058_heyreach_outcomes.py`. Sample the 3,894 unreadable replies
   and CLASSIFY A HUNDRED BY HAND before touching code. Write down what the
   categories actually are. The answer is in that sample, not in a prompt.

2. Establish how many of the unreadable ones are genuinely ambiguous versus
   simply not matched. Those need different responses: the first is a real
   UNKNOWN and must stay unknown, the second is a missing pattern.

3. Extend `replies.classify` for the patterns the sample shows. Re-measure on
   all 5,291 and report the new distribution beside the old one.

## THE RULE THAT OUTRANKS THE NUMBER

**Do not reduce `unknown` by guessing.** `CLAUDE.md`: "Missing evidence is
never positive evidence", and "no silent fallbacks on a safety path -
classify explicitly and fail closed."

An UNKNOWN reply is treated conservatively downstream: it pauses the account.
A wrong POSITIVE could let automation continue at somebody who said no. So a
pattern that is merely PROBABLE belongs in unknown, and a classifier that
reports 20% unknown by guessing is worse than one reporting 73% honestly.

Report precision on a held-out hand-labelled set, not just the reduction.

## ALSO WORTH KNOWING

`heyreach.direction`, `is_from_correspondent` and `unknown_directions` exist
because telling OUR message from THEIR reply is itself hard. Confirm the
unreadable bucket is not partly a DIRECTION problem before treating it all as
a classification problem. If some of those 3,894 are our own words, that is a
different and more serious defect.

## WHAT YOU MAY NOT DO

- Do not touch `work/queue.jsonl` or `work/campaigns.jsonl`.
- No provider write. Reads and the cached dataset only.
- Do not commit prospect reply text verbatim. Aggregate, or paraphrase a
  handful as illustrations with no name or company attached.

## RESULT BLOCK

STATUS, COMMIT SHA, TESTS, FILES CHANGED, FINDINGS, RISKS, RECOMMENDED
CLAUDE ACTION. FINDINGS must carry the before/after distribution over all
5,291 replies and a precision figure on hand-labelled data.
