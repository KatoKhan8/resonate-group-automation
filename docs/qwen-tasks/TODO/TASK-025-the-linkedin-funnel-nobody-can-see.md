# TASK-025 - The LinkedIn funnel, and what is missing to see it

Operator backlog: QWEN-13's analysis half, and items 6 and 7 of the analysis
list - connection request, acceptance, reply.

## GOAL

State exactly which stages of the LinkedIn funnel this system can measure
today, which it cannot, and the cheapest read that would close each gap.

## WHY IT MATTERS - measured 2026-09-14

`/campaign/GetAll` returns `progressStats`, and it is EXECUTION only:
totalUsers, pending, inProgress, finished, failed, excluded, manuallyStopped.
Across 83 campaigns that is 949,536 users.

**Connection acceptance is not in it.** The operator's own hierarchy puts
acceptance below reply and warns against optimising it - but "do not
over-weight it" and "cannot see it at all" are different situations, and
right now it is the second.

Conversations give replies: 697 of 6,000 threads sampled carry an inbound
message, 11.6%.

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

1. Enumerate the funnel: targeted -> request sent -> accepted -> messaged ->
   replied -> positive -> meeting. For EACH stage say SUPPORTED (naming the
   route and field), UNSUPPORTED (naming what was looked for and where), or
   UNDETERMINED (naming the single cheapest live read that would settle it
   and what each possible answer would mean).
2. Do the same for action-type performance: does anything let us compare a
   CONNECTION_REQUEST, a MESSAGE, a VIEW_PROFILE, a FOLLOW and an INMAIL for
   effect? Say so honestly if the answer is no.
3. Quantify the cost of each missing read. A per-lead read across 949,536
   users is not a measurement, it is a bill - say how big.
4. Write a test asserting that a step naming an unproven capability is HELD
   by the planner and not silently dropped. Assert on what the planner
   returns. This overlaps TASK-021 by design; coordinate through Claude
   rather than editing `src/linkedinstate.py` here.

## FILES ALLOWED

`scripts/`, `docs/`, `docs/qwen-tasks/`, `tests/`.

## FILES FORBIDDEN

`src/**`, `work/**`.

## TESTS REQUIRED

Behavioural, on invented fixtures. Zero network.
