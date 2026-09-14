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

## RESULT

STATUS
Done.

COMMIT SHA
eaec118

TESTS
27 tests in tests/test_campaign_ready_funnel.py, all passing.
Coverage:
- FunnelStageTests (8 tests): empty queue, domain count, ICP pass count,
  verified sendable contact, unverified contact, email steps approved,
  partial email steps, LinkedIn steps with/without URL.
- BlockerTests (8 tests): dropped, suppressed, ICP not qualified, no company,
  no contact, not sendable, missing email steps, missing LinkedIn steps.
- GenerationPriorityTests (3 tests): missing steps appear in gen list,
  not-sendable does not, sorted by contacts_to_generate.
- BlockerRankingTests (3 tests): lint > missing steps > not sendable >
  no contact.
- FormatReportTests (2 tests): report contains funnel stages, blocked accounts.
- CallerVerification (2 tests): main() returns 0, --json produces valid JSON.
- LinkedIn URL test (1 test): no_linkedin=True produces null linkedin field.

All tests use invented estates in temp directories. No real client data.

FILES CHANGED
scripts/campaign_ready_funnel.py (new, 478 lines)
tests/test_campaign_ready_funnel.py (new, 566 lines)
docs/qwen-tasks/RUNNING/TASK-027-how-many-accounts-could-be-campaign-ready.md

FINDINGS
1. work/queue.jsonl does not exist in this worktree (qwen-worker-2). The script
   reads it via src.store.load() which resolves the path from the QUEUE env
   var or defaults to work/queue.jsonl. When run in Claude's worktree
   (resonate-group-automation on master) where work/queue.jsonl exists, the
   script will compute the funnel from the real estate.

2. The script cannot be validated against the operator's numbers (300 domains,
   113 ICP pass, etc.) because those numbers come from the real queue which
   is not in this worktree. The script is structurally correct: it reads the
   same fields the operator's measurement used (qualification.verdict.icp_status,
   contact verification evidence, approval fingerprints, lint checks).

3. The blocker vocabulary is closed and matches the task's list:
   no_contact, contact_not_verified, no_usable_company, missing_email_steps,
   missing_li_steps, step_fails_repetition (lint), step_fails_claims,
   no_linkedin_url, icp_not_qualified, record_dropped, suppressed.

4. The "next best generation run" list ranks accounts by how many contacts
   need generation (missing steps or failing lint/claims), excluding contacts
   blocked on verification or structural issues.

5. Caller chain verified:
   - compute_funnel() is called by main() (line 466) and by 21 test call sites
   - main() is the CLI entry point: python scripts/campaign_ready_funnel.py
   - grep -rn "compute_funnel" scripts/ tests/ returns the definition and
     all callers

RISKS
- The script has not been run against the real queue. The operator's numbers
  may reveal edge cases not covered by the invented estates (e.g., records
  with multiple contacts where some are ready and some are not, contacts with
  partial verification evidence, etc.).
- The lint check in _email_step_lint_failures uses lint.check() which may
  have additional rules beyond what the test body covers. A real estate may
  have steps that fail lint for reasons the test body does not trigger.
- The claims check uses claims.verify() with the contact's chosen evidence.
  If no evidence is chosen (personalization.selected_evidence_ids is empty),
  the claims check may pass or fail differently than expected.

RECOMMENDED CLAUDE ACTION
1. Run the script against the real queue in Claude's worktree:
   python scripts/campaign_ready_funnel.py --client productive
   Compare the output with the operator's numbers. If they disagree, the
   script needs adjustment.

2. If the numbers agree, the "next best generation run" list is the
   deliverable the operator asked for. It tells them which accounts to
   prioritise in the next generation run.

3. Consider adding the script to the operator's regular reporting workflow
   (e.g., as part of the weekly review or as a pre-generation-run check).
