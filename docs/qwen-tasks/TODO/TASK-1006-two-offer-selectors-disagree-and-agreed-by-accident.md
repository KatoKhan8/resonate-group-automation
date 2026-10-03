# TASK-1006 — two offer selectors disagree, and until last night they agreed by accident

Found 2026-10-03 by the copy lane, while measuring a per-module name-set diff
for unrelated work. **Attributed by measurement rather than by argument**, and
the measurement says the exposing commit is mine.

## Measured

    generate_campaign._select_offers('productive', 'champion')
        -> [OFFER-B-OPERATIONS]

    campaignstrategy._offers_for_segment('productive', 'champion')
        -> [OFFER-B-OPERATIONS, OFFER-GIVE-001]

`_select_offers` narrows to the **composed** offer. `_offers_for_segment`
filters on **segment and persona only**. Two functions answer "which offer is
this campaign built from" and they return different sets.

`tests/test_only_the_selected_offer_is_validated` carries two failing names
that master does not. Both fail at `e471a035` — the copy branch's base, before
any of today's work — and they arrive with **`4099a130`, the give-first offer
commit**, because `OFFER-GIVE-001` is the first offer in the library that is
approved, carries persona `champion`, and **composes nothing**.

**Until that offer existed, the two functions agreed by accident.** Every
earlier offer happened to be both composed and segment-matched, so no input
separated them. The divergence is not new; the input that reveals it is.

And that test's own docstring predicted it in those words: *"the gate is
validating one set while the campaign is built from another."*

## Why it is on the send path

The offer the strategy would carry **unvalidated** is precisely the one with
`client_approved: false` — the give-first workspace, which the operator
recorded as a working hypothesis pending the client's answer. So the function
that validates sees one offer and the function that builds the campaign sees
two, and the extra one is the one nobody has approved for sending.

**Nothing can be sent with it meanwhile**, which is why this is a task and not
an incident: `eligibility._offer_unapproved` holds any step that names it. The
hold is the only thing standing between the divergence and a prospect, and a
hold is a consequence rather than a design.

## What to do

1. **One authority for "which offers is this campaign built from".** Either
   `_offers_for_segment` composes, or `_select_offers` is the only caller any
   builder uses. Prefer canonical state to a second representation of it — this
   is that rule's textbook case, and two functions answering one question is
   how the two drift.
2. **Do NOT edit the test to agree with either side.** It is correctly
   reporting a disagreement; weakening it hides the thing it was written to
   find, and its docstring says so.
3. Whichever function survives, assert the OTHER one's callers are migrated,
   not merely that the survivor is right.

## Acceptance

```
python -c "import sys; sys.path.insert(0,'.'); from src import generate_campaign as g, campaignstrategy as s; a=set(g._select_offers('productive','champion')); b=set(s._offers_for_segment('productive','champion')); assert a, 'the selector returned nothing - this command is reading the wrong thing'; assert a==b, 'the two selectors disagree for productive/champion: _select_offers=%s _offers_for_segment=%s'%(sorted(a), sorted(b)); print('OK both selectors agree:', sorted(a))"
```

```
python -m unittest tests.test_only_the_selected_offer_is_validated -v
```

### WHERE THESE COMMANDS MUST BE RUN, which is not optional

**On a tree that carries `OFFER-GIVE-001`** — today `task-copy-exemplars`
(`68f3601b`). Measured both ways on 2026-10-03:

| tree | command 1 | command 2 |
|---|---|---|
| `task-defect-map` (master + docs, no offer) | **PASSES** — both selectors return `['OFFER-B-OPERATIONS']` | **PASSES** |
| `task-copy-exemplars` (`68f3601b`, offer present) | **FAILS**, printing both sets | **FAILS**, 2 failures |

So an acceptance command here passes on master and fails on the branch, which
is backwards from every other task in this directory and is exactly why it is
written down: **run these on master and you will conclude the defect is
fixed.** The divergence is only observable where an offer exists that is
approved, persona-matched and composes nothing, and that is the one input the
library gained last night.

### NEGATIVE CONTROL

**Command 1 fails today**, printing both sets so the disagreement is visible
rather than asserted. Its first assertion is the control that the selector
answered at all: a function returning `[]` would make the two sets equal and
the command would pass having compared nothing — the empty-set pass is this
repository's most common vacuous green.

Command 2 is the test that found it, and it must go from red to green **without
being edited**. Check that: `git diff` on the test file must be empty in the
commit that fixes this.

## Files

`src/generate_campaign.py` (`_select_offers`), `src/campaignstrategy.py`
(`_offers_for_segment`), and every caller of whichever one is retired.

## Not in scope

`OFFER-GIVE-001` itself. The offer is correct data — operator-approved for
generation, `client_approved: false` for sending, with approver, date and SHA
recorded. It exposed the defect; it is not the defect, and removing it would
hide the divergence again rather than fix it.
