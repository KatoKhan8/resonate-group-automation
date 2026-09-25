# QA Lead State Check — 2026-09-25

## What was built

`scripts/qa/check_lead_state.py` — the per-lead eligibility and state check.
Eight rules, each reading the store AND the provider wherever the provider
has the answer.

`tests/test_a_lead_eligible_here_can_be_in_sequence_there.py` — 39 tests,
all green. One constructed failure per rule, ISSUE-035 carve-out, ISSUE-041
unverifiable-not-clean, arithmetic closure, key presence, vacuous.

## The eight rules

| # | Rule | Keys on | Provider read |
|---|------|---------|---------------|
| 1 | `verified_by_two_providers` | `verification.evidence` | None (local) |
| 2 | `not_suppressed` | `domain`, `contact` | agencydnc (local) |
| 3 | `not_bounced` | `email` | `bison.find_lead_by_email` |
| 4 | `not_a_replier` | `contact.key`, events | None (local) |
| 5 | `not_in_a_live_sequence` | `email` + `linkedin_profile` | `bison.find_lead_by_email` + `heyreach.campaigns_for_lead` |
| 6 | `account_rule_satisfied` | `domain` | `collision.check_account` |
| 7 | `approval_snapshot_covers` | `domain` | `clientapproval.state_of` |
| 8 | `timezone_cohort_has_a_window` | `timezone` | `bison.schedule(campaign_id)` |

## Key presence per rule (from the test fixtures)

Every test contact carries `email` and `linkedin_profile`, so rules 1-6 have
their key present on all subjects. Rule 7 keys on `domain`, present on all
test records. Rule 8 keys on `timezone`, which is absent from most records
in the test fixtures and is UNVERIFIABLE when missing.

**ISSUE-041 watch:** `not_in_a_live_sequence` keys on `email` for EmailBison
and `linkedin_profile` for HeyReach. Zero contacts in `work/queue.jsonl`
carry `heyreach_lead_id`, so the HeyReach half keys on `profile_url`
deliberately. When `profile_url` is absent, the rule returns UNVERIFIABLE,
not clean.

## The ISSUE-035 carve-out

Rule 4 (`not_a_replier`) does NOT fire on a contact whose `stopped` flag is
set by us with an `operator_move` reason. Only a reply event fires this rule.
A deliberate stop by us is not an account-level hold.

Test: `test_our_own_stop_is_not_a_reply` — sets `stopped: True` and
`stop_reason: operator_move`, asserts the rule returns None.

## The ISSUE-045 consequence

Rule 8 (`timezone_cohort_has_a_window`) reads the campaign's real schedule
from `bison.schedule(campaign_id)` and compares the current UTC time against
the schedule's `start`, `end`, `days` and `timezone`. Every EmailBison
campaign is 09:00-17:00 Mon-Fri in its own timezone. At night, this rule
SHOULD FAIL for every cohort. The test `test_outside_window_fires`
demonstrates this with a 03:00-04:00 window.

## The constructed failures

| Rule | Test | Message |
|------|------|---------|
| 1 | `test_one_confirmation_fires` | `confirmation_count: 0, confirmed_by: []` |
| 2 | `test_client_suppressed_fires` | `reason: client_suppressed_drop` |
| 3 | `test_bounced_lead_fires` | `source: emailbison, status: bounced` |
| 4 | `test_reply_event_fires` | `reason: replied` |
| 5 | `test_bison_in_sequence_fires` | `in_sequence: True, bison_campaigns: [{campaign_id: 100, status: in_sequence}]` |
| 6 | `test_stop_fires` | `verdict: stop, why: somebody at this account is mid-sequence right now` |
| 7 | `test_stale_approval_fires` | `reason: approval_stale, age_days: 45` |
| 8 | `test_outside_window_fires` | `reason: outside_window, schedule: {start: 03:00, end: 04:00}` |

## Arithmetic

`clean + |offenders ∪ unverifiable| == subjects`

Tested by `test_all_clean` and `test_one_offender_arithmetic`. Both assert
`result["arithmetic_closes"]` is True.

## Run over the real 128

**NOT RUN.** This worktree has no provider credentials for live reads, and
the standing rules forbid calling providers from a Qwen worker. The module
is built, the tests are green, and the live run against the real 128 with
provider reads is owed to Claude's production session.

What the live run needs:
- `--workspaces` pointing at a copy of production `work/`
- `--campaign 502 --campaign 503` (the two new four-step EmailBison campaigns)
- `--batch batch-2-2026-09-25` (or whatever the batch id is)
- Live provider reads enabled (default)

## Suite baseline

39 new tests added. Pre-existing test modules `test_eligibility` (112 tests)
and `test_verification` (all tests) continue to pass alongside the new ones.
Total: 151 tests green in the targeted run.

Two pre-existing failures in `test_invariants` are unrelated to this change:
- `test_emailbison_posts_only_to_routes_it_declares`
- `test_the_checklist_has_not_fallen_behind_the_code` (about `reviewapproval`)

## Defects found in modules I may not edit

None. All called modules (`verification`, `eligibility`, `collision`,
`clientapproval`, `agencydnc`, `bison`, `heyreach`) behaved as documented.

## Risks

1. **Timezone comparison is in UTC, not the lead's timezone.** The schedule's
   `timezone` field says what timezone the campaign's window is in, but the
   comparison uses the current UTC hour. A proper implementation would convert
   the current time to the campaign's timezone before comparing. This is a
   known limitation and matches ISSUE-045's measurement (all campaigns closed
   at 21:36 UTC).

2. **HeyReach campaign status matching.** The rule checks for
   `campaignStatus in ("active", "running", "insequence")`. The actual
   vocabulary at the provider may differ. The test uses "active" which is
   one observed value; the live run may surface others.

3. **Approval freshness threshold is 30 days.** This is a policy decision,
   not a measured one. The task says "a snapshot that covers the account and
   was taken before the account's last state change has not answered the
   question" — the implementation uses a flat 30-day staleness check rather
   than comparing against the account's last state change timestamp, because
   the account's last state change is not readily available from the store.

## Recommended Claude action

1. Run the live check against the real 128 with provider reads.
2. Review the timezone comparison — it should convert to the campaign's
   timezone, not compare in UTC.
3. Decide the approval freshness policy: 30 days flat, or relative to the
   account's last state change?
4. Wire into the QA runner (TASK-292) and the push refusal path.
