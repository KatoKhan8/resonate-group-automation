# TASK-027 - How many Productive accounts could be campaign-ready

Operator backlog: QWEN-17, QWEN-19, and item 11 of the analysis list.

## GOAL

A reproducible report of the campaign-ready funnel, and a ranked list of what
each blocked account is blocked ON.

## WHY IT MATTERS - measured 2026-09-14

    productive domains                       300
    icp_pass*                                113
    + a verified sendable contact             54
    + a usable company name                   45
    contacts with 5 approved email steps      20
      EMAIL-READY                              8
    contacts with li1-li5 approved + URL      13
      LINKEDIN-READY                           9

Forty-five accounts qualify and eight have copy that passes. The gap is
entirely generation and regeneration, and the operator wants as large a clean
inventory as possible waiting behind the live gate.

What nobody can currently answer is WHICH accounts are one step from ready and
which are five - so there is no way to spend a generation run well.

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

1. A script under `scripts/` that computes the funnel above from
   `work/queue.jsonl` and prints it. It must agree with those numbers or
   explain why not.
2. Per blocked account, the SPECIFIC blocker, ranked by how close it is:
   no contact / contact not verified / no usable company name / missing N
   email steps / missing N LinkedIn steps / a step fails repetition / a step
   fails claims / collision-blocked by the client's estate.
3. A "next best generation run" list: the accounts where one generation pass
   would produce the most newly-ready accounts. This is the deliverable the
   operator will actually use.
4. Do not change any gate to make the number look better. A looser gate
   yielding 40 ready accounts is worth less than a true 8.

## FILES ALLOWED

`scripts/`, `docs/`, `docs/qwen-tasks/`, `tests/`.

## FILES FORBIDDEN

`src/**`. `work/**` is READ-ONLY - read `work/queue.jsonl`, never write it. A
second process writing the estate is how a run loses its own work, and it has
happened here.

## TESTS REQUIRED

Tests on an invented estate with known answers for every funnel stage and
every blocker category.
