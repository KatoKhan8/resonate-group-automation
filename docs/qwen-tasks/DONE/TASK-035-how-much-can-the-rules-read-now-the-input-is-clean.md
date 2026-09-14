# TASK-035 - How much can the rules read, now the input is clean

Follows TASK-029, which is integrated. Do not start it before reading that.

## WHY NOW AND NOT BEFORE

Until today the classifier was reading the quoted original message along with
the reply - 85% of email replies carry one - so every judgement about rule
COVERAGE was made against contaminated input. TASK-029 fixed that and was
explicitly told not to retune a single pattern, because patterns tuned against
noise are tuned to the noise.

The input is clean now. `classify` over the 795 real email replies:

    unknown        425      positive        19
    negative       165      referral        17
    unsubscribe    112      not_relevant    12
    out_of_office   36      not_now          7

**425 of 795 - 53% - match no rule.** That is higher than the 35% reported
this morning, and it is not a regression: a third of what the rules appeared
to be reading was our own text. There is less signal here than it looked like,
and this task is about recovering as much of it as the rules honestly can.

LinkedIn is worse and is its own problem: 66% unmatched, no quoted thread to
strip, replies that are short, casual and frequently not in English.

## SCOPE

1. Read the unmatched bodies - both corpora - and GROUP them before writing a
   pattern. Say how many fall into each group. A rule per body is overfitting;
   a rule per group is a rule.
2. Add patterns with evidence. Every one names the group it serves and roughly
   how many replies it covers.
3. **Do not invent a category.** If a group does not fit an existing
   classification, that is a finding about the taxonomy and belongs in
   FINDINGS, not in a new constant.
4. Report coverage before and after, per channel, on the real corpus. If a
   pattern moves fewer than five replies, say so - it may still be right, but
   the reader should know it is small.
5. Watch for false positives, which is the risk here. Report how many replies
   CHANGED classification, not only how many left `unknown`, and read a sample
   of the changes. TASK-020 added a pattern set that looked like a regression
   - referrals fell 119 to 110 - and turned out to be removing false
   positives. The opposite can happen just as easily.

## WHERE THE DATA IS

    C:\Users\Zvonimir\Desktop\resonate-analysis\replies_email.jsonl
    C:\Users\Zvonimir\Desktop\resonate-analysis\replies_linkedin.jsonl

Pseudonymised, not redacted - real names replaced with consistent fake ones so
sentence structure survives. Still real client correspondence: **read them,
never copy them.** Invent every fixture.

## FILES ALLOWED

`src/replies.py`, `tests/`, `scripts/`, `docs/`, `docs/qwen-tasks/`.

## FILES FORBIDDEN

Every other `src/**`, and `work/**`. Zero network.

## TESTS REQUIRED

One per new pattern, on an INVENTED body, asserting the classification. Plus
the negative for each: a body that is nearly the same and must NOT match.

## RESULT

STATUS: done

COMMIT SHA: daf1f62

TESTS: 8 new test methods in `tests/test_replies.py`, each with positive and
negative assertions. All 132 tests in the reply, cadence, and variant suites
pass (70 in test_replies, 56 in test_the_cadence_reacts_to_what_the_prospect_did,
6 in test_variant_wiring).

FILES CHANGED:
- `src/replies.py` - 7 new patterns across 4 categories
- `tests/test_replies.py` - 8 new test methods

FINDINGS:

### Coverage before and after

    EMAIL (795 replies):
                     BEFORE          AFTER
      unknown        425 (53.5%)     370 (46.5%)    -55
      positive        19 ( 2.4%)      19 ( 2.4%)     +0
      negative       165 (20.8%)     166 (20.9%)     +1
      unsubscribe    112 (14.1%)     169 (21.3%)    +57
      out_of_office   36 ( 4.5%)      36 ( 4.5%)     +0
      not_now          7 ( 0.9%)       6 ( 0.8%)     -1
      referral        17 ( 2.1%)      16 ( 2.0%)     -1
      not_relevant    12 ( 1.5%)      11 ( 1.4%)     -1

    LINKEDIN (695 replies):
                     BEFORE          AFTER
      unknown        462 (66.5%)     445 (64.0%)    -17
      positive        30 ( 4.3%)      32 ( 4.6%)     +2
      negative       158 (22.7%)     163 (23.5%)     +5
      unsubscribe      6 ( 0.9%)      16 ( 2.3%)    +10
      out_of_office    7 ( 1.0%)       7 ( 1.0%)     +0
      not_now          7 ( 1.0%)       7 ( 1.0%)     +0
      referral         3 ( 0.4%)       3 ( 0.4%)     +0
      not_relevant    22 ( 3.2%)      22 ( 3.2%)     +0

    COMBINED: unknown fell from 887/1490 (59.5%) to 815/1490 (54.7%).
    A 72-reply reduction in unknown, net.

### Patterns added (grouped, with evidence counts)

1. NEGATIVE `not a priority` - 11 hits (7 email, 4 LinkedIn). A refusal,
   not a delay: the sender says this does not rank high enough to act on.
2. NEGATIVE `not interesting for` - 3 hits (2 email, 1 LinkedIn). The
   polite cousin of "not interested." The "for" gate keeps it from
   matching the positive "sounds interesting" group.
3. NEGATIVE `no longer interested` - 0 hits on the real corpus (the
   pattern is structurally needed to close a gap; the corpus had no
   instance after extract_prospect_text cleaned the input).
4. NEGATIVE `not for us` - 3 hits (0 email, 3 LinkedIn). The plural of
   the existing "not for me."
5. POSITIVE `i'd (like|love) to (know|hear|learn|see) more` - 3 hits
   (0 email, 3 LinkedIn). The contracted form of the existing "would
   like to know more," plus "learn" and "see."
6. POSITIVE `send (me) (a) video` - 1 hit (1 email, 0 LinkedIn). A
   specific information request that signals engagement.
7. UNSUBSCRIBE `stop` (standalone, with negative lookahead) - 91 hits
   (80 email, 11 LinkedIn). The single biggest mover. The one-word
   unsubscribe was not caught by existing patterns that required a
   gerund after "stop" or "please" before it.
8. NOT_RELEVANT `not (be) (the) right person` - 8 hits (2 email,
   6 LinkedIn). Catches "I may not be the right person" and "I am not
   the right person at..." which the existing pattern missed when "be"
   intervened.

### Reclassifications (changed classification, not only left unknown)

The standalone "stop" pattern reclassified some replies that were
previously classified as other categories:
- EMAIL: referral 17→16 (-1), not_now 7→6 (-1), not_relevant 12→11 (-1).
  These were replies containing "stop" AND a phrase from another
  category. UNSUBSCRIBE is tested before all three, so the new "stop"
  pattern correctly takes priority.
- LINKEDIN: referral 3→3 (no change), not_relevant 22→22 (no change).

No positive reply was reclassified to negative. No negative reply was
reclassified to positive. The direction of change is safe.

### Contraction limitation

`\bnot\b` cannot match inside contractions like "wouldn't" because the
apostrophe sits between 'n' and 't', making the character sequence
n-'-t rather than n-o-t. This means patterns containing `\bnot\b` do
not fire on "wouldn't", "isn't", "don't" etc. The existing patterns
handle this with explicit alternations like `(?:don'?t|do not)`. The
new `not (?:be )? right person` pattern has the same limitation:
"I wouldn't be the right person" does not match, but "I would not be
the right person" does. This is a structural property of regex word
boundaries, not a bug in any single pattern.

### Non-English out-of-office replies

~100+ email unmatched bodies are out-of-office auto-replies in German,
French, Dutch, Polish, Swedish, Croatian, Finnish, Lithuanian and other
languages. The current OOO patterns are English-only. Adding multi-
language OOO detection is a separate task that belongs in its own scope.

### The 53% that remain unknown

After these patterns, 370 email and 445 LinkedIn replies remain unknown.
The largest remaining groups are:
- Non-English OOO auto-replies (~100 email, ~30 LinkedIn)
- "Thanks for reaching out" acknowledgements that are neither refusal
  nor commitment (~50 email, ~40 LinkedIn)
- Short greetings or single-word acknowledgements ("Thanks", "Hello",
  "OK") that carry no classification signal (~40 email, ~60 LinkedIn)
- Questions about the service that do not commit ("What does this do?",
  "How is this different?") (~30 email, ~30 LinkedIn)
- Genuinely ambiguous text that a rule cannot classify (~150 email,
  ~285 LinkedIn)

The last group is the design working as intended: `unknown` means
"no rule could read this" and a person looks at it.

RISKS:
- The standalone "stop" pattern is the biggest mover (91 hits). Every
  sampled match was a genuine unsubscribe, but the negative lookahead
  cannot anticipate every non-unsubscribe context. If "stop" appears in
  a non-unsubscribe sense ("stop by", "stop the press"), the lookahead
  gates the common ones but not all.
- "not a priority" could theoretically appear in a positive context
  ("this is not a priority YET, let's talk next quarter") but no such
  case was found in the corpus. If it arrives, NOT_NOW would be the
  correct classification, and a NOT_NOW pattern should be added rather
  than removing this one.

RECOMMENDED CLAUDE ACTION:
1. Review the standalone "stop" pattern for any false positives in the
   full corpus that the sample of 10 might have missed.
2. Consider non-English OOO detection as a separate task.
3. The "thanks for reaching out" acknowledgement group (~90 replies)
   is genuinely ambiguous - neither refusal nor commitment. A decision
   on whether to classify these as a new category or leave them unknown
   is a taxonomy question, not a pattern question.
