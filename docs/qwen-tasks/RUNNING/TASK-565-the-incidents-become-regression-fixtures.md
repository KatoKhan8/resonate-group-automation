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

---

## COMPLETE AUDIT — 2026-09-29 (background agent completed)

### Incident-by-incident status

| # | Incident | Guard on Master? | Test on Master? | Verified? | Action Needed |
|---|----------|------------------|-----------------|-----------|---------------|
| 1 | Wrong-company copy | Partial (tenancy) | Partial | No | Needs specific fixture |
| 2 | Signature mismatch | No | No (branch only) | No | NEW fixture required |
| 3 | Unrendered variable | Yes (copylint.py:459,643) | Yes (test_copylint.py) | Rule exists | Mutation test needed |
| 4,5 | Unsupported figures | No (`_invented_quantities` on other branch) | Partial (claims.py) | No | Investigate claims.foreign_product |
| 6 | Refusal → another message | Yes (replies.py, leadstop.py) | Yes (extensive) | Likely | Verify lowest layer |
| 7 | Old approval reused | Yes (approval.py fingerprint) | Yes (extensive) | Likely | Verify lowest layer |
| 8 | Factory bypass | Yes (providers/__init__.py:733) | Yes | Exists | "Worktree-ineffective" per task |
| 9 | P.S. lost | Partial (linted, not traced) | Partial | No | End-to-end fixture needed |
| 10 | LinkedIn step lost | Partial (planner-level) | Partial | No | End-to-end fixture needed |

### Detailed findings

**Incident 1 (wrong-company copy):**
- `test_a_client_can_never_reach_another_client.py` — tenancy isolation
- `test_activation_refuses_without_the_operators_approval.py` — docstring describes the exact incident
- `test_the_provider_holds_what_was_approved.py` — cross-channel and tenancy fail
- GAP: No test reproduces wrong-copy-wrong-signature-wrong-mailbox combination

**Incident 2 (signature mismatch):**
- ABSENT from master per task file
- Negative controls exist on branch `task-p0a-signature-chain` (d93b0674)
- `test_the_sender_on_a_queue_row_is_a_dict.py` tests different bug (domain extraction)
- ACTION: New fixture required

**Incident 3 (unrendered variable):**
- `src/copylint.py:459` — rule in RULES tuple
- `src/copylint.py:479` — UNRENDERED_RE regex
- `src/copylint.py:643` — check fires and appends to offenders
- `test_a_blank_email_can_never_be_sent_again.py` — direct fixture of incident
- `src/emptyrender.py` — dedicated blank-email detection module
- STATUS: Rule exists and is NOT demoted (line 490+), meaning it REFUSES
- ACTION: Mutation test to prove removal breaks fixture

**Incidents 4,5 (unsupported figures):**
- `_invented_quantities` NOT on master (on branch `task-p0b-copy-engine-pareto`)
- `src/claims.py` — `foreign_product()` function exists
- `src/generate.py` — calls `foreign_product()` at lines 962, 1334, 1415, 1576
- `test_a_client_supplied_figure_licenses_no_claim_in_either_gate.py` — figure tests
- `test_copylint.py:112` — `test_an_invented_date_is_refused`
- `test_copylint.py:242` — `LinkedInAndPSTextIsCheckedByEveryRule` class
- ACTION: Investigate if `claims.foreign_product` is the right guard

**Incident 6 (refusal → another message):**
- `src/replies.py` — UNSUBSCRIBE_PATTERNS line 164, NEGATIVE_PATTERNS line 253
- `src/leadstop.py` — `stop_contact`, `stop_linkedin_contact`
- `src/eligibility.py` — BLOCKED_UNSUBSCRIBED
- `test_a_forwarding_assistant_is_not_a_refusal.py:112` — refusal stays NEGATIVE
- `test_an_assistant_is_not_a_buying_signal.py:112` — short refusals stay refusals
- `test_account_policy.py:66` — unsubscribe stops permanently
- STATUS: Strong coverage, needs lowest-layer verification

**Incident 7 (old approval reused):**
- `src/approval.py` — fingerprint-based approval
- `src/bisonfactory.py:1105` — `_certified_copy` function
- `test_an_approval_certifies_the_words_that_ship.py:85` — CertifiedCopyTest
- `test_an_approval_certifies_the_words_that_ship.py:254` — body edited after approval refuses
- `test_an_approval_survives_no_manual_change.py` — every material change invalidates
- STATUS: Strong coverage, fingerprint mechanism well-tested

**Incident 8 (factory bypass):**
- `src/providers/__init__.py:733` — `refuse_unauthorized_write` function
- `src/providers/__init__.py:763` — called before every `_urllib_transport`
- `src/providerwrites.py` — permission layer, SUPPORTED tuple
- `test_a_prompt_asking_nicely_is_not_a_security_boundary.py:313` — directly tests guard
- STATUS: Guard exists, task says "worktree-ineffective" — needs investigation

**Incident 9 (P.S. lost):**
- `src/copystages.py:471` — P.S. variant included in writer output
- `src/copyprompts.py:404` — `PS_VARIANTS` and `ps_variant_for()`
- `test_copylint.py:242` — `LinkedInAndPSTextIsCheckedByEveryRule`
- `test_only_the_last_subject_may_claim_finality.py:231` — P.S. finality refused
- GAP: No test verifies P.S. survives end-to-end to provider payload
- ACTION: End-to-end fixture needed

**Incident 10 (LinkedIn step lost):**
- `src/heyreachfactory.py:226` — `assemble_linkedin_copy` function
- `test_task025_funnel_unproven_held.py:83` — `test_no_step_is_silently_dropped`
- `test_the_linkedin_graph_follows_the_canonical_days.py:217` — all node types present
- `test_a_linkedin_approval_certifies_the_words_that_ship.py` — LinkedIn certified copy
- GAP: No test traces LinkedIn step from generation to HeyReach payload
- ACTION: End-to-end fixture needed

### Guard layers (from executionguard.py:33-43)

1. **tenancy** — which estate
2. **approval** — fingerprint-based word certification
3. **readback** — provider currently holds the words
4. **jit** — suppression, collision, fatigue, sender health
5. **cap** — durable ledger cap
6. **ledger** — reserve the key
7. **killswitch** — operator stop button

### Work required

**Immediate (if unblocked):**
1. Verify incident 3 blocks (mutation test on copylint.unrendered_variable)
2. Investigate incidents 4,5 (is claims.foreign_product the right guard?)
3. Verify incident 8 (what does "worktree-ineffective" mean?)
4. Write incident 2 fixture (signature mismatch) — ABSENT from master
5. Write incident 9 fixture (P.S. end-to-end) — GAP identified
6. Write incident 10 fixture (LinkedIn step end-to-end) — GAP identified

**Extended:**
7. Write incident 1 fixture (wrong-company copy specific shape)
8. Verify incidents 6, 7 at lowest layer
9. Mutation test all 10 fixtures

### Blocker status

**TASK-906 dependency:** Not found in queue. Task requires Brand IQ artifact before starting. Brand IQ referenced in docs but completion status unclear.

**Decision required:** Is this task BLOCKED on TASK-906, or can it proceed with the audit and fixture writing?
