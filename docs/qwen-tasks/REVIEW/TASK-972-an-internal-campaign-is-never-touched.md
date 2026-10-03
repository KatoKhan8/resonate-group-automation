# TASK-972 — an internal campaign is never touched, and UNKNOWN is never a pass

Written 2026-10-03 for work already finished on
`task-guard-regressions-rebased`, because the branch carried no task file and
`glm_verify_branch.py` extracts its acceptance from one: no file, no GLM
verdict, and UNKNOWN does not pass. **Written AFTER the code and saying so**,
with every command executed before being written down.

This branch is **REQUIRED for the canary** — `scratchpad/canarypath.py` measured
the send-path closure at 109 of 258 `src/` modules and named this branch for a
reason worth restating: **the internal-campaign protection does not exist on
master in any form.**

## The discriminator, measured on both sides

The obvious candidate is wrong, and it is worth writing down so nobody uses it:

    master   CONDITIONAL verbs: 8
    branch   CONDITIONAL verbs: 8

Same eight — `bison.activate`, `bison.assign_sender`, `bison.resume`,
`heyreach.activate`, `heyreach.add_lead`, `heyreach.add_lead_to_list`,
`heyreach.create_campaign`, `heyreach.start_empty_for_staging`. Counting them
proves nothing.

**The real discriminator is the ownership classifier, and on master it does not
exist:**

    master   hasattr(providerwrites, "classify_campaign") -> False
    branch   classify_campaign("email", "327")            -> resonate_internal

On master those eight verbs are conditioned on other questions — whether a
campaign is a declared staging campaign, whether a list is unbound — so an
operator-internal campaign was never refused *for being theirs*. That is A1.

Measured on the branch:

| input | verdict |
|---|---|
| `274`, `327`, `328`, `352` | `resonate_internal` |
| `481` (with the production ledger) | `resonate_os` |
| `999999`, `None`, unreadable | `unknown` |
| `327`, `"327"`, `327.0`, `" 0327"` | all `resonate_internal` — one campaign |

## Acceptance

```
python -c "import os,subprocess,sys; out=subprocess.run(['git','rev-parse','--path-format=absolute','--git-common-dir'],capture_output=True,text=True,encoding='utf-8').stdout.strip(); assert out and os.path.isabs(out), 'git would not answer absolutely'; os.environ['CAMPAIGNS']=os.path.join(os.path.dirname(out),'work','campaigns.jsonl'); sys.path.insert(0,'.'); from src import providerwrites as pw; assert hasattr(pw,'classify_campaign'), 'there is no ownership classifier - this is master, not the branch'; states={pw.classify_campaign('email',c) for c in ('274','327','328','352')}; assert states=={'resonate_internal'}, states; assert pw.classify_campaign('email','481')=='resonate_os', pw.classify_campaign('email','481'); assert pw.classify_campaign('email','999999')=='unknown'; assert pw.classify_campaign('email',None)=='unknown'; print('OK internal/ours/unknown all distinguished, from the production ledger')"
```

```
python -c "import sys; sys.path.insert(0,'.'); from src import providerwrites as pw; spellings={pw.classify_campaign('email',v) for v in (327,'327',327.0,' 0327')}; assert len(spellings)==1, spellings; junk={pw.classify_campaign('email',v) for v in (None,'','abc',0,-1,[])}; assert junk=={'unknown'}, junk; assert set(pw.classify_campaign('email',x) for x in ('327','999999'))<= {'resonate_os','resonate_internal','unknown'}; print('OK four spellings are one campaign, and junk is UNKNOWN, never a pass:', spellings, junk)"
```

```
python -m unittest tests.test_an_internal_campaign_is_never_touched -v
```

### NEGATIVE CONTROL

**Command 1 dies on master** with `there is no ownership classifier - this is
master, not the branch`, which is the whole point of the branch; and it reads
the PRODUCTION ledger through `--path-format=absolute --git-common-dir` rather
than the calling tree's, because a worktree's own `work/` is empty and `481`
then reads `unknown` — true, and true for the wrong reason. Measured both ways
before this was written.

Command 2's junk set is the control that the classifier does not fall OPEN:
`None`, `""`, `"abc"`, `0`, `-1` and `[]` must all be `unknown`, because a value
nothing can be matched against is a value nobody may write to. Its first half is
the opposite control — four spellings of one id must not become four campaigns,
which is how `"487" in {487}` once read as "not ours".

Command 3 is the branch's own 651-line module, nine classes including
`UnknownIsNeverAPass`, `AnInternalCampaignIsRefusedForEveryVerb`,
`TheAllowedPathIsUNCHANGED` and `TheExistingSealsDoNotRegress`. The last two are
the ones that matter for a guard: a refusal that also refuses the allowed path
is not a guard, it is an outage.

## One nuance recorded rather than smoothed over

`require_conditional_permission(op, '327')` called WITHOUT a canonical
`campaign_id` raises `WriteRefused`, but the message names the AUTHORIZATION
SCOPE, not ownership — so that call proves a refusal happened, not that it
happened for the right reason. The ownership refusals are asserted through the
classifier (commands 1 and 2) and through the branch's own per-verb tests
(command 3), which pass the canonical campaign the condition needs.

## Files

`src/providerwrites.py`, `src/bison_watch_loop.py`, the declaration config, and
the tests. Nothing in this file changes code.

## Not in scope

A3, the 487 seal, which is `task-936-487-on-the-gate`. The canary itself.
