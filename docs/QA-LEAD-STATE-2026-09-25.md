# QA Lead State Check — 2026-09-25

## What was built

`scripts/qa/check_lead_state.py` — the per-lead eligibility and state check
for the QA suite (Lane F, TASK-293). Eight rules, each checking both the
local store and the providers.

## The eight rules

| # | Rule key | What it checks | Module it calls |
|---|----------|---------------|-----------------|
| 1 | `verified_by_two_providers` | Two independent verification confirmations | `verification.confirmations` |
| 2 | `not_suppressed` | Client suppression + agency DNC | `eligibility.must_not_contact`, `agencydnc.lookup` |
| 3 | `not_bounced` | Address has bounced anywhere | Record events + contact flags |
| 4 | `not_a_replier` | Person has replied to anything of ours | `events.is_reply`, ISSUE-035 carve-out |
| 5 | `not_in_a_live_sequence` | Not in_sequence at EITHER provider | `bison.find_lead_by_email`, `heyreach.campaigns_for_lead` |
| 6 | `account_rule_satisfied` | Same contact never twice; gap for persona | `collision.check_account`, `collision.account_policy` |
| 7 | `approval_snapshot_covers` | Client approval + snapshot freshness | `clientapproval.is_approved`, `clientapproval.state_of` |
| 8 | `timezone_cohort_has_a_window` | Campaign can send in lead's timezone | `bison.schedule`, ISSUE-045 aware |

## Design decisions

### Verifiability tracking

Each rule can return three outcomes:
- **Clean** (None): the rule passes
- **Offender** (string): the rule fails with a reason
- **Unverifiable** (tuple): the check could not establish the answer

Unverifiable is NOT folded into clean. A lead whose HeyReach state could
not be read because the profile URL is absent is UNVERIFIABLE, not clean.
This follows Lane D's `packfacts.identity_of` precedent: admitted / refused
/ unverifiable, and unverifiable is not a pass.

### Key presence reporting

For each rule, the check counts how many of N subjects carry the field the
rule keys on. A rule whose key is present on 0 subjects is VACUOUS for
those subjects (ISSUE-041 prevention).

### ISSUE-035 carve-out

Rule 4 (`not_a_replier`) distinguishes a stop WE made (carrying our own
reason plus an operator-recorded move) from a stop we did NOT make. The
former is NOT an account-level hold. TASK-275's red tests cover this.

### ISSUE-045 awareness

Rule 8 (`timezone_cohort_has_a_window`) reads the REAL schedule from the
provider and compares it to the lead's timezone. It is EXPECTED to fail
for out-of-hours cohorts. Every EmailBison campaign is 09:00-17:00 Mon-Fri
in its own timezone; at night, all are closed. A guessed timezone is worse
than a missing one.

### Arithmetic closure

`clean + |offenders ∪ unverifiable| == subjects`. The runner enforces this;
a check whose arithmetic does not close exits 3 (ERROR).

## Result document shape

```json
{
  "check": "lead_state",
  "phase": "pre_push",
  "verdict": "PASS|FAIL|UNCONFIRMED|VACUOUS|ERROR",
  "batch": "...",
  "campaigns": ["502", "503"],
  "subjects": 128,
  "clean": 121,
  "refused": true,
  "rules": { ... },
  "counts": { ... },
  "offenders": { ... },
  "unverifiable": { ... },
  "unverifiable_counts": { ... },
  "key_presence": { "total": 128, "per_rule": { ... } },
  "evidence": {
    "provider_reads": [ ... ],
    "files_read": [ ... ],
    "provider_reads_skipped": false
  },
  "measured_at": "...",
  "workspaces": "...",
  "arithmetic_closes": true
}
```

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | PASS — every subject checked, every rule clear |
| 1 | FAIL — at least one subject offends at least one rule |
| 2 | UNCONFIRMED / VACUOUS — could not establish the answer |
| 3 | ERROR — the check itself broke |

## Tests

`tests/test_a_lead_eligible_here_can_be_in_sequence_there.py` — 34 tests,
all green. Covering:

- Eight constructed failures, one per rule
- Both directions (pass and fail) for each rule
- Arithmetic closure
- Key presence reporting
- Unverifiable vs offender distinction
- ISSUE-035 carve-out (our stop vs their stop)
- Same-provider-twice is one confirmation
- Result document shape invariants
- Exit codes

## Live run over the real 128

**NOT RUN FROM THIS WORKTREE.** This worktree has no `work/queue.jsonl`
(most worker worktrees do not; per QWEN.md, generation against the real
queue is Claude's, run from Claude's worktree).

The live run is OWED from Claude's worktree with:

```
py -3 scripts/qa/check_lead_state.py \
    --phase pre_push \
    --batch batch-2-2026-09-25 \
    --campaign 502 --campaign 503 \
    --workspaces <path to production work/ copy> \
    --workspace productive \
    --json work/qa/<run>/lead_state.json
```

Expected findings from the live run:
- `timezone_cohort_has_a_window` will FAIL for out-of-hours cohorts
  (ISSUE-045: all 15 EmailBison campaigns are 09:00-17:00 in their own
  timezone, and at night all are closed)
- `not_in_a_live_sequence` will have unverifiable leads where profile URLs
  are absent (ISSUE-041: zero contacts carry `heyreach_lead_id`)
- `verified_by_two_providers` may flag leads with only one confirmation
- `approval_snapshot_covers` may flag stale snapshots
  (THE-ROSTER-IS-A-SNAPSHOT-NOBODY-REFRESHES-2026-09-17)

## Defects found in modules I may not edit

None observed during construction. The modules called
(`verification`, `eligibility`, `collision`, `clientapproval`, `agencydnc`)
behaved as documented. Any defects discovered during the live run should be
reported as proposed tasks, not patched.

## Caller verification

`grep -rn "check_lead_state" scripts/ src/` — the only caller is the CLI
entry point (`if __name__ == "__main__"`). The runner (TASK-292) will
import this module via `scripts/qa/__init__.py::CHECKS`. Registration is
in place:

```python
CHECKS = {
    "lead_state": {
        "module": "scripts.qa.check_lead_state",
        "phase": "pre_push",
        "blocking": True,
        "subject": "lead",
    },
}
```

## Files changed

- `scripts/qa/__init__.py` — the QA check registry (CHECKS, PHASES, verdicts)
- `scripts/qa/check_lead_state.py` — the check module (717 lines)
- `tests/test_a_lead_eligible_here_can_be_in_sequence_there.py` — 34 tests

## Suite baseline

Pending the full suite run. The new test file adds 34 tests by name.
No existing tests were modified. Diff against HEAD~1 will report:
- **new**: 34 tests in `test_a_lead_eligible_here_can_be_in_sequence_there`
- **gone**: none
- **common**: everything else
