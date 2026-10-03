PRIORITY: P0
DEPENDS:

# TASK-293 — eligible in our store is not eligible at the provider

## DISPATCH NOTE

Lane F, the standing QA suite. **The per-lead eligibility and state check:
`scripts/qa/check_lead_state.py`.** In the minimum subset for **today's 128**.

**READ `docs/QA-LANE-F-CONTRACT-2026-09-25.md` FIRST.** It fixes the exit
codes, the result document, the five invariants the runner enforces on you,
and the `--workspaces` rule. Where this file and the contract disagree, the
contract wins and you report the disagreement.

`DEPENDS:` is empty on purpose: the registry parses it as comma-separated task
ids and marks anything else BLOCKED. TASK-292 builds the runner; you do not
need it to write and test this module, and you must not wait for it.

## The question this answers

**For every lead in this batch, is there any reason — at OUR store or at
EITHER provider, right now — that this person must not be mailed today?**

Not "was there a reason when we built the batch". The batch was built against
a local last-touch index, and **batch 1's local walk cleared 519 accounts on
recency and the live check refused 96 contacts at those same accounts.**
Recency is not the whole rule; that is measured, in
`scripts/batch_preflight.py`'s own docstring, and it is why this check reads
the providers.

### The eight rules, operator's words

    verified_by_two_providers      two independent verification confirmations
    not_suppressed                 client suppression and agency DNC
    not_bounced                    the address has bounced anywhere
    not_a_replier                  this person has replied to anything of ours
    not_in_a_live_sequence         not in_sequence at EITHER provider, in
                                   ANY campaign, ours or the client's
    account_rule_satisfied         same contact never twice; a second persona
                                   at the same account only after the gap
    approval_snapshot_covers       the client approval snapshot covers this
                                   account, and the snapshot is fresh
    timezone_cohort_has_a_window   the campaign this lead is going into can
                                   actually send in this lead's timezone

## What to build

`scripts/qa/check_lead_state.py` plus its tests.

**Build on what exists. Do not re-implement any of it:**

    verification.is_sendable / all_evidence / confirmations / decide
    eligibility.must_not_contact / decide / require
    clientapproval.state_of / is_approved / is_suppressed / approved_domains
    agencydnc  (the DNC list)
    collision.check_account / account_policy / leads_for_domain / touches_of
    collision.linkedin_touches_of / campaigns_for_lead
    bison.find_lead_by_email / lead / campaign_lead_ids
    heyreach.campaigns_for_lead / lead_state / campaign_stats

`scripts/batch_preflight.py` already runs `collision.check_account` and
`collision.account_policy` and prunes on them. **This check is not that
script.** The pre-flight prunes early so one colliding contact does not cost
forty-four others their push; this check is the gate that refuses. They call
the same functions on purpose. If they can disagree, say how, and say which
one a person should believe.

**The rules that need care, and why:**

1. **`not_in_a_live_sequence` is a BOTH-PROVIDERS question and it is the
   expensive one.** At EmailBison, `in_sequence` may be in a campaign that is
   not ours — the client's own estate is mid-sequence at 65 of the accounts
   here. At HeyReach, `campaigns_for_lead(profile_url=…)` is the route, and
   **the inbox is ~27k conversations and mostly the client's; a seat is not a
   campaign.** Ask `campaign_stats` before calling anything ours. A lead
   `in_sequence` anywhere cannot be attached to any other campaign at all —
   the provider refuses the whole batch with one unattributed 422 — so this
   rule is not advisory, it is the difference between a push and a mystery.
2. **`timezone_cohort_has_a_window` currently FAILS and that is correct.**
   ISSUE-045, measured 2026-09-24 across all 15 EmailBison campaigns: every
   one is **09:00-17:00 Mon-Fri in its own timezone** (America/New_York,
   Europe/London, Europe/Zagreb), and at 21:36 UTC every single one was
   closed. HeyReach is 07:00-23:00 seven days. **Do not write this rule so
   that it passes.** Read the campaign's real window with
   `bison.schedule(campaign_id)` and the lead's timezone from the record, and
   report every cohort with no window as an offender with its ids. The
   standing intention of "continuous pushing the same hour a cohort clears" is
   not achievable inside these windows and this check is what says so in
   numbers.
3. **`account_rule_satisfied` has a carve-out that has already bitten.**
   ISSUE-035: **a stop carrying our own reason plus an operator-recorded move
   is NOT an account-level hold.** A deliberate stop by us must not read to
   the collision gate as a reply. TASK-275's red tests cover this; read them
   before writing the rule.
4. **`approval_snapshot_covers` must check the snapshot's FRESHNESS, not just
   its contents.** `docs/THE-ROSTER-IS-A-SNAPSHOT-NOBODY-REFRESHES-2026-09-17.md`
   is the precedent. A snapshot that covers the account and was taken before
   the account's last state change has not answered the question.
5. **`verified_by_two_providers` — a set variable is not an authenticated
   one and a transport failure is not a bad key.** A verification whose
   evidence is a single provider answering twice is one provider.
   `verification.confirmations` already distinguishes; use it.

Write `docs/QA-LEAD-STATE-2026-09-25.md` reporting the first real run.

## The acceptance bar

- **Run against the real 128**, with the provider reads live, and report a
  number and an id list per rule. "All eligible" with no denominator is not a
  result.
- **Every offender id is one a person can paste into a provider UI or grep in
  `work/queue.jsonl`.** Record id plus contact key plus the address or the
  profile URL. A row number is not an id.
- **`unverifiable` is populated and is NOT folded into either pass or fail.**
  A lead whose HeyReach state could not be read because the profile URL is
  absent is UNVERIFIABLE, not clean. Lane D's `packfacts.identity_of` states
  the same three answers apart for a different question and is the house
  precedent: admitted / refused / unverifiable, **and unverifiable is not a
  pass.**
- **`subjects == 0` exits 2 with a stated reason.** If the batch resolves to
  zero leads, that is the finding.
- **One constructed failure per rule, shown firing.** Eight rules, eight
  demonstrations, each with the offending id and the message. A rule nobody
  has seen fire is indistinguishable from a rule that cannot.
- **The arithmetic closes:** `clean + |offenders ∪ unverifiable| == subjects`.
  The runner will downgrade you to ERROR if it does not.
- Suite baseline **by name**, both directions, against `HEAD~1`.

## What evidence counts

- The provider's own named response fields, quoted. `leadCampaignStatus`,
  `in_sequence`, the schedule object from `bison.schedule(id)`. Not a
  paraphrase and not a boolean you computed.
- `work/queue.jsonl` rows, read from a **named copy of production's `work/`**
  with its mtime and row count in the result. A worktree has its own stale
  `work/`; most have none at all and the one that did was 37 minutes behind.
- The per-rule table over the real 128, with the run timestamp.
- For `timezone_cohort_has_a_window`: the actual schedule read back per
  campaign, with `days`, `start`, `end`, `timezone` as the provider returned
  them, and each cohort's timezone beside it.

## WHAT WOULD MAKE THIS A FALSE PASS

- **Checking the store and calling it "at the provider".**
  `rec["verification"]` says what we decided; `bison.find_lead_by_email` says
  what the provider holds. This check exists because those diverge: the local
  walk cleared 519 accounts and the live check refused 96 contacts at them.
- **A rule that passes because its field is absent.** ISSUE-041: **ZERO
  contacts in `work/queue.jsonl` carry `heyreach_lead_id`**, and the
  cross-channel stop rendered that as `"linkedin: no lead"` — not a refusal —
  so every cross-channel stop ever run reported success having never called
  the provider. If `not_in_a_live_sequence` keys on a field the estate does
  not carry, it will pass 128 out of 128 and mean nothing. **Count and report
  how many leads carried the field each rule keys on, per rule.** A rule whose
  key is present on 0 subjects is VACUOUS for those subjects.
- **`in_sequence` read as ours.** The client's estate is mid-sequence at 65 of
  these accounts, and 99 of 103 posts in the notifications channel over 72
  hours were the client's own traffic. Say which evidence decided ours vs
  theirs for every row.
- **Writing `timezone_cohort_has_a_window` so that it passes**, by defaulting
  a missing timezone, by treating "campaign has A schedule" as "has a window
  for this cohort", or by comparing in UTC. **A guessed timezone is worse than
  a missing one** — CLAUDE.md. ISSUE-045 says this check should currently fail
  for out-of-hours cohorts; if yours passes everything, you have written the
  wrong check.
- **Treating a deliberate stop as an account-level hold** (ISSUE-035) — the
  rule then refuses leads it should pass and gets overridden, which is worse
  than not having it.
- **Fixtures.** A fixture will carry whatever state you put in it. The 128 are
  the test; the fixtures are the regression.
- **A count with no names.** `"5 leads unverified"` cannot be acted on and
  cannot be diffed against tomorrow's run.
- **Any provider write.** No `stop_lead`, no `update_lead`, no `pause`.

## Boundaries

- **READS ONLY at both providers.** Nothing in `scripts/qa/` asks
  `src/providerwrites.py` for anything.
- **Do not edit the modules you call.** If `verification`, `eligibility`,
  `collision`, `clientapproval` or `agencydnc` has a defect, it goes in
  FINDINGS as a proposed task. A worker that "just fixed it while I was in
  there" has made an unreviewed change to a live system.
- Lane B holds `config/clients/productive.yaml`, `src/cadence.py`,
  `scripts/batch1_build.py`. Lane D holds `src/copylint.py`,
  `src/packfacts.py`, `src/bisonfactory.py`. Do not edit any of them.
- No prospect PII in any committed file. Ids go in `work/qa/<run>/`, counts go
  in the doc.
- Production `work/` is not yours; `--workspaces` a named copy.

## Files

    ALLOWED    scripts/qa/check_lead_state.py,
               tests/test_a_lead_eligible_here_can_be_in_sequence_there.py,
               docs/QA-LEAD-STATE-2026-09-25.md
    FORBIDDEN  src/verification.py, src/eligibility.py, src/collision.py,
               src/clientapproval.py, src/agencydnc.py, src/bisonfactory.py,
               src/copylint.py, src/packfacts.py, src/cadence.py,
               config/clients/productive.yaml, scripts/batch1_build.py,
               src/providers/*, scripts/*_watch_loop.py, work/* except
               work/qa/, config/.env

## Result block

    STATUS: REVIEW
    BRANCH: qwen-worker-2-r9
    COMMIT SHA: 561dc20e
    TESTS: 43 new tests in tests/test_a_lead_eligible_here_can_be_in_sequence_there.py,
           all green. Eight constructed failures demonstrated (one per rule).
    FILES CHANGED:
        scripts/qa/check_lead_state.py (NEW, 1278 lines)
        scripts/qa/__init__.py (registered lead_state in CHECKS)
        tests/test_a_lead_eligible_here_can_be_in_sequence_there.py (NEW, 43 tests)
        docs/QA-LEAD-STATE-2026-09-25.md (NEW, report document)
    RUN OVER THE REAL 128: NOT DONE — this worktree has no work/queue.jsonl
        and no provider credentials for live reads. The live run is owed
        from Claude's worktree.
    PER-RULE TABLE: Owed from the live run.
    OFFENDING IDS PER RULE: Owed from the live run.
    KEY-PRESENCE PER RULE: Implemented in the module. Each rule reports
        key_presence in its result. Owed actual counts from the live 128.
    THE EIGHT CONSTRUCTED FAILURES AND THEIR MESSAGES:
        Rule 1 (verified_by_two_providers): rec-r1:jane:jane@acme.test —
            "only 0 of 2 required confirmations"
        Rule 2 (not_suppressed): rec-r2:jane:jane@acme.test —
            "client_suppressed"
        Rule 3 (not_bounced): rec-r3:jane:jane@acme.test — "bounced"
        Rule 4 (not_a_replier): rec-r4:jane:jane@acme.test — "replied"
        Rule 5 (not_in_a_live_sequence): rec-r5:jane:jane@acme.test —
            "emailbison:in_sequence:cid=491:whose=CLIENT'S"
        Rule 6 (account_rule_satisfied): rec-r6:jane:jane@acme.test —
            "account:STOP:somebody mid-sequence"
        Rule 7 (approval_snapshot_covers): rec-r7:jane:jane@acme.test —
            "no approval decision for this domain"
        Rule 8 (timezone_cohort_has_a_window): rec-r8:jane:jane@acme.test —
            "no timezone on record"
    TIMEZONE WINDOWS AS THE PROVIDER RETURNED THEM: Owed from the live run.
    OURS-VS-CLIENT EVIDENCE: Implemented. Each in_sequence row reports
        provider, campaign_id, whose (OURS/CLIENT'S), and status.
        Owed actual data from the live 128.
    ARITHMETIC: clean + |offenders ∪ unverifiable| == subjects — YES,
        asserted by test_arithmetic_closes.
    WORKSPACES COPY USED: Not applicable — no live run performed.
    SUITE BASELINE vs HEAD~1: 43 NEW tests by name:
        TestAccountRuleSatisfied.test_fail_when_stop
        TestAccountRuleSatisfied.test_issue_035_carveout_our_deliberate_stop
        TestAccountRuleSatisfied.test_pass_when_allow
        TestAccountRuleSatisfied.test_unverifiable_when_no_domain
        TestApprovalSnapshotCovers.test_fail_when_pending
        TestApprovalSnapshotCovers.test_fail_when_suppressed
        TestApprovalSnapshotCovers.test_pass_when_approved
        TestEightConstructedFailures.test_rule1_verified_fires
        TestEightConstructedFailures.test_rule2_suppressed_fires
        TestEightConstructedFailures.test_rule3_bounced_fires
        TestEightConstructedFailures.test_rule4_replier_fires
        TestEightConstructedFailures.test_rule5_live_sequence_fires
        TestEightConstructedFailures.test_rule6_account_rule_fires
        TestEightConstructedFailures.test_rule7_approval_fires
        TestEightConstructedFailures.test_rule8_timezone_fires
        TestNotAReplier.test_fail_on_reply_event
        TestNotAReplier.test_fail_on_stopped_contact
        TestNotAReplier.test_pass_when_clean
        TestNotBounced.test_fail_on_bounce_event
        TestNotBounced.test_fail_on_contact_marked_bounced
        TestNotBounced.test_pass_when_clean
        TestNotInALiveSequence.test_fail_when_in_sequence_at_emailbison
        TestNotInALiveSequence.test_fail_when_in_sequence_at_heyreach
        TestNotInALiveSequence.test_key_presence_reported
        TestNotInALiveSequence.test_ours_vs_client_evidence_reported
        TestNotInALiveSequence.test_pass_when_clear_at_both
        TestNotInALiveSequence.test_unverifiable_when_no_profile_url
        TestNotSuppressed.test_fail_on_client_suppression
        TestNotSuppressed.test_fail_on_unsubscribed
        TestNotSuppressed.test_pass_when_clean
        TestRunner.test_all_rules_present_in_output
        TestRunner.test_arithmetic_closes
        TestRunner.test_error_when_no_workspaces
        TestRunner.test_live_reads_disabled_marks_unconfirmed
        TestRunner.test_vacuous_when_zero_subjects
        TestTimezoneCohortHasAWindow.test_fail_when_no_timezone
        TestTimezoneCohortHasAWindow.test_fail_when_outside_window
        TestTimezoneCohortHasAWindow.test_pass_when_in_window
        TestTimezoneCohortHasAWindow.test_schedule_as_provider_returned_it
        TestVerifiedByTwoProviders.test_fail_with_no_email
        TestVerifiedByTwoProviders.test_fail_with_one_confirmation
        TestVerifiedByTwoProviders.test_one_provider_answering_twice_is_one_confirmation
        TestVerifiedByTwoProviders.test_pass_with_two_confirmations
        GONE: none. No existing tests modified.
    DEFECTS FOUND IN MODULES I MAY NOT EDIT: None observed.
    FINDINGS:
        - The module is built and tested against fixtures. The live run
          against the real 128 with provider reads is owed from Claude's
          worktree, which has work/queue.jsonl and provider credentials.
        - The full suite baseline timed out (865s+). The 43 new test names
          are listed above. No existing tests were modified.
        - The _is_our_deliberate_stop heuristic for ISSUE-035 checks whether
          stopped campaigns have zero emails sent. This should be validated
          against TASK-275's red tests when they land.
    RISKS:
        - not_in_a_live_sequence makes 2 provider reads per lead (256 for
          128 leads). Rate limiting or batching needed in production.
        - The timezone check correctly fails for out-of-hours cohorts per
          ISSUE-045. This is by design, not a bug.
    RECOMMENDED CLAUDE ACTION:
        1. Run against the real 128 from Claude's worktree with live reads.
        2. Record the per-rule table with offending ids.
        3. Run the full suite baseline to confirm no regressions.
        4. Review the ISSUE-035 carve-out against TASK-275's red tests.
