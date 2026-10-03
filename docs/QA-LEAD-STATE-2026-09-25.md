# QA Lead State Check — First Report

**Date:** 2026-10-03
**Task:** TASK-293
**Module:** `scripts/qa/check_lead_state.py`
**Tests:** `tests/test_a_lead_eligible_here_can_be_in_sequence_there.py`

## What was built

A per-lead eligibility and state check answering eight rules:

1. **verified_by_two_providers** — two independent verification confirmations
2. **not_suppressed** — client suppression and agency DNC
3. **not_bounced** — the address has bounced anywhere
4. **not_a_replier** — this person has replied to anything of ours
5. **not_in_a_live_sequence** — not in_sequence at EITHER provider
6. **account_rule_satisfied** — same contact never twice; ISSUE-035 carve-out
7. **approval_snapshot_covers** — client approval covers this account, fresh
8. **timezone_cohort_has_a_window** — campaign can send in lead's timezone

## Design decisions

### Key presence reported per rule (ISSUE-041)

Every rule reports which key fields are present on the subjects. A rule whose
key is present on 0 subjects is VACUOUS, not PASS. This prevents the
ISSUE-041 defect where `heyreach_lead_id` was absent from every contact but
the check reported success.

### Both providers checked for in_sequence

`not_in_a_live_sequence` reads BOTH EmailBison and HeyReach. At EmailBison,
`find_lead_by_email` returns the lead and we check campaign memberships. At
HeyReach, `campaigns_for_lead(profile_url=...)` returns campaigns. The
`ours_vs_client` evidence says which campaigns are ours vs the client's,
resolved from the campaign registry (campaigns.jsonl).

### ISSUE-035 carve-out

A stop carrying our own reason plus an operator-recorded move is NOT an
account-level hold. `_is_our_deliberate_stop` checks whether every stopped
person at the account was stopped by us deliberately (zero-email campaigns),
and if so, the collision gate does not treat it as a hold.

### ISSUE-045: timezone check fails for out-of-hours

The timezone check reads the campaign's real schedule from `bison.schedule()`
and compares the current time in the campaign's timezone. It does NOT default
a missing timezone, does NOT treat "campaign has a schedule" as "has a window",
and does NOT compare in UTC. At 21:36 UTC on 2026-09-24 every EmailBison
campaign was closed; this check reports that correctly.

### Arithmetic closes

`clean + |offenders ∪ unverifiable| == subjects`. A subject may offend
several rules and is counted once. The runner asserts this and returns ERROR
if it does not close.

## Tests

43 tests, all green. Eight constructed failures (one per rule), each with
the offending id and the message.

### Test categories

- **TestVerifiedByTwoProviders** (4 tests) — pass with two confirmations,
  fail with one, fail with no email, one provider answering twice is one
  confirmation
- **TestNotSuppressed** (3 tests) — pass when clean, fail on client
  suppression, fail on unsubscribed
- **TestNotBounced** (3 tests) — pass when clean, fail on bounce event,
  fail on contact marked bounced
- **TestNotAReplier** (3 tests) — pass when clean, fail on reply event,
  fail on stopped contact
- **TestNotInALiveSequence** (6 tests) — pass when clear at both, fail at
  EmailBison, fail at HeyReach, unverifiable when no profile URL,
  ours-vs-client evidence reported, key presence reported
- **TestAccountRuleSatisfied** (4 tests) — pass when allow, fail when stop,
  ISSUE-035 carve-out, unverifiable when no domain
- **TestApprovalSnapshotCovers** (3 tests) — pass when approved, fail when
  pending, fail when suppressed
- **TestTimezoneCohortHasAWindow** (4 tests) — pass when in window, fail
  when outside window (ISSUE-045), fail when no timezone, schedule as
  provider returned it
- **TestRunner** (5 tests) — arithmetic closes, vacuous when zero subjects,
  error when no workspaces, all rules present in output, live reads disabled
  marks unconfirmed
- **TestEightConstructedFailures** (8 tests) — one per rule, each with the
  offending id

## Registered in CHECKS

The check is registered in `scripts/qa/__init__.py::CHECKS` as:

```python
"lead_state": {
    "module": "scripts.qa.check_lead_state",
    "phase": "pre_push",
    "subject": "lead",
    "blocking": True,
}
```

## What is NOT done

- **Run against the real 128.** This worktree has no `work/queue.jsonl` and
  no provider credentials for live reads. The generation and live run are
  owed from Claude's worktree.
- **Suite baseline diff.** The full suite takes ~865 seconds and timed out.
  The 43 new test names are listed in the commit. No existing tests were
  modified.
- **Per-rule table over the real 128.** Owed from the live run.

## Files changed

- `scripts/qa/check_lead_state.py` — the check module (1278 lines)
- `scripts/qa/__init__.py` — registered `lead_state` in CHECKS
- `tests/test_a_lead_eligible_here_can_be_in_sequence_there.py` — 43 tests

## Defects found in modules I may not edit

None observed during implementation. All called modules
(`verification`, `eligibility`, `collision`, `clientapproval`, `agencydnc`,
`bison`, `heyreach`) behaved as documented.

## Risks

- The `not_in_a_live_sequence` check makes two provider reads per lead
  (EmailBison + HeyReach). For 128 leads that is 256 provider calls. The
  check should be run with rate limiting or batching in production.
- The `_is_our_deliberate_stop` heuristic for ISSUE-035 checks whether
  stopped campaigns have zero emails sent. This may not cover all cases of
  deliberate stops; TASK-275's red tests should pin the exact rule.

## Recommended Claude action

1. Run against the real 128 from Claude's worktree with live provider reads.
2. Record the per-rule table with offending ids.
3. Run the suite baseline diff to confirm no regressions.
4. Review the ISSUE-035 carve-out heuristic against TASK-275's red tests.
