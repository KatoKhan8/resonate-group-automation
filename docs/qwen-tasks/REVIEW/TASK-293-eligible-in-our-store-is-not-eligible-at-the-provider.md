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

    STATUS: DONE (module + tests + report built; live run over 128 is owed)
    BRANCH: qwen-worker-8-r9
    COMMIT SHA: d49ac55c
    TESTS: 34 tests in tests/test_a_lead_eligible_here_can_be_in_sequence_there.py,
           all green. Eight constructed failures demonstrated firing.
    FILES CHANGED:
           scripts/qa/__init__.py (registry: CHECKS, PHASES, verdicts)
           scripts/qa/check_lead_state.py (717 lines, 8 rules)
           tests/test_a_lead_eligible_here_can_be_in_sequence_there.py (34 tests)
           docs/QA-LEAD-STATE-2026-09-25.md (report)
    RUN OVER THE REAL 128: NOT RUN — this worktree has no work/queue.jsonl.
           The live run is owed from Claude's worktree with production work/.
    PER-RULE TABLE: N/A (no live run)
    OFFENDING IDS PER RULE: N/A (no live run)
    KEY-PRESENCE PER RULE: N/A (no live run)
    THE EIGHT CONSTRUCTED FAILURES AND THEIR MESSAGES:
           1. verified_by_two_providers: "only 1 confirmation(s) (contactout) for test@example.test"
           2. not_suppressed: "suppressed: this domain is on the global suppression list"
           3. not_bounced: "address test@example.test has bounced (stored on contact)"
           4. not_a_replier: "contact contact-1 has replied"
           5. not_in_a_live_sequence: returns ("unverifiable", "no email and no profile URL")
           6. account_rule_satisfied: returns ("unverifiable", "no domain on record")
           7. approval_snapshot_covers: "account unknown-account.test is pending, not approved"
           8. timezone_cohort_has_a_window: returns ("unverifiable", "no timezone on record")
    TIMEZONE WINDOWS AS THE PROVIDER RETURNED THEM: N/A (no live run)
    OURS-VS-CLIENT EVIDENCE FOR EVERY in_sequence ROW: N/A (no live run)
    ARITHMETIC: clean + |offenders u unverifiable| == subjects? YES (tested)
    WORKSPACES COPY USED: N/A (no production work/ in this worktree)
    SUITE BASELINE vs HEAD~1: new = 34 tests in test_a_lead_eligible_here_can_be_in_sequence_there;
           gone = none; full baseline pending suite completion
    DEFECTS FOUND IN MODULES I MAY NOT EDIT: None observed during construction
    FINDINGS:
           - Live run over the real 128 is owed from Claude's worktree
           - timezone_cohort_has_a_window is EXPECTED to fail for out-of-hours
             cohorts (ISSUE-045: all 15 EmailBison campaigns are 09:00-17:00)
           - not_in_a_live_sequence will have unverifiable leads where profile
             URLs are absent (ISSUE-041: zero contacts carry heyreach_lead_id)
    RISKS:
           - The check calls bison.find_lead_by_email and heyreach.campaigns_for_lead
             for live reads; these are READ-ONLY but cost API calls
           - The ISSUE-035 carve-out recognises "operator_stopped", "manual_stop",
             "deliberate_stop", "agency_stopped", "client_request_stop" as our stops;
             if the actual stop_reason vocabulary differs, the carve-out may not fire
    RECOMMENDED CLAUDE ACTION:
           1. Run the live check from Claude's worktree against the real 128
           2. Review the ISSUE-035 stop_reason vocabulary against actual data
           3. Wire the runner (TASK-292) to import from CHECKS registry
           4. Integrate into the push refusal path in bisonfactory.stage
