# QA Campaign Bison Check — 2026-09-25

**TASK-296.** The per-campaign EmailBison check: is the campaign these leads
are about to be attached to actually built at the provider, right now, to
send what we think it will send?

## What it checks

Eight rules, each returning PASS/FAIL/UNCONFIRMED/VACUOUS per campaign:

| Rule | What it asks | Why it matters |
|------|-------------|----------------|
| `campaign_exists` | Does the campaign exist at the provider BY ID? | ISSUE-036: name lookup cannot find a campaign this system just created |
| `step_count_matches` | Do the provider step KEYS (as a set) match the stored `cadence_steps` keys? | Eleven campaigns hold three steps; new ones hold four. A count comparison passes while the keys differ |
| `templates_use_only_carried_variables` | Does every `{VARIABLE}` in every template exist on the leads, and vice versa? | Catches a blank before it renders; both directions |
| `sender_attached_and_connected` | Is at least one sender attached AND Connected? | Attached is not Connected; a disconnected mailbox is attached and useless |
| `schedule_and_limits_set` | Are days, start_time, end_time, timezone all set? | A campaign with no schedule sends nothing or sends at 3am |
| `no_settled_blank_rows` | Are there zero settled blank rows in the queue? | 496/497/498 held 63 stopped leads from the blank-email incident |
| `not_paused` | Is the campaign not paused at the provider? | A paused campaign sends nothing; the intent may differ from the state |
| `id_matches_our_registry` | Does the provider id match a row in campaigns.jsonl? | A campaign at the provider with no registry row is untracked |

## The central design decision: set diff, not count

`step_count_matches` compares step keys as SETS in BOTH DIRECTIONS, not
counts. `len(a) == len(b)` passes while the sets differ:

    stored:   {em1, em2, em3}
    provider: {em1, em2, em4}
    count:    3 == 3  -> PASS (wrong)
    set diff: em3 only in stored, em4 only in provider -> FAIL (correct)

This is the whole point of Option A: eleven campaigns legitimately hold
three steps while new ones hold four. A check comparing to a global constant
refuses eleven correct campaigns. A check comparing counts passes a
half-applied change. The set diff catches both cases correctly.

## The eleven three-step campaigns

Under Option A, campaigns 485-500 (minus those archived or empty) stay at
three steps. New campaigns 502+ get four. The check reads each campaign's
OWN stored `cadence_steps` and compares against that, never against a
global constant.

The eleven three-step campaigns are correct and the check must say so
explicitly. A check that refuses them is wrong, not strict.

## Zero scheduled rows is VACUOUS, not PASS

A campaign with zero scheduled rows in the queue is NOT a campaign with
zero blanks. It is a campaign with NO EVIDENCE either way. The check
reports it as VACUOUS (exit 2), not PASS (exit 0).

This is the ISSUE-041 shape: a check that passes because the thing it
checks is absent. The blank-email incident (76 empty emails) happened
because a campaign looked fine and nobody checked what was actually going
to send.

## Attached is not Connected

`bison.campaign_senders(id)` returns sender IDs. A sender can be attached
to a campaign but have status `disconnected` — a mailbox that stopped
working. The check reads the full sender inventory via
`bison.sender_emails()` and cross-references status.

A campaign with one attached sender whose status is `disconnected` and
zero `Connected` senders FAILS this rule.

## Template variables: both directions

The check extracts `{VARIABLE}` names from every step template the provider
returned, and diffs against the variables the leads actually carry.

**Direction 1**: a template naming a variable no lead carries -> the email
renders blank at that position.

**Direction 2**: a lead carrying a variable no template names -> wasted
render, and how `body_4` came to exist while nothing read it.

The step→variable mapping is positional: em4 reads `{BODY_3}`, em5 reads
`{BODY_4}` (TASK-295 has the table). The step key is NOT the variable
number.

## Workspace assertion

`workspace_id` is accepted and discarded by every list route on the
EmailBison API. A caller can believe it scoped a read and be holding
another client's estate. The check calls `bison.bound_workspace()` before
any list read and records the result.

## Exit codes

    0   PASS         every campaign checked, every rule clear
    1   FAIL         at least one campaign offends at least one rule
    2   UNCONFIRMED  a provider read failed, or subjects == 0 (VACUOUS)
    3   ERROR        the check itself broke

## Usage

    py -3 scripts/qa/check_campaign_bison.py \
        --phase pre_push \
        --campaign 485 --campaign 502 \
        --workspaces <path to work/ copy> \
        --json work/qa/<run>/campaign_bison.json

## What it does NOT do

- **No provider writes.** No `set_sequence`, no `set_schedule`, no
  `set_limits`, no `pause`, no `resume`. If the check finds a campaign
  misconfigured, that is a TASK, not a fix.
- **No name lookups.** `find_campaigns_by_name` cannot find a campaign this
  system just created (ISSUE-036). The check uses `bison.campaign(id)`.
- **No global step count.** Eleven campaigns hold three and are correct.
- **No fixture reads.** The check reads the provider, not a cassette.

## Boundaries

- READS ONLY at EmailBison.
- Does not edit `src/bisonfactory.py`, `src/cadence.py`,
  `config/clients/productive.yaml`, `scripts/batch1_build.py`, or
  `src/providers/*`.
- Does not edit `scripts/*_watch_loop.py` or anything under `work/` except
  `work/qa/`.
- Production `work/` is not yours; `--workspaces` a named copy.

## Tests

`tests/test_step_counts_agree_while_the_keys_do_not.py` — 20 tests, all
green. One constructed failure per rule, including the central case: three
steps on both sides but different keys, which a count comparison passes and
the set diff catches.

## Files

    scripts/qa/__init__.py
    scripts/qa/check_campaign_bison.py
    tests/test_step_counts_agree_while_the_keys_do_not.py
    docs/QA-CAMPAIGN-BISON-2026-09-25.md
