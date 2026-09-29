PRIORITY: P1
SIZE: L
DEPENDS: TASK-906

# TASK-565 — every real incident becomes a regression fixture

**Operator, Zvonimir, 2026-09-28. PART OF THE ACCEPTANCE BOUNDARY.**

**The one-real-account artifact is not evidence of production safety until
BOTH TASK-564 and this task are independently verified.** Historical
incidents are not documentation. They are **permanent regression
requirements**.

**THE BOUNDARY CONDITION, stated exactly:** for each fixture you must prove
that **removing or bypassing the ACTUAL LOWEST-LAYER GUARD makes that
fixture FAIL.** Not a guard near it, and not a symptom one layer above —
the real one. A fixture that survives the removal of the thing it is
supposed to depend on is testing something else. Write these **after the
Brand IQ artifact exists and before any canary.** Do not start earlier — the
artifact is the priority and these must not compete with it.

## The rule for where each one lives
**Each fixture goes at the LOWEST LAYER THAT PREVENTS THE REAL EFFECT.** Not at
the layer where the bug happened to be found. A test that asserts a symptom one
layer above the guard passes when the guard is removed — that exact failure was
measured here on 2026-09-28: a bypass mutation left a test green because a
*different* guard produced a HELD instead of a BLOCK.

## The ten
1. **Wrong-company copy sent from a Productive mailbox** — 64 emails carrying
   another agency's pitch, signed with the operator's name, from 503/504/505.
2. **Signature not matching the mailbox owner.**
3. **Empty body from unresolved variables** — 77 emails with an empty subject
   and a `<p></p>` body, 2026-09-23.
4. **An unsupported figure on an email.**
5. **An unsupported figure on a LinkedIn message.**
6. **A prospect who replied "no thank you" receiving another message** —
   happened 2026-09-23, seven minutes after the refusal.
7. **An old approval reused after the copy changed.**
8. **A direct `create_lead` / attach bypassing the factory.**
9. **The P.S. lost before it reaches the provider.**
10. **A LinkedIn step lost before HeyReach** — see TASK-548.

## STEP ONE: mark which already exist, and VERIFY rather than assume
My own reading, **all UNVERIFIED — check each before writing anything**:

    2   negative controls exist on branch task-p0a-signature-chain (d93b0674),
        NOT on master
    3   `unrendered_variable` exists; whether it BLOCKS is unverified
    4,5 `_invented_quantities` exists on task-p0b-copy-engine-pareto
        (556593a0) and carries the defect TASK-557 fixes
    8   `refuse_unauthorized_write` exists but is worktree-ineffective
    1,6,7,9,10  believed ABSENT

**Do not rewrite a fixture that already exists** — extend it or say it is
covered. **Do not claim one exists without running it.**

## Each fixture must
- reproduce the **real effect**, not a paraphrase of it
- **FAIL if its guard is removed** — prove that with a mutation, restore
  byte-identical by sha256
- carry a **control** proving it does not refuse everything
- name the incident it descends from, in the test's own docstring, so the next
  person knows why it exists

## Rules
No prospect data in a tracked file — these are real incidents and real people;
use the shapes, never the identities. **Never weaken a gate to make a fixture
pass.** Provider writes 0, `sending.live` false, freeze active. Suite logs
outside the repository; compare the baseline **as sets**; derive a suite verdict
from a `Ran N tests` line, never from `$?`. Commit, push, verify the remote
after your last commit. Report **CLAIM / AUTHORITY / MEASURED AT / STATE**.

---

## AUDIT IN PROGRESS — 2026-09-29

### BLOCKER: TASK-906 dependency not found

The task file states `DEPENDS: TASK-906` and requires the Brand IQ artifact to
exist before starting. No task file for TASK-906 exists in `docs/qwen-tasks/`
in any state directory (TODO, RUNNING, REVIEW, DONE). The Brand IQ artifact is
referenced in docs but its completion status is unclear.

**Decision required:** Is TASK-906 complete, or is this task BLOCKED on it?

### STEP ONE audit findings (preliminary)

**Guards found on master:**

1. **Incident 3 (unrendered_variable)** — `src/copylint.py:459,643`
   - Rule exists in RULES list
   - UNRENDERED_RE regex at line 478
   - Check applied at line 643
   - **Status:** EXISTS, needs verification that it BLOCKS (not just warns)
   - **Test coverage:** `test_copylint.py` exists but needs mutation check

2. **Incident 8 (refuse_unauthorized_write)** — `src/providers/__init__.py:733`
   - Function defined and called before every write
   - Raises ProviderWriteRefused
   - **Status:** EXISTS, task says "worktree-ineffective"
   - **Test coverage:** `test_a_prompt_asking_nicely_is_not_a_security_boundary.py`

3. **Incidents 4,5 (unsupported figures)** — `_invented_quantities` NOT on master
   - Task says it exists on branch `task-p0b-copy-engine-pareto` (556593a0)
   - On master: `claims.foreign_product()` exists in `src/claims.py`
   - Used in `src/generate.py` at lines 962, 1334, 1415, 1576
   - **Status:** Different implementation than expected, needs investigation
   - **Test coverage:** `test_a_client_supplied_figure_licenses_no_claim_in_either_gate.py`

4. **Incident 6 (reply after opt-out)** — Reply stopping exists
   - `src/leadstop.py` has stop_contact and stop_linkedin_contact
   - `src/inbound.py` handles reply processing
   - `src/eligibility.py` has BLOCKED_UNSUBSCRIBED
   - **Status:** Guard exists, needs fixture
   - **Test coverage:** `test_the_reply_path_may_stop_and_nothing_else.py`,
     `test_a_linkedin_reply_stops_email_inside_fifteen_minutes.py`

**Guards NOT found on master (believed ABSENT per task):**

- Incident 1 (wrong-company copy) — no specific test found
- Incident 2 (signature mismatch) — signature tests exist but for Slack/webhook,
  not email signature matching mailbox owner
- Incident 7 (stale approval reuse) — stale approval tests exist but not for
  copy change scenario
- Incident 9 (P.S. lost) — no specific test found
- Incident 10 (LinkedIn step lost) — no specific test found

### Next steps required

1. **Clarify TASK-906 dependency** — is this task BLOCKED or can it proceed?
2. **Verify incident 3 blocks** — run mutation test on copylint.unrendered_variable
3. **Investigate incidents 4,5** — is claims.foreign_product the right guard?
4. **Verify incident 8** — what does "worktree-ineffective" mean?
5. **Write missing fixtures** — incidents 1,2,7,9,10 need new tests
6. **Mutation testing** — each fixture must fail when its guard is removed

### Files examined

- `src/copylint.py` — unrendered_variable rule
- `src/providers/__init__.py` — refuse_unauthorized_write
- `src/claims.py` — foreign_product (figure checking)
- `src/generate.py` — uses claims.foreign_product
- `src/leadstop.py` — stop_contact functions
- `src/inbound.py` — reply handling
- `src/eligibility.py` — BLOCKED_UNSUBSCRIBED
- `tests/test_copylint.py` — existing copylint tests
- `tests/test_the_reply_path_may_stop_and_nothing_else.py` — reply stop tests
- `tests/test_a_client_supplied_figure_licenses_no_claim_in_either_gate.py` — figure tests
