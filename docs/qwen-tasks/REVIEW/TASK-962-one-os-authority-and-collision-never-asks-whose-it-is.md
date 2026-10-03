# TASK-962 — one OS authority, and collision never asks whose sequence it is

Written 2026-10-02 on the operator's order, for work that was already done on
`task-one-os-authority`: the branch carried no task file, so
`scripts/glm_verify_branch.py` could not extract acceptance commands, the GLM
half of the gate could not run at all, and UNKNOWN does not pass. Its suite half
was already clean — 231 names, 0 new, 0 gone, against the reference measured on
the master it merges into.

**This file is docs-only and was written AFTER the code.** That is stated rather
than hidden: acceptance written after the fact can be acceptance chosen because
it passes. Three defences, all checkable by a reviewer:

1. every command below was EXECUTED before being written down, and the output of
   each is recorded under it;
2. command 1 carries a control that fails against an empty authority, so it
   cannot pass by watching nothing;
3. one of the four claims the operator's brief named is **contradicted by the
   measurement**, and this file says so instead of bending the code to the
   sentence — see "The brief's third claim" below.

## What the branch decides, and where

| question | consults ownership | lives in |
|---|---|---|
| **ATTRIBUTION** — whose campaign sent it | **yes**, this is what the authority is for | `osattribution.attribution`, `collision.os_campaign_ids`, `our_heyreach_campaign_ids` |
| **COLLISION** — is somebody mid-sequence to this person RIGHT NOW | **no, never** | `collision.account_policy` |

Operator's refined decision, quoted in the branch's own test docstring:

> "Atribucija: ne-OS povijest ne blokira i ne broji se kao naš touch. Kolizija:
> ako je osoba trenutno mid-sequence u bilo kojoj aktivnoj kampanji, OS ili ne,
> verdikt je HOLD do kraja te sekvence, ne STOP i ne DNC."

## The brief's third claim, and the measurement that contradicts it

The order that produced this file asked for an acceptance command proving that
**a non-OS mid-sequence gives HOLD and an OS one gives STOP.** That was true of
`8bfd9431` and is **no longer true of the branch**: `aef91548` reversed it after
the operator refined the decision, deleted
`tests/test_a_non_os_sequence_is_not_our_collision.py`, and replaced it with
`tests/test_a_live_sequence_holds_whoever_is_running_it.py`, whose
`test_an_os_sequence_holds_the_account_identically` and
`test_the_three_verdicts_are_literally_the_same` assert HOLD for an OS sequence
too. `account_policy(account)` at the branch head takes **no ownership
arguments at all.**

Measured, not inferred: an account with one live membership on **OS 487** gives
`hold`, the same account on **internal 352** gives `hold`, and the two verdicts
are equal. Command 3 asserts exactly that. Writing the brief's version would
have reverted the operator's own refinement on the strength of one line.

What still STOPs is a **reply**, and it is asked FIRST — command 4.

## Acceptance

**Commands run from a checkout of this branch**, and they need nothing from the
environment: command 1 RESOLVES the production ledger itself through
`git rev-parse --path-format=absolute --git-common-dir`, the one path identical
from the main checkout and from every worktree, and refuses a relative answer
rather than resolving it.

That matters because `work/` is gitignored and every worktree has its own: in a
fresh worktree the authority reads as **readable with ZERO campaigns**, which is
a different state from unreadable and would make "274 is not ours" true for the
wrong reason. An earlier draft of this command took `CAMPAIGNS` from the
environment, which would have FAILED inside the GLM harness - that runs
acceptance in a temporary worktree and sets no such variable.

```
python -c "import os,subprocess,sys; out=subprocess.run(['git','rev-parse','--path-format=absolute','--git-common-dir'],capture_output=True,text=True,encoding='utf-8').stdout.strip(); assert out and os.path.isabs(out), 'git would not answer absolutely, so the ledger cannot be found'; os.environ['CAMPAIGNS']=os.path.join(os.path.dirname(out),'work','campaigns.jsonl'); sys.path.insert(0,'.'); from src import collision; ids,readable=collision.os_campaign_ids(); assert readable, 'the authority was not readable, so every \"not ours\" below would be vacuous'; keys={collision.campaign_key(i) for i in ids}; assert collision.campaign_key(481) in keys, '481 is not in the authority: wrong ledger'; internal=[c for c in (274,327,328,352) if collision.campaign_key(c) in keys]; assert not internal, 'operator-declared internal campaigns are in the OS authority: '+str(internal); print('OK 481 is OS, 274/327/328/352 are not, authority readable,', len(ids), 'campaigns, from', os.environ['CAMPAIGNS'])"
```

→ measured: `OK 481 is OS, 274/327/328/352 are not, authority readable, 20 campaigns, from ...\work\campaigns.jsonl`

```
python -c "import sys; sys.path.insert(0,'.'); from src import osattribution as oa; read=oa.attribution('bison',481,ledger_says='resonate_internal',authority_says=(frozenset(),True)); blind=oa.attribution('bison',481,ledger_says='resonate_internal',authority_says=(frozenset(),False)); assert read=='not_ours', 'a READ authority must let a positive internal claim disown: '+read; assert blind=='unknown', 'an UNREADABLE authority must give UNKNOWN, never not_ours: '+blind; assert oa.attribution('bison',481,ledger_says='resonate_os',authority_says=(frozenset(),False))=='ours'; print('OK readable+internal ->', read, '| unreadable+internal ->', blind)"
```

→ measured: `OK readable+internal -> not_ours | unreadable+internal -> unknown`

```
python -c "import sys; sys.path.insert(0,'.'); from src import collision as c; mem=lambda cid: {'campaign_id':cid,'status':'in_sequence','emails_sent':1,'replies':0,'opens':0,'interested':False}; raw=lambda e,cid: {'email':e,'id':1,'status':'active','overall_stats':{'emails_sent':1,'replies':0,'opens':0},'lead_campaign_data':[mem(cid)],'created_at':'2026-08-01T00:00:00+00:00'}; acct=lambda cid: (lambda people: {'domain':'example.test','workspace':'productive','leads':len(people),'people':people,'our_staging_excluded':[],'emails_sent_total':1,'anyone_in_sequence':any(p['in_sequence'] for p in people),'unknown_statuses':[],'any_bounce':False,'verdict':c.IN_SEQUENCE,'checked_at':'2026-10-02T00:00:00+00:00'})([c.touches_of(raw('a@example.test',cid))]); ours=acct(487); theirs=acct(352); assert ours['anyone_in_sequence'] and theirs['anyone_in_sequence'], 'the fixture carries no live sequence, so it proves nothing'; vo,wo=c.account_policy(ours); vt,wt=c.account_policy(theirs); assert vo==c.HOLD and vt==c.HOLD, 'a live sequence must HOLD whoever owns it: OS='+vo+' internal='+vt; assert 'our' not in wo.lower() and 'ours' not in wt.lower(), 'the reason claims ownership, which collision never asks: '+wo+' / '+wt; print('OK OS 487 ->', vo, '| internal 352 ->', vt, '| same verdict:', vo==vt)"
```

→ measured: `OK OS 487 -> hold | internal 352 -> hold | same verdict: True`

```
python -c "import sys; sys.path.insert(0,'.'); from src import collision as c; mem={'campaign_id':352,'status':'in_sequence','emails_sent':2,'replies':1,'opens':1,'interested':False}; raw={'email':'a@example.test','id':1,'status':'active','overall_stats':{'emails_sent':2,'replies':1,'opens':1},'lead_campaign_data':[mem],'created_at':'2026-08-01T00:00:00+00:00'}; p=c.touches_of(raw); acct={'domain':'example.test','workspace':'productive','leads':1,'people':[p],'our_staging_excluded':[],'emails_sent_total':2,'anyone_in_sequence':p['in_sequence'],'unknown_statuses':[],'any_bounce':False,'verdict':c.IN_SEQUENCE,'checked_at':'2026-10-02T00:00:00+00:00'}; v,why=c.account_policy(acct); assert v==c.STOP, 'a reply is terminal and is asked FIRST, before the live-sequence HOLD: got '+v+' - '+why; print('OK a reply beside a live sequence ->', v)"
```

→ measured: `OK a reply beside a live sequence -> stop`

### NEGATIVE CONTROL

Each command can fail, and three of them were observed failing or were built
around a failure:

- **Command 1 against a worktree's own empty ledger fails**, measured:
  `AssertionError: 481 is not in the authority: wrong ledger`. That is the
  control that it reads the real authority rather than an empty one — and the
  `assert readable` line above it is the control that an unreadable authority is
  not being mistaken for an empty one. Both halves matter: a `readable` that is
  False and a `keys` set that is empty are different failures with opposite
  consequences.
- **Command 2 IS a pair**: the same `ledger_says='resonate_internal'` with the
  authority readable and unreadable must give two DIFFERENT answers. One arm
  alone would pass under a function that ignored readability entirely.
- **Command 3 asserts its own fixture first** (`anyone_in_sequence` on both
  sides) before asserting the verdicts, because a hand-built account with the
  wrong shape reports an empty membership set, which is indistinguishable from
  "nobody is mid-sequence" and would make HOLD arrive for the wrong reason. The
  branch's own commit names that reader bug.
- **Command 4 is the control on command 3**: if the live-sequence HOLD had
  swallowed the reply arm, a replying account would HOLD instead of STOP, and
  the account would be left open to a second sequence.

## Files

None. This is a docs-only addition to a branch whose code is finished.

`.md` IS in `test_fixture_hygiene`'s `TEXT_SUFFIXES`, so adding this file is not
automatically invisible to the suite — the claim that the banked suite result
still stands is MEASURED by running that module alone against the branch with
this file in the tree, and it must give the same five failing names the
reference carries.

## Not in scope

Wiring `recontact-suppression.json` into `eligibility` (TASK-953). The 937
rebase. Anything that touches the send path.
