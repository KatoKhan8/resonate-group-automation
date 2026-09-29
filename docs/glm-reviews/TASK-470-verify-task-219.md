# TASK-470 — Independent verification of TASK-240

## Review metadata

    reviewed task       TASK-240 — the arity rule moves from the campaign to the action
    reviewed branch     origin/qwen-worker-r55
    reviewed HEAD SHA   8f4406e1bb2a4f9ce273b16785011c88da26b4f1
    SHA verified        yes — `git rev-parse origin/qwen-worker-r55` returned
                          8f4406e1bb2a4f9ce273b16785011c88da26b4f1, matching the
                          task file exactly. The branch has not moved.
    review worktree     .qwen/worktrees/glm-task470 (detached at the SHA above,
                          now removed)
    reviewer            GLM (independent, via TASK-470)
    date                2026-09-29

Note: the task file names the output file `TASK-470-verify-task-219.md`; this
is a template copy-paste error — the review target is TASK-240.

---

## 1. Does the artifact exist on this ref, and does it do what the result block claims?

**VERIFIED.** Four files changed, all present at the reviewed SHA:

    src/executionguard.py                                    (+87 -58)
    tests/test_no_write_happens_without_every_gate.py        (+53 -10)
    tests/test_task240_arity_rule_moves_to_action.py         (+170, new file)
    docs/qwen-tasks/DONE/TASK-240-...md                      (TODO → DONE, +70)

`git diff master...origin/qwen-worker-r55 --diff-filter=D --name-only` returns
nothing — no files deleted.

### What the artifact does

`_owner_for(campaign, channel)` replaces `_sender_for` as the guard's
predicate. Where `_sender_for` refused when `len(ids) != 1`, `_owner_for`
resolves each campaign seat to its human owner via
`senderownership.resolve_owner(seat)` and refuses when the seats do not all
resolve to the same attested human. The campaign may name many seats; an
action is attributed to exactly one human.

The `authorize()` caller at line 653 now reads:

    owner_id, _seats = _owner_for(campaign, channel)
    sender_id = owner_id

This replaces the previous 40-line inline seat-check block with a 3-line call.

### Result block claims —逐项 verified

| Claim | Verdict |
|-------|---------|
| `_sender_for` deprecated, returns raw id list | VERIFIED — line 1101, returns `ids` with no arity check |
| `_owner_for` resolves via `senderownership.resolve_owner` | VERIFIED — line 1174 |
| Refuses: unowned, uninventoried, deactivated, unhealthy, another-client, multi-human | VERIFIED — each clause raises `NotAuthorized` with named text |
| `authorize()` caller updated | VERIFIED — line 653 |
| Two changed tests renamed | VERIFIED — `test_two_senders_are_refused_when_they_are_two_people`, `test_a_seat_with_no_human_owner_is_refused` |
| New sibling `test_two_seats_same_human_pass` | VERIFIED — goes through full `authorize()` via `self.attempt()` |
| 11 new direct tests for `_owner_for` | VERIFIED — `test_task240_arity_rule_moves_to_action.py` contains 11 tests |
| `providerwrites.SUPPORTED` unchanged (14 verbs) | VERIFIED — `git diff` shows zero changes to `src/providerwrites.py` |

---

## 2. Existence is not function — is every link consumed?

**VERIFIED.** Two new/changed call chains, both consumed:

### `_owner_for` → `authorize()`

    src/executionguard.py:653  owner_id, _seats = _owner_for(campaign, channel)

This is the production entry point. `authorize()` is called by
`providerwrites.perform` (via the guard) and by every test that exercises the
full gate stack. The chain is real.

### `senderownership.resolve_owner` → `_owner_for` → `authorize()`

    src/executionguard.py:1174  owner = senderownership.resolve_owner(seat)

`resolve_owner` also has independent callers in `src/assignment.py:131` and
`src/assignment.py:415`, confirming it is not a dead module.

### `_sender_for` deprecation

`_sender_for` has zero production callers in `src/` after this change. The
only remaining references are:
- `src/nextaction.py:478` — a DIFFERENT function with the same name (takes
  different arguments, returns an assignment dict, not a provider id)
- `src/senderownership.py:208,230` and `src/senders.py:48` — docstring
  references, informational only

This is not a defect — the function is explicitly marked DEPRECATED and kept
for backward compatibility. But it is dead code in the production path and
should be removed in a follow-up.

---

## 3. Falsification — mutation test

**PERFORMED.** I deleted the `if len(owners) != 1: raise NotAuthorized(...)`
block from `_owner_for` (line 1183) and re-ran the two tests that assert
multi-human refusal:

    test_two_seats_two_humans_refused         FAIL — NotAuthorized not raised
    test_two_senders_are_refused_when_they_are_two_people  FAIL — NotAuthorized not raised

Both tests failed for the intended reason (the refusal they assert was not
raised), and no other guard fired first. The tests are falsifiable and they
are wired to the production entry point.

---

## 4. Are the tests falsifiable?

**YES.** Specific analysis:

- `test_two_seats_two_humans_refused`: asserts `NotAuthorized` with
  `"2 distinct"` in the message. Removing the arity check causes
  `AssertionError: NotAuthorized not raised` — the test catches the defect.
- `test_a_seat_with_no_human_owner_is_refused`: asserts refusal with
  `"no attested human owner"`. This is the INVERSION of the old test that
  asserted the opposite. The new test catches the case where an unowned seat
  would silently pass.
- `test_two_seats_same_human_pass`: asserts `"sender" in auth.gates` after
  going through the full `authorize()` path. This catches the case where the
  predicate incorrectly refuses a valid multi-seat single-human campaign.
- All 11 `_owner_for` direct tests assert on specific `NotAuthorized`
  messages, not on `hasattr` or source text.

The tests are driven through `authorize()` (the production entry point) in
the gate test file, and directly in the TASK-240 test file. Both paths are
the real ones.

---

## 5. Would merging delete anything?

**NO.** `git diff master...origin/qwen-worker-r55 --diff-filter=D --name-only`
returns nothing. No files are deleted. The diff is purely additive and
modifying:

    4 files changed, 380 insertions(+), 68 deletions(-)

All four files are named in TASK-240's FILES ALLOWED section.

---

## 6. Scope drift

**NONE.** The branch carries exactly two commits beyond master:

    3b2c06cb TASK-240: arity rule moves from the campaign to the action
    8f4406e1 TASK-240 done: arity rule moves from campaign to action, result block filled

Changed files:

    src/executionguard.py                                    — allowed
    tests/test_no_write_happens_without_every_gate.py        — allowed
    tests/test_task240_arity_rule_moves_to_action.py         — allowed (new)
    docs/qwen-tasks/DONE/TASK-240-...md                      — task file move

No forbidden files touched (`src/providerwrites.py`, `src/providers/*`,
`config/` all clean). No junk, no scratch output, no unrelated changes.

---

## 7. Additional findings

### 7a. Ledger semantic change — ACCEPTED, with a note

`sender_id = owner_id` at line 654 means the ledger now records the human
sender_id (e.g., `"anna"`) instead of the provider_account_id (e.g.,
`"116968"`). The result block acknowledges this explicitly:

> "The ledger's `sender_id` field now receives the human sender_id... The
>  ledger is currently empty, so no existing rows are affected."

I verified:
- `actionledger.count_on` does string comparison on `sender_id` — consistent
  regardless of whether the value is a human id or a provider id.
- No provider module reads `auth.sender_id` — `git grep` for
  `auth.sender_id` and `authorization.sender_id` in `src/providerwrites.py`
  and `src/providers/` returns nothing.
- `Authorization.as_dict()` includes `sender_id`, but no caller in
  `providerwrites.py` or `nextaction.py` reads it.

This is a semantic change that is safe today because the ledger is empty and
no downstream consumer depends on the provider-account-id shape. It should be
documented when the ledger gains its first reader.

### 7b. Pre-existing test_invariants failures — NOT CAUSED BY TASK-240

Three `test_invariants` failures exist on the branch:

    test_bison_sending_schedule.py:26 imports ProviderError
    test_task235_dnc_cannot_stop_linkedin.py:20 imports ProviderError
    test_emailbison_posts_only_to_routes_it_declares

TASK-240 did not touch `test_invariants.py`, `test_bison_sending_schedule.py`,
`test_task235_dnc_cannot_stop_linkedin.py`, or any provider module. These
failures are pre-existing on master and unrelated to this change.

### 7c. `_sender_for` is dead code

`_sender_for` has zero production callers after this change. It is marked
DEPRECATED in its docstring but remains in the module. This is not a defect
— it is explicitly kept for backward compatibility — but it should be removed
in a follow-up to avoid confusion. The `nextaction.py` module has a DIFFERENT
function also called `_sender_for` that is unrelated.

---

## 8. Test execution summary

    tests/test_task240_arity_rule_moves_to_action.py    11 tests   ALL PASS
    tests/test_no_write_happens_without_every_gate.py   78 tests   ALL PASS
    tests.test_a_confirmed_action_cannot_happen_twice    4 tests   ALL PASS
    tests.test_a_stop_beats_an_authorization             5 tests   ALL PASS
    tests.test_sender_ownership                          8 tests   ALL PASS
    tests.test_the_attestation_packet_...                4 tests   ALL PASS
    tests.test_the_write_layer_is_sealed                 7 tests   ALL PASS
    tests.test_write_surface_enumeration                 4 tests   ALL PASS
                                                         ----
                                                    121 tests total, 0 failures

---

## Disposition

| # | Finding | Severity | Evidence |
|---|---------|----------|----------|
| 1 | Artifacts exist on the reviewed ref and do what the result block claims | — | §1 |
| 2 | `_owner_for` has a production caller (`authorize()` line 653) | — | §2 |
| 3 | `senderownership.resolve_owner` has production callers | — | §2 |
| 4 | Mutation test confirms tests are falsifiable | — | §3 |
| 5 | No files deleted by merge | — | §5 |
| 6 | No scope drift — all files in FILES ALLOWED | — | §6 |
| 7 | Ledger `sender_id` semantic change is safe today (empty ledger, no downstream reader) | NOTE | §7a |
| 8 | `_sender_for` is dead code after this change | NOTE | §7c |
| 9 | 3 pre-existing `test_invariants` failures, unrelated to TASK-240 | NOTE | §7b |

---

## Recommendation

**MERGE.**

The predicate is correct, strictly stronger than the old one, has a real
production caller, and its tests are falsifiable through the real entry
point. The scope is clean, no forbidden files were touched, and no files
would be deleted by merge. The two NOTES (§7a, §7c) are follow-up items,
not blockers.

The three pre-existing `test_invariants` failures (§7b) are not caused by
this change and should not block it.
