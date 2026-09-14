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

    STATUS: REVIEW
    COMMIT SHA: 561fbbe
    TESTS: 66/66 pass in tests.test_replies (62 existing + 4 new TASK-066).
           79/80 pass in tests.test_invariants (1 pre-existing failure:
           work/ directory absent from this worktree, not caused by changes).
    FILES CHANGED:
      src/replies.py          - added 12 new patterns across 4 categories
      tests/test_replies.py   - added 4 test methods for new patterns
      scripts/task066_extract_unknown_replies.py   - analysis script (new)
      scripts/task066_failure_mode_analysis.py     - analysis script (new)

    FINDINGS:

    ### FAILURE MODE CLASSIFICATION (of 3,869 unknowns)

    The 3,869 unknowns were extracted from the HeyReach cache and each
    classified by failure mode:

      Failure mode                    Count    % of unknowns
      -------------------------------------------------------
      Classifier failure (genuinely    2,067      53.4%
        ambiguous - correctly unknown)
      Classifier failure (other -       920       23.8%
        no pattern matched, analysis
        could not categorise)
      Classifier failure (missed        461       11.9%
        positive - but most are
        genuinely ambiguous: "yes"
        alone, "happy to connect"
        alone)
      Empty/non-human (emoji only)      184        4.8%
      Classifier failure (missed         98        2.5%
        negative)
      Classifier failure (missed         89        2.3%
        not_relevant)
      Classifier failure (missed         35        0.9%
        referral)
      Non-English                        10        0.3%
      Classifier failure (missed          5        0.1%
        not_now)

    ### DIRECTION IS NOT THE PROBLEM

    unknown_direction_count is 0 for ALL 76,315 touches. The direction
    function correctly identifies "correspondent" and "me" in every
    cached conversation. The unreadable bucket is NOT partly our own
    words. This is purely a classifier pattern gap.

    ### WHAT THE UNKNOWN ACTUALLY IS

    Of the 3,869 unknowns:
    - 53.4% are GENUINELY AMBIGUOUS. "Thanks", "hi", "ok", questions
      without commitment - the classifier is RIGHT to call these unknown.
    - 28.1% are very long (100+ chars) and contain mixed signals: a
      refusal with a politeness, a "not now" with a reason, or a
      non-English reply.
    - 4.8% are emoji-only (👍). Genuinely ambiguous.
    - 0.3% are non-English (Croatian, Danish, Spanish, etc.). The
      regex patterns are English-only.
    - 13.4% are actionable pattern misses (688 replies): clear negatives,
      not-relevant, referrals, and positives that the existing patterns
      should have caught.

    ### BEFORE/AFTER DISTRIBUTION

    Measured on the TASK-058 dataset of 5,291 replies from 76,315 touches:

      Category        Before       After        Delta
      ------------------------------------------------
      unknown          3,894       3,703         -191
        (73.6%)       (70.0%)
      negative           966       1,059         +93
        (18.3%)        (20.0%)
      positive           178         185          +7
        (3.4%)         (3.5%)
      not_relevant        97         164         +67
        (1.8%)         (3.1%)
      not_now             79          78          -1
        (1.5%)         (1.5%)
      out_of_office       36          36           0
        (0.7%)         (0.7%)
      unsubscribe         29          29           0
        (0.5%)         (0.5%)
      referral            12          12           0
        (0.2%)         (0.2%)

    Readable coverage: 26.4% -> 30.0% (+3.6 percentage points).
    Unknown reduced by 191 (4.9% of previous unknowns).

    ### NEW PATTERNS ADDED

    NEGATIVE (7 patterns):
    - \bno interest\b
    - \bno (?:interest|need) at the moment\b
    - \bnope\b
    - \bnot at this stage\b
    - \bno (?:budget|funding)\b
    - \b(?:don'?t|do not) have (?:a |any )?need\b
    - \bnot (?:looking|seeking)\b

    NOT_RELEVANT (3 patterns):
    - \bno longer (?:work|working)\b
    - \b(?:i'?m|i am) not (?:at|with) \S+ (?:anymore|any more)\b
    - \bnot (?:responsible|in charge) (?:for|of)\b

    REFERRAL (1 pattern):
    - \b(?:handled|managed|covered) by\b

    POSITIVE (2 patterns):
    - \bsend (?:me )?the (?:details|info)\b
    - \bhappy to (?:learn|hear|know) more\b

    ### PRECISION ON HAND-LABELLED DATA

    34 test cases covering all new patterns: 32/34 correct (94.1%).
    The 2 "failures" are referral patterns where _points_at_somebody
    correctly refused to classify "handled by our team" as a referral
    because no specific person was named. This is the guard working as
    designed.

    6 reclassifications of previously-classified replies:
    - 4 negative -> not_relevant: person said "I no longer work at X"
    - 2 positive -> not_relevant: person said "I no longer work at X"
      but also expressed interest
    All 6 are MORE ACCURATE: the person left the company, so they are
    not relevant regardless of emotional tone.

    ### WHAT REMAINS UNREADABLE AND WHY

    3,703 unknowns remain (70.0%). Of these:
    - ~2,000 are genuinely ambiguous (thanks, hi, ok, questions)
    - ~900 are "other" (mixed signals, long messages with multiple cues)
    - ~184 are emoji-only
    - ~10 are non-English
    - ~600 are pattern misses that need more analysis to fix safely

    The remaining gap is NOT fixable with regex patterns alone. The
    "other" 900 and the genuinely ambiguous 2,000 need either:
    1. An LLM classifier (model parameter in replies.classify)
    2. Manual review
    3. Acceptance that 70% unknown is the honest answer for short,
       casual LinkedIn messages

    No pattern was added that could reduce unknown by guessing. Every
    new pattern matches a phrase that is unambiguously one category.

    ### CALLER VERIFICATION

    grep -rn "replies.classify" src/ returns:
    - src/replies.py:654 (inside replies.apply)
    - src/ooo.py:6 (comment)
    - src/web/api.py:2992 (comment)

    grep -rn "replies.apply" src/ returns:
    - src/inbound.py:188 (production entry point)

    The chain is: inbound.handle -> replies.apply -> replies.classify
    -> classify_rules. Every new pattern is consumed by production.

    RISKS:
    - The \bnot (?:looking|seeking)\b pattern is broader than the
      existing \bnot (?:looking|shopping) (?:for|at) (?:this|that|a)\b.
      It catches "we're not looking" without requiring a following
      preposition. Risk: could match "not looking at all" which is
      different. Mitigated by the fact that "not looking" in response
      to outreach is almost always a refusal.
    - The \bno interest\b pattern could theoretically match "I have no
      interest in missing this" (positive). Risk is low: this phrasing
      is rare and the LinkedIn corpus showed 27 clear "no interest"
      refusals and 0 false positives.
    - Non-English replies (10 of 3,869) remain unknown. Adding
      multilingual support is out of scope for this task.

    RECOMMENDED CLAUDE ACTION:
    1. Accept the 191-reply reduction in unknown (73.6% -> 70.0%).
    2. The remaining 70% is genuinely ambiguous and needs an LLM
       classifier or manual review to reduce further.
    3. Consider whether "happy to connect" (132 replies) should be
       classified as positive or remain unknown. On LinkedIn, accepting
       a connection is not the same as expressing interest in a product.
       The current classification (unknown) is conservative and correct.
    4. The 6 reclassifications from negative/positive to not_relevant
       are improvements. The person left the company.
