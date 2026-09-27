# QA check: EmailBison campaign readiness

**TASK-296, Lane F.  2026-09-25.**

## What this checks

Whether a campaign the system is about to push leads to is actually built
at the provider, right now, to send what we think it will send. Every
readback this project has trusted and then found wrong was of this shape:
`active`, `in_sequence` and `scheduled` were each read as a send; campaign
485 was left at 0 steps; 76 blank emails went out of a campaign that
looked fine.

## The eight rules

| # | Rule | What it catches |
|---|------|-----------------|
| 1 | `campaign_exists` | Campaign exists by ID at the provider (ISSUE-036: name lookup cannot find a campaign this system just created) |
| 2 | `step_count_matches` | Stored `cadence_steps` matches provider step keys, diffed as SETS both directions. Catches the half-applied change where count matches but keys differ |
| 3 | `templates_use_only_carried_variables` | Template `{VARIABLE}` names vs lead variables, both directions. Template names no lead carries → blank render. Lead names no template uses → wasted variable |
| 4 | `sender_attached_and_connected` | At least one sender attached AND its status is Connected. Attached ≠ Connected (a disconnected mailbox is attached and useless). Workspace asserted via `bound_workspace()` |
| 5 | `schedule_and_limits_set` | Sending window (days, start, end, timezone) and daily limits, both read back from the provider |
| 6 | `no_settled_blank_rows` | Zero settled blank rows in the scheduled queue. Zero scheduled rows is VACUOUS, not PASS (ISSUE-041) |
| 7 | `not_paused` | Provider paused state matches the registry intent for THAT campaign |
| 8 | `id_matches_our_registry` | Provider campaign ID equals the registry's `bison_campaign_id` |

## The Option A step count

Under Option A, new campaigns get four steps; 485–500 stay three-step.
Eleven rows legitimately hold three while new ones hold four. The check
reads the row's own `cadence_steps` and compares against THAT, never
against a global constant. A check comparing to 4 refuses eleven correct
campaigns; a check comparing to `copylint.STEPS_EXPECTED` (which is 5)
refuses all of them.

## The step key set diff

`len(a) == len(b)` compares equal while the sets differ: `{1, 2, 4}` and
`{1, 2, 3}` both have length 3 but are different steps. The check diffs
the SETS in both directions and reports the names:

    stored=3  provider_keys=[1, 2, 4]  expected_keys=[1, 2, 3]
    only_provider=[4]  only_stored=[3]

## The variable diff, both directions

A template naming a variable no lead carries sends a gap (blank render).
A lead carrying a variable no template names is wasted render and is how
`body_4` came to exist while nothing read it. Both directions are
reported per campaign, named:

    template_vars=[body_1, subject_1]  lead_vars=[body_1, body_9, subject_1]
    only_template=[]  only_lead=[body_9]

## VACUOUS, not PASS

A campaign with zero scheduled rows is VACUOUS for the blank rule, not
PASS. It has no evidence either way — the ISSUE-041 shape. The result
says which campaigns were vacuous.

## Usage

    py -3 scripts/qa/check_campaign_bison.py \
        --workspaces <path to work/ copy> \
        --campaign 502 --campaign 503 \
        --json work/qa/2026-09-25T06-00Z/campaign_bison.json

Or as an import:

    from scripts.qa import check_campaign_bison
    result = check_campaign_bison.run(
        workspaces="path/to/work-copy",
        campaign_ids=[502, 503])

## Exit codes

    0  PASS         every campaign, every rule clear
    1  FAIL         at least one campaign offends at least one rule
    2  UNCONFIRMED  a provider read failed or the subject set was empty
    3  ERROR        the check itself broke

## What the check does NOT do

- No provider write. Not `set_sequence`, `set_schedule`, `set_limits`,
  `pause`, `resume`, or anything else.
- No `find_campaigns_by_name` (ISSUE-036: it cannot find a campaign this
  system just created).
- No global step count. Each campaign's own `cadence_steps` is the oracle.
- No count comparison for step keys. The SET diff is the whole point.
- No `attached` read as `Connected`. A disconnected mailbox is attached.
- No sorting by `created_at`. It is null on the campaigns that send.
  Sorted by provider ID, numerically.

## Files

    scripts/qa/check_campaign_bison.py   the check
    scripts/qa/__init__.py               the QA package
    tests/test_step_counts_agree_while_the_keys_do_not.py
                                         58 tests, one constructed failure
                                         per rule
