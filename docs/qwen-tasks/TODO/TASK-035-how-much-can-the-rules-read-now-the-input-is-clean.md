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
