# TASK-024 - Correlate campaign shape with outcome, at scale

Operator backlog: QWEN-04, QWEN-05, QWEN-10, and items 1, 2 and 10 of the
analysis list.

## GOAL

Take `docs/ESTATE-LEARNING-2026-09-14.md` from a hand-read of aggregates to a
reproducible analysis, and say which of its four hypotheses the data can
actually support.

## WHY IT MATTERS

That document found reply rate by sequence length is NOT monotonic - 0.85% at
one step, 8.49% at eight, 2.38% at forty-four - and that the best performers
share five properties our own campaign has none of. It was read by hand from
22 campaign rows. Every conclusion in it is therefore one person's reading,
and the operator's instruction is explicit: separate OBSERVATION, HYPOTHESIS,
EXPERIMENT, EVIDENCE and PROMOTION, and do not rewrite production strategy on
a small sample.

## WHERE THE DATA IS

Claude holds the provider credentials; this worktree has none, by design and
structurally - `config/.env` does not exist here. So the provider reads are
already done and the results are on disk OUTSIDE any repository:

    C:\Users\Zvonimir\Desktop\resonate-analysis\

    replies_email.jsonl      sanitised inbound email replies
    replies_linkedin.jsonl   sanitised inbound LinkedIn messages
    bison_campaigns.json     22 EmailBison campaigns with outcome counters
    hr_campaigns.json        83 HeyReach campaigns with progressStats

The reply bodies are SANITISED: emails, URLs, phone numbers and every personal
and company name this system knows are replaced with placeholders. They are
still real client correspondence. **Read them, never copy them.** No body, no
fragment of a body, and no name may enter this repository - not into a
fixture, not into a docstring, not into a commit message. Invent every example
you need. `tests/test_fixture_hygiene` is failing today because that rule was
broken before.

Do NOT attempt a provider call. There are no credentials here, and a task that
tries to get some has misunderstood its job.


## SCOPE

1. A script under `scripts/` that reads the files named above and reproduces
   every table in `ESTATE-LEARNING-2026-09-14.md`. If a number disagrees with
   the document, THE DOCUMENT IS WRONG and you say so in FINDINGS.
2. Extend it: reply rate by sequence length, by number of subject variants,
   by whether step 2 threads with `Re:`, by whether a referral step exists, by
   wait pattern, by geography, by campaign age.
3. For each, report the SAMPLE SIZE and what is confounded with what. The
   April-22 rebuild changed copy, length and variant count together; any
   statement that does not acknowledge that is wrong however the arithmetic
   comes out.
4. Rank the four hypotheses H1-H4 by how much support the data gives them,
   and say plainly which cannot be separated from each other at all.

## WHAT YOU MAY NOT CONCLUDE

That a correlation is a cause. That a difference between two campaigns is
about the one property you happened to compare. That connection acceptance or
open rate means anything here - opens are switched off estate-wide and
acceptance is not in the payload at all.

## FILES ALLOWED

`scripts/`, `docs/`, `docs/qwen-tasks/`, `tests/`.

## FILES FORBIDDEN

All of `src/**` and `work/**`. This task changes no product code.

## TESTS REQUIRED

The analysis script needs tests on INVENTED rows with known answers - a
grouping that silently drops a campaign is how a table lies. Assert the
arithmetic, not the estate.
