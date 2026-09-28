# TASK-483 — Independent verification of TASK-327

**Reviewer:** GLM (Qwen-7 worktree)
**Date:** 2026-09-28
**Target task:** TASK-327 — a lead is never modelled as an isolated campaign unit
**Branch:** `origin/qwen-worker-2-r60`
**Branch HEAD SHA:** `94819507ab30153ea72d570442d356fd5a7a32c8` (verified with `git rev-parse`; matches task file)
**Isolated worktree:** `.qwen/worktrees/task483-review` at exact SHA, now removed

---

## Summary

**DISPOSITION: MERGE**

TASK-327 delivers what it claims: 35 tripwire tests covering all 13 edges in the operator's relationship chain, plus four operator rules and a flattened-model tripwire. All 35 tests pass on the branch head. No `src/` files are changed. Production callers are extensive and verified. All four falsification claims were independently reproduced by mutation. The branch is clean — no scope drift, no junk, no unrelated changes.

One weakness found: `test_fails_if_contacts_have_distinct_account_identities` is tautological (see Finding 1). This does not block merge — the other two tests in the class provide real tripwire value, and the tautology is a nice-to-have fix, not a defect.

---

## 1. Does the artifact exist, and does it do what the result block claims?

**YES — verified on the exact ref.**

Files on `94819507ab`:
- `tests/test_the_account_relationships_survive.py` — NEW, 461 lines, 35 tests in 18 classes
- `docs/state/ACCOUNT-MODEL-INVARIANTS.md` — NEW, 172 lines, generated invariant doc
- `docs/qwen-tasks/DONE/TASK-327-*.md` — task file moved from TODO to DONE

Test run on the isolated worktree:

    Ran 35 tests in 0.315s — OK

The result block claims "13 classes" but there are actually 18: 13 edge classes + 4 operator-rule classes + 1 flattened-model tripwire class. The total of 35 tests is correct. This is a minor counting inaccuracy in the result block, not a defect.

---

## 2. Existence is not function — are the traversals CONSUMED?

**YES — extensively.**

Production callers verified on the branch head:

| Traversal | Production callers in `src/` |
|-----------|------------------------------|
| `account.contacts_of` | 37+ call sites: accountpolicy, accountsaturation, cadenceexposure, cadencematurity, cadencereplies, cadencesafety, campaignqa, conversation, hygiene, nextaction, oooreturn, orchestrator, outcomes, priority, revival, signals, variants, web/api |
| `account.touches` | 20+ call sites: accountsaturation, cadenceexposure, conversation, digest, fatigue, hygiene, nextaction, outcomes, outreachclaims, priority, revival, signals, variants, web/api |
| `account.replies` | 15+ call sites: cadenceexposure, cadencereplies, cadencesafety, digest, hygiene, oooreturn, outreachclaims (via referred_by), priority, revival, web/api |
| `account.referrals` | conversation, signals, web/api |
| `account.referred_by` | outreachclaims |
| `account.referred_to` | accountpolicy |
| `account.graph` | 20+ call sites: accountpolicy, accountsaturation, contextpack, fatigue, nextaction, notify, outreachclaims, web/api |
| `account.team_for` | web/api |
| `accountpolicy.apply_reply` | replies, cadence, events, inbound, tagsync, web/api |
| `accountpolicy.effects` | cadence, web/api |

**No zero-consumer components.** Every traversal the tests exercise is wired into production through multiple independent callers.

---

## 3. Falsification — are the tests seen to FAIL when broken?

**YES — all four independently reproduced.**

I performed each mutation on `src/accountpolicy.py` in the isolated worktree and ran the affected test class.

### Rule 1: `on_negative` changed from `(CONTINUE, CONTACT)` to `(STOP, ACCOUNT)`

    FAIL: test_negative_reply_does_not_suppress_colleagues
    AssertionError: True is not false  (sarah.get("unsubscribed"))
    FAIL: test_only_unsubscribe_sets_unsubscribed
    AssertionError: True is not false  (john.get("unsubscribed"))

**Matches the result block exactly.**

### Rule 2: `on_account_dnc` scope changed from `ACCOUNT` to `CONTACT`

    FAIL: test_account_dnc_reaches_every_contact
    AssertionError: None is not true : sarah not suppressed
    FAIL: test_account_level_suppression_flag_is_set
    AssertionError: None is not true

**Matches the result block exactly.**

### Rule 3: `_TRANSITION[(CONTINUE, CONTACT)]` replier changed from `STOP` to `CONTINUE`

    FAIL: test_negative_reply_stops_the_replier
    AssertionError: 'continue' not found in ('stop', 'hold', 'suppress')
    FAIL: test_apply_reply_marks_replier_state
    AssertionError: None is not true : John replied but nothing stopped or held him
    ok: test_positive_reply_stops_the_replier

**Matches the result block exactly.** The positive test passes because POSITIVE goes through `(HOLD, ACCOUNT)`, not `(CONTINUE, CONTACT)` — a different guard, unaffected by this mutation.

### Rule 4: Added `replier.pop("unsubscribed", None)` before the normal apply logic

    FAIL: test_reapply_cannot_lift_a_suppression
    AssertionError: None is not true  (john.get("unsubscribed"))
    ok: test_reapply_cannot_lift_a_hold

**Matches the result block exactly.** The hold-lift test passes because the mutation only cleared `unsubscribed`, not `paused` — a different guard.

---

## 4. Are the tests falsifiable?

**YES — with one weakness.**

The 34 tests outside `ThreeContactsAreOneAccount` are genuine behavioural assertions:
- They call real production functions (`account.contacts_of`, `accountpolicy.apply_reply`, etc.)
- They assert on returned values and record state, not on source text or `hasattr`
- They are driven through the real entry points, not through fakes or cassettes
- Each operator-rule test was observed to fail for the intended reason when its guard was broken

**Finding 1 — `test_fails_if_contacts_have_distinct_account_identities` is tautological.**

```python
def test_fails_if_contacts_have_distinct_account_identities(self):
    rec = self.make_record()
    contacts = account.contacts_of(rec)
    account_ids = {rec["id"]}
    self.assertEqual(len(account_ids), 1, ...)
```

This constructs `account_ids` from `rec["id"]` alone — always a set of 1. It does not inspect the contacts returned by `contacts_of` for distinct account identities. The test would pass regardless of what `contacts_of` returns. The docstring claims it detects account fragmentation, but it cannot.

**Severity:** Nice-to-have fix. The other two tests in the class (`test_all_contacts_share_one_domain`, `test_graph_groups_contacts_under_one_account`) provide real tripwire value by asserting 3 contacts exist and the graph groups them under one `record_id`. A refactor that fragmented the account would still be caught by `test_graph_groups_contacts_under_one_account` (the graph would report wrong `decision_makers` count or `record_id`).

**Fix (not implemented, read-only review):** Replace `account_ids = {rec["id"]}` with something that checks whether each contact in the `contacts_of` result carries the same account identity, e.g. asserting all contacts share `rec["domain"]` or that the graph's `record_id` matches.

---

## 5. Would merging DELETE anything?

**NO — the merge is purely additive plus one legitimate task-file move.**

    docs/qwen-tasks/DONE/TASK-327-*.md      A (new)
    docs/qwen-tasks/TODO/TASK-327-*.md      D (moved to DONE)
    docs/state/ACCOUNT-MODEL-INVARIANTS.md   A (new)
    tests/test_the_account_relationships_survive.py  A (new)

The TODO file exists on master and is being moved to DONE — a legitimate state transition. No `src/` files changed. No production code affected. Zero risk of deleting anything valuable.

Verified: `git diff master...origin/qwen-worker-2-r60 --stat -- src/` returns empty.

---

## 6. Scope drift

**NONE.**

Two commits on the branch, both TASK-327:
- `7ce02414` — the test file and invariant doc
- `94819507` — task file move to DONE

Four files changed total. No unrelated changes, no scratch output, no junk. Clean cherry-pick if needed (but the whole branch is mergeable as-is).

---

## 7. Pre-existing test health

The 35 new tests do not break any existing tests. Seven pre-existing failures in `test_*account*` files exist on both master and the branch — they are unrelated to TASK-327 (confirmed by running the same suite on master, which produces the same 7 failures).

---

## Findings

| # | Severity | Finding | Disposition |
|---|----------|---------|-------------|
| 1 | Nice to have | `test_fails_if_contacts_have_distinct_account_identities` is tautological — asserts `{rec["id"]}` has cardinality 1, which is always true regardless of what `contacts_of` returns | NEW TASK (minor fix; the class still provides value through its other two tests) |

---

## Recommendations

**MERGE.** The branch is clean, the tests are real tripwires against production code, all four falsification claims are independently verified, and no production code is changed. The one weakness (Finding 1) is a nice-to-have fix that does not block merge.
